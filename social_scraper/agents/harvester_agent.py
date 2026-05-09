"""
Agent Harvester — Raw Data Collector
======================================
Reads scout targets from data/raw/scout/ and scrapes raw content
(text, metadata, comments) from each platform.

Output per item:
{
    "platform": "Instagram",
    "type": "post|comment|story|video|tweet",
    "id": "123456789",
    "content": "Caption atau teks",
    "media": ["url_gambar1"],
    "metadata": {
        "like": 1000,
        "timestamp": "2024-05-20T12:00:00Z",
        "location": "Jakarta",
        "user": "username"
    }
}
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))

from utils.anti_bot import get_headers, get_json_headers, get_proxy, safe_get, random_delay, micro_delay, make_driver
from utils.config_loader import get_api_key, get_scraping_config, is_platform_enabled, get
from utils.logger import get_logger, ActivityLog

logger = get_logger("harvester")
activity = ActivityLog("harvester")

RAW_DIR = _root / "data" / "raw"
SCOUT_DIR = _root / "data" / "raw" / "scout"
RAW_DIR.mkdir(parents=True, exist_ok=True)

_cfg = get_scraping_config()
_CHECKPOINT_FILE = _root / "data" / ".harvester_checkpoint.json"


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_item(
    platform: str,
    type_: str,
    id_: str,
    content: str,
    media: list[str] | None = None,
    metadata: dict | None = None,
) -> dict:
    return {
        "platform": platform,
        "type": type_,
        "id": id_,
        "content": content,
        "media": media or [],
        "metadata": {
            "like": 0,
            "timestamp": _now_utc(),
            "location": None,
            "user": None,
            **(metadata or {}),
        },
        "scraped_at": _now_utc(),
    }


# ── Checkpoint (resume on interrupt) ──────────────────────────────────────────

def _load_checkpoint() -> set[str]:
    if _CHECKPOINT_FILE.exists():
        data = json.loads(_CHECKPOINT_FILE.read_text(encoding="utf-8"))
        return set(data.get("done", []))
    return set()


def _save_checkpoint(done: set[str]) -> None:
    _CHECKPOINT_FILE.write_text(
        json.dumps({"done": list(done), "updated": _now_utc()}, indent=2),
        encoding="utf-8",
    )


# ── YouTube ────────────────────────────────────────────────────────────────────

def harvest_youtube(entry: dict) -> list[dict]:
    results = []
    url = entry.get("url", "")
    api_key = get_api_key("youtube")

    # Extract video ID from URL
    vid_id = None
    if "watch?v=" in url:
        vid_id = url.split("watch?v=")[-1].split("&")[0]
    elif "youtu.be/" in url:
        vid_id = url.split("youtu.be/")[-1].split("?")[0]

    if vid_id and api_key:
        try:
            # Video metadata
            meta_url = (
                f"https://www.googleapis.com/youtube/v3/videos"
                f"?part=snippet,statistics&id={vid_id}&key={api_key}"
            )
            r = safe_get(meta_url)
            if r and r.status_code == 200:
                items = r.json().get("items", [])
                for item in items:
                    s = item.get("snippet", {})
                    st = item.get("statistics", {})
                    results.append(_make_item(
                        "YouTube", "video", vid_id,
                        s.get("description", ""),
                        media=[s.get("thumbnails", {}).get("high", {}).get("url", "")],
                        metadata={
                            "title": s.get("title", ""),
                            "like": int(st.get("likeCount", 0)),
                            "view": int(st.get("viewCount", 0)),
                            "comment_count": int(st.get("commentCount", 0)),
                            "timestamp": s.get("publishedAt", _now_utc()),
                            "user": s.get("channelTitle", ""),
                            "channel_id": s.get("channelId", ""),
                            "tags": s.get("tags", []),
                        },
                    ))

            # Comments
            comments_url = (
                f"https://www.googleapis.com/youtube/v3/commentThreads"
                f"?part=snippet&videoId={vid_id}&maxResults=100&key={api_key}"
            )
            r = safe_get(comments_url)
            if r and r.status_code == 200:
                for item in r.json().get("items", []):
                    c = item["snippet"]["topLevelComment"]["snippet"]
                    results.append(_make_item(
                        "YouTube", "comment", item["id"],
                        c.get("textDisplay", ""),
                        metadata={
                            "like": c.get("likeCount", 0),
                            "timestamp": c.get("publishedAt", _now_utc()),
                            "user": c.get("authorDisplayName", ""),
                            "video_id": vid_id,
                        },
                    ))
            activity.log("harvest", "youtube", "ok", {"vid_id": vid_id, "items": len(results)})
        except Exception as e:
            activity.log("harvest", "youtube", "error", {"error": str(e), "url": url})
    elif vid_id:
        # Scrape without API
        try:
            r = safe_get(f"https://www.youtube.com/watch?v={vid_id}", headers=get_headers())
            if r and r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                title = soup.find("meta", {"name": "title"})
                desc = soup.find("meta", {"name": "description"})
                results.append(_make_item(
                    "YouTube", "video", vid_id,
                    desc["content"] if desc else "",
                    metadata={
                        "title": title["content"] if title else "",
                        "timestamp": _now_utc(),
                    },
                ))
        except Exception as e:
            activity.log("harvest_scrape", "youtube", "error", {"error": str(e)})

    # Search results
    if entry.get("type") == "keyword" and api_key:
        kw = entry.get("identifier", "")
        try:
            search_url = (
                f"https://www.googleapis.com/youtube/v3/search"
                f"?part=snippet&q={requests.utils.quote(kw)}&maxResults=25&type=video&key={api_key}"
            )
            r = safe_get(search_url)
            if r and r.status_code == 200:
                for item in r.json().get("items", []):
                    s = item.get("snippet", {})
                    results.append(_make_item(
                        "YouTube", "video", item["id"].get("videoId", ""),
                        s.get("description", ""),
                        media=[s.get("thumbnails", {}).get("high", {}).get("url", "")],
                        metadata={
                            "title": s.get("title", ""),
                            "timestamp": s.get("publishedAt", _now_utc()),
                            "user": s.get("channelTitle", ""),
                            "keyword": kw,
                        },
                    ))
        except Exception as e:
            activity.log("search_harvest", "youtube", "error", {"error": str(e)})
    return results


# ── Reddit ─────────────────────────────────────────────────────────────────────

def harvest_reddit(entry: dict) -> list[dict]:
    results = []
    url = entry.get("url", "")
    identifier = entry.get("identifier", "")

    # Determine subreddit or post
    if "/r/" in url:
        subreddit = url.split("/r/")[-1].split("/")[0]
        try:
            r = safe_get(
                f"https://www.reddit.com/r/{subreddit}/hot.json?limit=50",
                headers=get_headers({"Accept": "application/json"}),
            )
            if r and r.status_code == 200:
                for post in r.json()["data"]["children"]:
                    d = post["data"]
                    results.append(_make_item(
                        "Reddit", "post", d.get("id", ""),
                        d.get("selftext", "") or d.get("title", ""),
                        media=[d.get("url", "")] if d.get("url", "").startswith("http") and not d.get("is_self") else [],
                        metadata={
                            "title": d.get("title", ""),
                            "like": d.get("score", 0),
                            "timestamp": datetime.utcfromtimestamp(d.get("created_utc", 0)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "user": d.get("author", ""),
                            "subreddit": subreddit,
                            "num_comments": d.get("num_comments", 0),
                            "url": d.get("url", ""),
                            "flair": d.get("link_flair_text", ""),
                        },
                    ))

                    # Fetch comments for first 5 posts
                    if len([r2 for r2 in results if r2["type"] == "post"]) <= 5:
                        random_delay(1, 3)
                        comments = _fetch_reddit_comments(subreddit, d.get("id", ""))
                        results.extend(comments)

            activity.log("harvest", "reddit", "ok", {"subreddit": subreddit, "items": len(results)})
        except Exception as e:
            activity.log("harvest", "reddit", "error", {"error": str(e), "subreddit": identifier})
    return results


def _fetch_reddit_comments(subreddit: str, post_id: str) -> list[dict]:
    results = []
    try:
        r = safe_get(
            f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json?limit=50",
            headers=get_headers({"Accept": "application/json"}),
        )
        if r and r.status_code == 200:
            data = r.json()
            if len(data) > 1:
                for comment in data[1]["data"]["children"]:
                    c = comment.get("data", {})
                    body = c.get("body", "")
                    if body and body != "[deleted]":
                        results.append(_make_item(
                            "Reddit", "comment", c.get("id", ""),
                            body,
                            metadata={
                                "like": c.get("score", 0),
                                "timestamp": datetime.utcfromtimestamp(c.get("created_utc", 0)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                "user": c.get("author", ""),
                                "post_id": post_id,
                                "subreddit": subreddit,
                            },
                        ))
    except Exception:
        pass
    return results


# ── Twitter / X ────────────────────────────────────────────────────────────────

def harvest_twitter(entry: dict) -> list[dict]:
    results = []
    identifier = entry.get("identifier", "")
    url = entry.get("url", "")
    bearer = get_api_key("twitter_bearer")

    if bearer:
        query = f"#{identifier} lang:id" if entry.get("type") == "hashtag" else identifier
        try:
            r = safe_get(
                f"https://api.twitter.com/2/tweets/search/recent"
                f"?query={requests.utils.quote(query)}&max_results=100"
                f"&tweet.fields=created_at,public_metrics,author_id,lang,entities"
                f"&expansions=author_id&user.fields=username,name",
                headers={"Authorization": f"Bearer {bearer}"},
            )
            if r and r.status_code == 200:
                data = r.json()
                users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
                for tweet in data.get("data", []):
                    metrics = tweet.get("public_metrics", {})
                    author = users.get(tweet.get("author_id", ""), {})
                    results.append(_make_item(
                        "Twitter", "tweet", tweet["id"],
                        tweet.get("text", ""),
                        metadata={
                            "like": metrics.get("like_count", 0),
                            "retweet": metrics.get("retweet_count", 0),
                            "reply": metrics.get("reply_count", 0),
                            "timestamp": tweet.get("created_at", _now_utc()),
                            "user": author.get("username", ""),
                            "user_name": author.get("name", ""),
                            "lang": tweet.get("lang", ""),
                            "hashtags": [h["tag"] for h in tweet.get("entities", {}).get("hashtags", [])],
                        },
                    ))
            activity.log("harvest", "twitter", "ok", {"query": query, "items": len(results)})
        except Exception as e:
            activity.log("harvest", "twitter", "error", {"error": str(e)})
    else:
        # Fallback: Nitter
        try:
            nitter_url = f"https://nitter.privacydev.net/search?q={requests.utils.quote(identifier)}&f=tweets"
            r = safe_get(nitter_url, headers=get_headers())
            if r and r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for tweet_div in soup.select("div.tweet-content")[:50]:
                    text = tweet_div.get_text(strip=True)
                    if text:
                        results.append(_make_item(
                            "Twitter", "tweet", f"nitter_{hash(text) & 0xFFFFFF:06x}",
                            text, metadata={"source": "nitter"},
                        ))
            activity.log("harvest_nitter", "twitter", "ok", {"items": len(results)})
        except Exception as e:
            activity.log("harvest_nitter", "twitter", "error", {"error": str(e)})
    return results


# ── Instagram ──────────────────────────────────────────────────────────────────

def harvest_instagram(entry: dict) -> list[dict]:
    """Instagram requires Selenium (headless) for most content."""
    results = []
    url = entry.get("url", "")
    identifier = entry.get("identifier", "")

    try:
        # Public hashtag page via JSON endpoint
        hashtag = identifier.lstrip("#")
        api_url = f"https://www.instagram.com/explore/tags/{hashtag}/?__a=1&__d=dis"
        r = safe_get(api_url, headers=get_json_headers({
            "Referer": "https://www.instagram.com/",
            "X-Requested-With": "XMLHttpRequest",
        }))
        if r and r.status_code == 200 and r.text.startswith("{"):
            data = r.json()
            edges = (
                data.get("graphql", {})
                    .get("hashtag", {})
                    .get("edge_hashtag_to_media", {})
                    .get("edges", [])
            )
            for edge in edges[:50]:
                n = edge.get("node", {})
                results.append(_make_item(
                    "Instagram", "post", n.get("id", ""),
                    n.get("edge_media_to_caption", {}).get("edges", [{}])[0].get("node", {}).get("text", ""),
                    media=[n.get("display_url", "")],
                    metadata={
                        "like": n.get("edge_liked_by", {}).get("count", 0),
                        "timestamp": datetime.utcfromtimestamp(n.get("taken_at_timestamp", 0)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "user": n.get("owner", {}).get("username", ""),
                        "shortcode": n.get("shortcode", ""),
                        "hashtag": hashtag,
                    },
                ))
            activity.log("harvest_json", "instagram", "ok", {"hashtag": hashtag, "items": len(results)})
        else:
            # Needs Selenium for login-gated content
            activity.log("harvest", "instagram", "warn", {
                "note": "JSON endpoint unavailable — use Selenium harvester",
                "hashtag": hashtag,
            })
            results = _harvest_instagram_selenium(url, hashtag)
    except Exception as e:
        activity.log("harvest", "instagram", "error", {"error": str(e)})
    return results


def _harvest_instagram_selenium(url: str, hashtag: str) -> list[dict]:
    """Headless Selenium fallback for Instagram."""
    results = []
    try:
        driver = make_driver(headless=True)
        driver.get(url)
        random_delay(3, 6)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        driver.quit()
        for article in soup.select("article")[:20]:
            img = article.find("img")
            caption = article.find("div", {"class": re.compile("caption")})
            results.append(_make_item(
                "Instagram", "post", f"ig_{hash(url) & 0xFFFFFF:06x}",
                caption.get_text(strip=True) if caption else "",
                media=[img["src"]] if img else [],
                metadata={"hashtag": hashtag, "source": "selenium"},
            ))
    except Exception as e:
        activity.log("selenium_harvest", "instagram", "error", {"error": str(e)})
    return results


# ── TikTok ─────────────────────────────────────────────────────────────────────

def harvest_tiktok(entry: dict) -> list[dict]:
    """TikTok requires Selenium. Uses unofficial API endpoint as first attempt."""
    results = []
    hashtag = entry.get("identifier", "").lstrip("#")

    try:
        # Unofficial hashtag API
        api_url = f"https://www.tiktok.com/api/challenge/item_list/?challengeName={hashtag}&count=30&cursor=0"
        r = safe_get(api_url, headers=get_json_headers({
            "Referer": "https://www.tiktok.com/",
        }))
        if r and r.status_code == 200 and "itemList" in r.text:
            for item in r.json().get("itemList", []):
                video = item.get("video", {})
                author = item.get("author", {})
                stats = item.get("stats", {})
                desc = item.get("desc", "")
                results.append(_make_item(
                    "TikTok", "video", item.get("id", ""),
                    desc,
                    media=[video.get("originCover", "")],
                    metadata={
                        "like": stats.get("diggCount", 0),
                        "view": stats.get("playCount", 0),
                        "share": stats.get("shareCount", 0),
                        "comment": stats.get("commentCount", 0),
                        "timestamp": datetime.utcfromtimestamp(item.get("createTime", 0)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "user": author.get("uniqueId", ""),
                        "hashtag": hashtag,
                        "music": item.get("music", {}).get("title", ""),
                    },
                ))
            activity.log("harvest_api", "tiktok", "ok", {"hashtag": hashtag, "items": len(results)})
        else:
            # Selenium fallback
            results = _harvest_tiktok_selenium(hashtag)
    except Exception as e:
        activity.log("harvest", "tiktok", "error", {"error": str(e)})
        results = _harvest_tiktok_selenium(hashtag)
    return results


def _harvest_tiktok_selenium(hashtag: str) -> list[dict]:
    results = []
    try:
        driver = make_driver(headless=True)
        driver.get(f"https://www.tiktok.com/tag/{hashtag}")
        random_delay(3, 7)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        driver.quit()
        for div in soup.select("div[data-e2e='challenge-item']")[:30]:
            img = div.find("img")
            link = div.find("a")
            results.append(_make_item(
                "TikTok", "video", f"tt_{hash(hashtag) & 0xFFFFFF:06x}",
                "",
                media=[img["src"]] if img else [],
                metadata={"hashtag": hashtag, "url": link.get("href", "") if link else ""},
            ))
        activity.log("harvest_selenium", "tiktok", "ok", {"hashtag": hashtag, "items": len(results)})
    except Exception as e:
        activity.log("harvest_selenium", "tiktok", "error", {"error": str(e)})
    return results


# ── Facebook ───────────────────────────────────────────────────────────────────

def harvest_facebook(entry: dict) -> list[dict]:
    """Facebook requires Selenium for most content."""
    results = []
    url = entry.get("url", "")
    identifier = entry.get("identifier", "")
    try:
        driver = make_driver(headless=True)
        driver.get(url)
        random_delay(3, 6)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        driver.quit()
        for post in soup.select("div[data-testid='post_message']")[:20]:
            text = post.get_text(strip=True)
            if text:
                results.append(_make_item(
                    "Facebook", "post", f"fb_{hash(text) & 0xFFFFFF:06x}",
                    text, metadata={"keyword": identifier},
                ))
        activity.log("harvest_selenium", "facebook", "ok", {"items": len(results)})
    except Exception as e:
        activity.log("harvest_selenium", "facebook", "error", {"error": str(e)})
    return results


# ── Medium ─────────────────────────────────────────────────────────────────────

def harvest_medium(entry: dict) -> list[dict]:
    results = []
    tag = entry.get("identifier", "")
    try:
        r = safe_get(
            f"https://medium.com/tag/{tag}/archive",
            headers=get_headers(),
        )
        if r and r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for article in soup.select("article")[:30]:
                title_el = article.find("h2") or article.find("h3")
                author_el = article.find("a", {"data-action": "show-user-card"})
                link_el = article.find("a", {"data-action": "open-post"})
                claps_el = article.find("button", {"data-action": "show-recommends"})
                title = title_el.get_text(strip=True) if title_el else ""
                if title:
                    results.append(_make_item(
                        "Medium", "post", f"med_{hash(title) & 0xFFFFFF:06x}",
                        title,
                        metadata={
                            "like": int(re.sub(r"[^\d]", "", claps_el.text) or 0) if claps_el else 0,
                            "user": author_el.get_text(strip=True) if author_el else "",
                            "url": link_el.get("href", "") if link_el else "",
                            "tag": tag,
                        },
                    ))
        activity.log("harvest", "medium", "ok", {"tag": tag, "items": len(results)})
    except Exception as e:
        activity.log("harvest", "medium", "error", {"error": str(e)})
    return results


# ── Twitch ─────────────────────────────────────────────────────────────────────

def harvest_twitch(entry: dict) -> list[dict]:
    results = []
    game = entry.get("identifier", "")
    try:
        r = safe_get(
            f"https://api.twitch.tv/helix/streams?game_id={game}&first=25",
            headers=get_json_headers({"Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko"}),
        )
        if r and r.status_code == 200:
            for stream in r.json().get("data", []):
                results.append(_make_item(
                    "Twitch", "stream", stream.get("id", ""),
                    stream.get("title", ""),
                    media=[stream.get("thumbnail_url", "").replace("{width}", "640").replace("{height}", "360")],
                    metadata={
                        "like": stream.get("viewer_count", 0),
                        "timestamp": stream.get("started_at", _now_utc()),
                        "user": stream.get("user_name", ""),
                        "game": game,
                        "tags": stream.get("tags", []),
                    },
                ))
        activity.log("harvest", "twitch", "ok", {"game": game, "items": len(results)})
    except Exception as e:
        activity.log("harvest", "twitch", "error", {"error": str(e)})
    return results


# ── Generic HTML scraper ───────────────────────────────────────────────────────

def harvest_generic(entry: dict) -> list[dict]:
    """Fallback scraper for any URL — extracts text content."""
    results = []
    url = entry.get("url", "")
    platform = entry.get("platform", "Unknown")
    if not url:
        return results
    try:
        r = safe_get(url, headers=get_headers())
        if r and r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for s in soup(["script", "style", "nav", "footer", "header"]):
                s.decompose()
            text = soup.get_text(separator="\n", strip=True)
            paragraphs = [p.strip() for p in text.split("\n") if len(p.strip()) > 50][:20]
            if paragraphs:
                results.append(_make_item(
                    platform, "page", f"gen_{hash(url) & 0xFFFFFF:06x}",
                    "\n".join(paragraphs),
                    metadata={"url": url},
                ))
        activity.log("harvest_generic", platform, "ok", {"url": url})
    except Exception as e:
        activity.log("harvest_generic", platform, "error", {"error": str(e)})
    return results


# ── Platform dispatcher ────────────────────────────────────────────────────────

_HARVESTERS = {
    "youtube":   harvest_youtube,
    "tiktok":    harvest_tiktok,
    "instagram": harvest_instagram,
    "facebook":  harvest_facebook,
    "twitter":   harvest_twitter,
    "reddit":    harvest_reddit,
    "medium":    harvest_medium,
    "twitch":    harvest_twitch,
}


def _dispatch(entry: dict) -> list[dict]:
    platform = entry.get("platform", "").lower()
    fn = _HARVESTERS.get(platform, harvest_generic)
    return fn(entry)


# ── HarvesterAgent class ───────────────────────────────────────────────────────

class HarvesterAgent:
    """Reads scout targets and harvests raw data. Supports resume on interrupt."""

    def run(self, scout_file: Optional[Path] = None) -> dict[str, list[dict]]:
        targets = self._load_targets(scout_file)
        if not targets:
            logger.warning("No targets found. Run ScoutAgent first.")
            return {}

        done = _load_checkpoint()
        logger.info(f"Harvester start — {len(targets)} targets, {len(done)} already done")

        results: dict[str, list[dict]] = {}

        for entry in targets:
            key = f"{entry['platform']}::{entry['identifier']}"
            if key in done:
                logger.debug(f"Skip (already done): {key}")
                continue

            platform = entry.get("platform", "unknown").lower()
            if not is_platform_enabled(platform):
                continue

            try:
                logger.info(f"Harvesting [{platform}] {entry.get('identifier', '')}...")
                items = _dispatch(entry)
                if items:
                    results.setdefault(platform, []).extend(items)
                    self._save_partial(platform, items)
                done.add(key)
                _save_checkpoint(done)
                random_delay()
            except KeyboardInterrupt:
                _save_checkpoint(done)
                logger.info("Harvester interrupted — checkpoint saved")
                raise
            except Exception as e:
                activity.log("run", platform, "error", {"entry": key, "error": str(e)})

        total = sum(len(v) for v in results.values())
        logger.info(f"Harvester complete — {total} items across {len(results)} platforms")
        return results

    def _load_targets(self, scout_file: Optional[Path] = None) -> list[dict]:
        if scout_file and scout_file.exists():
            return json.loads(scout_file.read_text(encoding="utf-8"))
        # Find most recent combined scout file
        files = sorted(SCOUT_DIR.glob("combined_*.json"), reverse=True)
        if not files:
            # Fall back to any scout file
            files = sorted(SCOUT_DIR.glob("*.json"), reverse=True)
        if not files:
            return []
        data = json.loads(files[0].read_text(encoding="utf-8"))
        logger.info(f"Loaded targets from {files[0].name}")
        return data if isinstance(data, list) else []

    def _save_partial(self, platform: str, items: list[dict]) -> None:
        out_dir = RAW_DIR / platform.lower()
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        out_file = out_dir / f"{platform}_{ts}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
        activity.log("save", platform, "ok", {"file": out_file.name, "items": len(items)})


if __name__ == "__main__":
    agent = HarvesterAgent()
    agent.run()
