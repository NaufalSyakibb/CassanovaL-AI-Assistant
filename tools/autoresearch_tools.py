"""
Autoresearch tools — autonomous self-improvement for CassanovaL agents.

Concept (from @karpathy's autoresearch):
  Each agent maintains a program.md (current strategy + hypotheses to test),
  runs behavioral experiments across sessions, logs results, and iterates.
  The "metric" is qualitative session quality, not val_bpb.

Operations:
  read_program(agent_name)      → read the agent's program.md
  log_experiment(...)           → append one experiment result to experiment_log.md
  update_program(...)           → overwrite a section in program.md

All files live in: {vault}/AI Data/{Agent Folder}/ (Obsidian vault)
                or: {project_root}/AI Data/{Agent Folder}/ (fallback)
"""
import os
import re
from pathlib import Path
from datetime import datetime
from langchain.tools import tool


# ── Folder map: agent key → folder name ──────────────────────────────────────
_AGENT_FOLDER_MAP: dict[str, str] = {
    "task":     "TaskCore Agent",
    "notes":    "Notes Agent",
    "news":     "Najwa Agent",
    "coding":   "Linus Agent",
    "schedule": "CalCore Agent",
    "budget":   "Mansa Agent",
    "research": "Ferry Agent",
    "fitness":  "Lavoiser Agent",
    "journal":  "Dostoyevsky Agent",
    "davinci":      "Da Vinci Agent",
    "dataanalyst":  "DataAnalyst Agent",
}

# ── Internal helper ───────────────────────────────────────────────────────────

def _agent_dir(agent_name: str) -> Path:
    """
    Resolve the autoresearch directory for the given agent.
    Priority: Obsidian vault → project-local AI Data/.
    Creates the directory if it doesn't exist.
    """
    folder = _AGENT_FOLDER_MAP.get(agent_name.lower(), f"{agent_name.capitalize()} Agent")

    vault_path = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    if vault_path:
        base = Path(vault_path) / "AI Data" / folder
    else:
        base = Path(__file__).parent.parent / "AI Data" / folder

    base.mkdir(parents=True, exist_ok=True)
    return base


def _default_program(agent_name: str) -> str:
    """Return a minimal default program.md for an agent that doesn't have one yet."""
    today = datetime.now().strftime("%Y-%m-%d")
    name = agent_name.capitalize()
    return (
        f"---\n"
        f"agent: {name}\n"
        f"created: {today}\n"
        f"metric: Session quality — user satisfaction and task effectiveness\n"
        f"---\n\n"
        f"# Autoresearch Program — {name}\n\n"
        f"## Current Hypothesis\n\n"
        f"**H-001** (Baseline): Default behavioral strategy — observe what works and iterate.\n\n"
        f"## Metric\n\n"
        f"Qualitative session quality: user engages meaningfully, tasks are completed, "
        f"and explicit positive feedback outweighs corrections.\n\n"
        f"## Baseline Approach\n\n"
        f"Follow the system prompt exactly. Note deviations that produce better outcomes.\n\n"
        f"## Next Experiments\n\n"
        f"- [ ] **E-001**: Identify the most common user request type and optimize the opening response for it.\n"
        f"- [ ] **E-002**: Track which tool calls are never used — consider whether they add noise.\n"
        f"- [ ] **E-003**: Test asking one clarifying question vs. attempting a direct answer on ambiguous inputs.\n\n"
        f"## Experiment Log\n\n"
        f"See: [[experiment_log]]\n"
    )


# ── Public @tool functions ────────────────────────────────────────────────────

@tool
def read_program(agent_name: str) -> str:
    """
    Read this agent's autoresearch program from program.md.
    Call this ONCE at the start of a complex or strategic session to recall
    the current hypothesis, baseline approach, and what experiments to observe.

    Args:
        agent_name: The agent's key, e.g. 'task', 'fitness', 'coding', 'budget'.
    """
    try:
        d = _agent_dir(agent_name)
        program_file = d / "program.md"

        if not program_file.exists():
            # Create default scaffold so subsequent calls work
            default = _default_program(agent_name)
            program_file.write_text(default, encoding="utf-8")
            return (
                f"[program.md not found — created default scaffold]\n\n{default}\n\n"
                f"💡 Edit this file at: {program_file}\n"
                f"   Update 'Current Hypothesis' and 'Next Experiments' to your actual strategy."
            )

        return program_file.read_text(encoding="utf-8")
    except Exception as e:
        return f"[read_program error] {e}"


@tool
def log_experiment(
    agent_name: str,
    hypothesis_id: str,
    what_happened: str,
    verdict: str,
    confidence: str,
) -> str:
    """
    Append one experiment result to experiment_log.md (append-only, never overwrites).
    Call this ONLY on meaningful feedback events:
      - User gives explicit positive or negative feedback
      - A recommendation or strategy clearly succeeded or failed
    Do NOT call this on routine turns.

    Args:
        agent_name:    The agent's key, e.g. 'task', 'fitness'.
        hypothesis_id: The hypothesis being tested, e.g. 'H-001', 'E-002'.
        what_happened: Brief description of what the user did/said that constitutes signal.
        verdict:       One of: 'KEEP', 'DISCARD', 'INCONCLUSIVE'.
        confidence:    One of: 'HIGH', 'MEDIUM', 'LOW'.
    """
    try:
        d = _agent_dir(agent_name)
        log_file = d / "experiment_log.md"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")

        if not log_file.exists():
            header = (
                f"---\nagent: {agent_name}\ntype: experiment-log\n---\n\n"
                f"# Experiment Log — {agent_name.capitalize()}\n\n"
                f"> Append-only. Each entry records one behavioral experiment result.\n"
                f"> Verdict: KEEP | DISCARD | INCONCLUSIVE  ·  Confidence: HIGH | MEDIUM | LOW\n\n"
                f"---\n"
            )
            log_file.write_text(header, encoding="utf-8")

        entry = (
            f"\n## [{ts}] {hypothesis_id}\n"
            f"**Verdict:** {verdict.upper()}\n"
            f"**Confidence:** {confidence.upper()}\n"
            f"**What happened:** {what_happened}\n\n"
            f"---"
        )

        with log_file.open("a", encoding="utf-8") as f:
            f.write(entry)

        return (
            f"✅ Experiment logged: {hypothesis_id} → {verdict.upper()} ({confidence.upper()} confidence)\n"
            f"   File: {log_file}"
        )
    except Exception as e:
        return f"[log_experiment error] {e}"


@tool
def update_program(
    agent_name: str,
    section: str,
    new_content: str,
) -> str:
    """
    Overwrite a named section in program.md with new content.
    Call this ONLY when a hypothesis is validated or invalidated with HIGH
    confidence across multiple interactions — not after a single session.

    Args:
        agent_name:  The agent's key, e.g. 'task', 'coding'.
        section:     Section to replace. One of:
                       'Current Hypothesis', 'Next Experiments', 'Baseline Approach'.
        new_content: The replacement content (markdown, no leading ##).
    """
    try:
        d = _agent_dir(agent_name)
        program_file = d / "program.md"

        if not program_file.exists():
            # Auto-create default first
            program_file.write_text(_default_program(agent_name), encoding="utf-8")

        content = program_file.read_text(encoding="utf-8")
        header = f"## {section}"

        if header not in content:
            return (
                f"[update_program] Section '## {section}' not found in program.md.\n"
                f"Valid sections: 'Current Hypothesis', 'Next Experiments', 'Baseline Approach'."
            )

        # Replace section content — handle both mid-file (next ## follows) and end-of-file
        pattern = rf"(## {re.escape(section)}\n)([\s\S]*?)(?=\n## |\Z)"

        def replacer(m: re.Match) -> str:
            return m.group(1) + "\n" + new_content.strip() + "\n"

        new_full = re.sub(pattern, replacer, content)

        # Update modified timestamp in frontmatter if present
        today = datetime.now().strftime("%Y-%m-%d")
        new_full = re.sub(r"updated: \d{4}-\d{2}-\d{2}", f"updated: {today}", new_full)

        program_file.write_text(new_full, encoding="utf-8")
        return f"✅ Section '{section}' updated in program.md for agent '{agent_name}'."
    except Exception as e:
        return f"[update_program error] {e}"


AUTORESEARCH_TOOLS = [read_program, log_experiment, update_program]
