from contextlib import asynccontextmanager
from fastapi import FastAPI
from database import db_manager
from graph_store import neo4j_manager, save_graph_data, clear_graph_data, retrieve_graph_context
from schemas import Message
from llm_service import ask_llm, extract_facts, extract_graph_data
from vector_store import save_fact, search_facts, retrieve_facts, clear_facts

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
            result = await db_manager.channels.delete_many({})
            mongo_deleted = result.deleted_count
            print(f"Cleared {mongo_deleted} documents from MongoDB channels.")
    except Exception as e:
        print(f"Error clearing MongoDB: {e}")
    return {
        "status": "cleared",
        "weaviate": "Fact collection reset",
        "neo4j": "Entity nodes deleted",
        "mongodb_channels_deleted": mongo_deleted,
    }

@app.post("/ingest-mock")
async def ingest_mock(message: Message):
    print(f"Received validated message from {message.author.name}: {message.text}")
    
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

@app.get("/test-llm")
async def test_llm(query: str):
    answer = await ask_llm(query)
    return {"query": query, "answer": answer}
