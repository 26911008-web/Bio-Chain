"""Pengambilan biochar petani untuk sawah — sisi keluar Dompet Biochar.

Invarian: saldo tersedia = Σ ledger − Σ permintaan berstatus 'diajukan'. Ledger `redemption` (negatif) hanya
ditulis pabrik saat karung benar-benar diserahkan, sehingga dompet tidak pernah berkurang untuk biochar yang
belum keluar gudang. Serah-terima mengunci baris permintaan (FOR UPDATE) → tidak bisa tercatat dua kali.
"""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import update, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.circular import BiocharRedemption
from ..models.ledger import BiocharLedgerEntry
from ..models.user import User
from .custody import wallet_balance
from .locks import lock_row


def redemption_dict(r: BiocharRedemption, farmer_name: str | None = None) -> dict:
    return {"id": r.id, "farmer_id": r.farmer_id, "farmer_name": farmer_name, "kg": r.kg,
            "land_area_ha": r.land_area_ha, "pickup_point": r.pickup_point, "status": r.status, "note": r.note,
            "estimate": r.estimate, "ledger_entry_id": r.ledger_entry_id, "cancel_reason": r.cancel_reason,
            "handed_over_at": r.handed_over_at.isoformat() if r.handed_over_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None}


async def pending_kg(db: AsyncSession, farmer_id: int) -> float:
    v = (await db.execute(select(func.coalesce(func.sum(BiocharRedemption.kg), 0.0))
                          .where(BiocharRedemption.farmer_id == farmer_id, BiocharRedemption.status == "diajukan"))).scalar()
    return round(float(v or 0), 2)


async def request_redemption(db: AsyncSession, farmer: User, kg: float, land_area_ha: float | None,
                             pickup_point: str, note: str | None) -> dict:
    from ..engines.biochar_field import estimate
    # Kunci baris petani agar dua pengajuan serentak tidak sama-sama lolos cek saldo (PG & SQLite — audit fase 5)
    await lock_row(db, User, farmer.id)
    available = await wallet_balance(db, farmer.id) - await pending_kg(db, farmer.id)
    if kg > available + 1e-6:
        raise HTTPException(409, f"Saldo biochar tersedia {max(0.0, available):.1f} kg (sebagian mungkin sedang diajukan).")
    r = BiocharRedemption(farmer_id=farmer.id, kg=round(kg, 2), land_area_ha=land_area_ha, pickup_point=pickup_point,
                          note=(note or "").strip() or None,
                          estimate=estimate(kg, land_area_ha) if land_area_ha else None)
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return redemption_dict(r)


async def cancel_redemption(db: AsyncSession, actor: User, redemption_id: int, reason: str) -> dict:
    r = (await db.execute(select(BiocharRedemption).where(BiocharRedemption.id == redemption_id)
                          .with_for_update())).scalar_one_or_none()
    if r is None or (actor.role.value == "petani" and r.farmer_id != actor.id):
        raise HTTPException(404, "Permintaan tidak ditemukan")
    if r.status != "diajukan":
        raise HTTPException(409, f"Permintaan sudah {r.status}.")
    res = await db.execute(update(BiocharRedemption).where(BiocharRedemption.id == r.id, BiocharRedemption.status == "diajukan")
                           .values(status="dibatalkan", cancel_reason=reason).execution_options(synchronize_session=False))
    if res.rowcount != 1:                       # baru saja diserahkan petugas → jangan tandai batal (dompet sudah terpotong)
        await db.rollback()
        raise HTTPException(409, "Permintaan ini baru saja diserahkan; tidak bisa dibatalkan.")
    await db.commit()
    await db.refresh(r)
    return redemption_dict(r)


async def list_redemptions(db: AsyncSession, status: str = "diajukan", limit: int = 100) -> list[dict]:
    q = select(BiocharRedemption, User.full_name).join(User, User.id == BiocharRedemption.farmer_id)
    if status != "semua":
        q = q.where(BiocharRedemption.status == status)
    rows = (await db.execute(q.order_by(BiocharRedemption.id.desc()).limit(limit))).all()
    return [redemption_dict(r, name) for r, name in rows]


async def handover(db: AsyncSession, operator: User, redemption_id: int, kg: float | None, note: str | None) -> dict:
    r = (await db.execute(select(BiocharRedemption).where(BiocharRedemption.id == redemption_id)
                          .with_for_update())).scalar_one_or_none()
    if r is None:
        raise HTTPException(404, "Permintaan tidak ditemukan")
    if r.status != "diajukan":
        raise HTTPException(409, f"Permintaan sudah {r.status}.")
    out_kg = round(kg if kg is not None else r.kg, 2)
    if out_kg > r.kg + 1e-6:
        raise HTTPException(422, "Kg diserahkan tidak boleh melebihi yang diajukan.")
    await lock_row(db, User, r.farmer_id)          # serah-terima beberapa permintaan petani yang sama → cek saldo berurutan
    if out_kg > await wallet_balance(db, r.farmer_id) + 1e-6:
        raise HTTPException(409, "Saldo dompet petani tidak cukup (cek penyesuaian ledger).")
    now = datetime.now(timezone.utc)
    # Klaim status dulu (compare-and-swap): atomik juga di SQLite yang mengabaikan FOR UPDATE → dua klik "Serahkan"
    # bersamaan tidak bisa memotong dompet petani dua kali.
    claimed = await db.execute(update(BiocharRedemption).where(BiocharRedemption.id == r.id, BiocharRedemption.status == "diajukan")
                               .values(status="diserahkan", handed_over_by_id=operator.id, handed_over_at=now)
                               .execution_options(synchronize_session=False))
    if claimed.rowcount != 1:
        await db.rollback()
        raise HTTPException(409, "Permintaan ini baru saja diserahkan petugas lain.")
    entry = BiocharLedgerEntry(farmer_id=r.farmer_id, entry_type="redemption", amount_kg=-out_kg,
                               note=f"Diambil untuk sawah ({r.land_area_ha or '-'} ha) · permintaan #{r.id}"
                                    + (f" · {note.strip()}" if note and note.strip() else ""),
                               created_by_id=operator.id)
    db.add(entry)
    await db.flush()
    r.status, r.ledger_entry_id, r.handed_over_by_id, r.handed_over_at = "diserahkan", entry.id, operator.id, now
    if out_kg < r.kg:
        r.note = ((r.note or "") + f" · diserahkan {out_kg} dari {r.kg} kg").strip(" ·")
        r.kg = out_kg
    await db.commit()
    return {**redemption_dict(r), "balance_kg": await wallet_balance(db, r.farmer_id)}
