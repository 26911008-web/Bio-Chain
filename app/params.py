"""Registry parameter asumsi — satu sumber kebenaran untuk semua angka yang bisa berubah sesuai keadaan.

Setiap angka asumsi bisnis/lapangan (harga, ambang mutu, ongkos, efisiensi, faktor emisi, preset biomassa,
bobot keputusan) didefinisikan di sini dengan default, satuan, batas, penjelasan & rujukan. Nilai aktual
disimpan di tabel `system_parameters` dan diubah lewat menu ⚙️ Parameter (Pabrik/Admin) dengan alasan
wajib; setiap perubahan tercatat di `parameter_changes` (audit).

TIDAK termasuk di sini (sengaja): konstanta fisika (jari-jari bumi, panas laten air, LHV metana) karena
bukan asumsi; parameter teknis algoritma & infrastruktur (iterasi ILS, pool DB) karena bukan kondisi lapangan.

Engine membaca nilai saat dijalankan lewat `P(key)` (cache dalam proses, disegarkan berkala dari DB).
"""

import time
from dataclasses import dataclass, field
from typing import Any

from .config import settings

GROUPS = {
    "harga_mutu": "Harga & Mutu Sekam",
    "rendemen": "Model Rendemen Biochar",
    "sirkular": "Mass Balance & Ekonomi Sirkular",
    "logistik": "Logistik & Rute",
    "pasar": "Pasar B2B",
    "karbon": "Karbon (IPCC 2006)",
    "abu": "Abu ke lahan (logam berat)",
    "proyeksi": "Proyeksi Pasokan",
    "insentif": "Insentif Petani",
    "limbah": "Limbah → Energi",
    "energi": "Energi & IKE",
    "feedstock": "Bobot Perbandingan Feedstock (TOPSIS)",
    "blending": "Blending & Spesifikasi Produk",
    "biomassa": "Preset Biomassa",
    "pabrik": "Pabrik & Biaya Produksi",
    "evaluasi": "Target Evaluasi & Optimasi",
    "pajak": "Pajak Pembelian",
    "biochar_sawah": "Biochar untuk Sawah (Ekonomi Sirkular)",
}


@dataclass(frozen=True)
class Col:
    name: str
    label: str
    unit: str = ""
    min: float | None = None
    max: float | None = None
    kind: str = "number"            # number | text | bool


@dataclass(frozen=True)
class ParamDef:
    key: str
    label: str
    default: Any
    unit: str = ""
    min: float | None = None
    max: float | None = None
    help: str = ""
    source: str = ""
    kind: str = "number"            # number | table | choice
    columns: tuple[Col, ...] = field(default_factory=tuple)
    options: tuple[tuple[str, str], ...] = field(default_factory=tuple)   # choice: (nilai, label)
    required_input: bool = False    # True = tanpa angka bawaan; wajib diisi pengguna sebelum dipakai

    @property
    def group(self) -> str:
        return self.key.split(".", 1)[0]


def _n(key, label, default, unit="", lo=None, hi=None, help="", source=""):
    return ParamDef(key, label, default, unit, lo, hi, help, source)


BIOMASS_COLS = (
    Col("id", "Kode", kind="text"), Col("name", "Nama", kind="text"),
    Col("moisture", "Kadar air", "% bb", 0, 95), Col("ash", "Abu", "% bk", 0, 60),
    Col("volatile_matter", "VM", "% bk", 0, 100), Col("fixed_carbon", "FC", "% bk", 0, 100),
    Col("hydrogen", "H", "% bk", 0, 15), Col("cn_ratio", "C/N", "", 1, 1000),
    Col("bmp_m3_ch4_per_t_vs", "BMP", "m³ CH₄/t VS", 0, 600),
    Col("lignocellulosic", "Lignoselulosa", kind="bool"),
    Col("price_rp_per_ton", "Harga", "Rp/ton", 0, 50_000_000),
)
BLEND_COLS = (
    Col("id", "Kode", kind="text"), Col("name", "Nama", kind="text"),
    Col("cost_per_ton", "Harga", "Rp/ton", 0, 50_000_000), Col("stock_ton", "Stok", "ton", 0, 1_000_000),
    Col("moisture", "Kadar air", "%", 0, 60), Col("ash", "Abu", "%", 0, 60), Col("fixed_carbon", "FC", "%", 0, 100),
)

_SRC_PHYLLIS = "Nilai tipikal literatur (Phyllis2 ECN/TNO; Vassilev 2010) — ganti hasil uji lab"

DEFS: list[ParamDef] = [
    # ---------------- Harga & mutu sekam (Engine ② + verifikasi pengepul)
    _n("harga_mutu.base_price_per_kg", "Harga dasar sekam", settings.BASE_PRICE_PER_KG, "Rp/kg", 1, 10_000,
       "Harga sebelum pengali grade (pembelian non-lelang)."),
    _n("harga_mutu.mult_A", "Pengali harga Grade A", 1.15, "×", 0, 3),
    _n("harga_mutu.mult_B", "Pengali harga Grade B", 1.05, "×", 0, 3),
    _n("harga_mutu.mult_C", "Pengali harga Grade C", 1.00, "×", 0, 3),
    _n("harga_mutu.grade_A_min", "Skor minimum Grade A", 80, "skor", 0, 100),
    _n("harga_mutu.grade_B_min", "Skor minimum Grade B", 60, "skor", 0, 100),
    _n("harga_mutu.moisture_reject", "Batas tolak kadar air", 25.0, "% bb", 5, 60),
    _n("harga_mutu.contamination_reject", "Batas tolak kontaminan", 10.0, "%", 1, 50),
    _n("harga_mutu.moisture_best", "Kadar air ideal (skor penuh)", 10.0, "% bb", 0, 30),
    _n("harga_mutu.contamination_best", "Kontaminan ideal (skor penuh)", 1.0, "%", 0, 10),
    _n("harga_mutu.fc_best", "Fixed carbon ideal", 17.0, "%", 0, 40),
    _n("harga_mutu.fc_worst", "Fixed carbon terendah (skor 0)", 8.0, "%", 0, 40),
    _n("harga_mutu.ash_ideal_min", "Batas bawah abu ideal", 14.0, "% bk", 0, 40),
    _n("harga_mutu.ash_ideal_max", "Batas atas abu ideal", 20.0, "% bk", 0, 40),
    _n("harga_mutu.w_moisture", "Bobot skor: kadar air", 0.35, "", 0, 1, "Bobot dinormalisasi otomatis (jumlah = 1)."),
    _n("harga_mutu.w_contamination", "Bobot skor: kontaminan", 0.30, "", 0, 1),
    _n("harga_mutu.w_ash", "Bobot skor: kadar abu", 0.15, "", 0, 1),
    _n("harga_mutu.w_fc", "Bobot skor: fixed carbon", 0.20, "", 0, 1),
    ParamDef("harga_mutu.pricing_method", "Metode harga beli dari petani (jalur rute)", "basis_kering", kind="choice",
             options=(("basis_kering", "Basis bahan kering: harga dasar × (1−M)/(1−M_acuan) × (1−kontaminan) × bonus grade"),
                      ("pengali_grade", "Pengali grade saja (harga dasar × pengali A/B/C)")),
             help="Basis kering menghapus 'tebing harga' di batas grade: setiap 1% air dibayar sesuai bahan kering, "
                  "sama dengan rumus QC pabrik (jalur Delivery Request).",
             source="ISO 17225-1 / praktik dagang biomassa: harga per ton bahan kering"),
    _n("harga_mutu.reference_moisture_pct", "Kadar air acuan harga dasar petani", 12.0, "% bb", 0, 40,
       "Harga dasar berlaku pada kadar air ini; lebih basah → harga turun proporsional bahan kering."),
    _n("harga_mutu.moisture_mold_risk_pct", "Ambang risiko jamur (wajib keringkan / angkut cepat)", 15.0, "% bb", 5, 40,
       "Di atas ini sekam ditandai 'risiko jamur': prioritas jemput & larangan simpan tertutup > 48 jam.",
       source="Proksi FAO (gabah): jamur simpan naik pada 14,5–18,3%; simpan aman 12–14%. Belum ada standar khusus sekam."),
    # ---------------- Rendemen
    _n("rendemen.yield_300c", "Rendemen biochar @300 °C", 57.13, "% bk", 1, 100,
       source="Slow pyrolysis sekam padi (literatur)"),
    _n("rendemen.yield_700c", "Rendemen biochar @700 °C", 37.19, "% bk", 1, 100),
    _n("rendemen.ref_ash", "Kadar abu acuan kalibrasi", 18.0, "% bk", 1, 40),
    _n("rendemen.ash_yield_coef", "Koefisien koreksi abu", 0.5, "", 0, 2,
       "Kenaikan rendemen per 1% abu di atas acuan (abu tertahan di char)."),
    _n("rendemen.sio2_fraction_of_ash", "Fraksi SiO₂ dalam abu", 0.90, "fraksi", 0.5, 1),
    # ---------------- Sirkular
    _n("sirkular.shrinkage_tolerance_pct", "Toleransi susut pengepul→pabrik", settings.SHRINKAGE_TOLERANCE_PCT,
       "%", 0, 50, "Selisih timbangan di atas ini ditandai untuk auditor."),
    _n("sirkular.estimate_tolerance_pct", "Toleransi taksiran petani vs timbangan", settings.ESTIMATE_TOLERANCE_PCT,
       "%", 0, 100),
    _n("sirkular.farmer_return_share", "Porsi biochar dikembalikan ke petani", settings.BIOCHAR_FARMER_RETURN_SHARE,
       "fraksi", 0, 1, "Dibagi proporsional berat sekam yang diterima pabrik."),
    # ---------------- Logistik
    _n("logistik.road_factor", "Faktor jalan (jarak jalan ÷ jarak lurus)", 1.3, "×", 1, 3,
       "Ganti dengan rasio aktual dari OSRM/GPS armada."),
    _n("logistik.vehicle_m3", "Volume bak truk default", 30.0, "m³", 1, 200),
    _n("logistik.bulk_density_kg_m3", "Densitas curah sekam", 110.0, "kg/m³", 50, 400),
    _n("logistik.cost_per_km", "Biaya angkut truk", 4_000.0, "Rp/km", 0, 100_000, "BBM + sopir + penyusutan."),
    _n("logistik.time_budget_ms", "Anggaran waktu optimasi rute", 250, "ms", 10, 2_000),
    _n("logistik.vehicle_payload_kg", "Muatan maksimum truk (berat)", 5_000.0, "kg", 100, 40_000,
       "Dipakai sebagai pembagi faktor muat untuk konsumsi BBM (bukan pembatas rute; sekam terbatas volume)."),
    _n("logistik.fuel_l_per_km_empty", "Konsumsi BBM truk kosong", 0.15, "L/km", 0.01, 2,
       "ASUMSI — wajib diganti catatan BBM armada aktual (L ÷ km saat kosong).",
       source="ISO 14083:2023 mengutamakan data primer; GIZ 2022: pick-up Indonesia rata-rata 7,7 L/100 km"),
    _n("logistik.fuel_l_per_km_full", "Konsumsi BBM truk muatan penuh", 0.20, "L/km", 0.01, 2,
       "ASUMSI — konsumsi pada muatan = Muatan maksimum. Di antara kosong–penuh diinterpolasi linear.",
       source="GLEC v3.2 / HBEFA: konsumsi linear terhadap faktor muat"),
    _n("logistik.gps_max_accuracy_m", "Akurasi GPS maksimum yang dipakai", 50.0, "m", 5, 1_000,
       "Titik dengan radius akurasi lebih besar dibuang dari perhitungan jarak."),
    _n("logistik.gps_max_speed_kmh", "Kecepatan maksimum wajar truk", 110.0, "km/jam", 20, 200,
       "Lompatan antar titik di atas kecepatan ini dianggap glitch GPS dan dibuang."),
    _n("logistik.gps_min_step_m", "Langkah GPS minimum", 15.0, "m", 0, 500,
       "Pergerakan lebih kecil dianggap diam (jitter) agar jarak tidak membengkak saat truk berhenti."),
    _n("logistik.gps_gap_road_factor", "Faktor jalan untuk celah GPS", 1.3, "×", 1, 3,
       "Bila GPS mati di tengah perjalanan, celah antar titik diisi jarak lurus × faktor ini (ditandai estimasi)."),
    _n("logistik.pickup_geofence_m", "Radius geofence pickup", 500.0, "m", 50, 20_000,
       "Scan QR lebih jauh dari ini terhadap titik penggilingan ditandai untuk auditor (tidak diblokir: "
       "GPS di desa bisa meleset & lokasi penggilingan bisa belum akurat)."),
    ParamDef("logistik.qr_legacy_policy", "QR lot lama (tanpa tanda tangan, sebelum F14)", "terima_tandai", kind="choice",
             options=(("terima_tandai", "Terima, tandai untuk auditor (masa transisi nota/karung yang sudah tercetak)"),
                      ("tolak", "Tolak — minta pengepul/petani cetak ulang QR baru dari aplikasi")),
             help="QR baru BIO-XXXXXXXX-TTTTTT bertanda tangan HMAC dan bisa dicek offline di HP supir. "
                  "Ganti ke 'tolak' setelah semua lot lama terangkut."),
    _n("logistik.cancel_fee_per_km", "Ongkos batal per km (dibebankan ke pembatal)", 4_000.0, "Rp/km", 0, 100_000,
       "Kompensasi jarak kosong (deadhead) truk bila pengepul membatalkan setelah truk berangkat."),
    # ---------------- Pasar B2B
    _n("pasar.farmer_truck_kg", "Kapasitas angkut petani (skema antar)", 2_000.0, "kg", 50, 20_000),
    _n("pasar.farmer_cost_per_km", "Ongkos angkut petani", 3_000.0, "Rp/km", 0, 100_000),
    _n("pasar.default_resale_price_per_kg", "Harga jual pengepul ke pabrik (default)", 560.0, "Rp/kg", 1, 10_000),
    _n("pasar.default_margin_per_kg", "Margin pengepul (default)", 30.0, "Rp/kg", 0, 5_000),
    _n("pasar.default_margin_pct", "Margin pengepul (default, persen)", 5.0, "% harga jual", 0, 50,
       "Dipakai penasihat tawaran bila pengepul mengisi margin dalam persen (bisa diubah ± di layar)."),
    _n("pasar.dp_max_pct", "Uang muka (DP) maksimum", 30.0, "% perkiraan nilai lot", 0, 100,
       "Batas DP pengepul ke petani; DP dipotong otomatis saat pelunasan, hangus untuk petani bila pengepul batal sepihak."),
    _n("pasar.farmer_payment_due_days", "Batas waktu bayar petani", 3, "hari", 0, 60,
       "Lot terverifikasi yang belum dibayar melewati batas ini ditandai 'terlambat' di menu Pembayaran petani."),
    # ---------------- Karbon
    ParamDef("karbon.price_per_tco2_rp", "Harga pasar karbon / NEK", None, "Rp/tCO₂e", 0, 10_000_000,
             help="Wajib diisi; dasar penilaian nilai ekonomi karbon. Contoh IDXCarbon: Rp 69.000–300.000/tCO₂e.",
             source="Pasar karbon / IDXCarbon", required_input=True),
    _n("karbon.coal_ef_kg_co2_per_gj", "Faktor emisi batubara", 96.1, "kgCO₂/GJ", 50, 150,
       source="IPCC 2006 Vol.2 Ch.2 (sub-bituminous)"),
    _n("karbon.husk_hhv_mj_kg", "Nilai kalor sekam (basis kering)", 13.5, "MJ/kg", 5, 25),
    _n("karbon.coal_hhv_mj_kg", "Nilai kalor batubara", 22.0, "MJ/kg", 10, 35),
    _n("karbon.boiler_efficiency", "Efisiensi boiler", 0.85, "fraksi", 0.3, 1),
    _n("karbon.transport_ef_kg_co2_per_tkm", "Faktor emisi angkutan truk", 0.062, "kgCO₂/t·km", 0, 1),
    _n("karbon.diesel_ttw_kg_co2e_per_l", "Emisi solar fosil tank-to-wheel", 2.68, "kgCO₂e/L", 1, 4,
       source="GLEC Framework v3.2 (2025) Tabel faktor bahan bakar Eropa: 3,22 kg/kg × 0,832 kg/L ≈ 2,68"),
    _n("karbon.diesel_wtt_kg_co2e_per_l", "Emisi hulu solar fosil well-to-tank", 0.81, "kgCO₂e/L", 0, 2,
       source="GLEC Framework v3.2 (2025): WTW 4,19 − TTW 3,22 kg/kg × 0,832 kg/L ≈ 0,81"),
    _n("karbon.fame_wtw_kg_co2e_per_l", "Emisi biodiesel (FAME) well-to-wheel", 1.16, "kgCO₂e/L", 0, 4,
       "CO₂ biogenik pembakaran FAME = 0 (netral); yang dihitung emisi hulu budidaya & pengolahan. "
       "Nilai GLEC untuk campuran rapeseed/UCO/kedelai; FAME sawit dengan alih guna lahan bisa jauh lebih tinggi — "
       "ganti dengan nilai LCA pemasok bila tersedia.",
       source="GLEC Framework v3.2: 35,4 gCO₂e/MJ × ±32,7 MJ/L"),
    _n("karbon.open_burning_share", "Porsi sekam yang dibakar terbuka (baseline)", 0.60, "fraksi", 0, 1,
       "Skenario tanpa proyek: sebagian sekam dibakar di tepi sawah. Ganti dengan survei wilayah.",
       source="SOP Bio-Chain §1.1 (>60% dibakar/dibuang); perlu survei baseline lokal"),
    _n("karbon.open_burning_combustion_factor", "Faktor pembakaran (CF) residu padi", 0.80, "fraksi", 0, 1,
       source="IPCC 2006 Vol.4 Ch.2 Tabel 2.6 (residu padi)"),
    _n("karbon.open_burning_ch4_g_per_kg", "EF CH₄ pembakaran terbuka", 2.7, "g/kg bk", 0, 20,
       source="IPCC 2006 Vol.4 Ch.2 Tabel 2.5 (residu pertanian)"),
    _n("karbon.open_burning_n2o_g_per_kg", "EF N₂O pembakaran terbuka", 0.07, "g/kg bk", 0, 2,
       source="IPCC 2006 Vol.4 Ch.2 Tabel 2.5 (residu pertanian)"),
    _n("karbon.gwp_ch4", "GWP-100 CH₄", 28.0, "×", 1, 100, source="IPCC AR5 (AR6: 27,9 non-fosil)"),
    _n("karbon.gwp_n2o", "GWP-100 N₂O", 265.0, "×", 1, 400, source="IPCC AR5 (AR6: 273)"),
    _n("karbon.biochar_c_org_fraction", "Fraksi C organik biochar sekam (F_C)", 0.49, "fraksi", 0.1, 0.95,
       "Biochar sekam kaya abu (SiO₂) sehingga C organik jauh di bawah biochar kayu. Ganti hasil uji CHN lab per batch.",
       source="IPCC 2019 Refinement Vol.4 Ch.2 Ap.4 — default sekam/jerami (verifikasi dengan uji lab)"),
    _n("karbon.grid_ef_kg_co2_per_kwh", "Faktor emisi listrik grid", 0.87, "kgCO₂/kWh", 0, 2,
       "Grid Jawa-Madura-Bali; perbarui sesuai publikasi faktor emisi GRK sistem ketenagalistrikan ESDM terbaru.",
       source="Kepmen ESDM No. 163.K/HK.02/MEM.S/2021 (combined margin JAMALI, data 2019: 0,87 tCO₂/MWh) — "
              "bukan batas PTBAE PLTU 0,911–1,297 (docs/15 §4)"),
    _n("karbon.biochar_moisture_pct", "Kadar air biochar saat ditimbang (bila belum diuji lab)", 10.0, "% bb", 0, 60,
       "Biochar sering di-quench air; karbon dihitung atas massa KERING. Ganti hasil uji lab per batch.",
       source="Puro.earth Biochar Methodology 2025 & VM0044: kuantifikasi atas massa kering biochar"),
    _n("karbon.uncertainty_deduction_pct", "Potongan ketidakpastian klaim removal", 10.0, "%", 0, 50,
       "Potongan konservatif selama F_C, H/C_org & F_perm belum dari uji lab (CI 90%). Turunkan setelah data lab tersedia.",
       source="Pendekatan pengurangan ketidakpastian VM0044 (nilai internal konservatif — verifikasi ke VVB)"),
    _n("karbon.h_corg_max", "Batas rasio molar H/C-org biochar untuk klaim", 0.7, "mol/mol", 0.1, 1.0,
       "Klaim removal (F11) ditolak bila hasil lab H/C-org di atas batas ini: karbon belum cukup stabil.",
       source="Puro.earth Biochar Methodology 2025 (syarat H/C_org < 0,7); EBC 2023 §; IPCC 2019 Ref. Vol.4 Ap.4"),
    _n("abu.limit_as_ppm", "Batas As abu ke lahan", 10.0, "mg/kg", 0, 1000, "Abu lulus hanya bila semua logam terukur ≤ batas.", source="Kepmentan No. 261/KPTS/SR.310/M/4/2019 (persyaratan teknis minimal pupuk organik & pembenah tanah) — docs/15 §6a"),
    _n("abu.limit_hg_ppm", "Batas Hg abu ke lahan", 1.0, "mg/kg", 0, 100, source="Kepmentan No. 261/KPTS/SR.310/M/4/2019 (persyaratan teknis minimal pupuk organik & pembenah tanah) — docs/15 §6a"),
    _n("abu.limit_pb_ppm", "Batas Pb abu ke lahan", 50.0, "mg/kg", 0, 1000, source="Kepmentan No. 261/KPTS/SR.310/M/4/2019 (persyaratan teknis minimal pupuk organik & pembenah tanah) — docs/15 §6a"),
    _n("abu.limit_cd_ppm", "Batas Cd abu ke lahan", 2.0, "mg/kg", 0, 100, source="Kepmentan No. 261/KPTS/SR.310/M/4/2019 (persyaratan teknis minimal pupuk organik & pembenah tanah) — docs/15 §6a"),
    _n("abu.limit_cr_ppm", "Batas Cr abu ke lahan", 180.0, "mg/kg", 0, 2000, source="Kepmentan No. 261/KPTS/SR.310/M/4/2019 (persyaratan teknis minimal pupuk organik & pembenah tanah) — docs/15 §6a"),
    _n("abu.limit_ni_ppm", "Batas Ni abu ke lahan", 50.0, "mg/kg", 0, 1000, source="Kepmentan No. 261/KPTS/SR.310/M/4/2019 (persyaratan teknis minimal pupuk organik & pembenah tanah) — docs/15 §6a"),
    _n("karbon.pyrolysis_ch4_kg_per_t_biochar", "Emisi CH₄ reaktor per t biochar", 0.0, "kg CH₄/t", 0, 100,
       "0 = BELUM DIUKUR → klaim ditandai belum lengkap. Isi hasil uji emisi cerobong/flare (FID/GC).",
       source="Puro 2025 / EBC C-Sink: emisi CH₄ pirolisis wajib dihitung (GWP-100)"),
    _n("karbon.lpg_ef_kg_co2e_per_kg", "Faktor emisi LPG (start-up/pengering)", 2.985, "kgCO₂/kg", 0, 5,
       source="IPCC 2006 Vol.2 Tabel 1.2 & 2.2: 63,1 kgCO₂/GJ × NCV 47,3 MJ/kg"),
    _n("karbon.biodiesel_blend_pct", "Porsi biodiesel dalam solar (B-mandatori)", 40.0, "%", 0, 100,
       source="Kepmen ESDM 341.K/EK.01/MEM.E/2024 — mandatori B40 sejak 1 Jan 2025"),
    # ---------------- Proyeksi
    _n("proyeksi.harvest_area_ha", "Luas panen wilayah layanan", 600.0, "ha", 1, 1_000_000,
       "Dipakai dasbor proyeksi 30 hari pabrik."),
    _n("proyeksi.productivity_ton_per_ha", "Produktivitas gabah", 5.3, "ton/ha", 1, 15, source="BPS"),
    _n("proyeksi.husk_ratio", "Rasio sekam terhadap gabah", 0.20, "fraksi", 0.1, 0.35),
    _n("proyeksi.seasonal_amplitude", "Amplitudo musiman", 0.40, "", 0, 1),
    _n("proyeksi.peak_month_1", "Bulan puncak panen 1", 4, "bulan", 1, 12),
    _n("proyeksi.peak_month_2", "Bulan puncak panen 2", 9, "bulan", 1, 12),
    _n("proyeksi.history_weight", "Bobot data historis", 0.6, "fraksi", 0, 1),
    _n("proyeksi.ci_width_model", "Lebar selang (model saja)", 0.25, "±fraksi", 0, 1),
    _n("proyeksi.ci_width_history", "Lebar selang (dengan histori)", 0.15, "±fraksi", 0, 1),
    # ---------------- Insentif
    _n("insentif.xp_grade_A", "XP per ton Grade A (×10)", 3.0, "", 0, 20),
    _n("insentif.xp_grade_B", "XP per ton Grade B (×10)", 2.0, "", 0, 20),
    _n("insentif.xp_grade_C", "XP per ton Grade C (×10)", 1.0, "", 0, 20),
    _n("insentif.bonus_on_time", "Bonus tepat waktu", 0.20, "fraksi", 0, 5),
    _n("insentif.bonus_lean_season", "Bonus pasokan musim paceklik", 0.50, "fraksi", 0, 5),
    _n("insentif.tier_aktif_xp", "Ambang XP Pemasok Aktif", 100, "XP", 1, 1_000_000),
    _n("insentif.tier_emas_xp", "Ambang XP Mitra Emas", 500, "XP", 1, 1_000_000),
    _n("insentif.tier_platinum_xp", "Ambang XP Mitra Platinum", 1500, "XP", 1, 1_000_000),
    _n("insentif.bonus_price_aktif", "Pengali harga Pemasok Aktif", 1.05, "×", 1, 3),
    _n("insentif.bonus_price_emas", "Pengali harga Mitra Emas", 1.12, "×", 1, 3),
    _n("insentif.bonus_price_platinum", "Pengali harga Mitra Platinum", 1.20, "×", 1, 3),
    # ---------------- Limbah → energi
    _n("limbah.eta_boiler_heat", "Efisiensi boiler → panas proses", 0.80, "fraksi", 0.1, 1),
    _n("limbah.eta_steam_chp_el", "Efisiensi listrik CHP uap", 0.18, "fraksi", 0.01, 0.6),
    _n("limbah.eta_gasifier_engine_el", "Efisiensi listrik gasifier + mesin", 0.25, "fraksi", 0.01, 0.6),
    _n("limbah.eta_ad_chp_el", "Efisiensi listrik mesin biogas", 0.35, "fraksi", 0.01, 0.6),
    _n("limbah.eta_el_steam_small", "Prototipe 2: η listrik turbin uap kecil", 0.22, "fraksi", 0.05, 0.45,
       "Grate/stoker + turbin uap 1–10 MWe: 15–25 % (≤5 MWe cenderung 15–20 %).", source="IRENA 2012 Biomass for Power Generation; ERIA 2019 Ch.5 (docs/15 §4)"),
    _n("limbah.eta_el_integrated", "Prototipe 2: η listrik sistem terintegrasi", 0.28, "fraksi", 0.05, 0.5,
       "Gasifier + mesin gas / CHP terintegrasi: 20–28 % (umpan MC < 15–20 %).", source="IRENA 2012 Biomass for Power Generation; ERIA 2019 Ch.5 (docs/15 §4); IEA Bioenergy Task 33"),
    _n("limbah.eta_el_cofiring", "Prototipe 2: η listrik co-firing PLTU", 0.36, "fraksi", 0.2, 0.5,
       "Co-firing di PLTU 36–44 % (batas bawah dipakai: PLTU subkritis Jawa).",
       source="IRENA-ETSAP Tech Brief E21 Biomass Co-firing (2013)"),
    _n("limbah.cofiring_gcv_min_kcal", "Prototipe 2: GCV ar minimum co-firing", 3009.0, "kcal/kg", 1000, 6000,
       source="Spesifikasi woodchip PLTU Teluk Sirih (PT Indonesia Power) — docs/15 §5"),
    _n("limbah.cofiring_mc_max", "Prototipe 2: kadar air maks co-firing", 25.0, "%", 5, 60,
       "Woodchip TM ≤ 25 % (serbuk gergaji ≤ 45 % pada kontrak tertentu).", source="PLTU Teluk Sirih — docs/15 §5"),
    _n("limbah.cofiring_max_km", "Prototipe 2: jarak maks ke PLTU", 150.0, "km", 1, 2000,
       "Di atas jarak ini biaya & emisi angkut biasanya menghapus manfaat co-firing (biomassa curah densitas rendah)."),
    _n("limbah.drying_mj_per_kg_water", "Energi pengeringan", 3.0, "MJ/kg air", 2.443, 10,
       "≥ panas laten 2,443 MJ/kg + rugi pengering."),
    _n("limbah.pellet_kwh_per_ton", "Listrik densifikasi pellet", 120.0, "kWh/ton", 0, 500),
    _n("limbah.pyrolysis_temp_c", "Suhu pirolisis acuan", 500.0, "°C", 300, 800),
    _n("limbah.operating_days", "Hari operasi per tahun (default)", 300, "hari", 1, 366),
    _n("limbah.biochar_hhv_mj_kg", "Nilai kalor biochar", 25.0, "MJ/kg", 5, 35),
    # ---------------- Energi & IKE
    _n("energi.tariff_rp_per_kwh", "Tarif listrik rata-rata", 1_444.7, "Rp/kWh", 1, 10_000),
    _n("energi.anomaly_z", "Ambang anomali (robust z)", 2.5, "z", 1, 10, source="Iglewicz & Hoaglin 1993"),
    _n("energi.diesel_mj_per_l", "Nilai kalor neto solar", 36.0, "MJ/L", 30, 40,
       source="IPCC 2006 Vol.2 Tabel 1.2: NCV gas/diesel oil 43,0 MJ/kg × densitas 0,84 kg/L"),
    _n("energi.sec_window", "Prototipe 3: jendela rata-rata bergerak", 7.0, "log", 3, 60),
    _n("energi.sec_sigma_warn", "Prototipe 3: batas peringatan", 2.0, "σ", 1, 6, source="Montgomery 2019 (Shewhart ±2σ peringatan)"),
    _n("energi.sec_sigma_action", "Prototipe 3: batas aksi", 3.0, "σ", 1.5, 8, source="Montgomery 2019 (±3σ aksi)"),
    _n("energi.base_load_alert_share", "Ambang beban dasar tinggi", 0.30, "fraksi", 0, 1),
    _n("energi.ike_ac_1", "IKE AC: batas Sangat efisien", 8.5, "kWh/m²/bln", 0, 100, source="Permen ESDM 13/2012 (regulasi)"),
    _n("energi.ike_ac_2", "IKE AC: batas Efisien", 14.0, "kWh/m²/bln", 0, 100, source="Permen ESDM 13/2012 (regulasi)"),
    _n("energi.ike_ac_3", "IKE AC: batas Cukup efisien", 18.5, "kWh/m²/bln", 0, 100, source="Permen ESDM 13/2012 (regulasi)"),
    _n("energi.ike_non_ac_1", "IKE non-AC: batas Sangat efisien", 3.4, "kWh/m²/bln", 0, 100, source="Permen ESDM 13/2012 (regulasi)"),
    _n("energi.ike_non_ac_2", "IKE non-AC: batas Efisien", 5.6, "kWh/m²/bln", 0, 100, source="Permen ESDM 13/2012 (regulasi)"),
    _n("energi.ike_non_ac_3", "IKE non-AC: batas Cukup efisien", 7.4, "kWh/m²/bln", 0, 100, source="Permen ESDM 13/2012 (regulasi)"),
    # ---------------- Bobot TOPSIS (dinormalisasi per tujuan)
    _n("feedstock.biochar_w_yield", "Biochar: bobot rendemen", 0.30, "", 0, 1),
    _n("feedstock.biochar_w_fc", "Biochar: bobot fixed carbon", 0.20, "", 0, 1),
    _n("feedstock.biochar_w_cost", "Biochar: bobot biaya per ton biochar", 0.30, "", 0, 1),
    _n("feedstock.biochar_w_moisture", "Biochar: bobot kadar air", 0.10, "", 0, 1),
    _n("feedstock.biochar_w_ash", "Biochar: bobot kadar abu", 0.10, "", 0, 1),
    _n("feedstock.pellet_w_lhv", "Pellet: bobot nilai kalor", 0.30, "", 0, 1),
    _n("feedstock.pellet_w_ash", "Pellet: bobot kadar abu", 0.30, "", 0, 1),
    _n("feedstock.pellet_w_moisture", "Pellet: bobot kadar air", 0.15, "", 0, 1),
    _n("feedstock.pellet_w_cost", "Pellet: bobot biaya per GJ", 0.25, "", 0, 1),
    _n("feedstock.burn_w_lhv", "Pembakaran: bobot nilai kalor", 0.30, "", 0, 1),
    _n("feedstock.burn_w_cost", "Pembakaran: bobot biaya per GJ", 0.35, "", 0, 1),
    _n("feedstock.burn_w_ash", "Pembakaran: bobot kadar abu", 0.20, "", 0, 1),
    _n("feedstock.burn_w_moisture", "Pembakaran: bobot kadar air", 0.15, "", 0, 1),
    # ---------------- Blending & spesifikasi produk
    ParamDef("blending.drying_cost_rp_per_kg_water", "Biaya pengeringan per kg air diuapkan", None, "Rp/kg air", 0, 10_000,
             required_input=True,
             help="Prototipe 1 (blend bahan bakar): biaya pengering (BBM/listrik/tenaga) per kg air yang diuapkan. "
                  "Acuan energi ±3 MJ/kg air (≈1,2× panas laten); isi sesuai harga bahan bakar pengering Anda.",
             source="Panas laten 2,443 MJ/kg (ISO 18125) × rugi pengering ±1,2 — engines/waste_energy.py"),
    _n("blending.ai_max_kg_gj", "Batas indeks alkali campuran", 0.34, "kg/GJ", 0.05, 2.0,
       "Di atas batas → campuran ditolak optimizer (>0,34 hampir pasti terak; 0,17–0,34 peringatan).",
       source="Miles dkk. 1996 NREL/TP-433-8142; Zhu dkk. 2014 Front. Energy Res. 2:7 (docs/15 §2)"),
    _n("blending.biochar_tanah_moisture_max", "Biochar tanah: kadar air maks", 14.0, "%", 0, 60),
    _n("blending.biochar_tanah_ash_max", "Biochar tanah: abu maks", 16.0, "%", 0, 60),
    _n("blending.biochar_tanah_fc_min", "Biochar tanah: FC min", 15.0, "%", 0, 100),
    _n("blending.qlc_moisture_max", "Quick Light Charcoal: kadar air maks", 12.0, "%", 0, 60),
    _n("blending.qlc_ash_max", "Quick Light Charcoal: abu maks", 8.0, "%", 0, 60),
    _n("blending.qlc_fc_min", "Quick Light Charcoal: FC min", 18.0, "%", 0, 100),
    ParamDef("blending.feedstocks", "Feedstock tersedia untuk blending", kind="table", columns=BLEND_COLS, default=[
        {"id": "sekam", "name": "Sekam padi", "cost_per_ton": 400_000, "stock_ton": 120, "moisture": 11, "ash": 18, "fixed_carbon": 15},
        {"id": "bonggol", "name": "Bonggol jagung", "cost_per_ton": 650_000, "stock_ton": 40, "moisture": 12, "ash": 2, "fixed_carbon": 17},
        {"id": "serbuk", "name": "Serbuk kayu", "cost_per_ton": 550_000, "stock_ton": 30, "moisture": 15, "ash": 1.5, "fixed_carbon": 16},
        {"id": "tempurung", "name": "Tempurung kelapa", "cost_per_ton": 2_000_000, "stock_ton": 15, "moisture": 10, "ash": 1, "fixed_carbon": 22},
    ], help="Harga & stok aktual di pabrik; properti dari uji lab."),
    # ---------------- Preset biomassa
    ParamDef("biomassa.presets", "Preset karakteristik biomassa", kind="table", columns=BIOMASS_COLS, source=_SRC_PHYLLIS,
             help="Dipakai Engine ⑧ & ⑨ bila pengguna memilih preset.", default=[
        {"id": "sekam_padi", "name": "Sekam padi", "moisture": 11, "ash": 18.0, "volatile_matter": 64.0, "fixed_carbon": 18.0, "hydrogen": 5.0, "cn_ratio": 80, "bmp_m3_ch4_per_t_vs": 50, "lignocellulosic": True, "price_rp_per_ton": 400_000},
        {"id": "jerami_padi", "name": "Jerami padi", "moisture": 15, "ash": 15.0, "volatile_matter": 68.0, "fixed_carbon": 17.0, "hydrogen": 5.5, "cn_ratio": 60, "bmp_m3_ch4_per_t_vs": 230, "lignocellulosic": True, "price_rp_per_ton": 300_000},
        {"id": "tongkol_jagung", "name": "Tongkol jagung", "moisture": 12, "ash": 2.0, "volatile_matter": 80.0, "fixed_carbon": 18.0, "hydrogen": 6.0, "cn_ratio": 90, "bmp_m3_ch4_per_t_vs": 250, "lignocellulosic": True, "price_rp_per_ton": 650_000},
        {"id": "tempurung_kelapa", "name": "Tempurung kelapa", "moisture": 10, "ash": 1.0, "volatile_matter": 75.0, "fixed_carbon": 24.0, "hydrogen": 6.0, "cn_ratio": 130, "bmp_m3_ch4_per_t_vs": 40, "lignocellulosic": True, "price_rp_per_ton": 2_000_000},
        {"id": "serbuk_gergaji", "name": "Serbuk gergaji", "moisture": 15, "ash": 1.5, "volatile_matter": 82.0, "fixed_carbon": 16.5, "hydrogen": 6.0, "cn_ratio": 400, "bmp_m3_ch4_per_t_vs": 40, "lignocellulosic": True, "price_rp_per_ton": 550_000},
        {"id": "tkks", "name": "Tandan kosong sawit", "moisture": 60, "ash": 5.0, "volatile_matter": 79.0, "fixed_carbon": 16.0, "hydrogen": 6.0, "cn_ratio": 50, "bmp_m3_ch4_per_t_vs": 200, "lignocellulosic": True, "price_rp_per_ton": 250_000},
        {"id": "ampas_tebu", "name": "Ampas tebu (bagas)", "moisture": 50, "ash": 3.0, "volatile_matter": 82.0, "fixed_carbon": 15.0, "hydrogen": 6.0, "cn_ratio": 110, "bmp_m3_ch4_per_t_vs": 220, "lignocellulosic": True, "price_rp_per_ton": 300_000},
        {"id": "kotoran_sapi", "name": "Kotoran sapi", "moisture": 85, "ash": 20.0, "volatile_matter": 66.0, "fixed_carbon": 14.0, "hydrogen": 5.0, "cn_ratio": 20, "bmp_m3_ch4_per_t_vs": 220, "lignocellulosic": False, "price_rp_per_ton": 50_000},
        {"id": "sisa_makanan", "name": "Sisa makanan / sayur pasar", "moisture": 80, "ash": 7.0, "volatile_matter": 85.0, "fixed_carbon": 8.0, "hydrogen": 7.0, "cn_ratio": 17, "bmp_m3_ch4_per_t_vs": 420, "lignocellulosic": False, "price_rp_per_ton": 0},
    ]),
]
# ---------------- Pabrik & biaya produksi (Fase 3). Harga jual = asumsi pasar, WAJIB diganti harga kontrak aktual.
_PB = "pabrik"
DEFS += [
    # Harga jual = INPUT wajib (tanpa angka bawaan): isi dengan harga kontrak/pasar aktual
    ParamDef(f"{_PB}.price_biochar_per_kg", "Harga jual biochar", None, "Rp/kg", 0, 100_000, required_input=True,
             help="Wajib diisi — harga kontrak/pasar aktual. Tanpa ini harga beli & biaya per produk tidak dihitung."),
    ParamDef(f"{_PB}.price_pellet_per_kg", "Harga jual bio-pellet", None, "Rp/kg", 0, 100_000, required_input=True,
             help="Wajib diisi — harga kontrak/pasar aktual."),
    ParamDef(f"{_PB}.price_silica_per_kg", "Harga jual bio-silika", None, "Rp/kg", 0, 500_000, required_input=True,
             help="Wajib diisi — harga kontrak/pasar aktual (sesuai kemurnian produk)."),
    _n(f"{_PB}.pellet_share", "Porsi sekam ke lini pellet", 0.30, "fraksi", 0, 1,
       "Sisanya masuk pirolisis. Dapat ditimpa per batch."),
    ParamDef(f"{_PB}.silica_route", "Jalur produksi bio-silika", "biochar", kind="choice", options=(
        ("biochar", "Dari biochar (ekstraksi alkali dari char)"),
        ("abu_pembakaran", "Dari abu pembakaran sekam (panas tungku dimanfaatkan)"),
        ("sekam_langsung", "Dari sekam langsung (pelindian asam + kalsinasi, kemurnian tinggi)")),
        help="Dapat ditimpa per batch."),
    _n(f"{_PB}.silica_share_of_biochar", "Porsi biochar diekstrak jadi bio-silika (jalur biochar)", 0.20, "fraksi", 0, 1),
    _n(f"{_PB}.silica_husk_share", "Porsi sekam ke lini silika (jalur abu / sekam langsung)", 0.20, "fraksi", 0, 1),
    _n(f"{_PB}.silica_eff_ash", "Efisiensi ekstraksi silika dari abu pembakaran", 0.90, "fraksi", 0.1, 1),
    _n(f"{_PB}.silica_eff_direct", "Efisiensi silika jalur sekam langsung", 0.92, "fraksi", 0.1, 1),
    _n(f"{_PB}.chemical_cost_direct_per_kg_silica", "Biaya asam pelindian per kg silika (jalur langsung)", 6_000.0,
       "Rp/kg", 0, 200_000),
    _n(f"{_PB}.pellet_moisture_pct", "Kadar air produk pellet", 10.0, "% bb", 0, 30),
    _n(f"{_PB}.pellet_process_loss", "Susut proses lini pellet", 0.05, "fraksi", 0, 0.5),
    _n(f"{_PB}.dryer_target_moisture_pct", "Target kadar air sebelum pirolisis", 10.0, "% bb", 0, 30),
    _n(f"{_PB}.silica_extraction_eff", "Efisiensi ekstraksi silika dari biochar", 0.85, "fraksi", 0.1, 1,
       source="Bio-silika dari biochar sekam (SiO₂ ±80% di char)"),
    _n(f"{_PB}.drying_cost_rp_per_mj", "Biaya panas pengering", 25.0, "Rp/MJ", 0, 1_000,
       "Sebagian besar panas dapat dari syngas pirolisis; isi biaya bahan bakar tambahan per MJ."),
    _n(f"{_PB}.kwh_per_ton_input", "Listrik proses per ton sekam", 150.0, "kWh/ton", 0, 2_000,
       "Selaraskan dengan SEC aktual dari modul Energi ⑩."),
    _n(f"{_PB}.labor_hours_per_ton", "Jam kerja per ton sekam", 2.0, "jam/ton", 0, 100),
    _n(f"{_PB}.labor_rate_per_hour", "Upah tenaga kerja", 20_000.0, "Rp/jam", 0, 1_000_000),
    _n(f"{_PB}.chemical_cost_per_kg_silica", "Biaya bahan kimia per kg silika (jalur biochar / abu)", 4_000.0,
       "Rp/kg", 0, 200_000),
    _n(f"{_PB}.packaging_cost_per_kg", "Biaya kemasan per kg produk", 100.0, "Rp/kg", 0, 10_000),
    _n(f"{_PB}.machine_value", "Nilai perolehan mesin", 2_500_000_000.0, "Rp", 0, 1e12),
    _n(f"{_PB}.machine_salvage", "Nilai sisa mesin", 250_000_000.0, "Rp", 0, 1e12),
    _n(f"{_PB}.machine_life_hours", "Umur ekonomis mesin", 40_000.0, "jam", 1, 1_000_000,
       source="Depresiasi garis lurus per jam operasi"),
    _n(f"{_PB}.operating_hours_per_month", "Jam operasi per bulan", 416.0, "jam", 1, 744),
    _n(f"{_PB}.other_fixed_cost_per_month", "Biaya tetap lain per bulan", 60_000_000.0, "Rp/bulan", 0, 1e11,
       "Gaji tetap, sewa, asuransi, perawatan terjadwal."),
    _n(f"{_PB}.planned_input_ton_per_month", "Rencana sekam diolah per bulan", 300.0, "ton/bulan", 1, 1_000_000),
    _n(f"{_PB}.target_margin_pct", "Margin target", 15.0, "% nilai produk", 0, 90),
    _n(f"{_PB}.reference_moisture_pct", "Kadar air acuan harga", 11.0, "% bb", 0, 60,
       "Harga kontrak disetarakan basis kering terhadap kadar air ini."),
    _n(f"{_PB}.closure_tolerance_pct", "Toleransi penutupan mass balance", 3.0, "%", 0, 50),
    _n(f"{_PB}.max_negotiation_rounds", "Maksimum putaran tawar-menawar", 3, "putaran", 1, 20),
    ParamDef(f"{_PB}.joint_cost_method", "Metode alokasi biaya bersama", "nrv", kind="choice",
             options=(("nrv", "Net Realizable Value (nilai jual − biaya terpisah)"), ("fisik", "Unit fisik (berat)")),
             source="Horngren, Cost Accounting — joint cost allocation"),
    # ---- Target dashboard Evaluasi & Optimasi (app/services/insights.py). Target lain memakai parameter yang
    #      sudah ada: sirkular.shrinkage_tolerance_pct, sirkular.estimate_tolerance_pct, pasar.default_margin_per_kg,
    #      pabrik.target_margin_pct, pabrik.closure_tolerance_pct, pabrik.kwh_per_ton_input,
    #      pabrik.planned_input_ton_per_month, harga_mutu.moisture_best, harga_mutu.base_price_per_kg.
    _n("evaluasi.window_months", "Jendela evaluasi", 3, "bulan", 1, 12,
       "KPI dihitung dari N bulan terakhir dan dibandingkan dengan N bulan sebelumnya."),
    _n("evaluasi.warn_band_pct", "Pita 'perhatian' di sekitar target", 15.0, "% dari target", 1, 100,
       "Di dalam pita = 'perhatian'; di luar pita = 'kritis'."),
    _n("evaluasi.grade_a_share_min_pct", "Porsi Grade A minimum (petani)", 60.0, "% lot", 0, 100),
    _n("evaluasi.collector_outstanding_max_pct", "Piutang pabrik maksimum (pengepul)", 30.0, "% tagihan", 0, 100,
       "Tagihan ke pabrik yang belum dibayar dibanding total tagihan pada jendela evaluasi."),
    _n("evaluasi.reject_max_pct", "Porsi sekam ditolak maksimum", 5.0, "% berat", 0, 100),
    _n("evaluasi.stop_success_min_pct", "Keberhasilan stop penjemputan minimum", 90.0, "% stop", 0, 100,
       "Stop dijemput dibanding stop dijemput + gagal (supir)."),
    _n("evaluasi.vehicle_utilization_min_pct", "Utilisasi bak truk minimum", 85.0, "% volume", 0, 100,
       source="Rencana rute (utilization_pct, Engine ⑤)"),
    _n("pajak.pph22_farmer_pct", "PPh 22 atas pembelian dari petani", 0.0, "% bruto", 0, 5,
       "Default 0. Isi hanya bila pembeli ditetapkan sebagai pemungut PPh 22 atas pembelian hasil pertanian "
       "(mis. industri/eksportir tertentu) — konsultasikan dengan konsultan pajak.",
       source="UU PPh Pasal 22 & peraturan menteri keuangan pelaksananya"),
    # ---- Biochar untuk sawah (engines/biochar_field.py). Nilai & rujukan: docs/08_RISET_BIOCHAR_SAWAH.md
    _n("biochar_sawah.base_yield_t_ha", "Produktivitas padi dasar (Y0)", 5.5, "t GKP/ha/musim", 1, 12,
       "BPS 2024: Jateng ≈5,7 t GKG/ha, DIY ≈4,7 t GKG/ha. Ganti dengan data kecamatan bila ada.",
       source="BPS — Luas panen & produksi padi 2024"),
    _n("biochar_sawah.gkp_price_rp_kg", "Harga gabah kering panen (GKP)", 6_500.0, "Rp/kg", 1_000, 20_000,
       "HPP GKP di petani; harga pasar Jul 2026 ≈ Rp7.000.", source="Keputusan Kepala Bapanas 2/2025 (HPP gabah)"),
    _n("biochar_sawah.yield_gain_max_pct", "Kenaikan hasil maksimum (R_max)", 10.0, "%", 0, 60,
       "Meta-analisis padi: +10,7% (Liu 2022), +11,3% (Bu 2022), +16% (Awad 2018). Konservatif untuk biochar sekam "
       "yang miskin hara & tanah vulkanik Sleman/Klaten yang relatif subur.",
       source="Liu et al. 2022 Sci. Total Environ.; Bu et al. 2022 — lihat docs/08 §tabel koefisien"),
    _n("biochar_sawah.yield_response_k", "Laju menuju jenuh (k)", 0.20, "1/(t/ha)", 0.01, 5,
       "Koefisien PALING tidak pasti (asumsi): respons hasil di meta-analisis hampir tak bergantung dosis. "
       "Kalibrasi dengan demplot lokal.", source="Asumsi; Yu et al. 2023, Iboko et al. 2023"),
    _n("biochar_sawah.rate_cap_t_ha", "Dosis maksimum yang dihitung (r_cap)", 10.0, "t/ha", 1, 50,
       "Di atas dosis ini tidak ada tambahan manfaat yang diperhitungkan."),
    _n("biochar_sawah.residual_seasons", "Jumlah musim efek sisa (N)", 4, "musim", 1, 12,
       "Efek biasanya tak lagi nyata setelah ±3 tahun.", source="Yu et al. 2023; Koyama & Hayashi 2019"),
    _n("biochar_sawah.residual_decay", "Sisa efek ke musim berikut (d)", 0.5, "fraksi", 0, 1,
       source="Koyama & Hayashi 2019 — efek musim ke-2 melemah"),
    _n("biochar_sawah.urea_dose_kg_ha", "Dosis urea per musim", 250.0, "kg/ha", 0, 1_000,
       source="Pratiwi 2021 (UGM): rekomendasi 266 kg/ha"),
    _n("biochar_sawah.urea_price_rp_kg", "Harga urea (subsidi HET)", 1_800.0, "Rp/kg", 0, 20_000,
       "Non-subsidi bisa ±Rp5.800/kg — ganti bila petani tidak mendapat alokasi subsidi.",
       source="Kepmentan 1117/2025 (HET pupuk bersubsidi, berlaku 22 Okt 2025)"),
    _n("biochar_sawah.fert_saving_per_t", "Hemat urea per t/ha biochar (s_k)", 0.03, "fraksi per t/ha", 0, 0.5,
       source="Xu et al. 2022 — 80% N + 5 t/ha biochar, hasil +10,2%"),
    _n("biochar_sawah.fert_saving_max_frac", "Hemat urea maksimum (s_max)", 0.15, "fraksi", 0, 1, source="Xu et al. 2022"),
    _n("biochar_sawah.spreading_cost_rp_kg", "Ongkos angkut & tebar biochar (c_s)", 100.0, "Rp/kg biochar", 0, 5_000,
       "Asumsi dari upah buruh tani; isi sesuai kondisi desa."),
    _n("biochar_sawah.carbon_frac", "Karbon organik biochar (F_C)", 0.49, "fraksi", 0.1, 0.95,
       "Sekam berabu tinggi — utamakan hasil lab C-organik.", source="IPCC 2019 Refinement Vol.4 Tabel 4Ap.1"),
    _n("biochar_sawah.stable_frac_100y", "Fraksi karbon stabil 100 tahun (F_perm)", 0.80, "fraksi", 0, 1,
       "0,65 (350–450 °C) · 0,80 (450–600 °C) · 0,89 (>600 °C).", source="IPCC 2019 Refinement Vol.4 Tabel 4Ap.2"),
    _n("biochar_sawah.rate_recommended_min_t_ha", "Dosis anjuran minimum", 1.0, "t/ha", 0, 50),
    _n("biochar_sawah.rate_recommended_max_t_ha", "Dosis anjuran maksimum", 2.0, "t/ha", 0, 50,
       "Dosis kecil lebih ekonomis untuk biochar terbatas; sebarkan merata ke lebih banyak lahan/musim."),
    _n("evaluasi.plant_capacity_min_pct", "Pemenuhan rencana input pabrik minimum", 80.0, "% rencana", 0, 200,
       "Sekam diterima per bulan dibanding parameter Pabrik → Rencana sekam diolah per bulan."),
]
REGISTRY: dict[str, ParamDef] = {d.key: d for d in DEFS}

# ---------------------------------------------------------------- cache nilai aktif
_values: dict[str, Any] = {}
_loaded_at = 0.0
REFRESH_S = 30.0


def P(key: str) -> Any:
    """Nilai parameter aktif (dari DB bila pernah diubah, selain itu default)."""
    d = REGISTRY[key]
    return _values.get(key, d.default)


class ParamError(ValueError):
    pass


def missing_inputs(keys) -> list[str]:
    """Label parameter wajib-isi yang belum diisi pengguna."""
    return [REGISTRY[k].label for k in keys if P(k) is None]


def validate(d: ParamDef, value: Any) -> Any:
    if d.kind == "choice":
        allowed = [o[0] for o in d.options]
        if value not in allowed:
            raise ParamError(f"{d.label}: pilih salah satu {allowed}")
        return value
    if d.kind == "number":
        try:
            v = float(value)
        except (TypeError, ValueError) as e:
            raise ParamError(f"{d.label}: harus angka") from e
        if v != v or v in (float("inf"), float("-inf")):
            raise ParamError(f"{d.label}: nilai tidak valid")
        if d.min is not None and v < d.min or d.max is not None and v > d.max:
            raise ParamError(f"{d.label}: harus di antara {d.min:g} dan {d.max:g} {d.unit}".strip())
        return int(v) if isinstance(d.default, int) and v.is_integer() else v
    if not isinstance(value, list) or not value:
        raise ParamError(f"{d.label}: harus daftar baris, minimal satu")
    out, seen = [], set()
    for i, row in enumerate(value, 1):
        if not isinstance(row, dict):
            raise ParamError(f"{d.label} baris {i}: format salah")
        clean = {}
        for c in d.columns:
            raw = row.get(c.name)
            if c.kind == "text":
                if not isinstance(raw, str) or not raw.strip() or len(raw) > 80:
                    raise ParamError(f"{d.label} baris {i}: '{c.label}' wajib diisi (≤ 80 karakter)")
                clean[c.name] = raw.strip()
            elif c.kind == "bool":
                clean[c.name] = bool(raw)
            else:
                try:
                    v = float(raw)
                except (TypeError, ValueError) as e:
                    raise ParamError(f"{d.label} baris {i}: '{c.label}' harus angka") from e
                if c.min is not None and v < c.min or c.max is not None and v > c.max:
                    raise ParamError(f"{d.label} baris {i}: '{c.label}' harus {c.min:g}–{c.max:g} {c.unit}".strip())
                clean[c.name] = v
        if clean.get("id") in seen:
            raise ParamError(f"{d.label}: kode '{clean['id']}' ganda")
        seen.add(clean.get("id"))
        out.append(clean)
    return out


def cross_check(key: str, value: Any) -> None:
    """Aturan lintas-parameter yang menjaga konsistensi model."""
    view = {**{k: P(k) for k in REGISTRY}, key: value}
    if view["harga_mutu.grade_B_min"] >= view["harga_mutu.grade_A_min"]:
        raise ParamError("Skor minimum Grade B harus lebih kecil dari Grade A.")
    if view["harga_mutu.ash_ideal_min"] >= view["harga_mutu.ash_ideal_max"]:
        raise ParamError("Batas bawah abu ideal harus lebih kecil dari batas atas.")
    if view["harga_mutu.fc_worst"] >= view["harga_mutu.fc_best"]:
        raise ParamError("FC terendah harus lebih kecil dari FC ideal.")
    if view["harga_mutu.moisture_best"] >= view["harga_mutu.moisture_reject"]:
        raise ParamError("Kadar air ideal harus lebih kecil dari batas tolak.")
    if view["rendemen.yield_700c"] >= view["rendemen.yield_300c"]:
        raise ParamError("Rendemen @700 °C harus lebih kecil dari @300 °C (rendemen turun dengan suhu).")
    t = view
    if not (t["insentif.tier_aktif_xp"] < t["insentif.tier_emas_xp"] < t["insentif.tier_platinum_xp"]):
        raise ParamError("Ambang XP tier harus naik: Aktif < Emas < Platinum.")
    for b in ("ac", "non_ac"):
        a1, a2, a3 = (t[f"energi.ike_{b}_{i}"] for i in (1, 2, 3))
        if not (a1 < a2 < a3):
            raise ParamError(f"Batas IKE {b} harus naik berurutan.")
    if t["pabrik.pellet_share"] + (t["pabrik.silica_husk_share"] if t["pabrik.silica_route"] != "biochar" else 0) > 1:
        raise ParamError("Porsi pellet + porsi silika dari sekam tidak boleh melebihi 1.")
    if t["pabrik.machine_salvage"] > t["pabrik.machine_value"]:
        raise ParamError("Nilai sisa mesin tidak boleh melebihi nilai perolehan.")
    for prefix in ("harga_mutu.w_", "feedstock.biochar_w_", "feedstock.pellet_w_", "feedstock.burn_w_"):
        if sum(v for k, v in t.items() if k.startswith(prefix)) <= 0:
            raise ParamError("Jumlah bobot dalam satu kelompok harus > 0.")


_weights_cache: dict[str, dict[str, float]] = {}


def weights(prefix: str) -> dict[str, float]:
    """Bobot satu kelompok, dinormalisasi agar berjumlah 1."""
    cached = _weights_cache.get(prefix)
    if cached is not None:
        return cached
    w = {k[len(prefix):]: float(P(k)) for k in REGISTRY if k.startswith(prefix)}
    total = sum(w.values()) or 1.0
    res = {k: v / total for k, v in w.items()}
    _weights_cache[prefix] = res
    return res


def describe(key: str) -> dict:
    d = REGISTRY[key]
    return {"key": key, "group": d.group, "group_label": GROUPS[d.group], "label": d.label, "unit": d.unit,
            "kind": d.kind, "value": P(key), "default": d.default, "min": d.min, "max": d.max, "help": d.help,
            "source": d.source, "modified": key in _values and _values[key] != d.default,
            "required_input": d.required_input, "missing": d.required_input and P(key) is None,
            "columns": [c.__dict__ for c in d.columns], "options": [list(o) for o in d.options]}


_dirty: bool = False


def mark_stale() -> None:
    """Tandai cache parameter basi agar segera dimuat ulang dari database pada request berikutnya."""
    global _dirty
    _dirty = True
    _weights_cache.clear()


def _set_cache(values: dict[str, Any]) -> None:
    global _loaded_at, _dirty
    _dirty = False
    _values.clear()
    _weights_cache.clear()
    _values.update({k: v for k, v in values.items() if k in REGISTRY})
    _loaded_at = time.monotonic()


def needs_refresh() -> bool:
    global _dirty
    if _dirty:
        return True
    return time.monotonic() - _loaded_at > REFRESH_S


def reset_cache() -> None:
    """Untuk tes: kembali ke default."""
    _set_cache({})
