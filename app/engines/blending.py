"""Engine ③ — Blending Optimizer (Linear Programming, solver HiGHS via SciPy).

Mencari campuran feedstock termurah yang memenuhi spesifikasi produk, dengan asumsi
properti campuran = rata-rata berbobot massa (blending linear).
"""

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator
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
    model_config = ConfigDict(extra="ignore")
    moisture_max: float | None = None
    ash_max: float | None = None
    fixed_carbon_min: float | None = None


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


class BlendRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    feedstocks: list[Feedstock] = Field(default_factory=default_feedstocks)
    spec: ProductSpec | None = None
    target_ton: float = Field(10.0, gt=0)
    pyrolysis_temp_c: float = Field(500, ge=300, le=700)

    @model_validator(mode="before")
    @classmethod
    def resolve_spec_and_feeds(cls, data: any):
        if isinstance(data, dict):
            # Feedstocks resolution
            if not data.get("feedstocks"):
                data["feedstocks"] = [f.model_dump() for f in default_feedstocks()]
            # Spec resolution: can be string preset like "biochar_tanah", None, or ProductSpec dict
            s = data.get("spec")
            specs_map = product_specs()
            if isinstance(s, str):
                if s in specs_map:
                    data["spec"] = specs_map[s]["spec"].model_dump()
                else:
                    data["spec"] = specs_map["biochar_tanah"]["spec"].model_dump()
            elif s is None:
                data["spec"] = specs_map["biochar_tanah"]["spec"].model_dump()
            elif isinstance(s, dict):
                pass
            if not data.get("target_ton"):
                data["target_ton"] = 10.0
        return data


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
                "relax_one_of": blocking,
                "computation_details": {
                    "method": "Linear Programming Cost Optimization via SciPy HiGHS Solver",
                    "solver_status": "infeasible",
                    "steps": [
                        {"step": "Kelayakan formulasi LP", "formula": "linprog(c, A_ub, b_ub, A_eq, b_eq, bounds)", "value": 0, "unit": "status"},
                    ],
                }}

    x = [float(v) for v in res.x]
    mix = lambda attr: float(sum(getattr(f, attr) * xi for f, xi in zip(fs, x)) / target)
    blend_ash = mix("ash")
    blend_moisture = mix("moisture")
    y = biochar_yield_db(req.pyrolysis_temp_c, blend_ash)
    biochar_ton = target * (1 - blend_moisture / 100) * y / 100

    comp_details = {
        "method": "Linear Programming Cost Optimization via SciPy HiGHS Solver",
        "inputs": {
            "target_ton": target,
            "pyrolysis_temp_c": req.pyrolysis_temp_c,
            "feedstock_count": len(fs),
            "spec": req.spec.model_dump(),
        },
        "solver_status": "optimal",
        "steps": [
            {"step": "Kendala neraca massa", "formula": "∑(x_i) = target", "value": round(target, 2), "unit": "ton"},
            {"step": "Kadar air rata-rata tertimbang", "formula": "∑(moist_i × x_i) ÷ target", "value": round(blend_moisture, 2), "unit": "%"},
            {"step": "Kadar abu rata-rata tertimbang", "formula": "∑(ash_i × x_i) ÷ target", "value": round(blend_ash, 2), "unit": "%"},
            {"step": "Estimasi rendemen biochar", "formula": "biochar_yield_db(temp, blend_ash)", "value": round(y, 2), "unit": "%"},
            {"step": "Estimasi output biochar", "formula": "target × (1 − moist) × y ÷ 100", "value": round(biochar_ton, 2), "unit": "ton"},
            {"step": "Biaya rata-rata per ton", "formula": "total_cost ÷ target", "value": round(float(res.fun) / target), "unit": "Rp/ton"},
            {"step": "Total biaya optimal campuran", "formula": "min ∑(c_i × x_i)", "value": round(float(res.fun)), "unit": "Rp"},
        ],
        "parameters_used": [
            "rendemen.sio2_fraction_of_ash",
        ],
        "references": [
            "Huangfu, Q. and Hall, J. A. J. (2018) Parallelizing the dual revised simplex method. Mathematical Programming Computation",
        ],
    }

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
        "computation_details": comp_details,
    }
