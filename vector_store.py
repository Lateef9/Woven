import weaviate
import weaviate.classes.config as wc
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

async def save_facts_to_weaviate(facts, source_message_id: str):
    """
    Takes a list of AtomicFact objects and saves them to the Weaviate database.
    """
    if not facts:
        return
        
    client = get_weaviate_client()
    try:
        # Get the Fact collection
        fact_collection = client.collections.get("Fact")
        
        # Prepare the objects for batch insertion
        objects_to_insert = [
            {
                "fact_text": fact.fact_text,
                "source_message_id": source_message_id
            }
            for fact in facts
        ]
        
        # Insert them into Weaviate
        fact_collection.data.insert_many(objects_to_insert)
        print(f"Successfully saved {len(objects_to_insert)} facts to Weaviate!")
        
    except Exception as e:
        print(f"Error saving to Weaviate: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    # Test the initialization directly
    init_weaviate_schema()
