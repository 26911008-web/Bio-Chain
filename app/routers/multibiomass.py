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


# ---------------------------------------------------------------- Prototipe 1: blend bahan bakar (fase 2)
class FuelFeedInput(BaseModel):
    code: str = Field(..., max_length=24)
    available_kg: float = Field(..., ge=0, le=100_000_000)
    price_per_kg: float | None = Field(None, ge=0, le=100_000, description="Kosong = harga dasar master")
    moisture_pct: float | None = Field(None, ge=0, lt=95, description="Kosong = MC tipikal master; isi hasil ukur")
    min_share_pct: float = Field(0, ge=0, le=100)
    max_share_pct: float = Field(100, ge=0, le=100)


class FuelBlendRequest(BaseModel):
    preset: str | None = Field(None, description="pelet_iso17225_6_a | pelet_iso17225_6_b | pelet_4000_kcal | cofiring_pln")
    feeds: list[FuelFeedInput] = Field(..., min_length=1, max_length=20)
    target_kg: float = Field(..., gt=0, le=10_000_000)
    product_moisture_pct: float | None = Field(None, ge=0, lt=60)
    lhv_ar_min_kcal: float | None = Field(None, gt=0, lt=7000, description="Target kalori as-received (kcal/kg)")
    calorific_basis: str | None = Field(None, pattern="^(ncv_ar|gcv_ar)$", description="Basis target kalori")
    ash_max_pct: float | None = Field(None, gt=0, lt=60)
    cl_max_pct: float | None = Field(None, gt=0, lt=5)
    s_max_pct: float | None = Field(None, gt=0, lt=5)
    ai_max: float | None = Field(None, gt=0, lt=5)


class FuelEvaluateRequest(BaseModel):
    feeds: list[FuelFeedInput] = Field(..., min_length=1, max_length=20)
    shares_pct: dict[str, float] = Field(..., description="Porsi basis kering per kode (slider)")
    product_moisture_pct: float = Field(10, ge=0, lt=60)


async def _blend_feeds(db: AsyncSession, items: list[FuelFeedInput]):
    from ..engines.fuel_blend import BlendFeed
    from ..models.biomass import OXIDES
    from fastapi import HTTPException
    feeds = []
    for it in items:
        b = await svc.get_biomass(db, it.code)
        price = it.price_per_kg if it.price_per_kg is not None else svc.base_price_for(b)
        if price is None:
            raise HTTPException(422, f"Harga {b.name} belum diisi (isi di baris ini atau harga dasar master).")
        feeds.append(BlendFeed(
            code=b.code, name=b.name, available_kg=it.available_kg, price_per_kg=price,
            moisture_pct=it.moisture_pct if it.moisture_pct is not None else b.moisture_typ_pct,
            ash_pct_db=b.ash_pct_db, lhv_db_mj_kg=b.lhv_db_mj_kg, hhv_db_mj_kg=b.hhv_db_mj_kg,
            chlorine_pct_db=b.chlorine_pct_db, sulfur_pct_db=b.sulfur_pct_db,
            min_share_pct=it.min_share_pct, max_share_pct=it.max_share_pct,
            **{f"{o}_pct_ash": getattr(b, f"{o}_pct_ash") for o in OXIDES}))
    return feeds


@router.get("/factory/fuel-blend/presets")
async def fuel_blend_presets(db: DB, user: Annotated[User, Depends(_operator)]):
    """Preset spesifikasi produk + stok bahan di pabrik (lot diterima, belum diolah) per komoditas."""
    from sqlalchemy import func, select
    from ..engines.fuel_blend import PRESETS, THRESHOLDS
    from ..models.harvest import Harvest
    from ..params import P
    rows = (await db.execute(select(Harvest.commodity, func.coalesce(func.sum(Harvest.received_kg), 0.0))
                             .where(Harvest.received_kg.is_not(None), Harvest.conversion_id.is_(None))
                             .group_by(Harvest.commodity))).all()
    return {"presets": PRESETS, "thresholds": {k: v[2] for k, v in THRESHOLDS.items()},
            "factory_stock_kg": {c or "sekam_padi": round(kg, 1) for c, kg in rows},
            "drying_cost_rp_per_kg_water": P("blending.drying_cost_rp_per_kg_water"),
            "ai_max_default": P("blending.ai_max_kg_gj")}


@router.post("/factory/fuel-blend/optimize")
async def fuel_blend_optimize(req: FuelBlendRequest, db: DB, user: Annotated[User, Depends(_operator)]):
    """Prototipe 1: campuran biaya terendah yang memenuhi nilai kalor, abu, Cl, S dan indeks alkali (anti-terak)."""
    from fastapi import HTTPException
    from ..engines.fuel_blend import KCAL_PER_MJ, PRESETS, BlendOptimizeRequest, BlendSpec, optimize
    from ..params import P
    base = PRESETS.get(req.preset or "", {}) if req.preset else {}
    if req.preset and not base:
        raise HTTPException(422, f"Preset '{req.preset}' tidak dikenal.")
    spec = BlendSpec(
        target_kg=req.target_kg,
        product_moisture_pct=req.product_moisture_pct if req.product_moisture_pct is not None else base.get("product_moisture_pct", 10),
        lhv_ar_min_mj=(req.lhv_ar_min_kcal / KCAL_PER_MJ) if req.lhv_ar_min_kcal else base.get("lhv_ar_min_mj"),
        calorific_basis=req.calorific_basis or base.get("calorific_basis", "ncv_ar"),
        ash_max_pct=req.ash_max_pct if req.ash_max_pct is not None else base.get("ash_max_pct"),
        cl_max_pct=req.cl_max_pct if req.cl_max_pct is not None else base.get("cl_max_pct"),
        s_max_pct=req.s_max_pct if req.s_max_pct is not None else base.get("s_max_pct"),
        ai_max=req.ai_max if req.ai_max is not None else P("blending.ai_max_kg_gj"),
        drying_cost_rp_per_kg_water=P("blending.drying_cost_rp_per_kg_water"))
    out = optimize(BlendOptimizeRequest(feeds=await _blend_feeds(db, req.feeds), spec=spec))
    if spec.drying_cost_rp_per_kg_water is None:
        out.setdefault("notes", []).append("Biaya pengeringan belum dihitung: isi parameter 'Biaya pengeringan per kg "
                                           "air diuapkan' agar bahan basah (mis. ampas tebu) tidak tampak murah.")
    return {"spec": spec.model_dump(), **out}


@router.post("/factory/fuel-blend/evaluate")
async def fuel_blend_evaluate(req: FuelEvaluateRequest, db: DB, user: Annotated[User, Depends(_operator)]):
    """Slider manual: sifat campuran & indeks terak untuk porsi yang dipilih pengguna (tanpa optimasi)."""
    from fastapi import HTTPException
    from ..engines.fuel_blend import evaluate
    feeds = await _blend_feeds(db, req.feeds)
    shares = [max(0.0, req.shares_pct.get(f.code, 0.0)) for f in feeds]
    if sum(shares) <= 0:
        raise HTTPException(422, "Porsi campuran masih kosong.")
    return evaluate(feeds, shares, req.product_moisture_pct)
