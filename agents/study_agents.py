import json
import re
import time
from agents.base import build_agent


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


_MATERI_PROMPT = """Kamu adalah MateriAgent — ahli pendidikan yang membuat materi belajar komprehensif dan mendalam.
Kamu menerima topik pelajaran dari pengguna dan menghasilkan konten edukasi yang lengkap dalam Bahasa Indonesia.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "sections": [
    {
      "title": "judul bagian (mis. Pengertian Dasar / Proses / Contoh / Aplikasi)",
      "content": "penjelasan mendalam 100-200 kata, informatif dan terstruktur"
    }
  ]
}

Buat 3-5 section yang logis dan berurutan. Setiap section harus:
- Memiliki judul yang jelas dan deskriptif
- Berisi penjelasan mendalam dengan contoh konkret
- Menggunakan bahasa formal namun mudah dipahami mahasiswa
- Membangun pemahaman secara progresif dari konsep dasar ke lanjutan
"""

_KONSEP_PROMPT = """Kamu adalah KonsepAgent — analis konsep yang membaca materi pembelajaran dan mengekstrak poin-poin esensial.
Kamu menerima topik DAN teks materi lengkap yang sudah dibuat oleh MateriAgent.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "concepts": [
    {
      "term": "nama konsep atau istilah kunci",
      "definition": "penjelasan singkat 1-2 kalimat yang tepat dan informatif"
    }
  ]
}

Buat 6-12 konsep kunci yang berasal LANGSUNG dari materi yang diberikan. Jangan mengarang konsep yang tidak ada di materi.
Prioritaskan: definisi utama, rumus/formula, hubungan antar konsep, dan istilah teknis penting.
"""

_RINGKASAN_PROMPT = """Kamu adalah RingkasanAgent — editor akademik yang menulis ringkasan komprehensif dari materi pembelajaran.
Kamu menerima topik, materi lengkap dari MateriAgent, dan konsep kunci dari KonsepAgent.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "summary": "ringkasan 3-5 kalimat yang mencakup semua poin penting dari materi"
}

Ringkasan harus:
- Mencakup semua konsep kunci secara singkat
- Menggunakan bahasa formal dan akademis
- Mengalir sebagai paragraf yang kohesif, bukan daftar
- Panjang ideal: 80-120 kata
"""


def run_materi_agent(topic: str) -> dict:
    agent = build_agent(_MATERI_PROMPT, [])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Buat materi belajar lengkap tentang: {topic}"}]
    })
    return _parse_json_output(result)


def run_konsep_agent(topic: str, materi_text: str) -> dict:
    agent = build_agent(_KONSEP_PROMPT, [])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Topik: {topic}\n\nMateri:\n{materi_text}"}]
    })
    return _parse_json_output(result)


def run_ringkasan_agent(topic: str, materi_text: str, konsep_text: str) -> dict:
    agent = build_agent(_RINGKASAN_PROMPT, [])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Topik: {topic}\n\nMateri:\n{materi_text}\n\nKonsep Kunci:\n{konsep_text}"}]
    })
    return _parse_json_output(result)
