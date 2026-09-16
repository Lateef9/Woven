import os
import json
from dotenv import load_dotenv
import litellm
from schemas import AtomicFact, FactList

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
