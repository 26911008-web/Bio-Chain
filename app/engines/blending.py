"""Engine ③ — Blending Optimizer (Linear Programming, solver HiGHS via SciPy).

Mencari campuran feedstock termurah yang memenuhi spesifikasi produk, dengan asumsi
properti campuran = rata-rata berbobot massa (blending linear).
"""

import numpy as np
from pydantic import BaseModel, Field
from scipy.optimize import linprog

from ..params import P
from .quality import biochar_yield_db


class Feedstock(BaseModel):
    id: str
    name: str
    cost_per_ton: float = Field(..., ge=0, description="Rp/ton sampai di pabrik")
    stock_ton: float = Field(..., ge=0)
    moisture: float
    ash: float
    fixed_carbon: float
    min_share: float = Field(0, ge=0, le=1, description="Porsi minimum dalam campuran")


class ProductSpec(BaseModel):
    moisture_max: float | None = None
    ash_max: float | None = None
    fixed_carbon_min: float | None = None


class BlendRequest(BaseModel):
    feedstocks: list[Feedstock]
    spec: ProductSpec
    target_ton: float = Field(..., gt=0)
    pyrolysis_temp_c: float = Field(500, ge=300, le=700)


def default_feedstocks() -> list[Feedstock]:
    """Feedstock pabrik dari menu Parameter (tabel `blending.feedstocks`)."""
    return [Feedstock(**r) for r in P("blending.feedstocks")]


def product_specs() -> dict:
    return {
        "biochar_tanah": {"label": "Biochar pembenah tanah",
                          "spec": ProductSpec(moisture_max=P("blending.biochar_tanah_moisture_max"),
                                              ash_max=P("blending.biochar_tanah_ash_max"),
                                              fixed_carbon_min=P("blending.biochar_tanah_fc_min"))},
        "quick_light_charcoal": {"label": "Quick Light Charcoal",
                                 "spec": ProductSpec(moisture_max=P("blending.qlc_moisture_max"),
                                                     ash_max=P("blending.qlc_ash_max"),
                                                     fixed_carbon_min=P("blending.qlc_fc_min"))},
    }


def _constraints(fs: list[Feedstock], spec: ProductSpec, target: float, skip: str | None = None):
    rows, rhs, names = [], [], []
    if spec.moisture_max is not None and skip != "moisture_max":
        rows.append([f.moisture - spec.moisture_max for f in fs]); rhs.append(0); names.append("moisture_max")
    if spec.ash_max is not None and skip != "ash_max":
        rows.append([f.ash - spec.ash_max for f in fs]); rhs.append(0); names.append("ash_max")
    if spec.fixed_carbon_min is not None and skip != "fixed_carbon_min":
        rows.append([spec.fixed_carbon_min - f.fixed_carbon for f in fs]); rhs.append(0); names.append("fixed_carbon_min")
    for i, f in enumerate(fs):
        if f.min_share > 0 and skip != f"min_share:{f.id}":
            row = [0.0] * len(fs); row[i] = -1.0
            rows.append(row); rhs.append(-f.min_share * target); names.append(f"min_share:{f.id}")
    return rows, rhs, names


def _solve(fs, spec, target, skip=None):
    rows, rhs, _ = _constraints(fs, spec, target, skip)
    return linprog(
        c=[f.cost_per_ton for f in fs],
        A_ub=np.array(rows) if rows else None, b_ub=rhs or None,
        A_eq=[[1.0] * len(fs)], b_eq=[target],
        bounds=[(0, f.stock_ton) for f in fs],
        method="highs",
    )


def optimize_blend(req: BlendRequest) -> dict:
    fs, spec, target = req.feedstocks, req.spec, req.target_ton
    res = _solve(fs, spec, target)

    if res.status != 0:
        _, _, names = _constraints(fs, spec, target)
        blocking = [n for n in names if _solve(fs, spec, target, skip=n).status == 0]
        if sum(f.stock_ton for f in fs) < target:
            blocking.append("stok total < target")
        return {"feasible": False,
                "message": "Tidak ada campuran yang memenuhi spesifikasi dengan stok saat ini. "
                           + ("Longgarkan salah satu batasan di relax_one_of." if blocking
                              else "Kurangi target tonase atau tambah stok feedstock berkualitas tinggi."),
                "relax_one_of": blocking}

    x = [float(v) for v in res.x]
    mix = lambda attr: float(sum(getattr(f, attr) * xi for f, xi in zip(fs, x)) / target)
    blend_ash = mix("ash")
    blend_moisture = mix("moisture")
    y = biochar_yield_db(req.pyrolysis_temp_c, blend_ash)
    biochar_ton = target * (1 - blend_moisture / 100) * y / 100

    return {
        "feasible": True,
        "composition": [
            {"id": f.id, "name": f.name, "ton": round(xi, 2), "share_pct": round(100 * xi / target, 1),
             "cost": round(f.cost_per_ton * xi)}
            for f, xi in zip(fs, x) if xi > 1e-6
        ],
        "total_cost": round(float(res.fun)),
        "cost_per_ton": round(float(res.fun) / target),
        "blend_properties": {"moisture": round(blend_moisture, 2), "ash": round(blend_ash, 2),
                             "fixed_carbon": round(mix("fixed_carbon"), 2)},
        "pred_biochar_yield_pct_db": round(y, 2),
        "pred_biochar_output_ton": round(biochar_ton, 2),
        "pred_sio2_ton": round(target * (1 - blend_moisture / 100) * blend_ash / 100
                               * P("rendemen.sio2_fraction_of_ash"), 2),
        "note": "Model rendemen dikalibrasi untuk sekam; untuk campuran bersifat aproksimasi.",
    }
