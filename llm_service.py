import os
from dotenv import load_dotenv
import litellm

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
