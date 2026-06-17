import json
import re
import time
from agents.base import build_agent


def _invoke_with_retry(agent, messages: dict, max_retries: int = 5) -> dict:
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


def _extract_json(agent_result: dict):
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
    return None


_ANALYST_PROMPT = """You are the WordAnalyst — a precise lexical editor trained in Orwell's six rules.
You receive a passage of prose and identify weak, vague, passive, or imprecise words and phrases that would benefit from sharper replacements.

Return ONLY valid JSON in this exact format:
{
  "words": [
    {
      "original": "the exact word or phrase to replace (as it appears in the text)",
      "suggestion": "the sharper replacement",
      "reason": "one concise sentence explaining why the replacement is stronger (max 15 words)"
    }
  ]
}

Rules:
- Find 3 to 10 replacements. Quality over quantity.
- Target: weak verbs (was walking → strode), vague nouns (thing → object), deadwood phrases (due to the fact that → because), passive voice, clichés, pretentious jargon, unnecessary adverbs.
- The "original" field must match the exact casing and spacing from the input text.
- Replacements must preserve the meaning and register of the passage.
- Do not suggest changes that needlessly alter the writer's voice.
- Return ONLY the JSON — no preamble, no explanation outside the JSON.
"""

_REWRITER_PROMPT = """You are the ParagraphRewriter — George Orwell's editorial hand.
You receive the original text and a list of accepted word substitutions.

Your job:
1. Apply every provided substitution to the text exactly.
2. Improve the overall paragraph beyond just word swaps: tighten structure, cut deadwood, convert unnecessary passive to active, sharpen the opening and closing sentence.
3. Preserve the writer's voice and intent — do not add ideas that were not there.

Return ONLY valid JSON in this exact format:
{
  "paragraph": "the complete rewritten paragraph as a single string",
  "summary": "2-3 sentences explaining the main structural changes made beyond the word swaps"
}

Return ONLY the JSON — no preamble, no extra commentary.
"""


def run_word_analyst(text: str) -> dict:
    agent = build_agent(_ANALYST_PROMPT, [], model="mistral-large-latest", temperature=0.2)
    result = _invoke_with_retry(agent, {"messages": [{"role": "human", "content": text}]})
    parsed = _extract_json(result)
    if parsed and "words" in parsed:
        return parsed
    return {"words": [], "error": "Could not parse analyst output"}


def run_paragraph_rewriter(text: str, substitutions: list) -> dict:
    if substitutions:
        subs_str = "\n".join(
            f'- Replace "{s["original"]}" with "{s["replacement"]}"'
            for s in substitutions
        )
    else:
        subs_str = "(none — improve the paragraph on its own merit)"
    prompt = f"Original text:\n{text}\n\nAccepted substitutions:\n{subs_str}"
    agent = build_agent(_REWRITER_PROMPT, [], model="mistral-large-latest", temperature=0.3)
    result = _invoke_with_retry(agent, {"messages": [{"role": "human", "content": prompt}]})
    parsed = _extract_json(result)
    if parsed and "paragraph" in parsed:
        return parsed
    return {"paragraph": "", "summary": "", "error": "Could not parse rewriter output"}
