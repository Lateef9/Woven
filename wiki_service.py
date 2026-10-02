from datetime import datetime, timezone

from database import db_manager
from graph_store import list_person_entities, list_triples_for_names
from llm_service import ask_llm
from vector_store import list_facts_by_message_ids


async def list_wiki_channels() -> list[dict]:
    """
    Channels that have ingested messages (and therefore can have wiki content).
    Prefers the channels collection; falls back to distinct channels on messages.
    """
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
            # Keep only channels that actually have messages
            with_msgs = set()
            pipeline = [
                {"$group": {"_id": "$channel.channel_id"}},
                {"$match": {"_id": {"$ne": None}}},
            ]
            for row in await db_manager.messages.aggregate(pipeline).to_list(length=500):
                with_msgs.add(row["_id"])
            filtered = [c for c in channels if c["channel_id"] in with_msgs]
            return filtered or channels

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
        print(f"Error listing wiki channels: {e}")
        return []


async def _channel_messages(channel_id: str) -> list[dict]:
    cursor = db_manager.messages.find(
        {"channel.channel_id": channel_id},
        {
            "_id": 0,
            "message_id": 1,
            "text": 1,
            "author": 1,
            "channel": 1,
        },
    )
    return await cursor.to_list(length=1000)


def _filter_people_for_channel(
    people: list[dict],
    messages: list[dict],
    facts: list[dict],
) -> list[dict]:
    """Keep Person entities mentioned in channel messages/facts, or channel authors."""
    corpus_parts: list[str] = []
    author_names: set[str] = set()

    for msg in messages:
        text = (msg.get("text") or "").strip()
        if text:
            corpus_parts.append(text)
        author = msg.get("author") or {}
        name = (author.get("name") or "").strip()
        if name:
            author_names.add(name.lower())
            corpus_parts.append(name)

    for fact in facts:
        ft = (fact.get("fact_text") or "").strip()
        if ft:
            corpus_parts.append(ft)

    corpus = "\n".join(corpus_parts).lower()
    if not corpus and not author_names:
        return []

    matched: list[dict] = []
    seen: set[str] = set()
    for person in people:
        name = (person.get("name") or "").strip()
        pid = (person.get("id") or "").strip()
        key = pid or name.lower()
        if not name or key in seen:
            continue
        name_l = name.lower()
        if name_l in author_names or name_l in corpus or (pid and pid.lower() in corpus):
            seen.add(key)
            matched.append({
                "id": pid,
                "name": name,
                "type": person.get("type") or "Person",
            })
    return matched


async def _get_cached_overview(channel_id: str) -> str | None:
    try:
        doc = await db_manager.wiki_pages.find_one(
            {"channel_id": channel_id},
            {"_id": 0, "overview": 1},
        )
        if doc and isinstance(doc.get("overview"), str) and doc["overview"].strip():
            return doc["overview"].strip()
    except Exception as e:
        print(f"Error reading wiki_pages cache: {e}")
    return None


async def _cache_overview(channel_id: str, overview: str) -> None:
    try:
        await db_manager.wiki_pages.update_one(
            {"channel_id": channel_id},
            {
                "$set": {
                    "channel_id": channel_id,
                    "overview": overview,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
    except Exception as e:
        print(f"Error caching wiki overview: {e}")


async def _generate_overview(channel_name: str, facts: list[dict]) -> str:
    top_facts = [f.get("fact_text") or "" for f in facts[:12] if f.get("fact_text")]
    if not top_facts:
        return f"No facts yet for #{channel_name}. Ingest more conversation to build this wiki page."

    fact_lines = "\n".join(f"- {t}" for t in top_facts)
    prompt = (
        f"Write a short wiki overview (2-4 sentences) for the Slack/chat channel "
        f"#{channel_name}. Use ONLY the facts below. Be clear and neutral; "
        f"do not invent details.\n\nFacts:\n{fact_lines}"
    )
    try:
        overview = (await ask_llm(prompt) or "").strip()
        if overview:
            return overview
    except Exception as e:
        print(f"Error generating wiki overview: {e}")

    return f"#{channel_name} has {len(top_facts)} extracted fact(s). Overview generation failed."


async def get_wiki_channel_page(channel_id: str) -> dict | None:
    """
    Build a per-channel wiki page: overview, facts, people, relationships.
    Returns None if the channel has no messages.
    """
    channel_id = (channel_id or "").strip()
    if not channel_id:
        return None

    messages = await _channel_messages(channel_id)
    if not messages:
        # Still allow if channel doc exists but empty? User asked for channels with facts/messages.
        return None

    channel_meta = messages[0].get("channel") or {}
    channel_name = channel_meta.get("name") or channel_id
    platform = channel_meta.get("platform") or "mock"

    # Prefer name/platform from channels collection when available
    try:
        ch_doc = await db_manager.channels.find_one(
            {"channel_id": channel_id},
            {"_id": 0, "name": 1, "platform": 1},
        )
        if ch_doc:
            channel_name = ch_doc.get("name") or channel_name
            platform = ch_doc.get("platform") or platform
    except Exception as e:
        print(f"Error loading channel metadata: {e}")

    message_ids = [m.get("message_id") for m in messages if m.get("message_id")]
    facts = list_facts_by_message_ids(message_ids, limit=100)

    all_people = await list_person_entities(limit=200)
    people = _filter_people_for_channel(all_people, messages, facts)

    # Relationship names: people + tokens from facts for broader graph context
    name_seeds = [p["name"] for p in people]
    for msg in messages:
        author = (msg.get("author") or {}).get("name")
        if author:
            name_seeds.append(author)

    relationships = await list_triples_for_names(name_seeds, limit=50)
    # If no people-seeded triples, fall back to triples mentioning anything in fact text
    if not relationships and facts:
        # Pull entity-like capitalized tokens is fragile; use person list globally filtered
        # by fact corpus already applied — broaden seeds with words from facts
        extra: list[str] = []
        for f in facts:
            for token in (f.get("fact_text") or "").replace(",", " ").split():
                if len(token) > 2 and token[0].isupper():
                    extra.append(token.strip(".,;:\"'"))
        relationships = await list_triples_for_names(name_seeds + extra, limit=50)

    overview = await _get_cached_overview(channel_id)
    if overview is None:
        overview = await _generate_overview(channel_name, facts)
        await _cache_overview(channel_id, overview)

    return {
        "channel_id": channel_id,
        "name": channel_name,
        "platform": platform,
        "overview": overview,
        "facts": facts,
        "people": people,
        "relationships": relationships,
    }
