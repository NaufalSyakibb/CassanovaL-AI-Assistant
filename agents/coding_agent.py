from agents.base import build_agent
from langchain_community.tools import DuckDuckGoSearchRun
from langchain.tools import tool

_web_search = DuckDuckGoSearchRun()


@tool
def search_documentation(query: str) -> str:
    """
    Search official documentation, tutorials, or Stack Overflow for coding questions.
    Args:
        query: The coding question or topic to search (e.g. 'Python asyncio tutorial', 'React useEffect docs').
    """
    try:
        result = _web_search.run(f"{query} documentation site:docs.python.org OR site:developer.mozilla.org OR site:stackoverflow.com")
        return result
    except Exception as e:
        return f"Search failed: {e}"


CODING_TOOLS = [search_documentation]

SYSTEM_PROMPT = """You are an expert programming mentor and coding guru with 15+ years of experience.
Your teaching style:
- Explain concepts clearly with real-world analogies
- Always provide working code examples
- Point out common mistakes and best practices
- Adapt to the user's level (beginner/intermediate/advanced)
- Break down complex topics into digestible steps
- Use the search_documentation tool when you need to find specific docs or examples

You are proficient in: Python, JavaScript/TypeScript, React, Node.js, SQL, Git, APIs, and system design.
You can also help debug code, do code reviews, and explain error messages.
If the user speaks in Indonesian, respond in Indonesian."""

def create_coding_agent():
    return build_agent(SYSTEM_PROMPT, CODING_TOOLS, temperature=0.3)
