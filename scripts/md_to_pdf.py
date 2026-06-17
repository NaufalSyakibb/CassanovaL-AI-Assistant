"""Convert Markdown docs to styled PDF using `markdown` + Playwright (Chromium).

Usage:  python.exe scripts/md_to_pdf.py FILE.md [FILE2.md ...]
Output: FILE.pdf next to each input.
"""
import sys
import re
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

CSS = """
@page { size: A4; margin: 18mm 16mm; }
* { box-sizing: border-box; }
body {
  font-family: "Segoe UI", Inter, Helvetica, Arial, sans-serif;
  font-size: 10.5pt; line-height: 1.55; color: #1a1a1a; max-width: 100%;
}
h1, h2, h3, h4 { color: #6b4f1d; line-height: 1.25; page-break-after: avoid; }
h1 { font-size: 22pt; border-bottom: 3px solid #A68A3E; padding-bottom: 6px; margin-top: 0; }
h2 { font-size: 16pt; border-bottom: 1px solid #d8cba6; padding-bottom: 4px; margin-top: 26px; }
h3 { font-size: 13pt; margin-top: 20px; }
h4 { font-size: 11pt; color: #333; }
p, li { orphans: 3; widows: 3; }
a { color: #8a6d2f; text-decoration: none; }
code {
  font-family: "JetBrains Mono", "Cascadia Code", Consolas, monospace;
  font-size: 9pt; background: #f4f0e6; padding: 1px 5px; border-radius: 4px; color: #6b4f1d;
}
pre {
  background: #1e1b14; color: #f0ead6; padding: 12px 14px; border-radius: 8px;
  overflow-x: auto; font-size: 8.6pt; line-height: 1.45; page-break-inside: avoid;
  border: 1px solid #3a3326;
}
pre code { background: none; color: inherit; padding: 0; font-size: inherit; }
table { border-collapse: collapse; width: 100%; margin: 14px 0; font-size: 9.2pt; page-break-inside: avoid; }
th, td { border: 1px solid #d8cba6; padding: 6px 9px; text-align: left; vertical-align: top; }
th { background: #f4f0e6; color: #6b4f1d; font-weight: 600; }
tr:nth-child(even) td { background: #faf8f1; }
blockquote {
  border-left: 3px solid #A68A3E; margin: 12px 0; padding: 4px 14px;
  background: #faf8f1; color: #555; border-radius: 0 6px 6px 0;
}
hr { border: none; border-top: 1px solid #e0d6bb; margin: 22px 0; }
ul, ol { padding-left: 22px; }
.doc-footer { margin-top: 30px; padding-top: 10px; border-top: 1px solid #e0d6bb;
  font-size: 8pt; color: #999; text-align: center; }
"""

EXTS = ["tables", "fenced_code", "toc", "sane_lists", "attr_list", "def_list"]


def convert(md_path: Path) -> Path:
    text = md_path.read_text(encoding="utf-8")
    html_body = markdown.markdown(text, extensions=EXTS)
    title = md_path.stem
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>{title}</title><style>{CSS}</style></head>
<body>{html_body}
<div class="doc-footer">CassanovaL — {title} · generated from {md_path.name}</div>
</body></html>"""
    pdf_path = md_path.with_suffix(".pdf")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "18mm", "bottom": "18mm", "left": "16mm", "right": "16mm"},
            display_header_footer=True,
            header_template="<div></div>",
            footer_template=(
                '<div style="font-size:8px;color:#999;width:100%;text-align:center;">'
                '<span class="pageNumber"></span> / <span class="totalPages"></span></div>'
            ),
        )
        browser.close()
    return pdf_path


def main():
    if len(sys.argv) < 2:
        print("usage: md_to_pdf.py FILE.md [FILE2.md ...]")
        sys.exit(1)
    for arg in sys.argv[1:]:
        src = Path(arg)
        if not src.exists():
            print(f"  ! skip (not found): {src}")
            continue
        out = convert(src)
        print(f"  OK  {src.name} -> {out.name}  ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
