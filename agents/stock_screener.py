import json
import re
import time
from agents.base import build_agent
from tools.stock_tools import get_market_data, get_technical_indicators


def _invoke_with_retry(agent, messages: dict, max_retries: int = 5) -> dict:
    """Invoke a LangGraph agent with exponential backoff on 429 / rate-limit errors."""
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
    """Extract the last AI message content and parse it as JSON. Returns error dict on failure."""
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


WATCHLISTS = {
    "us": [
        "NUE", "DVN", "JAZZ", "OXY", "SLB",
        "CROX", "MTB", "GXO", "URI", "FHN",
        "CELH", "EXAS", "PERI", "TRIP", "ADMA",
    ],
    "asia": [
        "6501.T", "000270.KS", "6902.T", "INFY", "HDB",
        "2303.TW", "005380.KS", "JD", "BIDU", "9984.T",
    ],
    "idx": [
        "ITMG.JK", "MDKA.JK", "SIDO.JK", "CPIN.JK", "MAPI.JK",
        "ACES.JK", "SMGR.JK", "KLBF.JK", "ICBP.JK", "BBNI.JK",
        "BMRI.JK", "PTBA.JK", "ERAA.JK", "INDF.JK", "EMTK.JK",
    ],
}

_SCREENER_PROMPT = """Kamu adalah StockScreener Agent — analis saham yang mencari saham underrated dan undervalued dengan fundamental kuat yang diabaikan pasar.

Gunakan tool get_market_data dan get_technical_indicators untuk mengambil data saham yang diberikan. Kemudian nilai apakah saham ini layak dibeli sebagai underrated pick.

Fokus pada:
- Valuasi rendah vs fundamental (P/E rendah, P/B rendah, FCF positif)
- Pertumbuhan pendapatan stabil tapi saham masih murah
- Momentum teknikal yang belum overbought (RSI < 65 ideal)
- Bukan mega-cap yang sudah dikenal semua orang

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "verdict": "BUY atau WATCH atau SKIP",
  "conviction_score": 7,
  "rationale": "1-2 kalimat mengapa saham ini underrated dan layak beli atau diperhatikan",
  "key_catalyst": "faktor utama yang bisa mendorong kenaikan harga",
  "risk_factor": "risiko utama yang perlu diperhatikan",
  "pe_ratio": 11.2,
  "rsi": 42.1
}

verdict: BUY = sangat layak beli sekarang, WATCH = menarik tapi tunggu entry lebih baik, SKIP = tidak menarik saat ini.
conviction_score: 1-10 (10 = paling yakin).
pe_ratio dan rsi: ambil langsung dari data tool. Jika tidak tersedia, gunakan 0.
"""


def run_pick_screener(ticker: str) -> dict:
    agent = build_agent(_SCREENER_PROMPT, [get_market_data, get_technical_indicators])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Analisis saham: {ticker}"}]
    })
    parsed = _parse_json_output(result)
    parsed["ticker"] = ticker
    return parsed
