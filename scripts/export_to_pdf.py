"""Script untuk mengonversi DOKUMENTASI_LENGKAP_WEBSITE_DAN_MEKANISME_ANGKA.md ke PDF
menggunakan Python Markdown dan Headless Browser (Edge/Chrome) untuk hasil cetak
berkualitas tinggi dengan layout A4, tabel rapi, dan styling modern.
"""
import os
import subprocess
import markdown
import fitz  # PyMuPDF

MD_PATH = r"d:\IDE\bio-chain-prototype\docs\DOKUMENTASI_LENGKAP_WEBSITE_DAN_MEKANISME_ANGKA.md"
HTML_PATH = r"d:\IDE\bio-chain-prototype\docs\DOKUMENTASI_LENGKAP_WEBSITE_DAN_MEKANISME_ANGKA.html"
PDF_PATH = r"d:\IDE\bio-chain-prototype\docs\DOKUMENTASI_LENGKAP_WEBSITE_DAN_MEKANISME_ANGKA.pdf"

CSS_STYLES = """
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');

@page {
    size: A4;
    margin: 18mm 14mm 18mm 14mm;
    @bottom-center {
        content: "Halaman " counter(page) " dari " counter(pages);
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 8pt;
        color: #64748b;
    }
    @top-right {
        content: "Bio-Chain v2 · Master Documentation";
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 8pt;
        color: #94a3b8;
    }
}

* {
    box-sizing: border-box;
}

body {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    font-size: 9.5pt;
    line-height: 1.55;
    color: #1e293b;
    background-color: #ffffff;
    margin: 0;
    padding: 0;
}

/* Headings */
h1, h2, h3, h4, h5, h6 {
    color: #0f172a;
    font-weight: 700;
    margin-top: 1.4em;
    margin-bottom: 0.5em;
    page-break-after: avoid;
    break-after: avoid;
}

h1 {
    font-size: 19pt;
    font-weight: 800;
    color: #0f172a;
    border-bottom: 2.5px solid #10b981;
    padding-bottom: 6px;
    margin-top: 0;
}

/* Major Chapter Break */
body > h1:not(:first-of-type) {
    page-break-before: always;
    break-before: page;
    margin-top: 10mm;
}

h2 {
    font-size: 13pt;
    color: #047857;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 4px;
    margin-top: 1.6em;
}

h3 {
    font-size: 11pt;
    color: #1e293b;
    margin-top: 1.3em;
}

h4 {
    font-size: 10pt;
    color: #334155;
}

p, ul, ol {
    margin-top: 0.4em;
    margin-bottom: 0.7em;
}

li {
    margin-bottom: 0.25em;
}

/* Tables */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0 1.2em 0;
    font-size: 8.5pt;
    page-break-inside: avoid;
    break-inside: avoid;
}

th, td {
    border: 1px solid #cbd5e1;
    padding: 6px 9px;
    text-align: left;
    vertical-align: top;
}

th {
    background-color: #0f172a;
    color: #ffffff;
    font-weight: 600;
    font-size: 8.5pt;
}

tr:nth-child(even) {
    background-color: #f8fafc;
}

/* Code & Pre */
pre {
    background-color: #0f172a;
    color: #f8fafc;
    padding: 10px 14px;
    border-radius: 6px;
    font-family: 'JetBrains Mono', Consolas, Monaco, monospace;
    font-size: 8pt;
    line-height: 1.45;
    overflow-x: hidden;
    white-space: pre-wrap;
    word-break: break-all;
    page-break-inside: avoid;
    break-inside: avoid;
    border: 1px solid #334155;
}

code {
    font-family: 'JetBrains Mono', Consolas, Monaco, monospace;
    font-size: 8.5pt;
    background-color: #f1f5f9;
    color: #0f766e;
    padding: 1.5px 4px;
    border-radius: 4px;
    border: 1px solid #e2e8f0;
}

pre code {
    background-color: transparent;
    color: inherit;
    padding: 0;
    border: none;
    font-size: 8pt;
}

/* Blockquotes */
blockquote {
    border-left: 4px solid #10b981;
    background-color: #ecfdf5;
    margin: 1em 0;
    padding: 8px 14px;
    color: #065f46;
    font-size: 9pt;
    page-break-inside: avoid;
    break-inside: avoid;
    border-radius: 0 6px 6px 0;
}

hr {
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 1.8em 0;
}

/* Header Banner / Badge */
.doc-header-banner {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    color: #ffffff;
    padding: 24px 28px;
    border-radius: 10px;
    margin-bottom: 24px;
    border-left: 6px solid #10b981;
}

.doc-header-banner h1 {
    color: #ffffff;
    border-bottom: none;
    margin: 0 0 6px 0;
    padding: 0;
    font-size: 20pt;
}

.doc-header-banner p {
    color: #94a3b8;
    margin: 0;
    font-size: 10pt;
}

.doc-meta-tags {
    margin-top: 12px;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

.meta-pill {
    background: rgba(16, 185, 129, 0.15);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.3);
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 8pt;
    font-weight: 600;
}
"""

def main():
    print(f"Membaca Markdown dari: {MD_PATH}")
    with open(MD_PATH, "r", encoding="utf-8") as f:
        md_content = f.read()

    print("Mengonversi Markdown ke HTML...")
    # Extensions: extra covers tables, attr_list, def_list, fenced_code, etc.
    html_body = markdown.markdown(
        md_content,
        extensions=[
            "extra",
            "codehilite",
            "toc",
            "sane_lists"
        ]
    )

    full_html = f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<title>Bio-Chain v2 — Master Documentation</title>
<style>
{CSS_STYLES}
</style>
</head>
<body>
{html_body}
</body>
</html>
"""

    print(f"Menulis HTML ke: {HTML_PATH}")
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(full_html)

    # Temukan browser executable
    browsers = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    browser_exe = None
    for b in browsers:
        if os.path.exists(b):
            browser_exe = b
            break

    if not browser_exe:
        raise RuntimeError("Tidak dapat menemukan Google Chrome atau Microsoft Edge.")

    print(f"Mengeksekusi headless browser untuk cetak PDF: {browser_exe}")
    cmd = [
        browser_exe,
        "--headless=new",
        "--disable-gpu",
        "--allow-file-access-from-files",
        "--no-pdf-header-footer",
        f"--print-to-pdf={PDF_PATH}",
        f"file:///{HTML_PATH.replace(os.sep, '/')}"
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Peringatan browser: {res.stderr}")

    if not os.path.exists(PDF_PATH):
        raise RuntimeError(f"Gagal membuat file PDF di {PDF_PATH}")

    # Cek PDF dengan PyMuPDF
    doc = fitz.open(PDF_PATH)
    page_count = len(doc)
    doc.close()

    size_kb = os.path.getsize(PDF_PATH) / 1024
    print(f"Berhasil! PDF telah dibuat: {PDF_PATH}")
    print(f"Jumlah halaman: {page_count} halaman")
    print(f"Ukuran berkas: {size_kb:.2f} KB")

if __name__ == "__main__":
    main()
