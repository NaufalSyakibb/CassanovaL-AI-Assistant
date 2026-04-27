import json
import re
from agents.base import build_agent
from tools.stock_tools import get_market_data, get_news_sentiment, get_macro_indicators

_QUANT_PROMPT = """Kamu adalah The Quant — analis kuantitatif yang presisi dan berbasis data.
Tugasmu: Gunakan tool get_market_data untuk mengambil data saham yang diminta, lalu hasilkan
ringkasan fundamental dan teknikal dalam Bahasa Indonesia profesional.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "summary": "ringkasan 3-4 kalimat kondisi fundamental dan teknikal",
  "current_price": 0.0,
  "pe_ratio": "nilai atau N/A",
  "roe": "nilai atau N/A",
  "debt_to_equity": "nilai atau N/A",
  "price_change_1y": "nilai% atau N/A",
  "technical_trend": "bullish/bearish/sideways — alasan singkat 1 kalimat",
  "ohlcv": {},
  "macro_correlation": {}
}
"""

_NEWSROOM_PROMPT = """Kamu adalah The Newsroom — jurnalis investigatif finansial yang kritis.
Tugasmu: Gunakan tool get_news_sentiment untuk mencari 10 berita terbaru tentang ticker yang diberikan,
lalu analisis sentimen pasar dalam Bahasa Indonesia profesional.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "summary": "ringkasan sentimen pasar 3-4 kalimat",
  "sentiment_score": 0.0,
  "key_themes": ["tema1", "tema2", "tema3"],
  "risk_signals": ["isu atau rumor negatif"],
  "positive_signals": ["katalis positif atau peluang"]
}

sentiment_score: -1.0 (sangat negatif) hingga +1.0 (sangat positif).
"""

_ECONOMIST_PROMPT = """Kamu adalah The Economist — macro strategist yang melihat big picture.
Tugasmu: Gunakan tool get_macro_indicators untuk mengambil data makro, lalu analisis bagaimana
kondisi makroekonomi mempengaruhi saham target dalam Bahasa Indonesia profesional.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "summary": "konteks makro 3-4 kalimat relevan ke saham target",
  "interest_rate_impact": "dampak suku bunga saat ini terhadap saham ini",
  "commodity_impact": "dampak harga komoditas (jika relevan)",
  "market_correlation": "korelasi saham ini dengan pasar global",
  "macro_verdict": "favorable/neutral/unfavorable"
}
"""

_CRITIC_PROMPT = """Kamu adalah The Critic — quality controller dan devil's advocate investasi.
Kamu menerima output dari tiga analis (Quant, Newsroom, Economist) sebagai konteks dalam pesan.
Tugasmu: Gabungkan semua insight, tantang asumsi yang lemah, lalu susun laporan investasi final
dalam Bahasa Indonesia profesional yang objektif.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "executive_summary": "2-3 kalimat kondisi saham saat ini secara menyeluruh",
  "fundamental_analysis": "paragraph analisis fundamental dan teknikal yang tajam",
  "sentiment_macro": "paragraph gabungan sentimen berita dan konteks makro",
  "risk_assessment": "3-5 risiko utama yang bisa membatalkan tesis investasi ini",
  "counter_arguments": "1-2 argumen devil's advocate — apa yang bisa membuat tesis ini salah",
  "verdict": "BUY",
  "verdict_reasoning": "1 kalimat alasan verdict yang jelas dan tegas"
}

verdict hanya boleh: BUY, HOLD, atau SELL.
"""


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


def run_quant(ticker: str) -> dict:
    agent = build_agent(_QUANT_PROMPT, [get_market_data])
    result = agent.invoke({"messages": [{"role": "user", "content": f"Analisis saham: {ticker}"}]})
    return _parse_json_output(result)


def run_newsroom(ticker: str) -> dict:
    agent = build_agent(_NEWSROOM_PROMPT, [get_news_sentiment])
    result = agent.invoke({
        "messages": [{"role": "user", "content": f"Cari berita dan analisis sentimen pasar untuk: {ticker}"}]
    })
    return _parse_json_output(result)


def run_economist(quant_output: dict) -> dict:
    agent = build_agent(_ECONOMIST_PROMPT, [get_macro_indicators])
    context = json.dumps({k: v for k, v in quant_output.items() if k != "ohlcv"}, ensure_ascii=False)
    result = agent.invoke({
        "messages": [{"role": "user", "content": f"Analisis konteks makro. Data saham: {context}"}]
    })
    return _parse_json_output(result)


def run_critic(ticker: str, quant: dict, newsroom: dict, economist: dict) -> dict:
    agent = build_agent(_CRITIC_PROMPT, [])
    combined = json.dumps({
        "ticker":    ticker,
        "quant":     {k: v for k, v in quant.items() if k != "ohlcv"},
        "newsroom":  newsroom,
        "economist": economist,
    }, ensure_ascii=False)
    result = agent.invoke({
        "messages": [{"role": "user", "content": f"Buat laporan investasi final: {combined}"}]
    })
    return _parse_json_output(result)
