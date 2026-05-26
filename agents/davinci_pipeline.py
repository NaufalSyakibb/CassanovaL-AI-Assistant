import json
import re
import time
from agents.base import build_agent
from tools.davinci_tools import save_idea


def _invoke_with_retry(agent, messages: dict, max_retries: int = 5) -> dict:
    """Invoke a LangGraph agent with exponential backoff on 429 rate-limit errors."""
    delay = 20
    last_exc = None
    for attempt in range(max_retries):
        try:
            return agent.invoke(messages)
        except Exception as e:
            last_exc = e
            if "429" in str(e) or "rate" in str(e).lower():
                time.sleep(delay)
                delay = min(delay * 2, 120)
            else:
                raise
    raise last_exc


def _parse_json_output(agent_result: dict) -> dict:
    """Extract last AI message content and parse the first JSON object found."""
    messages = agent_result.get("messages", [])
    for msg in reversed(messages):
        content = getattr(msg, "content", "")
        if not content:
            continue
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue
    raw = str(messages[-1]) if messages else "no messages"
    return {"error": "Could not parse agent output", "raw": raw[:500]}


_GENERATOR_PROMPT = """Kamu adalah IdeaGenerator — seorang kreatif polymath seperti Leonardo da Vinci yang merentang dari yang konvensional hingga yang radikal.
Kamu menerima topik atau pertanyaan kreatif dari pengguna dan menghasilkan 6 ide yang beragam.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "ideas": [
    {
      "id": 1,
      "title": "judul singkat ide (max 5 kata)",
      "tagline": "deskripsi satu kalimat yang tajam dan menggugah",
      "spectrum": "Konvensional"
    }
  ]
}

Buat tepat 6 ide dengan distribusi spectrum:
- Ide 1-2: "Konvensional" — pendekatan yang terbukti, mudah diimplementasi
- Ide 3-4: "Inovatif" — pendekatan segar yang realistis namun belum umum
- Ide 5-6: "Liar" — pendekatan radikal, tidak biasa, bisa mengubah paradigma

Setiap ide harus:
- Memiliki judul yang singkat dan memukau (bukan generik)
- Tagline yang spesifik dan memancing rasa ingin tahu
- Berbeda satu sama lain — tidak ada tumpang tindih konsep
"""

_EXPANDER_PROMPT = """Kamu adalah IdeaExpander — ahli strategi kreatif yang mengembangkan ide menjadi rencana yang konkret dan actionable.
Kamu menerima judul dan tagline sebuah ide kreatif dan mengembangkannya secara mendalam.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "title": "judul ide (sama dengan input)",
  "use_cases": "3-4 kasus penggunaan spesifik, dipisahkan titik koma",
  "steps": "4-5 langkah implementasi konkret, dipisahkan titik koma",
  "example": "satu contoh nyata atau analogi yang memperjelas ide",
  "impact": "dampak potensial jika ide ini berhasil diimplementasi"
}

Semua konten dalam Bahasa Indonesia. Konkret, spesifik, actionable — bukan abstrak.
"""


def run_idea_generator(topic: str) -> dict:
    agent = build_agent(_GENERATOR_PROMPT, [])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Hasilkan 6 ide kreatif untuk topik: {topic}"}]
    })
    parsed = _parse_json_output(result)
    if "ideas" not in parsed:
        return {"ideas": []}
    return parsed


def run_idea_expander(idea_title: str, idea_tagline: str) -> dict:
    agent = build_agent(_EXPANDER_PROMPT, [save_idea])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Kembangkan ide ini:\nJudul: {idea_title}\nTagline: {idea_tagline}"}]
    })
    return _parse_json_output(result)
