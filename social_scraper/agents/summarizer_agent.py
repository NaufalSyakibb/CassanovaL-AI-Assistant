import json
import re
from pathlib import Path

_NAV_PHRASES = re.compile(
    r"^(sign in|log in|log out|sign up|register|create account|"
    r"skip navigation|skip to content|back|home|menu|close|open|"
    r"next|previous|load more|see more|show more|cookie|accept|"
    r"privacy|terms|settings|notifications|messages|search)$",
    re.IGNORECASE,
)
_AUTH_LINK = re.compile(r"\[.*?\]\(.*?/(login|signin|signup|register|auth).*?\)", re.IGNORECASE)

_SUMMARY_PROMPT = """Kamu adalah analis konten media sosial. Berdasarkan data tren yang dikumpulkan dari {platform}, buat ringkasan terstruktur dalam Bahasa Indonesia.

Data mentah:
{content}

Buat analisis dalam format berikut:

## Trending Topics
- Daftar topik/tagar/konten yang sedang tren

## Konten Populer
- Jenis konten yang banyak muncul

## Tema Utama
- Tema atau isu besar yang mendominasi

## Insight
- Analisis singkat: mengapa topik ini tren, siapa audiensnya, potensi viralnya

Tulis dalam Bahasa Indonesia yang informatif dan padat."""


def _clean_markdown(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if len(stripped) < 20:
            continue
        if _AUTH_LINK.match(stripped):
            continue
        if _NAV_PHRASES.match(stripped):
            continue
        lines.append(stripped)
    return "\n".join(lines)


class SummarizerAgent:
    def _get_llm(self):
        import os
        from langchain_mistralai import ChatMistralAI
        return ChatMistralAI(
            model="mistral-large-latest",
            api_key=os.getenv("MISTRAL_API_KEY", ""),
            temperature=0.4,
        )

    def _summarize_platform(self, platform: str, raw_path: Path) -> str:
        try:
            items = json.loads(raw_path.read_text(encoding="utf-8"))
        except Exception:
            return f"_Gagal membaca data untuk {platform}._"

        raw_text = "\n\n".join(
            item.get("content", item.get("topic", ""))
            for item in items
            if isinstance(item, dict)
        )

        cleaned = _clean_markdown(raw_text)
        if not cleaned.strip():
            return f"_Tidak ada konten yang bisa dianalisis untuk {platform}._"

        truncated = cleaned[:6000]

        prompt = _SUMMARY_PROMPT.format(platform=platform.upper(), content=truncated)
        try:
            llm = self._get_llm()
            response = llm.invoke(prompt)
            return response.content if hasattr(response, "content") else str(response)
        except Exception as exc:
            return f"_Gagal generate summary untuk {platform}: {exc}_"

    def run(self, raw_files: dict) -> dict:
        summaries = {}
        for platform, path in raw_files.items():
            summaries[platform] = self._summarize_platform(platform, Path(path))
        return summaries
