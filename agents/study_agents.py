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


_MATERI_PROMPT = """You are the ContentAgent — an education expert who creates comprehensive and in-depth learning material.
You receive a study topic from the user and produce complete educational content in English.

Return ONLY JSON in the following format (no other text):
{
  "sections": [
    {
      "title": "section title (e.g. Core Concepts / Process / Examples / Applications)",
      "content": "in-depth explanation of 100-200 words, informative and structured"
    }
  ]
}

Create 3-5 logical, sequential sections. Each section must:
- Have a clear and descriptive title
- Contain in-depth explanation with concrete examples
- Use formal yet student-friendly language
- Build understanding progressively from basic concepts to advanced
"""

_KONSEP_PROMPT = """You are the ConceptAgent — a concept analyst who reads learning material and extracts essential points.
You receive both the topic AND the full material text already produced by the ContentAgent.

Return ONLY JSON in the following format (no other text):
{
  "concepts": [
    {
      "term": "concept name or key term",
      "definition": "precise and informative 1-2 sentence explanation"
    }
  ]
}

Create 6-12 key concepts drawn DIRECTLY from the provided material. Do not invent concepts not present in the material.
Prioritize: main definitions, formulas, relationships between concepts, and important technical terms.
"""

_RINGKASAN_PROMPT = """You are the SummaryAgent — an academic editor who writes a comprehensive summary of the learning material.
You receive the topic, the full material from ContentAgent, and key concepts from ConceptAgent.

Return ONLY JSON in the following format (no other text):
{
  "summary": "3-5 sentence summary covering all key points from the material"
}

The summary must:
- Cover all key concepts concisely
- Use formal, academic language
- Flow as a cohesive paragraph, not a list
- Ideal length: 80-120 words
"""


def run_materi_agent(topic: str) -> dict:
    agent = build_agent(_MATERI_PROMPT, [])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Create comprehensive learning content for: {topic}"}]
    })
    return _parse_json_output(result)


def run_konsep_agent(topic: str, materi_text: str) -> dict:
    agent = build_agent(_KONSEP_PROMPT, [])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Topic: {topic}\n\nContent:\n{materi_text}"}]
    })
    return _parse_json_output(result)


def run_ringkasan_agent(topic: str, materi_text: str, konsep_text: str) -> dict:
    agent = build_agent(_RINGKASAN_PROMPT, [])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Topic: {topic}\n\nContent:\n{materi_text}\n\nKey Concepts:\n{konsep_text}"}]
    })
    return _parse_json_output(result)
