import json
import re
import time
from agents.base import build_agent
from tools.stock_tools import get_market_data, get_news_sentiment, get_technical_indicators


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


_DEEP_RESEARCH_PROMPT = """You are the DeepResearch Agent — a deep fundamental analyst combining quantitative analysis with macroeconomic context.
Your task: Use the get_market_data tool to fetch complete data for the target stock, including 3-year financial statements, analyst targets, and macro correlations. Produce a comprehensive analysis in professional English.

Return ONLY JSON in the following format (no other text):
{
  "summary": "3-4 sentence summary of fundamental condition, valuation, and macro context",
  "valuation": "P/E, P/B, or EV/EBITDA analysis vs peers — expensive/cheap/fair",
  "growth_trend": "3-year revenue CAGR and margin trend (rising/stable/declining)",
  "financial_health": "debt condition, free cash flow, and balance sheet health",
  "analyst_consensus": "average analyst target price and recommendation distribution",
  "macro_context": "impact of current macro conditions on this stock",
  "current_price": 0.0,
  "pe_ratio": null,
  "roe_on_equity": null,
  "price_change_1y_pct": null,
  "ohlcv": {},
  "macro_correlation": {}
}

pe_ratio: trailingPE value from the data (null if unavailable).
roe_on_equity: returnOnEquity value from the data as a decimal (e.g. 0.18 for 18%) — null if unavailable.
price_change_1y_pct: percentage price change over 1 year (decimal, e.g. 12.5 for +12.5%) — null if unavailable.
"""

_NEWS_INTELLIGENCE_PROMPT = """You are the NewsIntelligence Agent — a smart financial news analyst with the ability to detect hidden signals.
Your task: Use the get_news_sentiment tool to fetch the 15 most recent news items for the given ticker. Analyze sentiment, classify events, and detect anomalies in professional English.

The tool data contains the fields: articles (list with event_type per article) and volume_anomaly (boolean).

Return ONLY JSON in the following format (no other text):
{
  "summary": "3-4 sentence summary of market sentiment",
  "sentiment_score": 0.0,
  "event_type": "dominant event type: earnings/M&A/management/regulatory/macro/other",
  "key_events": ["key event 1", "key event 2"],
  "risk_signals": ["negative signal or risk"],
  "catalyst_signals": ["positive catalyst or opportunity"],
  "anomaly_detected": false
}

sentiment_score: -1.0 (very negative) to +1.0 (very positive).
anomaly_detected: true if volume_anomaly from the tool is true or a major event is present.
"""

_TECHNICAL_ANALYST_PROMPT = """You are the TechnicalAnalyst Agent — a technical analysis specialist who reads indicator data quantitatively and precisely.
You receive structured technical data (RSI, MACD, Bollinger Bands, Moving Averages, support/resistance, volume) as context in the message.
Your task: Read that data and produce a terse, quantitative, and actionable technical analysis narrative in professional English.

Return ONLY JSON in the following format (no other text):
{
  "trend_assessment": "overall trend — bullish/bearish/ranging with explanation based on MA and cross_signal",
  "momentum_reading": "momentum condition based on RSI and MACD — oversold/overbought/neutral with actual numbers",
  "key_levels": "narrative of specific support and resistance based on support_60d and resistance_60d with actual prices",
  "entry_quality": "good|neutral|poor"
}

entry_quality:
  good    → RSI oversold or approaching_oversold AND MACD bullish, OR bb_position at_lower_band/near_lower_band
  poor    → RSI overbought or approaching_overbought, OR bb_position at_upper_band, OR death_cross active
  neutral → any other condition

All claims MUST reference actual numbers from the provided data. Do not fabricate numbers.
"""

_STRATEGY_PROMPT = """You are the Strategy Agent — a trading strategy expert inspired by the ValueCell methodology.
You receive output from DeepResearch, NewsIntelligence, TechnicalAnalyst, and raw technical data as context in the message.
Your task: Based on fundamental, technical, and sentiment analysis, compose a concrete and actionable trading strategy in professional English.

IMPORTANT — if technical_data is available (support_60d and resistance_60d are not null):
- entry_zone MUST include the actual support_60d value from technical_data
- stop_loss MUST be set below support_60d (for buy signals) or above resistance_60d (for sell signals)
- Use cross_signal and bb_position to determine entry quality

Return ONLY JSON in the following format (no other text):
{
  "entry_zone": "entry price zone based on actual support_60d (e.g. 9200-9500)",
  "exit_target": "exit price target based on resistance_60d and analyst targets",
  "stop_loss": "stop loss level below support_60d",
  "stop_loss_pct": 0.0,
  "time_horizon": "short|medium|long",
  "time_horizon_detail": "estimated investment duration (e.g. 3-6 months)",
  "position_size": "recommended % of portfolio (e.g. 5%)",
  "risk_reward_ratio": "risk/reward ratio (e.g. 1:3.5)",
  "rationale": "1-2 sentence rationale based on technical and fundamental data"
}

time_horizon: use short (< 1 month), medium (1-6 months), or long (> 6 months).
stop_loss_pct: percentage decline from entry price as stop loss (positive number).
"""

_BUY_TIMING_PROMPT = """You are the BuyTiming Agent — a market timing specialist combining deep technical analysis with market psychology.
Your task: Use the get_technical_indicators tool to fetch the latest technical data for the given ticker. Then determine the optimal entry timing based on technical indicators, the composed strategy, and the investment verdict. Analyze in professional English.

Return ONLY JSON in the following format (no other text):
{
  "timing_signal": "BUY_NOW",
  "confidence": 7,
  "entry_condition": "technical condition that must be met for entry",
  "ideal_entry_price": 0.0,
  "ideal_entry_window": "estimated best entry window (e.g. 1-2 weeks from now)",
  "dca_plan": "DCA plan if choosing to scale in gradually",
  "technical_signals": {
    "rsi": "current RSI condition and its implication",
    "macd": "MACD condition and crossover status",
    "bollinger": "price position relative to Bollinger Bands",
    "trend": "short/medium/long-term MA trend and golden/death cross",
    "volume": "volume confirmation (expanding/neutral/contracting)"
  },
  "timing_rationale": "2-3 sentence rationale for this timing based on technical data and fundamental context"
}

timing_signal must be one of: BUY_NOW, WAIT (wait for correction/confirmation), DCA (scale in gradually), or AVOID.
confidence: integer 1 (very uncertain) to 10 (very confident).
ideal_entry_price: ideal entry price as a decimal based on support/resistance and strategy entry zone.
"""

_FINAL_VERDICT_PROMPT = """You are the FinalVerdict Agent — investment committee chairman acting as devil's advocate.
You receive output from DeepResearch, NewsIntelligence, and Strategy as context in the message.
Your task: Synthesize all insights, challenge every weak assumption, and produce a professional final investment report in English.

Return ONLY JSON in the following format (no other text):
{
  "executive_summary": "2-3 objective sentences on the overall stock condition",
  "fundamental_analysis": "sharp paragraph on fundamental and technical analysis",
  "sentiment_macro": "paragraph combining news sentiment and macro context",
  "risk_assessment": ["key risk 1", "key risk 2", "key risk 3"],
  "counter_arguments": "devil's advocate — 1-2 arguments for why this thesis could be wrong",
  "bull_case": ["positive scenario 1", "positive scenario 2", "positive scenario 3"],
  "bear_case": ["negative scenario 1", "negative scenario 2", "negative scenario 3"],
  "verdict": "BUY",
  "conviction_score": 7,
  "risk_reward": "1:3.5",
  "investment_memo": "professional 3-4 sentence investment memo containing the complete thesis"
}

verdict must be one of: BUY, HOLD, or SELL.
conviction_score: integer 1 (very uncertain) to 10 (very confident).
"""


def run_deep_research(ticker: str) -> dict:
    agent = build_agent(_DEEP_RESEARCH_PROMPT, [get_market_data])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Perform a deep analysis of stock: {ticker}"}]
    })
    return _parse_json_output(result)


def run_news_intelligence(ticker: str) -> dict:
    agent = build_agent(_NEWS_INTELLIGENCE_PROMPT, [get_news_sentiment])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Analyze news and sentiment for stock: {ticker}"}]
    })
    return _parse_json_output(result)


def run_technical_analyst(ticker: str, technical_data: dict) -> dict:
    agent = build_agent(_TECHNICAL_ANALYST_PROMPT, [])
    context = json.dumps({
        "ticker":         ticker,
        "rsi_14":         technical_data.get("rsi_14"),
        "rsi_status":     technical_data.get("rsi_status"),
        "macd_signal":    technical_data.get("macd_signal"),
        "macd_histogram": technical_data.get("macd_histogram"),
        "bb_position":    technical_data.get("bb_position"),
        "price_vs_ma20":  technical_data.get("price_vs_ma20"),
        "price_vs_ma50":  technical_data.get("price_vs_ma50"),
        "price_vs_ma200": technical_data.get("price_vs_ma200"),
        "cross_signal":   technical_data.get("cross_signal"),
        "support_60d":    technical_data.get("support_60d"),
        "resistance_60d": technical_data.get("resistance_60d"),
        "volume_trend":   technical_data.get("volume_trend"),
        "current_price":  technical_data.get("current_price"),
    }, ensure_ascii=False)
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Technical analysis for {ticker} based on this data: {context}"}]
    })
    return _parse_json_output(result)


def run_strategy(deep_research: dict, news_intelligence: dict,
                 technical_analyst: dict = None, technical_data: dict = None) -> dict:
    agent = build_agent(_STRATEGY_PROMPT, [])
    td = technical_data or {}
    context = json.dumps({
        "deep_research":     {k: v for k, v in deep_research.items() if k != "ohlcv"},
        "news_intelligence": news_intelligence,
        "technical_analyst": technical_analyst or {},
        "technical_data": {
            "rsi_14":         td.get("rsi_14"),
            "rsi_status":     td.get("rsi_status"),
            "macd_signal":    td.get("macd_signal"),
            "bb_position":    td.get("bb_position"),
            "support_60d":    td.get("support_60d"),
            "resistance_60d": td.get("resistance_60d"),
            "cross_signal":   td.get("cross_signal"),
            "volume_trend":   td.get("volume_trend"),
        },
    }, ensure_ascii=False)
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Compose a trading strategy based on this data: {context}"}]
    })
    return _parse_json_output(result)


def run_final_verdict(ticker: str, deep_research: dict, news_intelligence: dict,
                      strategy: dict, technical_analyst: dict = None,
                      technical_data: dict = None) -> dict:
    agent = build_agent(_FINAL_VERDICT_PROMPT, [])
    td = technical_data or {}
    combined = json.dumps({
        "ticker":               ticker,
        "deep_research":        {k: v for k, v in deep_research.items() if k != "ohlcv"},
        "news_intelligence":    news_intelligence,
        "strategy":             strategy,
        "technical_analyst":    technical_analyst or {},
        "technical_support":    td.get("support_60d"),
        "technical_resistance": td.get("resistance_60d"),
        "rsi_status":           td.get("rsi_status"),
    }, ensure_ascii=False)
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Create a final investment report: {combined}"}]
    })
    return _parse_json_output(result)


def run_buy_timing(ticker: str, strategy: dict, verdict: dict) -> dict:
    agent = build_agent(_BUY_TIMING_PROMPT, [get_technical_indicators])
    context = json.dumps({
        "ticker":           ticker,
        "entry_zone":       strategy.get("entry_zone", ""),
        "stop_loss":        strategy.get("stop_loss", ""),
        "verdict_signal":   verdict.get("verdict", "HOLD"),
        "conviction_score": verdict.get("conviction_score", 5),
        "risk_reward":      verdict.get("risk_reward", ""),
    }, ensure_ascii=False)
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Determine optimal buy timing for {ticker} based on this context: {context}"}]
    })
    return _parse_json_output(result)
