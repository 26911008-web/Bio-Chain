"""Engine ⑨b — Prototipe 2 (fase 3): energi riil basis as-received & pohon keputusan teknologi termokimia.

Rumus (MJ/kg, MC fraksi):
    LHV_ar = LHV_db·(1 − MC) − 2,443·MC                              ISO 18125:2017 (24,43 J/g per % air)
    E_th [GJ]  = massa [kg] × LHV_ar / 1000
    E_el [MWh] = massa [kg] × LHV_ar × η_th-el / 3600                1 MWh = 3.600 MJ
    CO₂ dihindari [t] = E_el × EF_grid JAMALI (0,87 tCO₂/MWh, Kepmen ESDM 163.K/2021)
Bila MC melebihi batas rute, energi pengeringan (limbah.drying_mj_per_kg_water ≈ 1,2 × panas laten) dikurangkan dari
energi rute itu (dipasok dari biomassa sendiri) — itu sebabnya bahan basah tampak "berenergi" tetapi netonya kecil.

Pohon keputusan (docs/15 §5; Basu 2018; Zhu 2014; spesifikasi PLTU Teluk Sirih):
  1. Abu kaya silika (SiO₂ abu ≥ 85 % & abu ≥ 12 %)     → Pirolisis lambat: biochar + bio-silika (nilai tambah > listrik)
     atau karbon tetap tinggi (FC ≥ 20 % & abu ≤ 3 %)    → Pirolisis: arang/karbon aktif (mis. tempurung kelapa)
  2. Lolos spek co-firing (GCV ar ≥ 3.009, MC ≤ 25 %, Cl ≤ 0,2 %, AI ≤ 0,34) & PLTU ≤ jarak maks → Co-firing PLTU (η tertinggi)
  3. Skala ≥ 50 t/hari & MC ≤ 55 % & abu ≤ 20 %          → Pembakaran langsung + turbin uap (η 22 %)
  4. MC ≤ 20 % (atau dapat dikeringkan) & abu ≤ 6 %       → Gasifikasi + mesin gas (η 28 %)
  5. Selain itu                                          → Pembakaran langsung skala kecil (panas proses/boiler)
Emisi yang DIHINDARI dilaporkan terpisah dari removal karbon (GHG Protocol LSR) — CO₂ biogenik dianggap netral.
"""

from pydantic import BaseModel, Field

from ..params import P
from .biomass_data import biochar_yield_estimate
from .fuel_blend import KCAL_PER_MJ, LATENT

ROUTES = {
    "pirolisis": "Pirolisis lambat → biochar & bio-silika",
    "cofiring": "Co-firing PLTU",
    "pembakaran": "Pembakaran langsung + turbin uap",
    "gasifikasi": "Gasifikasi + mesin gas",
    "pembakaran_kecil": "Pembakaran langsung skala kecil (panas proses)",
}


class ConversionInput(BaseModel):
    code: str
    name: str
    ton_per_month: float = Field(..., gt=0, le=1_000_000, description="Tonase as-received per bulan")
    moisture_pct: float = Field(..., ge=0, lt=95, description="MC as-received aktual lapangan")
    ash_pct_db: float = Field(..., ge=0, lt=60)
    lhv_db_mj_kg: float = Field(..., gt=5, lt=35)
    hhv_db_mj_kg: float | None = None
    volatile_pct_db: float | None = None
    fixed_carbon_pct_db: float | None = None
    chlorine_pct_db: float | None = None
    sio2_pct_ash: float | None = None
    k2o_pct_ash: float | None = None
    na2o_pct_ash: float | None = None
    operating_days_per_month: float = Field(25, gt=0, le=31)
    distance_to_pltu_km: float | None = Field(None, ge=0, le=5000)


def lhv_ar(lhv_db: float, mc_pct: float) -> float:
    mc = mc_pct / 100
    return lhv_db * (1 - mc) - LATENT * mc


def _drying_gj(t_ar: float, mc_from: float, mc_to: float) -> float:
    """GJ untuk mengeringkan t_ar ton dari mc_from ke mc_to (%)."""
    if mc_from <= mc_to:
        return 0.0
    dry_t = t_ar * (1 - mc_from / 100)
    water_t = t_ar * mc_from / 100 - dry_t * mc_to / (100 - mc_to)
    return water_t * P("limbah.drying_mj_per_kg_water")                  # t × MJ/kg = GJ


def analyse(x: ConversionInput) -> dict:
    t = x.ton_per_month
    kg = t * 1000
    hhv = x.hhv_db_mj_kg or x.lhv_db_mj_kg + 1.2
    lhv = lhv_ar(x.lhv_db_mj_kg, x.moisture_pct)
    gcv_ar = hhv * (1 - x.moisture_pct / 100)
    th_gj = max(0.0, kg * lhv / 1000)
    ef = P("karbon.grid_ef_kg_co2_per_kwh")                                  # kg/kWh = t/MWh
    eta = {"turbin_uap_kecil": P("limbah.eta_el_steam_small"), "terintegrasi": P("limbah.eta_el_integrated"),
           "cofiring_pltu": P("limbah.eta_el_cofiring")}
    el = {k: round(max(0.0, kg * lhv * v / 3600), 2) for k, v in eta.items()}
    ai = (x.ash_pct_db * ((x.k2o_pct_ash or 0) + (x.na2o_pct_ash or 0)) / (10 * hhv)) if x.k2o_pct_ash is not None else None
    t_day = t / x.operating_days_per_month
    cl = x.chlorine_pct_db

    # ---------------- syarat tiap rute (cek eksplisit agar pohon bisa ditampilkan)
    def check(label, ok, detail):
        return {"check": label, "ok": bool(ok), "detail": detail}
    silica_rich = (x.sio2_pct_ash or 0) >= 85 and x.ash_pct_db >= 12
    carbon_rich = (x.fixed_carbon_pct_db or 0) >= 20 and x.ash_pct_db <= 3
    cof_max_km = P("limbah.cofiring_max_km")
    checks = {
        "pirolisis": [check("Produk karbon/silika bernilai tinggi", silica_rich or carbon_rich,
                            f"SiO₂ abu {x.sio2_pct_ash or 0:g} % & abu {x.ash_pct_db:g} % (bio-silika: ≥ 85 & ≥ 12) · "
                            f"FC {x.fixed_carbon_pct_db or 0:g} % & abu {x.ash_pct_db:g} % (arang/karbon aktif: ≥ 20 & ≤ 3)"),
                      check("MC dapat dikeringkan ke < 20 %", x.moisture_pct <= 40, f"MC {x.moisture_pct:g} % (≤ 40 % agar pengeringan wajar)")],
        "cofiring": [check("GCV ar", gcv_ar * KCAL_PER_MJ >= P("limbah.cofiring_gcv_min_kcal"),
                           f"{gcv_ar * KCAL_PER_MJ:,.0f} kcal/kg (min {P('limbah.cofiring_gcv_min_kcal'):,.0f})"),
                     check("Kadar air", x.moisture_pct <= P("limbah.cofiring_mc_max"), f"{x.moisture_pct:g} % (maks {P('limbah.cofiring_mc_max'):g})"),
                     check("Klorin", cl is not None and cl <= 0.2, f"{cl if cl is not None else '?'} % (≤ 0,2)"),
                     check("Indeks alkali", ai is not None and ai <= 0.34, f"{round(ai, 3) if ai is not None else '?'} kg/GJ (≤ 0,34)"),
                     check("Jarak ke PLTU", x.distance_to_pltu_km is not None and x.distance_to_pltu_km <= cof_max_km,
                           f"{x.distance_to_pltu_km if x.distance_to_pltu_km is not None else 'tidak diisi'} km (≤ {cof_max_km:g})")],
        "pembakaran": [check("Skala", t_day >= 50, f"{t_day:,.1f} t/hari (≥ 50 untuk turbin uap 1–10 MWe)"),
                       check("Kadar air", x.moisture_pct <= 55, f"{x.moisture_pct:g} % (grate ≤ 55)"),
                       check("Abu", x.ash_pct_db <= 20, f"{x.ash_pct_db:g} % (≤ 20, grate bergerak)")],
        "gasifikasi": [check("Kadar air (setelah pengering)", x.moisture_pct <= 35, f"{x.moisture_pct:g} % → keringkan ke < 20 %"),
                       check("Abu", x.ash_pct_db <= 6, f"{x.ash_pct_db:g} % (≤ 6 downdraft: clinker/bridging)"),
                       check("Skala", 2 <= t_day <= 25, f"{t_day:,.1f} t/hari (2–25)")],
        "pembakaran_kecil": [check("Selalu tersedia", True, "boiler panas proses; listrik tidak ekonomis di skala kecil")],
    }
    path, choice = [], None
    for key, q in (("pirolisis", "Abu kaya silika atau karbon tetap tinggi?"), ("cofiring", "Lolos spek co-firing PLTU & dekat PLTU?"),
                   ("pembakaran", "Skala besar & toleran MC/abu?"), ("gasifikasi", "Kering & abu rendah?")):
        ok = all(c["ok"] for c in checks[key])
        path.append({"question": q, "answer": "ya" if ok else "tidak", "route": key if ok else None})
        if ok:
            choice = key
            break
    choice = choice or "pembakaran_kecil"

    # ---------------- keluaran per rute (net setelah pengeringan ke MC kerja rute)
    route_mc = {"pirolisis": 15, "cofiring": P("limbah.cofiring_mc_max"), "pembakaran": 35, "gasifikasi": 15,
                "pembakaran_kecil": 35}
    route_eta = {"cofiring": eta["cofiring_pltu"], "pembakaran": eta["turbin_uap_kecil"], "gasifikasi": eta["terintegrasi"]}
    routes = []
    for key, label in ROUTES.items():
        dry_gj = _drying_gj(t, x.moisture_pct, route_mc[key])
        out = {"route": key, "label": label, "feasible": all(c["ok"] for c in checks[key]), "checks": checks[key],
               "drying_gj_per_month": round(dry_gj, 1)}
        if key in route_eta:
            net_gj = max(0.0, th_gj - dry_gj)
            mwh = net_gj * route_eta[key] / 3.6
            out.update({"eta_el": route_eta[key], "electricity_mwh_per_month": round(mwh, 1),
                        "co2_avoided_t_per_month": round(mwh * ef, 2)})
        elif key == "pirolisis":
            dry_t = t * (1 - x.moisture_pct / 100)
            y = biochar_yield_estimate(x.fixed_carbon_pct_db or 16, x.volatile_pct_db or 66, x.ash_pct_db, 500)
            silica_t = dry_t * x.ash_pct_db / 100 * (x.sio2_pct_ash or 0) / 100 * 0.9   # rendemen ekstraksi ≈ 90 %
            out.update({"biochar_t_per_month": round(dry_t * y / 100, 2), "biochar_yield_pct_db": round(y, 1),
                        "bio_silica_potential_t_per_month": round(silica_t, 2) if silica_rich else 0.0,
                        "product": "biochar + bio-silika" if silica_rich else ("arang / karbon aktif" if carbon_rich else "biochar"),
                        "note": "Panas volatil/syngas memasok pengering; karbon biochar → klaim removal (F11), bukan emisi dihindari."})
        else:
            out.update({"process_heat_gj_per_month": round(max(0.0, th_gj - dry_gj) * P("limbah.eta_boiler_heat"), 1)})
        routes.append(out)

    best = next(r for r in routes if r["route"] == choice)
    warnings = []
    if lhv <= 0:
        warnings.append("LHV as-received ≤ 0: air menyerap seluruh energi — keringkan dulu atau pilih jalur biokimia.")
    if x.moisture_pct > 40:
        warnings.append(f"MC {x.moisture_pct:g} %: energi pengeringan besar — pertimbangkan pengeringan matahari di gudang pengepul.")
    if ai is not None and ai > 0.34:
        warnings.append("Indeks alkali > 0,34 kg/GJ: pembakaran/co-firing berisiko terak — campur dengan bahan rendah alkali (Prototipe 1).")
    return {
        "commodity": x.code, "name": x.name,
        "inputs": {"ton_per_month": t, "moisture_pct": x.moisture_pct, "ash_pct_db": x.ash_pct_db, "t_per_day": round(t_day, 2)},
        "energy": {"lhv_db_mj_kg": x.lhv_db_mj_kg, "lhv_ar_mj_kg": round(lhv, 3), "lhv_ar_kcal_kg": round(lhv * KCAL_PER_MJ),
                   "gcv_ar_kcal_kg": round(gcv_ar * KCAL_PER_MJ), "thermal_gj_per_month": round(th_gj, 1),
                   "electricity_mwh_per_month": el,
                   "co2_avoided_t_per_month": {k: round(v * ef, 2) for k, v in el.items()},
                   "grid_ef_t_per_mwh": ef, "alkali_index": round(ai, 3) if ai is not None else None},
        "decision": {"route": choice, "label": ROUTES[choice], "path": path, "best": best},
        "routes": routes, "warnings": warnings,
        "computation_details": {
            "formulas": ["LHV_ar = LHV_db·(1−MC) − 2,443·MC  (ISO 18125)",
                         "E_el [MWh] = massa[kg] × LHV_ar × η / 3600",
                         "CO₂ dihindari = E_el × EF grid JAMALI",
                         "pengeringan = air diuapkan × limbah.drying_mj_per_kg_water"],
            "references": ["ISO 18125:2017", "IRENA 2012 Biomass for Power Generation", "IRENA-ETSAP E21 (2013) Co-firing",
                           "Kepmen ESDM 163.K/2021 faktor emisi grid", "Basu P. (2018) Biomass Gasification, Pyrolysis "
                           "and Torrefaction 3rd ed.", "Zhu dkk. (2014) Front. Energy Res. 2:7", "docs/15 §3–5"],
            "note": "Emisi dihindari ≠ removal; dilaporkan terpisah (GHG Protocol LSR). Nilai master = literatur sampai diganti lab.",
        },
    }
