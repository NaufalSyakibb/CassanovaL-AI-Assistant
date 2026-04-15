"""
Idea management tools for Leonardo da Vinci agent.
Saves all ideas to: AI Data/Da Vinci Agent/
One file per idea: Idea_YYYYMMDD_HHMMSS_Title.md
"""
import re
from pathlib import Path
from datetime import datetime
from langchain.tools import tool

DAVINCI_FOLDER = Path(__file__).parent.parent / "AI Data" / "Da Vinci Agent"


def _ideas_dir() -> Path:
    DAVINCI_FOLDER.mkdir(parents=True, exist_ok=True)
    return DAVINCI_FOLDER


def _now() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _time_str() -> str:
    return datetime.now().strftime("%H:%M")


def _slugify(text: str) -> str:
    """Convert title to a safe filename."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "_", text)
    return text[:60]


def _find_idea_file(title_or_slug: str) -> Path | None:
    """Find an existing idea file by title or partial match."""
    ideas_dir = _ideas_dir()
    slug = _slugify(title_or_slug)
    # Exact slug match first
    for f in ideas_dir.glob("Idea_*.md"):
        if slug in f.stem.lower():
            return f
    # Fallback: search by content title
    for f in ideas_dir.glob("Idea_*.md"):
        try:
            content = f.read_text(encoding="utf-8")
            title_match = re.search(r"^title:\s*(.+)$", content, re.MULTILINE)
            if title_match and title_or_slug.lower() in title_match.group(1).lower():
                return f
        except Exception:
            continue
    return None


@tool
def save_idea(
    title: str,
    content: str,
    category: str = "General",
    tags: str = "",
) -> str:
    """
    Save a new creative idea to the Da Vinci vault.
    Args:
        title: Short descriptive title for the idea
        content: The full idea description, details, and possibilities
        category: Category label (e.g. 'Tech', 'Art', 'Business', 'Science', 'Life', 'Product')
        tags: Comma-separated tags (e.g. 'AI,automation,creative')
    """
    try:
        ideas_dir = _ideas_dir()
        slug = _slugify(title)
        timestamp = _now()
        filename = f"Idea_{timestamp}_{slug}.md"
        filepath = ideas_dir / filename

        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        tag_yaml = f"[{', '.join(tag_list)}]" if tag_list else "[]"

        frontmatter = (
            f"---\n"
            f"title: {title}\n"
            f"category: {category}\n"
            f"tags: {tag_yaml}\n"
            f"created: {_today()} {_time_str()}\n"
            f"status: raw\n"
            f"---\n\n"
            f"# {title}\n\n"
            f"{content}\n"
        )

        filepath.write_text(frontmatter, encoding="utf-8")

        return (
            f"Ide disimpan → Da Vinci Agent/{filename}\n"
            f"  Judul: '{title}' | Kategori: {category}"
            + (f" | Tags: {', '.join(tag_list)}" if tag_list else "")
        )
    except Exception as e:
        return f"[save_idea error] {e}"


@tool
def list_ideas(category: str = "") -> str:
    """
    List all saved ideas, optionally filtered by category.
    Args:
        category: Filter by category name. Leave empty to list all ideas.
    """
    try:
        ideas_dir = _ideas_dir()
        files = sorted(ideas_dir.glob("Idea_*.md"), reverse=True)

        if not files:
            return "Belum ada ide tersimpan. Yuk mulai brainstorm — ceritakan ide pertamamu!"

        results = []
        for f in files:
            try:
                content = f.read_text(encoding="utf-8")
            except Exception:
                continue
            title_m = re.search(r"^title:\s*(.+)$", content, re.MULTILINE)
            cat_m = re.search(r"^category:\s*(.+)$", content, re.MULTILINE)
            created_m = re.search(r"^created:\s*(.+)$", content, re.MULTILINE)
            status_m = re.search(r"^status:\s*(.+)$", content, re.MULTILINE)

            title = title_m.group(1).strip() if title_m else f.stem
            cat = cat_m.group(1).strip() if cat_m else "—"
            created = created_m.group(1).strip() if created_m else "—"
            status = status_m.group(1).strip() if status_m else "raw"

            if category and category.lower() not in cat.lower():
                continue

            results.append(f"  [{cat}] {title}  |  {created}  |  status: {status}")

        if not results:
            return f"Tidak ada ide dengan kategori '{category}'."

        header = f"Ide tersimpan ({len(results)} ide)"
        if category:
            header += f" — kategori: {category}"
        return header + ":\n\n" + "\n".join(results)
    except Exception as e:
        return f"[list_ideas error] {e}"


@tool
def read_idea(title: str) -> str:
    """
    Read the full content of a saved idea.
    Args:
        title: The title or partial title of the idea to read.
    """
    try:
        filepath = _find_idea_file(title)
        if not filepath:
            return f"Ide dengan judul '{title}' tidak ditemukan. Coba cek daftar ide dengan list_ideas()."

        content = filepath.read_text(encoding="utf-8")
        return f"[IDE: {filepath.name}]\n\n{content}"
    except Exception as e:
        return f"[read_idea error] {e}"


@tool
def expand_idea(title: str, expansion: str) -> str:
    """
    Expand or elaborate on an existing idea by appending new thoughts, angles, or details.
    Args:
        title: Title or partial title of the idea to expand
        expansion: New content to add — could be a new angle, implementation detail,
                   counter-argument, wild variation, or next steps
    """
    try:
        filepath = _find_idea_file(title)
        if not filepath:
            return f"Ide '{title}' tidak ditemukan. Gunakan save_idea() untuk membuat ide baru."

        ts = _time_str()
        today = _today()
        expansion_block = f"\n## Ekspansi — {today} {ts}\n\n{expansion}\n"

        with filepath.open("a", encoding="utf-8") as f:
            f.write(expansion_block)

        # Update status to 'expanded'
        raw = filepath.read_text(encoding="utf-8")
        raw = re.sub(r"^status:.*$", "status: expanded", raw, flags=re.MULTILINE)
        filepath.write_text(raw, encoding="utf-8")

        return (
            f"Ide '{title}' berhasil diperluas.\n"
            f"  File: Da Vinci Agent/{filepath.name}\n"
            f"  Status diupdate → expanded"
        )
    except Exception as e:
        return f"[expand_idea error] {e}"


@tool
def search_ideas(query: str) -> str:
    """
    Search across all saved ideas for a keyword or phrase.
    Args:
        query: Keyword or phrase to search in idea titles and content.
    """
    try:
        ideas_dir = _ideas_dir()
        query_lower = query.lower()
        results = []

        for filepath in sorted(ideas_dir.glob("Idea_*.md"), reverse=True):
            try:
                content = filepath.read_text(encoding="utf-8")
            except Exception:
                continue
            if query_lower not in content.lower():
                continue

            title_m = re.search(r"^title:\s*(.+)$", content, re.MULTILINE)
            cat_m = re.search(r"^category:\s*(.+)$", content, re.MULTILINE)
            title = title_m.group(1).strip() if title_m else filepath.stem
            cat = cat_m.group(1).strip() if cat_m else "—"

            idx = content.lower().find(query_lower)
            start = max(0, idx - 80)
            snippet = re.sub(r"\n+", " ", content[start: idx + 180].strip())
            results.append(f"  [{cat}] {title}\n   ...{snippet}...")

        if not results:
            return f"Tidak ada ide yang mengandung '{query}'."

        return (
            f"Ditemukan {len(results)} ide untuk '{query}':\n\n"
            + "\n\n".join(results[:10])
        )
    except Exception as e:
        return f"[search_ideas error] {e}"


@tool
def update_idea_status(title: str, status: str) -> str:
    """
    Update the status of a saved idea.
    Args:
        title: Title or partial title of the idea
        status: New status — one of: 'raw', 'expanded', 'in-progress', 'shelved', 'done'
    """
    valid_statuses = {"raw", "expanded", "in-progress", "shelved", "done"}
    try:
        if status not in valid_statuses:
            return f"Status tidak valid. Pilih salah satu: {', '.join(valid_statuses)}"

        filepath = _find_idea_file(title)
        if not filepath:
            return f"Ide '{title}' tidak ditemukan."

        raw = filepath.read_text(encoding="utf-8")
        raw = re.sub(r"^status:.*$", f"status: {status}", raw, flags=re.MULTILINE)
        filepath.write_text(raw, encoding="utf-8")

        return f"Status ide '{title}' diupdate → {status}"
    except Exception as e:
        return f"[update_idea_status error] {e}"


DAVINCI_TOOLS = [
    save_idea,
    list_ideas,
    read_idea,
    expand_idea,
    search_ideas,
    update_idea_status,
]
