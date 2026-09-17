from contextlib import asynccontextmanager
from fastapi import FastAPI
from database import db_manager
from schemas import Message
from llm_service import ask_llm, extract_facts
from vector_store import save_fact, search_facts

@asynccontextmanager
async def lifespan(app: FastAPI):
    db_manager.connect()
    yield
    db_manager.close()

app = FastAPI(lifespan=lifespan)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Woven"}

@app.post("/test-db")
async def test_db():
    result = await db_manager.channels.insert_one({"name": "test_channel", "platform": "slack"})
    return {"id": str(result.inserted_id)}

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
        
    return {"status": "received", "facts_extracted": len(facts)}

@app.get("/search-facts")
async def search_facts_endpoint(query: str):
    results = search_facts(query)
    return {"query": query, "results": results}

@app.get("/test-llm")
async def test_llm(query: str):
    answer = await ask_llm(query)
    return {"query": query, "answer": answer}
