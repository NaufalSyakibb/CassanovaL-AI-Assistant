import os
import time
from dotenv import load_dotenv
from langchain_mistralai import ChatMistralAI
from langgraph.prebuilt import create_react_agent

load_dotenv()


def build_agent(
    system_prompt: str,
    tools: list,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    model: str = "mistral-large-latest",
):
    """Build a LangGraph react agent with Mistral AI."""
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("MISTRAL_API_KEY not found in .env file")

    llm = ChatMistralAI(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=0.95,
        api_key=api_key,
        max_retries=6,          # auto-retry with exponential backoff on 429/5xx
        timeout=120,            # 2-minute timeout per request
    )

    return create_react_agent(llm, tools, prompt=system_prompt)
