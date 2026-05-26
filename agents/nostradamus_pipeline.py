import json
import re
import time
from agents.base import build_agent


def _invoke_with_retry(agent, messages: dict, max_retries: int = 5) -> dict:
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


PREDICTORS = [
    {
        "id": "trend",
        "name": "Trend Analyst",
        "prompt": """Kamu adalah Analis Tren — pakar yang membaca momentum dan arah pergerakan dari pola data terkini.
Berdasarkan berita yang diberikan, prediksi ke mana peristiwa ini akan berkembang berdasarkan tren saat ini.

Kembalikan HANYA JSON (tanpa teks lain):
{
  "agent_id": "trend",
  "agent_name": "Trend Analyst",
  "prediction_title": "judul prediksi singkat (max 8 kata)",
  "prediction": "prediksi konkret 2-3 kalimat",
  "confidence": 72,
  "reasoning": "penjelasan singkat mengapa ini yang paling mungkin"
}""",
    },
    {
        "id": "risk",
        "name": "Risk Assessor",
        "prompt": """Kamu adalah Penilai Risiko — pessimist yang mengidentifikasi skenario terburuk dan risiko ekor (tail risks).
Berdasarkan berita yang diberikan, identifikasi apa yang bisa salah dan skenario paling berbahaya.

Kembalikan HANYA JSON (tanpa teks lain):
{
  "agent_id": "risk",
  "agent_name": "Risk Assessor",
  "prediction_title": "judul prediksi singkat (max 8 kata)",
  "prediction": "prediksi konkret 2-3 kalimat tentang risiko",
  "confidence": 60,
  "reasoning": "mengapa risiko ini nyata dan perlu diwaspadai"
}""",
    },
    {
        "id": "optimist",
        "name": "Optimist",
        "prompt": """Kamu adalah Optimis — analis yang mengidentifikasi katalis positif dan jendela peluang terbaik.
Berdasarkan berita yang diberikan, prediksi skenario terbaik yang realistis dan bisa terjadi.

Kembalikan HANYA JSON (tanpa teks lain):
{
  "agent_id": "optimist",
  "agent_name": "Optimist",
  "prediction_title": "judul prediksi singkat (max 8 kata)",
  "prediction": "prediksi konkret 2-3 kalimat tentang peluang terbaik",
  "confidence": 65,
  "reasoning": "katalis apa yang bisa mendorong skenario positif ini"
}""",
    },
    {
        "id": "history",
        "name": "Historical Analogist",
        "prompt": """Kamu adalah Analis Sejarah — pakar yang menemukan analog historis dan pola siklus berulang.
Berdasarkan berita yang diberikan, temukan peristiwa serupa dari sejarah dan prediksi berdasarkan preseden tersebut.

Kembalikan HANYA JSON (tanpa teks lain):
{
  "agent_id": "history",
  "agent_name": "Historical Analogist",
  "prediction_title": "judul prediksi singkat (max 8 kata)",
  "prediction": "prediksi konkret 2-3 kalimat, sebutkan preseden historis yang relevan",
  "confidence": 70,
  "reasoning": "analog historis mana yang paling relevan dan mengapa polanya berulang"
}""",
    },
    {
        "id": "systems",
        "name": "Systems Thinker",
        "prompt": """Kamu adalah Pemikir Sistem — analis yang memetakan efek lanjutan (second-order effects) dan konsekuensi berantai yang sering terlewat.
Berdasarkan berita yang diberikan, prediksi dampak tidak langsung yang akan terasa di luar bidang utama.

Kembalikan HANYA JSON (tanpa teks lain):
{
  "agent_id": "systems",
  "agent_name": "Systems Thinker",
  "prediction_title": "judul prediksi singkat (max 8 kata)",
  "prediction": "prediksi konkret 2-3 kalimat tentang efek lanjutan yang tidak terduga",
  "confidence": 68,
  "reasoning": "mekanisme sebab-akibat yang menghasilkan efek lanjutan ini"
}""",
    },
]

_GATHERER_PROMPT = """Kamu adalah NewsGatherer — analis berita yang mengumpulkan berita terkini dari berbagai sumber global.
Gunakan tool get_recent_news untuk mencari berita tentang topik yang diberikan.

Kembalikan HANYA JSON (tanpa teks lain):
{
  "news": [
    {
      "headline": "judul berita",
      "source": "nama media",
      "date": "tanggal/waktu",
      "summary": "ringkasan 1-2 kalimat"
    }
  ]
}

Kumpulkan 5-8 berita terbaru. Jika tool tidak menemukan hasil, kembalikan {"news": []}.
"""

_COUNCIL_PROMPT = """Kamu adalah Dewan Peramal — majelis hakim yang menimbang 5 prediksi dari perspektif berbeda dan menetapkan vonis akhir.
Gunakan tool save_prophecy untuk menyimpan vonis ke vault sebelum mengembalikan JSON.

Kembalikan HANYA JSON (tanpa teks lain):
{
  "verdict_title": "judul vonis singkat (max 8 kata)",
  "verdict_detail": "vonis konkret 3-4 kalimat — prediksi paling mungkin dan alasannya",
  "confidence": 75,
  "endorsed_agent": "nama agen yang prediksinya paling akurat",
  "dissenting_view": "1 kalimat sudut pandang berbeda yang patut dipertimbangkan"
}
"""


def run_news_gatherer(event: str) -> dict:
    from tools.news_tools import get_recent_news
    agent = build_agent(_GATHERER_PROMPT, [get_recent_news])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Cari berita terkini tentang: {event}"}]
    })
    parsed = _parse_json_output(result)
    if "news" not in parsed:
        return {"news": []}
    return parsed


def run_predictor(predictor: dict, event: str, news_summary: str) -> dict:
    agent = build_agent(predictor["prompt"], [])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Topik: {event}\n\nBerita terkini:\n{news_summary}\n\nBerikan prediksimu."}]
    })
    return _parse_json_output(result)


def run_council(event: str, predictions: list) -> dict:
    from tools.nostradamus_tools import save_prophecy
    agent = build_agent(_COUNCIL_PROMPT, [save_prophecy])
    preds_text = "\n\n".join(
        f"[{p.get('agent_name', '?')}]\n"
        f"Prediksi: {p.get('prediction_title', '')}\n"
        f"{p.get('prediction', '')}\n"
        f"Kepercayaan: {p.get('confidence', '?')}%"
        for p in predictions
    )
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Topik: {event}\n\n5 Prediksi:\n\n{preds_text}\n\nTetapkan vonis dan simpan ke vault."}]
    })
    return _parse_json_output(result)
