import json
import re
import time
from agents.base import build_agent

_EMOTION_PROMPT = """You are EmotionAgent — a precise emotional analyst. You receive the full text of a personal journal entry and return a structured JSON analysis of the emotional content.

Analyze the journal and identify:
1. The dominant mood (single lowercase word: e.g. "anxious", "grateful", "content", "sad")
2. mood_cat: "positive" | "negative" | "neutral"
3. Up to 5 specific emotions present, each with an intensity score 0–100
4. what_happened: 1–2 sentences describing the factual events of the day (objective, no interpretation)
5. summary: 2 sentences describing the overall emotional arc of the day (interpretive)

Return ONLY valid JSON — no other text:
{
  "dominant_mood": "...",
  "mood_cat": "positive|negative|neutral",
  "emotions": [
    {"name": "...", "intensity": 0},
    {"name": "...", "intensity": 0}
  ],
  "what_happened": "...",
  "summary": "..."
}

Rules:
- dominant_mood and all emotion names must be lowercase single words
- Limit to the 5 most prominent emotions
- what_happened is factual only — no emotional interpretation
- summary describes the emotional journey
- Return ONLY the JSON object, nothing else"""


def _invoke_with_retry(agent, messages: dict, max_retries: int = 5) -> dict:
    delay = 20
    last_exc: Exception = RuntimeError("no retry attempts made")
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


def run_emotion_agent(date: str, journal_content: str) -> dict:
    agent = build_agent(_EMOTION_PROMPT, [])
    user_msg = f"Date: {date}\n\nJournal:\n{journal_content}"
    result = _invoke_with_retry(agent, {"messages": [("human", user_msg)]})
    return _parse_json_output(result)
