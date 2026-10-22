"""Gabungkan bab-bab Manual Book (docs/manual/parts/*.md) → satu Markdown + satu HTML siap cetak.

    py scripts/build_manual_book.py            # HTML merujuk ./screenshots/ (folder harus ikut disalin)
    py scripts/build_manual_book.py --embed    # HTML mandiri: gambar disematkan sebagai JPEG base64

Luaran: docs/manual/BIOCHAIN_VISUAL_MANUAL_BOOK.md dan .html
"""

import base64
import html
import io
import re
import sys
from datetime import date
from pathlib import Path

import markdown
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
MANUAL = ROOT / "docs" / "manual"
PARTS = ["bab1_bab2.md", "bab3_petani.md", "bab4_bab5.md", "bab6_pabrik.md", "storyboard_video.md", "troubleshooting.md"]
TITLE = "Manual Book Visual Bio-Chain"

CSS = """
:root{--ink:#1c2620;--muted:#5b6b60;--bg:#fbfcf8;--card:#fff;--line:#dfe6dc;--brand:#3f6212;--brand-soft:#ecfccb;
--red:#EF4444;--green:#22C55E;--callout:#f0f7ff;--callout-line:#2563eb;--warn:#fff7ed;--warn-line:#ea580c}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--ink:#e6efe7;--muted:#a3b3a7;--bg:#111614;--card:#18201c;
--line:#2b3a31;--brand:#a3e635;--brand-soft:#1f2d14;--callout:#0f1b2d;--callout-line:#60a5fa;--warn:#2a1a0e;--warn-line:#fb923c}}
:root[data-theme="dark"]{--ink:#e6efe7;--muted:#a3b3a7;--bg:#111614;--card:#18201c;--line:#2b3a31;--brand:#a3e635;
--brand-soft:#1f2d14;--callout:#0f1b2d;--callout-line:#60a5fa;--warn:#2a1a0e;--warn-line:#fb923c}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 "Plus Jakarta Sans",system-ui,sans-serif}
.layout{display:grid;grid-template-columns:300px minmax(0,1fr);max-width:1400px;margin:0 auto}
nav.toc{position:sticky;top:0;height:100vh;overflow:auto;padding:24px 16px;border-right:1px solid var(--line);font-size:14px}
nav.toc ul{list-style:none;padding-left:12px;margin:4px 0}nav.toc>ul{padding-left:0}
nav.toc a{color:var(--ink);text-decoration:none;display:block;padding:2px 0}nav.toc a:hover{color:var(--brand)}
nav.toc .toc-title{font-weight:800;margin-bottom:12px;color:var(--brand)}
main{padding:32px 48px;min-width:0}
.cover{padding:48px 0 32px;border-bottom:3px solid var(--brand);margin-bottom:32px}
.cover h1{font-size:2.6rem;line-height:1.15;margin:0 0 8px}.cover p{color:var(--muted);margin:4px 0}
h1{font-size:2rem;margin-top:56px;padding-top:16px;border-top:2px solid var(--line);color:var(--brand)}
h2{font-size:1.45rem;margin-top:40px}h3{font-size:1.15rem;margin-top:32px;padding:8px 12px;background:var(--brand-soft);border-radius:8px}
img{max-width:100%;height:auto;border:1px solid var(--line);border-radius:10px;box-shadow:0 4px 16px rgba(0,0,0,.08);display:block;margin:16px auto}
img[src*="_petani_"],img[src*="_driver_"],img[src*="00_login"]{max-width:420px}
table{border-collapse:collapse;width:100%;margin:16px 0;font-size:14px;display:block;overflow-x:auto}
th,td{border:1px solid var(--line);padding:8px 10px;vertical-align:top;text-align:left}th{background:var(--brand-soft)}
blockquote{margin:16px 0;padding:12px 16px;background:var(--callout);border-left:4px solid var(--callout-line);border-radius:6px}
blockquote.warn{background:var(--warn);border-left-color:var(--warn-line)}
code{background:var(--brand-soft);padding:1px 5px;border-radius:4px;font-size:.9em}
pre{background:var(--card);border:1px solid var(--line);padding:12px;border-radius:8px;overflow-x:auto}pre code{background:none}
.num{display:inline-flex;align-items:center;justify-content:center;min-width:1.6em;height:1.6em;border-radius:50%;
background:var(--red);color:#fff;font-weight:800;font-size:.95em;line-height:1;margin-right:2px}
.mermaid{background:#fff;border-radius:10px;padding:12px;border:1px solid var(--line)}
.theme-btn{position:fixed;right:16px;bottom:16px;border:1px solid var(--line);background:var(--card);color:var(--ink);
border-radius:999px;padding:8px 14px;cursor:pointer}
@media (max-width:900px){.layout{grid-template-columns:1fr}nav.toc{position:static;height:auto;border-right:0;border-bottom:1px solid var(--line)}
main{padding:16px}.cover h1{font-size:1.9rem}}
@media print{nav.toc,.theme-btn{display:none}.layout{display:block}main{padding:0}h1{page-break-before:always}
img,table,blockquote{page-break-inside:avoid}:root{--bg:#fff}}
"""


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80] or "bagian"


def embed_img(src: str) -> str:
    """PNG @2x → JPEG q82 lebar maks 1600 px sebagai data URI (HTML mandiri yang tetap ringan)."""
    path = MANUAL / src
    if not path.exists():
        return src
    im = Image.open(path).convert("RGB")
    if im.width > 1600:
        im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def build(embed: bool) -> None:
    missing = [p for p in PARTS if not (MANUAL / "parts" / p).exists()]
    if missing:
        sys.exit(f"Bagian belum ada: {', '.join(missing)}")
    body_md = "\n\n".join((MANUAL / "parts" / p).read_text(encoding="utf-8").strip() for p in PARTS)
    today = date.today().strftime("%d-%m-%Y")
    header = f"# {TITLE}\n\nPanduan penggunaan bergambar: Petani → Pengepul → Driver → Pabrik → sirkular abu/biochar.\n\n" \
             f"*Dibangun {today} · screenshot asli aplikasi (`scripts/capture_annotated_manual.mts`).*\n\n"
    (MANUAL / "BIOCHAIN_VISUAL_MANUAL_BOOK.md").write_text(header + body_md + "\n", encoding="utf-8")

    # Blok mermaid dibiarkan sebagai <pre class="mermaid"> agar dirender mermaid.js
    mermaid_blocks: list[str] = []

    def keep_mermaid(m: re.Match) -> str:
        mermaid_blocks.append(m.group(1))
        return f"\n\nMERMAIDBLOCK{len(mermaid_blocks) - 1}\n\n"

    src = re.sub(r"```mermaid\n(.*?)```", keep_mermaid, body_md, flags=re.S)
    md = markdown.Markdown(extensions=["tables", "fenced_code", "attr_list", "sane_lists"])
    out = md.convert(src)
    for i, blk in enumerate(mermaid_blocks):
        out = out.replace(f"<p>MERMAIDBLOCK{i}</p>", f'<pre class="mermaid">{html.escape(blk)}</pre>')

    # Judul ber-id + daftar isi (h1/h2/h3)
    toc: list[tuple[int, str, str]] = []
    seen: dict[str, int] = {}

    def add_id(m: re.Match) -> str:
        level, inner = int(m.group(1)), m.group(2)
        text = re.sub(r"<[^>]+>", "", inner)
        sid = slug(text)
        seen[sid] = seen.get(sid, 0) + 1
        if seen[sid] > 1:
            sid = f"{sid}-{seen[sid]}"
        toc.append((level, sid, text))
        return f'<h{level} id="{sid}">{inner}</h{level}>'

    out = re.sub(r"<h([123])>(.*?)</h\1>", add_id, out)
    out = re.sub(r"[①-⑳]", lambda m: f'<span class="num">{m.group(0)}</span>', out)
    out = re.sub(r"<blockquote>(\s*<p>\s*(?:<strong>)?\s*⚠️)", r'<blockquote class="warn">\1', out)
    if embed:
        out = re.sub(r'src="(\./screenshots/[^"]+)"', lambda m: f'src="{embed_img(m.group(1))}"', out)
    out = out.replace("<img ", '<img loading="lazy" ')

    toc_html, depth = ["<ul>"], 1
    for level, sid, text in toc:
        while depth < level:
            toc_html.append("<ul>"); depth += 1
        while depth > level:
            toc_html.append("</ul>"); depth -= 1
        toc_html.append(f'<li><a href="#{sid}">{html.escape(text)}</a></li>')
    toc_html.append("</ul>" * depth)

    page = f"""<!doctype html>
<html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{TITLE}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;800&display=swap" rel="stylesheet">
<style>{CSS}</style></head>
<body><div class="layout">
<nav class="toc" aria-label="Daftar isi"><div class="toc-title">📘 Daftar Isi</div>{''.join(toc_html)}</nav>
<main><section class="cover"><h1 style="border:0;margin:0;padding:0;color:inherit">{TITLE}</h1>
<p>Panduan penggunaan bergambar: Petani / Penggilingan → Pengepul → Driver → Pabrik → sirkular abu & biochar.</p>
<p>Dibangun {today} · seluruh gambar adalah tangkapan layar asli aplikasi dengan anotasi <span class="num">①</span><span class="num">②</span><span class="num">③</span>.</p></section>
{out}
</main></div>
<button class="theme-btn" type="button" onclick="const r=document.documentElement;r.dataset.theme=r.dataset.theme==='dark'?'light':'dark'">🌓 Tema</button>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"
  integrity="sha384-WmdflGW9aGfoBdHc4rRyWzYuAjEmDwMdGdiPNacbwfGKxBW/SO6guzuQ76qjnSlr" crossorigin="anonymous"></script>
<script>try{{mermaid.initialize({{startOnLoad:true,theme:'neutral'}});}}catch(e){{}}</script>
</body></html>"""
    target = MANUAL / "BIOCHAIN_VISUAL_MANUAL_BOOK.html"
    target.write_text(page, encoding="utf-8")
    print(f"MD  : {MANUAL / 'BIOCHAIN_VISUAL_MANUAL_BOOK.md'}")
    print(f"HTML: {target} ({target.stat().st_size / 1_048_576:.1f} MB, {'mandiri' if embed else 'rujuk ./screenshots'}, {len(toc)} judul)")


if __name__ == "__main__":
    build(embed="--embed" in sys.argv)
