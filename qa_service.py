import json
import litellm
from llm_service import route_query
from vector_store import retrieve_facts
from graph_store import retrieve_graph_context

SYSTEM_PROMPT = (
    "Answer using ONLY the provided context. If the context is insufficient, "
    "say you do not know. Be concise. Cite supporting context items inline "
    "as [1], [2], etc., matching the numbered items in the context. "
    "Do not invent citations that are not in the context."
)


def _build_context_and_citations(
    semantic_hits: list[dict], graph_hits: list[dict]
) -> tuple[str, list[dict]]:
    """
    Number semantic + graph hits continuously and build citation metadata.
    Returns (context_text, citations).
    """
    lines: list[str] = []
    citations: list[dict] = []
    index = 1

    for hit in semantic_hits:
        fact = hit.get("fact_text") or ""
        source_id = hit.get("source_message_id") or None
        citation: dict = {
            "index": index,
            "type": "fact",
            "text": fact,
        }
        if source_id:
            citation["source_message_id"] = source_id
        citations.append(citation)

        source_part = f" (source_message_id={source_id})" if source_id else ""
        lines.append(f"[{index}] {fact}{source_part}")
        index += 1

    for hit in graph_hits:
        source = hit.get("source") or ""
        relation = hit.get("relation") or ""
        target = hit.get("target") or ""
        source_entity_id = hit.get("source_id") or ""
        target_entity_id = hit.get("target_id") or ""
        text = f"{source} -[{relation}]-> {target}"
        citations.append({
            "index": index,
            "type": "graph",
            "text": text,
        })

        id_parts = []
        if source_entity_id:
            id_parts.append(f"source_id={source_entity_id}")
        if target_entity_id:
            id_parts.append(f"target_id={target_entity_id}")
        id_part = f" ({', '.join(id_parts)})" if id_parts else ""
        lines.append(f"[{index}] {text}{id_part}")
        index += 1

    if not lines:
        return "No context available.", []

    return "\n".join(lines), citations


async def _prepare_qa(question: str) -> tuple[str, list[dict], list[dict], list[dict], str]:
    """Route + retrieve + build prompts. Returns (route, semantic_hits, graph_hits, citations, user_prompt)."""
    question = (question or "").strip()
    decision = await route_query(question)
    route = decision.route

    semantic_hits: list[dict] = []
    graph_hits: list[dict] = []

    if route in ("semantic", "both"):
        semantic_hits = retrieve_facts(query=question, limit=5)

    if route in ("graph", "both"):
        graph_hits = await retrieve_graph_context(query=question, limit=10)

    context, citations = _build_context_and_citations(semantic_hits, graph_hits)
    user_prompt = f"Question: {question}\n\nContext:\n{context}"
    return route, semantic_hits, graph_hits, citations, user_prompt


async def answer_question(question: str) -> dict:
    """
    Route a question to semantic and/or graph retrieval, then answer from that context only.
    """
    route, semantic_hits, graph_hits, citations, user_prompt = await _prepare_qa(question)

    try:
        response = await litellm.acompletion(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        answer = response.choices[0].message.content or ""
    except Exception as e:
        print(f"Error generating answer: {e}")
        answer = "I do not know. The answer model failed and no reliable response could be produced."

    return {
        "answer": answer,
        "route": route,
        "semantic_hits": semantic_hits,
        "graph_hits": graph_hits,
        "citations": citations,
    }


async def stream_answer(question: str):
    """
    Async generator yielding SSE-compatible dicts for EventSourceResponse.
    Streams text deltas as default message events, then a final `done` event with metadata.
    """
    citations: list[dict] = []
    try:
        route, semantic_hits, graph_hits, citations, user_prompt = await _prepare_qa(question)
    except Exception as e:
        print(f"Error preparing streamed answer: {e}")
        yield {"event": "error", "data": "Failed to prepare answer context."}
        yield {
            "event": "done",
            "data": json.dumps({
                "route": "both",
                "semantic_hits": [],
                "graph_hits": [],
                "citations": [],
            }),
        }
        return

    try:
        response = await litellm.acompletion(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            stream=True,
        )
        async for chunk in response:
            try:
                delta = chunk.choices[0].delta.content
            except (AttributeError, IndexError, TypeError):
                delta = None
            if delta:
                yield {"data": delta}
    except Exception as e:
        print(f"Error streaming answer: {e}")
        yield {
            "data": "I do not know. The answer model failed and no reliable response could be produced."
        }

    yield {
        "event": "done",
        "data": json.dumps({
            "route": route,
            "semantic_hits": semantic_hits,
            "graph_hits": graph_hits,
            "citations": citations,
        }),
    }
