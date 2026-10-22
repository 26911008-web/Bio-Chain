"""Router: Admin (⚙️) — Manajemen users, data seed, system overview."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..concurrency import run_cpu
from ..database import get_db
from ..dependencies import require_role
from ..models.user import User, UserRole, IncentiveTier
from ..models.harvest import Harvest
from ..models.route import Route
from ..models.harvest import Mill
from ..routers.auth import hash_password
from ..services.phone import require_phone

router = APIRouter()

_admin_dep = require_role(UserRole.ADMIN)


class AdminCreateUserRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)        # "   " tidak lolos min_length

    username: str | None = Field(None, min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: str | None = Field(None, max_length=100, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str = Field(..., min_length=8, max_length=20, description="Nomor telepon")
    password: str = Field(..., min_length=6, max_length=100)
    full_name: str = Field(..., min_length=2, max_length=100)
    role: str = Field("petani", pattern="^(petani|pengepul|driver|pabrik|admin|auditor)$")
    kecamatan: str | None = Field(None, max_length=100)
    kabupaten: str | None = Field("Sleman", max_length=100)
    is_active: bool = True
    lat: float | None = Field(None, ge=-11, le=6)
    lon: float | None = Field(None, ge=95, le=141)

    _phone = field_validator("phone")(require_phone)


@router.get("/users")
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_admin_dep)],
    role: str | None = None,
):
    """Daftar semua user. Optional filter by role."""
    # NULLS LAST + id: di PostgreSQL NULL terurut PALING ATAS pada DESC → baris lama tanpa created_at menutupi
    # pengguna baru dalam batas 200 (audit: pendaftar baru tak terlihat admin)
    query = select(User).order_by(User.created_at.desc().nulls_last(), User.id.desc())
    if role:
        query = query.where(User.role == role)
    result = await db.execute(query.limit(200))
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "phone": u.phone,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role.value if hasattr(u.role, 'value') else str(u.role),
            "is_active": u.is_active,
            "kecamatan": u.kecamatan,
            "kabupaten": u.kabupaten,
            "xp_total": u.xp_total,
            "incentive_tier": u.incentive_tier.value if hasattr(u.incentive_tier, 'value') else str(u.incentive_tier),
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.post("/users", status_code=201)
async def create_user(
    req: AdminCreateUserRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(_admin_dep)],
):
    """Admin membuat user baru secara langsung (semua role, langsung aktif atau nonaktif)."""
    role_val = req.role.lower()
    try:
        role_enum = UserRole(role_val)
    except ValueError:
        raise HTTPException(400, f"Role tidak valid. Pilihan: {', '.join(r.value for r in UserRole)}")

    conds = [User.phone == req.phone]
    if req.username:
        conds.append(User.username == req.username)
    if req.email:
        conds.append(User.email == req.email)

    existing = await db.execute(select(User).where(or_(*conds)))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Nomor telepon, username, atau email sudah terdaftar")

    new_user = User(
        username=req.username,
        email=req.email,
        phone=req.phone,
        password_hash=await run_cpu(hash_password, req.password),
        full_name=req.full_name,
        role=role_enum,
        is_active=req.is_active,
        kecamatan=req.kecamatan,
        kabupaten=req.kabupaten or "Sleman",
        lat=req.lat,
        lon=req.lon,
        xp_total=0,
        incentive_tier=IncentiveTier.PEMULA,
    )
    db.add(new_user)
    await db.flush()
    return {
        "id": new_user.id,
        "phone": new_user.phone,
        "username": new_user.username,
        "full_name": new_user.full_name,
        "role": new_user.role.value if hasattr(new_user.role, 'value') else str(new_user.role),
        "is_active": new_user.is_active,
        "kecamatan": new_user.kecamatan,
        "message": f"User {new_user.full_name} berhasil dibuat",
    }


@router.post("/users/{user_id}/activate")
async def activate_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(_admin_dep)],
):
    """Aktifkan user (terutama untuk pabrik yang butuh approval)."""
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(404, "User tidak ditemukan")
    target.is_active = True
    return {"message": f"User {target.full_name} berhasil diaktifkan", "is_active": True}


@router.post("/users/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(_admin_dep)],
):
    """Toggle status aktif/nonaktif user."""
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(404, "User tidak ditemukan")
    if target.id == admin.id:
        raise HTTPException(400, "Tidak dapat menonaktifkan akun sendiri")
    target.is_active = not target.is_active
    status_str = "diaktifkan" if target.is_active else "dinonaktifkan"
    return {"message": f"User {target.full_name} berhasil {status_str}", "is_active": target.is_active}


@router.get("/stats")
async def system_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(_admin_dep)],
):
    """Statistik keseluruhan sistem termasuk multi-biomassa, lelang, dan logistik sirkular."""
    users_count = await db.execute(select(func.count(User.id)))
    harvests_count = await db.execute(select(func.count(Harvest.id)))
    total_biomass_query = await db.execute(select(func.sum(Harvest.quantity_kg)))
    routes_count = await db.execute(select(func.count(Route.id)))
    mills_count = await db.execute(select(func.count(Mill.id)))

    # Users by role
    role_counts = await db.execute(
        select(User.role, func.count(User.id)).group_by(User.role)
    )

    # Circular & auction stats (graceful fallback if tables are empty)
    total_auctions = 0
    total_bids = 0
    total_weighbridge = 0
    total_redemptions = 0
    try:
        from ..models.trade import AuctionRoom, Bid
        from ..models.circular import WeighbridgeTicket, BiocharRedemption
        auc_res = await db.execute(select(func.count(AuctionRoom.id)))
        total_auctions = auc_res.scalar() or 0
        bid_res = await db.execute(select(func.count(Bid.id)))
        total_bids = bid_res.scalar() or 0
        wb_res = await db.execute(select(func.count(WeighbridgeTicket.id)))
        total_weighbridge = wb_res.scalar() or 0
        red_res = await db.execute(select(func.count(BiocharRedemption.id)))
        total_redemptions = red_res.scalar() or 0
    except Exception:
        pass

    return {
        "total_users": users_count.scalar() or 0,
        "total_harvests": harvests_count.scalar() or 0,
        "total_biomass_kg": float(total_biomass_query.scalar() or 0.0),
        "total_routes": routes_count.scalar() or 0,
        "total_mills": mills_count.scalar() or 0,
        "total_auctions": total_auctions,
        "total_bids": total_bids,
        "total_weighbridge_tickets": total_weighbridge,
        "total_biochar_redemptions": total_redemptions,
        "users_by_role": {
            r[0].value if hasattr(r[0], 'value') else r[0]: r[1]
            for r in role_counts.all()
        },
    }


@router.post("/seed-demo-data")
async def seed_demo_data(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(_admin_dep)],
    force_reset: bool = False,
):
    """Seed data demo lengkap (users, mills, harvests, routes, conversions) via seed.py — hanya DEMO_MODE."""
    from ..config import settings
    if not settings.DEMO_MODE:
        raise HTTPException(404, "Not Found")
    from ..seed import seed_demo_data as run_seed
    result = await run_seed(db, force_reset=force_reset)
    return result


@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(_admin_dep)],
):
    """Reset password oleh admin (F6) — untuk petani/pengepul yang lupa password di lapangan.

    Password sementara acak (10 karakter, tanpa huruf yang mirip seperti O/0, l/1) dikembalikan SEKALI ke admin
    untuk disampaikan langsung ke pemilik akun; server hanya menyimpan hash-nya.
    """
    import secrets

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User tidak ditemukan")
    if user.id == admin.id:
        raise HTTPException(400, "Gunakan menu ganti password untuk akun Anda sendiri.")
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"
    temp = "".join(secrets.choice(alphabet) for _ in range(10))
    user.password_hash = await run_cpu(hash_password, temp)
    user.must_change_password = True                  # pemilik akun wajib ganti saat masuk berikutnya
    user.token_version = int(user.token_version or 0) + 1   # sesi lama (mis. HP dicuri) langsung tidak berlaku
    await db.commit()
    return {"user_id": user.id, "full_name": user.full_name, "username": user.username, "phone": user.phone,
            "temporary_password": temp,
            "note": "Sampaikan langsung ke pemilik akun (jangan lewat grup chat). Minta segera diganti setelah masuk."}
