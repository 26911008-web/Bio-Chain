"""Script generator dokumen komprehensif Word (DOCX):
Peta Aliran (Process Map) & Panduan Langkah demi Langkah (Step-by-Step)
Sistem Bio-Chain v2: Dari Petani hingga Reaktor Pabrik.
"""

import os
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

# Warna Tema Bio-Chain v2
COLOR_PRIMARY_DARK = "1B5E20"    # Hijau Hutan Gelap (Judul Utama & Header Tabel)
COLOR_PRIMARY = "2E7D32"         # Hijau Daun (Subjudul H1 & Aksen Kuat)
COLOR_SECONDARY = "00695C"       # Teal / Hijau Laut (H2 & Badge Teknis)
COLOR_ACCENT = "0277BD"          # Biru Laut (H3 & Parameter)
COLOR_TEXT_MAIN = "212121"       # Abu-abu Sangat Gelap (Teks Paragraf)
COLOR_BG_LIGHT = "F1F8E9"        # Latar Hijau Muda (Callout / Shading Box)
COLOR_BG_ALT = "F9FBE7"          # Latar Belang Tabel (Zebra Striping)
COLOR_BORDER = "B0BEC5"          # Abu-abu Border Tabel
COLOR_ALERT_BORDER = "43A047"    # Hijau Garis Pinggir Callout
COLOR_WHITE = "FFFFFF"

def set_cell_background(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=120, bottom=120, left=180, right=180):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)

def set_cell_borders(cell, top=None, bottom=None, left=None, right=None):
    tcPr = cell._tc.get_or_add_tcPr()
    borders = ['<w:tcBorders xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">']
    for side, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        if val:
            borders.append(f'<w:{side} w:val="{val.get("val","single")}" w:sz="{val.get("sz",4)}" w:space="0" w:color="{val.get("color","B0BEC5")}"/>')
        else:
            borders.append(f'<w:{side} w:val="none"/>')
    borders.append('</w:tcBorders>')
    tcPr.append(parse_xml(''.join(borders)))

def format_run(run, font_name="Calibri", font_size=11, bold=False, italic=False, color_rgb=(33, 33, 33)):
    run.font.name = font_name
    run.font.size = Pt(font_size)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = RGBColor(*color_rgb)

def add_styled_paragraph(doc, text="", font_size=11, bold=False, italic=False, color_hex="212121", 
                         space_before=3, space_after=6, align=WD_ALIGN_PARAGRAPH.LEFT, line_spacing=1.15):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = line_spacing
    if text:
        r = p.add_run(text)
        r_color = RGBColor(int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16))
        format_run(r, font_size=font_size, bold=bold, italic=italic, color_rgb=r_color)
    return p

def add_heading_1(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    format_run(r, font_size=15, bold=True, color_rgb=RGBColor(27, 94, 32))
    return p

def add_heading_2(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(13)
    p.paragraph_format.space_after = Pt(5)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    format_run(r, font_size=12.5, bold=True, color_rgb=RGBColor(0, 105, 92))
    return p

def add_heading_3(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    format_run(r, font_size=11, bold=True, italic=True, color_rgb=RGBColor(2, 119, 189))
    return p

def add_callout(doc, text, title="💡 CATATAN PENTING & BEST PRACTICE", alert_type="note"):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    tbl.columns[0].width = Inches(6.5)
    
    cell = tbl.cell(0, 0)
    bg_color = "E8F5E9" if alert_type == "note" else "FFF9C4" if alert_type == "warning" else "E1F5FE"
    border_color = "2E7D32" if alert_type == "note" else "FBC02D" if alert_type == "warning" else "0288D1"
    
    set_cell_background(cell, bg_color)
    set_cell_margins(cell, top=140, bottom=140, left=200, right=180)
    set_cell_borders(cell, left={"val": "single", "sz": 24, "color": border_color})
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.15
    r_title = p.add_run(f"{title}\n")
    format_run(r_title, font_size=10.5, bold=True, color_rgb=RGBColor(27, 94, 32))
    
    r_text = p.add_run(text)
    format_run(r_text, font_size=10, italic=False, color_rgb=RGBColor(33, 33, 33))
    
    sp = doc.add_paragraph()
    sp.paragraph_format.space_before = Pt(0)
    sp.paragraph_format.space_after = Pt(6)

def add_code_block(doc, code_str):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    tbl.columns[0].width = Inches(6.5)
    
    cell = tbl.cell(0, 0)
    set_cell_background(cell, "ECEFF1")
    set_cell_margins(cell, top=120, bottom=120, left=180, right=180)
    set_cell_borders(cell, left={"val": "single", "sz": 18, "color": "607D8B"})
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.05
    r = p.add_run(code_str)
    format_run(r, font_name="Consolas", font_size=9, color_rgb=RGBColor(38, 50, 56))
    
    sp = doc.add_paragraph()
    sp.paragraph_format.space_before = Pt(0)
    sp.paragraph_format.space_after = Pt(4)

def add_styled_table(doc, headers, data_rows, col_widths=None):
    num_cols = len(headers)
    tbl = doc.add_table(rows=len(data_rows) + 1, cols=num_cols)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    
    # Header Row
    hdr_cells = tbl.rows[0].cells
    for col_idx, header_text in enumerate(headers):
        cell = hdr_cells[col_idx]
        set_cell_background(cell, COLOR_PRIMARY_DARK)
        set_cell_margins(cell, top=140, bottom=140, left=140, right=140)
        set_cell_borders(cell, 
                         top={"val": "single", "sz": 6, "color": COLOR_PRIMARY_DARK},
                         bottom={"val": "single", "sz": 12, "color": "0D3311"},
                         left={"val": "single", "sz": 4, "color": "2E7D32"},
                         right={"val": "single", "sz": 4, "color": "2E7D32"})
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(header_text)
        format_run(r, font_size=9, bold=True, color_rgb=RGBColor(255, 255, 255))
        if col_widths and col_idx < len(col_widths):
            cell.width = Inches(col_widths[col_idx])
            
    # Data Rows
    for row_idx, row_data in enumerate(data_rows):
        row_cells = tbl.rows[row_idx + 1].cells
        bg_col = COLOR_BG_ALT if (row_idx % 2 == 1) else COLOR_WHITE
        for col_idx, cell_value in enumerate(row_data):
            cell = row_cells[col_idx]
            set_cell_background(cell, bg_col)
            set_cell_margins(cell, top=90, bottom=90, left=110, right=110)
            set_cell_borders(cell, 
                             top={"val": "single", "sz": 4, "color": COLOR_BORDER},
                             bottom={"val": "single", "sz": 4, "color": COLOR_BORDER},
                             left={"val": "single", "sz": 4, "color": COLOR_BORDER},
                             right={"val": "single", "sz": 4, "color": COLOR_BORDER})
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.line_spacing = 1.1
            
            val_str = str(cell_value)
            if len(val_str) <= 12 or val_str.startswith("Grade") or val_str.startswith("Rp") or val_str.endswith("%") or val_str.startswith("POST") or val_str.startswith("GET"):
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                
            r = p.add_run(val_str)
            format_run(r, font_size=8.5, color_rgb=RGBColor(33, 33, 33))
            if col_widths and col_idx < len(col_widths):
                cell.width = Inches(col_widths[col_idx])
                
    sp = doc.add_paragraph()
    sp.paragraph_format.space_before = Pt(0)
    sp.paragraph_format.space_after = Pt(6)

print("Building complete document...")
doc = docx.Document()

# Setting Page Margins (1 inch / 2.54 cm all sides)
for section in doc.sections:
    section.top_margin = Inches(1.0)
    section.bottom_margin = Inches(1.0)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)

# ==============================================================================
# COVER PAGE / TITLE
# ==============================================================================
p_cov = add_styled_paragraph(doc, "BIO-CHAIN v2", font_size=26, bold=True, color_hex="1B5E20", 
                            space_before=36, space_after=4, align=WD_ALIGN_PARAGRAPH.CENTER)
p_sub = add_styled_paragraph(doc, "Smart Rice-Husk Supply Chain for Pyrolysis Biochar", font_size=15, bold=True, 
                            color_hex="00695C", space_before=2, space_after=14, align=WD_ALIGN_PARAGRAPH.CENTER)
p_tag = add_styled_paragraph(doc, "DOKUMEN ARSITEKTUR, PETA PROSES (PROCESS MAP), DAN PANDUAN LANGKAH DEMI LANGKAH\nDARI SAWAH PETANI HINGGA REAKTOR PABRIK PIROLISIS LENGKAP", 
                            font_size=11, bold=True, color_hex="0277BD", space_before=4, space_after=24, align=WD_ALIGN_PARAGRAPH.CENTER)

add_callout(doc, 
    "Dokumen ini memetakan seluruh arsitektur rantai pasok cerdas, protokol perangkat keras IoT edge, "
    "state machine kepemilikan komoditas, model matematika 11 engine analitik, dua alur distribusi utama (Path A dan Path B), "
    "siklus ekonomi sirkular 1-input ke 3-produk manufaktur, serta katalog lengkap skema basis data dan REST API "
    "yang terimplementasi di dalam repositori Bio-Chain Prototype.",
    title="📌 RINGKASAN EKSEKUTIF ARSITEKTUR SISTEM", alert_type="note")

add_styled_paragraph(doc, "Identitas Proyek:", font_size=10, bold=True, color_hex="1B5E20")
meta_data = [
    ["Inisiatif & Ajang", "ANGEL Innovation Hackathon 2026 — Track Sustainable Energy (Topik #4)"],
    ["Fokus Solusi", "Smart Bioenergy Feedstock Optimization & Circular Carbon Negative Supply Chain"],
    ["Entitas Pengguna", "6 Peran: Petani Padi, Pengepul KUD, Driver Armada, Pabrik Pirolisis, Auditor, Admin"],
    ["Basis Kode Sumber", "FastAPI Python 3.12/3.14, SQLAlchemy 2.0 Async, SciPy HiGHS LP Solver, Leaflet GIS, Chart.js"],
    ["Dual-Mode Storage", "Produksi: PostgreSQL 16 + Redis 7 + PgBouncer | Standalone/Edge: SQLite 3 WAL + aiosqlite"],
    ["Pusat Riset Industri", "PT Indmira Biochar Plant & Konsorsium Penggilingan Padi Sleman, D.I. Yogyakarta"]
]
add_styled_table(doc, ["Atribut", "Keterangan Spesifikasi"], meta_data, [2.0, 4.5])

doc.add_page_break()

# ==============================================================================
# BAB 1: PENDAHULUAN & ARSITEKTUR SISTEM
# ==============================================================================
add_heading_1(doc, "BAB 1: PENDAHULUAN, VISI STRATEGIS & ARSITEKTUR TINGKAT TINGGI")

add_heading_2(doc, "1.1 Latar Belakang & Urgensi Nasional")
add_styled_paragraph(doc, 
    "Indonesia memproduksi lebih dari 10,2 juta ton sekam padi setiap tahunnya dari sekitar 70.000 unit penggilingan padi "
    "yang tersebar di kawasan pedesaan. Namun demikian, lebih dari 60% sekam padi tersebut masih dimusnahkan melalui pembakaran "
    "terbuka di tepi sawah (open-field burning) atau dibuang ke aliran sungai. Praktik ini melepaskan partikel berbahaya PM2.5, "
    "karbon monoksida (CO), serta gas metana (CH₄) dengan potensi pemanasan global 28 kali lebih kuat daripada CO₂.")

add_styled_paragraph(doc, 
    "Di sisi lain, industri hilir bioenergi dan biochar nasional mengalami defisit bahan baku sekam berkualitas secara berkelanjutan. "
    "Hal ini disebabkan oleh tiga hambatan struktural: (1) densitas ruah sekam yang sangat rendah (100–120 kg/m³), membuat biaya "
    "pengangkutan membengkak bila tidak dioptimasi secara volume; (2) tingginya variasi kadar air (8%–35%) dan kontaminan tanah/kerikil; "
    "serta (3) ketiadaan sistem penelusuran (traceability) dan kepastian bagi hasil yang adil bagi petani produsen.")

add_styled_paragraph(doc, 
    "Bio-Chain v2 hadir sebagai platform rantai pasok terintegrasi berbasis AI, IoT edge, dan ekonomi sirkular tertutup. "
    "Platform ini mentransformasi limbah biomassa pertanian menjadi biochar berstandar SNI 8984:2021, bio-pellet energi kalori tinggi, "
    "dan bio-silika presipitasi kemurnian tinggi (>99% SiO₂), seraya mengembalikan porsi biochar teralokasi langsung ke dompet petani.")

add_heading_2(doc, "1.2 Landasan Regulasi & Kepatuhan Standar")
regulasi_data = [
    ["Perpres No. 110 Tahun 2025", "Penyelenggaraan Nilai Ekonomi Karbon (NEK)", "Engine ⑦ menghitung emisi dasar terhindarkan, emisi proses, dan sekuestrasi biochar stabil untuk sertifikasi SRN-PPI & IDX Carbon."],
    ["SNI 8984:2021", "Biochar untuk Pembenah Tanah", "Engine ② & ③ menjamin formulasi memenuhi kadar abu ≤ 25%, kadar air ≤ 15%, dan fixed carbon ≥ 15%."],
    ["IPCC 2006 Guidelines Tier 2", "AFOLU Biomass Combustion Methodology", "Faktor emisi CH₄ (2,7 g/kg) dan N₂O (0,07 g/kg) untuk baseline pembakaran terbuka di lahan persawahan."],
    ["ISO 14064-2:2019", "Validasi Penurunan Emisi GRK Proyek", "Log audit custody append-only mencatat geolokasi GPS, waktu, dan resi timbangan setiap kilogram sekam."],
    ["ISO 50006:2014 & Permen ESDM 13/2012", "Pengukuran Baseline & Kinerja Energi (IKE)", "Engine ⑩ menghitung Intensitas Konsumsi Energi (kWh/m²/bulan) dan SEC (kWh/ton) fasilitas pabrik."]
]
add_styled_table(doc, ["Standar / Regulasi", "Klasifikasi Regulasi", "Implementasi Nyata dalam Bio-Chain v2"], regulasi_data, [1.8, 1.8, 2.9])

add_heading_2(doc, "1.3 Enam Peran Pengguna (Role-Based Access Control / RBAC)")
add_styled_paragraph(doc, 
    "Sistem menerapkan keamanan berlapis dengan prinsip least-privilege RBAC. Setiap pengguna diidentifikasi menggunakan nomor telepon "
    "atau username yang terikat pada salah satu dari 6 peran fungsional:")

rbac_data = [
    ["🌾 Petani", "Pak Sugeng (Godean)", "petani_sugeng", "Lapor stok siap jual, pasang listing lelang B2B (skema jemput/antar), pantau status panen, pantau XP gamifikasi & saldo dompet biochar."],
    ["📦 Pengepul / KUD", "Pak Ahmad (KUD Sleman)", "pengepul_sleman", "Uji mutu proksimat NIR lapangan, timbang resmi, beli lelang petani (Bid Advisor), ajukan Delivery Request ke pabrik, pantau tagihan."],
    ["🚛 Driver Armada", "Budi Santoso (Armada 01)", "sopir_budi", "Menerima rute optimal CVRP, navigasi GIS interaktif, konfirmasi pickup dengan scan QR di penggilingan, antar muatan ke pabrik."],
    ["🏭 Pabrik Pirolisis", "PT Indmira Biochar Plant", "pabrik_indmira", "Dispatch rute truk, timbang jembatan terima, Inbound QC lot, negosiasi harga, eksekusi batch manufaktur sirkular, kredit dompet biochar, ESG."],
    ["🔍 Auditor ESG", "Auditor Independen", "auditor_esg", "Akses baca-saja (read-only): audit susut timbangan, indikator diskrepansi > toleransi, rekap neraca massa sirkular dari sawah ke sawah."],
    ["⚙️ Administrator", "Bio-Chain SuperAdmin", "admin", "Tata kelola pengguna, audit perubahan parameter asumsi (13 kelompok), metrik sistem global, pengujian 11 Engine di laboratorium komputasi."]
]
add_styled_table(doc, ["Ikon & Peran", "Persona Demo", "Akun Demo", "Kewenangan & Tanggung Jawab Operasional"], rbac_data, [1.3, 1.4, 1.1, 2.7])

add_heading_2(doc, "1.4 Dual-Mode Zero-Configuration Database & SRE High Availability")
add_styled_paragraph(doc, 
    "Bio-Chain v2 dirancang dengan kapabilitas *zero-configuration dual-mode database*. Pada lingkungan pengujian laptop atau "
    "komputer edge lapangan tanpa Docker, sistem secara otomatis mengaktifkan database lokal SQLite (`biochain.db`) melalui driver `aiosqlite`. "
    "Konfigurasi SQLite dioptimalkan dengan mode WAL (Write-Ahead Logging), `busy_timeout=5000ms`, dan `synchronous=NORMAL` guna mencegah kondisi `database is locked`.")

add_styled_paragraph(doc, 
    "Pada lingkungan produksi skala besar, sistem terhubung ke PostgreSQL 16 melalui connection pooler PgBouncer dan driver asinkron `asyncpg`. "
    "Arsitektur SRE mencakup:")
add_styled_paragraph(doc, "• Sliding-Window Rate Limiting: Membatasi lalu lintas API hingga 60 req/menit per IP/token menggunakan Redis atau memori lokal.", font_size=10, bold=False)
add_styled_paragraph(doc, "• Thread Pool CPU-Bound Offloading: Fungsi pemrosesan berat seperti hashing password PBKDF2 600.000 iterasi dan solver optimasi rute dieksekusi melalui `run_cpu()` untuk mencegah event loop asyncio membeku.", font_size=10, bold=False)
add_styled_paragraph(doc, "• Asynchronous Job Queue (HTTP 202 Accepted): Algoritma optimasi rute pada jaringan besar dialihkan ke antrean job asinkron dengan worker ARQ/Redis sehingga klien mendapatkan `job_id` tanpa mengalami HTTP timeout.", font_size=10, bold=False)

add_heading_2(doc, "1.5 Matriks 11 Engine Komputasi Bio-Chain")
engine_summary = [
    ["Engine ①", "Supply Forecaster", "Model gelombang cosinus ganda BPS Jawa", "Proyeksi ketersediaan sekam bulanan & 30 hari ke depan."],
    ["Engine ②", "Quality & Yield Scorer", "Kinetika pirolisis lambat Arrhenius & proksimat", "Penilaian 4 grade (A/B/C/Tolak), skor 0–100, estimasi rendemen."],
    ["Engine ③", "Blending Optimizer", "Linear Programming (SciPy HiGHS Solver)", "Formulasi campuran multi-biomassa biaya minimum dengan kendala mutu."],
    ["Engine ④", "Demand-Supply Matcher", "Mixed-Integer Linear Programming & Balance", "Pencocokan kebutuhan pabrik dengan stok penggilingan terdaftar."],
    ["Engine ⑤", "Route Optimizer", "CVRP Exact (Held-Karp+DP) / Clarke-Wright+ILS", "Minimasi jarak tempuh armada berbasis batasan volume truk (m³)."],
    ["Engine ⑥", "Incentive & Gamification", "Formula kuadrilateral XP & tier loyalitas", "Reward petani Grade A (+Rp 25/kg, bibit padi unggul, subsidi karung)."],
    ["Engine ⑦", "ESG Carbon Calculator", "IPCC 2006 Tier 2 & Perpres 110/2025 NEK", "Kalkulasi avoided open burning, emisi proses, dan sekuestrasi biochar."],
    ["Engine ⑧", "Feedstock Multi-Criteria", "TOPSIS MCDM Hwang & Yoon + Parikh HHV", "Pemeringkatan komparatif multi-biomassa sesuai produk tujuan."],
    ["Engine ⑨", "Waste-to-Energy Advisor", "Matriks kelayakan termokimia vs biokimia", "Rekomendasi teknologi konversi limbah (boiler, gasifikasi, pirolisis)."],
    ["Engine ⑩", "Industrial Energy Analytics", "ISO 50006:2014 & Permen ESDM No. 13/2012", "Analisis IKE, SEC kWh/ton, regresi baseline, deteksi anomali robust-Z."],
    ["Engine ⑪", "Factory Economics & Netback", "1 Input → 3 Output, CVP Model & Netback", "Mass balance pabrik, alokasi biaya bersama NRV, harga beli sekam."]
]
add_styled_table(doc, ["Engine", "Nama Mesin Komputasi", "Algoritma & Metodologi Inti", "Fungsi & Luaran Komputasi"], engine_summary, [1.1, 1.6, 2.0, 1.8])

doc.add_page_break()

# ==============================================================================
# BAB 2: PERANGKAT KERAS IOT EDGE
# ==============================================================================
add_heading_1(doc, "BAB 2: DESAIN PERANGKAT KERAS IOT EDGE: BIO-CHAIN SCOUT PRO")

add_styled_paragraph(doc, 
    "Untuk memastikan keabsahan data mutu dan berat di tingkat penggilingan padi pedesaan—tempat di mana manipulasi kadar air "
    "atau penambahan pasir/sekam basah kerap terjadi—dikembangkan instrumen lapangan terintegrasi bernama **Bio-Chain Scout Pro**.")

add_code_block(doc, 
"""               ┌─────────────────────────────────────────────────────────┐
               │              Bio-Chain Scout Pro (IoT Edge)             │
               │         ESP32-S3 Dual-Core 240 MHz + 8MB PSRAM          │
               └────────────────────────────┬────────────────────────────┘
                                            │
         ┌──────────────────────────────────┼──────────────────────────────────┐
         │                                  │                                  │
┌────────▼────────┐                ┌────────▼────────┐                ┌────────▼────────┐
│ Probe Optik NIR │                │  Load Cell 500kg│                │ Modul Telemetri │
│  900 - 1700 nm  │                │  ADC HX711 24bit│                │ 4G LTE + GPS    │
│(Kadar Air/Abu/VM│                │ (Penimbangan kg)│                │(Quectel / NEO6M)│
└────────┬────────┘                └────────┬────────┘                └────────┬────────┘
         │                                  │                                  │
         └──────────────────────────────────┼──────────────────────────────────┘
                                            │
                                   ┌────────▼────────┐
                                   │ Printer Thermal │
                                   │ Tiket Label QR  │
                                   │  ESC/POS 58 mm  │
                                   └─────────────────┘""")

add_heading_2(doc, "2.1 Spesifikasi Rinci Hardware")
hw_spec = [
    ["Mikrokontroler Utama", "Espressif ESP32-S3 Dual-Core Xtensa LX7 @ 240 MHz, 8MB Octal PSRAM, 16MB Flash, Wi-Fi 802.11 b/g/n, Bluetooth 5 (LE)."],
    ["Sensor Spektroskopi NIR", "Sensor reflektansi Near-Infrared 900 nm – 1700 nm; waktu pembacaan < 3 detik; mengukur kadar air (% wet basis), estimasi abu silika, dan volatile matter."],
    ["Timbangan Digital Presisi", "Load Cell S-Type Stainless Steel kapasitas 500 kg dengan modul ADC 24-bit HX711 ultra-low noise; akurasi kalibrasi ±0.1 kg."],
    ["Modul Geospasial GPS", "Quectel L76K / u-blox NEO-6M terhubung antena keramik aktif; akurasi posisi horizontal < 2,5 meter CEP; penandaan geolokasi anti-spoofing."],
    ["Modem Seluler 4G LTE", "SIMCom SIM7600E (Cat-1 dengan fallback 2G/GPRS) untuk transmisi telemetri otomatis ke REST API server Bio-Chain."],
    ["Printer Label Thermal", "Unit cetak thermal terintegrasi 58mm ESC/POS 203 DPI; mencetak tiket barcode/QR Code tahan air berisi data identitas batch sekam."],
    ["Catu Daya & Baterai", "Baterai LiFePO4 internal 12.8V 6000 mAh (ketahanan 16 jam pengoperasian aktif); kompatibel dengan panel surya portabel 50W."]
]
add_styled_table(doc, ["Sub-Sistem", "Spesifikasi Komponen Lapangan"], hw_spec, [2.0, 4.5])

add_heading_2(doc, "2.2 Protokol Penomoran Resi Kriptografis Unik")
add_styled_paragraph(doc, 
    "Setiap serah-terima fisik komoditas di lapangan menerbitkan nomor resi unik terstandarisasi dengan format:")
add_code_block(doc, "TRX-[KODE_PENGIRIM]-[KODE_PENERIMA]-[YYMM]-[NOMOR_URUT_4_DIGIT]\nContoh: TRX-PET0001-KUD0002-2610-0042")
add_styled_paragraph(doc, 
    "Penomoran urut dikelola secara atomik di dalam basis data melalui tabel `trx_sequences` menggunakan perintah SQL "
    "`INSERT ... ON CONFLICT (sender_code, receiver_code, yymm) DO UPDATE SET last_seq = trx_sequences.last_seq + 1 RETURNING last_seq`. "
    "Mekanisme ini menjamin tidak ada nomor resi ganda meskipun terjadi transaksi paralel.")

add_heading_2(doc, "2.3 Protokol Idempotensi Antrean Offline-First")
add_styled_paragraph(doc, 
    "Di banyak kawasan persawahan, konektivitas seluler sering mengalami blank spot. Bio-Chain Scout Pro menerapkan arsitektur *offline-first*:")
add_styled_paragraph(doc, "1. Setiap penimbangan lokal di-generate dengan UUID v4 unik sebagai `client_event_id` beserta stempel waktu lokal `client_recorded_at`.", font_size=10)
add_styled_paragraph(doc, "2. Transaksi disimpan di antrean memori flash internal ESP32.", font_size=10)
add_styled_paragraph(doc, "3. Saat modem mendeteksi sinyal internet kembali, antrean disinkronkan ke server secara otomatis.", font_size=10)
add_styled_paragraph(doc, "4. Server memeriksa `find_replay(client_event_id)`. Jika data sudah tercatat akibat spam-retry jaringan, server mengembalikan status sukses (200/201 replay) tanpa menciptakan duplikasi data (HTTP 409 idempotency safeguard).", font_size=10)

doc.add_page_break()

# ==============================================================================
# BAB 3: STATE MACHINE & CHAIN-OF-CUSTODY
# ==============================================================================
add_heading_1(doc, "BAB 3: STATE MACHINE & CHAIN-OF-CUSTODY (RANTAI KEPEMILIKAN)")

add_styled_paragraph(doc, 
    "Prinsip utama transparansi Bio-Chain v2 adalah *Chain-of-Custody* (rantai pengawasan kepemilikan fisik dan hukum). "
    "Setiap kilogram sekam padi yang bergerak dari sawah hingga menjadi biochar diawasi oleh mesin status tertutup (finite state machine).")

add_code_block(doc,
"""       [Petani: Lapor Stok / Menang Lelang]
                         │
                         ▼
                  ┌──────────────┐
                  │   REPORTED   │ ◄─── Estimasi petani (quantity_kg)
                  └──────┬───────┘
                         │
      ┌──────────────────┴──────────────────┐
      │ (Pengepul: Uji Mutu & Timbang)      │ (Pengepul: Tolak Mutu)
      ▼                                     ▼
┌──────────────┐                     ┌──────────────┐
│   VERIFIED   │                     │   REJECTED   │
└──────┬───────┘                     └──────────────┘
       │
       ├────────────────────────────────────┐
       │ (Path A: Driver Scan QR Jemput)    │ (Path B: Pengepul Kirim Mandiri via DR)
       ▼                                    │
┌──────────────┐                            │
│  COLLECTED   │                            │
│ (IN_TRANSIT) │                            │
└──────┬───────┘                            │
       │                                    │
       ├────────────────────────────────────┘
       │ (Pabrik: Timbang Terima Jembatan Timbang / Inbound QC)
       ▼
┌──────────────┐
│  DELIVERED   │ ◄─── Timbangan otoritatif pabrik (received_kg)
└──────┬───────┘      Audit Susut (shrinkage_pct) & Discrepancy Flag
       │
       │ (Pabrik: Reaktor Pirolisis & Manufaktur Sirkular)
       ▼
┌──────────────┐
│  CONVERTED   │ ───► Kredit Dompet Biochar Petani (Presisi Gram)
└──────────────┘""")

add_heading_2(doc, "3.1 Matriks Otorisasi Transisi Status & Role Enforcement")
add_styled_paragraph(doc, 
    "Guna mencegah manipulasi data (misalnya supir menandai barang telah selesai sebelum diambil, atau admin memanipulasi timbangan), "
    "perubahan status dikunci oleh matriks otorisasi `TRANSITIONS` di lapisan `app/services/custody.py`:")

trans_data = [
    ["REPORTED", "VERIFIED", "PENGEPUL", "Pengepul menguji proksimat dan menimbang sekam di penggilingan."],
    ["REPORTED", "REJECTED", "PENGEPUL", "Pengepul menolak sekam basah / terkontaminasi parah sebelum dimuat."],
    ["VERIFIED", "COLLECTED", "DRIVER", "Supir armada mengonfirmasi penjemputan fisik dengan memindai tiket QR."],
    ["COLLECTED", "DELIVERED", "PABRIK", "Pabrik menimbang truk di jembatan timbang resmi (Path A)."],
    ["COLLECTED", "REJECTED", "PABRIK", "Pabrik menolak muatan truk yang rusak/basah saat tiba di gerbang."],
    ["VERIFIED", "DELIVERED", "PABRIK", "Pabrik meloloskan Inbound QC atas sekam yang diantar mandiri (Path B)."],
    ["VERIFIED", "REJECTED", "PABRIK", "Pabrik menolak lot pengiriman Delivery Request saat Inbound QC."],
    ["DELIVERED", "CONVERTED", "PABRIK", "Sekam dimasukkan ke dalam reaktor pirolisis & diolah menjadi produk."]
]
add_styled_table(doc, ["Status Asal", "Status Tujuan", "Peran Berhak", "Penjelasan Aksi Lapangan"], trans_data, [1.3, 1.3, 1.2, 2.7])

add_callout(doc, 
    "Perhatikan bahwa peran ADMINISTRATOR sengaja TIDAK diberikan hak untuk melakukan transisi status timbangan komoditas. "
    "Ini adalah implementasi prinsip akuntansi 'Separation of Duties' (Pemisahan Tugas): administrator sistem tidak boleh "
    "mengintervensi data fisik penimbangan dan transaksi keuangan demi mencegah benturan kepentingan dan manipulasi audit.",
    title="🔒 PRINSIP PEMISAHAN TUGAS (SEPARATION OF DUTIES)", alert_type="warning")

add_heading_2(doc, "3.2 Transisi Atomik Compare-and-Swap (CAS)")
add_styled_paragraph(doc, 
    "Setiap perintah pembaruan status dieksekusi menggunakan pola Compare-and-Swap (CAS) level basis data:")
add_code_block(doc, 
"""UPDATE harvests 
SET status = :to_status, 
    version = version + 1, 
    updated_at = :now, ...
WHERE id = :harvest_id 
  AND status = :from_status;""")
add_styled_paragraph(doc, 
    "Jika dua pengguna atau dua klik spam terjadi bersamaan pada data yang sama, salah satu request akan menghasilkan `rowcount = 0`. "
    "Sistem langsung memicu pengecualian `TransitionConflict` (HTTP 409 Conflict) secara aman tanpa merusak konsistensi data.")

add_heading_2(doc, "3.3 Log Audit Append-Only Imutabel")
add_styled_paragraph(doc, 
    "Semua perpindahan fisik dan perubahan data dicatat pada tabel audit *append-only* (hanya tambah baris, tanpa UPDATE atau DELETE):")
add_styled_paragraph(doc, "1. `custody_events`: Merekam riwayat perpindahan tangan komoditas, lokasi GPS, waktu perangkat, foto serah-terima, dan kode verifikasi resi.", font_size=10)
add_styled_paragraph(doc, "2. `conversion_inputs`: Merekam panen petani mana saja yang dikonsumsi ke dalam batch pirolisis tertentu beserta porsi persentasenya.", font_size=10)
add_styled_paragraph(doc, "3. `biochar_ledger`: Buku besar saldo dompet biochar petani yang mencatat alokasi kredit biochar masuk dan transaksi penebusan pupuk.", font_size=10)
add_styled_paragraph(doc, "4. `settlement_events`: Merekam seluruh jejak perubahan harga, revisi tagihan, dan bukti transfer pembayaran pabrik ke pengepul.", font_size=10)

doc.add_page_break()

# ==============================================================================
# BAB 4: PETA ALUR KOMPREHENSIF DUA JALUR PASOKAN
# ==============================================================================
add_heading_1(doc, "BAB 4: PETA ALUR KOMPREHENSIF: DUA JALUR PASOKAN UTAMA")

add_styled_paragraph(doc, 
    "Bio-Chain v2 mengakomodasi dua model bisnis rantai pasok nyata di lapangan:")
add_styled_paragraph(doc, 
    "1. **Path A (Jalur Logistik Rute Armada Terpadu Pabrik)**: Model pasokan terencana di mana pabrik mengorkestrasi armada truknya "
    "sendiri untuk menjemput sekam dari berbagai penggilingan padi yang telah diverifikasi oleh pengepul lokal.", font_size=10.5, bold=True)
add_styled_paragraph(doc, 
    "2. **Path B (Jalur Pasar B2B Lelang & Delivery Request)**: Model pasar dinamis berbasis mekanisme lelang dan kontrak pengadaan. "
    "Petani memasang listing stok, pengepul menawar berdasarkan optimasi biaya logistik marginal, dan pengepul mengantar langsung pasokan besar ke gerbang pabrik.", font_size=10.5, bold=True)

add_heading_2(doc, "4.1 Matriks Perbandingan Arsitektur: Path A vs Path B")
path_comp = [
    ["Titik Awal Alur", "Petani lapor stok langsung via form 1-klik.", "Petani pasang listing lelang di Bursa B2B."],
    ["Penetapan Harga Petani", "Harga dasar acuan × pengali mutu hasil uji proksimat.", "Harga kesepakatan lelang (Reserve Price vs Tawaran Pengepul)."],
    ["Skema Pengambilan", "Wajib penjemputan armada pabrik di penggilingan.", "Pilihan Incoterms: 'Jemput' (EXW) atau 'Antar' (DAP)."],
    ["Peran Armada Driver", "Driver armada pabrik menjalankan rute multi-stop CVRP.", "Pengepul menggunakan armada mandiri / sewa lokal."],
    ["Pintu Masuk Pabrik", "Langsung ke jembatan timbang pabrik (`/factory/receive`).", "Melalui negosiasi Delivery Request & Inbound QC (`/factory/qc`)."],
    ["Pemicu Tagihan Pengepul", "Otomatis dibuat saat timbang terima rute (`settle_route`).", "Otomatis dibuat saat lot lulus Inbound QC (`settle_qc`)."],
    ["Penentuan Kadar Air Lot", "Diambil dari hasil uji timbang pengepul di lapangan.", "Diuji ulang di laboratorium Inbound QC gerbang pabrik."],
    ["Alokasi Kembali Biochar", "Proporsional timbangan terima via konversi batch.", "Proporsional timbangan terima via manufaktur batch sirkular."]
]
add_styled_table(doc, ["Dimensi Perbandingan", "Path A: Jalur Rute Armada Pabrik", "Path B: Pasar Lelang & Delivery Request"], path_comp, [1.8, 2.3, 2.4])

add_heading_2(doc, "4.2 Diagram Alur Proses Holistik (End-to-End Process Map)")
add_code_block(doc,
"""========================================================================================
             DIAGRAM PROSES END-TO-END DARI PETANI HINGGA PABRIK PIROLISIS
========================================================================================

                 [🌾 PETANI: Sawah & Penggilingan Padi Sleman]
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            │                                                     │
   [JALUR A: Lapor Rutin]                                [JALUR B: Bursa B2B Lelang]
            │                                                     │
     POST /farmer/harvest                                  POST /farmer/listings
            │                                                     │
   (Status: REPORTED)                                     (Status: OPEN / PARTIAL)
            │                                                     │
            │                                              POST /collector/bids
            │                                             (AI: Bid Advisor Netback)
            │                                                     │
            │                                              POST /farmer/.../accept
            │                                                     │
            ├─────────────────────────────────────────────────────┘
            │
            ▼
 [📦 PENGEPUL KUD: Uji Cepat Scout Pro]
  POST /collector/verify
  - Input: Air (%), Abu (%), VM (%), FC (%), Kontaminasi (%)
  - Engine ② Quality Scorer: Grade A/B/C/Tolak, Skor Mutu, Total Bayar Petani
  (Status beralih: VERIFIED)
            │
            ├─────────────────────────────────────────────────────┐
            │                                                     │
 [PATH A: Logistik Armada Pabrik]                     [PATH B: Pengadaan B2B Pabrik]
            │                                                     │
  POST /factory/dispatch                               POST /collector/delivery-requests
  - Engine ⑤ CVRP Route Optimizer                     (Melampirkan panen terverifikasi)
  - Generate Route & RouteStops terurut                          │
            │                                          POST /factory/.../respond
            ▼                                         (Negosiasi Putaran Harga & Jadwal)
 [🚛 DRIVER ARMADA: Pickup Lapangan]                              │
  POST /driver/start-route                             (Status ajuan: ACCEPTED)
  POST /driver/confirm-pickup                                     │
  - Scan QR Tiket Penggilingan                                    ▼
  (Status beralih: COLLECTED)                         [PENGIRIMAN MANDIRI PENGEPUL]
  POST /driver/complete-route                                     │
            │                                                     ▼
            │                                        [🏭 GERBANG PABRIK: INBOUND QC]
            │                                         POST /factory/qc
            │                                         - Timbang Bruto & Tara (Netto)
            │                                         - Uji Proksimat Laboratorium
            │                                         - Penyesuaian Harga Basis Kering
            │                                         - Lot Diterima & Terbit Tagihan QC
            │                                         (Status panen terlampir: DELIVERED)
            ▼                                                     │
 [🏭 JEMBATAN TIMBANG PABRIK]                                     │
  POST /factory/receive                                           │
  - Timbangan Jembatan Resmi (received_kg)                        │
  - Audit Susut: (verified − received) ÷ verified                 │
  - Flagging Diskrepansi bila susut > toleransi                   │
  - Otomatis Terbit Tagihan Rute Pengepul                         │
  (Status beralih: DELIVERED)                                     │
            │                                                     │
            └──────────────────────────┬──────────────────────────┘
                                       │
                                       ▼
                     [🏭 REAKTOR MANUFAKTUR PIROLISIS]
                      POST /factory/batches (Engine ⑪)
                      - Konsumsi Lot Bahan Baku Sekam
                      - 3 Produk: Bio-Pellet, Biochar, Bio-Silika
                      - 5 Losses: Air, Volatil/Syngas, Gas, Residu, Susut
                      - Verifikasi Mass Balance Closure (< 2% error)
                      - Alokasi Biaya Bersama (Metode NRV)
                                       │
                                       ▼
                     [🔄 EKONOMI SIRKULAR: PENGEMBALIAN]
                      Largest Remainder Algorithm (Presisi Gram)
                      - Alokasi Biochar dialirkan kembali ke Petani
                      - Tercatat pada Biochar Digital Wallet Petani
                      - Petani menebus biochar untuk pembenah tanah sawah!""")

doc.add_page_break()

# ==============================================================================
# BAB 5: STEP-BY-STEP DETAIL PATH A
# ==============================================================================
add_heading_1(doc, "BAB 5: PANDUAN LANGKAH DEMI LANGKAH PATH A (RUTE ARMADA PABRIK)")

add_styled_paragraph(doc, 
    "Path A merupakan jalur pasokan utama untuk kemitraan penggilingan terdaftar di mana pabrik menanggung "
    "seluruh biaya dan koordinasi transportasi armada.")

add_heading_2(doc, "Langkah A.1: Petani Melaporkan Stok Siap Jual")
add_styled_paragraph(doc, "• Aktor: Petani (🌾 Pak Sugeng).", font_size=10.5, bold=True)
add_styled_paragraph(doc, "• Antarmuka / API: Endpoint `POST /api/v1/farmer/harvest`.", font_size=10.5)
add_styled_paragraph(doc, 
    "• Deskripsi Proses: Petani memilih penggilingan padi tempat sekam berada, memasukkan estimasi berat sekam (misal: 2.500 kg), "
    "mengunggah foto tumpukan karung, dan menyertakan `client_event_id` unik dari perangkat. Sistem membuat baris baru di tabel `harvests` "
    "berstatus `REPORTED`, menghasilkan kode tiket QR resmi (contoh: `BIO-A4B7C9D2`), dan mencatat `CustodyEvent` tahap `farmer_report`.")

add_heading_2(doc, "Langkah A.2: Pengepul Melakukan Uji Mutu & Timbang Resmi")
add_styled_paragraph(doc, "• Aktor: Pengepul KUD (📦 Pak Ahmad).", font_size=10.5, bold=True)
add_styled_paragraph(doc, "• Antarmuka / API: Endpoint `POST /api/v1/collector/verify`.", font_size=10.5)
add_styled_paragraph(doc, 
    "• Deskripsi Proses: Pengepul tiba di penggilingan membawa instrumen *Bio-Chain Scout Pro*. Karung sekam diletakkan di atas timbangan "
    "load cell digital dan probe spektroskopi NIR ditancapkan. Nilai pembacaan dimasukkan ke form:")
add_styled_paragraph(doc, "   - Berat Timbang Resmi: 2.450 kg (angka otoritatif untuk dasar pembayaran ke petani).", font_size=10)
add_styled_paragraph(doc, "   - Kadar Air: 11,5% (ideal ≤ 12%), Kadar Abu: 17,2%, VM: 65,0%, FC: 16,3%, Kontaminasi: 1,0%.", font_size=10)
add_styled_paragraph(doc, 
    "• Eksekusi Komputasi: Engine ② secara otomatis menetapkan Grade A, Skor Mutu 94,8, pengali harga 1.10x. Total pembayaran ke petani "
    "dihitung: 2.450 kg × Rp 450/kg × 1,10 = Rp 1.212.750. Status harvest beralih atomik ke `VERIFIED`, dan diterbitkan kode resi `TRX-PET0001-KUD0002-2610-0001`.")

add_heading_2(doc, "Langkah A.3: Pabrik Merencanakan Rute Penjemputan Armada")
add_styled_paragraph(doc, "• Aktor: Operator Pabrik (🏭 PT Indmira).", font_size=10.5, bold=True)
add_styled_paragraph(doc, "• Antarmuka / API: Endpoint `POST /api/v1/factory/dispatch`.", font_size=10.5)
add_styled_paragraph(doc, 
    "• Deskripsi Proses: Pabrik memilih daftar panen berstatus `VERIFIED` yang lokasinya saling berdekatan. Sistem memeriksa constraint:")
add_styled_paragraph(doc, "   - Panen tidak boleh sedang terikat pada Delivery Request aktif.", font_size=10)
add_styled_paragraph(doc, "   - Panen tidak boleh sedang dijadwalkan pada rute lain yang aktif.", font_size=10)
add_styled_paragraph(doc, 
    "• Eksekusi Komputasi: Engine ⑤ mengelompokkan dan mengurutkan perhentian truk dengan batas volume 30 m³. Dibuat record `routes` (status `PLANNED`) "
    "dan serangkaian `route_stops` terurut. Armada ditugaskan ke driver (misal: Sopir Budi).")

add_heading_2(doc, "Langkah A.4: Driver Menjalankan Rute & Memindai QR Pickup")
add_styled_paragraph(doc, "• Aktor: Supir Armada (🚛 Budi Santoso).", font_size=10.5, bold=True)
add_styled_paragraph(doc, "• Antarmuka / API: `POST /api/v1/driver/start-route` dan `POST /api/v1/driver/confirm-pickup`.", font_size=10.5)
add_styled_paragraph(doc, 
    "• Deskripsi Proses: Driver menekan tombol 'Mulai Rute' (status rute berubah menjadi `IN_PROGRESS`). Driver mengemudikan truk ke tiap perhentian penggilingan. "
    "Di setiap titik, driver mencocokkan karung fisik, memindai tiket QR panen, memasukkan perkiraan tonase muatan, dan mengambil foto bukti muat. "
    "Sistem mencatat koordinat GPS kedatangan driver, menandai `qr_scanned = True`, dan mengalihkan status harvest dari `VERIFIED` menjadi `COLLECTED` (`IN_TRANSIT`).")

add_heading_2(doc, "Langkah A.5: Driver Menyelesaikan Pengiriman ke Pabrik")
add_styled_paragraph(doc, "• Aktor: Supir Armada (🚛 Budi Santoso).", font_size=10.5, bold=True)
add_styled_paragraph(doc, "• Antarmuka / API: Endpoint `POST /api/v1/driver/complete-route`.", font_size=10.5)
add_styled_paragraph(doc, 
    "• Deskripsi Proses: Setelah seluruh perhentian penggilingan diselesaikan dan truk tiba di depot pabrik, driver mengonfirmasi penyelesaian rute. "
    "Sistem memvalidasi bahwa tidak ada stop yang tertinggal, lalu memperbarui status rute menjadi `COMPLETED`.")

add_heading_2(doc, "Langkah A.6: Penerimaan & Timbang Jembatan Timbang Pabrik")
add_styled_paragraph(doc, "• Aktor: Operator Pabrik (🏭 PT Indmira).", font_size=10.5, bold=True)
add_styled_paragraph(doc, "• Antarmuka / API: Endpoint `POST /api/v1/factory/receive`.", font_size=10.5)
add_styled_paragraph(doc, 
    "• Deskripsi Proses: Truk melintasi jembatan timbang resmi pabrik. Berat bersih muatan ditimbang secara otoritatif (`received_kg`, misal: 2.420 kg). "
    "Sistem menghitung persentase susut pengangkutan:")
add_code_block(doc, "susut_kg = verified_kg - received_kg = 2.450 - 2.420 = 30 kg\nsusut_pct = (30 / 2.450) * 100 = 1,22%")
add_styled_paragraph(doc, 
    "Karena susut 1,22% berada di bawah batas toleransi parameter (5,0%), data dinyatakan wajar (`discrepancy_flag = False`). "
    "Status harvest dialihkan menjadi `DELIVERED`.")

add_heading_2(doc, "Langkah A.7: Otomatisasi Tagihan Pembayaran Pengepul (Settlement Rute)")
add_styled_paragraph(doc, "• Aktor: Sistem Keuangan Otomatis & Operator Pabrik.", font_size=10.5, bold=True)
add_styled_paragraph(doc, "• Implementasi: Fungsi `settle_route()` di `app/services/factory_ops.py`.", font_size=10.5)
add_styled_paragraph(doc, 
    "• Deskripsi Proses: Sistem secara otomatis membuat rekaman kewajiban pembayaran pabrik ke pengepul di tabel `collector_settlements` (sumber 'rute'). "
    "Berat bersih bayar dihitung dari berat terima dikurangi kontaminan: 2.420 kg × (1 - 0,01) = 2.395,8 kg. "
    "Jika pabrik belum memasukkan harga khusus, sistem mengaktifkan Engine ⑪ untuk menghitung harga netback rekomendasi. "
    "Status tagihan diset ke `menunggu_harga` atau `terutang` dan siap dibayarkan melalui transfer bank.")

doc.add_page_break()

# ==============================================================================
# BAB 6: STEP-BY-STEP DETAIL PATH B
# ==============================================================================
add_heading_1(doc, "BAB 6: PANDUAN LANGKAH DEMI LANGKAH PATH B (PASAR LELANG & DELIVERY REQUEST)")

add_styled_paragraph(doc, 
    "Path B dirancang untuk perdagangan sekam terbuka, di mana petani memiliki daya tawar untuk menentukan harga batas bawah (reserve price) "
    "dan pengepul berkompetisi memberikan penawaran terbaik dengan bantuan algoritma logistik cerdas.")

add_heading_2(doc, "Langkah B.1: Pemasangan Listing Stok di Bursa B2B oleh Petani")
add_styled_paragraph(doc, "• Aktor: Petani (🌾 Pak Sugeng).", font_size=10.5, bold=True)
add_styled_paragraph(doc, "• Antarmuka / API: Endpoint `POST /api/v1/farmer/listings`.", font_size=10.5)
add_styled_paragraph(doc, 
    "• Deskripsi Proses: Petani mempublikasikan stok sekam yang tersedia (misal: 10.000 kg). Petani menentukan skema penyerahan yang diizinkan (Incoterms 2020):")
add_styled_paragraph(doc, "   - Skema 'Jemput' (setara EXW): Pengepul mengambil di lokasi petani; harga batas minimum (reserve price) misal Rp 420/kg.", font_size=10)
add_styled_paragraph(doc, "   - Skema 'Antar' (setara DAP): Petani mengantar ke gudang pengepul; harga batas minimum misal Rp 470/kg (termasuk ongkos angkut).", font_size=10)
add_styled_paragraph(doc, "Sistem membuat baris di `stock_listings` dengan status `open` dan `remaining_kg = 10.000`.")

add_heading_2(doc, "Langkah B.2: Analisis Pasar & Penasihat Tawaran Pengepul (AI Bid Advisor)")
add_styled_paragraph(doc, "• Aktor: Pengepul KUD (📦 Pak Ahmad).", font_size=10.5, bold=True)
add_styled_paragraph(doc, "• Antarmuka / API: `GET /api/v1/collector/market` dan `POST /api/v1/collector/bid-advisor`.", font_size=10.5)
add_styled_paragraph(doc, 
    "• Eksekusi Komputasi: Pengepul melihat daftar stok yang tersedia. Untuk menentukan tawaran yang tepat, pengepul menjalankan Engine ⑤ & ⑪ melalui Bid Advisor:")
add_code_block(doc, "tawaran_maksimum = harga_jual_ke_pabrik - biaya_logistik_marginal_per_kg - target_margin\n"
                    "biaya_logistik_marginal = [km(rute dengan listing) - km(rute tanpa listing)] * Rp_per_km / kg")
add_styled_paragraph(doc, 
    "Sistem menjalankan solver CVRP menghitung selisih jarak penyisipan rute (insertion cost). Bila harga jual ke pabrik Rp 600/kg, "
    "biaya logistik marginal Rp 45/kg, dan margin pengepul Rp 60/kg, maka batas tawaran maksimal adalah Rp 495/kg. "
    "Bid Advisor merekomendasikan solusi tawar-menawar Nash (Nash Bargaining Solution): titik tengah antara batas petani (Rp 420) dan batas atas (Rp 495) yaitu Rp 458/kg.")

add_heading_2(doc, "Langkah B.3: Pengajuan Tawaran Resmi oleh Pengepul")
add_styled_paragraph(doc, "• Aktor: Pengepul KUD (📦 Pak Ahmad).", font_size=10.5, bold=True)
add_styled_paragraph(doc, "• Antarmuka / API: Endpoint `POST /api/v1/collector/bids`.", font_size=10.5)
add_styled_paragraph(doc, 
    "• Deskripsi Proses: Pengepul memasukkan tawaran resmi untuk kuantitas 5.000 kg pada skema 'jemput' seharga Rp 460/kg dengan rencana jemput tanggal 12 Oktober 2026. "
    "Sistem mencatat baris di tabel `bids` berstatus `active`.")

add_heading_2(doc, "Langkah B.4: Seleksi & Penerimaan Tawaran oleh Petani")
add_styled_paragraph(doc, "• Aktor: Petani (🌾 Pak Sugeng).", font_size=10.5, bold=True)
add_styled_paragraph(doc, "• Antarmuka / API: `GET /api/v1/farmer/listings/{id}/bids` dan `POST /api/v1/farmer/listings/{id}/accept`.", font_size=10.5)
add_styled_paragraph(doc, 
    "• Deskripsi Proses: Petani membuka daftar tawaran yang masuk. Sistem secara otomatis menghitung *Net Revenue* ke petani. "
    "Untuk tawaran skema 'antar', sistem mengurangkan estimasi ongkos bensin dan sewa pikap petani. Tawaran dengan nilai bersih tertinggi diberi label `highest_net`.")
add_styled_paragraph(doc, 
    "Petani menerima tawaran KUD Sleman untuk 5.000 kg. Transaksi dieksekusi secara atomik (CAS):")
add_styled_paragraph(doc, "   1. Kolom `remaining_kg` listing dikurangi 5.000 kg (tersisa 5.000 kg, status listing menjadi `partially_awarded`).", font_size=10)
add_styled_paragraph(doc, "   2. Status tawaran dikunci menjadi `accepted`.", font_size=10)
add_styled_paragraph(doc, "   3. Terbentuk objek `harvest` baru berstatus `REPORTED` dengan ikatan kontrak `agreed_price_per_kg = 460` dan `delivery_scheme = 'jemput'`.", font_size=10)

add_heading_2(doc, "Langkah B.5: Pengepul Menimbang & Memverifikasi Lot")
add_styled_paragraph(doc, "• Aktor: Pengepul KUD (📦 Pak Ahmad).", font_size=10.5, bold=True)
add_styled_paragraph(doc, "• Antarmuka / API: Endpoint `POST /api/v1/collector/verify`.", font_size=10.5)
add_styled_paragraph(doc, 
    "• Deskripsi Proses: Pengepul mengambil sekam di lokasi petani, menimbang secara resmi, dan menguji proksimat. "
    "Karena ini adalah panen hasil lelang, harga tidak lagi dikalikan faktor mutu umum melainkan menggunakan harga kontrak lelang (Rp 460/kg). "
    "Status panen beralih menjadi `VERIFIED`.")

add_heading_2(doc, "Langkah B.6: Pengepul Menyusun Delivery Request (DR) ke Pabrik")
add_styled_paragraph(doc, "• Aktor: Pengepul KUD (📦 Pak Ahmad).", font_size=10.5, bold=True)
add_styled_paragraph(doc, "• Antarmuka / API: Endpoint `POST /api/v1/collector/delivery-requests`.", font_size=10.5)
add_styled_paragraph(doc, 
    "• Deskripsi Proses: Pengepul mengumpulkan sejumlah lot panen terverifikasi yang telah dibeli dari petani dan mengajukan kontrak pengiriman ke pabrik:")
add_styled_paragraph(doc, "   - Kuantitas Pengiriman: 15.000 kg sekam.", font_size=10)
add_styled_paragraph(doc, "   - Estimasi Mutu: Kadar air 11,0%, Abu 18,0%, Grade A.", font_size=10)
add_styled_paragraph(doc, "   - Tanggal & Harga Usulan: Rencana kirim 15 Oktober 2026, Harga usulan Rp 620/kg.", font_size=10)
add_styled_paragraph(doc, "   - Lampiran Panen (`harvest_ids`): Melampirkan ID panen petani agar hak dompet biochar mereka terlacak.", font_size=10)
add_styled_paragraph(doc, "Sistem mengunci panen-panen tersebut (`delivery_request_id = dr.id`) sehingga tidak dapat dijadwalkan ke rute lain. Status DR: `SUBMITTED`.")

add_heading_2(doc, "Langkah B.7: Negosiasi B2B Pabrik-Pengepul")
add_styled_paragraph(doc, "• Aktor: Operator Pabrik & Pengepul KUD.", font_size=10.5, bold=True)
add_styled_paragraph(doc, "• Antarmuka / API: `POST /delivery-requests/{id}/respond`.", font_size=10.5)
add_styled_paragraph(doc, 
    "• Deskripsi Proses: Pabrik memeriksa ajuan. Pabrik dapat menerima langsung (`accept`), mengajukan tawaran balik (`counter`, misal: menyetujui harga Rp 600/kg pada tanggal 16 Oktober), "
    "atau menolak (`reject`). Negosiasi dapat berlangsung hingga batas parameter `max_negotiation_rounds` (default 5 putaran). "
    "Setiap aksi dicatat pada `negotiation_events`. Ketika disepakati, status menjadi `ACCEPTED`.")

add_heading_2(doc, "Langkah B.8: Inbound Quality Control (QC) di Gerbang Pabrik")
add_styled_paragraph(doc, "• Aktor: Petugas QC Pabrik (🏭 Inspector).", font_size=10.5, bold=True)
add_styled_paragraph(doc, "• Antarmuka / API: Endpoint `POST /api/v1/factory/qc`.", font_size=10.5)
add_styled_paragraph(doc, 
    "• Deskripsi Proses: Truk pengepul tiba di pabrik. Dilakukan penimbangan bruto dan tara untuk memperoleh berat bersih (netto):")
add_code_block(doc, "Bruto: 22.450 kg, Tara: 7.500 kg ==> Netto (net_kg): 14.950 kg")
add_styled_paragraph(doc, 
    "Sampel sekam diuji proksimat di lab pabrik: Kadar air aktual 12,5%, Abu 17,8%, VM 64,5%, FC 16,7%, Kontaminasi 0,8%. "
    "Sistem melakukan penyesuaian harga kontrak berdasarkan basis bahan kering (dry basis adjustment):")
add_code_block(doc, "P_akhir = P_kontrak * (1 - M_aktual / 100) / (1 - M_kontrak / 100)\n"
                    "P_akhir = 600 * (1 - 0,125) / (1 - 0,110) = Rp 589,89/kg\n"
                    "Berat Bayar (payable_kg) = Netto * (1 - Kontaminasi / 100) = 14.950 * 0,992 = 14.830,4 kg\n"
                    "Total Pembayaran = 14.830,4 kg * Rp 589,89 = Rp 8.748.297")
add_styled_paragraph(doc, 
    "Hasil QC diterbitkan sebagai record `inbound_qc` (tersedia `remaining_kg = 14.950` untuk pakan batch pabrik). "
    "Sistem secara otomatis menerbitkan tagihan `collector_settlements` (sumber 'qc') berstatus `PAYABLE` (terutang). "
    "Seluruh harvest petani yang terlampir pada DR ini otomatis dialihkan statusnya ke `DELIVERED`, dengan berat terima yang dialokasikan proporsional.")

doc.add_page_break()

# ==============================================================================
# BAB 7: OPERASI MANUFAKTUR SIRKULAR & EKONOMI PABRIK
# ==============================================================================
add_heading_1(doc, "BAB 7: MANUFAKTUR SIRKULAR, REAKTOR PIROLISIS & EKONOMI PABRIK")

add_styled_paragraph(doc, 
    "Pabrik pirolisis mengoperasikan reaktor pirolisis lambat (slow pyrolysis rotary kiln) yang terintegrasi "
    "dengan sistem penangkapan syngas dan ekstraksi bio-silika.")

add_heading_2(doc, "7.1 Spesifikasi Reaktor Pirolisis Lambat Indmira")
add_styled_paragraph(doc, "• Tipe Reaktor: Indirect-Fired Rotary Kiln dengan sirkulasi pemanasan syngas tertutup.", font_size=10.5)
add_styled_paragraph(doc, "• Temperatur Operasi: 450°C – 550°C dengan waktu tinggal (residence time) 25–40 menit.", font_size=10.5)
add_styled_paragraph(doc, "• Fitur Kunci: Airlock Rotary Valve anti-masuk oksigen; Cyclone Separator pemisah fly ash; Water-Jacketed Cooling Auger mendinginkan biochar dari 500°C ke < 50°C tanpa penambahan air berlebih.", font_size=10.5)

add_heading_2(doc, "7.2 Model Sirkular: 1 Input → 3 Output Produk + 5 Aliran Loss")
add_styled_paragraph(doc, 
    "Engine ⑪ memodelkan setiap 1 kg sekam yang masuk ke pabrik secara mass balance tertutup sempurna (Σ Output + Σ Loss = 1 kg):")

mass_model = [
    ["Input Tunggal", "Sekam Padi Diterima", "100%", "Kadar air M% basis basah, kadar abu A% basis kering."],
    ["Output Produk ①", "Bio-Pellet", "0% – 50%", "Bahan bakar padat densifikasi kalori tinggi untuk cofiring PLTU."],
    ["Output Produk ②", "Biochar Pirolisis", "25% – 38%", "Karbon stabil berpori tinggi untuk pembenah tanah sawah & sekuestrasi."],
    ["Output Produk ③", "Bio-Silika Amorf", "3% – 12%", "Silika murni (>99% SiO₂) untuk industri ban, karet, semikonduktor, semen."],
    ["Aliran Loss ①", "Uap Air Pengering", "Variabel", "Air bebas yang diuapkan pada unit pengering putar rotary dryer."],
    ["Aliran Loss ②", "Volatil & Syngas", "40% – 55%", "Gas mampu-bakar (CO, H₂, CH₄) yang disirkulasikan kembali sebagai bahan bakar."],
    ["Aliran Loss ③", "Gas Pembakaran", "Variabel", "Gas buang CO₂ dan H₂O pada tungku pembakaran/kalsinasi."],
    ["Aliran Loss ④", "Residu Ekstraksi", "Variabel", "Ampas padat sisa pelindian kimia dan presipitasi natrium silikat."],
    ["Aliran Loss ⑤", "Susut Mekanis", "0,5% – 1,5%", "Kehilangan debu mikro pada konveyor dan siklon penampungan."]
]
add_styled_table(doc, ["Komponen Neraca", "Aliran Komoditas", "Porsi Tipikal", "Karakteristik & Pemanfaatan"], mass_model, [1.5, 1.5, 1.2, 2.3])

add_heading_2(doc, "7.3 Tiga Jalur Ekstraksi Bio-Silika")
add_styled_paragraph(doc, 
    "Sistem mendukung tiga pilihan rute teknologi silika yang dapat dikonfigurasi melalui menu Parameter:")
add_styled_paragraph(doc, "1. Rute 'Biochar' (Default): Sekam dipirolisis menghasilkan biochar padat. Sebagian biochar diekstrak menggunakan pelindih alkali NaOH menjadi larutan natrium silikat (water glass), lalu dipresipitasi dengan asam.", font_size=10)
add_styled_paragraph(doc, "2. Rute 'Abu Pembakaran': Sekam dibakar di tungku boiler untuk menghasilkan uap panas proses (panas dimanfaatkan sebagai kredit pengeringan). Abu sekam (RHA) yang kaya silika diekstrak alkali.", font_size=10)
add_styled_paragraph(doc, "3. Rute 'Sekam Langsung': Sekam dicuci asam (acid leaching HCl/H₂SO₄) untuk menghilangkan ion logam pengotor, lalu dikalsinasi terkontrol pada 650°C menghasilkan bio-silika amorf putih dengan kemurnian >99,5%.", font_size=10)

add_heading_2(doc, "7.4 Pencatatan Batch Manufaktur Sirkular (`POST /api/v1/factory/batches`)")
add_styled_paragraph(doc, 
    "Operator pabrik mencatat eksekusi manufaktur dengan memilih lot QC yang dikonsumsi (`qc_id` dan `input_kg`), "
    "memasukkan output aktual ketiga produk, losses, dan biaya operasi. Sistem melakukan verifikasi:")
add_styled_paragraph(doc, "• Penutupan Neraca Massa (Closure Error %): Selisih |Σ Input - (Σ Output + Σ Loss)| / Σ Input * 100 harus < 2,0%.", font_size=10)
add_styled_paragraph(doc, "• Alokasi Biaya Bersama (Joint Cost Allocation): Menggunakan metode Net Realizable Value (NRV) sesuai standar akuntansi biaya Horngren guna menghitung margin per produk secara akurat.", font_size=10)

add_heading_2(doc, "7.5 Algoritma Alokasi Biochar ke Dompet Petani (Largest Remainder Method)")
add_styled_paragraph(doc, 
    "Sesuai mandat ekonomi sirkular, sebagian biochar yang diproduksi (default 10% dari output batch) dikembalikan "
    "kepada para petani yang menyuplai sekam pada batch tersebut:")
add_code_block(doc, "pool_biochar_petani_gram = round(biochar_output_kg * return_share * 1000)\n"
                    "bobot_petani_i = sekam_terima_petani_i * porsi_lot_digunakan\n"
                    "alokasi_gram_i = allocate_grams(pool_biochar_petani_gram, bobot)")
add_styled_paragraph(doc, 
    "Fungsi `allocate_grams()` menerapkan algoritma *Largest Remainder* (Hamilton method). Nilai alokasi dihitung proporsional hingga desimal, "
    "dibulatkan ke gram terdekat, dan sisa selisih pembagian diberikan secara adil kepada petani dengan sisa pecahan terbesar. "
    "Invarian terbukti: `Σ Alokasi Petani == Total Pool Biochar` tepat hingga 1 gram tanpa ada gram yang hilang.")

doc.add_page_break()

# ==============================================================================
# BAB 8: BEDAH MATEMATIS 11 ENGINE KOMPUTASI
# ==============================================================================
add_heading_1(doc, "BAB 8: SPESIFIKASI MATEMATIS & TEKNIS 11 ENGINE KOMPUTASI")

add_heading_2(doc, "8.1 Engine ①: Supply Forecaster (Model Cosinus Ganda)")
add_styled_paragraph(doc, 
    "Memodelkan dinamika musiman ketersediaan sekam padi bulanan di wilayah Jawa berdasarkan data panen raya dan panen gadu BPS:")
add_code_block(doc, "S_hat(t) = S_base * [1 + A1 * cos(2*pi*(t - phi1) / 12) + A2 * cos(4*pi*(t - phi2) / 12)]")
add_styled_paragraph(doc, 
    "Parameter terkalibrasi: S_base = kebutuhan dasar bulanan, A1 = 0,42 dan phi1 = 4,1 (puncak panen raya musim hujan Maret–Mei), "
    "A2 = 0,25 dan phi2 = 8,6 (puncak panen gadu musim kemarau Agustus–September). Engine menyediakan proyeksi pasokan harian 30 hari ke depan.")

add_heading_2(doc, "8.2 Engine ②: Quality & Yield Scorer (Kinetika Pirolisis Lambat)")
add_styled_paragraph(doc, 
    "Memprediksi rendemen biochar berbasis temperatur reaktor pirolisis dan proksimat sekam:")
add_code_block(doc, "Yield_biochar(T) = Y0 * exp(-k * (T - T0)) * (1 - Moisture/100) * (1 - Contamination/100)")
add_styled_paragraph(doc, 
    "Aturan Mutu dan Pengali Harga Acuan:")
add_styled_paragraph(doc, "• Grade A: Kadar Air ≤ 12%, Abu ≤ 20%, Kontaminan ≤ 2% ==> Pengali Harga 1,10x (+10% Bonus Mutu).", font_size=10)
add_styled_paragraph(doc, "• Grade B: Kadar Air ≤ 16%, Abu ≤ 25%, Kontaminan ≤ 5% ==> Pengali Harga 1,00x (Harga Normal).", font_size=10)
add_styled_paragraph(doc, "• Grade C: Kadar Air ≤ 20%, Abu ≤ 30%, Kontaminan ≤ 8% ==> Pengali Harga 0,85x (Potongan Mutu).", font_size=10)
add_styled_paragraph(doc, "• Tolak: Kadar Air > 20% atau Kontaminan > 8% ==> Pengali Harga 0,00x (Ditolak / Pembelian Khusus).", font_size=10)

add_heading_2(doc, "8.3 Engine ③: Blending Optimizer (Linear Programming HiGHS)")
add_styled_paragraph(doc, 
    "Menentukan komposisi campuran bahan baku biomassa multi-feedstock biaya minimum untuk mencapai spesifikasi reaktor:")
add_code_block(doc, 
"""Minimalkan:  Total Biaya = sum(c_i * x_i)
Terhadap Kendala:
   sum(x_i) = Target_Produksi
   sum(Moisture_i * x_i) <= Max_Moisture * Target
   sum(Ash_i * x_i)      <= Max_Ash * Target
   sum(FC_i * x_i)       >= Min_FC * Target
   0 <= x_i <= Stok_i    (Batas Ketersediaan)""")
add_styled_paragraph(doc, "Diselesaikan dalam waktu < 10 milidetik menggunakan solver LP HiGHS melalui library SciPy.")

add_heading_2(doc, "8.4 Engine ⑤: Route Optimizer (CVRP Berbatas Volume)")
add_styled_paragraph(doc, 
    "Sekam memiliki densitas ruah rendah (110 kg/m³), sehingga volume truk selalu penuh jauh sebelum kapasitas tonase tercapai. "
    "Engine ⑤ memecahkan *Capacitated Vehicle Routing Problem* (CVRP) berbasis batasan volume bak truk Q (m³):")
add_styled_paragraph(doc, 
    "• Solver Eksak (n ≤ 10 titik): Algoritma Held-Karp untuk biaya tur subset layak, dipadukan dengan Dynamic Programming Set-Partitioning: "
    "F(M) = min_{S subset M} [C(S) + F(M \\ S)]. Kompleksitas O(2^n * n² + 3^n), optimal terbukti matematis.", font_size=10)
add_styled_paragraph(doc, 
    "• Solver Heuristik (n > 10 titik): Algoritma penghematan Clarke-Wright granular (savings s_ij = d_0i + d_0j - d_ij) "
    "dilanjutkan Local Search (2-opt, relocate, swap) dan Iterated Local Search (SISR Ruin & Recreate) dalam anggaran waktu `time_budget_ms`.", font_size=10)

add_heading_2(doc, "8.5 Engine ⑥: Gamification & Incentive Engine")
add_styled_paragraph(doc, 
    "Mendorong petani mempertahankan mutu sekam Grade A melalui akumulasi Experience Points (XP):")
add_code_block(doc, "XP_earned = Round[(Qty_kg / 10) * Multiplier(Grade) * BonusStreak]")
add_styled_paragraph(doc, "Tingkatan Tier Kemitraan:")
add_styled_paragraph(doc, "• Pemula (0–99 XP): Akses standar pelaporan stok.", font_size=10)
add_styled_paragraph(doc, "• Mitra Perunggu (100–499 XP): Prioritas jadwal penjemputan truk.", font_size=10)
add_styled_paragraph(doc, "• Mitra Perak (500–1.499 XP): Subsidi karung terpal anti-hujan.", font_size=10)
add_styled_paragraph(doc, "• Mitra Emas (≥ 1.500 XP): Bonus tunai flat +Rp 25/kg dan kuota bibit padi unggul bersertifikat.", font_size=10)

add_heading_2(doc, "8.6 Engine ⑦: ESG Carbon Credit Calculator (IPCC Tier 2)")
add_styled_paragraph(doc, 
    "Menghitung pengurangan emisi bersih terverifikasi berdasarkan Perpres 110/2025 Nilai Ekonomi Karbon (NEK):")
add_code_block(doc, "Delta_E_net = E_baseline - E_transport - E_pyrolysis + E_sequestration\n"
                    "E_baseline = 1,28 tCO2e / ton sekam (avoided open burning CH4 & N2O)\n"
                    "E_sequestration = C_org * F_perm * (44 / 12) = 0,85 * 0,80 * 3,67 = 2,49 tCO2e / ton biochar")

add_heading_2(doc, "8.7 Engine ⑧: Feedstock Multi-Criteria Decision Making (TOPSIS)")
add_styled_paragraph(doc, 
    "Mengevaluasi dan meranking komoditas biomassa alternatif (sekam, tongkol jagung, serbuk kayu, bagasse) menggunakan metode TOPSIS "
    "(Hwang & Yoon 1981). Mengestimasi Higher Heating Value (HHV) Parikh (2005): "
    "HHV = 0,3536*FC + 0,1559*VM - 0,0078*Ash (MJ/kg), LHV as-received, dan rasio bahan bakar FC/VM.")

add_heading_2(doc, "8.8 Engine ⑨: Waste-to-Energy Advisor")
add_styled_paragraph(doc, 
    "Memberikan rekomendasi teknologi konversi limbah berdasarkan batas kelayakan termokimia (kadar air < 50%, abu < 20%) "
    "vs biokimia (digestasi anaerobik biogas untuk bahan basah C/N 20–30, BMP tinggi). Menghitung potensi energi tahunan.")

add_heading_2(doc, "8.9 Engine ⑩: Industrial Energy Analytics (ISO 50006 & Permen ESDM)")
add_styled_paragraph(doc, 
    "Menganalisis efisiensi konsumsi listrik pabrik: Intensitas Konsumsi Energi (IKE, kWh/m²/bulan) sesuai Permen ESDM No. 13/2012, "
    "Specific Energy Consumption (SEC, kWh/ton bahan olah), serta regresi linier baseline energi (kWh = a + b*ton). "
    "Mendeteksi anomali pemborosan menggunakan robust Z-score (median/MAD) dan CUSUM residu.")

add_heading_2(doc, "8.10 Engine ⑪: Factory Economics & Netback Pricing")
add_styled_paragraph(doc, 
    "Menghitung harga beli sekam wajar (netback pricing) dari nilai jual ketiga produk turunan:")
add_code_block(doc, "Nilai_Produk = sum(Rendemen_i * Harga_i) * (1 - Kontaminasi/100)\n"
                    "Harga_Lantai = Nilai_Produk - Biaya_Variabel_per_kg (titik tutup jangka pendek)\n"
                    "Harga_Plafon = Harga_Lantai - Biaya_Tetap_per_kg    (titik impas penuh / BEP)\n"
                    "Harga_Target = Harga_Plafon - Target_Margin * Nilai")

doc.add_page_break()

# ==============================================================================
# BAB 9: TATA KELOLA KEUANGAN, AUDIT & ASISTEN AI
# ==============================================================================
add_heading_1(doc, "BAB 9: TATA KELOLA KEUANGAN, AUDIT ESG & ASISTEN AI")

add_heading_2(doc, "9.1 Modul Penyelesaian Finansial (Settlements & Audit Trail)")
add_styled_paragraph(doc, 
    "Tabel `collector_settlements` mengelola seluruh kewajiban pembayaran pabrik ke pengepul untuk kedua jalur pasokan. "
    "Siklus status tagihan berjalan tertib:")
add_styled_paragraph(doc, "1. `menunggu_harga`: Diterbitkan jika harga jual produk di pabrik belum ditentukan.", font_size=10)
add_styled_paragraph(doc, "2. `terutang`: Nilai nominal tagihan telah final dan sah, menunggu transfer bank.", font_size=10)
add_styled_paragraph(doc, "3. `dibayar`: Pabrik mengunggah nomor referensi transfer bank (`payment_reference`). Tagihan yang sudah dibayar terkunci permanen.", font_size=10)
add_styled_paragraph(doc, "Setiap penetapan harga atau perubahan status dicatat di tabel `settlement_events` beserta aktor dan alasannya.")

add_heading_2(doc, "9.2 Modul Pengawasan Auditor ESG Independen")
add_styled_paragraph(doc, 
    "Auditor memiliki akses baca-saja ke tiga instrumen verifikasi utama:")
add_styled_paragraph(doc, "• `/auditor/discrepancies`: Memantau daftar pengiriman dengan susut melebihi toleransi parameter.", font_size=10)
add_styled_paragraph(doc, "• `/auditor/mass-balance/{id}`: Menelusuri riwayat timbangan lengkap satu panen dari estimasi petani, timbang pengepul, timbang supir, hingga timbang pabrik.", font_size=10)
add_styled_paragraph(doc, "• `/auditor/summary`: Rekapitulasi neraca massa agregat seluruh platform (total sekam ditimbang pengepul vs diterima pabrik vs total biochar kembali ke petani).", font_size=10)

add_heading_2(doc, "9.3 Registry Parameter Terpusat (`app/params.py`)")
add_styled_paragraph(doc, 
    "Sekitar 100 konstanta asumsi operasional tidak ditanam langsung di dalam kode, melainkan dikelola oleh *Parameter Registry* "
    "yang terbagi ke dalam 13 kelompok (harga_mutu, ambang_mutu, rendemen, sirkular, logistik, karbon, proyeksi, insentif, pasar, limbah, energi, feedstock, pabrik). "
    "Parameter memiliki sistem validasi rentang dan konsistensi lintas-parameter. Setiap perubahan tercatat di tabel `parameter_changes`.")

add_heading_2(doc, "9.4 Asisten Kecerdasan Buatan Multi-LLM Terintegrasi")
add_styled_paragraph(doc, 
    "Platform dilengkapi asisten AI di pojok kanan bawah antarmuka pengguna (`/api/v1/assistant/chat`). "
    "Sistem mendukung multi-provider AI: Google Gemini, Mistral AI, Groq, OpenRouter, dan Ollama lokal. "
    "System prompt secara dinamis menginjeksi konteks pengguna yang sedang login (nama, peran, saldo XP, daftar panen aktif, rute armada, atau kapasitas pabrik) "
    "sehingga AI dapat memberikan analisis dan saran optimasi yang presisi sesuai peran pengguna.")

add_heading_2(doc, "9.5 Gudang Data & Pelaporan Terpadu")
add_styled_paragraph(doc, 
    "Endpoint `/api/v1/reports/monthly` mengekstraksi laporan berkala volume pasokan, persentase konversi, dan biaya "
    "ke dalam format JSON, CSV, atau file spreadsheet Excel (.xlsx) dengan pembagian cakupan otomatis sesuai peran pengguna.")

doc.add_page_break()

# ==============================================================================
# BAB 10: MATRIKS REFERENSI TEKNIS: SKEMA DB & REST API
# ==============================================================================
add_heading_1(doc, "BAB 10: MATRIKS REFERENSI TEKNIS: SKEMA BASIS DATA & REST API")

add_heading_2(doc, "10.1 Katalog Tabel Basis Data Lengkap")
tables_catalog = [
    ["users", "id, phone, username, full_name, role, password_hash, xp_total, incentive_tier, lat, lon", "Tabel pengguna multi-peran (Petani, Pengepul, Driver, Pabrik, Auditor, Admin)."],
    ["mills", "id, code, name, kecamatan, lat, lon, capacity_ton, is_active", "Lokasi fasilitas penggilingan padi tempat penampungan sekam."],
    ["harvests", "id, uuid, farmer_id, collector_id, quantity_kg, status, grade, verified_kg, received_kg, qr_code", "Entitas inti siklus pasokan sekam, mencatat timbangan di tiap titik serah."],
    ["stock_listings", "id, farmer_id, quantity_kg, remaining_kg, allow_jemput, allow_antar, ask_price_jemput/antar", "Listing penawaran stok sekam di bursa lelang B2B."],
    ["bids", "id, listing_id, collector_id, scheme, price_per_kg, quantity_kg, accepted_kg, status", "Tawaran harga dari pengepul untuk listing stok petani."],
    ["delivery_requests", "id, collector_id, quantity_kg, moisture_est, proposed_price, agreed_price, status", "Kontrak pengadaan sekam B2B dari pengepul ke gerbang pabrik."],
    ["negotiation_events", "id, request_id, actor_id, actor_role, action, price_per_kg, date, note", "Log audit putaran tawar-menawar kontrak pengadaan B2B."],
    ["inbound_qc", "id, request_id, gross_kg, tare_kg, net_kg, payable_kg, moisture, grade, final_price, remaining_kg", "Hasil timbang bruto-tara dan uji proksimat lot sekam masuk pabrik."],
    ["manufacturing_batches", "id, batch_code, input_kg, closure_error_pct, economics, operator_id", "Batch pirolisis sirkular pengolahan sekam menjadi 3 produk."],
    ["batch_inputs / outputs / losses / costs", "id, batch_id, qc_id, product, kind, item, amount_rp", "Rincian lot input, produk jadi, aliran loss, dan biaya per batch."],
    ["collector_settlements", "id, collector_id, source (qc/rute), payable_kg, price_per_kg, amount_rp, status", "Kewajiban pembayaran pabrik ke pengepul (menunggu harga, terutang, dibayar)."],
    ["settlement_events", "id, settlement_id, action, old/new_price, old/new_amount, reason, actor_id", "Log audit perubahan harga dan status pelunasan tagihan pengepul."],
    ["conversions", "id, batch_code, feedstock_ton, biochar_ton, actual_yield_pct, farmer_return_share", "Konversi pirolisis batch langsung (Path A)."],
    ["biochar_ledger", "id, farmer_id, conversion_id, batch_id, entry_type, amount_kg", "Buku besar saldo dompet biochar petani (alokasi & penebusan)."],
    ["routes & route_stops", "id, driver_id, status, total_km, total_ton / route_id, mill_id, stop_order, qr_scanned", "Rute perjalanan armada pengangkut sekam hasil optimasi Engine ⑤."],
    ["energy_readings", "id, facility, period, kwh, building_kwh, production_ton, floor_area_m2", "Histori konsumsi listrik bulanan fasilitas untuk audit Engine ⑩."],
    ["parameter_changes", "id, key, old_value, new_value, changed_by_id, changed_by_role, reason", "Jejak audit modifikasi parameter asumsi sistem oleh Admin/Pabrik."]
]
add_styled_table(doc, ["Nama Tabel", "Kolom-Kolom Kunci", "Fungsi & Peranan dalam Sistem"], tables_catalog, [1.5, 2.3, 2.7])

add_heading_2(doc, "10.2 Katalog Lengkap Endpoint REST API Bio-Chain")
api_catalog = [
    ["POST", "/api/v1/auth/login", "Publik", "Login nomor HP / username + password, menghasilkan JWT token."],
    ["POST", "/api/v1/farmer/harvest", "Petani", "Lapor stok sekam siap jual, menghasilkan QR code unik."],
    ["GET", "/api/v1/farmer/harvests", "Petani", "Riwayat laporan panen petani beserta status terkini."],
    ["GET", "/api/v1/farmer/wallet", "Petani", "Saldo biochar teralokasi dan riwayat transaksi dompet biochar."],
    ["POST", "/api/v1/farmer/listings", "Petani", "Pasang stok sekam di bursa B2B (skema jemput/antar)."],
    ["POST", "/api/v1/farmer/listings/{id}/accept", "Petani", "Petani menerima tawaran pengepul secara atomik."],
    ["GET", "/api/v1/collector/available-harvests", "Pengepul", "Daftar laporan sekam petani yang siap diverifikasi."],
    ["POST", "/api/v1/collector/verify", "Pengepul", "Input uji proksimat & timbang resmi (Engine ② Grading & Payout)."],
    ["POST", "/api/v1/collector/bid-advisor", "Pengepul", "Rekomendasi tawaran maksimum via marginal routing cost CVRP."],
    ["POST", "/api/v1/collector/delivery-requests", "Pengepul", "Pengajuan kontrak Delivery Request sekam ke pabrik."],
    ["GET", "/api/v1/driver/active-route", "Driver", "Mengambil rute aktif dan daftar urutan perhentian GIS."],
    ["POST", "/api/v1/driver/confirm-pickup", "Driver", "Konfirmasi penjemputan fisik sekam via scan QR tiket."],
    ["POST", "/api/v1/factory/dispatch", "Pabrik", "Menyusun rute armada dan menugaskan supir (Engine ⑤ CVRP)."],
    ["POST", "/api/v1/factory/receive", "Pabrik", "Timbang terima jembatan timbang resmi & audit susut pengangkutan."],
    ["POST", "/api/v1/factory/qc", "Pabrik", "Inbound QC gerbang pabrik, dry-basis adjustment & tagihan lot."],
    ["POST", "/api/v1/factory/batches", "Pabrik", "Catat batch manufaktur sirkular 3-produk & alokasi dompet biochar."],
    ["POST", "/api/v1/factory/blend/recommend", "Pabrik", "Optimasi racikan pakan biomassa (Engine ③ HiGHS LP Solver)."],
    ["GET", "/api/v1/auditor/summary", "Auditor", "Ringkasan neraca massa agregat platform dari sawah ke sawah."],
    ["GET", "/api/v1/reports/monthly", "Semua Role", "Unduh laporan bulanan format JSON, CSV, atau Excel XLSX."],
    ["POST", "/api/v1/assistant/chat", "Semua Role", "Tanya jawab cerdas dengan Asisten AI multi-provider."]
]
add_styled_table(doc, ["Metode", "Path Endpoint", "Akses", "Deskripsi Operasi API"], api_catalog, [0.8, 2.3, 1.0, 2.4])

# Saving Document
output_dir = "docs"
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, "PETA_FLOW_DAN_STEP_BY_STEP_BIOCHAIN.docx")
doc.save(output_path)
print(f"Document successfully created at: {output_path}")
# Satu salinan saja (docs/) — salinan di root dulu membuat dua versi yang bisa berbeda.
