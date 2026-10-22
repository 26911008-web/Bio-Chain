"""Engine ③b — Least-cost fuel blending multi-biomassa + indeks keamanan abu (slagging/fouling). Prototipe 1 (fase 2).

Variabel keputusan xᵢ = kg BAHAN KERING komoditas i (semua kendala jadi linear, solver HiGHS via SciPy):

    min  Σ xᵢ·[harga_arᵢ/(1−MCᵢ) + biaya_keringᵢ]
    s.t. Σ xᵢ = D                                   D = target produk × (1 − MC_produk)
         Σ xᵢ·(LHV_dᵢ − LHV_d,min) ≥ 0             LHV_d,min dari target LHV_ar pada MC produk (ISO 18125)
         Σ xᵢ·(Aᵢ − A_max) ≤ 0 ;  Σ xᵢ·(Clᵢ − Cl_max) ≤ 0 ;  Σ xᵢ·(Sᵢ − S_max) ≤ 0
         Σ xᵢ·(Aᵢ·alkᵢ/10⁴ − AI_max·HHVᵢ/1000) ≤ 0  indeks alkali Miles 1996 ditulis linear (docs/15 §2)
         0 ≤ xᵢ ≤ stokᵢ·(1−MCᵢ);  porsi min/maks opsional

Rumus energi: LHV_ar = LHV_d·(1−MC) − 2,443·MC  [MJ/kg; MC fraksi] — ISO 18125:2017 (24,43 J/g per % air).
Indeks abu dihitung dari komposisi oksida campuran BERBOBOT MASSA ABU (rasio tidak aditif): B/A, Rs, Fu, Si/Al, G
(ambang Zhu dkk. 2014, Front. Energy Res. 2:7). Indeks ini berasal dari batu bara dan sering bertentangan untuk
biomassa (Garcia-Maraver 2017; Lachman 2021) → hasil = penyaring awal; uji AFT ISO 21404 tetap wajib.
"""

import numpy as np
from pydantic import BaseModel, Field, model_validator
from scipy.optimize import linprog

LATENT = 2.443                       # MJ/kg air, ISO 18125
KCAL_PER_MJ = 238.846
OXIDES = ("sio2", "k2o", "na2o", "cao", "mgo", "fe2o3", "al2o3", "p2o5")

THRESHOLDS = {  # (batas_rendah, batas_tinggi, label) — Zhu dkk. 2014 Tabel 4; Miles 1996
    "alkali_index": (0.17, 0.34, "kg/GJ: <0,17 rendah · 0,17–0,34 mungkin terak · >0,34 hampir pasti terak"),
    "base_acid": (0.206, 0.4, "<0,206 rendah · 0,206–0,4 sedang · >0,4 tinggi"),
    "slagging_rs": (0.6, 2.0, "<0,6 rendah · 0,6–2,0 sedang · >2,0 tinggi"),
    "fouling_fu": (0.6, 40.0, "<0,6 rendah · 0,6–40 tinggi · >40 sangat tinggi"),
    "chlorine_pct": (0.2, 0.3, "% bk: <0,2 rendah · 0,2–0,3 sedang · >0,3 tinggi (korosi HCl)"),
}

PRESETS = {   # spesifikasi produk; nilai ISO 17225-6 bertanda [L] di docs/15 §9b (standar berbayar)
    "pelet_iso17225_6_a": {"label": "Pelet non-kayu ISO 17225-6 kelas A", "product_moisture_pct": 12,
                           "lhv_ar_min_mj": 14.5, "ash_max_pct": 6, "cl_max_pct": 0.10, "s_max_pct": 0.20},
    "pelet_iso17225_6_b": {"label": "Pelet non-kayu ISO 17225-6 kelas B", "product_moisture_pct": 15,
                           "lhv_ar_min_mj": 14.5, "ash_max_pct": 10, "cl_max_pct": 0.30, "s_max_pct": 0.30},
    # Pasar pelet RI & spesifikasi PLN menyebut kalori sebagai GCV as-received (bukan NCV) — docs/15 §5
    "pelet_4000_kcal": {"label": "Pelet industri 4.000 kcal/kg (GCV ar, praktik pasar)", "product_moisture_pct": 10,
                        "lhv_ar_min_mj": round(4000 / KCAL_PER_MJ, 2), "calorific_basis": "gcv_ar", "ash_max_pct": 10,
                        "cl_max_pct": 0.30, "s_max_pct": 0.30},
    "briket_sni": {"label": "Briket biomassa (SNI / pasar: GCV ≥ 4.400 kcal/kg, MC ≤ 8 %, abu ≤ 8 %)", "product_moisture_pct": 8,
                   "lhv_ar_min_mj": round(4400 / KCAL_PER_MJ, 2), "calorific_basis": "gcv_ar", "ash_max_pct": 8,
                   "cl_max_pct": 0.20, "s_max_pct": 0.20},
    "cofiring_pln": {"label": "Co-firing PLTU (spek woodchip PLN: GCV ≥ 3.009 kcal/kg, MC ≤ 25 %)", "product_moisture_pct": 25,
                     "lhv_ar_min_mj": round(3009 / KCAL_PER_MJ, 2), "calorific_basis": "gcv_ar", "ash_max_pct": 10,
                     "cl_max_pct": 0.30, "s_max_pct": 0.30},
}


class BlendFeed(BaseModel):
    code: str
    name: str
    available_kg: float = Field(..., ge=0, description="Stok basah (as received)")
    price_per_kg: float = Field(..., ge=0, description="Rp/kg basah sampai pabrik")
    moisture_pct: float = Field(..., ge=0, lt=95)
    ash_pct_db: float = Field(..., ge=0, lt=60)
    lhv_db_mj_kg: float = Field(..., gt=5, lt=35)
    hhv_db_mj_kg: float | None = Field(None, gt=5, lt=35)
    chlorine_pct_db: float | None = Field(None, ge=0, le=5)
    sulfur_pct_db: float | None = Field(None, ge=0, le=5)
    sio2_pct_ash: float | None = None
    k2o_pct_ash: float | None = None
    na2o_pct_ash: float | None = None
    cao_pct_ash: float | None = None
    mgo_pct_ash: float | None = None
    fe2o3_pct_ash: float | None = None
    al2o3_pct_ash: float | None = None
    p2o5_pct_ash: float | None = None
    min_share_pct: float = Field(0, ge=0, le=100, description="Porsi minimum (basis kering)")
    max_share_pct: float = Field(100, ge=0, le=100, description="Porsi maksimum, mis. sekam ≤ 30 % untuk durabilitas pelet")

    @property
    def hhv(self) -> float:
        return self.hhv_db_mj_kg or self.lhv_db_mj_kg + 1.2          # LHV_d ≈ HHV_d − 1,1…1,3 (docs/15 §1a)

    @property
    def alkali_known(self) -> bool:
        return self.k2o_pct_ash is not None                                # Na₂O kecil; boleh kosong (dianggap 0)

    @property
    def alkali(self) -> float:
        return (self.k2o_pct_ash or 0) + (self.na2o_pct_ash or 0)


class BlendSpec(BaseModel):
    target_kg: float = Field(..., gt=0, le=10_000_000, description="Massa produk pada kadar air produk")
    product_moisture_pct: float = Field(10, ge=0, lt=60)
    lhv_ar_min_mj: float | None = Field(None, gt=0, lt=30, description="Target kalori as-received (MJ/kg) pada basis di bawah")
    calorific_basis: str = Field("ncv_ar", pattern="^(ncv_ar|gcv_ar)$",
                                 description="ncv_ar = LHV_d(1−MC) − 2,443·MC; gcv_ar = HHV_d(1−MC)")
    ash_max_pct: float | None = Field(None, gt=0, lt=60)
    cl_max_pct: float | None = Field(None, gt=0, lt=5)
    s_max_pct: float | None = Field(None, gt=0, lt=5)
    ai_max: float | None = Field(0.34, gt=0, lt=5, description="Batas indeks alkali (kg/GJ); None = hanya dilaporkan")
    drying_cost_rp_per_kg_water: float | None = Field(None, ge=0, le=10_000)


class BlendOptimizeRequest(BaseModel):
    feeds: list[BlendFeed] = Field(..., min_length=1, max_length=20)
    spec: BlendSpec

    @model_validator(mode="after")
    def _unique(self):
        if len({f.code for f in self.feeds}) != len(self.feeds):
            raise ValueError("Komoditas ganda dalam daftar")
        return self


def lhv_ar(lhv_d: float, mc_pct: float) -> float:
    mc = mc_pct / 100
    return lhv_d * (1 - mc) - LATENT * mc


def _water_per_dry(mc_pct: float) -> float:
    return mc_pct / (100 - mc_pct)


def _level(key: str, v: float | None) -> str:
    if v is None:
        return "tidak_diketahui"
    lo, hi, _ = THRESHOLDS[key]
    return "rendah" if v < lo else ("sedang" if v <= hi else "tinggi")


def evaluate(feeds: list[BlendFeed], dry_kg: list[float], product_moisture_pct: float) -> dict:
    """Sifat campuran + indeks abu untuk komposisi kering tertentu (dipakai solver & slider manual)."""
    D = sum(dry_kg)
    if D <= 0:
        raise ValueError("Komposisi kosong")
    w = [x / D for x in dry_kg]
    lhv_d = sum(wi * f.lhv_db_mj_kg for wi, f in zip(w, feeds))
    hhv_d = sum(wi * f.hhv for wi, f in zip(w, feeds))
    ash = sum(wi * f.ash_pct_db for wi, f in zip(w, feeds))
    cl = sum(wi * (f.chlorine_pct_db or 0) for wi, f in zip(w, feeds))
    s = sum(wi * (f.sulfur_pct_db or 0) for wi, f in zip(w, feeds))
    alk_kg_per_kg = sum(wi * f.ash_pct_db * f.alkali / 1e4 for wi, f in zip(w, feeds))
    # K₂O tidak diketahui pada bahan yang dipakai → indeks "tidak diketahui", BUKAN 0 (gagal-terbuka berbahaya)
    alkali_known = all(f.alkali_known for wi, f in zip(w, feeds) if wi > 1e-9)
    ai = alk_kg_per_kg / (hhv_d / 1000) if hhv_d > 0 and alkali_known else None
    ash_mass = [wi * f.ash_pct_db for wi, f in zip(w, feeds)]
    oxide_known = all(f.sio2_pct_ash is not None and f.k2o_pct_ash is not None for wi, f in zip(w, feeds) if wi > 1e-9)
    ox = {o: (sum(a * (getattr(f, f"{o}_pct_ash") or 0) for a, f in zip(ash_mass, feeds) if a > 0) / sum(ash_mass))
          if sum(ash_mass) > 0 and oxide_known else None for o in OXIDES}
    ba = rs = fu = si_al = g = None
    if oxide_known and sum(ash_mass) > 0:
        base = ox["fe2o3"] + ox["cao"] + ox["mgo"] + ox["na2o"] + ox["k2o"]
        acid = ox["sio2"] + ox["al2o3"]
        ba = base / acid if acid > 0 else None
        rs = ba * s if ba is not None else None
        fu = ba * (ox["na2o"] + ox["k2o"]) if ba is not None else None
        si_al = ox["sio2"] / ox["al2o3"] if ox["al2o3"] > 0 else None
        gden = ox["sio2"] + ox["fe2o3"] + ox["cao"] + ox["mgo"]
        g = 100 * ox["sio2"] / gden if gden > 0 else None
    lhv_p = lhv_ar(lhv_d, product_moisture_pct)
    gcv_p = hhv_d * (1 - product_moisture_pct / 100)
    indices = {"alkali_index": ai, "base_acid": ba, "slagging_rs": rs, "fouling_fu": fu, "chlorine_pct": cl}
    levels = {k: _level(k, v) for k, v in indices.items()}
    warnings = []
    if levels["alkali_index"] == "tidak_diketahui":
        warnings.append("Indeks alkali tidak diketahui: K₂O abu belum diisi untuk bahan yang dipakai — uji XRF/AAS abu "
                        "sebelum dibakar di boiler (risiko terak tidak bisa dinilai).")
    if levels["alkali_index"] == "tinggi":
        warnings.append("Risiko Tinggi Terak/Slagging pada Boiler Industri (indeks alkali > 0,34 kg/GJ)")
    elif levels["alkali_index"] == "sedang":
        warnings.append("Terak mungkin terjadi (indeks alkali 0,17–0,34 kg/GJ) — pantau deposit & suhu bed")
    if levels["chlorine_pct"] == "tinggi":
        warnings.append("Klorin tinggi → korosi HCl/KCl pada superheater")
    husk = sum(wi for wi, f in zip(w, feeds) if f.code == "sekam_padi")
    if husk > 0.3:
        warnings.append(f"Sekam {husk * 100:.0f} % (bk): silika abu mengkristal (kristobalit) di atas ±800 °C — "
                        "jaga suhu tungku & pakai APD debu abu (Fernandes 2016)")
    if ox.get("k2o") and ox.get("sio2") and ox["k2o"] > 10 and ox["sio2"] > 40:
        warnings.append("Campuran kaya K₂O + SiO₂: risiko K-silikat bertitik leleh rendah (interaksi tidak tertangkap "
                        "rata-rata linear) — uji AFT ISO 21404")
    return {
        "lhv_db_mj_kg": round(lhv_d, 3), "hhv_db_mj_kg": round(hhv_d, 3),
        "lhv_ar_mj_kg": round(lhv_p, 3), "lhv_ar_kcal_kg": round(lhv_p * KCAL_PER_MJ),
        "gcv_ar_mj_kg": round(gcv_p, 3), "gcv_ar_kcal_kg": round(gcv_p * KCAL_PER_MJ),
        "product_moisture_pct": product_moisture_pct, "ash_pct_db": round(ash, 3), "chlorine_pct_db": round(cl, 4),
        "sulfur_pct_db": round(s, 4),
        "ash_oxides_pct": {k: (round(v, 2) if v is not None else None) for k, v in ox.items()},
        "indices": {k: (round(v, 3) if v is not None else None) for k, v in {**indices, "si_al": si_al, "viscosity_g": g}.items()},
        "risk_levels": levels,
        "thresholds": {k: v[2] for k, v in THRESHOLDS.items()},
        "warnings": warnings,
        "slagging_verdict": "BAHAYA" if levels["alkali_index"] == "tinggi" else
                            ("WASPADA" if "sedang" in (levels["alkali_index"], levels["base_acid"], levels["chlorine_pct"])
                             or levels["chlorine_pct"] == "tinggi" or levels["alkali_index"] == "tidak_diketahui" else "AMAN"),
    }


def _rows(feeds: list[BlendFeed], spec: BlendSpec, D: float, skip: str | None = None):
    A, b, names = [], [], []
    def add(name, row, rhs):
        if skip != name:
            A.append(row); b.append(rhs); names.append(name)
    if spec.lhv_ar_min_mj is not None:
        mc = spec.product_moisture_pct / 100
        if spec.calorific_basis == "gcv_ar":
            add("lhv_min", [spec.lhv_ar_min_mj / (1 - mc) - f.hhv for f in feeds], 0.0)
        else:
            lhv_d_min = (spec.lhv_ar_min_mj + LATENT * mc) / (1 - mc)
            add("lhv_min", [lhv_d_min - f.lhv_db_mj_kg for f in feeds], 0.0)
    if spec.ash_max_pct is not None:
        add("ash_max", [f.ash_pct_db - spec.ash_max_pct for f in feeds], 0.0)
    if spec.cl_max_pct is not None:
        add("cl_max", [(f.chlorine_pct_db or 0) - spec.cl_max_pct for f in feeds], 0.0)
    if spec.s_max_pct is not None:
        add("s_max", [(f.sulfur_pct_db or 0) - spec.s_max_pct for f in feeds], 0.0)
    if spec.ai_max is not None:
        add("alkali_index_max", [f.ash_pct_db * f.alkali / 1e4 - spec.ai_max * f.hhv / 1000 for f in feeds], 0.0)
        for i, f in enumerate(feeds):                       # K₂O tak diketahui → tidak boleh dipakai saat batas terak aktif
            if not f.alkali_known:
                row = [0.0] * len(feeds); row[i] = 1.0
                add(f"alkali_unknown:{f.code}", row, 0.0)
    for i, f in enumerate(feeds):
        if f.min_share_pct > 0:
            row = [0.0] * len(feeds); row[i] = -1.0
            add(f"min_share:{f.code}", row, -f.min_share_pct / 100 * D)
    return A, b, names


def _unit_cost(f: BlendFeed, spec: BlendSpec) -> float:
    purchase = f.price_per_kg / (1 - f.moisture_pct / 100)
    water = max(0.0, _water_per_dry(f.moisture_pct) - _water_per_dry(spec.product_moisture_pct))
    return purchase + water * (spec.drying_cost_rp_per_kg_water or 0)


def _solve(feeds, spec, D, skip=None):
    A, b, _ = _rows(feeds, spec, D, skip)
    bounds = [(0, min(f.available_kg * (1 - f.moisture_pct / 100), f.max_share_pct / 100 * D)) for f in feeds]
    return linprog(c=[_unit_cost(f, spec) for f in feeds], A_ub=np.array(A) if A else None, b_ub=b or None,
                   A_eq=[[1.0] * len(feeds)], b_eq=[D], bounds=bounds, method="highs")


def optimize(req: BlendOptimizeRequest) -> dict:
    feeds, spec = req.feeds, req.spec
    D = spec.target_kg * (1 - spec.product_moisture_pct / 100)
    res = _solve(feeds, spec, D)
    method = {"method": "LP biaya terendah basis kering (SciPy HiGHS)", "dry_target_kg": round(D, 2),
              "objective": "Σ xᵢ·[harga_ar/(1−MC) + air diuapkan × biaya pengeringan]",
              "lhv_formula": "LHV_ar = LHV_d·(1−MC) − 2,443·MC (ISO 18125)",
              "alkali_constraint": "Σ xᵢ·(Aᵢ·alkᵢ/10⁴ − AI_max·HHVᵢ/1000) ≤ 0 (Miles 1996, docs/15 §2)",
              "drying_cost_included": spec.drying_cost_rp_per_kg_water is not None}
    if res.status != 0:
        _, _, names = _rows(feeds, spec, D)
        relax = [n for n in names if _solve(feeds, spec, D, skip=n).status == 0]
        stock_dry = sum(min(f.available_kg * (1 - f.moisture_pct / 100), f.max_share_pct / 100 * D) for f in feeds)
        return {"feasible": False, "relax_one_of": relax, "stock_dry_kg": round(stock_dry, 1),
                "message": ("Tidak ada campuran yang memenuhi semua batas. " +
                            (f"Melonggarkan salah satu dari: {', '.join(relax)} membuatnya layak." if relax else
                             "Tambah stok bahan rendah abu/alkali atau kurangi target.")),
                "computation_details": method}
    x = [float(v) for v in res.x]
    props = evaluate(feeds, x, spec.product_moisture_pct)
    comp, purchase_total, drying_total = [], 0.0, 0.0
    for f, xi in zip(feeds, x):
        if xi <= 1e-6:
            continue
        wet = xi / (1 - f.moisture_pct / 100)
        water = max(0.0, _water_per_dry(f.moisture_pct) - _water_per_dry(spec.product_moisture_pct)) * xi
        cost_buy = wet * f.price_per_kg
        cost_dry = water * (spec.drying_cost_rp_per_kg_water or 0)
        purchase_total += cost_buy; drying_total += cost_dry
        comp.append({"code": f.code, "name": f.name, "dry_kg": round(xi, 1), "wet_kg_to_use": round(wet, 1),
                     "share_dry_pct": round(100 * xi / D, 2), "water_to_evaporate_kg": round(water, 1),
                     "purchase_rp": round(cost_buy), "drying_rp": round(cost_dry)})
    total = purchase_total + drying_total
    return {
        "feasible": True, "composition": comp, "properties": props,
        "cost": {"purchase_rp": round(purchase_total), "drying_rp": round(drying_total), "total_rp": round(total),
                 "rp_per_kg_product": round(total / spec.target_kg, 1),
                 "rp_per_gj_ncv": round(total / (spec.target_kg * props["lhv_ar_mj_kg"] / 1000)) if props["lhv_ar_mj_kg"] > 0 else None},
        "feasibility_card": _card(props, spec),
        "computation_details": method,
    }


def _card(props: dict, spec: BlendSpec) -> dict:
    checks = []
    def chk(name, ok, detail):
        checks.append({"check": name, "ok": ok, "detail": detail})
    if spec.lhv_ar_min_mj is not None:
        key, lbl = ("gcv_ar", "GCV ar") if spec.calorific_basis == "gcv_ar" else ("lhv_ar", "NCV ar")
        chk("Nilai kalor", props[f"{key}_mj_kg"] >= spec.lhv_ar_min_mj - 1e-3,
            f"{props[f'{key}_kcal_kg']} kcal/kg {lbl} vs min {round(spec.lhv_ar_min_mj * KCAL_PER_MJ)}")
    if spec.ash_max_pct is not None:
        chk("Abu", props["ash_pct_db"] <= spec.ash_max_pct + 1e-6, f"{props['ash_pct_db']} % bk vs maks {spec.ash_max_pct}")
    if spec.cl_max_pct is not None:
        chk("Klorin", props["chlorine_pct_db"] <= spec.cl_max_pct + 1e-6, f"{props['chlorine_pct_db']} % vs maks {spec.cl_max_pct}")
    ai = props["indices"]["alkali_index"]
    if spec.ai_max is not None:                             # sama dengan batas yang dipakai optimizer (parameter)
        chk("Indeks alkali", ai is not None and ai <= spec.ai_max + 1e-6,
            f"{ai if ai is not None else 'tidak diketahui'} kg/GJ vs maks {spec.ai_max:g} ({props['risk_levels']['alkali_index']})")
    if spec.s_max_pct is not None:
        chk("Sulfur", props["sulfur_pct_db"] <= spec.s_max_pct + 1e-6, f"{props['sulfur_pct_db']} % vs maks {spec.s_max_pct}")
    # Vonis = cek terhadap batas yang SAMA dengan optimizer (parameter). Bila pengguna sengaja melonggarkan batas alkali
    # (mis. memakai aditif kaolin), risiko terak tetap ditampilkan terpisah & tegas — tidak disembunyikan.
    verdict = "LAYAK" if all(c["ok"] for c in checks) else "TIDAK LAYAK"
    rec = ("Uji AFT (ISO 21404) & durabilitas pelet sebelum produksi rutin; indeks abu turunan kriteria batu bara hanya "
           "penyaring awal (Zhu 2014; Lachman 2021).")
    if props["slagging_verdict"] == "BAHAYA":
        rec = ("PERINGATAN: indeks alkali > 0,34 kg/GJ (hampir pasti terak) — hanya untuk tungku dengan aditif "
               "pengikat alkali (kaolin/zeolit) atau suhu bed rendah. " + rec)
    return {"verdict": verdict, "slagging": props["slagging_verdict"], "checks": checks, "recommendation": rec}

