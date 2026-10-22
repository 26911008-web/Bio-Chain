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
    "proyeksi": "Proyeksi Pasokan",
    "insentif": "Insentif Petani",
    "limbah": "Limbah → Energi",
    "energi": "Energi & IKE",
    "feedstock": "Bobot Perbandingan Feedstock (TOPSIS)",
    "blending": "Blending & Spesifikasi Produk",
    "biomassa": "Preset Biomassa",
    "pabrik": "Pabrik & Biaya Produksi",
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
    # ---------------- Pasar B2B
    _n("pasar.farmer_truck_kg", "Kapasitas angkut petani (skema antar)", 2_000.0, "kg", 50, 20_000),
    _n("pasar.farmer_cost_per_km", "Ongkos angkut petani", 3_000.0, "Rp/km", 0, 100_000),
    _n("pasar.default_resale_price_per_kg", "Harga jual pengepul ke pabrik (default)", 560.0, "Rp/kg", 1, 10_000),
    _n("pasar.default_margin_per_kg", "Margin pengepul (default)", 30.0, "Rp/kg", 0, 5_000),
    # ---------------- Karbon
    _n("karbon.coal_ef_kg_co2_per_gj", "Faktor emisi batubara", 96.1, "kgCO₂/GJ", 50, 150,
       source="IPCC 2006 Vol.2 Ch.2 (sub-bituminous)"),
    _n("karbon.husk_hhv_mj_kg", "Nilai kalor sekam (basis kering)", 13.5, "MJ/kg", 5, 25),
    _n("karbon.coal_hhv_mj_kg", "Nilai kalor batubara", 22.0, "MJ/kg", 10, 35),
    _n("karbon.boiler_efficiency", "Efisiensi boiler", 0.85, "fraksi", 0.3, 1),
    _n("karbon.transport_ef_kg_co2_per_tkm", "Faktor emisi angkutan truk", 0.062, "kgCO₂/t·km", 0, 1),
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
    _n("limbah.drying_mj_per_kg_water", "Energi pengeringan", 3.0, "MJ/kg air", 2.443, 10,
       "≥ panas laten 2,443 MJ/kg + rugi pengering."),
    _n("limbah.pellet_kwh_per_ton", "Listrik densifikasi pellet", 120.0, "kWh/ton", 0, 500),
    _n("limbah.pyrolysis_temp_c", "Suhu pirolisis acuan", 500.0, "°C", 300, 800),
    _n("limbah.operating_days", "Hari operasi per tahun (default)", 300, "hari", 1, 366),
    _n("limbah.biochar_hhv_mj_kg", "Nilai kalor biochar", 25.0, "MJ/kg", 5, 35),
    # ---------------- Energi & IKE
    _n("energi.tariff_rp_per_kwh", "Tarif listrik rata-rata", 1_444.7, "Rp/kWh", 1, 10_000),
    _n("energi.anomaly_z", "Ambang anomali (robust z)", 2.5, "z", 1, 10, source="Iglewicz & Hoaglin 1993"),
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


def weights(prefix: str) -> dict[str, float]:
    """Bobot satu kelompok, dinormalisasi agar berjumlah 1."""
    w = {k[len(prefix):]: float(P(k)) for k in REGISTRY if k.startswith(prefix)}
    total = sum(w.values()) or 1.0
    return {k: v / total for k, v in w.items()}


def describe(key: str) -> dict:
    d = REGISTRY[key]
    return {"key": key, "group": d.group, "group_label": GROUPS[d.group], "label": d.label, "unit": d.unit,
            "kind": d.kind, "value": P(key), "default": d.default, "min": d.min, "max": d.max, "help": d.help,
            "source": d.source, "modified": key in _values and _values[key] != d.default,
            "required_input": d.required_input, "missing": d.required_input and P(key) is None,
            "columns": [c.__dict__ for c in d.columns], "options": [list(o) for o in d.options]}


def _set_cache(values: dict[str, Any]) -> None:
    global _loaded_at
    _values.clear()
    _values.update({k: v for k, v in values.items() if k in REGISTRY})
    _loaded_at = time.monotonic()


def needs_refresh() -> bool:
    return time.monotonic() - _loaded_at > REFRESH_S


def reset_cache() -> None:
    """Untuk tes: kembali ke default."""
    _set_cache({})
