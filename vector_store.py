import weaviate
import weaviate.classes.config as wc
from weaviate.classes.query import MetadataQuery
import os
from dotenv import load_dotenv

load_dotenv()

def get_weaviate_client():
    """
    Connects to Weaviate at http://localhost:8080 and sets up the OpenAI integration.
    """
    headers = {}
    if os.getenv("OPENAI_API_KEY"):
        headers["X-OpenAI-Api-Key"] = os.getenv("OPENAI_API_KEY")

    # Connect to the local Weaviate instance running via Docker Compose
    client = weaviate.connect_to_local(
        host="localhost",
        port=8080,
        grpc_port=50051,
        headers=headers
    )
    return client

def init_weaviate_schema():
    """
    Checks if 'Fact' collection exists, creates it if not.
    The collection has properties for fact_text and source_message_id.
    """
    client = get_weaviate_client()
    try:
        if not client.collections.exists("Fact"):
            client.collections.create(
                name="Fact",
                vectorizer_config=wc.Configure.Vectorizer.text2vec_openai(
                    model="text-embedding-3-small"
                ),
                properties=[
                    wc.Property(name="fact_text", data_type=wc.DataType.TEXT),
                    wc.Property(name="source_message_id", data_type=wc.DataType.TEXT),
                ]
            )
            print("Successfully created 'Fact' collection in Weaviate.")
        else:
            print("Weaviate collection 'Fact' already exists.")
    except Exception as e:
        print(f"Error initializing Weaviate schema: {e}")
    finally:
        client.close()

def clear_facts() -> None:
    """Deletes all Fact objects by recreating an empty Fact collection."""
    client = None
    try:
        client = get_weaviate_client()
        if client.collections.exists("Fact"):
            client.collections.delete("Fact")
        client.collections.create(
            name="Fact",
            vectorizer_config=wc.Configure.Vectorizer.text2vec_openai(
                model="text-embedding-3-small"
            ),
            properties=[
                wc.Property(name="fact_text", data_type=wc.DataType.TEXT),
                wc.Property(name="source_message_id", data_type=wc.DataType.TEXT),
            ],
        )
        print("Cleared Weaviate: recreated empty Fact collection.")
    except Exception as e:
        print(f"Error clearing Weaviate facts: {e}")
    finally:
        if client is not None:
            client.close()


def save_fact(fact_text: str, message_id: str):
    """
    Inserts a new object into the 'Fact' collection in Weaviate.
    """
    client = get_weaviate_client()
    try:
        fact_collection = client.collections.get("Fact")
        fact_collection.data.insert({
            "fact_text": fact_text,
            "source_message_id": message_id
        })
        print(f"Successfully saved fact to Weaviate: {fact_text}")
    except Exception as e:
        print(f"Error saving to Weaviate: {e}")
    finally:
        client.close()

def search_facts(query: str, limit: int = 3):
    """
    Performs a semantic nearText search on the 'Fact' collection
    and returns the closest facts.
    """
    return retrieve_facts(query=query, limit=limit)

def retrieve_facts(query: str, limit: int = 5) -> list[dict]:
    """
    Semantic nearText retrieval against the Fact collection.
    Returns fact_text, source_message_id, and a relevance score when available.
    Empty results or errors return [] (never raises).
    """
    if not query or not query.strip():
        return []

    client = None
    try:
        client = get_weaviate_client()
        if not client.collections.exists("Fact"):
            return []

        fact_collection = client.collections.get("Fact")
        response = fact_collection.query.near_text(
            query=query,
            limit=limit,
            return_metadata=MetadataQuery(distance=True, certainty=True),
        )

        results = []
        for obj in response.objects:
            score = None
            if obj.metadata is not None:
                if obj.metadata.certainty is not None:
                    score = obj.metadata.certainty
                elif obj.metadata.distance is not None:
                    # Lower distance = closer; convert to a 0-1-ish relevance score
                    score = max(0.0, 1.0 - float(obj.metadata.distance))

            results.append({
                "fact_text": obj.properties.get("fact_text"),
                "source_message_id": obj.properties.get("source_message_id"),
                "score": score,
            })
        return results
    except Exception as e:
        print(f"Error retrieving facts from Weaviate: {e}")
        return []
    finally:
        if client is not None:
            client.close()

if __name__ == "__main__":
    # Test the initialization directly
    init_weaviate_schema()
