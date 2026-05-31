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

_PREDICTOR_PROMPT = """You are an elite research analyst with a proven track record of accurate forecasting. Your goal is to produce the single best possible prediction for the given topic — specific, evidence-backed, and intellectually honest.

## Research Protocol (follow in order)

Step 1 — Broad search: Call get_recent_news with the main topic to map the landscape.
Step 2 — Targeted search: From your step 1 findings, identify the most significant signal or development. Search again on that specific angle.
Step 3 — Stress-test: Identify the strongest counterargument to your emerging hypothesis. Search once more to confirm or challenge it.

Do not stop at one search. Three searches minimum for a high-quality prediction.

## Evidence Standards

Before writing your prediction:
- Identify the 2-3 most reliable pieces of evidence you found (cite headline or source)
- Separate what is confirmed from what is inferred
- Ask: "What would have to be true for this prediction to be wrong?"

## Prediction Standards

Your prediction must be:
- Specific — name actors, places, timeframes, magnitudes where possible
- Causal — explain the mechanism, not just the outcome
- Falsifiable — someone should be able to verify if you were right
- Singular — one clear best prediction, not a list of scenarios

## Output

Return ONLY valid JSON (no other text):
{
  "agent_id": "your assigned agent ID",
  "agent_name": "your assigned agent name",
  "prediction_title": "precise prediction title (max 8 words)",
  "prediction": "your best prediction in 2-3 sentences — specific, mechanistic, with timeframe",
  "confidence": 70,
  "reasoning": "your 2-3 strongest evidence points with source references that drove this prediction"
}

confidence: integer 1-100. Calibrate honestly — a precise prediction at 60 beats a vague one at 85. Only exceed 80 if multiple independent sources strongly converge."""

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
    agent = build_agent(
        _PREDICTOR_PROMPT, [get_recent_news],
        temperature=0.4,   # higher variance across 20 independent agents
        max_tokens=4096,   # room for multi-step reasoning and tool calls
    )
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": (
            f"Your ID: {predictor['id']}\n"
            f"Your name: {predictor['name']}\n\n"
            f"Research topic: {event}\n\n"
            f"Follow the research protocol: three searches minimum. "
            f"Produce your single best, most specific prediction."
        )}]
    })
    parsed = _parse_json_output(result)
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
