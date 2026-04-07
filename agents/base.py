import os
from dotenv import load_dotenv
from langchain_mistralai import ChatMistralAI
from langgraph.prebuilt import create_react_agent

load_dotenv()


def build_agent(system_prompt: str, tools: list, temperature: float = 0.2):
    """Build a LangGraph react agent with Mistral AI."""
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("MISTRAL_API_KEY not found in .env file")

    llm = ChatMistralAI(
        model="mistral-large-latest",
        temperature=temperature,
        api_key=api_key,
    )

    return create_react_agent(llm, tools, prompt=system_prompt)
