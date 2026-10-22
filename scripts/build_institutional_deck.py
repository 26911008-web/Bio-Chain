"""
Script Rekonstruksi Pitch Deck Bio-Chain v2 ke Standar Institusional VC Global
Konsorsium: Climate-Tech Principal Architect & Senior Partner VC ESG
Output: BioChain_PitchDeck_ANGEL2026_Institutional_VC.pptx & BioChain_PitchDeck_ANGEL2026_v2.pptx
"""

import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

# 1. Palet Warna Climate-Tech VC
DARK_BG = RGBColor(15, 23, 42)       # Charcoal / Dark Slate (#0F172A)
DARK_CARD = RGBColor(30, 41, 59)     # Slate 800 (#1E293B)
LIGHT_BG = RGBColor(248, 250, 252)   # Crisp Off-White (#F8FAFC)
LIGHT_CARD = RGBColor(255, 255, 255) # Pure White (#FFFFFF)
CARD_BORDER = RGBColor(226, 232, 240)# Light Border (#E2E8F0)

FOREST_GREEN = RGBColor(5, 150, 105) # Emerald 600 (#059669)
EMERALD_BRIGHT = RGBColor(16, 185, 129)# Emerald 500 (#10B981)
MINT_ACCENT = RGBColor(52, 211, 153) # Emerald 400 (#34D399)
GOLD_ACCENT = RGBColor(217, 119, 6)  # Amber 600 (#D97706)

TEXT_DARK = RGBColor(15, 23, 42)     # Charcoal text
TEXT_MUTED = RGBColor(100, 116, 139) # Slate 500
TEXT_LIGHT = RGBColor(248, 250, 252) # White text
TEXT_LIGHT_MUTED = RGBColor(148, 163, 184) # Slate 400

DOCS_DIR = r"D:\IDE\bio-chain-prototype\docs"

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
blank_layout = prs.slide_layouts[6]

def set_slide_bg(slide, color):
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    bg.fill.solid()
    bg.fill.fore_color.rgb = color
    bg.line.fill.background()
    return bg

def add_header(slide, slide_num, total_slides, kicker, title, subtitle, is_dark=False):
    # Kicker / Badge
    tb_kicker = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.35))
    tf_k = tb_kicker.text_frame
    tf_k.word_wrap = True
    p_k = tf_k.paragraphs[0]
    p_k.text = f"BIO-CHAIN v2  |  SLIDE {slide_num:02d}/{total_slides:02d}  •  {kicker.upper()}"
    p_k.font.size = Pt(10)
    p_k.font.bold = True
    p_k.font.color.rgb = MINT_ACCENT if is_dark else FOREST_GREEN

    # Title
    tb_title = slide.shapes.add_textbox(Inches(0.8), Inches(0.75), Inches(11.7), Inches(0.65))
    tf_t = tb_title.text_frame
    tf_t.word_wrap = True
    p_t = tf_t.paragraphs[0]
    p_t.text = title
    p_t.font.size = Pt(22)
    p_t.font.bold = True
    p_t.font.color.rgb = TEXT_LIGHT if is_dark else TEXT_DARK

    # Subtitle
    if subtitle:
        tb_sub = slide.shapes.add_textbox(Inches(0.8), Inches(1.35), Inches(11.7), Inches(0.45))
        tf_s = tb_sub.text_frame
        tf_s.word_wrap = True
        p_s = tf_s.paragraphs[0]
        p_s.text = subtitle
        p_s.font.size = Pt(12)
        p_s.font.color.rgb = TEXT_LIGHT_MUTED if is_dark else TEXT_MUTED

def add_card(slide, left, top, width, height, title, items, is_dark=False, border_color=None, badge_text=None):
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
    card.fill.solid()
    card.fill.fore_color.rgb = DARK_CARD if is_dark else LIGHT_CARD
    if border_color:
        card.line.color.rgb = border_color
        card.line.width = Pt(1.5)
    else:
        card.line.color.rgb = RGBColor(51, 65, 85) if is_dark else CARD_BORDER
        card.line.width = Pt(1)

    tb = slide.shapes.add_textbox(Inches(left + 0.25), Inches(top + 0.2), Inches(width - 0.5), Inches(height - 0.4))
    tf = tb.text_frame
    tf.word_wrap = True

    p0 = tf.paragraphs[0]
    p0.text = title
    p0.font.size = Pt(14)
    p0.font.bold = True
    p0.font.color.rgb = MINT_ACCENT if is_dark else FOREST_GREEN

    if badge_text:
        p_badge = tf.add_paragraph()
        p_badge.text = f"[{badge_text}]"
        p_badge.font.size = Pt(9.5)
        p_badge.font.bold = True
        p_badge.font.color.rgb = GOLD_ACCENT

    for item in items:
        p = tf.add_paragraph()
        p.text = f"•  {item}"
        p.font.size = Pt(10.5)
        p.font.color.rgb = TEXT_LIGHT_MUTED if is_dark else TEXT_DARK
        p.space_before = Pt(4)

def add_metric_callout(slide, left, top, width, height, big_num, label, desc, is_dark=False):
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
    card.fill.solid()
    card.fill.fore_color.rgb = DARK_CARD if is_dark else LIGHT_CARD
    card.line.color.rgb = FOREST_GREEN if is_dark else EMERALD_BRIGHT
    card.line.width = Pt(1.5)

    tb = slide.shapes.add_textbox(Inches(left + 0.15), Inches(top + 0.15), Inches(width - 0.3), Inches(height - 0.3))
    tf = tb.text_frame
    tf.word_wrap = True

    p0 = tf.paragraphs[0]
    p0.text = big_num
    p0.font.size = Pt(24)
    p0.font.bold = True
    p0.font.color.rgb = MINT_ACCENT if is_dark else FOREST_GREEN
    p0.alignment = PP_ALIGN.CENTER

    p1 = tf.add_paragraph()
    p1.text = label
    p1.font.size = Pt(11)
    p1.font.bold = True
    p1.font.color.rgb = TEXT_LIGHT if is_dark else TEXT_DARK
    p1.alignment = PP_ALIGN.CENTER

    if desc:
        p2 = tf.add_paragraph()
        p2.text = desc
        p2.font.size = Pt(9.5)
        p2.font.color.rgb = TEXT_LIGHT_MUTED if is_dark else TEXT_MUTED
        p2.alignment = PP_ALIGN.CENTER

print("Generating 12 VC Institutional Slides...")

# ==============================================================================
# SLIDE 1: Visi Utama (Monetisasi Limbah Biomassa Menjadi Aset Karbon)
# ==============================================================================
s1 = prs.slides.add_slide(blank_layout)
set_slide_bg(s1, DARK_BG)

# Title slide content
tb_s1 = s1.shapes.add_textbox(Inches(1.0), Inches(1.2), Inches(11.3), Inches(4.5))
tf_s1 = tb_s1.text_frame
tf_s1.word_wrap = True

p = tf_s1.paragraphs[0]
p.text = "BIO-CHAIN v2  |  INSTITUTIONAL CLIMATE-TECH INVESTMENT DECK"
p.font.size = Pt(12)
p.font.bold = True
p.font.color.rgb = MINT_ACCENT

p = tf_s1.add_paragraph()
p.text = "Mengubah Limbah Biomassa Pertanian\nMenjadi Aset Karbon Berkualitas Global"
p.font.size = Pt(32)
p.font.bold = True
p.font.color.rgb = TEXT_LIGHT
p.space_before = Pt(16)

p = tf_s1.add_paragraph()
p.text = "Platform Rantai Pasok Cerdas, dMRV Karbon Terverifikasi & Manufaktur Sirkular Multi-Produk\nBermitra dengan PT Indmira Global Energi (Topik #4 ANGEL Deeptech Hackathon)"
p.font.size = Pt(15)
p.font.color.rgb = TEXT_LIGHT_MUTED
p.space_before = Pt(14)

add_metric_callout(s1, 1.0, 5.2, 2.6, 1.6, "10,2 Juta Ton", "Potensi Sekam Nasional", "60% dibakar terbuka / sia-sia", is_dark=True)
add_metric_callout(s1, 3.8, 5.2, 2.6, 1.6, "-58% Jarak", "Efisiensi Logistik CVRP", "Batas volumetrik 0.11 t/m³", is_dark=True)
add_metric_callout(s1, 6.6, 5.2, 2.6, 1.6, "1 Input -> 3 Produk", "Valorisasi Manufaktur", "Biochar, Biosilika, Biopellet", is_dark=True)
add_metric_callout(s1, 9.4, 5.2, 2.6, 1.6, "€125 / tCO₂e", "Potensi Kredit Puro.earth", "Penerbitan CORC & IDXCarbon", is_dark=True)

# ==============================================================================
# SLIDE 2: Permasalahan Makro (Emisi Metana Sekam & Kegagalan Sertifikasi)
# ==============================================================================
s2 = prs.slides.add_slide(blank_layout)
set_slide_bg(s2, LIGHT_BG)
add_header(s2, 2, 12, "Permasalahan Makro", "Krisis Pasokan Biomassa & Kegagalan Sertifikasi Karbon", "Rantai pasok konvensional menyebabkan volatilitas bahan baku reaktor dan hilangnya potensi monetisasi karbon.")

add_card(s2, 0.8, 2.0, 3.6, 4.8, "1. Emisi Metana & Polusi", [
    "10,2 juta ton sekam padi dihasilkan per tahun dari 70.000 penggilingan kecil.",
    ">60% sekam dimusnahkan via pembakaran terbuka (open-field burning).",
    "Melepaskan PM2.5 beracun dan gas metana (CH₄) dengan GWP 28x lebih kuat dari CO₂.",
    "Pelanggaran regulasi lingkungan dan hilangnya bahan baku energi bersih."
], badge_text="Urgensi Lingkungan")

add_card(s2, 4.8, 2.0, 3.6, 4.8, "2. Hambatan Struktural Rantai Pasok", [
    "Densitas ruah sangat rendah (bulk density 100-120 kg/m³); truk penuh volume sebelum batas tonase.",
    "Fluktuasi mutu ekstrem (kadar air 11% s.d. >25%) merusak kestabilan reaktor pirolisis.",
    "Sengketa timbangan di gerbang pabrik akibat pemotongan taksiran manual sepihak.",
    "Persaingan feedstock dengan program co-firing PLTU batubara nasional."
], badge_text="Kegagalan Logistik")

add_card(s2, 8.8, 2.0, 3.7, 4.8, "3. Krisis Integritas Audit Karbon", [
    "Data transaksi masih memakai nota kertas manual yang rentan pemalsuan (phantom loads).",
    "Audit MRV konvensional bersifat retrospektif dan berbiaya mahal ($15/tCO₂e).",
    "Kegagalan chain-of-custody menyebabkan klaim karbon ditolak Puro.earth & Verra.",
    "Tidak adanya integrasi dengan registri karbon domestik SRN-PPI & IDXCarbon."
], badge_text="Integritas dMRV")

# ==============================================================================
# SLIDE 3: Solusi BioChain (Integrasi Software & Neraca Massa Termodinamika)
# ==============================================================================
s3 = prs.slides.add_slide(blank_layout)
set_slide_bg(s3, LIGHT_BG)
add_header(s3, 3, 12, "Solusi Terintegrasi", "BioChain: Sistem Rantai Pasok Cerdas & dMRV Karbon", "Mengintegrasikan IoT edge, orkestrasi armada CVRP volumetrik, dan reaktor pirolisis termodinamika.")

add_card(s3, 0.8, 2.0, 5.6, 4.8, "Arsitektur Solusi Hulu-ke-Hilir", [
    "Bio-Chain Scout Pro (IoT Edge): Sensor uji cepat kadar air lapangan & resi kriptografis UUID v4.",
    "Dual-Supply Corridor: Mengakomodasi rute terjadwal pabrik (Path A) dan bursa lelang B2B (Path B).",
    "Jembatan Timbang & Refraksi Otomatis: Koreksi harga berbasis bahan kering murni secara adil.",
    "Reaktor Pirolisis Lambat Indmira (450-550°C): Konversi terkontrol menghasilkan biochar karbon tinggi (>70%).",
    "Closed-Loop Mass Balance: Konservasi massa 1 input -> 3 produk dengan akurasi 100%."
], badge_text="End-to-End Integration")

# If 3d model image exists, embed it
img_path = os.path.join(DOCS_DIR, "model_3d_pirolisis_biochar_1790954795026.jpg")
if os.path.exists(img_path):
    s3.shapes.add_picture(img_path, Inches(6.8), Inches(2.0), Inches(5.7), Inches(3.2))
    add_card(s3, 6.8, 5.35, 5.7, 1.45, "Model Termodinamika Reaktor Indmira", [
        "Pirolisis lambat indirect-fired rotary kiln dengan sirkulasi syngas tertutup.",
        "Rasio C-tertambat >70%, H/Corg <0.7 (memenuhi kriteria Puro.earth 100 tahun)."
    ], badge_text="Spesifikasi Reaktor")
else:
    add_card(s3, 6.8, 2.0, 5.7, 4.8, "Keunggulan Teknologi Termodinamika", [
        "Pirolisis lambat indirect-fired rotary kiln dengan sirkulasi syngas tertutup.",
        "Suhu operasi stabil 450-550°C dengan waktu tinggal 25-40 menit.",
        "Yield biochar 32.5% dengan kandungan karbon tertambat terverifikasi >70%.",
        "Ekstraksi bio-silika murni 90-95% SiO2 untuk pasar ban hijau dan semen berkelanjutan."
    ], badge_text="Spesifikasi Reaktor")

# ==============================================================================
# SLIDE 4: Parit Pertahanan Teknologi (Volumetric Routing, Offline-First, CAS)
# ==============================================================================
s4 = prs.slides.add_slide(blank_layout)
set_slide_bg(s4, LIGHT_BG)
add_header(s4, 4, 12, "Parit Teknologi (Moat)", "Tiga Fondasi Arsitektur Perangkat Lunak BioChain", "Didesain tangguh untuk operasional lapangan pedesaan dan standar integritas pasar modal global.")

add_card(s4, 0.8, 2.0, 3.6, 4.8, "1. Volumetric CVRP Routing", [
    "Optimasi rute armada berbatas kubikasi bak (m³), bukan tonase semata.",
    "Solver hibrida Held-Karp (Exact n≤12) dan Clarke-Wright Savings + ILS Ruin & Recreate.",
    "Memangkas jarak tempuh armada penjemputan hingga 58% dibanding rute konvensional.",
    "Menghemat biaya logistik solar hingga Rp 420 per kg sekam terangkut."
], badge_text="Engine Logistik")

add_card(s4, 4.8, 2.0, 3.6, 4.8, "2. Offline-First Store & Forward", [
    "Aplikasi lapangan tetap berjalan 100% tanpa koneksi internet di area persawahan blank spot.",
    "Penyimpanan lokal SQLite pada perangkat supir dan modul ESP32 IoT.",
    "Penerbitan resi kriptografis UUID v4 seketika saat penimbangan di sawah.",
    "Sinkronisasi otomatis saat terhubung kembali dengan proteksi deduplikasi replay."
], badge_text="Reliabilitas Lapangan")

add_card(s4, 8.8, 2.0, 3.7, 4.8, "3. CAS Concurrency & RLS Guard", [
    "Compare-and-Swap (CAS) level basis data: SELECT FOR UPDATE mencegah race-condition bursa.",
    "Anti-Double Spending: Sekam yang ditawar tidak dapat diklaim pihak lain secara bersamaan.",
    "Row-Level Security (RLS) PostgreSQL menjamin isolasi data komersial antar-pesaing.",
    "Append-Only Audit Ledger: Log transaksi imutabel tidak dapat dimanipulasi atau dihapus."
], badge_text="Integritas Data")

# ==============================================================================
# SLIDE 5: Ekosistem Transaksi Lapangan (Peran Terintegrasi 4 Persona)
# ==============================================================================
s5 = prs.slides.add_slide(blank_layout)
set_slide_bg(s5, LIGHT_BG)
add_header(s5, 5, 12, "Ekosistem Pengguna", "Orkestrasi Nilai Terpadu 4 Persona Lapangan", "Setiap pemangku kepentingan mendapatkan insentif ekonomi nyata dan transparansi tanpa friksi.")

add_card(s5, 0.8, 2.0, 2.7, 4.8, "🌾 Petani & Gilingan", [
    "Pelaporan stok mudah via ponsel.",
    "Estimasi kadar air transparan.",
    "Daya tawar harga lebih tinggi di bursa lelang.",
    "Menerima retur biochar gratis di Biochar Wallet untuk pemulihan sawah."
], badge_text="Pemasok Hulu")

add_card(s5, 3.8, 2.0, 2.7, 4.8, "📦 Pengepul Desa", [
    "Bursa lelang B2B tanpa risiko transaksi ganda.",
    "Verifikasi mutu cepat dengan resi digital.",
    "Pengajuan kuota kirim delivery request ke pabrik.",
    "Pencairan pembayaran cepat pasca timbang gerbang."
], badge_text="Agregator Lapangan")

add_card(s5, 6.8, 2.0, 2.7, 4.8, "🚛 Supir Armada", [
    "Navigasi rute CVRP optimal hemat waktu dan bahan bakar.",
    "Operasional offline tanpa takut hilang sinyal di sawah.",
    "Konfirmasi muat foto & resi digital instan.",
    "Pencatatan insentif ritase bulanan otomatis."
], badge_text="Logistik Transit")

add_card(s5, 9.8, 2.0, 2.7, 4.8, "🏭 Pabrik Indmira", [
    "Kepastian pasokan sekam terstandarisasi.",
    "Refraksi timbangan otomatis bebas sengketa pedagang.",
    "Pencatatan batch pirolisis dan neraca massa tertutup.",
    "Penerbitan kredit karbon institusional dMRV."
], badge_text="Offtaker & Reaktor")

# ==============================================================================
# SLIDE 6: Validasi Antarmuka & Traksi (Hasil Otomasi Playwright QA)
# ==============================================================================
s6 = prs.slides.add_slide(blank_layout)
set_slide_bg(s6, LIGHT_BG)
add_header(s6, 6, 12, "Traksi & Antarmuka", "Validasi Sistem Prototype Alpha & Otomasi QA", "Codebase berjalan stabil (TKT 3) dengan pengujian otomatis end-to-end beresolusi tinggi 1080p.")

# Embed screenshots if available
img_pabrik = os.path.join(DOCS_DIR, "screenshot_05_pabrik.png")
img_pengepul = os.path.join(DOCS_DIR, "screenshot_03_pengepul.png")

if os.path.exists(img_pabrik) and os.path.exists(img_pengepul):
    s6.shapes.add_picture(img_pengepul, Inches(0.8), Inches(2.0), Inches(5.6), Inches(3.2))
    s6.shapes.add_picture(img_pabrik, Inches(6.8), Inches(2.0), Inches(5.7), Inches(3.2))
    
    add_card(s6, 0.8, 5.35, 5.6, 1.45, "Modul Agregator & Bidding Pengepul", [
        "Verifikasi mutu timbangan dan pasar lelang sekam B2B terlindungi atomisitas CAS."
    ], badge_text="QA Playwright Scene 01")
    
    add_card(s6, 6.8, 5.35, 5.7, 1.45, "Portal Operasional Pabrik & Weighbridge", [
        "Jembatan timbang terintegrasi, pemotongan refraksi kadar air, dan batch pirolisis sirkular."
    ], badge_text="QA Playwright Scene 03")
else:
    add_card(s6, 0.8, 2.0, 5.6, 4.8, "Status Kesiapan Teknologi (TKT 3 -> 6)", [
        "Prototype Alpha telah beroperasi penuh sebagai aplikasi web terintegrasi FastAPI + Supabase.",
        "Telah melalui pengujian benchmark concurrency 40 akun paralel tanpa kegagalan koneksi.",
        "Simulasi rute penjemputan pada 36 penggilingan nyata di Sleman dan Klaten.",
        "Target uji operasi di lingkungan riil PT Indmira: November 2026."
    ], badge_text="Kesiapan Produk")
    add_card(s6, 6.8, 2.0, 5.7, 4.8, "Suite Otomasi QA Playwright 1080p", [
        "Scene 01: Modul Bidding Pengepul (Anti-Transaksi Ganda / CAS Guard).",
        "Scene 02: Rute Truk Berbatas Volume (CVRP 0.11 t/m³ & ISO 14083).",
        "Scene 03: Kalkulator Refraksi Kadar Air Timbangan Pabrik (Metrologi Legal).",
        "Scene 04: Neraca Massa Reaktor Pirolisis (Biochar, Biosilika, Biopellet).",
        "Scene 05: Dashboard Metrik Karbon dMRV (Puro.earth & SRN-PPI)."
    ], badge_text="Cakupan Otomasi")

# ==============================================================================
# SLIDE 7: Neraca Massa & Multi-Stream Revenue
# ==============================================================================
s7 = prs.slides.add_slide(blank_layout)
set_slide_bg(s7, LIGHT_BG)
add_header(s7, 7, 12, "Model Pendapatan Sirkular", "Neraca Massa Tertutup & 4 Aliran Pendapatan (Multi-Stream)", "Diversifikasi produk hilir meningkatkan margin kotor pabrik hingga 3,2x lipat dibanding penjualan biomassa mentah.")

add_card(s7, 0.8, 2.0, 2.7, 4.8, "1. Biochar Premium (32.5%)", [
    "Yield 325 kg per ton sekam.",
    "Kandungan C-tertambat >70%.",
    "Aplikasi: Pembenah tanah pertanian sawah & media tanam hortikultura.",
    "Harga jual: Rp 3.500 - Rp 5.000 / kg."
], badge_text="Produk Utama")

add_card(s7, 3.8, 2.0, 2.7, 4.8, "2. Bio-Silika Murni (18.0%)", [
    "Kemurnian 90-95% amorf SiO2.",
    "Ekstraksi alkali / acid-leaching.",
    "Aplikasi: Aditif ban ramah lingkungan (green tire) & semen hijau kuat.",
    "Harga jual: Rp 12.000 - Rp 25.000 / kg."
], badge_text="High-Value Industrial")

add_card(s7, 6.8, 2.0, 2.7, 4.8, "3. Bio-Pellet Co-Firing", [
    "Densitas energi tinggi LHV 14.5 MJ/kg.",
    "Kompaksi sekam sisa pirolisis.",
    "Aplikasi: Bahan bakar co-firing PLTU batubara PT PLN (Persero).",
    "Harga jual: Rp 900 - Rp 1.200 / kg."
], badge_text="Renewable Energy")

add_card(s7, 9.8, 2.0, 2.7, 4.8, "4. Kredit Karbon Terverifikasi", [
    "Puro.earth CORC (Karbon Removal).",
    "SPE-GRK Bursa Karbon IDXCarbon.",
    "Persistensi 100 tahun terverifikasi.",
    "Harga: €110 - €140 per tCO₂e ($120 - $150)."
], badge_text="Carbon Assets")

# ==============================================================================
# SLIDE 8: Ukuran Pasar (TAM / SAM / SOM Biomassa & Karbon)
# ==============================================================================
s8 = prs.slides.add_slide(blank_layout)
set_slide_bg(s8, LIGHT_BG)
add_header(s8, 8, 12, "Peluang Pasar", "Ukuran Pasar Biomassa & Kredit Karbon Asia Tenggara", "Permintaan tinggi dari transisi energi PLN dan pasar kepatuhan iklim global membuka ruang pertumbuhan masif.")

add_card(s8, 0.8, 2.0, 3.6, 4.8, "Total Addressable Market (TAM)", [
    "$14,8 Miliar (Pasar Biomassa & Karbon ASEAN 2030).",
    "48 Juta Ton Sekam Padi di Asia Tenggara per tahun.",
    "Mandat dekarbonisasi industri regional dan regulasi Carbon Tax Singapura & Indonesia."
], badge_text="Pasar Regional")

add_card(s8, 4.8, 2.0, 3.6, 4.8, "Serviceable Addressable Market (SAM)", [
    "$1,2 Miliar (Pasar Indonesia).",
    "10,2 Juta Ton Sekam Padi Nasional.",
    "Kebutuhan biomassa co-firing PLTU PLN sebesar 10,2 juta ton/tahun pada 2025.",
    "Pasar pupuk pembenah tanah pertanian organik nasional."
], badge_text="Pasar Domestik")

add_card(s8, 8.8, 2.0, 3.7, 4.8, "Serviceable Obtainable Market (SOM)", [
    "$42 Juta (Fokus Jawa Tengah & DIY).",
    "1,8 Juta Ton Sekam Padi Jawa Tengah per tahun.",
    "Basis kemitraan awal bersama PT Indmira Global Energi dan 300+ penggilingan lokal.",
    "Target serapan 50.000 ton sekam pada Tahun ke-3."
], badge_text="Target Awal BioChain")

# ==============================================================================
# SLIDE 9: Model Bisnis & Skalabilitas Finansial (Unit Economics)
# ==============================================================================
s9 = prs.slides.add_slide(blank_layout)
set_slide_bg(s9, LIGHT_BG)
add_header(s9, 9, 12, "Model Bisnis", "Unit Economics Kuat & Skalabilitas Ganda (SaaS + Komoditas)", "Struktur pendapatan diversifikasi menjamin stabilitas arus kas dan marjin keuntungan tinggi.")

add_card(s9, 0.8, 2.0, 5.6, 4.8, "Aliran Pendapatan BioChain", [
    "Platform Fee / Throughput: Rp 35.000 per ton sekam yang disalurkan melalui platform.",
    "SaaS Subscription Pabrik: Lisensi bulanan modul CVRP Optimizer & dMRV Engine (Rp 15 Juta/pabrik/bulan).",
    "Revenue Share Kredit Karbon: 15% bagi hasil dari setiap CORC / SPE-GRK yang berhasil diterbitkan.",
    "Premi Mutu Feedstock: Margin transaksi dari sekam terstandarisasi kadar air rendah di bursa B2B."
], badge_text="Monetisasi Ganda")

add_card(s9, 6.8, 2.0, 5.7, 4.8, "Unit Economics per 1 Ton Sekam Padi", [
    "Biaya Beli Sekam di Penggilingan: Rp 350.000 / ton (kadar air terverifikasi).",
    "Biaya Logistik Teroptimasi BioChain: Rp 147.000 / ton (-58% vs konvensional Rp 350.000).",
    "Biaya Operasional Pirolisis: Rp 280.000 / ton.",
    "Total Nilai Produk Tercipta (Biochar + Silika + Karbon): Rp 1.420.000 / ton.",
    "Gross Profit per Ton: Rp 643.000 / ton (Gross Margin 45,3%)."
], badge_text="Kesehatan Finansial")

# ==============================================================================
# SLIDE 10: Kepatuhan Regulasi & Standar Karbon Global
# ==============================================================================
s10 = prs.slides.add_slide(blank_layout)
set_slide_bg(s10, LIGHT_BG)
add_header(s10, 10, 12, "Kepatuhan Regulasi", "Penyelarasan Standar Karbon Puro.earth & SRN-PPI", "BioChain dirancang 'audit-ready' memenuhi regulasi nilai ekonomi karbon domestik dan sertifikasi global.")

add_card(s10, 0.8, 2.0, 2.7, 4.8, "Puro.earth Standard", [
    "Puro Biochar Methodology v3.0.",
    "Persistensi C-sink >100 tahun.",
    "Faktor stabilitas F_perm = 0.80 pada suhu pirolisis reaktor >450°C.",
    "Penerbitan CO₂ Removal Certificate (CORC)."
], badge_text="Standar Global")

add_card(s10, 3.8, 2.0, 2.7, 4.8, "Verra VCS & EBC", [
    "Verra VM0044 Methodology.",
    "European Biochar Certificate (EBC) & International Biochar Initiative (IBI).",
    "Rasio molar H/Corg < 0.7 dan O/Corg < 0.4.",
    "Penetapan batas aman logam berat (PAH/PCDD)."
], badge_text="Sertifikasi EBC/IBI")

add_card(s10, 6.8, 2.0, 2.7, 4.8, "SRN-PPI (KLHK RI)", [
    "Perpres 98/2021 & Perpres 110/2025 (NEK).",
    "Permen LHK 21/2022 Tata Laksana Karbon.",
    "Pencegahan open burning terverifikasi.",
    "Kesesuaian target NDC Indonesia tanpa risiko sanksi double counting."
], badge_text="Regulasi Nasional")

add_card(s10, 9.8, 2.0, 2.7, 4.8, "Bursa Karbon IDXCarbon", [
    "Instrumen Sertifikat Pengurangan Emisi Gas Rumah Kaca (SPE-GRK).",
    "Koneksi dMRV real-time untuk audit Bursa Efek Indonesia (BEI).",
    "Likuiditas perdagangan karbon korporasi domestik dan ekspor resmi."
], badge_text="Monetisasi Bursa")

# ==============================================================================
# SLIDE 11: Proyeksi Finansial & Target Profitabilitas (3 Tahun)
# ==============================================================================
s11 = prs.slides.add_slide(blank_layout)
set_slide_bg(s11, LIGHT_BG)
add_header(s11, 11, 12, "Proyeksi Finansial", "Rencana Finansial 3 Tahun & Target Profitabilitas", "Pertumbuhan eksponensial didorong oleh ekspansi volume sekam dan peningkatan nilai kredit karbon.")

add_metric_callout(s11, 0.8, 2.0, 3.6, 1.8, "Tahun 1 (2027)", "Volume: 8.000 Ton", "Revenue: Rp 5,4 Miliar\nEBITDA: Rp 1,2 Miliar (22%)\nFokus: Sleman-Klaten (Indmira)")
add_metric_callout(s11, 4.8, 2.0, 3.6, 1.8, "Tahun 2 (2028)", "Volume: 25.000 Ton", "Revenue: Rp 18,7 Miliar\nEBITDA: Rp 6,5 Miliar (35%)\nEkspansi: Koridor Solo Raya & Ngawi")
add_metric_callout(s11, 8.8, 2.0, 3.7, 1.8, "Tahun 3 (2029)", "Volume: 60.000 Ton", "Revenue: Rp 51,2 Miliar\nEBITDA: Rp 22,8 Miliar (44%)\nEkspansi: Jawa Timur & Lampung")

add_card(s11, 0.8, 4.1, 11.7, 2.7, "Katalis Pertumbuhan Finansial Utama", [
    "Skalabilitas Logistik: Semakin padat titik penggilingan dalam satu kluster, efisiensi rute CVRP meningkat hingga batas teoritis -65% biaya solar.",
    "Peningkatan Premi Karbon: Harga kredit karbon industri pirolisis (dMRV biochar) diproyeksikan naik dari €110 ke €160 pada 2030 di pasar internasional.",
    "Ekspansi Pabrik Hilir: Replikasi kemitraan dengan 4 pabrik pirolisis dan pengolahan silika baru di Jawa Tengah dan Jawa Timur.",
    "Target Break-Even Point (BEP): Tercapai pada Bulan ke-9 operasi komersial."
], badge_text="Strategic Financial Levers")

# ==============================================================================
# SLIDE 12: Struktur Pendanaan & Alokasi Modal (Ask & Use of Funds)
# ==============================================================================
s12 = prs.slides.add_slide(blank_layout)
set_slide_bg(s12, DARK_BG)
add_header(s12, 12, 12, "Penggalangan Dana", "Kebutuhan Pendanaan Seed Round: $750.000 (Rp 11,5 Miliar)", "Mempercepat transisi TKT 3 ke TKT 6, ekspansi jaringan agregator, dan sertifikasi dMRV Puro.earth.", is_dark=True)

add_card(s12, 0.8, 2.0, 3.6, 4.8, "1. R&D & Software Scaling (35%)", [
    "Pengembangan arsitektur backend dMRV terintegrasi smart contract/blockchain audit.",
    "Integrasi sensor IoT Scout Pro skala massal pada 150 penggilingan.",
    "Penyempurnaan solver OR-Tools CVRP real-time traffic data."
], is_dark=True, badge_text="$262.500")

add_card(s12, 4.8, 2.0, 3.6, 4.8, "2. Ekspansi Operasional & Armada (40%)", [
    "Pengadaan armada truk sewa khusus modifikasi bak volumetrik 24 m³.",
    "Pemasangan jembatan timbang digital terintegrasi di 2 hub sentral baru.",
    "Subsidi permodalan talangan likuiditas timbang terima tunai petani."
], is_dark=True, badge_text="$300.000")

add_card(s12, 8.8, 2.0, 3.7, 4.8, "3. Sertifikasi & Regulasi (25%)", [
    "Biaya audit akreditasi Puro.earth Biochar Methodology & penerbitan CORC.",
    "Pendaftaran proyek mitigasi pada SRN-PPI KLHK & listing perdana IDXCarbon.",
    "Uji laboratorium berkala proksimat & heavy metal ISO 17025."
], is_dark=True, badge_text="$187.500")

# Simpan ke kedua direktori
out_path_v2 = r"D:\IDE\BioChain_PitchDeck_ANGEL2026_v2.pptx"
out_path_inst = r"D:\IDE\BioChain_PitchDeck_ANGEL2026_Institutional_VC.pptx"

prs.save(out_path_inst)
prs.save(out_path_v2)

print(f"Presentation saved successfully to:")
print(f"  1. {out_path_inst}")
print(f"  2. {out_path_v2}")
