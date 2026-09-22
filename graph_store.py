import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase
from schemas import GraphExtractionResult

load_dotenv()


class Neo4jManager:
    driver = None

    @classmethod
    def connect(cls):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")

        cls.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        print(f"Connected to Neo4j at {uri}")

    @classmethod
    async def close(cls):
        if cls.driver:
            await cls.driver.close()
            cls.driver = None
            print("Neo4j connection closed.")

    @classmethod
    async def verify_connectivity(cls) -> dict:
        """Runs a simple Cypher query to confirm the driver works."""
        async with cls.driver.session() as session:
            result = await session.run("RETURN 1 AS num")
            record = await result.single()
            return {"num": record["num"]}


neo4j_manager = Neo4jManager()


async def clear_graph_data() -> None:
    """Deletes all Entity nodes and RELATION edges from Neo4j."""
    if not neo4j_manager.driver:
        print("Error clearing graph data: Neo4j driver is not connected.")
        return

    try:
        async with neo4j_manager.driver.session() as session:
            await session.run("MATCH (n:Entity) DETACH DELETE n")
        print("Cleared all Entity nodes and relationships from Neo4j.")
    except Exception as e:
        print(f"Error clearing Neo4j graph data: {e}")


async def save_graph_data(extraction_result: GraphExtractionResult) -> None:
    """
    Persists extracted entities and relationships into Neo4j using MERGE.
    Errors are logged and do not raise, so callers can keep running.
    """
    if not neo4j_manager.driver:
        print("Error saving graph data: Neo4j driver is not connected.")
        return

    if not extraction_result.entities and not extraction_result.relationships:
        return

    entities = [
        {"id": e.id, "name": e.name, "type": e.type}
        for e in extraction_result.entities
    ]
    relationships = [
        {
            "source_entity_id": r.source_entity_id,
            "target_entity_id": r.target_entity_id,
            "relation_type": r.relation_type,
        }
        for r in extraction_result.relationships
    ]

    try:
        async with neo4j_manager.driver.session() as session:
            if entities:
                await session.run(
                    """
                    UNWIND $entities AS e
                    MERGE (n:Entity {id: e.id})
                    SET n.name = e.name, n.type = e.type
                    """,
                    entities=entities,
                )

            if relationships:
                await session.run(
                    """
                    UNWIND $relationships AS r
                    MATCH (src:Entity {id: r.source_entity_id}),
                          (tgt:Entity {id: r.target_entity_id})
                    MERGE (src)-[rel:RELATION {type: r.relation_type}]->(tgt)
                    """,
                    relationships=relationships,
                )

        print(
            f"Successfully saved {len(entities)} entities and "
            f"{len(relationships)} relationships to Neo4j."
        )
    except Exception as e:
        print(f"Error saving graph data to Neo4j: {e}")


async def retrieve_graph_context(query: str, limit: int = 10) -> list[dict]:
    """
    Retrieve neighboring graph triples relevant to a natural-language query.
    Uses the LLM to extract keywords, then matches Entity nodes in Neo4j.
    Returns [] on empty input or any failure (never raises to the caller).
    """
    if not query or not query.strip():
        return []

    if not neo4j_manager.driver:
        print("Error retrieving graph context: Neo4j driver is not connected.")
        return []

    try:
        from llm_service import extract_query_keywords

        keywords = await extract_query_keywords(query)
    except Exception as e:
        print(f"Error retrieving graph keywords from LLM: {e}")
        return []

    if not keywords:
        # Fallback: use the raw query as a single keyword
        keywords = [query.strip()]

    cypher = """
        MATCH (n:Entity)-[r]-(m:Entity)
        WHERE toLower(coalesce(n.name, '')) CONTAINS toLower($kw)
           OR toLower(coalesce(n.id, '')) CONTAINS toLower($kw)
        RETURN n.name AS source_name,
               n.id AS source_id,
               type(r) AS rel_label,
               r.type AS rel_type,
               m.name AS target_name,
               m.id AS target_id
        LIMIT $limit
    """

    results: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    try:
        async with neo4j_manager.driver.session() as session:
            for kw in keywords:
                try:
                    result = await session.run(cypher, kw=kw, limit=limit)
                    async for record in result:
                        source = record["source_name"] or record["source_id"] or ""
                        target = record["target_name"] or record["target_id"] or ""
                        relation = record["rel_type"] or record["rel_label"] or "RELATED"
                        key = (source, relation, target)
                        if not source or not target or key in seen:
                            continue
                        seen.add(key)
                        results.append({
                            "source": source,
                            "relation": relation,
                            "target": target,
                        })
                        if len(results) >= limit:
                            return results
                except Exception as cypher_error:
                    print(f"Cypher error for keyword '{kw}': {cypher_error}")
                    continue
    except Exception as e:
        print(f"Error retrieving graph context from Neo4j: {e}")
        return []

    return results


async def list_recent_graph_triples(limit: int = 50) -> list[dict]:
    """
    Return entity/relationship triples from Neo4j for the wiki page.
    Shape: { source, relation, target }. Empty list on failure.
    """
    if not neo4j_manager.driver:
        print("Error listing graph triples: Neo4j driver is not connected.")
        return []

    cypher = """
        MATCH (a:Entity)-[r]->(b:Entity)
        RETURN a.name AS source_name,
               a.id AS source_id,
               type(r) AS rel_label,
               r.type AS rel_type,
               b.name AS target_name,
               b.id AS target_id
        LIMIT $limit
    """

    try:
        async with neo4j_manager.driver.session() as session:
            result = await session.run(cypher, limit=max(1, min(limit, 200)))
            triples: list[dict] = []
            async for record in result:
                source = record["source_name"] or record["source_id"] or ""
                target = record["target_name"] or record["target_id"] or ""
                relation = record["rel_type"] or record["rel_label"] or "RELATED"
                if source and target:
                    triples.append({
                        "source": source,
                        "relation": relation,
                        "target": target,
                    })
            return triples
    except Exception as e:
        print(f"Error listing graph triples from Neo4j: {e}")
        return []
