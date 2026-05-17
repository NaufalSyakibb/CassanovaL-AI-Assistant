"""
Harvester using ScrapeGraphAI (SearchGraph) + Mistral AI.

Flow per platform:
  1. SearchGraph queries DuckDuckGo for trending content on the platform
  2. Fetches and reads the top result pages
  3. Mistral extracts structured trending topics / hashtags / discussions
  4. Saves raw JSON to data/raw/<platform>/scrapegraph_<platform>_<ts>.json
"""
import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Platform search queries ────────────────────────────────────────────────
PLATFORM_SEARCHES = {
    "youtube":    "YouTube trending videos viral content today",
    "tiktok":     "TikTok trending hashtags viral videos today",
    "facebook":   "Facebook trending topics viral posts today",
    "instagram":  "Instagram trending reels hashtags explore today",
    "twitter":    "Twitter X trending topics hashtags today",
    "reddit":     "Reddit top posts viral trending today",
    "linkedin":   "LinkedIn trending topics professional insights today",
    "medium":     "Medium trending articles popular reads today",
    "twitch":     "Twitch trending streams games today",
    "pinterest":  "Pinterest trending pins boards today",
    "quora":      "Quora trending questions answers today",
    "soundcloud": "SoundCloud trending music tracks artists today",
}

PLATFORM_LABELS = {
    "youtube":    "YouTube Trending",
    "tiktok":     "TikTok Trends",
    "facebook":   "Facebook Trending",
    "instagram":  "Instagram Explore",
    "twitter":    "Twitter/X Trends",
    "reddit":     "Reddit Top Today",
    "linkedin":   "LinkedIn Trending",
    "medium":     "Medium Trending",
    "twitch":     "Twitch Trending",
    "pinterest":  "Pinterest Trending",
    "quora":      "Quora Trending",
    "soundcloud": "SoundCloud Trending",
}

_DATA_DIR = Path(__file__).parent.parent / "data" / "raw"


def _flatten_result(result) -> list[str]:
    """Normalize SearchGraph output (dict, list, or str) to a flat list of strings."""
    if result is None:
        return []
    if isinstance(result, str):
        return [line.strip() for line in result.splitlines() if line.strip()]
    if isinstance(result, list):
        out = []
        for item in result:
            if isinstance(item, dict):
                parts = [str(v) for v in item.values() if v and str(v).strip()]
                if parts:
                    out.append(" — ".join(parts))
            elif item:
                out.append(str(item).strip())
        return [t for t in out if t]
    if isinstance(result, dict):
        out = []
        for v in result.values():
            out.extend(_flatten_result(v))
        return out
    return [str(result).strip()] if str(result).strip() else []


class ScrapeGraphHarvester:
    """
    Harvester powered by ScrapeGraphAI SearchGraph + Mistral AI.

    SearchGraph searches the web for each platform's trending content, fetches
    the top result pages, and uses Mistral to intelligently extract structured
    data — trending topics, hashtags, viral titles, and discussion threads.
    """

    def __init__(self):
        self._api_key = os.getenv("MISTRAL_API_KEY", "")
        self._config = {
            "llm": {
                "model": "mistralai/mistral-small",
                "api_key": self._api_key,
                "temperature": 0.1,
            },
            "verbose": False,
            "headless": True,
            "max_results": 5,       # top search results to fetch
        }

    def _build_prompt(self, platform: str, keywords: list[str] | None) -> str:
        """
        Prompt acts as both the DuckDuckGo search query (SearchInternetNode)
        and the LLM extraction instruction (SmartScraperGraph + MergeAnswersNode).
        In ScrapeGraphAI v2, SearchGraph has no separate `source` param.
        """
        label = PLATFORM_LABELS.get(platform, platform.capitalize())
        base_search = PLATFORM_SEARCHES.get(platform, f"{platform} trending today")
        kw_note = f" related to {', '.join(keywords)}" if keywords else ""
        return (
            f"{base_search}{' ' + ' '.join(keywords) if keywords else ''}. "
            f"Extract and list the top 15 currently trending topics, popular hashtags, "
            f"and viral content titles on {label}{kw_note} today. "
            f"For each item include its title and a brief description of why it is trending."
        )

    def _scrape_platform(self, platform: str, keywords: list[str] | None = None) -> list[str]:
        from scrapegraphai.graphs import SearchGraph

        graph = SearchGraph(
            prompt=self._build_prompt(platform, keywords),
            config=self._config,
        )
        result = graph.run()
        return _flatten_result(result)

    def _save(self, platform: str, items: list[dict]) -> Path:
        out_dir = _DATA_DIR / platform
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = out_dir / f"scrapegraph_{platform}_{ts}.json"
        path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def run(self, platforms: list[str] | None = None, keywords: list[str] | None = None) -> dict:
        """
        Scrape trending content for the given platforms.

        Returns:
            dict[platform_key, Path] — paths to saved raw JSON files.
        """
        active = platforms or list(PLATFORM_SEARCHES.keys())
        saved: dict = {}

        for plat in active:
            if plat not in PLATFORM_SEARCHES:
                print(f"[ScrapeGraph] Unknown platform '{plat}', skipping")
                continue
            try:
                print(f"[ScrapeGraph] Scraping {plat}...")
                topics = self._scrape_platform(plat, keywords)

                if not topics:
                    print(f"[ScrapeGraph] {plat}: no topics found")
                    continue

                content = "\n".join(topics)
                label = PLATFORM_LABELS[plat]
                items = [{
                    "platform":   plat,
                    "metadata":   {"label": label, "items_count": len(topics)},
                    "content":    content,
                    "raw_length": len(content),
                }]
                saved[plat] = self._save(plat, items)
                print(f"[ScrapeGraph] {plat}: {len(topics)} topics saved")
            except Exception as exc:
                print(f"[ScrapeGraph] {plat} error: {exc}")

        return saved
