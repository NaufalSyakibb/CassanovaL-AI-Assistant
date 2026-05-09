"""
Agent Cleaner — Data Normalizer & Spam Detector
=================================================
Reads raw data from data/raw/{platform}/, applies:
  1. Deduplication by content hash
  2. Number normalization ("1.2K" → 1200)
  3. Timestamp standardization to UTC ISO-8601
  4. Language detection + optional translation
  5. Bot/spam detection (heuristics + optional ML)
  6. Missing-field handling

Output saved to data/cleaned/{platform}/.

Output format per item:
{
    "platform": "Instagram",
    "type": "comment",
    "id": "123456789",
    "content": "Original text",
    "content_translated": "...",   # if non-English
    "language": "en",
    "is_spam": false,
    "media": [],
    "metadata": {
        "like": 1200,
        "timestamp": "2024-05-20T05:00:00Z",
        "location": null,
        "user": "username",
        "user_type": "human"
    }
}
"""
import json
import re
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))

from utils.config_loader import get_api_key, get
from utils.logger import get_logger, ActivityLog

logger = get_logger("cleaner")
activity = ActivityLog("cleaner")

RAW_DIR    = _root / "data" / "raw"
CLEAN_DIR  = _root / "data" / "cleaned"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)


# ── Number normalizer ─────────────────────────────────────────────────────────

_SUFFIX_MAP = {
    "k": 1_000, "K": 1_000,
    "m": 1_000_000, "M": 1_000_000,
    "b": 1_000_000_000, "B": 1_000_000_000,
    "rb": 1_000, "jt": 1_000_000,   # Indonesian: ribu, juta
}

def normalize_number(value) -> int | float | None:
    """Convert '1.2K', '500K', '1.5M', '2rb', etc. to int/float."""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip().replace(",", "").replace(".", "").replace("\xa0", "")
    # Try direct parse first
    try:
        return int(s)
    except ValueError:
        pass
    # Suffix parse
    m = re.match(r"^([\d]+(?:[.,]\d+)?)\s*([KkMmBbRrJj][bBtT]?)$", str(value).strip())
    if m:
        num = float(m.group(1).replace(",", "."))
        suffix = m.group(2)
        for key, mult in _SUFFIX_MAP.items():
            if suffix.lower() == key.lower():
                return int(num * mult)
    # Extract first digit sequence
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else 0


# ── Timestamp normalizer ───────────────────────────────────────────────────────

_TZ_OFFSETS = re.compile(r"([+-]\d{2}):?(\d{2})$")

def normalize_timestamp(ts) -> Optional[str]:
    """Normalize any timestamp string to UTC ISO-8601 ('2024-05-20T05:00:00Z')."""
    if not ts:
        return None
    if isinstance(ts, (int, float)):
        try:
            return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (OSError, OverflowError):
            return None

    s = str(ts).strip()
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y",
        "%B %d, %Y",
        "%b %d, %Y",
    ]
    # Handle timezone offsets like +07:00
    m = _TZ_OFFSETS.search(s)
    if m:
        hours, mins = int(m.group(1)), int(m.group(2))
        offset_secs = (hours * 60 + (mins if hours >= 0 else -mins)) * 60
        s_clean = s[:m.start()].strip()
        for fmt in formats:
            try:
                dt = datetime.strptime(s_clean, fmt)
                dt_utc = dt.replace(tzinfo=timezone.utc) - __import__("datetime").timedelta(seconds=offset_secs)
                return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                pass

    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pass
    return s  # Return as-is if we can't parse


# ── Language detection ─────────────────────────────────────────────────────────

def detect_language(text: str) -> str:
    """Detect language code (ISO 639-1). Falls back to 'und' (undefined)."""
    if not text or len(text.strip()) < 5:
        return "und"
    try:
        from langdetect import detect
        return detect(text)
    except Exception:
        pass
    # Heuristic fallback: common Indonesian/English markers
    id_markers = ["yang", "dan", "dengan", "untuk", "tidak", "adalah", "ini", "itu", "dari", "ke"]
    tokens = text.lower().split()
    id_count = sum(1 for t in tokens if t in id_markers)
    if id_count >= 2:
        return "id"
    return "en"


# ── Translation ────────────────────────────────────────────────────────────────

def translate_text(text: str, source_lang: str, target_lang: str = "en") -> Optional[str]:
    """Translate text. Tries DeepL → Google Translate API → googletrans (free)."""
    if not text or source_lang == target_lang or source_lang == "und":
        return None
    if len(text.strip()) < 3:
        return None

    # DeepL
    deepl_key = get_api_key("deepl")
    if deepl_key:
        try:
            import requests as _req
            r = _req.post(
                "https://api-free.deepl.com/v2/translate",
                data={"auth_key": deepl_key, "text": text[:5000], "target_lang": target_lang.upper()},
                timeout=10,
            )
            if r.status_code == 200:
                return r.json()["translations"][0]["text"]
        except Exception:
            pass

    # Google Translate API
    google_key = get_api_key("google")
    if google_key:
        try:
            import requests as _req
            r = _req.post(
                f"https://translation.googleapis.com/language/translate/v2?key={google_key}",
                json={"q": text[:5000], "source": source_lang, "target": target_lang, "format": "text"},
                timeout=10,
            )
            if r.status_code == 200:
                return r.json()["data"]["translations"][0]["translatedText"]
        except Exception:
            pass

    # googletrans (free, unofficial)
    try:
        from googletrans import Translator
        t = Translator()
        result = t.translate(text[:5000], src=source_lang, dest=target_lang)
        return result.text
    except Exception:
        pass

    return None


# ── Spam detection ────────────────────────────────────────────────────────────

_SPAM_PATTERNS = [
    # Generic filler comments
    r"^(nice\s*post|great\s*post|love\s*this|awesome|amazing|beautiful|wonderful|perfect|fantastic)[!.]*$",
    r"^(follow\s*me|follow\s*back|f4f|l4l|like4like|follow4follow)",
    r"^(check\s*(out\s*)?my|visit\s*my|see\s*my)",
    r"(buy\s*(now|cheap)|click\s*here|free\s*(money|gift|iphone)|earn\s*\$)",
    r"^(.)\1{4,}$",  # AAAAA, !!!!!
    r"^[^\w\s]{3,}$",  # Pure symbols/emoji
    r"(\b(?:http|www)\S+){3,}",  # Spam with 3+ URLs
    r"(DM\s*me|inbox\s*me).{0,30}(price|offer|deal)",
]
_SPAM_RE = re.compile("|".join(_SPAM_PATTERNS), re.IGNORECASE)

_BOT_NAME_PATTERNS = re.compile(
    r"(bot|crawler|spider|scraper|auto|robot|official_\d|promo_\d)", re.IGNORECASE
)

def is_spam(content: str, user: str = "") -> bool:
    """Heuristic spam classifier. Returns True if likely spam/bot."""
    if not content:
        return True
    c = content.strip()
    if len(c) < 2:
        return True
    if _SPAM_RE.search(c):
        return True
    # Very short with only emoji
    if len(re.sub(r"[^\w\s]", "", c)) < 3:
        return True
    return False


def classify_user(user: str, content: str) -> str:
    """Classify user as 'human' or 'bot' based on username + content signals."""
    if not user:
        return "unknown"
    if _BOT_NAME_PATTERNS.search(user):
        return "bot"
    # Generic account names
    if re.match(r"^user\d{5,}$", user, re.IGNORECASE):
        return "bot"
    return "human"


# ── NLP spam (optional HuggingFace) ───────────────────────────────────────────

_spam_classifier = None

def _get_spam_classifier():
    global _spam_classifier
    if _spam_classifier is None:
        try:
            from transformers import pipeline as hf_pipeline
            _spam_classifier = hf_pipeline(
                "text-classification",
                model="mrm8488/bert-tiny-finetuned-sms-spam-detection",
                truncation=True,
            )
        except Exception:
            _spam_classifier = False
    return _spam_classifier if _spam_classifier is not False else None


def is_spam_ml(content: str) -> Optional[bool]:
    """ML-based spam detection using HuggingFace (optional)."""
    clf = _get_spam_classifier()
    if not clf or not content:
        return None
    try:
        result = clf(content[:512])
        label = result[0]["label"].upper()
        return label == "SPAM" or label == "LABEL_1"
    except Exception:
        return None


# ── Content cleaner ────────────────────────────────────────────────────────────

def clean_content(text: str) -> str:
    """Remove HTML entities, excess whitespace. Preserve emojis."""
    if not text:
        return ""
    # Decode HTML entities
    try:
        from html import unescape
        text = unescape(text)
    except Exception:
        pass
    # Remove zero-width / invisible chars
    text = re.sub(r"[​‌‍﻿­]", "", text)
    # Collapse whitespace (but keep newlines for multi-paragraph)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Deduplication ──────────────────────────────────────────────────────────────

def content_hash(item: dict) -> str:
    """SHA-256 of platform + content for deduplication."""
    key = f"{item.get('platform', '')}::{item.get('content', '')}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


# ── Item cleaner ───────────────────────────────────────────────────────────────

def clean_item(item: dict, translate: bool = True, target_lang: str = "en") -> dict | None:
    """
    Clean and normalize a single raw item.
    Returns None if item should be discarded (spam/empty).
    """
    content = clean_content(item.get("content", ""))
    meta = dict(item.get("metadata", {}))

    # Normalize numbers
    for field in ("like", "view", "share", "comment", "retweet", "reply", "num_comments"):
        if field in meta:
            meta[field] = normalize_number(meta.get(field))

    # Normalize timestamp
    if "timestamp" in meta:
        meta["timestamp"] = normalize_timestamp(meta["timestamp"]) or meta["timestamp"]

    # User type classification
    user = meta.get("user", "")
    meta["user_type"] = classify_user(user, content)

    # Spam detection
    spam_heuristic = is_spam(content, user)
    spam_ml = is_spam_ml(content) if not spam_heuristic else None
    is_item_spam = spam_heuristic or (spam_ml is True)

    if is_item_spam and not item.get("type") in ("post", "video", "stream"):
        return None  # Drop spam comments/replies silently

    # Language detection
    lang = detect_language(content) if content else "und"

    # Translation
    content_translated = None
    if translate and lang not in ("en", "und", target_lang) and len(content) > 5:
        content_translated = translate_text(content, lang, target_lang)

    cleaned = {
        "platform":           item.get("platform", ""),
        "type":               item.get("type", ""),
        "id":                 item.get("id", ""),
        "content":            content,
        "language":           lang,
        "is_spam":            is_item_spam,
        "media":              item.get("media", []),
        "metadata":           meta,
        "cleaned_at":         datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if content_translated:
        cleaned["content_translated"] = content_translated

    return cleaned


# ── CleanerAgent class ────────────────────────────────────────────────────────

class CleanerAgent:
    """
    Reads all raw JSON files from data/raw/{platform}/,
    cleans + normalizes each item, deduplicates, and
    saves to data/cleaned/{platform}/.
    """

    def run(
        self,
        platforms: list[str] | None = None,
        translate: bool = True,
        target_lang: str = "en",
    ) -> dict:
        platform_dirs = (
            [RAW_DIR / p for p in platforms]
            if platforms
            else [d for d in RAW_DIR.iterdir() if d.is_dir() and d.name != "scout"]
        )

        stats = {}
        for platform_dir in platform_dirs:
            platform = platform_dir.name
            logger.info(f"Cleaning {platform}...")
            platform_stats = self._clean_platform(platform_dir, translate, target_lang)
            stats[platform] = platform_stats
            activity.log("clean", platform, "ok", platform_stats)

        total_clean = sum(s.get("clean", 0) for s in stats.values())
        total_raw   = sum(s.get("raw", 0) for s in stats.values())
        total_spam  = sum(s.get("spam_removed", 0) for s in stats.values())
        total_dups  = sum(s.get("duplicates_removed", 0) for s in stats.values())
        logger.info(
            f"Cleaner complete — {total_clean}/{total_raw} items kept | "
            f"{total_spam} spam removed | {total_dups} duplicates removed"
        )
        return stats

    def _clean_platform(
        self, platform_dir: Path, translate: bool, target_lang: str
    ) -> dict:
        platform = platform_dir.name
        raw_files = list(platform_dir.glob("*.json")) + list(platform_dir.glob("*.csv"))
        if not raw_files:
            return {"raw": 0, "clean": 0, "spam_removed": 0, "duplicates_removed": 0}

        raw_count = 0
        clean_items = []
        seen_hashes: set[str] = set()
        spam_count = 0
        dup_count = 0

        for raw_file in sorted(raw_files):
            try:
                items = self._load_raw(raw_file)
            except Exception as e:
                activity.log("load_error", platform, "error", {"file": raw_file.name, "error": str(e)})
                continue

            raw_count += len(items)
            for item in items:
                if not isinstance(item, dict):
                    continue

                cleaned = clean_item(item, translate=translate, target_lang=target_lang)
                if cleaned is None:
                    spam_count += 1
                    continue

                h = content_hash(cleaned)
                if h in seen_hashes:
                    dup_count += 1
                    continue
                seen_hashes.add(h)
                cleaned["_hash"] = h
                clean_items.append(cleaned)

        # Save
        if clean_items:
            self._save(platform, clean_items)

        return {
            "raw": raw_count,
            "clean": len(clean_items),
            "spam_removed": spam_count,
            "duplicates_removed": dup_count,
            "files_processed": len(raw_files),
        }

    def _load_raw(self, file: Path) -> list[dict]:
        if file.suffix == ".csv":
            import csv
            with open(file, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                return [dict(row) for row in reader]
        with open(file, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else [data]

    def _save(self, platform: str, items: list[dict]) -> None:
        out_dir = CLEAN_DIR / platform
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        # JSON
        json_file = out_dir / f"{platform}_cleaned_{ts}.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)

        # CSV
        csv_file = out_dir / f"{platform}_cleaned_{ts}.csv"
        try:
            import csv
            if items:
                # Flatten metadata for CSV
                flat_items = []
                for item in items:
                    flat = {k: v for k, v in item.items() if k not in ("metadata", "media")}
                    flat.update({f"meta_{k}": v for k, v in item.get("metadata", {}).items()})
                    flat["media"] = "|".join(item.get("media", []))
                    flat_items.append(flat)
                with open(csv_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=flat_items[0].keys(), extrasaction="ignore")
                    writer.writeheader()
                    writer.writerows(flat_items)
        except Exception as e:
            logger.warning(f"CSV save failed for {platform}: {e}")

        activity.log("save", platform, "ok", {"json": json_file.name, "items": len(items)})


if __name__ == "__main__":
    agent = CleanerAgent()
    agent.run()
