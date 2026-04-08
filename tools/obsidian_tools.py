"""
Obsidian vault integration tools.

Setup: Add OBSIDIAN_VAULT_PATH to your .env file:
    OBSIDIAN_VAULT_PATH=C:/Users/kamu/Documents/ObsidianVault

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
            "Tambahkan baris ini ke file .env kamu:\n"
            "  OBSIDIAN_VAULT_PATH=C:/Users/kamu/Documents/NamaVault"
        )
    vault = Path(path)
    if not vault.exists():
        raise FileNotFoundError(
            f"Vault tidak ditemukan di: {vault}\n"
            "Pastikan path di OBSIDIAN_VAULT_PATH sudah benar."
        )
    return vault


# ── Public tools (usable by agents) ──────────────────────────────────────────

@tool
def list_wiki_pages(folder: str = "") -> str:
    """
    List all Markdown pages in the Obsidian vault.
    Args:
        folder: Optional subfolder to filter (e.g. 'Fitness', 'Research').
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
    Read the full content of an Obsidian page by its title or filename.
    Args:
        title: Page title or relative path (with or without .md).
               Examples: 'Protein & Hypertrophy', 'Fitness/Nutrition/Leucine'
    """
    try:
        vault = _vault()
        clean = title[:-3] if title.endswith(".md") else title

        # 1. Try exact relative path
        candidates = list(vault.rglob(f"{clean}.md"))

        # 2. Case-insensitive stem match
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
        query: Keyword or phrase to search (e.g. 'protein', 'lean bulk', 'leucine').
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
                    if idx >= 0:
                        start = max(0, idx - 120)
                        snippet = content[start : idx + 240].strip()
                        snippet = re.sub(r"\n+", " ", snippet)
                    else:
                        snippet = content[:200].strip()
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

        safe_title = re.sub(r'[<>:"/\\|?*]', "-", title)
        page_path = target_dir / f"{safe_title}.md"
        page_path.write_text(content, encoding="utf-8")

        return f"✓ Disimpan ke vault: {folder}/{safe_title}.md"
    except Exception as e:
        return f"[save_to_obsidian error] {e}"


OBSIDIAN_TOOLS = [list_wiki_pages, read_wiki_page, search_wiki, save_to_obsidian]


# ── Internal utility (called by router, NOT a @tool) ─────────────────────────

def append_to_history(agent_name: str, user_msg: str, ai_response: str) -> None:
    """
    Append one conversation turn to the daily history file in Obsidian.
    Saved to: <vault>/AI Chat History/YYYY-MM-DD.md

    Silently no-ops if OBSIDIAN_VAULT_PATH is not configured, so the app
    never crashes because of missing Obsidian setup.
    """
    vault_path = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    if not vault_path:
        return

    try:
        vault = Path(vault_path)
        history_dir = vault / "AI Chat History"
        history_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        ts = datetime.now().strftime("%H:%M")
        history_file = history_dir / f"{today}.md"

        entry = (
            f"\n\n## {ts} · {agent_name.upper()}\n"
            f"**Kamu:** {user_msg}\n\n"
            f"**{agent_name.capitalize()}:** {ai_response}\n\n"
            f"---"
        )

        if not history_file.exists():
            header = f"# AI Chat History — {today}\n\n---"
            history_file.write_text(header + entry, encoding="utf-8")
        else:
            with history_file.open("a", encoding="utf-8") as f:
                f.write(entry)
    except Exception:
        pass  # never let Obsidian errors crash the main app
