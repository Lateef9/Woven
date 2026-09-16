from contextlib import asynccontextmanager
from fastapi import FastAPI
from database import db_manager
from schemas import Message
from llm_service import ask_llm

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
    print(f"Received validated message: {message}")
    return {"status": "received"}

@app.get("/test-llm")
async def test_llm(query: str):
    answer = await ask_llm(query)
    return {"query": query, "answer": answer}
