from langchain.tools import tool
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper

_search = DuckDuckGoSearchAPIWrapper(time="d", max_results=8)


@tool
def get_recent_news(topic: str) -> str:
    """
    Search for recent news from the last 24 hours on a given topic.
    Args:
        topic: The topic or keyword to search for (e.g. 'AI', 'Indonesia economy', 'tech').
    Returns a list of recent news summaries.
    """
    query = f"{topic} news today"
    try:
        results = _search.run(query)
        return results if results else f"No recent news found for '{topic}'."
    except Exception as e:
        return f"News search failed: {e}"


@tool
def get_top_headlines() -> str:
    """
    Get today's top headlines across major topics: tech, business, and world news.
    Returns a combined summary of top headlines.
    """
    topics = ["technology news today", "world news today", "business news today"]
    all_results = []
    for topic in topics:
        try:
            result = _search.run(topic)
            if result:
                all_results.append(f"--- {topic.upper()} ---\n{result}")
        except Exception:
            continue
    return "\n\n".join(all_results) if all_results else "Could not fetch headlines."


NEWS_TOOLS = [get_recent_news, get_top_headlines]
