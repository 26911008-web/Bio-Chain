"""Router: Lab 7 Engine — workbench analitik khusus Pabrik & Admin.

Sebelumnya endpoint ini publik tanpa login di root (`/quality/score`, `/blend/recommend`, ...).
Sekarang di bawah `/api/v1/labs`, dijaga `require_role` + kebijakan prefix (app.security.policy).
"""

from fastapi import APIRouter, Depends, HTTPException

from ..data import DEPOT, MILLS
from ..dependencies import require_role
from ..engines.blending import BlendRequest, default_feedstocks, optimize_blend, product_specs
from ..engines.biomass_data import presets
from ..engines.carbon import CarbonInput, calculate_carbon_reduction
from ..engines.energy import EnergyAnalysisRequest, analyze as analyze_energy
from ..engines.feedstock import FeedstockCompareRequest, compare_feedstocks
from ..engines.waste_energy import WasteStream, advise
from ..engines.forecaster import ForecastInput, forecast_supply
from ..engines.incentive import DeliveryEvent, calculate_incentive
from ..engines.quality import FeedstockSample, score_sample, yield_curve
from ..models.user import UserRole
from . import routing

LAB_ROLES = (UserRole.PABRIK, UserRole.ADMIN)

router = APIRouter(dependencies=[Depends(require_role(*LAB_ROLES))])


@router.post("/quality/score")
def quality_score(sample: FeedstockSample):
    return score_sample(sample)


@router.get("/quality/yield-curve")
def quality_yield_curve(ash: float | None = None):
    return yield_curve(ash)


@router.get("/blend/defaults")
def blend_defaults():
    return {
        "feedstocks": [f.model_dump() for f in default_feedstocks()],
        "products": {k: {"label": v["label"], "spec": v["spec"].model_dump()} for k, v in product_specs().items()},
    }


@router.post("/blend/recommend")
def blend_recommend(req: BlendRequest):
    if not req.feedstocks:
        raise HTTPException(422, "Minimal satu feedstock.")
    return optimize_blend(req)


@router.get("/supply/mills")
def supply_mills():
    return {"depot": DEPOT, "mills": MILLS}


@router.post("/carbon/calculate")
def carbon_calc(inp: CarbonInput):
    """Hitung pengurangan emisi CO₂ — IPCC Tier 2."""
    return calculate_carbon_reduction(inp)


@router.post("/forecast/supply")
def forecast(inp: ForecastInput):
    return forecast_supply(inp)


@router.post("/incentive/calculate")
def incentive_calc(event: DeliveryEvent):
    return calculate_incentive(event)


@router.get("/biomass/presets")
def biomass_presets():
    """Nilai tipikal literatur untuk mengisi form (ganti dengan hasil uji lab)."""
    return [p.__dict__ for p in presets().values()]


@router.post("/feedstock/compare")
def feedstock_compare(req: FeedstockCompareRequest):
    """⑧ Analisis & perbandingan feedstock (TOPSIS) + rekomendasi awal blending."""
    try:
        return compare_feedstocks(req)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/waste-energy/advise")
def waste_energy_advise(stream: WasteStream):
    """⑨ Rekomendasi teknologi konversi & estimasi potensi energi dari karakteristik/volume limbah."""
    return advise(stream)


@router.post("/energy/analyze")
def energy_analyze(req: EnergyAnalysisRequest):
    """⑩ Analisis IKE/SEC/anomali untuk data histori yang diunggah (mis. fasilitas lain)."""
    try:
        return analyze_energy(req)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


router.include_router(routing.router)          # POST /api/v1/labs/routes/optimize
