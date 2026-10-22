"""Bukti bayar pengepul → petani (F8).

- Rupiah dihitung dengan `Decimal` dan disimpan NUMERIC(14,0) (Rupiah bulat, pembulatan setengah-ke-atas).
  Nilai dasar = `harvests.total_price` (hasil verifikasi pengepul: harga basis kering / kontrak lelang).
- PPh 22 opsional lewat parameter `pajak.pph22_farmer_pct` (default 0 — pemotongan hanya berlaku bila pembeli
  termasuk pemungut yang ditetapkan; konsultasikan dengan konsultan pajak sebelum mengisi).
- Satu harvest = satu pembayaran (UNIQUE). Idempoten untuk antrean offline lewat `client_event_id`.
- Nomor kuitansi: `BYR-<pengepul>-<petani>-<YYMM>-<urut 5 digit>` memakai urutan atomik yang sama dengan resi TRX
  (pasangan pengirim→penerima terbalik, jadi urutannya terpisah dari resi serah-terima barang).
"""

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.compliance import FarmerDownPayment, FarmerPayment
from ..models.harvest import Harvest, HarvestStatus
from ..models.user import User
from ..params import P
from .trx_code import next_seq, party_code, yymm
from .locks import lock_row

PAID_STATES = {HarvestStatus.VERIFIED.value, HarvestStatus.COLLECTED.value, HarvestStatus.DELIVERED.value,
               HarvestStatus.CONVERTED.value}
METHODS = ("tunai", "transfer", "qris", "ewallet")


def rupiah(x) -> Decimal:
    return Decimal(str(x or 0)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _v(e):
    return e.value if hasattr(e, "value") else e


def payment_dict(p: FarmerPayment) -> dict:
    return {"id": p.id, "harvest_id": p.harvest_id, "farmer_id": p.farmer_id, "collector_id": p.collector_id,
            "gross_rp": int(p.gross_rp), "tax_rp": int(p.tax_rp), "dp_rp": int(p.dp_rp or 0), "net_rp": int(p.net_rp),
            "tax_basis": p.tax_basis,
            "method": p.method, "reference": p.reference, "receipt_code": p.receipt_code,
            "evidence_photo_url": p.evidence_photo_url,
            "paid_at": p.paid_at.isoformat() if p.paid_at else None}


async def pay_farmer(db: AsyncSession, collector: User, harvest_id: int, method: str, reference: str | None,
                     evidence_photo_url: str | None, client_event_id: str | None) -> dict:
    if method not in METHODS:
        raise HTTPException(422, f"Metode bayar harus salah satu: {', '.join(METHODS)}")
    if method != "tunai" and not (reference or "").strip():
        raise HTTPException(422, "Isi nomor referensi transfer/QRIS sebagai bukti bayar.")
    if client_event_id:
        prev = (await db.execute(select(FarmerPayment).where(FarmerPayment.client_event_id == client_event_id))).scalar_one_or_none()
        if prev:
            if prev.collector_id != collector.id:
                raise HTTPException(409, "client_event_id sudah dipakai.")
            return {**payment_dict(prev), "replayed": True}

    # DP & pelunasan lot yang sama diserialkan lewat kunci baris harvest (PG & SQLite): tanpa ini DP yang belum
    # ter-commit tidak terlihat → petani menerima DP + pelunasan penuh (audit fase 5)
    await lock_row(db, Harvest, harvest_id)
    h = (await db.execute(select(Harvest).where(Harvest.id == harvest_id))).scalar_one_or_none()
    if h is None:
        raise HTTPException(404, "Harvest tidak ditemukan")
    if h.collector_id != collector.id:
        raise HTTPException(403, "Hanya pengepul yang menimbang lot ini yang dapat mencatat pembayarannya.")
    if _v(h.status) not in PAID_STATES or h.total_price is None:
        raise HTTPException(409, "Lot belum diverifikasi/ditimbang — belum ada nilai yang harus dibayar.")
    existing = (await db.execute(select(FarmerPayment).where(FarmerPayment.harvest_id == h.id))).scalar_one_or_none()
    if existing:
        raise HTTPException(409, f"Lot ini sudah dibayar (kuitansi {existing.receipt_code}).")

    farmer = await db.get(User, h.farmer_id)
    gross = rupiah(h.total_price)
    pct = Decimal(str(P("pajak.pph22_farmer_pct") or 0))
    tax = (gross * pct / Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP) if pct > 0 else Decimal(0)
    # Uang muka aktif dipotong; bila DP > nilai timbangan, sisa dicatat sebagai kewajiban petani mengembalikan
    dp_row = (await db.execute(select(FarmerDownPayment).where(FarmerDownPayment.harvest_id == h.id,
                                                               FarmerDownPayment.status == "aktif")
                               .with_for_update())).scalar_one_or_none()
    dp_total = Decimal(dp_row.amount_rp) if dp_row else Decimal(0)
    dp_applied = min(dp_total, gross - tax)
    dp_excess = dp_total - dp_applied
    s, r, period = party_code(collector), party_code(farmer), yymm()
    code = f"BYR-{s}-{r}-{period}-{await next_seq(db, s, r, period):05d}"
    if dp_row is not None:
        dp_row.status = "dipotong" if dp_excess == 0 else "wajib_dikembalikan"
        dp_row.status_note = (f"Dipotong pada kuitansi {code}" if dp_excess == 0 else
                              f"Dipotong Rp{int(dp_applied):,} pada {code}; kelebihan DP Rp{int(dp_excess):,} wajib dikembalikan petani")
    pay = FarmerPayment(harvest_id=h.id, farmer_id=h.farmer_id, collector_id=collector.id, gross_rp=gross, tax_rp=tax,
                        dp_rp=dp_applied, net_rp=gross - tax - dp_applied,
                        tax_basis=f"PPh 22 {pct}%" if pct > 0 else None, method=method,
                        reference=(reference or "").strip() or None, receipt_code=code,
                        evidence_photo_url=evidence_photo_url, client_event_id=client_event_id,
                        paid_at=datetime.now(timezone.utc))
    db.add(pay)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Pembayaran untuk lot ini baru saja tercatat (kirim ganda).")
    out = payment_dict(pay)
    await db.commit()
    return {**out, "replayed": False, "farmer_name": farmer.full_name if farmer else None,
            "dp_excess_rp": int(dp_excess)}


def dp_dict(d: FarmerDownPayment) -> dict:
    return {"id": d.id, "harvest_id": d.harvest_id, "farmer_id": d.farmer_id, "collector_id": d.collector_id,
            "amount_rp": int(d.amount_rp), "method": d.method, "reference": d.reference, "receipt_code": d.receipt_code,
            "status": d.status, "status_note": d.status_note, "paid_at": d.paid_at.isoformat() if d.paid_at else None}


DP_STATES = {HarvestStatus.REPORTED.value, HarvestStatus.VERIFIED.value}


async def pay_down_payment(db: AsyncSession, collector: User, harvest_id: int, amount: float, method: str,
                           reference: str | None, client_event_id: str | None) -> dict:
    """Catat uang muka ke petani untuk lot yang sudah diikat pengepul ini (lelang diterima / sudah ditimbang)."""
    if method not in METHODS:
        raise HTTPException(422, f"Metode bayar harus salah satu: {', '.join(METHODS)}")
    if method != "tunai" and not (reference or "").strip():
        raise HTTPException(422, "Isi nomor referensi transfer/QRIS sebagai bukti DP.")
    if client_event_id:
        prev = (await db.execute(select(FarmerDownPayment).where(FarmerDownPayment.client_event_id == client_event_id))).scalar_one_or_none()
        if prev:
            if prev.collector_id != collector.id:
                raise HTTPException(409, "client_event_id sudah dipakai.")
            return {**dp_dict(prev), "replayed": True}
    await lock_row(db, Harvest, harvest_id)
    h = (await db.execute(select(Harvest).where(Harvest.id == harvest_id).with_for_update())).scalar_one_or_none()
    if h is None or h.collector_id != collector.id:
        raise HTTPException(404, "Lot tidak ditemukan pada pembelian Anda (DP hanya untuk lot yang sudah Anda ikat).")
    if _v(h.status) not in DP_STATES:
        raise HTTPException(409, "DP hanya untuk lot yang belum diangkut (dilaporkan/ditimbang).")
    if (await db.execute(select(FarmerPayment.id).where(FarmerPayment.harvest_id == h.id))).first():
        raise HTTPException(409, "Lot ini sudah dilunasi.")
    if (await db.execute(select(FarmerDownPayment.id).where(FarmerDownPayment.harvest_id == h.id))).first():
        raise HTTPException(409, "Lot ini sudah memiliki DP.")
    est = (h.agreed_price_per_kg or P("harga_mutu.base_price_per_kg")) * (h.verified_kg or h.quantity_kg)
    cap = est * P("pasar.dp_max_pct") / 100
    if amount > cap + 0.5:
        raise HTTPException(422, f"DP maksimal {P('pasar.dp_max_pct'):g}% dari perkiraan nilai lot (≈ Rp{cap:,.0f}).")
    farmer = await db.get(User, h.farmer_id)
    s, r, period = party_code(collector), party_code(farmer), yymm()
    code = f"DP-{s}-{r}-{period}-{await next_seq(db, s, r, period):05d}"
    d = FarmerDownPayment(harvest_id=h.id, farmer_id=h.farmer_id, collector_id=collector.id, amount_rp=rupiah(amount),
                          method=method, reference=(reference or "").strip() or None, receipt_code=code,
                          client_event_id=client_event_id, paid_at=datetime.now(timezone.utc))
    db.add(d)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "DP untuk lot ini baru saja tercatat (kirim ganda).")
    out = dp_dict(d)
    await db.commit()
    return {**out, "replayed": False, "farmer_name": farmer.full_name if farmer else None}


async def settle_dp_on_cancel(db: AsyncSession, harvest_id: int, outcome: str, note: str) -> dict | None:
    """Pembatalan: 'hangus_untuk_petani' (pengepul batal sepihak) atau 'wajib_dikembalikan' (stok tidak ada)."""
    d = (await db.execute(select(FarmerDownPayment).where(FarmerDownPayment.harvest_id == harvest_id,
                                                          FarmerDownPayment.status == "aktif")
                          .with_for_update())).scalar_one_or_none()
    if d is None:
        return None
    d.status, d.status_note = outcome, note
    await db.flush()
    return dp_dict(d)


async def farmer_overview(db: AsyncSession, farmer: User) -> dict:
    """Tiga keranjang untuk petani: dibayar · menunggu bayar (dengan status terlambat) · belum ditimbang."""
    now = datetime.now(timezone.utc)
    due = int(P("pasar.farmer_payment_due_days") or 0)
    pays = (await db.execute(select(FarmerPayment).where(FarmerPayment.farmer_id == farmer.id))).scalars().all()
    dps = {d.harvest_id: d for d in (await db.execute(select(FarmerDownPayment).where(
        FarmerDownPayment.farmer_id == farmer.id))).scalars().all()}
    paid_ids = {p.harvest_id for p in pays}
    rows = (await db.execute(
        select(Harvest, User.full_name).outerjoin(User, User.id == Harvest.collector_id)
        .where(Harvest.farmer_id == farmer.id, Harvest.status != HarvestStatus.REJECTED)
        .order_by(Harvest.id.desc()).limit(300))).all()
    pct = Decimal(str(P("pajak.pph22_farmer_pct") or 0))
    waiting, unweighed = [], []
    for h, collector_name in rows:
        if h.id in paid_ids:
            continue
        if _v(h.status) in PAID_STATES and h.total_price is not None:
            gross = rupiah(h.total_price)
            tax = (gross * pct / Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP) if pct > 0 else Decimal(0)
            ver = h.verified_at if h.verified_at is None or h.verified_at.tzinfo else h.verified_at.replace(tzinfo=timezone.utc)
            days = (now - ver).days if ver else None
            dp = dps.get(h.id)
            dp_amt = Decimal(dp.amount_rp) if dp is not None and dp.status == "aktif" else Decimal(0)
            waiting.append({"harvest_id": h.id, "collector_name": collector_name, "verified_kg": h.verified_kg,
                            "grade": _v(h.grade) if h.grade else None, "gross_rp": int(gross),
                            "dp_rp": int(dp_amt), "net_rp": int(max(Decimal(0), gross - tax - dp_amt)),
                            "verified_at": ver.isoformat() if ver else None, "days_waiting": days,
                            "late": days is not None and days > due})
        elif _v(h.status) == HarvestStatus.REPORTED.value:
            unweighed.append({"harvest_id": h.id, "quantity_kg": h.quantity_kg, "collector_name": collector_name,
                              "reported_at": h.reported_at.isoformat() if h.reported_at else None})
    return {
        "down_payments": [dp_dict(d) for d in sorted(dps.values(), key=lambda x: -x.id)][:50],
        "due_days": due,
        "paid": {"count": len(pays), "net_rp": int(sum(p.net_rp for p in pays)), "tax_rp": int(sum(p.tax_rp for p in pays)),
                 "last_paid_at": max((p.paid_at for p in pays), default=None)},
        "waiting": {"count": len(waiting), "net_rp": sum(w["net_rp"] for w in waiting),
                    "late_count": sum(1 for w in waiting if w["late"]), "items": waiting[:50]},
        "unweighed": {"count": len(unweighed), "quantity_kg": round(sum(u["quantity_kg"] for u in unweighed), 1),
                      "items": unweighed[:50]},
        "flow": ["Lapor stok", "Ditimbang & diuji pengepul (harga final)", "Dibayar + kuitansi BYR"],
    }


async def unpaid_for_collector(db: AsyncSession, collector: User, limit: int = 100) -> list[dict]:
    paid = select(FarmerPayment.harvest_id)
    rows = (await db.execute(
        select(Harvest, User.full_name).join(User, User.id == Harvest.farmer_id)
        .where(Harvest.collector_id == collector.id, Harvest.total_price.is_not(None),
               Harvest.status.in_([HarvestStatus(s) for s in PAID_STATES]), Harvest.id.not_in(paid))
        .order_by(Harvest.verified_at.desc()).limit(limit))).all()
    return [{"harvest_id": h.id, "farmer_id": h.farmer_id, "farmer_name": name, "verified_kg": h.verified_kg,
             "grade": _v(h.grade) if h.grade else None, "amount_rp": int(rupiah(h.total_price)),
             "verified_at": h.verified_at.isoformat() if h.verified_at else None} for h, name in rows]
