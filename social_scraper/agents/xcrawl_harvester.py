"""
xcrawl_harvester.py — Social Media Scraper via xcrawl.com API
==============================================================
Uses xcrawl's JS-rendered scraping service to collect content from
YouTube, TikTok, Facebook, and Instagram. Saves raw markdown + parsed
JSON to social_scraper/data/raw/<platform>/.
"""
import json
import sys
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))

from utils.logger import get_logger, ActivityLog

logger = get_logger("xcrawl")
activity = ActivityLog("xcrawl")

# ── Config ─────────────────────────────────────────────────────────────────────
XCRAWL_URL   = "https://run.xcrawl.com/v1/scrape"
XCRAWL_TOKEN = "xc-VyoRhxnsnXt1c34F83qBeu4tv4OFxeac1HXw6RRpanNfAUBN"
HEADERS = {
    "Authorization": f"Bearer {XCRAWL_TOKEN}",
    "Content-Type":  "application/json",
}
OUT_DIR = _root / "data" / "raw"

# Platform targets: list of (label, url, category)
PLATFORM_TARGETS = {
    "youtube": [
        ("trending_id",   "https://www.youtube.com/results?search_query=trending+indonesia",   "search"),
        ("trending_ai",   "https://www.youtube.com/results?search_query=AI+technology+2025",   "search"),
        ("trending_music","https://www.youtube.com/results?search_query=music+trending+2025",  "search"),
        ("shorts",        "https://www.youtube.com/shorts",                                    "shorts"),
    ],
    "tiktok": [
        ("explore",       "https://www.tiktok.com/explore",                                    "explore"),
        ("tag_viral",     "https://www.tiktok.com/tag/viral",                                  "hashtag"),
        ("tag_fyp",       "https://www.tiktok.com/tag/fyp",                                    "hashtag"),
        ("tag_indonesia", "https://www.tiktok.com/tag/indonesia",                              "hashtag"),
    ],
    "facebook": [
        ("home",          "https://www.facebook.com",                                          "homepage"),
        ("gaming",        "https://www.facebook.com/gaming/",                                  "page"),
        ("news",          "https://www.facebook.com/facebookapp/",                             "page"),
    ],
    "instagram": [
        ("explore",       "https://www.instagram.com/explore/",                                "explore"),
        ("tag_viral",     "https://www.instagram.com/explore/tags/viral/",                     "hashtag"),
        ("tag_trending",  "https://www.instagram.com/explore/tags/trending/",                  "hashtag"),
        ("tag_indonesia", "https://www.instagram.com/explore/tags/indonesia/",                 "hashtag"),
    ],
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _xcrawl(url: str, only_main: bool = True, timeout: int = 90) -> Optional[dict]:
    """Call xcrawl API and return the parsed response data dict, or None on failure."""
    payload = {
        "url": url,
        "mode": "sync",
        "proxy": {"location": "US"},
        "request": {
            "locale": "en-US",
            "device": "desktop",
            "only_main_content": only_main,
        },
        "js_render": {"enabled": True},
        "output": {"formats": ["markdown"]},
    }
    try:
        r = requests.post(XCRAWL_URL, headers=HEADERS, json=payload, timeout=timeout)
        if r.status_code == 200:
            return r.json().get("data", {})
        logger.warning(f"xcrawl HTTP {r.status_code} for {url}: {r.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"xcrawl request failed for {url}: {e}")
        return None


def _parse_markdown(platform: str, label: str, url: str,
                    category: str, data: dict) -> dict:
    """Wrap raw xcrawl data into our standard item schema."""
    md   = data.get("markdown", "")
    meta = data.get("metadata", {})
    return {
        "platform":    platform,
        "type":        category,
        "id":          f"xcrawl_{platform}_{label}_{int(time.time())}",
        "url":         url,
        "content":     md,
        "media":       [],
        "metadata": {
            "title":       meta.get("title", ""),
            "description": meta.get("description", ""),
            "og_image":    meta.get("og:image", ""),
            "scraped_at":  _now_utc(),
            "label":       label,
            "credits_used": data.get("credits_used", 0),
        },
        "scraped_at":  _now_utc(),
        "raw_length":  len(md),
    }


def scrape_platform(platform: str, targets: list[tuple]) -> list[dict]:
    """Scrape all targets for one platform. Returns list of items."""
    items = []
    logger.info(f"[{platform.upper()}] Scraping {len(targets)} targets…")
    for label, url, category in targets:
        logger.info(f"  >> {label}: {url}")
        data = _xcrawl(url)
        if data and data.get("markdown"):
            item = _parse_markdown(platform, label, url, category, data)
            items.append(item)
            activity.log("scrape", platform, "ok", {
                "label": label, "chars": item["raw_length"],
                "credits": data.get("credits_used", 0),
            })
            logger.info(f"     OK {item['raw_length']} chars")
        else:
            activity.log("scrape", platform, "empty", {"label": label, "url": url})
            logger.warning(f"     FAIL empty or failed")
        time.sleep(2)  # polite delay between requests
    return items


def _save(platform: str, items: list[dict]) -> Path:
    """Save scraped items as JSON. Returns the output file path."""
    out_dir = OUT_DIR / platform
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"xcrawl_{platform}_{ts}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved {len(items)} items → {out_file}")
    return out_file


class XcrawlHarvester:
    """Harvests social media content via xcrawl.com JS-render API."""

    def run(
        self,
        platforms: list[str] | None = None,
        keywords: list[str] | None = None,
    ) -> dict[str, Path]:
        """
        Run the harvester. Optionally inject keywords into search targets.

        Args:
            platforms: limit to these platforms (default: all 4)
            keywords:  extra search terms to append to YouTube/TikTok searches

        Returns:
            dict mapping platform → saved JSON file path
        """
        targets_map = {}
        active = platforms or list(PLATFORM_TARGETS.keys())

        for plat in active:
            base = list(PLATFORM_TARGETS.get(plat, []))
            if keywords and plat == "youtube":
                for kw in keywords[:3]:
                    kw_slug = kw.replace(" ", "+")
                    base.append((
                        f"kw_{kw_slug[:20]}",
                        f"https://www.youtube.com/results?search_query={kw_slug}",
                        "search",
                    ))
            if keywords and plat == "tiktok":
                for kw in keywords[:3]:
                    kw_slug = kw.replace(" ", "")
                    base.append((
                        f"kw_{kw_slug[:20]}",
                        f"https://www.tiktok.com/tag/{kw_slug}",
                        "hashtag",
                    ))
            if keywords and plat == "instagram":
                for kw in keywords[:3]:
                    kw_slug = kw.replace(" ", "").lower()
                    base.append((
                        f"kw_{kw_slug[:20]}",
                        f"https://www.instagram.com/explore/tags/{kw_slug}/",
                        "hashtag",
                    ))
            targets_map[plat] = base

        saved_files = {}
        total_items = 0

        for plat, targets in targets_map.items():
            items = scrape_platform(plat, targets)
            if items:
                path = _save(plat, items)
                saved_files[plat] = path
                total_items += len(items)
                logger.info(f"[{plat.upper()}] Done — {len(items)} items saved")
            else:
                logger.warning(f"[{plat.upper()}] No items collected")

        logger.info(f"XcrawlHarvester complete — {total_items} total items, {len(saved_files)} platforms")
        return saved_files


# ── CLI runner ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="xcrawl social media harvester")
    parser.add_argument("--platforms", "-p", nargs="+",
                        choices=list(PLATFORM_TARGETS.keys()),
                        default=["youtube", "tiktok", "facebook", "instagram"],
                        help="Platforms to scrape (default: all 4)")
    parser.add_argument("--keywords", "-k", nargs="+", help="Extra search keywords")
    args = parser.parse_args()

    harvester = XcrawlHarvester()
    saved = harvester.run(platforms=args.platforms, keywords=args.keywords)

    print("\n=== Files saved ===")
    for plat, path in saved.items():
        print(f"  {plat}: {path}")
