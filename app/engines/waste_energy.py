"""Engine ⑨ — Waste-to-Energy Advisor: rekomendasi teknologi konversi & estimasi potensi energi.

Masukan: karakteristik (kadar air, abu, VM, FC, C/N, BMP) dan volume aliran limbah.
Keluaran: kelayakan & skor tiap teknologi, potensi energi (panas/listrik/biogas/biochar/pellet) per
tahun, dan rekomendasi berurutan dengan alasan.

Logika pemilihan mengikuti pembagian klasik konversi biomassa: termokimia untuk bahan kering
(pembakaran, gasifikasi, pirolisis) vs biokimia untuk bahan basah (digestasi anaerob, kompos) —
McKendry (2002) Bioresour. Technol. 83:47-54. Ambang kelayakan (kadar air, C/N, abu) adalah heuristik
rekayasa umum; parameter efisiensi di bawah adalah nilai tipikal skala kecil-menengah.
"""

from pydantic import BaseModel, Field, model_validator

from ..params import P
from .biomass_data import CH4_LHV_MJ_M3, biochar_yield_estimate, hhv_parikh, lhv_as_received, presets

# DEFAULT efisiensi tipikal skala kecil–menengah; nilai aktif dari menu Parameter (limbah.*)
ETA_BOILER_HEAT = 0.80          # boiler biomassa → panas proses
ETA_STEAM_CHP_EL = 0.18         # siklus uap skala < 5 MWe
ETA_GASIFIER_ENGINE_EL = 0.25   # gasifier downdraft + mesin gas
ETA_AD_CHP_EL = 0.35            # mesin gas biogas
DRYING_MJ_PER_KG_WATER = 3.0    # termasuk rugi pengering (≈ 1,2 × panas laten)
PELLET_KWH_PER_TON = 120        # energi listrik densifikasi
PYROLYSIS_TEMP_C = 500
OPERATING_DAYS = 300


class WasteStream(BaseModel):
    name: str = Field("Limbah", max_length=80)
    preset: str | None = Field(None, description="Kode preset biomassa (menu Parameter → Preset Biomassa)")
    ton_per_day: float = Field(..., gt=0, le=10_000, description="Volume limbah as received")
    moisture: float | None = Field(None, ge=0, le=95, description="% basis basah")
    ash: float | None = Field(None, ge=0, le=60, description="% basis kering")
    volatile_matter: float | None = Field(None, ge=0, le=100)
    fixed_carbon: float | None = Field(None, ge=0, le=100)
    cn_ratio: float | None = Field(None, gt=0, le=1000)
    bmp_m3_ch4_per_t_vs: float | None = Field(None, ge=0, le=600, description="Potensi metana biokimia")
    hhv_mj_kg: float | None = Field(None, gt=0, le=35, description="HHV basis kering terukur")
    operating_days: int = Field(default_factory=lambda: int(P("limbah.operating_days")), ge=1, le=366)

    @model_validator(mode="after")
    def _fill(self):
        if self.preset:
            p = presets().get(self.preset)
            if p is None:
                raise ValueError(f"preset '{self.preset}' tidak dikenal")
            for f in ("moisture", "ash", "volatile_matter", "fixed_carbon", "cn_ratio", "bmp_m3_ch4_per_t_vs"):
                if getattr(self, f) is None:
                    setattr(self, f, getattr(p, f))
            if self.name == "Limbah":
                self.name = p.name
        missing = [f for f in ("moisture", "ash", "volatile_matter", "fixed_carbon") if getattr(self, f) is None]
        if missing:
            raise ValueError(f"Isi {missing} atau gunakan preset")
        return self


def _score(base: float, penalties: list[tuple[bool, float, str]]) -> tuple[float, list[str]]:
    notes = [msg for cond, _, msg in penalties if cond]
    return max(0.0, base - sum(p for cond, p, _ in penalties if cond)), notes


def advise(w: WasteStream) -> dict:
    ETA_BOILER_HEAT, ETA_STEAM_CHP_EL = P("limbah.eta_boiler_heat"), P("limbah.eta_steam_chp_el")
    ETA_GASIFIER_ENGINE_EL, ETA_AD_CHP_EL = P("limbah.eta_gasifier_engine_el"), P("limbah.eta_ad_chp_el")
    DRYING_MJ_PER_KG_WATER, PELLET_KWH_PER_TON = P("limbah.drying_mj_per_kg_water"), P("limbah.pellet_kwh_per_ton")
    PYROLYSIS_TEMP_C, BIOCHAR_HHV = P("limbah.pyrolysis_temp_c"), P("limbah.biochar_hhv_mj_kg")
    m, ash, vm, fc = w.moisture, w.ash, w.volatile_matter, w.fixed_carbon
    t_year = w.ton_per_day * w.operating_days
    dry_t = t_year * (1 - m / 100)
    vs_t = dry_t * (1 - ash / 100)
    hhv = w.hhv_mj_kg or hhv_parikh(fc, vm, ash)
    lhv_ar = lhv_as_received(hhv, m)
    primary_gj = max(lhv_ar, 0) * t_year                       # MJ/kg × t = GJ
    # Pengeringan ke 15% sebelum proses termokimia
    water_to_remove_t = max(0.0, t_year * (m / 100) - dry_t * 15 / 85)
    drying_gj = water_to_remove_t * DRYING_MJ_PER_KG_WATER
    thermo_net_gj = max(0.0, dry_t * lhv_as_received(hhv, 15) / (1 - 0.15) - drying_gj)
    cn = w.cn_ratio
    bmp = w.bmp_m3_ch4_per_t_vs

    techs = []

    s, n = _score(90, [(m > 50, 60, "kadar air > 50%: nyala tidak stabil tanpa pengeringan"),
                       (20 < m <= 50, 25, "kadar air 20–50%: efisiensi turun, perlu pengering"),
                       (ash > 15, 15, "abu tinggi: risiko slagging/fouling, butuh sistem penanganan abu"),
                       (w.ton_per_day < 5, 10, "skala < 5 t/hari: CHP kurang ekonomis, cukup boiler panas")])
    techs.append({"technology": "Pembakaran langsung (boiler / CHP uap)", "score": s, "notes": n,
                  "outputs": {"panas_proses_gj_per_tahun": round(thermo_net_gj * ETA_BOILER_HEAT, 0),
                              "listrik_mwh_per_tahun": round(thermo_net_gj * ETA_STEAM_CHP_EL / 3.6, 0)}})

    s, n = _score(80, [(m > 35, 50, "kadar air > 35%: syngas encer, pengeringan wajib"),
                       (15 < m <= 35, 15, "perlu pengeringan ke < 15%"),
                       (ash > 15, 25, "abu tinggi: risiko aglomerasi & tar, pilih gasifier khusus sekam"),
                       (w.ton_per_day < 2, 10, "skala sangat kecil")])
    techs.append({"technology": "Gasifikasi + mesin gas", "score": s, "notes": n,
                  "outputs": {"listrik_mwh_per_tahun": round(thermo_net_gj * ETA_GASIFIER_ENGINE_EL / 3.6, 0)}})

    y = biochar_yield_estimate(fc, vm, ash, PYROLYSIS_TEMP_C)
    biochar_t = dry_t * y / 100
    s, n = _score(85, [(m > 40, 45, "kadar air > 40%: energi pengeringan besar"),
                       (20 < m <= 40, 15, "perlu pengeringan ke < 15–20%"),
                       (fc < 10, 20, "fixed carbon rendah: rendemen biochar kecil"),
                       (ash > 25, 15, "abu sangat tinggi: kadar karbon biochar rendah")])
    if ash >= 15:
        n.append("abu kaya silika: biochar + bio-silika sebagai produk bernilai tambah")
    techs.append({"technology": "Pirolisis lambat (biochar)", "score": s, "notes": n,
                  "outputs": {"biochar_ton_per_tahun": round(biochar_t, 0),
                              "rendemen_biochar_pct_bk": round(y, 1),
                              "panas_volatil_untuk_pengeringan_gj": round(max(0.0, dry_t * hhv - biochar_t * BIOCHAR_HHV), 0)}})

    pellet_t = dry_t / 0.9                                      # produk pada kadar air 10%
    s, n = _score(80, [(m > 40, 40, "kadar air tinggi: biaya pengeringan dominan"),
                       (ash > 10, 35, "abu > 10%: di luar mutu pellet industri, abrasif pada die"),
                       (6 < ash <= 10, 15, "abu 6–10%: hanya mutu briket/industri"),
                       (w.ton_per_day < 1, 10, "skala kecil")])
    techs.append({"technology": "Pelletisasi / briket", "score": s, "notes": n,
                  "outputs": {"pellet_ton_per_tahun": round(pellet_t, 0),
                              "energi_terkandung_gj_per_tahun": round(pellet_t * lhv_as_received(hhv, 10), 0),
                              "listrik_densifikasi_mwh_per_tahun": round(pellet_t * PELLET_KWH_PER_TON / 1000, 0)}})

    ch4_m3 = vs_t * (bmp or 0)
    s, n = _score(90, [(m < 60, 35, "kadar air < 60%: perlu digestasi kering/penambahan air"),
                       (cn is not None and (cn < 15 or cn > 35), 25, f"C/N {cn:g} di luar 15–35: perlu co-digestion"
                        if cn else ""),
                       ((bmp or 0) < 150, 35, "potensi metana rendah (lignoselulosa sulit terurai)")])
    techs.append({"technology": "Digestasi anaerob (biogas)", "score": s, "notes": [x for x in n if x],
                  "outputs": {"metana_m3_per_tahun": round(ch4_m3, 0),
                              "listrik_mwh_per_tahun": round(ch4_m3 * CH4_LHV_MJ_M3 * ETA_AD_CHP_EL / 3600, 0)}})

    s, n = _score(60, [(m < 40 or m > 70, 25, "kadar air ideal kompos 40–65%"),
                       (cn is not None and (cn < 20 or cn > 40), 20, "C/N ideal kompos 20–40")])
    n.append("tanpa energi; opsi pengelolaan bila konversi energi tidak layak")
    techs.append({"technology": "Pengomposan", "score": s, "notes": n,
                  "outputs": {"kompos_ton_per_tahun": round(dry_t * 0.5, 0)}})

    ranked = sorted(techs, key=lambda t: -t["score"])
    for i, t in enumerate(ranked, 1):
        t["rank"] = i
        t["feasible"] = t["score"] >= 50
    best = ranked[0]
    return {
        "stream": w.name,
        "characteristics": {"ton_per_tahun": round(t_year, 0), "ton_kering_per_tahun": round(dry_t, 0),
                            "kadar_air_pct": m, "abu_pct_bk": ash, "cn_ratio": cn,
                            "hhv_bk_mj_kg": round(hhv, 2), "lhv_diterima_mj_kg": round(lhv_ar, 2)},
        "energy_potential": {
            "energi_primer_gj_per_tahun": round(primary_gj, 0),
            "setara_listrik_mwh_teoritis": round(primary_gj / 3.6, 0),
            "energi_pengeringan_ke_15pct_gj": round(drying_gj, 0),
        },
        "technologies": ranked,
        "recommendation": (f"Teknologi utama: {best['technology']} (skor {best['score']:.0f}/100). "
                           + (f"Alternatif: {ranked[1]['technology']} (skor {ranked[1]['score']:.0f}). "
                              if ranked[1]["feasible"] else "")
                           + ("Catatan: " + "; ".join(best["notes"]) + "." if best["notes"] else "")),
        "computation_details": {
            "formulas": {
                "HHV_bk": "0,3536·FC + 0,1559·VM − 0,0078·Ash (Parikh et al. 2005)" if not w.hhv_mj_kg else "terukur",
                "energi_primer": "massa_diterima × LHV_diterima",
                "pengeringan": f"air yang diuapkan ke 15% × {DRYING_MJ_PER_KG_WATER} MJ/kg",
                "biogas": f"VS × BMP; listrik = CH4 × {CH4_LHV_MJ_M3} MJ/m³ × η {ETA_AD_CHP_EL}",
                "skor": "100-an dikurangi penalti kelayakan (kadar air, abu, C/N, BMP, skala)",
            },
            "efficiencies": {"boiler_panas": ETA_BOILER_HEAT, "CHP_uap_listrik": ETA_STEAM_CHP_EL,
                             "gasifier_mesin_listrik": ETA_GASIFIER_ENGINE_EL, "biogas_CHP_listrik": ETA_AD_CHP_EL},
            "references": ["McKendry P. (2002) Bioresour. Technol. 83:47-54 — teknologi konversi biomassa",
                           "Parikh J. et al. (2005) Fuel 84:487-494 — korelasi HHV proksimat",
                           "Angelidaki I. et al. (2009) Water Sci. Technol. 59:927-934 — uji BMP"],
        },
    }
