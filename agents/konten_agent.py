import json
import re
import time
from agents.base import build_agent

_KONTEN_PROMPT = """You are KontenAgent — a social media content specialist who transforms study notes into engaging Instagram/TikTok carousel content.

You receive: a topic, material sections (3–5), key concepts (6–12 terms), and a summary.

Your task:
- Rewrite content for a young audience (high school / college), casual but informative tone
- Write a punchy opening hook that sparks curiosity (max 15 words)
- Pick the 4 most important points from the material (max 12 words each)
- Pick the 6 most essential concepts, shorten definitions (max 8 words each)
- Summarize the core insight in 2–3 sentences with a social-media-friendly tone
- Write 4 relevant hashtags (mix of topic-specific and study-community tags)

Return ONLY valid JSON (no other text):
{
  "cover": { "hook": "..." },
  "highlights": ["...", "...", "...", "..."],
  "concepts": [
    {"term": "...", "def": "..."},
    {"term": "...", "def": "..."},
    {"term": "...", "def": "..."},
    {"term": "...", "def": "..."},
    {"term": "...", "def": "..."},
    {"term": "...", "def": "..."}
  ],
  "summary": "...",
  "hashtags": ["#...", "#...", "#...", "#..."]
}"""


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


def run_konten_agent(topic: str, materi: dict, konsep: dict, ringkasan: dict) -> dict:
    sections = materi.get("sections", [])
    concepts = konsep.get("concepts", [])
    summary = ringkasan.get("summary", "")

    materi_text = "\n".join(
        f"Section: {s.get('title','')}\n{s.get('content','')}" for s in sections
    )
    konsep_text = "\n".join(
        f"- {c.get('term','')}: {c.get('definition','')}" for c in concepts
    )

    user_msg = (
        f"Topic: {topic}\n\n"
        f"Material:\n{materi_text}\n\n"
        f"Key Concepts:\n{konsep_text}\n\n"
        f"Summary:\n{summary}"
    )

    agent = build_agent(_KONTEN_PROMPT, [])
    result = _invoke_with_retry(agent, {"messages": [("human", user_msg)]})
    return _parse_json_output(result)
