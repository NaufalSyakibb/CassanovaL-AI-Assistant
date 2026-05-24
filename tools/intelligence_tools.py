# tools/intelligence_tools.py
from pathlib import Path
import os, json  # json used by generate_intelligence_synthesis
from datetime import datetime, timedelta  # used by generate_intelligence_synthesis (Task 2)

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
    if updated is None:
        updated = next(
            (line.split(":", 1)[1].strip() for line in text.split("\n")
             if line.strip().startswith("created:")),
            None,
        )
    return {"hypothesis": hypothesis, "updated": updated}


def get_all_agent_stats() -> list[dict]:
    """Read program.md + experiment_log.md for every agent. Returns list of stat dicts."""
    result = []
    for agent_key, folder_name in _AGENT_FOLDER_MAP.items():
        d = _get_agent_dir(agent_key)
        program = _parse_program_md(d / "program.md")
        exps    = _parse_experiment_log(d / "experiment_log.md")
        result.append({
            "agent_key":   agent_key,
            "folder":      folder_name,
            "hypothesis":  program["hypothesis"],
            "updated":     program["updated"],
            "experiments": exps,
        })
    return result


def generate_intelligence_synthesis(force: bool = False) -> dict:
    """
    Synthesize a learning report via mistral-large-latest.
    Caches to data/intelligence_synthesis.json for 7 days.
    Returns {"synthesis": str, "generated_at": ISO str, "agents": list[dict]}.
    """
    agents = get_all_agent_stats()

    # Return cached version if still fresh
    if not force and _CACHE_FILE.exists():
        try:
            cached = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
            if datetime.fromisoformat(cached["generated_at"]) > datetime.now() - timedelta(days=_CACHE_TTL_DAYS):
                cached["agents"] = agents
                return cached
        except Exception:
            pass  # corrupt cache → regenerate

    # Build prompt
    lines = ["Kamu adalah analis sistem AI. Berikut adalah data eksperimen dari semua agent milik user:\n"]
    active_agents = [a for a in agents if a["experiments"]["total"] > 0]
    if not active_agents:
        # No data yet — return immediately without caching so fresh data will trigger synthesis later
        return {
            "synthesis":    "Belum ada data eksperimen yang cukup. Gunakan CassanovaL lebih sering agar sistem dapat mulai belajar tentang preferensimu.",
            "generated_at": None,
            "agents":       agents,
        }

    # Synthesize via LLM
    for a in active_agents:
        lines += [
            f"### {a['folder']} ({a['agent_key']})",
            f"Hipotesis saat ini: {a['hypothesis'] or '(belum ada)'}",
            f"Eksperimen: {a['experiments']['KEEP']} KEEP, {a['experiments']['DISCARD']} DISCARD, {a['experiments']['INCONCLUSIVE']} INCONCLUSIVE\n",
        ]
    lines += [
        "\nTulis laporan ringkas dalam Bahasa Indonesia (3–5 paragraf) yang menjawab:",
        "1. Apa yang sudah dipelajari sistem tentang preferensi dan kebiasaan user?",
        "2. Agent mana yang paling aktif belajar, dan mana yang paling sedikit datanya?",
        "3. Pola apa yang muncul lintas agent (misalnya: gaya komunikasi, format respons)?",
        "4. Area konkret mana yang butuh lebih banyak eksperimen agar sistem bisa berkembang?",
    ]
    from langchain_mistralai import ChatMistralAI
    from langchain_core.messages import HumanMessage
    llm = ChatMistralAI(model="mistral-large-latest", temperature=0.3)
    synthesis = llm.invoke([HumanMessage(content="\n".join(lines))]).content

    result_to_cache = {
        "synthesis":    synthesis,
        "generated_at": datetime.now().isoformat(),
    }
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_FILE.write_text(json.dumps(result_to_cache, ensure_ascii=False, indent=2), encoding="utf-8")

    return {**result_to_cache, "agents": agents}
