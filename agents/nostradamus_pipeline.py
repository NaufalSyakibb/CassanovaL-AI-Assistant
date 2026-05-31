import json
import re
import time
from agents.base import build_agent


def _invoke_with_retry(agent, messages: dict, max_retries: int = 5) -> dict:
    delay = 20
    last_exc = RuntimeError("max_retries must be > 0")
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


# 20 anonymous independent research analysts — no predefined role or perspective.
PREDICTORS = [{"id": f"analyst_{i+1:02d}", "name": f"Analyst {i+1}"} for i in range(20)]

_PREDICTOR_PROMPT = """You are an independent research analyst. Your job is to investigate the given topic using the search tool, gather your own data, and form your own original prediction — without any predefined angle or bias.

Use the get_recent_news tool to search for relevant information about the topic. Let what you find guide your conclusion organically.

Return ONLY valid JSON (no other text):
{
  "agent_id": "fill with your assigned agent ID",
  "agent_name": "fill with your assigned agent name",
  "prediction_title": "short prediction title (max 8 words)",
  "prediction": "concrete prediction in 2-3 sentences based entirely on your own research",
  "confidence": 70,
  "reasoning": "key findings from your research that support this prediction"
}

confidence: integer 1-100 reflecting the strength and quality of evidence you found."""

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

_COUNCIL_PROMPT = """Kamu adalah Dewan Peramal — majelis hakim yang menimbang 20 prediksi independen dan menetapkan vonis akhir.
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


def run_predictor(predictor: dict, event: str, news_summary: str = "") -> dict:
    from tools.news_tools import get_recent_news
    agent = build_agent(_PREDICTOR_PROMPT, [get_recent_news])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": (
            f"Your ID: {predictor['id']}\n"
            f"Your name: {predictor['name']}\n\n"
            f"Research topic: {event}\n\n"
            f"Use the search tool to independently research this topic and form your own prediction."
        )}]
    })
    parsed = _parse_json_output(result)
    # Guarantee correct agent identity in output regardless of LLM fill-in
    parsed["agent_id"] = predictor["id"]
    parsed["agent_name"] = predictor["name"]
    return parsed


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
        "messages": [{"role": "user", "content": f"Topik: {event}\n\n{len(predictions)} Prediksi:\n\n{preds_text}\n\nTetapkan vonis dan simpan ke vault."}]
    })
    return _parse_json_output(result)
