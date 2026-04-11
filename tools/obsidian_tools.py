"""
Obsidian vault integration tools.

Setup: Add OBSIDIAN_VAULT_PATH to your .env file:
    OBSIDIAN_VAULT_PATH=C:/Users/muham/OneDrive/Dokumen/Obsidian Vault

All tools read from (and write to) your vault as plain Markdown files.
"""
import os
import re
from pathlib import Path
from datetime import datetime
from langchain.tools import tool


def _vault() -> Path:
    """Return the configured Obsidian vault Path, raising clearly if missing."""
    path = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    if not path:
        raise EnvironmentError(
            "OBSIDIAN_VAULT_PATH tidak di-set di .env.\n"
            "Tambahkan: OBSIDIAN_VAULT_PATH=C:/Users/muham/OneDrive/Dokumen/Obsidian Vault"
        )
    vault = Path(path)
    if not vault.exists():
        raise FileNotFoundError(f"Vault tidak ditemukan di: {vault}")
    return vault


def _safe(name: str) -> str:
    """Sanitize a string for use as a filename."""
    return re.sub(r'[<>:"/\\|?*]', "-", name).strip()


# ── Internal utilities (called by other tools/router, NOT @tool) ──────────────

def mirror_to_obsidian(folder: str, filename: str, content: str) -> None:
    """
    Write/overwrite a markdown file in the vault. Silent no-op if vault not configured.
    Used by task_tools, budget_tools, food_tools to keep Obsidian in sync.
    """
    vault_path = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    if not vault_path:
        return
    try:
        target = Path(vault_path) / folder
        target.mkdir(parents=True, exist_ok=True)
        (target / filename).write_text(content, encoding="utf-8")
    except Exception:
        pass


def create_clipping(url: str, title: str, body: str, tags: list[str] | None = None) -> None:
    """
    Save a URL fetch as an Obsidian Clipping with YAML frontmatter.
    Saved to: <vault>/Clippings/YYYY-MM-DD <title>.md
    Silent no-op if vault not configured.
    """
    vault_path = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    if not vault_path:
        return
    try:
        vault = Path(vault_path)
        clip_dir = vault / "Clippings"
        clip_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        tag_list = ", ".join(f'"{t}"' for t in (tags or []))
        frontmatter = (
            f"---\n"
            f"title: \"{_safe(title)}\"\n"
            f"source: {url}\n"
            f"date: {today}\n"
            f"type: clipping\n"
            f"tags: [{tag_list}]\n"
            f"---\n\n"
        )
        safe_title = _safe(title)[:80]
        filename = f"{today} {safe_title}.md"
        (clip_dir / filename).write_text(frontmatter + f"# {title}\n\n{body}", encoding="utf-8")
    except Exception:
        pass


# Routing table: agent_name → (vault subfolder, filename prefix, display title)
_AGENT_HISTORY_CONFIG: dict[str, tuple[str, str, str]] = {
    "news":     ("AI Data/Najwa Agent",    "News",      "Najwa News Log"),
    "budget":   ("AI Data/Mansa Agent",    "Financial", "Mansa Financial Log"),
    "research": ("AI Data/Ferry Agent",    "Research",  "Ferry Research Log"),
    "fitness":  ("AI Data/Lavoiser Agent",    "Makanan",   "Lavoiser Food & Fitness Log"),
    "task":     ("AI Data/TaskCore Agent",   "Tasks",     "TaskCore Log"),
    "notes":    ("AI Data/Notes Agent",      "Notes",     "Notes Log"),
    "coding":   ("AI Data/Linus Agent",      "Code",      "Linus Code Log"),
    "schedule": ("AI Data/CalCore Agent",    "Schedule",  "CalCore Schedule Log"),
    "journal":  ("AI Data/Dostoyevsky Agent","Journal",   "Dostoyevsky Journal Log"),
}


def append_to_history(agent_name: str, user_msg: str, ai_response: str) -> None:
    """
    Append one conversation turn to the agent's daily file in Obsidian.

    Agent-specific routing:
      news     → AI Data/Najwa Agent/News_YYYY-MM-DD.md
      budget   → AI Data/Mansa Agent/Financial_YYYY-MM-DD.md
      research → AI Data/Ferry Agent/Research_YYYY-MM-DD.md
      fitness  → AI Data/Lavoiser Agent/Makanan_YYYY-MM-DD.md
      others   → AI Chat History/YYYY-MM-DD.md
    """
    vault_path = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    if not vault_path:
        return
    try:
        vault = Path(vault_path)
        today = datetime.now().strftime("%Y-%m-%d")
        ts = datetime.now().strftime("%H:%M")

        if agent_name in _AGENT_HISTORY_CONFIG:
            folder, prefix, display_title = _AGENT_HISTORY_CONFIG[agent_name]
            target_dir = vault / folder
            history_file = target_dir / f"{prefix}_{today}.md"
            header = f"# {display_title} — {today}\n\n---"
        else:
            target_dir = vault / "AI Chat History"
            history_file = target_dir / f"{today}.md"
            header = f"# AI Chat History — {today}\n\n---"

        target_dir.mkdir(parents=True, exist_ok=True)

        entry = (
            f"\n\n## {ts} · {agent_name.upper()}\n"
            f"**Kamu:** {user_msg}\n\n"
            f"**{agent_name.capitalize()}:** {ai_response}\n\n"
            f"---"
        )

        if not history_file.exists():
            history_file.write_text(header + entry, encoding="utf-8")
        else:
            with history_file.open("a", encoding="utf-8") as f:
                f.write(entry)
    except Exception:
        pass


# ── Public @tool functions (usable by agents) ─────────────────────────────────

@tool
def list_wiki_pages(folder: str = "") -> str:
    """
    List all Markdown pages in the Obsidian vault.
    Args:
        folder: Optional subfolder to filter (e.g. 'Fitness', 'wiki', 'Clippings').
                Leave empty to list all pages in the vault.
    """
    try:
        vault = _vault()
        base = (vault / folder) if folder else vault
        if not base.exists():
            return f"Folder '{folder}' tidak ditemukan di vault."
        pages = sorted(base.rglob("*.md"))
        if not pages:
            return "Tidak ada halaman Markdown ditemukan" + (f" di folder '{folder}'." if folder else ".")
        lines = [f"📄 {p.relative_to(vault)}" for p in pages]
        return f"Wiki — {len(pages)} halaman ditemukan:\n" + "\n".join(lines)
    except Exception as e:
        return f"[list_wiki_pages error] {e}"


@tool
def read_wiki_page(title: str) -> str:
    """
    Read the full content of an Obsidian page by its title or path.
    Args:
        title: Page title or relative path (with or without .md).
               Examples: 'Protein & Hypertrophy', 'wiki/index', 'Clippings/2026-04-09 Article'
    """
    try:
        vault = _vault()
        clean = title[:-3] if title.endswith(".md") else title

        candidates = list(vault.rglob(f"{clean}.md"))
        if not candidates:
            candidates = [
                p for p in vault.rglob("*.md")
                if p.stem.lower() == Path(clean).name.lower()
            ]

        if not candidates:
            return (
                f"Halaman '{title}' tidak ditemukan di vault.\n"
                f"Gunakan list_wiki_pages() untuk melihat halaman yang tersedia."
            )

        page = candidates[0]
        content = page.read_text(encoding="utf-8")
        rel = page.relative_to(vault)
        return f"[WIKI: {rel}]\n\n{content}"
    except Exception as e:
        return f"[read_wiki_page error] {e}"


@tool
def search_wiki(query: str) -> str:
    """
    Search all Obsidian pages for a keyword in title or content.
    Args:
        query: Keyword or phrase to search.
    """
    try:
        vault = _vault()
        query_lower = query.lower()
        results = []

        for page in sorted(vault.rglob("*.md")):
            try:
                content = page.read_text(encoding="utf-8")
                rel = str(page.relative_to(vault))
                in_title = query_lower in page.stem.lower()
                in_body = query_lower in content.lower()
                if in_title or in_body:
                    idx = content.lower().find(query_lower)
                    start = max(0, idx - 120) if idx >= 0 else 0
                    snippet = re.sub(r"\n+", " ", content[start: idx + 240].strip())
                    match_type = "📌 judul" if in_title else "📝 isi"
                    results.append(f"📄 {rel} [{match_type}]\n   ...{snippet}...")
            except Exception:
                continue

        if not results:
            return f"Tidak ada halaman yang mengandung '{query}'."
        return f"Ditemukan {len(results)} halaman untuk '{query}':\n\n" + "\n\n".join(results[:10])
    except Exception as e:
        return f"[search_wiki error] {e}"


@tool
def save_to_obsidian(title: str, content: str, folder: str = "AI Notes") -> str:
    """
    Save or overwrite a Markdown page in the Obsidian vault.
    Args:
        title: Page title (used as filename, without .md).
        content: Full Markdown content to write.
        folder: Target subfolder inside the vault (default: 'AI Notes').
    """
    try:
        vault = _vault()
        target_dir = vault / folder
        target_dir.mkdir(parents=True, exist_ok=True)

        safe_title = _safe(title)
        page_path = target_dir / f"{safe_title}.md"
        page_path.write_text(content, encoding="utf-8")
        return f"✓ Disimpan ke vault: {folder}/{safe_title}.md"
    except Exception as e:
        return f"[save_to_obsidian error] {e}"


OBSIDIAN_TOOLS = [list_wiki_pages, read_wiki_page, search_wiki, save_to_obsidian]
