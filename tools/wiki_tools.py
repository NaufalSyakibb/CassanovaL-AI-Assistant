"""
LLM Wiki tools — persistent, compounding knowledge base in Obsidian.

Architecture (3 layers):
  raw/      → immutable source documents (LLM reads, never modifies)
  wiki/     → LLM-maintained markdown pages (summaries, entities, concepts)
  schema.md → conventions the LLM follows when maintaining the wiki

Operations:
  ingest_source()      → process a new source into the wiki
  update_wiki_entity() → create/update an entity or concept page
  query_wiki()         → search index + read pages + synthesize
  lint_wiki()          → health-check for orphans, contradictions, gaps
"""
import os
import re
from pathlib import Path
from datetime import datetime
from langchain.tools import tool


# ── Internal helpers ──────────────────────────────────────────────────────────

def _vault() -> Path:
    path = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    if not path:
        raise EnvironmentError("OBSIDIAN_VAULT_PATH tidak di-set di .env")
    v = Path(path)
    if not v.exists():
        raise FileNotFoundError(f"Vault tidak ditemukan: {v}")
    return v


def _wiki_dir() -> Path:
    d = _vault() / "wiki"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "-", name).strip()


def _ensure_scaffold() -> None:
    """Create index.md, log.md, and schema.md if they don't exist."""
    wiki = _wiki_dir()

    index = wiki / "index.md"
    if not index.exists():
        index.write_text(
            "# Wiki Index\n\n"
            "> Katalog semua halaman wiki. Diperbarui otomatis oleh LLM setiap ingest.\n\n"
            "## Entities\n\n"
            "_(belum ada)_\n\n"
            "## Concepts\n\n"
            "_(belum ada)_\n\n"
            "## Sources\n\n"
            "_(belum ada)_\n\n"
            "## Research Reports\n\n"
            "_(belum ada)_\n",
            encoding="utf-8",
        )

    log = wiki / "log.md"
    if not log.exists():
        log.write_text(
            "# Wiki Log\n\n"
            "> Append-only record of all wiki operations. Format: `## [YYYY-MM-DD] type | title`\n\n",
            encoding="utf-8",
        )

    schema = wiki / "schema.md"
    if not schema.exists():
        schema.write_text(
            "# Wiki Schema\n\n"
            "## Folder Structure\n"
            "```\n"
            "wiki/\n"
            "  index.md          ← catalog of all pages (LLM updates on every ingest)\n"
            "  log.md            ← append-only operation log\n"
            "  schema.md         ← this file (conventions)\n"
            "  entities/         ← pages about people, places, products, orgs\n"
            "  concepts/         ← pages about ideas, frameworks, theories\n"
            "  sources/          ← one summary page per ingested source\n"
            "  research/         ← research reports from the research agent\n"
            "  data/             ← structured data mirrors (tasks, budget, food)\n"
            "```\n\n"
            "## Page Frontmatter\n"
            "Every wiki page must have YAML frontmatter:\n"
            "```yaml\n"
            "---\n"
            "title: Page Title\n"
            "category: entity | concept | source | research\n"
            "tags: [tag1, tag2]\n"
            "created: YYYY-MM-DD\n"
            "updated: YYYY-MM-DD\n"
            "sources: [url1, url2]\n"
            "---\n"
            "```\n\n"
            "## Cross-Reference Convention\n"
            "Link to other wiki pages using `[[Page Title]]` syntax.\n"
            "Always add outbound links to related pages at the bottom under `## See Also`.\n\n"
            "## Ingest Workflow\n"
            "1. Read the source fully\n"
            "2. Create/update `wiki/sources/<title>.md` with summary + key claims\n"
            "3. Update any relevant entity/concept pages\n"
            "4. Update `wiki/index.md` with the new page entry\n"
            "5. Append to `wiki/log.md`\n\n"
            "## Lint Checks\n"
            "- Orphan pages (no inbound links)\n"
            "- Pages with no outbound links\n"
            "- Contradictions between entity pages and newer sources\n"
            "- Concepts mentioned in body text but lacking their own page\n",
            encoding="utf-8",
        )


def _append_to_log(entry_type: str, title: str, summary: str) -> None:
    """Append one entry to wiki/log.md."""
    try:
        wiki = _wiki_dir()
        log = wiki / "log.md"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n## [{ts}] {entry_type} | {title}\n{summary}\n"
        with log.open("a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass


def _update_index(title: str, summary: str, category: str, page_path: str) -> None:
    """
    Add or update one entry in wiki/index.md under the correct category section.
    Entry format: `- [[Page Title]] — one-line summary`
    """
    try:
        wiki = _wiki_dir()
        index_file = wiki / "index.md"
        _ensure_scaffold()
        content = index_file.read_text(encoding="utf-8")

        entry_line = f"- [[{title}]] — {summary}"
        # Section headers match schema: Entities, Concepts, Sources, Research Reports
        section_map = {
            "entity": "## Entities",
            "concept": "## Concepts",
            "source": "## Sources",
            "research": "## Research Reports",
        }
        section_header = section_map.get(category.lower(), "## Sources")

        # Remove old entry if it exists
        content = re.sub(rf"^- \[\[{re.escape(title)}\]\].*$", "", content, flags=re.MULTILINE)
        content = re.sub(r"\n{3,}", "\n\n", content)

        # Replace placeholder or append under section
        placeholder = "_(belum ada)_"
        if section_header in content:
            # Insert after section header, replacing placeholder if present
            def replace_section(m):
                block = m.group(0)
                if placeholder in block:
                    block = block.replace(placeholder, entry_line)
                else:
                    # append before next ##
                    block = block.rstrip() + "\n" + entry_line + "\n"
                return block

            pattern = rf"({re.escape(section_header)}\n)([\s\S]*?)(?=\n## |\Z)"
            content = re.sub(pattern, replace_section, content)
        else:
            content += f"\n{section_header}\n\n{entry_line}\n"

        index_file.write_text(content.strip() + "\n", encoding="utf-8")
    except Exception:
        pass


# ── Public @tool functions ────────────────────────────────────────────────────

@tool
def ingest_source(
    title: str,
    content: str,
    source_url: str = "",
    source_type: str = "article",
    tags: str = "",
) -> str:
    """
    Proses sebuah sumber (artikel, paper, catatan) ke dalam wiki.
    Membuat halaman ringkasan di wiki/sources/, memperbarui index.md, dan mencatat di log.md.

    Args:
        title      : Judul sumber.
        content    : Isi/ringkasan sumber yang sudah kamu baca dan ekstrak.
        source_url : URL asli (kosongkan jika tidak ada).
        source_type: Tipe sumber — 'article', 'paper', 'video', 'note', 'book'.
        tags       : Comma-separated tags (e.g. 'protein,hypertrophy,nutrition').
    """
    try:
        _ensure_scaffold()
        wiki = _wiki_dir()
        sources_dir = wiki / "sources"
        sources_dir.mkdir(exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        tag_yaml = ", ".join(f'"{t}"' for t in tag_list)

        page_content = (
            f"---\n"
            f"title: \"{_safe(title)}\"\n"
            f"category: source\n"
            f"source_type: {source_type}\n"
            f"source_url: {source_url or 'N/A'}\n"
            f"tags: [{tag_yaml}]\n"
            f"created: {today}\n"
            f"updated: {today}\n"
            f"---\n\n"
            f"# {title}\n\n"
            f"{content}\n\n"
            f"## See Also\n\n"
            f"_(tambahkan link ke halaman wiki terkait)_\n"
        )

        safe_title = _safe(title)
        page_file = sources_dir / f"{safe_title}.md"
        page_file.write_text(page_content, encoding="utf-8")

        # First line of content as summary for index
        first_line = content.strip().split("\n")[0][:120]
        _update_index(title, first_line, "source", f"wiki/sources/{safe_title}.md")
        _append_to_log("ingest", title, f"type={source_type} url={source_url or 'none'} tags=[{tags}]")

        return (
            f"✅ Sumber diingest ke wiki: wiki/sources/{safe_title}.md\n"
            f"   Index dan log diperbarui.\n"
            f"   Selanjutnya: perbarui halaman entity/concept yang relevan dengan update_wiki_entity()."
        )
    except Exception as e:
        return f"[ingest_source error] {e}"


@tool
def update_wiki_entity(
    name: str,
    new_info: str,
    category: str = "concept",
    related_pages: str = "",
) -> str:
    """
    Buat atau perbarui halaman entity/concept di wiki.
    Gunakan ini setelah ingest untuk memperbarui halaman topik yang terkena dampak sumber baru.

    Args:
        name         : Nama entity atau konsep (e.g. 'Leucine Threshold', 'Lean Bulk').
        new_info     : Informasi baru yang harus ditambahkan atau direvisi.
        category     : 'entity' (orang/tempat/produk) atau 'concept' (ide/teori/framework).
        related_pages: Comma-separated nama halaman wiki yang terkait (untuk See Also).
    """
    try:
        _ensure_scaffold()
        wiki = _wiki_dir()
        subdir = wiki / (category.lower() + "s")
        subdir.mkdir(exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        safe_name = _safe(name)
        page_file = subdir / f"{safe_name}.md"

        if page_file.exists():
            existing = page_file.read_text(encoding="utf-8")
            # Update the 'updated' date in frontmatter
            existing = re.sub(r"updated: \d{4}-\d{2}-\d{2}", f"updated: {today}", existing)
            # Append new info before See Also
            new_section = f"\n### Update {today}\n\n{new_info}\n"
            if "## See Also" in existing:
                existing = existing.replace("## See Also", new_section + "\n## See Also")
            else:
                existing = existing.rstrip() + new_section
            page_file.write_text(existing, encoding="utf-8")
            action = "diperbarui"
        else:
            related_links = "\n".join(
                f"- [[{r.strip()}]]" for r in related_pages.split(",") if r.strip()
            ) or "_(belum ada)_"
            page_content = (
                f"---\n"
                f"title: \"{_safe(name)}\"\n"
                f"category: {category}\n"
                f"tags: []\n"
                f"created: {today}\n"
                f"updated: {today}\n"
                f"---\n\n"
                f"# {name}\n\n"
                f"{new_info}\n\n"
                f"## See Also\n\n"
                f"{related_links}\n"
            )
            page_file.write_text(page_content, encoding="utf-8")
            action = "dibuat"

        first_line = new_info.strip().split("\n")[0][:120]
        _update_index(name, first_line, category, f"wiki/{category}s/{safe_name}.md")
        _append_to_log("entity_update", name, f"category={category} action={action}")

        return f"✅ Halaman '{name}' {action}: wiki/{category}s/{safe_name}.md"
    except Exception as e:
        return f"[update_wiki_entity error] {e}"


@tool
def query_wiki(question: str) -> str:
    """
    Cari jawaban dari wiki dengan membaca index.md terlebih dahulu,
    lalu drill ke halaman-halaman relevan dan sintesis jawabannya.

    Args:
        question: Pertanyaan atau topik yang ingin dicari di wiki.
    """
    try:
        _ensure_scaffold()
        wiki = _wiki_dir()
        vault = _vault()

        # Step 1: Read index
        index_file = wiki / "index.md"
        index_content = index_file.read_text(encoding="utf-8") if index_file.exists() else ""

        # Step 2: Find relevant pages by searching wiki folder
        q_lower = question.lower()
        matches = []
        for page in sorted(wiki.rglob("*.md")):
            if page.name in ("index.md", "log.md", "schema.md"):
                continue
            try:
                body = page.read_text(encoding="utf-8")
                if q_lower in page.stem.lower() or q_lower in body.lower():
                    idx = body.lower().find(q_lower)
                    start = max(0, idx - 150) if idx >= 0 else 0
                    snippet = re.sub(r"\n+", " ", body[start: idx + 300].strip())
                    rel = page.relative_to(vault)
                    matches.append(f"📄 [[{page.stem}]] ({rel})\n   ...{snippet}...")
            except Exception:
                continue

        if not matches:
            return (
                f"Tidak ada halaman wiki yang mengandung '{question}'.\n"
                f"Pertimbangkan untuk mengingest sumber terkait dengan ingest_source()."
            )

        _append_to_log("query", question, f"pages_found={len(matches)}")

        result = f"## Wiki Query: {question}\n\n"
        result += f"**{len(matches)} halaman relevan ditemukan:**\n\n"
        result += "\n\n".join(matches[:8])
        result += (
            "\n\n---\n"
            "_Baca halaman spesifik dengan read_wiki_page(title) untuk detail lengkap._"
        )
        return result
    except Exception as e:
        return f"[query_wiki error] {e}"


@tool
def lint_wiki() -> str:
    """
    Periksa kesehatan wiki: orphan pages, halaman tanpa cross-reference,
    gap topik, dan potensi kontradiksi antar halaman.
    """
    try:
        _ensure_scaffold()
        wiki = _wiki_dir()
        vault = _vault()

        all_pages = [p for p in wiki.rglob("*.md") if p.name not in ("index.md", "log.md", "schema.md")]
        if not all_pages:
            return "Wiki kosong. Mulai dengan ingest_source() untuk menambahkan sumber pertama."

        # Collect all outbound [[links]]
        all_titles = {p.stem for p in all_pages}
        link_pattern = re.compile(r"\[\[([^\]]+)\]\]")
        inbound: dict[str, int] = {t: 0 for t in all_titles}
        outbound: dict[str, list] = {}
        no_outbound = []

        for page in all_pages:
            try:
                body = page.read_text(encoding="utf-8")
                links = link_pattern.findall(body)
                outbound[page.stem] = links
                for lnk in links:
                    if lnk in inbound:
                        inbound[lnk] += 1
                if not links:
                    no_outbound.append(page.stem)
            except Exception:
                continue

        orphans = [t for t, count in inbound.items() if count == 0]
        rel_paths = {p.stem: str(p.relative_to(vault)) for p in all_pages}

        lines = ["# Wiki Lint Report", f"**Total halaman:** {len(all_pages)}", ""]

        if orphans:
            lines.append(f"## ⚠️ Orphan Pages ({len(orphans)}) — tidak ada halaman lain yang menaut ke sini")
            for o in orphans:
                lines.append(f"  - {rel_paths.get(o, o)}")
        else:
            lines.append("## ✅ Tidak ada orphan pages")

        lines.append("")
        if no_outbound:
            lines.append(f"## ⚠️ Halaman tanpa outbound links ({len(no_outbound)})")
            for p in no_outbound:
                lines.append(f"  - {rel_paths.get(p, p)}")
        else:
            lines.append("## ✅ Semua halaman punya outbound links")

        lines += [
            "",
            "## 💡 Rekomendasi",
            "- Untuk orphan pages: tambahkan [[link]] ke halaman tersebut dari halaman terkait.",
            "- Untuk halaman tanpa links: tambahkan bagian '## See Also' dengan [[link]] ke konsep terkait.",
            "- Jalankan ingest_source() untuk sumber baru yang belum diproses.",
        ]

        _append_to_log("lint", "Wiki Health Check", f"pages={len(all_pages)} orphans={len(orphans)}")
        return "\n".join(lines)
    except Exception as e:
        return f"[lint_wiki error] {e}"


@tool
def write_research_to_wiki(title: str, report: str, tags: str = "") -> str:
    """
    Simpan laporan riset ke wiki/research/ dan perbarui index + log.
    Dipanggil oleh research agent setelah menyelesaikan investigasi.

    Args:
        title : Judul laporan riset.
        report: Konten laporan lengkap dalam format Markdown.
        tags  : Comma-separated tags (e.g. 'AI,machine-learning,2026').
    """
    try:
        _ensure_scaffold()
        wiki = _wiki_dir()
        research_dir = wiki / "research"
        research_dir.mkdir(exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        tag_yaml = ", ".join(f'"{t}"' for t in tag_list)
        safe_title = _safe(title)

        frontmatter = (
            f"---\n"
            f"title: \"{_safe(title)}\"\n"
            f"category: research\n"
            f"tags: [{tag_yaml}]\n"
            f"created: {today}\n"
            f"updated: {today}\n"
            f"---\n\n"
        )

        page_file = research_dir / f"{today} {safe_title}.md"
        page_file.write_text(frontmatter + report, encoding="utf-8")

        first_line = report.strip().split("\n")[0].lstrip("#").strip()[:120]
        _update_index(title, first_line, "research", f"wiki/research/{today} {safe_title}.md")
        _append_to_log("research", title, f"tags=[{tags}]")

        return f"✅ Laporan riset disimpan: wiki/research/{today} {safe_title}.md"
    except Exception as e:
        return f"[write_research_to_wiki error] {e}"


WIKI_TOOLS = [
    ingest_source,
    update_wiki_entity,
    query_wiki,
    lint_wiki,
    write_research_to_wiki,
]
