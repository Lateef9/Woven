import litellm
from llm_service import route_query
from vector_store import retrieve_facts
from graph_store import retrieve_graph_context


def _build_context(semantic_hits: list[dict], graph_hits: list[dict]) -> str:
    sections: list[str] = []

    if semantic_hits:
        lines = []
        for i, hit in enumerate(semantic_hits, start=1):
            fact = hit.get("fact_text") or ""
            score = hit.get("score")
            score_part = f" (score={score:.3f})" if isinstance(score, (int, float)) else ""
            lines.append(f"{i}. {fact}{score_part}")
        sections.append("Semantic facts:\n" + "\n".join(lines))

    if graph_hits:
        lines = []
        for i, hit in enumerate(graph_hits, start=1):
            source = hit.get("source") or ""
            relation = hit.get("relation") or ""
            target = hit.get("target") or ""
            lines.append(f"{i}. {source} -[{relation}]-> {target}")
        sections.append("Graph relationships:\n" + "\n".join(lines))

    if not sections:
        return "No context available."

    return "\n\n".join(sections)


async def answer_question(question: str) -> dict:
    """
    Route a question to semantic and/or graph retrieval, then answer from that context only.
    """
    question = (question or "").strip()
    decision = await route_query(question)
    route = decision.route

    semantic_hits: list[dict] = []
    graph_hits: list[dict] = []

    if route in ("semantic", "both"):
        semantic_hits = retrieve_facts(query=question, limit=5)

    if route in ("graph", "both"):
        graph_hits = await retrieve_graph_context(query=question, limit=10)

    context = _build_context(semantic_hits, graph_hits)

    system_prompt = (
        "Answer using ONLY the provided context. If the context is insufficient, "
        "say you do not know. Be concise. Mention which facts or relationships "
        "support the answer."
    )
    user_prompt = (
        f"Question: {question}\n\n"
        f"Context:\n{context}"
    )

    try:
        response = await litellm.acompletion(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
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
    }
