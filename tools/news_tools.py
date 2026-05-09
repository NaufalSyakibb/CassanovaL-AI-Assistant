import os
import requests
from langchain.tools import tool


def _fetch_serper(query: str, max_results: int = 8) -> list:
    api_key = os.getenv("SERPER_API_KEY", "")
    if not api_key:
        return []
    try:
        resp = requests.post(
            "https://google.serper.dev/news",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": max_results},
            timeout=10,
        )
        if resp.status_code != 200:
            return []
        items = resp.json().get("news", [])
        return [
            {
                "title": i.get("title", ""),
                "source": i.get("source", ""),
                "snippet": i.get("snippet", ""),
                "date": i.get("date", ""),
                "url": i.get("link", ""),
                "imageUrl": i.get("imageUrl", ""),
            }
            for i in items
        ]
    except Exception:
        return []


def _fetch_ddg(query: str, max_results: int = 8) -> list:
    import concurrent.futures as _cf

    def _do():
        from ddgs import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.news(query, max_results=max_results):
                results.append({
                    "title":    r.get("title", ""),
                    "source":   r.get("source", ""),
                    "snippet":  r.get("body", ""),
                    "date":     r.get("date", ""),
                    "url":      r.get("url", ""),
                    "imageUrl": r.get("image", ""),
                })
        return results

    try:
        with _cf.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(_do).result(timeout=8)
    except Exception:
        return []


def _search_news(query: str, max_results: int = 8) -> list:
    results = _fetch_serper(query, max_results)
    if not results:
        results = _fetch_ddg(query, max_results)
    return results


@tool
def get_recent_news(topic: str) -> str:
    """
    Search for recent news from the last 24 hours on a given topic.
    Args:
        topic: The topic or keyword to search for (e.g. 'AI', 'Indonesia economy', 'tech').
    Returns a list of recent news summaries with sources and URLs.
    """
    results = _search_news(f"{topic} news", 8)
    if not results:
        return f"No recent news found for '{topic}'."
    lines = []
    for r in results:
        title   = r.get("title", "")
        source  = r.get("source", "")
        snippet = r.get("snippet", "")
        date    = r.get("date", "")
        url     = r.get("url", "")
        lines.append(f"- {title}\n  Source: {source} | {date}\n  {snippet}\n  URL: {url}")
    return "\n\n".join(lines)


@tool
def get_top_headlines() -> str:
    """
    Get today's top headlines across major topics: tech, business, and world news.
    Returns a combined summary of top headlines from each category.
    """
    topics = [
        ("TECHNOLOGY", "technology AI news today"),
        ("WORLD",      "world news today"),
        ("BUSINESS",   "business economy news today"),
    ]
    all_sections = []
    for label, query in topics:
        results = _search_news(query, 5)
        if not results:
            continue
        lines = [f"--- {label} ---"]
        for r in results:
            title  = r.get("title", "")
            source = r.get("source", "")
            snippet = r.get("snippet", "")
            url    = r.get("url", "")
            lines.append(f"- {title} ({source})\n  {snippet}\n  {url}")
        all_sections.append("\n".join(lines))
    return "\n\n".join(all_sections) if all_sections else "Could not fetch headlines at this time."


NEWS_TOOLS = [get_recent_news, get_top_headlines]
