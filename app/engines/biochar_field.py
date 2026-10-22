"""Manfaat ekonomi biochar sekam di sawah petani — rumus pendekatan ekonomi sirkular.

Semua koefisien adalah parameter (`biochar_sawah.*`, menu Parameter) dengan rujukan di
docs/08_RISET_BIOCHAR_SAWAH.md. Rumus sengaja konservatif: hasil adalah PERKIRAAN untuk membantu petani
memutuskan, bukan janji panen.

    r        = kg / 1000 / luas ;  r_eff = min(r, r_cap)         dosis (t/ha)
    f(r)     = R_maks · (1 − e^(−k·r_eff))                       kenaikan hasil (%), jenuh pada dosis tinggi
    ΔY_musim = Y0 · luas · f(r) / 100                            tambahan gabah musim ke-1 (t GKP)
    M        = Σ_{i=0..N−1} d^i = (1 − d^N)/(1 − d)             efek sisa N musim (d = sisa efek per musim)
    Pendapatan tambahan = ΔY_musim · M · 1000 · harga_GKP
    Hemat pupuk         = dosis_urea · luas · harga_urea · min(s_maks, s_k · r_eff) · M
    Biaya               = ongkos_tebar_per_kg · kg
    Manfaat bersih      = pendapatan tambahan + hemat pupuk − biaya
    Karbon tersimpan    = kg · C_frac · stabil_100th · 44/12 / 1000    (tCO2e; dicatat proyek pabrik)
"""

import math

from ..params import P

K = "biochar_sawah"


def _p(name: str) -> float:
    return float(P(f"{K}.{name}"))


def estimate(kg: float, land_area_ha: float) -> dict:
    rate = kg / 1000 / land_area_ha
    r_eff = min(rate, _p("rate_cap_t_ha"))
    g_max, k = _p("yield_gain_max_pct"), _p("yield_response_k")
    gain_pct = g_max * (1 - math.exp(-k * r_eff))
    seasons, decay = int(_p("residual_seasons")), _p("residual_decay")
    residual = sum(decay ** i for i in range(max(1, seasons)))
    y0, p_gkp = _p("base_yield_t_ha"), _p("gkp_price_rp_kg")
    d_yield_t = y0 * land_area_ha * gain_pct / 100
    extra_rev = d_yield_t * residual * 1000 * p_gkp

    save_frac = min(_p("fert_saving_max_frac"), _p("fert_saving_per_t") * r_eff)
    fert_save = _p("urea_dose_kg_ha") * land_area_ha * _p("urea_price_rp_kg") * save_frac * residual
    cost = _p("spreading_cost_rp_kg") * kg
    carbon_t = kg * _p("carbon_frac") * _p("stable_frac_100y") * 44 / 12 / 1000
    rec_lo, rec_hi = _p("rate_recommended_min_t_ha"), _p("rate_recommended_max_t_ha")
    advice = ("Dosis di bawah rentang anjuran — manfaat kecil; pusatkan di petak terluas/paling asam."
              if rate < rec_lo else
              "Dosis di atas rentang anjuran — tambahan manfaat makin kecil; sisakan untuk musim berikut."
              if rate > rec_hi else "Dosis dalam rentang anjuran.")
    net = extra_rev + fert_save - cost
    return {
        "input": {"kg": round(kg, 1), "land_area_ha": land_area_ha},
        "rate_t_ha": round(rate, 2), "rate_recommended_t_ha": [rec_lo, rec_hi], "advice": advice,
        "yield_gain_pct": round(gain_pct, 1), "extra_grain_t_per_season": round(d_yield_t, 3),
        "residual_seasons": seasons, "residual_factor": round(residual, 2),
        "extra_revenue_rp": round(extra_rev), "fertilizer_saving_rp": round(fert_save),
        "fertilizer_saving_pct": round(save_frac * 100, 1), "spreading_cost_rp": round(cost),
        "net_benefit_rp": round(net), "net_benefit_per_kg_biochar_rp": round(net / kg, 1) if kg else None,
        "carbon_stored_tco2e": round(carbon_t, 3),
        "carbon_note": "Karbon tersimpan dicatat pada proyek karbon pabrik (hindari hitung ganda), bukan pendapatan petani.",
        "formula": __doc__.split("\n\n", 2)[2].strip(),
        "disclaimer": "Perkiraan konservatif dari meta-analisis (docs/08_RISET_BIOCHAR_SAWAH.md); hasil nyata bergantung "
                      "tanah, air, varietas & cara aplikasi. Koefisien k paling tidak pasti — kalibrasi dengan demplot.",
        "sources": "Liu 2022; Bu 2022; Xu 2022; Yu 2023; IPCC 2019 Refinement; Bapanas 2/2025; Kepmentan 1117/2025",
    }
