import json
import re
import time
from agents.base import build_agent
from tools.davinci_tools import save_idea


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


_GENERATOR_PROMPT = """You are the IdeaGenerator — a creative polymath like Leonardo da Vinci, spanning the spectrum from conventional to radical.
You receive a topic or creative question from the user and generate 6 diverse ideas.

Return ONLY JSON in the following format (no other text):
{
  "ideas": [
    {
      "id": 1,
      "title": "short idea title (max 5 words)",
      "tagline": "one sharp, evocative sentence description",
      "spectrum": "Conventional"
    }
  ]
}

Create exactly 6 ideas with this spectrum distribution:
- Ideas 1-2: "Conventional" — proven approaches, easy to implement
- Ideas 3-4: "Innovative" — fresh yet realistic approaches not yet mainstream
- Ideas 5-6: "Wild" — radical, unconventional, potentially paradigm-shifting

Each idea must:
- Have a short, striking title (not generic)
- Have a specific tagline that sparks curiosity
- Be distinct from the others — no conceptual overlap
"""

_EXPANDER_PROMPT = """You are the IdeaExpander — a creative strategy expert who develops ideas into concrete, actionable plans.
You receive the title and tagline of a creative idea and expand it in depth.

Return ONLY JSON in the following format (no other text):
{
  "title": "idea title (same as input)",
  "use_cases": "3-4 specific use cases, separated by semicolons",
  "steps": "4-5 concrete implementation steps, separated by semicolons",
  "example": "one real example or analogy that clarifies the idea",
  "impact": "potential impact if this idea is successfully implemented"
}

All content in English. Concrete, specific, actionable — not abstract.
"""


def run_idea_generator(topic: str) -> dict:
    agent = build_agent(_GENERATOR_PROMPT, [])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Generate 6 creative ideas for the topic: {topic}"}]
    })
    parsed = _parse_json_output(result)
    if "ideas" not in parsed:
        return {"ideas": []}
    return parsed


def run_idea_expander(idea_title: str, idea_tagline: str) -> dict:
    agent = build_agent(_EXPANDER_PROMPT, [save_idea])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Expand this idea:\nTitle: {idea_title}\nTagline: {idea_tagline}"}]
    })
    return _parse_json_output(result)
