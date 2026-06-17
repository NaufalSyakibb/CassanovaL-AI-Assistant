"""Render each page of a PDF to PNG images, then build a Markdown viewer that
embeds the pages inline so GitHub displays the whole document without opening
the PDF.

Usage:  python.exe scripts/pdf_to_images.py FILE.pdf [FILE2.pdf ...]
Output: docs/preview/<stem>/page-001.png ...
        <stem>.view.md  (embeds all pages)
"""
import sys
from pathlib import Path

import fitz  # PyMuPDF

ZOOM = 2.0  # ~144 DPI, crisp on retina
PREVIEW_ROOT = Path("docs/preview")


def render(pdf_path: Path) -> int:
    stem = pdf_path.stem
    out_dir = PREVIEW_ROOT / stem
    out_dir.mkdir(parents=True, exist_ok=True)

    # Clear any stale pages so deleted pages don't linger
    for old in out_dir.glob("page-*.png"):
        old.unlink()

    doc = fitz.open(str(pdf_path))
    mat = fitz.Matrix(ZOOM, ZOOM)
    n = doc.page_count
    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=mat, alpha=False)
        pix.save(str(out_dir / f"page-{i:03d}.png"))
    doc.close()

    # Build the Markdown viewer
    rel = out_dir.as_posix()
    lines = [
        f"# {stem} — Rendered View",
        "",
        f"> Auto-generated from **{pdf_path.name}** ({n} pages). "
        f"Source: [`{stem}.md`]({stem}.md) · PDF: [`{pdf_path.name}`]({pdf_path.name})",
        "",
    ]
    for i in range(1, n + 1):
        lines.append(f"![{stem} page {i}]({rel}/page-{i:03d}.png)")
        lines.append("")
    view_md = Path(f"{stem}.view.md")
    view_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"  OK  {pdf_path.name}: {n} pages -> {out_dir}/  + {view_md.name}")
    return n


def main():
    if len(sys.argv) < 2:
        print("usage: pdf_to_images.py FILE.pdf [FILE2.pdf ...]")
        sys.exit(1)
    for arg in sys.argv[1:]:
        p = Path(arg)
        if not p.exists():
            print(f"  ! skip (not found): {p}")
            continue
        render(p)


if __name__ == "__main__":
    main()
