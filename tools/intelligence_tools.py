# tools/intelligence_tools.py
from pathlib import Path
import os, json, re
from datetime import datetime, timedelta

# Defined here (not imported from autoresearch_tools) so we can include orwell
# and avoid depending on a private variable in another module.
_AGENT_FOLDER_MAP = {
    "task":        "TaskCore Agent",
    "notes":       "Notes Agent",
    "news":        "Najwa Agent",
    "coding":      "Linus Agent",
    "schedule":    "CalCore Agent",
    "budget":      "Mansa Agent",
    "research":    "Ferry Agent",
    "fitness":     "Lavoiser Agent",
    "journal":     "Dostoyevsky Agent",
    "davinci":     "Da Vinci Agent",
    "orwell":      "Orwell Agent",
    "dataanalyst": "DataAnalyst Agent",
}

_CACHE_FILE = Path("data/intelligence_synthesis.json")
_CACHE_TTL_DAYS = 7


def _get_agent_dir(agent_key: str) -> Path:
    folder = _AGENT_FOLDER_MAP.get(agent_key, f"{agent_key.capitalize()} Agent")
    vault = os.getenv("OBSIDIAN_VAULT_PATH")
    return Path(vault) / folder if vault else Path("AI Data") / folder


def _parse_experiment_log(log_path: Path) -> dict:
    """Count KEEP/DISCARD/INCONCLUSIVE verdicts in experiment_log.md."""
    if not log_path.exists():
        return {"KEEP": 0, "DISCARD": 0, "INCONCLUSIVE": 0, "total": 0}
    text = log_path.read_text(encoding="utf-8")
    counts = {v: text.count(f"**Verdict:** {v}") for v in ["KEEP", "DISCARD", "INCONCLUSIVE"]}
    counts["total"] = sum(counts.values())
    return counts


def _parse_program_md(program_path: Path) -> dict:
    """Extract Current Hypothesis section and updated date from program.md."""
    if not program_path.exists():
        return {"hypothesis": None, "updated": None}
    text = program_path.read_text(encoding="utf-8")
    hypothesis = None
    if "## Current Hypothesis" in text:
        start = text.index("## Current Hypothesis") + len("## Current Hypothesis")
        rest = text[start:].strip()
        end = rest.find("\n##")
        hypothesis = (rest[:end] if end != -1 else rest).strip()
    updated = next(
        (line.split(":", 1)[1].strip() for line in text.split("\n")
         if line.strip().startswith("updated:")),
        None,
    )
    return {"hypothesis": hypothesis, "updated": updated}
