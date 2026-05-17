import asyncio
import io
import json
import os
from datetime import datetime
from pathlib import Path


def _silence_crawl4ai_console():
    """Redirect crawl4ai's rich Console to StringIO so it never hits the
    legacy Windows console renderer (which crashes on UTF-8 arrow chars)."""
    try:
        from crawl4ai.async_logger import AsyncLogger
        from rich.console import Console
        _null = io.StringIO()
        _orig_init = AsyncLogger.__init__

        def _patched_init(self, *args, **kwargs):
            _orig_init(self, *args, **kwargs)
            self.console = Console(file=_null, no_color=True)

        AsyncLogger.__init__ = _patched_init
    except Exception:
        pass


_silence_crawl4ai_console()


PLATFORM_TARGETS = {
    "youtube":   {"label": "YouTube Trending",   "url": "https://www.youtube.com/feed/trending"},
    "tiktok":    {"label": "TikTok Trends",      "url": "https://ads.tiktok.com/business/creativecenter/trends/popular/hashtags/pc/en"},
    "facebook":  {"label": "Facebook Trending",  "url": "https://www.facebook.com/trending"},
    "instagram": {"label": "Instagram Explore",  "url": "https://www.instagram.com/explore/"},
    "reddit":    {"label": "Reddit Top Today",   "url": "https://www.reddit.com/r/all/top/.json?t=day&limit=25"},
    "x_twitter": {"label": "X/Twitter Trends",  "url": "https://twitter.com/i/trends"},
}

_CSS_SCHEMA = {
    "name": "Global Trend Extractor",
    "baseSelector": "h3, h2, .title, [class*='item'], article, [class*='trend'], [class*='video'], li",
    "fields": [
        {"name": "topic", "selector": "text", "type": "text"},
        {"name": "link",  "selector": "a",    "type": "attribute", "attribute": "href"},
    ],
}

_DATA_DIR = Path(__file__).parent.parent / "data" / "raw"

# DuckDuckGo fallback search queries per platform
_DDG_QUERIES = {
    "youtube":   "youtube trending videos today viral",
    "tiktok":    "tiktok trending hashtags viral today",
    "facebook":  "facebook trending topics viral today",
    "instagram": "instagram trending reels hashtags today",
    "reddit":    "reddit top posts viral today",
    "x_twitter": "twitter trending topics today viral",
}


async def _crawl_with_browser(platform: str, meta: dict) -> list[str]:
    from crawl4ai import AsyncWebCrawler
    from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

    strategy = JsonCssExtractionStrategy(_CSS_SCHEMA)
    async with AsyncWebCrawler(verbose=False) as crawler:
        result = await crawler.arun(
            url=meta["url"],
            extraction_strategy=strategy,
            wait_for=4.0,
            browser_cfg={"stealth": True},
            bypass_cache=True,
        )

    if not result.success:
        return []

    try:
        raw_items = json.loads(result.extracted_content or "[]")
    except (json.JSONDecodeError, TypeError):
        return []

    return [
        item["topic"].strip()
        for item in raw_items
        if isinstance(item, dict) and len(item.get("topic", "").strip()) > 5
    ]


def _fetch_reddit_json(url: str) -> list[str]:
    """Reddit has a public JSON API — use requests directly."""
    import requests
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        r.raise_for_status()
        posts = r.json()["data"]["children"]
        return [p["data"]["title"] for p in posts if p["data"].get("title")]
    except Exception:
        return []


def _ddg_search(platform: str) -> list[str]:
    """DuckDuckGo news search — primary source since social platforms block crawlers."""
    try:
        from ddgs import DDGS
        query = _DDG_QUERIES.get(platform, f"{platform} trending today")
        results = list(DDGS().text(query, timelimit="d", max_results=25))
        topics = []
        for r in results:
            if r.get("title"):
                topics.append(r["title"])
            if r.get("body"):
                topics.append(r["body"][:300])
        return topics
    except Exception:
        return []


def _scrape_platform(platform: str, meta: dict) -> list[str]:
    """Collect trending content: DDG news search + optional browser crawl supplement."""
    topics: list[str] = []

    # DuckDuckGo news search (always reliable — no blocking)
    topics = _ddg_search(platform)

    # Reddit public JSON API supplement
    if platform == "reddit":
        reddit_titles = _fetch_reddit_json(
            "https://www.reddit.com/r/all/top.json?t=day&limit=25"
        )
        topics = reddit_titles + topics

    # Browser crawl supplement (best-effort; social platforms often block)
    if len(topics) < 5:
        try:
            browser_topics = asyncio.run(_crawl_with_browser(platform, meta))
            topics.extend(browser_topics)
        except Exception:
            pass

    return topics


def _save(platform: str, items: list[dict]) -> Path:
    out_dir = _DATA_DIR / platform
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"crawl4ai_{platform}_{ts}.json"
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class Crawl4AIHarvester:
    def run(self, platforms: list | None = None, keywords: list | None = None) -> dict:
        active = platforms or list(PLATFORM_TARGETS.keys())
        saved: dict = {}

        for plat in active:
            meta = PLATFORM_TARGETS.get(plat)
            if not meta:
                continue
            try:
                print(f"[crawl4ai] Scraping {plat}...")
                topics = _scrape_platform(plat, meta)

                # Filter by keywords if given
                if keywords and topics:
                    kw_lower = [k.lower() for k in keywords]
                    filtered = [t for t in topics if any(k in t.lower() for k in kw_lower)]
                    if filtered:
                        topics = filtered

                if not topics:
                    print(f"[crawl4ai] {plat}: no topics found")
                    continue

                content = "\n".join(topics)
                items = [{
                    "platform":   plat,
                    "url":        meta["url"],
                    "metadata":   {"label": meta["label"], "items_count": len(topics)},
                    "content":    content,
                    "raw_length": len(content),
                }]
                saved[plat] = _save(plat, items)
                print(f"[crawl4ai] {plat}: {len(topics)} topics saved")
            except Exception as exc:
                print(f"[crawl4ai] {plat} error: {exc}")

        return saved
