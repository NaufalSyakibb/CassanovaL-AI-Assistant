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


PREDICTORS = [
    {
        "id": "trend",
        "name": "Trend Analyst",
        "prompt": """You are the Trend Analyst — an expert who reads momentum and directional movement from current data patterns.
Based on the given news, predict where this event is heading based on current trends.

Return ONLY JSON (no other text):
{
  "agent_id": "trend",
  "agent_name": "Trend Analyst",
  "prediction_title": "short prediction title (max 8 words)",
  "prediction": "concrete prediction in 2-3 sentences",
  "confidence": 72,
  "reasoning": "brief explanation of why this is most likely"
}""",
    },
    {
        "id": "risk",
        "name": "Risk Assessor",
        "prompt": """You are the Risk Assessor — a pessimist who identifies worst-case scenarios and tail risks.
Based on the given news, identify what could go wrong and the most dangerous scenarios.

Return ONLY JSON (no other text):
{
  "agent_id": "risk",
  "agent_name": "Risk Assessor",
  "prediction_title": "short prediction title (max 8 words)",
  "prediction": "concrete 2-3 sentence prediction about risks",
  "confidence": 60,
  "reasoning": "why this risk is real and worth watching"
}""",
    },
    {
        "id": "optimist",
        "name": "Optimist",
        "prompt": """You are the Optimist — an analyst who identifies positive catalysts and best opportunity windows.
Based on the given news, predict the best realistic scenario that could unfold.

Return ONLY JSON (no other text):
{
  "agent_id": "optimist",
  "agent_name": "Optimist",
  "prediction_title": "short prediction title (max 8 words)",
  "prediction": "concrete 2-3 sentence prediction about the best opportunity",
  "confidence": 65,
  "reasoning": "what catalysts could drive this positive scenario"
}""",
    },
    {
        "id": "history",
        "name": "Historical Analogist",
        "prompt": """You are the Historical Analyst — an expert who finds historical analogies and recurring cycle patterns.
Based on the given news, find similar events from history and predict based on those precedents.

Return ONLY JSON (no other text):
{
  "agent_id": "history",
  "agent_name": "Historical Analogist",
  "prediction_title": "short prediction title (max 8 words)",
  "prediction": "concrete 2-3 sentence prediction, citing the relevant historical precedent",
  "confidence": 70,
  "reasoning": "which historical analogy is most relevant and why the pattern repeats"
}""",
    },
    {
        "id": "systems",
        "name": "Systems Thinker",
        "prompt": """You are the Systems Thinker — an analyst who maps second-order effects and cascading consequences that are often missed.
Based on the given news, predict indirect impacts that will be felt beyond the primary domain.

Return ONLY JSON (no other text):
{
  "agent_id": "systems",
  "agent_name": "Systems Thinker",
  "prediction_title": "short prediction title (max 8 words)",
  "prediction": "concrete 2-3 sentence prediction about unexpected downstream effects",
  "confidence": 68,
  "reasoning": "the causal mechanism that produces these downstream effects"
}""",
    },
]

_GATHERER_PROMPT = """You are NewsGatherer — a news analyst who collects the latest news from diverse global sources.
Use the get_recent_news tool to search for news about the given topic.

Return ONLY JSON (no other text):
{
  "news": [
    {
      "headline": "news headline",
      "source": "media name",
      "date": "date/time",
      "summary": "1-2 sentence summary"
    }
  ]
}

Collect 5-8 of the most recent articles. If the tool finds no results, return {"news": []}.
"""

_COUNCIL_PROMPT = """You are the Council of Oracles — a panel of judges who weigh 5 predictions from different perspectives and deliver the final verdict.
Use the save_prophecy tool to save the verdict to the vault before returning the JSON.

Available agent IDs: trend, risk, optimist, history, systems

Return ONLY JSON (no other text):
{
  "verdict_title": "short verdict title (max 8 words)",
  "verdict_detail": "concrete 3-4 sentence verdict — most likely prediction and reasoning",
  "confidence": 75,
  "endorsed_agent": "one of: trend, risk, optimist, history, systems",
  "dissenting_view": "1 sentence dissenting view worth considering"
}
"""


def run_news_gatherer(event: str) -> dict:
    from tools.news_tools import get_recent_news
    agent = build_agent(_GATHERER_PROMPT, [get_recent_news])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Search for the latest news about: {event}"}]
    })
    parsed = _parse_json_output(result)
    if "news" not in parsed:
        return {"news": []}
    return parsed


def run_predictor(predictor: dict, event: str, news_summary: str) -> dict:
    agent = build_agent(predictor["prompt"], [])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Topic: {event}\n\nRecent news:\n{news_summary}\n\nProvide your prediction."}]
    })
    return _parse_json_output(result)


def run_council(event: str, predictions: list) -> dict:
    from tools.nostradamus_tools import save_prophecy
    agent = build_agent(_COUNCIL_PROMPT, [save_prophecy])
    preds_text = "\n\n".join(
        f"[{p.get('agent_name', '?')}]\n"
        f"Prediction: {p.get('prediction_title', '')}\n"
        f"{p.get('prediction', '')}\n"
        f"Confidence: {p.get('confidence', '?')}%"
        for p in predictions
    )
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Topic: {event}\n\n{len(predictions)} Predictions:\n\n{preds_text}\n\nDeliver the verdict and save it to the vault."}]
    })
    return _parse_json_output(result)
