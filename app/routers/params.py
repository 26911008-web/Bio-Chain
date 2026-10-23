"""Router: ⚙️ Parameter Asumsi — lihat (semua peran), ubah (Pabrik/Admin, alasan wajib), riwayat (audit)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import params
from ..database import get_db
from ..dependencies import get_current_user, require_role
from ..models.params import ParameterChange
from ..models.user import User, UserRole
from ..services import params_store

from ..security.demo_guard import forbid_shared_account_change
router = APIRouter()
_editor = require_role(UserRole.PABRIK, UserRole.ADMIN)


class ParamUpdate(BaseModel):
    value: Any
    reason: str = Field(..., min_length=5, max_length=500, description="Alasan perubahan (wajib, untuk audit)")


class ParamReset(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


VISIBLE_GROUPS: dict[str, set[str]] = {
    UserRole.DRIVER.value: {"logistik"},
    UserRole.PETANI.value: {"harga_mutu", "insentif", "pasar"},
    UserRole.PENGEPUL.value: {"harga_mutu", "pasar", "logistik"},
}


@router.get("")
async def list_params(db: Annotated[AsyncSession, Depends(get_db)],
                      user: Annotated[User, Depends(get_current_user)], group: str | None = None):
    """Asumsi aktif dikelompokkan sesuai izin peran pengguna."""
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    allowed_groups = VISIBLE_GROUPS.get(role)

    if group is not None:
        if allowed_groups is not None and group not in allowed_groups:
            raise HTTPException(403, f"Peran '{role}' tidak berhak mengakses grup parameter '{group}'.")

    await params_store.load(db)
    groups = []
    for gid, glabel in params.GROUPS.items():
        if allowed_groups is not None and gid not in allowed_groups:
            continue
        if group and gid != group:
            continue
        items = [params.describe(d.key) for d in params.DEFS if d.group == gid]
        groups.append({"id": gid, "label": glabel, "params": items,
                       "modified": sum(i["modified"] for i in items)})
    from ..config import settings
    from ..security.demo_guard import shared_demo_usernames
    shared = settings.PUBLIC_DEMO and user.username in shared_demo_usernames()
    return {"can_edit": role in ("pabrik", "admin") and not shared, "groups": groups}


@router.put("/{key}")
async def update_param(key: str, body: ParamUpdate, db: Annotated[AsyncSession, Depends(get_db)],
                       user: Annotated[User, Depends(_editor)]):
    # Parameter berlaku global: di demo publik akun pabrik bersama tidak boleh mengubahnya untuk semua pengunjung
    forbid_shared_account_change(user.username, "Mengubah parameter global")
    try:
        return await params_store.set_value(db, key, body.value, user, body.reason)
    except params.ParamError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/{key}/reset")
async def reset_param(key: str, body: ParamReset, db: Annotated[AsyncSession, Depends(get_db)],
                      user: Annotated[User, Depends(_editor)]):
    # Parameter berlaku global: di demo publik akun pabrik bersama tidak boleh mengubahnya untuk semua pengunjung
    forbid_shared_account_change(user.username, "Mengubah parameter global")
    try:
        return await params_store.reset_value(db, key, user, body.reason)
    except params.ParamError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/history")
async def history(db: Annotated[AsyncSession, Depends(get_db)],
                  user: Annotated[User, Depends(require_role(UserRole.PABRIK, UserRole.ADMIN, UserRole.AUDITOR))],
                  key: str | None = None, limit: int = 100):
    q = select(ParameterChange, User.full_name).join(User, User.id == ParameterChange.changed_by_id)
    if key:
        q = q.where(ParameterChange.key == key)
    rows = (await db.execute(q.order_by(ParameterChange.id.desc()).limit(min(max(limit, 1), 500)))).all()
    return [{"id": c.id, "key": c.key, "label": params.REGISTRY[c.key].label if c.key in params.REGISTRY else c.key,
             "old_value": c.old_value, "new_value": c.new_value, "reset_to_default": c.new_value is None,
             "by": name, "role": c.changed_by_role, "reason": c.reason,
             "at": c.created_at.isoformat() if c.created_at else None} for c, name in rows]
