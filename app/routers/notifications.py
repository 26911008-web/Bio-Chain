"""Router API untuk Notifikasi Perubahan Transaksi Biomassa Lintas Persona."""

from typing import Annotated
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user
from ..models.user import User
from ..services.notifications import (
    get_persona_notifications,
    mark_notification_read,
    mark_all_notifications_read,
)

router = APIRouter()


@router.get("/")
async def list_notifications(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_group: str | None = Query(None, description="PENDING_ACTION | IN_PROGRESS | COMPLETED | ALERT_DISCREPANCY"),
    limit: int = Query(60, ge=1, le=200),
):
    """Mengambil daftar notifikasi yang relevan dengan persona pengguna, dikelompokkan berdasarkan status."""
    return await get_persona_notifications(db, user, status_group=status_group, limit=limit)


@router.get("/summary")
async def notifications_summary(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Mengambil ringkasan jumlah notifikasi belum dibaca dan total per grup status."""
    data = await get_persona_notifications(db, user, limit=1)
    return {
        "unread_count": data["unread_count"],
        "total_count": data["total_count"],
        "counts_by_group": data["counts_by_group"],
        "group_meta": data["group_meta"],
    }


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Menandai satu notifikasi telah dibaca."""
    ok = await mark_notification_read(db, notification_id, user)
    if not ok:
        raise HTTPException(status_code=404, detail="Notifikasi tidak ditemukan")
    return {"status": "ok", "id": notification_id, "is_read": True}


@router.post("/read-all")
async def mark_all_read(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Menandai semua notifikasi persona ini telah dibaca."""
    updated = await mark_all_notifications_read(db, user)
    return {"status": "ok", "marked_read_count": updated}
