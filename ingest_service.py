from database import db_manager
from graph_store import save_graph_data
from llm_service import extract_facts, extract_graph_data
from schemas import AtomicFact, Message
from vector_store import save_fact


async def ingest_message(message: Message) -> dict:
    """Shared ingest pipeline: validate → Mongo → Weaviate facts → Neo4j graph."""
    print(
        f"Ingest request platform={message.channel.platform} "
        f"channel_id={message.channel.channel_id} message_id={message.message_id}"
    )

    # Persist channel + raw message so Channels page (and fallbacks) have data
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

    # Extract + save facts (Weaviate)
    facts = await extract_facts(message.text)

    # Pleasantries / thin messages often yield zero facts; keep a searchable fallback
    # so Slack/live ingest still reaches semantic Ask.
    if not facts and message.text.strip():
        facts = [
            AtomicFact(
                fact_text=(
                    f"{message.author.name} said in #{message.channel.name}: "
                    f"{message.text.strip()}"
                ),
                confidence_score=0.5,
            )
        ]
        print("No LLM facts extracted; storing raw message as fallback fact.")

    print(f"Extracted {len(facts)} facts:")
    for fact in facts:
        print(f" - [{fact.confidence_score}] {fact.fact_text}")
        save_fact(fact.fact_text, message.message_id)

    # Extract + save graph (Neo4j)
    graph_data = await extract_graph_data(message.text)

    print(
        f"Extracted {len(graph_data.entities)} entities and "
        f"{len(graph_data.relationships)} relationships:"
    )
    for entity in graph_data.entities:
        print(f" - Entity: {entity.name} ({entity.type}) [ID: {entity.id}]")
    for rel in graph_data.relationships:
        print(f" - Rel: {rel.source_entity_id} -[{rel.relation_type}]-> {rel.target_entity_id}")

    await save_graph_data(graph_data)

    return {
        "status": "ok",
        "message_id": message.message_id,
        "facts_saved": len(facts),
        "entities_saved": len(graph_data.entities),
    }
