"""Router: Admin (⚙️) — Manajemen users, data seed, system overview."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_role
from ..models.user import User, UserRole
from ..models.harvest import Harvest
from ..models.route import Route
from ..models.harvest import Mill

router = APIRouter()

_admin_dep = require_role(UserRole.ADMIN)


@router.get("/users")
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_admin_dep)],
    role: str | None = None,
):
    """Daftar semua user. Optional filter by role."""
    query = select(User).order_by(User.created_at.desc())
    if role:
        query = query.where(User.role == role)
    result = await db.execute(query.limit(100))
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "phone": u.phone,
            "full_name": u.full_name,
            "role": u.role.value if hasattr(u.role, 'value') else u.role,
            "is_active": u.is_active,
            "kecamatan": u.kecamatan,
            "xp_total": u.xp_total,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


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
    return {"message": f"User {target.full_name} berhasil diaktifkan"}


@router.get("/stats")
async def system_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(_admin_dep)],
):
    """Statistik keseluruhan sistem."""
    users_count = await db.execute(select(func.count(User.id)))
    harvests_count = await db.execute(select(func.count(Harvest.id)))
    routes_count = await db.execute(select(func.count(Route.id)))
    mills_count = await db.execute(select(func.count(Mill.id)))

    # Users by role
    role_counts = await db.execute(
        select(User.role, func.count(User.id)).group_by(User.role)
    )

    return {
        "total_users": users_count.scalar() or 0,
        "total_harvests": harvests_count.scalar() or 0,
        "total_routes": routes_count.scalar() or 0,
        "total_mills": mills_count.scalar() or 0,
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
    """Seed data demo lengkap (users, mills, harvests, routes, conversions) via seed.py."""
    from ..seed import seed_demo_data as run_seed
    result = await run_seed(db, force_reset=force_reset)
    return result
