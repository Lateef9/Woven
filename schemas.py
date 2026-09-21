from pydantic import BaseModel
from datetime import datetime
from typing import Literal

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

class Entity(BaseModel):
    id: str
    type: str
    name: str

class Relationship(BaseModel):
    source_entity_id: str
    target_entity_id: str
    relation_type: str

class GraphExtractionResult(BaseModel):
    entities: list[Entity]
    relationships: list[Relationship]

class RouteDecision(BaseModel):
    route: Literal["semantic", "graph", "both"]
    reason: str

class AskRequest(BaseModel):
    question: str
