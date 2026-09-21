import os
import json
from dotenv import load_dotenv
import litellm
from schemas import AtomicFact, FactList, GraphExtractionResult

# Load environment variables from .env file
load_dotenv()

async def ask_llm(prompt: str) -> str:
    """
    Takes a user prompt, sends it to the LLM (gpt-4o-mini), and returns the text response.
    """
    response = await litellm.acompletion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    # Return the text response from the model
    return response.choices[0].message.content

async def extract_facts(message_text: str) -> list[AtomicFact]:
    """
    Extracts standalone technical facts from a chat message using JSON mode.
    """
    system_prompt = (
        "You are an extraction bot. Extract useful, standalone technical facts "
        "from the following chat message. Ignore pleasantries. Return the result "
        "as a JSON object with a single key 'facts', which is an array of objects matching the AtomicFact schema. "
        "The AtomicFact schema has two fields: 'fact_text' (string) and 'confidence_score' (float 0.0 to 1.0)."
    )

    response = await litellm.acompletion(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message_text}
        ],
        response_format={"type": "json_object"}
    )
    
    response_content = response.choices[0].message.content
    try:
        data = json.loads(response_content)
        fact_list = FactList(**data)
        return fact_list.facts
    except Exception as e:
        print(f"Error parsing facts: {e}")
        return []

async def extract_graph_data(message_text: str) -> GraphExtractionResult:
    """
    Extracts entities and relationships from a chat message.
    """
    system_prompt = (
        "You are a graph extraction bot. Identify key entities (Person, Project, Technology, Concept) "
        "and relationships from the text. Return a JSON object matching the GraphExtractionResult schema. "
        "Ensure relationship source and target IDs perfectly match the extracted entity IDs. "
        "Entity fields: id (lowercase/slugified string), type (e.g. Person, Project, Technology, Concept), name (string). "
        "Relationship fields: source_entity_id, target_entity_id, relation_type (uppercase, e.g. WORKS_ON, USES, MENTIONS)."
    )

    response = await litellm.acompletion(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message_text}
        ],
        response_format={"type": "json_object"}
    )
    
    response_content = response.choices[0].message.content
    try:
        data = json.loads(response_content)
        return GraphExtractionResult(**data)
    except Exception as e:
        print(f"Error parsing graph data: {e}")
        return GraphExtractionResult(entities=[], relationships=[])


async def extract_query_keywords(query: str) -> list[str]:
    """
    Extracts 1–5 likely entity names/keywords from a user query for graph lookup.
    Returns a plain list of strings; empty list on failure.
    """
    if not query or not query.strip():
        return []

    system_prompt = (
        "Extract 1 to 5 likely entity names or keywords from the user question "
        "that would help look up a knowledge graph. Prefer people, places, organizations, "
        "products, and concrete nouns. Return a JSON object with a single key 'keywords' "
        "whose value is an array of strings. Do not invent unrelated terms."
    )

    try:
        response = await litellm.acompletion(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content)
        keywords = data.get("keywords", [])
        if not isinstance(keywords, list):
            return []
        cleaned = [str(k).strip() for k in keywords if str(k).strip()]
        return cleaned[:5]
    except Exception as e:
        print(f"Error extracting query keywords: {e}")
        return []
