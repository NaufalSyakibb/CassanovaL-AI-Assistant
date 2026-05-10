"""
summarizer_agent.py — AI-powered social media content summarizer
=================================================================
Reads raw xcrawl JSON files, cleans the markdown noise (nav links,
sign-in buttons, UI chrome), and uses Mistral AI to generate a
structured per-platform summary in Indonesian.
"""
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))

from utils.logger import get_logger

logger = get_logger("summarizer")

# Auth/nav patterns to strip
_NAV_PATTERNS = re.compile(
    r"(sign in|log in|log out|sign up|daftar|masuk|register|forgot password|"
    r"skip navigation|back\s*$|create account|download app|get the app|"
    r"privacy policy|terms of service|cookie|copyright|all rights reserved)",
    re.IGNORECASE,
)
_PURE_LINK = re.compile(r"^\s*\[.*?\]\(.*?\)\s*$")
_AUTH_LINK  = re.compile(r"\((https?://)?(accounts\.|login|signup|register|auth|oauth)", re.IGNORECASE)


def _clean_markdown(text: str) -> str:
    """Strip navigation noise from raw xcrawl markdown."""
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()

        # Drop very short lines (UI labels, single emoji, etc.)
        if len(stripped) < 20:
            continue

        # Drop lines that are pure markdown links to auth/nav paths
        if _PURE_LINK.match(stripped) and _AUTH_LINK.search(stripped):
            continue

        # Drop lines matching common nav phrases
        if _NAV_PATTERNS.search(stripped):
            continue

        cleaned.append(stripped)

    # Collapse multiple blank lines
    result = re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned))
    return result.strip()


_SUMMARY_PROMPT = """\
Kamu adalah analis media sosial profesional. Berikut adalah konten yang berhasil di-scrape dari {platform}.

Analisis konten ini dan buat ringkasan terstruktur dalam Bahasa Indonesia. Fokus pada:
1. Topik apa yang sedang trending/populer
2. Jenis konten apa yang paling banyak muncul
3. Tema atau pola yang menonjol
4. Insight menarik yang bisa diambil

Format output HARUS menggunakan markdown dengan section berikut:

## Trending Topics
Daftar topik atau kata kunci yang paling sering muncul (bullet points)

## Konten Populer
Jenis konten apa yang dominan di platform ini (video, gambar, artikel, dll)

## Tema Utama
Tema besar yang mendominasi konten (teknologi, hiburan, berita, dll)

## Insight & Pola
Analisis singkat tentang tren dan pola yang terlihat

---
**Catatan:** Jika data terlalu sedikit atau kurang informatif, jelaskan limitasi tersebut dengan jujur.

Konten mentah ({chars} karakter setelah dibersihkan):

{content}
"""


class SummarizerAgent:
    """Summarizes raw xcrawl scraped content using Mistral AI."""

    def __init__(self, model: str = "mistral-large-latest"):
        self.model = model
        self._client = None

    def _get_llm(self):
        if self._client is None:
            # Add project root to path for dotenv
            project_root = Path(__file__).parent.parent.parent
            sys.path.insert(0, str(project_root))
            from dotenv import load_dotenv
            load_dotenv(project_root / ".env")
            api_key = os.getenv("MISTRAL_API_KEY")
            if not api_key:
                raise ValueError("MISTRAL_API_KEY not set in .env")
            from langchain_mistralai import ChatMistralAI
            self._client = ChatMistralAI(
                model=self.model,
                api_key=api_key,
                temperature=0.4,
                max_tokens=1200,
            )
        return self._client

    def _summarize_platform(self, platform: str, raw_path: Path) -> Optional[str]:
        """Load, clean, and summarize one platform's scraped data."""
        try:
            items = json.loads(raw_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Failed to read {raw_path}: {e}")
            return None

        # Concatenate all content fields
        raw_text = "\n\n---\n\n".join(
            item.get("content", "") for item in items if item.get("content")
        )
        if not raw_text.strip():
            logger.warning(f"{platform}: no content to summarize")
            return None

        cleaned = _clean_markdown(raw_text)

        # Budget: 6000 chars
        budget = 6000
        if len(cleaned) > budget:
            cleaned = cleaned[:budget] + "\n\n[... konten dipotong untuk efisiensi ...]"

        if len(cleaned) < 100:
            return (
                f"# Ringkasan {platform.capitalize()}\n\n"
                f"*Data yang di-scrape dari {platform} tidak mengandung cukup konten "
                f"teks untuk dianalisis. Kemungkinan halaman memerlukan autentikasi "
                f"atau konten di-render secara dinamis.*"
            )

        logger.info(f"[{platform}] Summarizing {len(cleaned)} chars with Mistral...")

        prompt = _SUMMARY_PROMPT.format(
            platform=platform.capitalize(),
            chars=len(cleaned),
            content=cleaned,
        )

        try:
            llm = self._get_llm()
            response = llm.invoke(prompt)
            summary = response.content.strip()
            logger.info(f"[{platform}] Summary generated ({len(summary)} chars)")
            return f"# Ringkasan {platform.capitalize()}\n\n{summary}"
        except Exception as e:
            logger.error(f"[{platform}] Mistral call failed: {e}")
            return (
                f"# Ringkasan {platform.capitalize()}\n\n"
                f"*Gagal generate summary: {type(e).__name__}: {e}*"
            )

    def run(self, raw_files: dict) -> dict[str, str]:
        """
        Generate AI summaries for all platforms.

        Args:
            raw_files: dict mapping platform_name -> Path to raw xcrawl JSON

        Returns:
            dict mapping platform_name -> markdown summary string
        """
        summaries = {}
        for platform, path in raw_files.items():
            summary = self._summarize_platform(platform, Path(path))
            if summary:
                summaries[platform] = summary
        return summaries
