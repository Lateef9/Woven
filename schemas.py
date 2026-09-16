from pydantic import BaseModel
from datetime import datetime

class User(BaseModel):
    user_id: str
    name: str
    platform: str

class Channel(BaseModel):
    channel_id: str
    name: str
    platform: str

class Message(BaseModel):
    message_id: str
    text: str
    timestamp: datetime
    author: User
    channel: Channel

class AtomicFact(BaseModel):
    fact_text: str
    confidence_score: float

class FactList(BaseModel):
    facts: list[AtomicFact]
