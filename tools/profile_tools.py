"""
User Profile — persistent per-domain preferences for all agents.

Stored in data/user_profile.json. Injected silently by router.py into every
agent's context so agents know your goals/targets without you re-stating them.

Alfred @tools (read + write):
  get_user_profile(domain)              — read profile section(s)
  update_user_profile(domain, field, value) — update one field

Internal helpers (used by router.py):
  _load_profile()                       — returns full profile dict
  _format_profile_for_agent(agent, profile) — returns SystemMessage-ready string
"""

import json
from pathlib import Path
from langchain.tools import tool

_PROFILE_FILE = Path("data/user_profile.json")

_DEFAULTS: dict = {
    "personal": {
        "name": "User",
        "age": None,
        "gender": None,
        "timezone": "Asia/Jakarta",
        "language": "id",
    },
    "fitness": {
        "goal": None,
        "activity_level": None,
        "calorie_target": 2000,
        "protein_target_g": None,
        "allergies": [],
        "preferred_foods": [],
    },
    "budget": {
        "primary_currency": "IDR",
        "savings_rate_target_pct": None,
        "risk_tolerance": None,
        "monthly_income_estimate": 0,
    },
    "tasks": {
        "work_start_hour": 9,
        "work_end_hour": 18,
        "preferred_task_priority": "deadline",
    },
    "journal": {
        "reflection_frequency": "daily",
        "topics_of_interest": [],
    },
}

# Which profile domains are relevant per agent key
_AGENT_DOMAINS: dict[str, list[str]] = {
    "fitness":  ["personal", "fitness"],
    "budget":   ["personal", "budget"],
    "task":     ["personal", "tasks"],
    "journal":  ["personal", "journal"],
    "schedule": ["personal", "tasks"],
    "notes":    ["personal"],
    "coding":   ["personal"],
    "news":     ["personal"],
    "research": ["personal"],
    "davinci":  ["personal"],
    "euler":    ["personal"],
    "orwell":   ["personal"],
}


def _load_profile() -> dict:
    try:
        data = json.loads(_PROFILE_FILE.read_text(encoding="utf-8"))
        # Merge with defaults so missing keys always have a value
        merged = {}
        for domain, defaults in _DEFAULTS.items():
            merged[domain] = {**defaults, **data.get(domain, {})}
        return merged
    except Exception:
        return {k: dict(v) for k, v in _DEFAULTS.items()}


def _save_profile(data: dict) -> None:
    try:
        _PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _PROFILE_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def _format_section(domain: str, values: dict) -> str:
    lines = [f"[{domain.upper()} PROFILE]"]
    for k, v in values.items():
        if v is None or v == [] or v == 0:
            continue
        if isinstance(v, list):
            lines.append(f"  {k}: {', '.join(str(i) for i in v)}")
        else:
            lines.append(f"  {k}: {v}")
    return "\n".join(lines)


def _format_profile_for_agent(agent_name: str, profile: dict) -> str:
    """
    Returns a SystemMessage-ready string with only the profile sections
    relevant to the given agent. Returns '' if nothing meaningful to inject.
    """
    domains = _AGENT_DOMAINS.get(agent_name, ["personal"])
    sections = []
    for domain in domains:
        values = profile.get(domain, {})
        # Only include if the section has at least one non-empty value beyond defaults
        meaningful = {k: v for k, v in values.items() if v not in (None, [], 0, "")}
        if meaningful:
            sections.append(_format_section(domain, meaningful))

    if not sections:
        return ""

    return (
        "[USER PROFILE — injected automatically, not visible to user]\n"
        + "\n".join(sections)
        + "\nUse this to give personalized advice without asking the user to repeat their details."
    )


def _coerce(value: str):
    """Try to coerce a string value to int, float, or list where appropriate."""
    # List: "a, b, c"
    if "," in value:
        return [v.strip() for v in value.split(",") if v.strip()]
    # Int
    try:
        return int(value)
    except ValueError:
        pass
    # Float
    try:
        return float(value)
    except ValueError:
        pass
    # Null/clear
    if value.lower() in ("null", "none", "clear", ""):
        return None
    return value


@tool
def get_user_profile(domain: str = "") -> str:
    """
    Read the user's persistent profile. Pass a domain name to read just that
    section (fitness, budget, tasks, journal, personal), or leave empty for
    the full profile. Use this to check what the agent already knows about the
    user's goals and preferences.
    """
    profile = _load_profile()
    if domain.strip() and domain in profile:
        return _format_section(domain, profile[domain])
    # Return all sections with meaningful data
    parts = []
    for d, values in profile.items():
        parts.append(_format_section(d, values))
    return "\n\n".join(parts)


@tool
def update_user_profile(domain: str, field: str, value: str) -> str:
    """
    Update one field in the user's persistent profile.
    domain: fitness | budget | tasks | journal | personal
    field: the field name within that domain (e.g. protein_target_g, goal)
    value: the new value as a string (lists as comma-separated: "item1, item2")
    Example: update_user_profile("fitness", "protein_target_g", "160")
    """
    profile = _load_profile()
    if domain not in profile:
        return f"Unknown domain '{domain}'. Valid: {', '.join(profile.keys())}"

    coerced = _coerce(value)
    profile[domain][field] = coerced
    _save_profile(profile)
    return f"Profile updated: {domain}.{field} = {coerced!r}"


PROFILE_TOOLS = [get_user_profile, update_user_profile]
