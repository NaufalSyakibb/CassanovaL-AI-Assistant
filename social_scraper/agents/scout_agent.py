"""
Agent Scout — Social Media Data Explorer
=========================================
Monitors trending topics, hashtags, and keywords across 25 platforms.
Identifies scrapable targets and saves metadata to data/raw/scout/.

Output format per entry:
{
    "platform": "TikTok",
    "type": "hashtag|account|group|keyword",
    "identifier": "viral",
    "url": "https://www.tiktok.com/tag/viral",
    "priority": "high|medium|low",
    "last_checked": "2024-05-20T12:00:00Z"
}
"""
import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

# Allow running from repo root or social_scraper/
_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))

from utils.anti_bot import get_headers, get_json_headers, get_proxy, safe_get, random_delay, micro_delay
from utils.config_loader import get_api_key, get_scraping_config, is_platform_enabled, get
from utils.logger import get_logger, ActivityLog

logger = get_logger("scout")
activity = ActivityLog("scout")

SCOUT_DIR = _root / "data" / "raw" / "scout"
SCOUT_DIR.mkdir(parents=True, exist_ok=True)

_cfg = get_scraping_config()
MAX_RESULTS = _cfg.get("max_results_per_platform", 50)


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_entry(
    platform: str,
    type_: str,
    identifier: str,
    url: str,
    priority: str = "medium",
) -> dict:
    return {
        "platform": platform,
        "type": type_,
        "identifier": identifier,
        "url": url,
        "priority": priority,
        "last_checked": _now_utc(),
    }


# ── YouTube ────────────────────────────────────────────────────────────────────

def scout_youtube(keywords: list[str] | None = None) -> list[dict]:
    results = []
    api_key = get_api_key("youtube")
    if api_key:
        # YouTube Data API v3 — trending videos
        try:
            url = "https://www.googleapis.com/youtube/v3/videos"
            params = {
                "part": "snippet,statistics",
                "chart": "mostPopular",
                "maxResults": min(MAX_RESULTS, 50),
                "regionCode": "ID",
                "key": api_key,
            }
            r = safe_get(url + "?" + "&".join(f"{k}={v}" for k, v in params.items()))
            if r and r.status_code == 200:
                for item in r.json().get("items", []):
                    vid_id = item["id"]
                    title = item["snippet"]["title"]
                    results.append(_make_entry(
                        "YouTube", "keyword", title,
                        f"https://www.youtube.com/watch?v={vid_id}", "high"
                    ))
                activity.log("trending_fetch", "youtube", "ok", {"count": len(results)})
        except Exception as e:
            activity.log("trending_fetch", "youtube", "error", {"error": str(e)})

    # Fallback: scrape YouTube trending page
    if not results:
        try:
            url = "https://www.youtube.com/feed/trending"
            r = safe_get(url, headers=get_headers())
            if r and r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.select("a#video-title")[:MAX_RESULTS]:
                    href = a.get("href", "")
                    title = a.get("title", a.text.strip())
                    if href.startswith("/watch"):
                        results.append(_make_entry(
                            "YouTube", "keyword", title,
                            f"https://www.youtube.com{href}", "high"
                        ))
                activity.log("trending_scrape", "youtube", "ok", {"count": len(results)})
        except Exception as e:
            activity.log("trending_scrape", "youtube", "error", {"error": str(e)})

    # Additional: keyword-based search
    if keywords:
        for kw in keywords[:5]:
            results.append(_make_entry(
                "YouTube", "keyword", kw,
                f"https://www.youtube.com/results?search_query={quote_plus(kw)}", "medium"
            ))
    return results


# ── TikTok ─────────────────────────────────────────────────────────────────────

def scout_tiktok(hashtags: list[str] | None = None) -> list[dict]:
    results = []
    default_tags = ["viral", "fyp", "trending", "foryoupage", "indonesia"]
    for tag in (hashtags or default_tags):
        results.append(_make_entry(
            "TikTok", "hashtag", tag,
            f"https://www.tiktok.com/tag/{quote_plus(tag)}", "high"
        ))
    # TikTok trending page (requires JS rendering — mark for harvester)
    try:
        r = safe_get(
            "https://www.tiktok.com/explore",
            headers=get_headers({"Referer": "https://www.tiktok.com/"}),
        )
        if r and r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.select("a[href*='/tag/']")[:MAX_RESULTS]:
                href = a.get("href", "")
                tag_name = href.split("/tag/")[-1].split("?")[0]
                if tag_name:
                    results.append(_make_entry(
                        "TikTok", "hashtag", tag_name,
                        f"https://www.tiktok.com/tag/{tag_name}", "high"
                    ))
        activity.log("trending_fetch", "tiktok", "ok", {"count": len(results)})
    except Exception as e:
        activity.log("trending_fetch", "tiktok", "error", {"error": str(e)})
    return results


# ── Instagram ──────────────────────────────────────────────────────────────────

def scout_instagram(hashtags: list[str] | None = None) -> list[dict]:
    results = []
    default_tags = ["viral", "trending", "explorepage", "indonesia", "lifestyle"]
    for tag in (hashtags or default_tags):
        results.append(_make_entry(
            "Instagram", "hashtag", tag,
            f"https://www.instagram.com/explore/tags/{quote_plus(tag)}/", "high"
        ))
    # Instagram explore (requires session — stub for now)
    activity.log("scout", "instagram", "ok", {"note": "hashtag targets queued", "count": len(results)})
    return results


# ── Facebook ───────────────────────────────────────────────────────────────────

def scout_facebook(keywords: list[str] | None = None) -> list[dict]:
    results = []
    kws = keywords or ["trending", "viral indonesia", "berita terkini"]
    for kw in kws:
        results.append(_make_entry(
            "Facebook", "keyword", kw,
            f"https://www.facebook.com/search/posts?q={quote_plus(kw)}", "medium"
        ))
    results.append(_make_entry(
        "Facebook", "group", "public-groups",
        "https://www.facebook.com/groups/feed/", "medium"
    ))
    activity.log("scout", "facebook", "ok", {"count": len(results)})
    return results


# ── Twitter / X ────────────────────────────────────────────────────────────────

def scout_twitter(woeid: int = 23424846) -> list[dict]:
    """woeid=23424846 = Indonesia. Falls back to Nitter scraping."""
    results = []
    bearer = get_api_key("twitter_bearer")

    if bearer:
        try:
            r = safe_get(
                f"https://api.twitter.com/1.1/trends/place.json?id={woeid}",
                headers={
                    "Authorization": f"Bearer {bearer}",
                    "User-Agent": "v2TrendsPython",
                },
            )
            if r and r.status_code == 200:
                for trend in r.json()[0].get("trends", [])[:MAX_RESULTS]:
                    name = trend.get("name", "")
                    url = trend.get("url", f"https://twitter.com/search?q={quote_plus(name)}")
                    type_ = "hashtag" if name.startswith("#") else "keyword"
                    results.append(_make_entry("Twitter", type_, name.lstrip("#"), url, "high"))
                activity.log("trending_fetch", "twitter", "ok", {"count": len(results)})
                return results
        except Exception as e:
            activity.log("trending_fetch", "twitter", "error", {"error": str(e)})

    # Fallback: Nitter trending
    try:
        r = safe_get("https://nitter.privacydev.net/explore", headers=get_headers())
        if r and r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for tag in soup.select("a.trend-link")[:MAX_RESULTS]:
                name = tag.text.strip().lstrip("#")
                results.append(_make_entry(
                    "Twitter", "hashtag", name,
                    f"https://twitter.com/hashtag/{quote_plus(name)}", "high"
                ))
        activity.log("trending_scrape", "twitter", "ok", {"count": len(results)})
    except Exception as e:
        activity.log("trending_scrape", "twitter", "error", {"error": str(e)})
    return results


# ── Reddit ─────────────────────────────────────────────────────────────────────

def scout_reddit() -> list[dict]:
    results = []
    client_id = get_api_key("reddit_client_id")
    client_secret = get_api_key("reddit_client_secret")

    if client_id and client_secret:
        try:
            import praw
            reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=get("api_keys.reddit_user_agent", "SocialScraper/1.0"),
            )
            for sub in reddit.subreddits.popular(limit=25):
                results.append(_make_entry(
                    "Reddit", "group", sub.display_name,
                    f"https://www.reddit.com/r/{sub.display_name}/", "medium"
                ))
            activity.log("trending_fetch", "reddit", "ok", {"count": len(results)})
            return results
        except Exception as e:
            activity.log("trending_fetch", "reddit", "error", {"error": str(e)})

    # Fallback: JSON API (no auth)
    try:
        r = safe_get(
            "https://www.reddit.com/r/popular.json?limit=25",
            headers=get_headers({"Accept": "application/json"}),
        )
        if r and r.status_code == 200:
            for post in r.json()["data"]["children"]:
                d = post["data"]
                results.append(_make_entry(
                    "Reddit", "keyword", d.get("title", ""),
                    f"https://www.reddit.com{d.get('permalink', '')}", "medium"
                ))
        activity.log("trending_fetch_json", "reddit", "ok", {"count": len(results)})
    except Exception as e:
        activity.log("trending_fetch_json", "reddit", "error", {"error": str(e)})
    return results


# ── LinkedIn ───────────────────────────────────────────────────────────────────

def scout_linkedin(keywords: list[str] | None = None) -> list[dict]:
    results = []
    kws = keywords or ["AI", "machine learning", "startup", "Indonesia tech"]
    for kw in kws:
        results.append(_make_entry(
            "LinkedIn", "keyword", kw,
            f"https://www.linkedin.com/search/results/content/?keywords={quote_plus(kw)}", "medium"
        ))
    activity.log("scout", "linkedin", "ok", {"count": len(results)})
    return results


# ── Pinterest ──────────────────────────────────────────────────────────────────

def scout_pinterest(keywords: list[str] | None = None) -> list[dict]:
    results = []
    kws = keywords or ["trending", "fashion", "food", "travel", "art"]
    for kw in kws:
        results.append(_make_entry(
            "Pinterest", "keyword", kw,
            f"https://www.pinterest.com/search/pins/?q={quote_plus(kw)}", "medium"
        ))
    try:
        r = safe_get("https://www.pinterest.com/today/", headers=get_headers())
        if r and r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.select("a[href*='/search/']")[:10]:
                href = a.get("href", "")
                text = a.text.strip()
                if text and "/search/" in href:
                    results.append(_make_entry(
                        "Pinterest", "keyword", text,
                        f"https://www.pinterest.com{href}" if href.startswith("/") else href, "medium"
                    ))
        activity.log("trending_scrape", "pinterest", "ok", {"count": len(results)})
    except Exception as e:
        activity.log("trending_scrape", "pinterest", "error", {"error": str(e)})
    return results


# ── Twitch ─────────────────────────────────────────────────────────────────────

def scout_twitch() -> list[dict]:
    results = []
    try:
        r = safe_get(
            "https://api.twitch.tv/helix/games/top?first=20",
            headers=get_json_headers({"Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko"}),
        )
        if r and r.status_code == 200:
            for game in r.json().get("data", []):
                name = game.get("name", "")
                results.append(_make_entry(
                    "Twitch", "keyword", name,
                    f"https://www.twitch.tv/directory/game/{quote_plus(name)}", "medium"
                ))
        activity.log("trending_fetch", "twitch", "ok", {"count": len(results)})
    except Exception as e:
        activity.log("trending_fetch", "twitch", "error", {"error": str(e)})
    return results


# ── Quora ──────────────────────────────────────────────────────────────────────

def scout_quora(topics: list[str] | None = None) -> list[dict]:
    results = []
    topics_ = topics or ["technology", "science", "psychology", "indonesia", "programming"]
    for topic in topics_:
        results.append(_make_entry(
            "Quora", "keyword", topic,
            f"https://www.quora.com/topic/{quote_plus(topic)}", "low"
        ))
    activity.log("scout", "quora", "ok", {"count": len(results)})
    return results


# ── Medium ─────────────────────────────────────────────────────────────────────

def scout_medium(topics: list[str] | None = None) -> list[dict]:
    results = []
    try:
        r = safe_get(
            "https://medium.com/_/api/tags/trending",
            headers=get_json_headers(),
        )
        if r and r.status_code == 200:
            for tag in r.json().get("payload", {}).get("value", [])[:MAX_RESULTS]:
                slug = tag.get("slug", "")
                name = tag.get("name", slug)
                results.append(_make_entry(
                    "Medium", "keyword", name,
                    f"https://medium.com/tag/{slug}", "medium"
                ))
        activity.log("trending_fetch", "medium", "ok", {"count": len(results)})
    except Exception as e:
        topics_ = topics or ["technology", "ai", "startup", "data-science", "programming"]
        for t in topics_:
            results.append(_make_entry(
                "Medium", "keyword", t,
                f"https://medium.com/tag/{t}", "medium"
            ))
        activity.log("trending_fallback", "medium", "warn", {"error": str(e)})
    return results


# ── Tumblr ─────────────────────────────────────────────────────────────────────

def scout_tumblr(tags: list[str] | None = None) -> list[dict]:
    results = []
    tags_ = tags or ["art", "aesthetic", "anime", "photography", "fashion"]
    for tag in tags_:
        results.append(_make_entry(
            "Tumblr", "hashtag", tag,
            f"https://www.tumblr.com/tagged/{quote_plus(tag)}", "low"
        ))
    activity.log("scout", "tumblr", "ok", {"count": len(results)})
    return results


# ── VK ─────────────────────────────────────────────────────────────────────────

def scout_vk(keywords: list[str] | None = None) -> list[dict]:
    results = []
    kws = keywords or ["технологии", "новости", "мода", "музыка"]
    for kw in kws:
        results.append(_make_entry(
            "VK", "keyword", kw,
            f"https://vk.com/search?q={quote_plus(kw)}&section=news", "low"
        ))
    activity.log("scout", "vk", "ok", {"count": len(results)})
    return results


# ── Glassdoor ─────────────────────────────────────────────────────────────────

def scout_glassdoor(companies: list[str] | None = None) -> list[dict]:
    results = []
    comps = companies or ["Google", "Microsoft", "Gojek", "Tokopedia", "Shopee"]
    for co in comps:
        results.append(_make_entry(
            "Glassdoor", "keyword", co,
            f"https://www.glassdoor.com/Reviews/{quote_plus(co)}-reviews-SRCH_KE0,{len(co)}.htm",
            "low"
        ))
    activity.log("scout", "glassdoor", "ok", {"count": len(results)})
    return results


# ── Goodreads ──────────────────────────────────────────────────────────────────

def scout_goodreads() -> list[dict]:
    results = []
    try:
        r = safe_get("https://www.goodreads.com/list/show/1.Best_Books_Ever", headers=get_headers())
        if r and r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.select("a.bookTitle")[:20]:
                title = a.text.strip()
                href = a.get("href", "")
                results.append(_make_entry(
                    "Goodreads", "keyword", title,
                    f"https://www.goodreads.com{href}" if href.startswith("/") else href, "low"
                ))
        activity.log("trending_scrape", "goodreads", "ok", {"count": len(results)})
    except Exception as e:
        activity.log("trending_scrape", "goodreads", "error", {"error": str(e)})
    return results


# ── Letterboxd ────────────────────────────────────────────────────────────────

def scout_letterboxd() -> list[dict]:
    results = []
    try:
        r = safe_get("https://letterboxd.com/films/popular/", headers=get_headers())
        if r and r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.select("a.frame")[:20]:
                href = a.get("href", "")
                slug = href.strip("/").split("/")[-1]
                results.append(_make_entry(
                    "Letterboxd", "keyword", slug,
                    f"https://letterboxd.com{href}", "low"
                ))
        activity.log("trending_scrape", "letterboxd", "ok", {"count": len(results)})
    except Exception as e:
        activity.log("trending_scrape", "letterboxd", "error", {"error": str(e)})
    return results


# ── TripAdvisor ───────────────────────────────────────────────────────────────

def scout_tripadvisor(cities: list[str] | None = None) -> list[dict]:
    results = []
    cities_ = cities or ["Bali", "Jakarta", "Yogyakarta", "Singapore", "Phuket"]
    for city in cities_:
        results.append(_make_entry(
            "TripAdvisor", "keyword", city,
            f"https://www.tripadvisor.com/Search?q={quote_plus(city)}", "low"
        ))
    activity.log("scout", "tripadvisor", "ok", {"count": len(results)})
    return results


# ── SoundCloud ────────────────────────────────────────────────────────────────

def scout_soundcloud(genres: list[str] | None = None) -> list[dict]:
    results = []
    genres_ = genres or ["electronic", "hip-hop", "pop", "indie", "lofi"]
    for g in genres_:
        results.append(_make_entry(
            "SoundCloud", "keyword", g,
            f"https://soundcloud.com/tags/{quote_plus(g)}", "low"
        ))
    try:
        r = safe_get("https://soundcloud.com/charts/top", headers=get_headers())
        if r and r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.select("a.chartTrack__title")[:20]:
                title = a.text.strip()
                href = a.get("href", "")
                results.append(_make_entry(
                    "SoundCloud", "keyword", title,
                    f"https://soundcloud.com{href}", "low"
                ))
        activity.log("trending_scrape", "soundcloud", "ok", {"count": len(results)})
    except Exception as e:
        activity.log("trending_scrape", "soundcloud", "error", {"error": str(e)})
    return results


# ── DeviantArt ────────────────────────────────────────────────────────────────

def scout_deviantart(tags: list[str] | None = None) -> list[dict]:
    results = []
    tags_ = tags or ["digital-art", "fanart", "photography", "anime", "illustration"]
    for tag in tags_:
        results.append(_make_entry(
            "DeviantArt", "keyword", tag,
            f"https://www.deviantart.com/tag/{quote_plus(tag)}", "low"
        ))
    activity.log("scout", "deviantart", "ok", {"count": len(results)})
    return results


# ── Google Dorking ─────────────────────────────────────────────────────────────

def scout_google_dork(queries: list[str] | None = None) -> list[dict]:
    """Use Google Custom Search API for OSINT-style discovery."""
    results = []
    api_key = get_api_key("google")
    cx = get("api_keys.google_cx", "")
    default_queries = [
        'site:tiktok.com "viral" intitle:"#"',
        'site:instagram.com/p/ inurl:?hl=en',
        'site:reddit.com/r/ "AMA" OR "megathread"',
    ]
    for query in (queries or default_queries):
        if api_key and cx:
            try:
                r = safe_get(
                    f"https://www.googleapis.com/customsearch/v1?q={quote_plus(query)}&key={api_key}&cx={cx}&num=10"
                )
                if r and r.status_code == 200:
                    for item in r.json().get("items", []):
                        results.append(_make_entry(
                            "Google", "keyword", item.get("title", query),
                            item.get("link", ""), "medium"
                        ))
                    continue
            except Exception:
                pass
        results.append(_make_entry(
            "Google", "keyword", query,
            f"https://www.google.com/search?q={quote_plus(query)}", "medium"
        ))
    activity.log("dorking", "google", "ok", {"count": len(results)})
    return results


# ── Main ScoutAgent class ──────────────────────────────────────────────────────

class ScoutAgent:
    """Orchestrates all platform scouts and saves output to data/raw/scout/."""

    PLATFORM_SCOUTS = {
        "youtube":    (scout_youtube,    "high"),
        "tiktok":     (scout_tiktok,     "high"),
        "instagram":  (scout_instagram,  "high"),
        "facebook":   (scout_facebook,   "high"),
        "twitter":    (scout_twitter,    "high"),
        "reddit":     (scout_reddit,     "high"),
        "linkedin":   (scout_linkedin,   "medium"),
        "pinterest":  (scout_pinterest,  "medium"),
        "twitch":     (scout_twitch,     "medium"),
        "quora":      (scout_quora,      "medium"),
        "medium":     (scout_medium,     "medium"),
        "tumblr":     (scout_tumblr,     "low"),
        "vk":         (scout_vk,         "low"),
        "glassdoor":  (scout_glassdoor,  "low"),
        "goodreads":  (scout_goodreads,  "low"),
        "letterboxd": (scout_letterboxd, "low"),
        "tripadvisor":(scout_tripadvisor,"low"),
        "soundcloud": (scout_soundcloud, "low"),
        "deviantart": (scout_deviantart, "low"),
    }

    # keyword-aware scouts: map platform → param name
    _KW_PARAM: dict[str, str] = {
        "youtube":    "keywords",
        "tiktok":     "hashtags",
        "instagram":  "hashtags",
        "facebook":   "keywords",
        "linkedin":   "keywords",
        "pinterest":  "keywords",
        "quora":      "topics",
        "medium":     "topics",
        "tumblr":     "tags",
        "vk":         "keywords",
        "glassdoor":  "companies",
        "tripadvisor":"cities",
        "soundcloud": "genres",
        "deviantart": "tags",
    }

    def run(self, platforms: list[str] | None = None, keywords: list[str] | None = None) -> list[dict]:
        """Run all scouts and return a flat list of target entries.

        Args:
            platforms: restrict to these platforms (None = all enabled)
            keywords:  search terms forwarded to each platform scout
        """
        all_results: dict[str, list[dict]] = {}
        targets = platforms or list(self.PLATFORM_SCOUTS.keys())

        logger.info(f"Scout run started — {len(targets)} platforms"
                    + (f", keywords={keywords}" if keywords else ""))

        for platform in targets:
            if not is_platform_enabled(platform):
                logger.debug(f"Skipping {platform} (disabled in config)")
                continue
            scout_fn, _ = self.PLATFORM_SCOUTS.get(platform, (None, None))
            if not scout_fn:
                continue
            try:
                logger.info(f"Scouting {platform}...")
                param = self._KW_PARAM.get(platform)
                entries = scout_fn(**{param: keywords}) if (param and keywords) else scout_fn()
                all_results[platform] = entries
                random_delay(1, 4)
            except Exception as e:
                logger.warning(f"Scout failed for {platform}: {e}")
                activity.log("run", platform, "error", {"error": str(e)})
                all_results[platform] = []

        # Google Dorking — pass keywords as custom queries
        try:
            dork_queries = keywords or None
            all_results["google_dork"] = scout_google_dork(queries=dork_queries)
        except Exception as e:
            activity.log("run", "google_dork", "error", {"error": str(e)})

        flat = self._save(all_results)
        total = len(flat)
        logger.info(f"Scout complete — {total} entries across {len(all_results)} platforms")
        return flat

    def _save(self, results: dict) -> list[dict]:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        for platform, entries in results.items():
            if not entries:
                continue
            out_file = SCOUT_DIR / f"{platform}_{ts}.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved {len(entries)} entries → {out_file.name}")

        # Combined flat list for harvester
        flat = [e for v in results.values() for e in v]
        combined = SCOUT_DIR / f"combined_{ts}.json"
        with open(combined, "w", encoding="utf-8") as f:
            json.dump(flat, f, indent=2, ensure_ascii=False)
        self._last_combined_path = combined  # Path object
        activity.log("save", "all", "ok", {"file": combined.name, "total": len(flat)})
        return flat

    def watch(self, interval_hours: float = 6.0) -> None:
        """Block and re-run scout every `interval_hours` hours."""
        import time as _time
        from apscheduler.schedulers.blocking import BlockingScheduler

        scheduler = BlockingScheduler()
        scheduler.add_job(
            self.run,
            "interval",
            hours=interval_hours,
            id="scout_job",
            replace_existing=True,
        )
        logger.info(f"Scout scheduler started — interval: {interval_hours}h")
        try:
            self.run()  # Run immediately on start
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scout scheduler stopped")


if __name__ == "__main__":
    agent = ScoutAgent()
    agent.run()
