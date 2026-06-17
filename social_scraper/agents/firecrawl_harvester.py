"""
Firecrawl-inspired multi-agent social media trend harvester.

Architecture mirrors Firecrawl's engine waterfall pipeline:

  Per platform — 3 sequential micro-agents:
    [1] DiscoveryAgent  — DuckDuckGo search → top 6 domain-diverse source URLs
    [2] ScraperAgent    — Waterfall engine strategy (Firecrawl's scrapeURL loop):
                            Engine 1: requests + html2text       (fast,  8s timeout)
                            Engine 2: Playwright headless        (JS,   20s timeout)
                            Engine 3: Firecrawl API              (premium, 25s, if key set)
                          Each engine passes a quality gate (≥300 meaningful chars).
                          Fatal errors (SSL, DNS, 404) abort remaining engines for that URL.
    [3] ExtractorAgent  — Mistral-small extracts + deduplicates structured trending topics

  Platforms run in parallel (ThreadPoolExecutor, max 3 concurrent).

Key Firecrawl patterns adopted:
  • Engine waterfall  — time-ordered engine cascade, first success wins
  • Quality gate      — markdown length + HTTP status check (mirrors Firecrawl's isLongEnough)
  • Error classes     — FatalScrapeError vs retryable; skip remaining engines on fatal
  • Content routing   — HTML → html2text, PDF → pdfminer, binary → skip
  • URL diversity     — DiscoveryAgent caps 2 URLs per domain
  • Deduplication     — ExtractorAgent strips repeated topics before returning

Output: social_scraper/data/raw/<platform>/firecrawl_<platform>_<ts>.json

Environment:
  FIRECRAWL_API_KEY  (optional) — premium Firecrawl API (JS rendering, anti-bot)
  MISTRAL_API_KEY    (required) — used by ExtractorAgent
"""

import os
import re
import json
import time
import threading
import requests
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutureTimeout

from dotenv import load_dotenv
load_dotenv()

# ─── Platform config ──────────────────────────────────────────────────────────

PLATFORM_QUERIES = {
    "youtube":    "YouTube trending videos viral popular creators today 2026",
    "tiktok":     "TikTok trending hashtags viral challenges creators today 2026",
    "facebook":   "Facebook trending topics viral posts discussion today 2026",
    "instagram":  "Instagram trending reels viral hashtags explore today 2026",
    "twitter":    "Twitter X trending topics viral tweets discussions today 2026",
    "reddit":     "Reddit top posts rising trending viral communities today 2026",
    "linkedin":   "LinkedIn trending professional topics insights articles today 2026",
    "medium":     "Medium trending articles popular reads technology today 2026",
    "twitch":     "Twitch trending streams popular games streamers today 2026",
    "pinterest":  "Pinterest trending pins viral boards aesthetics today 2026",
    "quora":      "Quora trending questions popular discussions answers today 2026",
    "soundcloud": "SoundCloud trending music tracks artists genres today 2026",
}

PLATFORM_LABELS = {
    "youtube": "YouTube", "tiktok": "TikTok", "facebook": "Facebook",
    "instagram": "Instagram", "twitter": "Twitter/X", "reddit": "Reddit",
    "linkedin": "LinkedIn", "medium": "Medium", "twitch": "Twitch",
    "pinterest": "Pinterest", "quora": "Quora", "soundcloud": "SoundCloud",
}

_DATA_DIR = Path(__file__).parent.parent / "data" / "raw"

# ─── Error classes (mirrors Firecrawl's error taxonomy) ───────────────────────

class FatalScrapeError(Exception):
    """Non-retryable: SSL, DNS, 404, unsupported content type.
    Firecrawl pattern: fatal errors skip remaining engines for that URL."""

class EngineScrapeError(Exception):
    """Retryable per-engine failure — waterfall to next engine."""


# ─── Noise filter (shared by all engines) ─────────────────────────────────────

_NOISE_LINE = re.compile(
    r"^(sign in|log in|log out|sign up|register|create account|"
    r"skip navigation|skip to content|back|home|menu|close|open|"
    r"next|previous|load more|see more|show more|cookie|accept|"
    r"privacy policy|terms of service|settings|notifications|"
    r"search|\s*)$",
    re.IGNORECASE,
)
_AUTH_LINK = re.compile(r"\[.{0,40}\]\(.*?/(login|signin|signup|register|auth).*?\)", re.IGNORECASE)

def _clean_markdown(text: str) -> str:
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if len(s) < 25:
            continue
        if _NOISE_LINE.match(s):
            continue
        if _AUTH_LINK.search(s):
            continue
        lines.append(s)
    return "\n".join(lines)

def _quality_gate(text: str) -> bool:
    """Firecrawl's isLongEnough: meaningful content must exceed threshold."""
    return len(text.strip()) >= 300


# ─────────────────────────────────────────────────────────────────────────────
# AGENT 1 — DiscoveryAgent
# DuckDuckGo search → domain-diverse top URLs.
# Firecrawl pattern: source diversity prevents redundant content from same site.
# ─────────────────────────────────────────────────────────────────────────────

class DiscoveryAgent:
    MAX_RESULTS = 6
    MAX_PER_DOMAIN = 2   # Firecrawl-inspired: avoid same-domain duplicates

    def run(self, platform: str, keywords: list | None = None) -> list[str]:
        from ddgs import DDGS

        query = PLATFORM_QUERIES.get(platform, f"{platform} trending today")
        if keywords:
            query += " " + " ".join(keywords)

        raw_urls: list[str] = []
        try:
            with DDGS(timeout=20) as ddgs:
                results = list(ddgs.text(query, max_results=self.MAX_RESULTS * 3))
            raw_urls = [r["href"] for r in results if r.get("href")]
        except Exception as e:
            print(f"  [Discovery:{platform}] DDG error - {e}")

        return self._diversify(raw_urls)

    def _diversify(self, urls: list[str]) -> list[str]:
        """Cap MAX_PER_DOMAIN per eTLD+1 — mirrors Firecrawl's source diversity."""
        domain_counts: dict[str, int] = {}
        diverse: list[str] = []
        for url in urls:
            try:
                host = urlparse(url).netloc.lstrip("www.")
            except Exception:
                host = url
            if domain_counts.get(host, 0) < self.MAX_PER_DOMAIN:
                diverse.append(url)
                domain_counts[host] = domain_counts.get(host, 0) + 1
            if len(diverse) >= self.MAX_RESULTS:
                break
        return diverse


# ─────────────────────────────────────────────────────────────────────────────
# AGENT 2 — ScraperAgent
# Engine waterfall: fetch → playwright → firecrawl.
# Mirrors Firecrawl's scrapeURLLoop: engines race with time-based waterfall;
# first engine to pass the quality gate wins; fatal errors abort the URL.
# ─────────────────────────────────────────────────────────────────────────────

SCRAPER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_FATAL_STATUS = {400, 401, 403, 404, 410, 451}  # Firecrawl: non-retryable HTTP codes
MAX_PAGE_CHARS   = 10_000
MAX_TOTAL_CHARS  = 25_000
ENGINE_TIMEOUTS  = {"fetch": 8, "playwright": 20, "firecrawl": 25}


class ScraperAgent:
    """
    Waterfall engine scraper — Firecrawl's core value proposition in Python.

    Engine order (fastest → most capable):
      1. fetch      — requests + html2text; free, fast, no JS
      2. playwright — headless Chromium; JS-capable, slower
      3. firecrawl  — official API; JS + anti-bot; requires key

    Quality gate applied after each engine: cleaned markdown must be ≥ 300 chars.
    Fatal HTTP codes (403, 404, etc.) raise FatalScrapeError → skip URL entirely.
    """

    def __init__(self):
        self._fc = self._init_firecrawl()
        self._pw = self._init_playwright()
        # Build active engine list in waterfall order
        self._engines: list[str] = ["fetch"]
        if self._pw:
            self._engines.append("playwright")
        if self._fc:
            self._engines.append("firecrawl")
        print(f"  [Scraper] Engines: {' → '.join(self._engines)}")

    def _init_firecrawl(self):
        key = os.getenv("FIRECRAWL_API_KEY", "").strip()
        if not key:
            return None
        try:
            from firecrawl import Firecrawl
            return Firecrawl(api_key=key)
        except ImportError:
            print("  [Scraper] firecrawl-py not installed — pip install firecrawl-py")
            return None

    def _init_playwright(self) -> bool:
        try:
            from playwright.sync_api import sync_playwright
            # Quick import-only check — don't launch yet
            return True
        except ImportError:
            return False

    # ── Engine implementations ────────────────────────────────────────────────

    def _engine_fetch(self, url: str) -> str:
        """Engine 1: requests + html2text. Fastest, no JS rendering."""
        try:
            resp = requests.get(url, timeout=ENGINE_TIMEOUTS["fetch"], headers=SCRAPER_HEADERS)
        except requests.exceptions.SSLError:
            raise FatalScrapeError(f"SSL error: {url}")
        except requests.exceptions.ConnectionError as e:
            raise EngineScrapeError(f"Connection failed: {e}")
        except requests.exceptions.Timeout:
            raise EngineScrapeError("Timeout")

        if resp.status_code in _FATAL_STATUS:
            raise FatalScrapeError(f"HTTP {resp.status_code}")

        content_type = resp.headers.get("Content-Type", "")
        if "pdf" in content_type:
            return self._parse_pdf_bytes(resp.content, url)
        if not any(t in content_type for t in ("html", "text", "xml")):
            raise FatalScrapeError(f"Unsupported content-type: {content_type}")

        return self._html_to_md(resp.text)

    def _engine_playwright(self, url: str) -> str:
        """Engine 2: Playwright headless Chrome. Handles JavaScript-rendered pages."""
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
                page = browser.new_page(
                    user_agent=SCRAPER_HEADERS["User-Agent"],
                    extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
                )
                try:
                    resp = page.goto(url, timeout=ENGINE_TIMEOUTS["playwright"] * 1000,
                                     wait_until="domcontentloaded")
                    if resp and resp.status in _FATAL_STATUS:
                        raise FatalScrapeError(f"HTTP {resp.status}")
                    # Wait for dynamic content to settle
                    page.wait_for_load_state("networkidle", timeout=5000)
                except PWTimeout:
                    pass  # Partial load is still usable
                html = page.content()
                browser.close()
            return self._html_to_md(html)
        except FatalScrapeError:
            raise
        except Exception as e:
            raise EngineScrapeError(f"Playwright: {e}")

    def _engine_firecrawl(self, url: str) -> str:
        """Engine 3: Official Firecrawl API (JS + anti-bot). Premium fallback."""
        try:
            doc = self._fc.scrape(url, formats=["markdown"])
            return doc.markdown or ""
        except Exception as e:
            raise EngineScrapeError(f"Firecrawl API: {e}")

    # ── Content helpers ───────────────────────────────────────────────────────

    def _html_to_md(self, html: str) -> str:
        try:
            import html2text
            h = html2text.HTML2Text()
            h.ignore_links = True
            h.ignore_images = True
            h.body_width = 0
            return h.handle(html)
        except ImportError:
            return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()

    def _parse_pdf_bytes(self, data: bytes, url: str) -> str:
        """Content-type routing for PDFs (mirrors Firecrawl's PDF engine)."""
        try:
            import pdfminer.high_level
            import io
            return pdfminer.high_level.extract_text(io.BytesIO(data))
        except ImportError:
            raise FatalScrapeError(f"pdfminer not installed, skipping PDF: {url}")
        except Exception as e:
            raise FatalScrapeError(f"PDF parse failed: {e}")

    # ── Waterfall orchestration ───────────────────────────────────────────────

    def scrape_one(self, url: str) -> dict | None:
        """
        Waterfall: try engines in order, return first result that passes quality gate.
        Firecrawl pattern: fatal errors abort URL; engine errors cascade to next engine.
        """
        dispatch = {
            "fetch":      self._engine_fetch,
            "playwright": self._engine_playwright,
            "firecrawl":  self._engine_firecrawl,
        }
        for engine in self._engines:
            try:
                raw = dispatch[engine](url)
                cleaned = _clean_markdown(raw)[:MAX_PAGE_CHARS]
                if _quality_gate(cleaned):
                    return {"url": url, "content": cleaned, "chars": len(cleaned), "engine": engine}
                print(f"    [Scraper:{engine}] quality gate failed ({len(cleaned)} chars) — trying next")
            except FatalScrapeError as e:
                print(f"    [Scraper] fatal: {e} — skipping URL")
                return None   # Non-retryable; abort all engines for this URL
            except EngineScrapeError as e:
                print(f"    [Scraper:{engine}] engine error: {e} — waterfalling")
            except Exception as e:
                print(f"    [Scraper:{engine}] unexpected: {e} — waterfalling")
        return None

    def run(self, urls: list[str]) -> list[dict]:
        """Scrape URLs sequentially — prevents nested-pool deadlock on Windows."""
        pages = []
        for url in urls:
            result = self.scrape_one(url)
            if result:
                pages.append(result)
        return pages


# ─────────────────────────────────────────────────────────────────────────────
# AGENT 3 — ExtractorAgent
# Mistral-small extracts structured trending topics, then deduplicates.
# Firecrawl pattern: deduplicateObjectsArray() removes redundant extraction output.
# ─────────────────────────────────────────────────────────────────────────────

_EXTRACT_PROMPT = """\
You are a social media trend content extractor. Based on the following web articles \
about {platform}, extract the most relevant trending information.

Content:
{content}

Output as a bullet-point list (max 20 items, format: "- Topic: brief reason why it's trending"):
- Focus on: popular hashtags, viral creator names, trending events/challenges, current news or issues
- Only include information that ACTUALLY EXISTS in the text above
- Ignore: navigation, ads, login buttons, footers, cookie notices
- Each item must be unique — do not duplicate the same topic"""


def _dedup_topics(items: list[str]) -> list[str]:
    """
    Firecrawl's deduplicateObjectsArray() equivalent.
    Removes items whose first-word (topic key) appears more than once.
    """
    seen_keys: set[str] = set()
    result: list[str] = []
    for item in items:
        # Extract topic key: first word before ":" or first 3 words
        key = item.split(":")[0].strip().lower() if ":" in item else " ".join(item.split()[:3]).lower()
        if key not in seen_keys:
            seen_keys.add(key)
            result.append(item)
    return result


class ExtractorAgent:
    def __init__(self):
        from langchain_mistralai import ChatMistralAI
        self._llm = ChatMistralAI(
            model="mistral-small-latest",
            api_key=os.getenv("MISTRAL_API_KEY", ""),
            temperature=0.1,
            max_tokens=1024,
            timeout=45,
            max_retries=1,
        )

    def run(self, platform: str, pages: list[dict]) -> list[str]:
        if not pages:
            return []

        # Merge pages up to MAX_TOTAL_CHARS, prefer pages from different engines
        sections: list[str] = []
        total = 0
        for p in pages:
            engine_tag = f" [{p.get('engine','?')}]" if p.get("engine") else ""
            chunk = f"[Source{engine_tag}: {p['url'][:80]}]\n{p['content']}"
            if total + len(chunk) > MAX_TOTAL_CHARS:
                break
            sections.append(chunk)
            total += len(chunk)

        combined = "\n\n---\n\n".join(sections)
        prompt = _EXTRACT_PROMPT.format(
            platform=PLATFORM_LABELS.get(platform, platform.upper()),
            content=combined,
        )

        try:
            resp = self._llm.invoke(prompt)
            text = resp.content if hasattr(resp, "content") else str(resp)
            raw_items = [
                line.lstrip("-•* ").strip()
                for line in text.splitlines()
                if line.strip() and line.strip()[0] in "-•*"
            ]
            return _dedup_topics(raw_items) if raw_items else [text.strip()]
        except Exception as e:
            print(f"  [Extractor:{platform}] Mistral error — {e}")
            return []


# ─────────────────────────────────────────────────────────────────────────────
# ORCHESTRATOR — FirecrawlHarvester
# Runs the 3-agent pipeline for each platform, platforms in parallel.
# ─────────────────────────────────────────────────────────────────────────────

class FirecrawlHarvester:
    """
    Multi-agent social media trend harvester — Firecrawl waterfall pattern in Python.

    Pipeline per platform:
        DiscoveryAgent → domain-diverse URL list
        ScraperAgent   → engine waterfall (fetch → playwright → firecrawl)
        ExtractorAgent → deduplicated trending topic list

    Platforms run concurrently (max 3 workers) to respect API rate limits.
    """

    def __init__(self):
        self._discovery  = DiscoveryAgent()
        self._scraper    = ScraperAgent()
        self._extractor  = ExtractorAgent()

    def _run_platform(self, platform: str, keywords: list | None) -> tuple[str, list[dict]]:
        label = PLATFORM_LABELS.get(platform, platform.capitalize())
        print(f"[{platform.upper()}] Starting pipeline...")

        # Agent 1 — Discover (domain-diverse)
        urls = self._discovery.run(platform, keywords)
        if not urls:
            print(f"  [{platform}] No URLs discovered — skipping")
            return platform, []
        print(f"  [{platform}] Discovered {len(urls)} URLs")

        # Agent 2 — Scrape (engine waterfall)
        pages = self._scraper.run(urls)
        if not pages:
            print(f"  [{platform}] Nothing scraped — skipping")
            return platform, []
        total_chars = sum(p["chars"] for p in pages)
        engine_summary = ", ".join(f"{p['engine']}" for p in pages)
        print(f"  [{platform}] Scraped {len(pages)} pages ({total_chars:,} chars) via [{engine_summary}]")

        # Agent 3 — Extract + deduplicate
        topics = self._extractor.run(platform, pages)
        print(f"  [{platform}] Extracted {len(topics)} unique trending topics")

        content = "\n".join(topics) if topics else "\n".join(
            p["content"][:400] for p in pages[:3]
        )
        items = [{
            "platform":    platform,
            "metadata":    {
                "label":       label,
                "urls_scraped": len(pages),
                "engines_used": list({p.get("engine","?") for p in pages}),
            },
            "url":         pages[0]["url"] if pages else "",
            "content":     content,
            "raw_length":  len(content),
            "topics":      topics,
            "sources":     [{"url": p["url"], "chars": p["chars"], "engine": p.get("engine")} for p in pages],
        }]
        return platform, items

    def _save(self, platform: str, items: list[dict]) -> Path:
        out_dir = _DATA_DIR / platform
        out_dir.mkdir(parents=True, exist_ok=True)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = out_dir / f"firecrawl_{platform}_{ts}.json"
        path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def run(self, platforms: list | None = None, keywords: list | None = None) -> dict:
        """
        Harvest trending content for the given platforms.

        Args:
            platforms: list of platform keys (defaults to all 12)
            keywords:  optional filter terms (e.g. ["AI", "Indonesia"])

        Returns:
            dict[platform_key → Path]  paths to raw JSON files
        """
        active = [p for p in (platforms or list(PLATFORM_QUERIES.keys()))
                  if p in PLATFORM_QUERIES]
        saved: dict = {}
        _PLATFORM_TIMEOUT = 120  # seconds max per platform

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {
                pool.submit(self._run_platform, plat, keywords): plat
                for plat in active
            }
            try:
                for future in as_completed(futures, timeout=_PLATFORM_TIMEOUT * len(active)):
                    plat = futures[future]
                    try:
                        _, items = future.result(timeout=_PLATFORM_TIMEOUT)
                        if items:
                            path = self._save(plat, items)
                            saved[plat] = path
                            print(f"[{plat.upper()}] Saved: {path.name}")
                        else:
                            print(f"[{plat.upper()}] No data")
                    except FutureTimeout:
                        print(f"[{plat.upper()}] Timed out — skipping")
                    except Exception as exc:
                        print(f"[{plat.upper()}] Pipeline error: {exc}")
            except FutureTimeout:
                print("[Harvester] Global timeout reached — collecting partial results")
                for future, plat in futures.items():
                    if future.done() and plat not in saved:
                        try:
                            _, items = future.result()
                            if items:
                                path = self._save(plat, items)
                                saved[plat] = path
                        except Exception:
                            pass

        return saved
