"""Router: Engine ⑤ Route Optimizer — membungkus engine murni `app.engines.routing`.

Sumber data penggilingan diinjeksi lewat `get_supply_network`, sehingga tes (atau versi produksi
berbasis DB) cukup menimpa dependency tanpa menyentuh algoritma.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from ..concurrency import run_cpu
from ..data import DEPOT, MILLS
from ..engines.routing import SolverLimitError, plan_routes
from ..schemas.routing import RouteRequest, RouteResponse

router = APIRouter()


def get_supply_network() -> tuple[dict, list[dict]]:
    """Dependency: (depot, daftar penggilingan). Versi produksi: query DB / cache Redis."""
    return DEPOT, MILLS


@router.post("/routes/optimize", response_model=RouteResponse)
async def routes_optimize(
    req: RouteRequest,
    network: Annotated[tuple[dict, list[dict]], Depends(get_supply_network)],
):
    """Optimasi rute penjemputan sekam (CVRP berbatas volume) + jejak komputasi yang dapat diaudit."""
    depot, mills = network
    if req.mill_ids:
        wanted = set(req.mill_ids)
        mills = [m for m in mills if m["id"] in wanted]
    if not mills:
        raise HTTPException(422, "Tidak ada penggilingan yang dipilih.")
    try:
        # CPU-bound: thread pool berkapasitas terbatas; antrean penuh → 503 (lihat app.concurrency).
        return await run_cpu(plan_routes, depot, mills, req)
    except SolverLimitError as e:
        raise HTTPException(422, str(e)) from e
    except (ZeroDivisionError, FloatingPointError, OverflowError, ValueError) as e:
        raise HTTPException(422, f"Data input tidak dapat dihitung: {e}") from e
