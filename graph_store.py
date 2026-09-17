import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

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
