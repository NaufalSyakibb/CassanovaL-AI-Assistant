import re
import requests
from langchain.tools import tool
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper

_search = DuckDuckGoSearchAPIWrapper(time="y", max_results=10)


def _fetch_url_text(url: str, max_chars: int = 4000) -> str:
    """Fetch raw text from a URL, stripping HTML tags."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=12)
        resp.raise_for_status()
        text = re.sub(r"<[^>]+>", " ", resp.text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars] + ("..." if len(text) > max_chars else "")
    except Exception as e:
        return f"[fetch failed: {e}]"


# ── 1. Deep web search ────────────────────────────────────────────────────────

@tool
def deep_web_search(query: str) -> str:
    """
    Search the web for a topic and return results from multiple angles.
    Runs 3 different search queries to get broad coverage on the topic.
    Args:
        query: The research topic or question.
    """
    queries = [
        query,
        f"{query} explained in depth",
        f"{query} latest findings 2024 2025",
    ]
    sections = []
    for q in queries:
        try:
            result = _search.run(q)
            if result:
                sections.append(f"[Query: {q}]\n{result}")
        except Exception as e:
            sections.append(f"[Query: {q}] Search failed: {e}")
    return "\n\n---\n\n".join(sections) if sections else "No results found."


@tool
def search_and_fetch(query: str) -> str:
    """
    Search the web for a topic and fetch the full content of the top result URL.
    Better than plain search when you need deeper detail from a specific page.
    Args:
        query: The topic or question to search.
    """
    try:
        results = _search.results(query, num_results=3)
        if not results:
            return "No search results found."
        output = []
        for r in results[:2]:
            url = r.get("link", "")
            title = r.get("title", "")
            snippet = r.get("snippet", "")
            page_text = _fetch_url_text(url, max_chars=2000)
            output.append(f"### {title}\nURL: {url}\nSnippet: {snippet}\n\nPage content:\n{page_text}")
        return "\n\n---\n\n".join(output)
    except Exception as e:
        return f"search_and_fetch failed: {e}"


# ── 2. URL / PDF summarizer ───────────────────────────────────────────────────

@tool
def fetch_and_read_url(url: str) -> str:
    """
    Fetch the full text content of any URL (article, blog post, research paper, docs page).
    Use this to read and summarize a specific page the user provides.
    Args:
        url: Full URL of the page to read.
    """
    text = _fetch_url_text(url, max_chars=6000)
    return f"[Content from {url}]\n\n{text}"


@tool
def summarize_multiple_urls(urls: str) -> str:
    """
    Fetch and return content from multiple URLs at once for comparison or synthesis.
    Args:
        urls: Comma-separated list of URLs (e.g. 'https://a.com, https://b.com').
    """
    url_list = [u.strip() for u in urls.split(",") if u.strip()]
    if not url_list:
        return "No URLs provided."
    results = []
    for url in url_list[:4]:  # cap at 4 to stay within context
        text = _fetch_url_text(url, max_chars=2000)
        results.append(f"### {url}\n{text}")
    return "\n\n---\n\n".join(results)


# ── 3. Autonomous research loop support ──────────────────────────────────────

@tool
def iterative_search(query: str, angle: str) -> str:
    """
    Search for a specific angle or sub-question within a broader research topic.
    Use this repeatedly to explore different facets of a topic before synthesizing.
    Args:
        query: The main research topic.
        angle: A specific sub-question or perspective to search (e.g. 'criticisms',
               'recent breakthroughs', 'real-world applications', 'history').
    """
    full_query = f"{query} {angle}"
    try:
        result = _search.run(full_query)
        return f"[Angle: {angle}]\n{result}" if result else f"No results for angle '{angle}'."
    except Exception as e:
        return f"Search failed: {e}"


@tool
def compile_research_report(topic: str, findings: str) -> str:
    """
    Format collected research findings into a structured report.
    Call this as the FINAL step after gathering enough information via other tools.
    Args:
        topic: The research topic/question.
        findings: All the raw findings you have gathered so far (paste them here).
    Returns a prompt for the LLM to synthesize into a clean report — the agent
    will then write the final structured output.
    """
    return (
        f"RESEARCH TOPIC: {topic}\n\n"
        f"RAW FINDINGS:\n{findings}\n\n"
        "INSTRUCTION: Synthesize the above into a well-structured research report with:\n"
        "1. Executive Summary (3-5 sentences)\n"
        "2. Key Findings (bullet points)\n"
        "3. Detailed Analysis (sections per sub-topic)\n"
        "4. Conclusions & Implications\n"
        "5. Sources referenced\n"
    )


RESEARCH_TOOLS = [
    deep_web_search,
    search_and_fetch,
    fetch_and_read_url,
    summarize_multiple_urls,
    iterative_search,
    compile_research_report,
]
