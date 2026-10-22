"""Engine ⑧ — Analisis, Perbandingan & Rekomendasi Awal Feedstock Biomassa.

Masukan: parameter tiap feedstock (proksimat, kadar air, harga, stok) + produk tujuan.
Keluaran:
  1. Properti turunan per feedstock: HHV (Parikh 2005), LHV as-received, rasio bahan bakar FC/VM,
     estimasi rendemen biochar, biaya per GJ dan per ton biochar.
  2. Peringkat multi-kriteria TOPSIS (Hwang & Yoon 1981) dengan bobot sesuai produk tujuan.
  3. Rekomendasi awal: feedstock utama + campuran termurah yang memenuhi spesifikasi (LP HiGHS,
     Engine ③) bila spesifikasi & target diberikan.
"""

from typing import Literal

import numpy as np
from pydantic import BaseModel, Field, model_validator

from ..params import weights
from .biomass_data import biochar_yield_estimate, hhv_parikh, lhv_as_received, presets
from .blending import BlendRequest, Feedstock, ProductSpec, optimize_blend

Purpose = Literal["biochar", "pellet", "pembakaran"]

# (kriteria, kunci bobot, arah) — arah +1 = makin besar makin baik, −1 = makin kecil makin baik.
# Bobot dibaca dari menu Parameter (feedstock.*) dan dinormalisasi agar berjumlah 1.
_CRITERIA_SPEC = {
    "biochar": ("feedstock.biochar_w_", [("biochar_yield_pct_db", "yield", +1), ("fixed_carbon", "fc", +1),
                                         ("cost_per_ton_biochar", "cost", -1), ("moisture", "moisture", -1),
                                         ("ash", "ash", -1)]),
    "pellet": ("feedstock.pellet_w_", [("lhv_ar_mj_kg", "lhv", +1), ("ash", "ash", -1), ("moisture", "moisture", -1),
                                       ("cost_per_gj", "cost", -1)]),
    "pembakaran": ("feedstock.burn_w_", [("lhv_ar_mj_kg", "lhv", +1), ("cost_per_gj", "cost", -1), ("ash", "ash", -1),
                                         ("moisture", "moisture", -1)]),
}


def criteria(purpose: str) -> list[tuple[str, float, int]]:
    prefix, spec = _CRITERIA_SPEC[purpose]
    w = weights(prefix)
    return [(field, w[wkey], direction) for field, wkey, direction in spec]
CRITERIA_LABEL = {
    "biochar_yield_pct_db": "rendemen biochar", "fixed_carbon": "fixed carbon", "cost_per_ton_biochar":
    "biaya per ton biochar", "moisture": "kadar air", "ash": "kadar abu", "lhv_ar_mj_kg": "nilai kalor (LHV)",
    "cost_per_gj": "biaya per GJ",
}


class FeedstockInput(BaseModel):
    id: str = Field(..., min_length=1, max_length=40)
    name: str | None = None
    preset: str | None = Field(None, description="Kode preset biomassa (menu Parameter → Preset Biomassa)")
    moisture: float | None = Field(None, ge=0, le=90, description="% basis basah")
    ash: float | None = Field(None, ge=0, le=60, description="% basis kering")
    volatile_matter: float | None = Field(None, ge=0, le=100)
    fixed_carbon: float | None = Field(None, ge=0, le=100)
    hhv_mj_kg: float | None = Field(None, gt=0, le=35, description="HHV basis kering terukur (opsional)")
    cost_per_ton: float = Field(..., ge=0, description="Rp/ton as received sampai pabrik")
    stock_ton: float = Field(0, ge=0)

    @model_validator(mode="after")
    def _fill_from_preset(self):
        if self.preset:
            p = presets().get(self.preset)
            if p is None:
                raise ValueError(f"preset '{self.preset}' tidak dikenal")
            for f in ("moisture", "ash", "volatile_matter", "fixed_carbon"):
                if getattr(self, f) is None:
                    setattr(self, f, getattr(p, f))
            self.name = self.name or p.name
        missing = [f for f in ("moisture", "ash", "volatile_matter", "fixed_carbon") if getattr(self, f) is None]
        if missing:
            raise ValueError(f"{self.id}: isi {missing} atau gunakan preset")
        if abs(self.ash + self.volatile_matter + self.fixed_carbon - 100) > 5:
            raise ValueError(f"{self.id}: Abu + VM + FC harus ≈ 100% basis kering")
        self.name = self.name or self.id
        return self


class FeedstockCompareRequest(BaseModel):
    feedstocks: list[FeedstockInput] = Field(..., min_length=2, max_length=200)
    purpose: Purpose = "biochar"
    pyrolysis_temp_c: float = Field(500, ge=300, le=700)
    spec: ProductSpec | None = Field(None, description="Opsional: jalankan LP blending termurah")
    target_ton: float | None = Field(None, gt=0)


def _properties(f: FeedstockInput, temp_c: float) -> dict:
    hhv = f.hhv_mj_kg or hhv_parikh(f.fixed_carbon, f.volatile_matter, f.ash)
    lhv = lhv_as_received(hhv, f.moisture)
    y = biochar_yield_estimate(f.fixed_carbon, f.volatile_matter, f.ash, temp_c)
    dry = 1 - f.moisture / 100
    biochar_t_per_t = dry * y / 100
    return {
        "id": f.id, "name": f.name, "moisture": f.moisture, "ash": f.ash, "volatile_matter": f.volatile_matter,
        "fixed_carbon": f.fixed_carbon, "stock_ton": f.stock_ton, "cost_per_ton": f.cost_per_ton,
        "hhv_db_mj_kg": round(hhv, 2), "hhv_source": "terukur" if f.hhv_mj_kg else "Parikh (2005)",
        "lhv_ar_mj_kg": round(lhv, 2), "fuel_ratio_fc_vm": round(f.fixed_carbon / f.volatile_matter, 3),
        "biochar_yield_pct_db": round(y, 1), "biochar_ton_per_ton_received": round(biochar_t_per_t, 3),
        "cost_per_gj": round(f.cost_per_ton / lhv, 0) if lhv > 0 else None,
        "cost_per_ton_biochar": round(f.cost_per_ton / biochar_t_per_t, 0) if biochar_t_per_t > 0 else None,
    }


def topsis(rows: list[dict], criteria: list[tuple[str, float, int]]) -> list[float]:
    """TOPSIS: normalisasi vektor → bobot → jarak ke solusi ideal positif/negatif → koefisien kedekatan."""
    X = np.array([[r[c] for c, _, _ in criteria] for r in rows], dtype=float)
    norm = np.linalg.norm(X, axis=0)
    norm[norm == 0] = 1.0
    w = np.array([wt for _, wt, _ in criteria])
    V = X / norm * w
    direction = np.array([d for _, _, d in criteria])
    ideal = np.where(direction > 0, V.max(axis=0), V.min(axis=0))
    anti = np.where(direction > 0, V.min(axis=0), V.max(axis=0))
    d_pos = np.linalg.norm(V - ideal, axis=1)
    d_neg = np.linalg.norm(V - anti, axis=1)
    denom = d_pos + d_neg
    return list(np.where(denom > 0, d_neg / np.where(denom > 0, denom, 1), 1.0))


def _strengths(row: dict, rows: list[dict], criteria) -> tuple[list[str], list[str]]:
    good, bad = [], []
    for c, _, d in criteria:
        vals = [r[c] for r in rows]
        best, worst = (max(vals), min(vals)) if d > 0 else (min(vals), max(vals))
        if row[c] == best and best != worst:
            good.append(CRITERIA_LABEL[c])
        elif row[c] == worst and best != worst:
            bad.append(CRITERIA_LABEL[c])
    return good, bad


def compare_feedstocks(req: FeedstockCompareRequest) -> dict:
    rows = [_properties(f, req.pyrolysis_temp_c) for f in req.feedstocks]
    criteria = globals()["criteria"](req.purpose)
    usable = [r for r in rows if all(r[c] is not None for c, _, _ in criteria)]
    if len(usable) < 2:
        raise ValueError("Minimal dua feedstock dengan nilai kalor/rendemen positif diperlukan untuk dibandingkan.")
    scores = topsis(usable, criteria)
    for r, s in zip(usable, scores):
        r["topsis_score"] = round(float(s), 4)
        r["strengths"], r["weaknesses"] = _strengths(r, usable, criteria)
    ranking = sorted(usable, key=lambda r: -r["topsis_score"])
    for i, r in enumerate(ranking, 1):
        r["rank"] = i

    top = ranking[0]
    warnings = []
    for r in rows:
        if r["moisture"] > 20 and req.purpose in ("biochar", "pellet"):
            warnings.append(f"{r['name']}: kadar air {r['moisture']}% > 20% — perlu pengeringan sebelum diolah.")
        if r["ash"] > 15 and req.purpose != "biochar":
            warnings.append(f"{r['name']}: abu {r['ash']}% tinggi — risiko slagging/fouling & abrasi die pellet.")
    recommendation = (
        f"Untuk {req.purpose}, {top['name']} paling unggul (skor TOPSIS {top['topsis_score']:.2f}"
        + (f"; unggul pada {', '.join(top['strengths'])}" if top["strengths"] else "") + ")."
    )
    if len(ranking) > 1:
        second = ranking[1]
        recommendation += (f" Alternatif: {second['name']} (skor {second['topsis_score']:.2f}). Campurkan bila stok "
                           f"{top['name']} tidak mencukupi atau untuk menyeimbangkan "
                           f"{', '.join(top['weaknesses']) or 'properti'}.")

    blend = None
    if req.spec is not None and req.target_ton:
        blend = optimize_blend(BlendRequest(
            feedstocks=[Feedstock(id=f.id, name=f.name, cost_per_ton=f.cost_per_ton, stock_ton=f.stock_ton,
                                  moisture=f.moisture, ash=f.ash, fixed_carbon=f.fixed_carbon)
                        for f in req.feedstocks],
            spec=req.spec, target_ton=req.target_ton, pyrolysis_temp_c=req.pyrolysis_temp_c))

    return {
        "purpose": req.purpose,
        "ranking": ranking,
        "recommendation": recommendation,
        "blend": blend,
        "warnings": warnings,
        "computation_details": {
            "criteria": [{"criterion": CRITERIA_LABEL[c], "field": c, "weight": w,
                          "direction": "maks" if d > 0 else "min"} for c, w, d in criteria],
            "formulas": {
                "HHV_db": "0,3536·FC + 0,1559·VM − 0,0078·Ash (Parikh et al. 2005)",
                "LHV_ar": "HHV_db·(1−w) − 2,443·(w + 9·H·(1−w)), H = 6% bk",
                "rendemen_biochar": "Ash + FC + r(T)·VM; r(T) dikalibrasi dari model rendemen sekam (Engine ②)",
                "TOPSIS": "C_i = d⁻ / (d⁺ + d⁻) pada matriks ternormalisasi-vektor berbobot (Hwang & Yoon 1981)",
            },
            "notes": "Properti campuran diasumsikan linear terhadap massa (Engine ③). Nilai preset = tipikal "
                     "literatur; ganti dengan hasil uji laboratorium.",
        },
    }
