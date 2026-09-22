from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from database import db_manager
from graph_store import neo4j_manager, save_graph_data, clear_graph_data, retrieve_graph_context
from schemas import Message, AskRequest
from llm_service import ask_llm, extract_facts, extract_graph_data, route_query
from vector_store import save_fact, search_facts, retrieve_facts, clear_facts
from qa_service import answer_question, stream_answer

@asynccontextmanager
async def lifespan(app: FastAPI):
    db_manager.connect()
    neo4j_manager.connect()
    yield
    await neo4j_manager.close()
    db_manager.close()

app = FastAPI(lifespan=lifespan)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Woven"}

@app.post("/test-db")
async def test_db():
    result = await db_manager.channels.insert_one({"name": "test_channel", "platform": "slack"})
    return {"id": str(result.inserted_id)}

@app.get("/test-neo4j")
async def test_neo4j():
    result = await neo4j_manager.verify_connectivity()
    return {"status": "ok", "result": result}

@app.post("/clear-stores")
async def clear_stores():
    """Wipe previous mock data from Weaviate, Neo4j, and Mongo before a fresh ingest."""
    clear_facts()
    await clear_graph_data()
    mongo_deleted = 0
    try:
        if db_manager.channels is not None:
            channels_result = await db_manager.channels.delete_many({})
            mongo_deleted += channels_result.deleted_count
        if db_manager.messages is not None:
            messages_result = await db_manager.messages.delete_many({})
            mongo_deleted += messages_result.deleted_count
            print(f"Cleared MongoDB channels/messages ({mongo_deleted} docs).")
    except Exception as e:
        print(f"Error clearing MongoDB: {e}")
    return {
        "status": "cleared",
        "weaviate": "Fact collection reset",
        "neo4j": "Entity nodes deleted",
        "mongodb_docs_deleted": mongo_deleted,
    }

@app.post("/ingest-mock")
async def ingest_mock(message: Message):
    print(f"Received validated message from {message.author.name}: {message.text}")

    # Persist channel + message so Channels page (and fallbacks) have data
    try:
        await db_manager.channels.update_one(
            {"channel_id": message.channel.channel_id},
            {
                "$set": {
                    "channel_id": message.channel.channel_id,
                    "name": message.channel.name,
                    "platform": message.channel.platform,
                }
            },
            upsert=True,
        )
        await db_manager.messages.update_one(
            {"message_id": message.message_id},
            {"$set": message.model_dump(mode="json")},
            upsert=True,
        )
    except Exception as e:
        print(f"Error persisting message/channel to MongoDB: {e}")
    
    # Extract facts from the message text
    facts = await extract_facts(message.text)
    
    print(f"Extracted {len(facts)} facts:")
    for fact in facts:
        print(f" - [{fact.confidence_score}] {fact.fact_text}")
        # Save each extracted fact to Weaviate
        save_fact(fact.fact_text, message.message_id)
        
    # Extract graph data from the message text
    graph_data = await extract_graph_data(message.text)
    
    print(f"Extracted {len(graph_data.entities)} entities and {len(graph_data.relationships)} relationships:")
    for entity in graph_data.entities:
        print(f" - Entity: {entity.name} ({entity.type}) [ID: {entity.id}]")
    for rel in graph_data.relationships:
        print(f" - Rel: {rel.source_entity_id} -[{rel.relation_type}]-> {rel.target_entity_id}")

    # Persist graph extraction into Neo4j (errors are logged, not raised)
    await save_graph_data(graph_data)
        
    return {
        "status": "received", 
        "facts_extracted": len(facts),
        "entities_extracted": len(graph_data.entities),
        "relationships_extracted": len(graph_data.relationships)
    }

@app.get("/api/channels")
async def list_channels():
    """Return known channels from MongoDB, or derive them from ingested messages."""
    try:
        docs = await db_manager.channels.find(
            {},
            {"_id": 0, "channel_id": 1, "name": 1, "platform": 1},
        ).to_list(length=500)

        channels = [
            {
                "channel_id": d.get("channel_id") or "",
                "name": d.get("name") or "",
                "platform": d.get("platform") or "mock",
            }
            for d in docs
            if d.get("channel_id")
        ]

        if channels:
            return channels

        # Fallback: unique channels from ingested messages
        pipeline = [
            {
                "$group": {
                    "_id": "$channel.channel_id",
                    "name": {"$first": "$channel.name"},
                    "platform": {"$first": "$channel.platform"},
                }
            },
            {"$match": {"_id": {"$ne": None}}},
            {"$sort": {"name": 1}},
        ]
        derived = await db_manager.messages.aggregate(pipeline).to_list(length=500)
        return [
            {
                "channel_id": d["_id"],
                "name": d.get("name") or d["_id"],
                "platform": d.get("platform") or "mock",
            }
            for d in derived
        ]
    except Exception as e:
        print(f"Error listing channels: {e}")
        return []

@app.get("/search-facts")
async def search_facts_endpoint(query: str):
    results = search_facts(query)
    return {"query": query, "results": results}

@app.get("/retrieve/semantic")
async def retrieve_semantic(query: str, limit: int = 5):
    results = retrieve_facts(query=query, limit=limit)
    return {"query": query, "limit": limit, "results": results}

@app.get("/retrieve/graph")
async def retrieve_graph(query: str, limit: int = 10):
    results = await retrieve_graph_context(query=query, limit=limit)
    return {"query": query, "limit": limit, "results": results}

@app.get("/route")
async def route(query: str):
    decision = await route_query(query)
    return {"query": query, "route": decision.route, "reason": decision.reason}

@app.get("/api/ask")
async def ask_get(question: str):
    return await answer_question(question)

@app.post("/api/ask")
async def ask_post(body: AskRequest):
    return await answer_question(body.question)

@app.get("/api/ask/stream")
async def ask_stream(question: str):
    async def event_generator():
        async for item in stream_answer(question):
            event = item.get("event")
            data = item.get("data", "")
            if event:
                yield f"event: {event}\ndata: {data}\n\n"
            else:
                yield f"data: {data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@app.get("/test-llm")
async def test_llm(query: str):
    answer = await ask_llm(query)
    return {"query": query, "answer": answer}
