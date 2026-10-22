"""Router multi-biomassa (018): master komoditas, gudang pengepul berefraksi, kelompok tani & ledger abu agronomi.

Dipasang di prefix /api/v1 — path di bawah memakai namespace peran yang sudah ada (collector/factory/farmer) sehingga
lapisan RoutePolicyMiddleware tetap berlaku; require_role tiap endpoint adalah lapisan kedua.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user, require_role
from ..engines.refraction import refract
from ..models.user import User, UserRole
from ..security.url import EvidenceUrl
from ..services import biomass as svc

router = APIRouter()
_operator = require_role(UserRole.PABRIK, UserRole.ADMIN)
_operator_read = require_role(UserRole.PABRIK, UserRole.ADMIN, UserRole.AUDITOR)
_collector = require_role(UserRole.PENGEPUL)
DB = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------- master komoditas
@router.get("/biomass")
async def biomass_list(db: DB, user: Annotated[User, Depends(get_current_user)], include_inactive: bool = False):
    """Karakteristik komoditas (proksimat, LHV, oksida abu, acuan refraksi, harga dasar). Nilai = literatur bila
    belum diganti hasil lab — lihat kolom `source`."""
    return await svc.list_biomass(db, active_only=not include_inactive)


class BiomassUpdate(BaseModel):
    changes: dict = Field(..., min_length=1)
    source: str = Field(..., min_length=5, max_length=500, description="Dasar perubahan: no. laporan lab / sumber")


@router.put("/biomass/{code}")
async def biomass_update(code: str, req: BiomassUpdate, db: DB, user: Annotated[User, Depends(_operator)]):
    return await svc.update_biomass(db, user, code, req.changes, req.source)


# ---------------------------------------------------------------- gudang pengepul
class WarehouseCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    lat: float | None = Field(None, ge=-11, le=6)
    lon: float | None = Field(None, ge=94, le=142)
    capacity_m3: float | None = Field(None, gt=0, le=100_000)
    is_covered: bool = True


@router.get("/collector/warehouses")
async def warehouses(db: DB, user: Annotated[User, Depends(_collector)]):
    return await svc.list_warehouses(db, user)


@router.post("/collector/warehouses", status_code=201)
async def warehouse_create(req: WarehouseCreate, db: DB, user: Annotated[User, Depends(_collector)]):
    return await svc.create_warehouse(db, user, req.model_dump())


class MovementCreate(BaseModel):
    commodity: str = Field(..., max_length=24)
    movement: str = Field(..., pattern="^(masuk|keluar|susut)$")
    kg: float = Field(..., gt=0, le=200_000)
    moisture_pct: float | None = Field(None, ge=0, le=95)
    contaminant_pct: float | None = Field(None, ge=0, le=100)
    accept_wet: bool = False                     # terima basah di atas batas tolak (pengepul keringkan sendiri)
    harvest_id: int | None = None
    delivery_ref: str | None = Field(None, max_length=40)
    note: str | None = Field(None, max_length=500)
    client_event_id: str | None = Field(None, max_length=64)


@router.get("/collector/warehouses/{warehouse_id}/movements")
async def movements(warehouse_id: int, db: DB, user: Annotated[User, Depends(_collector)]):
    return await svc.list_movements(db, user, warehouse_id)


@router.post("/collector/warehouses/{warehouse_id}/movements", status_code=201)
async def movement_create(warehouse_id: int, req: MovementCreate, db: DB, user: Annotated[User, Depends(_collector)]):
    """Stok masuk (berefraksi kadar air & kontaminan), keluar, atau susut. Idempoten (client_event_id)."""
    return await svc.add_movement(db, user, warehouse_id, req.model_dump())


class RefractionPreview(BaseModel):
    commodity: str
    kg: float = Field(..., gt=0, le=200_000)
    moisture_pct: float | None = Field(None, ge=0, le=95)
    contaminant_pct: float | None = Field(None, ge=0, le=100)
    accept_wet: bool = False


@router.post("/collector/refraction-preview")
async def refraction_preview(req: RefractionPreview, db: DB, user: Annotated[User, Depends(_collector)]):
    """Hitung berat bayar & nilai Rupiah sebelum transaksi (ditunjukkan ke petani di lokasi)."""
    b = await svc.get_biomass(db, req.commodity)
    r = refract(req.kg, req.moisture_pct, req.contaminant_pct, b.moisture_ref_pct, b.moisture_reject_pct,
                b.contaminant_tol_pct, accept_wet=req.accept_wet)
    price = svc.base_price_for(b)
    return {**r, "commodity": b.code, "base_price_per_kg": price,
            "value_rp": round(r["payable_kg"] * price) if price is not None else None,
            "price_missing": price is None}


# ---------------------------------------------------------------- kelompok tani
class GroupCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=120)
    simluhtan_id: str | None = Field(None, max_length=40)
    desa: str | None = Field(None, max_length=100)
    kecamatan: str = Field(..., min_length=2, max_length=100)
    kabupaten: str = Field(..., min_length=2, max_length=100)
    leader_user_id: int | None = None
    leader_name: str = Field(..., min_length=2, max_length=120)
    member_count: int | None = Field(None, ge=1, le=10_000)


@router.get("/factory/farmer-groups")
async def groups(db: DB, user: Annotated[User, Depends(_operator_read)]):
    return await svc.list_groups(db)


@router.post("/factory/farmer-groups", status_code=201)
async def group_create(req: GroupCreate, db: DB, user: Annotated[User, Depends(_operator)]):
    return await svc.create_group(db, req.model_dump())


# ---------------------------------------------------------------- ledger abu
class AshCreate(BaseModel):
    ash_type: str = Field(..., pattern="^(fly_ash|bottom_ash|silica_ash)$")
    source_commodity: str | None = Field(None, max_length=24)
    batch_id: int | None = None
    quantity_kg: float = Field(..., gt=0, le=10_000_000)


class AshLab(BaseModel):
    pb_ppm: float | None = Field(None, ge=0, le=100_000)
    cd_ppm: float | None = Field(None, ge=0, le=100_000)
    as_ppm: float | None = Field(None, ge=0, le=100_000)
    hg_ppm: float | None = Field(None, ge=0, le=100_000)
    cr_ppm: float | None = Field(None, ge=0, le=100_000)
    ni_ppm: float | None = Field(None, ge=0, le=100_000)
    lab_name: str | None = Field(None, max_length=120)
    lab_report_no: str | None = Field(None, max_length=80)
    lab_report_url: EvidenceUrl | None = None
    k2o_pct: float | None = Field(None, ge=0, le=100)
    cao_pct: float | None = Field(None, ge=0, le=100)
    sio2_pct: float | None = Field(None, ge=0, le=100)
    ph: float | None = Field(None, ge=0, le=14)


class AshAllocate(BaseModel):
    farmer_group_id: int
    land_area_ha: float | None = Field(None, gt=0, le=10_000)


class AshHandover(BaseModel):
    photo_url: EvidenceUrl = Field(..., min_length=9)
    lat: float = Field(..., ge=-11, le=6)
    lon: float = Field(..., ge=94, le=142)
    land_area_ha: float | None = Field(None, gt=0, le=10_000)


class AshDispose(BaseModel):
    note: str = Field(..., min_length=10, max_length=1000, description="Tujuan pembuangan berizin / pemanfaatan lain")


@router.get("/factory/ash")
async def ash_list(db: DB, user: Annotated[User, Depends(_operator_read)]):
    return await svc.list_ash(db)


@router.post("/factory/ash", status_code=201)
async def ash_create(req: AshCreate, db: DB, user: Annotated[User, Depends(_operator)]):
    return await svc.create_ash(db, user, req.model_dump())


@router.post("/factory/ash/{ash_id}/lab")
async def ash_lab(ash_id: int, req: AshLab, db: DB, user: Annotated[User, Depends(_operator)]):
    """Hasil uji logam berat → status lulus/gagal dihitung dari batas parameter (Kepmentan 261/2019)."""
    return await svc.record_lab(db, ash_id, req.model_dump())


@router.post("/factory/ash/{ash_id}/allocate")
async def ash_allocate(ash_id: int, req: AshAllocate, db: DB, user: Annotated[User, Depends(_operator)]):
    return await svc.allocate_ash(db, ash_id, req.farmer_group_id, req.land_area_ha)


@router.post("/factory/ash/{ash_id}/handover")
async def ash_handover(ash_id: int, req: AshHandover, db: DB, user: Annotated[User, Depends(_operator)]):
    return await svc.handover_ash(db, user, ash_id, req.model_dump())


@router.post("/factory/ash/{ash_id}/dispose")
async def ash_dispose(ash_id: int, req: AshDispose, db: DB, user: Annotated[User, Depends(_operator)]):
    return await svc.dispose_ash(db, ash_id, req.note)


@router.get("/farmer/ash")
async def farmer_ash(db: DB, user: Annotated[User, Depends(require_role(UserRole.PETANI))]):
    """Ketua Poktan melihat abu yang dialokasikan/diserahkan ke kelompoknya."""
    return await svc.list_ash(db, group_leader=user)
