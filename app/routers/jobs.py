"""Router: Job asinkron untuk komputasi berat (202 Accepted + polling)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import require_role
from ..jobs import get_job_backend
from ..models.user import UserRole
from ..schemas.routing import RouteRequest
from .routing import get_supply_network

router = APIRouter(dependencies=[Depends(require_role(UserRole.PABRIK, UserRole.ADMIN))])


@router.post("/routes/optimize", status_code=202)
async def submit_route_optimization(
    req: RouteRequest,
    network: Annotated[tuple[dict, list[dict]], Depends(get_supply_network)],
    jobs=Depends(get_job_backend),
):
    """Masukkan optimasi rute ke antrean; kembali seketika dengan job_id untuk dipantau."""
    depot, mills = network
    if req.mill_ids:
        wanted = set(req.mill_ids)
        mills = [m for m in mills if m["id"] in wanted]
    if not mills:
        raise HTTPException(422, "Tidak ada penggilingan yang dipilih.")
    job_id = await jobs.submit("route_optimize", {"depot": depot, "mills": mills, "request": req.model_dump()})
    out = {"job_id": job_id, "status": "queued", "backend": jobs.name, "poll_url": f"/api/v1/jobs/{job_id}"}
    if jobs.name == "inline":                         # sudah selesai di request ini: kirim hasil, tanpa polling
        out.update(await jobs.get(job_id) or {})
    return out


@router.get("/{job_id}")
async def get_job(job_id: str, jobs=Depends(get_job_backend)):
    job = await jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Job tidak ditemukan atau sudah kedaluwarsa.")
    return job
