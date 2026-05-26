from langchain.tools import tool
from pathlib import Path
from datetime import datetime


@tool
def save_prophecy(topic: str, verdict: str) -> str:
    """Save Nostradamus prophecy verdict to AI Data/Nostradamus Agent/ vault.
    Args:
        topic: The event or topic that was analyzed.
        verdict: The council verdict text to save.
    """
    vault = Path("AI Data/Nostradamus Agent")
    vault.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    fname = vault / f"prophecy_{ts}.md"
    fname.write_text(
        f"# Nostradamus Prophecy\n\n**Topik:** {topic}\n\n**Vonis:**\n{verdict}\n\n**Tanggal:** {ts}\n",
        encoding="utf-8"
    )
    return f"Saved to {fname}"
