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

_SCREENER_PROMPT = """You are the StockScreener Agent — a stock analyst who searches for underrated and undervalued stocks with strong fundamentals overlooked by the market.

Use the get_market_data and get_technical_indicators tools to fetch data for the given stock. Then evaluate whether this stock is worth buying as an underrated pick.

Focus on:
- Low valuation vs fundamentals (low P/E, low P/B, positive FCF)
- Stable revenue growth but the stock is still cheap
- Technical momentum not yet overbought (RSI < 65 ideal)
- Not a mega-cap that everyone already knows

Return ONLY JSON in the following format (no other text):
{
  "verdict": "BUY or WATCH or SKIP",
  "conviction_score": 7,
  "rationale": "1-2 sentences on why this stock is underrated and worth buying or watching",
  "key_catalyst": "primary factor that could drive price appreciation",
  "risk_factor": "main risk to watch out for",
  "pe_ratio": 11.2,
  "rsi": 42.1
}

verdict: BUY = highly worth buying now, WATCH = interesting but wait for a better entry, SKIP = not attractive at this time.
conviction_score: 1-10 (10 = most confident).
pe_ratio and rsi: take directly from the tool data. If unavailable, use 0.
"""


def run_pick_screener(ticker: str) -> dict:
    agent = build_agent(_SCREENER_PROMPT, [get_market_data, get_technical_indicators])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Analyze stock: {ticker}"}]
    })
    parsed = _parse_json_output(result)
    parsed["ticker"] = ticker
    return parsed
