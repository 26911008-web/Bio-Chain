"""Service: state machine harvest, chain-of-custody, mass balance, dan alokasi biochar ke petani.

Prinsip:
- Setiap perubahan status adalah compare-and-swap (`UPDATE ... WHERE status IN (asal)`); bila baris
  sudah diubah request lain, rowcount = 0 → `TransitionConflict` (HTTP 409). Tidak ada lost update,
  baik di SQLite (writer tunggal) maupun PostgreSQL READ COMMITTED (WHERE dievaluasi ulang setelah lock).
- Hak transisi dicek per role di sini juga (defense in depth, selain `require_role` di router).
- Semua tulis terjadi di transaksi request (`get_db`): exception di tengah alokasi → rollback penuh.
- `client_event_id` membuat setiap aksi idempoten untuk antrean offline di perangkat.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..params import P
from ..models.conversion import Conversion
from ..models.harvest import Harvest, HarvestStatus
from ..models.ledger import BiocharLedgerEntry, ConversionInput, CustodyEvent, CustodyStage
from ..models.user import User, UserRole
from .trx_code import new_verification_code

S, R = HarvestStatus, UserRole

# (asal, tujuan) → role yang berhak. Admin sengaja TIDAK ada: pemisahan tugas, admin tidak menyentuh timbangan.
TRANSITIONS: dict[tuple[HarvestStatus, HarvestStatus], set[UserRole]] = {
    (S.REPORTED, S.VERIFIED): {R.PENGEPUL},
    (S.REPORTED, S.REJECTED): {R.PENGEPUL},
    (S.VERIFIED, S.COLLECTED): {R.DRIVER},
    (S.COLLECTED, S.DELIVERED): {R.PABRIK},
    (S.COLLECTED, S.REJECTED): {R.PABRIK},
    (S.DELIVERED, S.CONVERTED): {R.PABRIK},
    # Jalur Delivery Request: pengepul mengantar sendiri (tanpa supir pabrik) → QC pabrik langsung
    (S.VERIFIED, S.DELIVERED): {R.PABRIK},
    (S.VERIFIED, S.REJECTED): {R.PABRIK},
}


# Tahap yang merupakan perpindahan fisik barang antar pihak → diberi resi serah-terima
HANDOVER_STAGES = {CustodyStage.COLLECTOR_WEIGH, CustodyStage.DRIVER_PICKUP, CustodyStage.FACTORY_RECEIVE}


async def handover_sender(db: AsyncSession, harvest_id: int, stage: CustodyStage) -> User | None:
    """Pihak yang memegang barang sebelum serah-terima ini (dari jejak custody, bukan dari input klien)."""
    h = (await db.execute(select(Harvest.farmer_id, Harvest.collector_id).where(Harvest.id == harvest_id))).one_or_none()
    if h is None:
        return None
    sender_id = h.farmer_id if stage == CustodyStage.COLLECTOR_WEIGH else h.collector_id
    if stage == CustodyStage.FACTORY_RECEIVE:
        driver = (await db.execute(
            select(CustodyEvent.actor_id).where(CustodyEvent.harvest_id == harvest_id,
                                                CustodyEvent.stage == CustodyStage.DRIVER_PICKUP.value)
            .order_by(CustodyEvent.id.desc()).limit(1))).scalar_one_or_none()
        sender_id = driver or h.collector_id
    if sender_id is None:
        return None
    return (await db.execute(select(User).where(User.id == sender_id))).scalar_one_or_none()


class TransitionConflict(Exception):
    """Status harvest sudah berubah (race / aksi ganda) atau transisi tidak sah."""


class CustodyForbidden(Exception):
    """Role tidak berhak melakukan transisi ini."""


def _val(e) -> str:
    return e.value if hasattr(e, "value") else str(e)


def trusted_device_time(dt: datetime | None) -> tuple[datetime, str | None]:
    """Waktu kejadian untuk laporan: jam perangkat bila masuk akal, selain itu jam server + catatan.

    Antrean offline wajar tertunda berjam-jam (sah), tetapi HP murah sering salah jam/tanggal. Di luar
    jendela [−CLIENT_CLOCK_MAX_PAST_HOURS, +CLIENT_CLOCK_MAX_FUTURE_MINUTES] jam perangkat tidak dipakai
    untuk laporan bulanan (event custody tetap menyimpan keduanya: device_time & server_time)."""
    from ..config import settings
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    if dt is None:
        return now, None
    dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    if dt > now + timedelta(minutes=settings.CLIENT_CLOCK_MAX_FUTURE_MINUTES):
        return now, f"jam perangkat {dt.isoformat()} di masa depan — dipakai jam server"
    if dt < now - timedelta(hours=settings.CLIENT_CLOCK_MAX_PAST_HOURS):
        return now, f"jam perangkat {dt.isoformat()} > {settings.CLIENT_CLOCK_MAX_PAST_HOURS:g} jam lalu — dipakai jam server"
    return dt, None


async def find_replay(db: AsyncSession, client_event_id: str | None) -> CustodyEvent | None:
    if not client_event_id:
        return None
    return (await db.execute(
        select(CustodyEvent).where(CustodyEvent.client_event_id == client_event_id)
    )).scalar_one_or_none()


async def transition(
    db: AsyncSession, harvest_id: int, from_status: HarvestStatus, to_status: HarvestStatus,
    actor: User, stage: CustodyStage, *, weight_kg: float | None = None,
    client_event_id: str | None = None, client_recorded_at: datetime | None = None,
    lat: float | None = None, lon: float | None = None, note: str | None = None,
    evidence_photo_url: str | None = None, **fields,
) -> CustodyEvent:
    """Pindahkan status secara atomik dan catat event custody. Idempoten terhadap client_event_id.
    Serah-terima fisik (HANDOVER_STAGES) mendapat resi TRX-[PENGIRIM]-[PENERIMA]-[YYMM]-[SEQ]."""
    replay = await find_replay(db, client_event_id)
    if replay is not None:
        if replay.harvest_id != harvest_id or replay.to_status != _val(to_status):
            raise TransitionConflict("client_event_id sudah dipakai untuk aksi lain.")
        return replay

    allowed = TRANSITIONS.get((from_status, to_status))
    if allowed is None:
        raise TransitionConflict(f"Transisi {_val(from_status)} → {_val(to_status)} tidak sah.")
    if UserRole(_val(actor.role)) not in allowed:
        raise CustodyForbidden(f"Role {_val(actor.role)} tidak berhak: {_val(from_status)} → {_val(to_status)}.")

    if UserRole(_val(actor.role)) == UserRole.PENGEPUL:
        existing_collector = (await db.execute(
            select(Harvest.collector_id).where(Harvest.id == harvest_id)
        )).scalar_one_or_none()
        if existing_collector is not None and existing_collector != actor.id:
            raise CustodyForbidden("Harvest ini hasil lelang pengepul lain.")

    res = await db.execute(
        update(Harvest)
        .where(Harvest.id == harvest_id, Harvest.status == from_status)
        .values(status=to_status, version=Harvest.version + 1, updated_at=datetime.now(timezone.utc), **fields)
        .execution_options(synchronize_session=False)
    )
    if res.rowcount != 1:
        current = (await db.execute(select(Harvest.status).where(Harvest.id == harvest_id))).scalar_one_or_none()
        if current is None:
            raise LookupError("Harvest tidak ditemukan")
        raise TransitionConflict(
            f"Harvest #{harvest_id} berstatus '{_val(current)}', bukan '{_val(from_status)}'. "
            "Kemungkinan sudah diproses pihak lain; muat ulang data.")

    _, clock_note = trusted_device_time(client_recorded_at)
    if clock_note:
        note = "; ".join(x for x in (note, clock_note) if x)
    code, sender_id = None, None
    if stage in HANDOVER_STAGES:
        sender = await handover_sender(db, harvest_id, stage)
        if sender is not None:
            code, sender_id = await new_verification_code(db, sender, actor), sender.id
    event = CustodyEvent(
        harvest_id=harvest_id, stage=_val(stage), from_status=_val(from_status), to_status=_val(to_status),
        weight_kg=weight_kg, actor_id=actor.id, actor_role=_val(actor.role), client_event_id=client_event_id,
        client_recorded_at=client_recorded_at, lat=lat, lon=lon, note=note,
        verification_code=code, sender_id=sender_id, receiver_id=actor.id if code else None,
        evidence_photo_url=evidence_photo_url,
    )
    db.add(event)
    await db.flush()
    return event


async def load_harvest(db: AsyncSession, harvest_id: int) -> Harvest:
    """Baca ulang dari DB (bypass identity map yang mungkin basi setelah UPDATE Core)."""
    h = (await db.execute(
        select(Harvest).where(Harvest.id == harvest_id).execution_options(populate_existing=True)
    )).scalar_one_or_none()
    if h is None:
        raise LookupError("Harvest tidak ditemukan")
    return h


def pct_diff(reference: float, measured: float) -> float:
    """(reference − measured) / reference × 100; positif = susut."""
    if reference <= 0:
        raise ZeroDivisionError("Berat acuan harus > 0 untuk menghitung susut.")
    return (reference - measured) / reference * 100


def shrinkage_fields(reference_kg: float, received_kg: float) -> dict:
    pct = pct_diff(reference_kg, received_kg)
    tol = P("sirkular.shrinkage_tolerance_pct")
    flag = abs(pct) > tol + 1e-9
    note = None
    if flag:
        kind = "susut" if pct > 0 else "KENAIKAN berat (indikasi penambahan air/kontaminan)"
        note = (f"{kind} {abs(pct):.2f}% melebihi toleransi {tol:g}% "
                f"({reference_kg:.2f} → {received_kg:.2f} kg)")
    return {"received_kg": received_kg, "shrinkage_kg": round(reference_kg - received_kg, 3),
            "shrinkage_pct": round(pct, 3), "discrepancy_flag": flag, "discrepancy_note": note}


def allocate_grams(total_g: int, weights: list[float]) -> list[int]:
    """Largest-remainder: bagi total_g proporsional bobot, hasil bulat gram, Σ hasil == total_g persis."""
    wsum = sum(weights)
    if wsum <= 0:
        raise ZeroDivisionError("Total input batch = 0 kg; tidak ada dasar alokasi.")
    raw = [total_g * w / wsum for w in weights]
    out = [int(x) for x in raw]
    for i in sorted(range(len(raw)), key=lambda i: raw[i] - out[i], reverse=True)[: total_g - sum(out)]:
        out[i] += 1
    return out


async def convert_and_allocate(
    db: AsyncSession, actor: User, harvest_ids: list[int], biochar_kg: float, batch_code: str,
    return_share: float, pyrolysis_temp_c: float | None = None,
) -> dict:
    """Satu batch pirolisis: DELIVERED → CONVERTED untuk semua harvest, lalu kreditkan biochar ke
    dompet petani proporsional received_kg. Atomik: gagal di titik mana pun → seluruh request di-rollback."""
    ids = sorted(set(harvest_ids))
    harvests = (await db.execute(
        select(Harvest).where(Harvest.id.in_(ids)).with_for_update().execution_options(populate_existing=True)
    )).scalars().all()
    by_id = {h.id: h for h in harvests}
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise LookupError(f"Harvest tidak ditemukan: {missing}")
    not_ready = [h.id for h in harvests if _val(h.status) != S.DELIVERED.value or h.received_kg is None]
    if not_ready:
        raise TransitionConflict(f"Harvest belum diterima pabrik (status ≠ delivered): {not_ready}")

    inputs = [float(by_id[i].received_kg) for i in ids]
    total_in = sum(inputs)
    allocated_g = round(biochar_kg * return_share * 1000)
    grams = allocate_grams(allocated_g, inputs)          # ZeroDivisionError bila total_in = 0

    conv = Conversion(
        batch_code=batch_code, operator_id=actor.id, feedstock_ton=total_in / 1000,
        feedstock_composition={str(i): kg for i, kg in zip(ids, inputs)},
        pyrolysis_temp_c=pyrolysis_temp_c, biochar_ton=biochar_kg / 1000,
        actual_yield_pct=round(biochar_kg / total_in * 100, 3),
        farmer_return_share=return_share, allocated_biochar_kg=allocated_g / 1000,
    )
    db.add(conv)
    await db.flush()

    allocations = []
    for hid, kg_in, g in zip(ids, inputs, grams):
        h = by_id[hid]
        await transition(db, hid, S.DELIVERED, S.CONVERTED, actor, CustodyStage.CONVERSION, weight_kg=kg_in,
                         note=f"Batch {batch_code}", conversion_id=conv.id)
        db.add(ConversionInput(conversion_id=conv.id, harvest_id=hid, farmer_id=h.farmer_id,
                               input_kg=kg_in, share=kg_in / total_in))
        db.add(BiocharLedgerEntry(farmer_id=h.farmer_id, conversion_id=conv.id, harvest_id=hid,
                                  entry_type="allocation", amount_kg=g / 1000, created_by_id=actor.id,
                                  note=f"{kg_in:g} kg sekam × {biochar_kg:g}/{total_in:g} × {return_share:g}"))
        allocations.append({"harvest_id": hid, "farmer_id": h.farmer_id, "input_kg": kg_in,
                            "share_pct": round(kg_in / total_in * 100, 3), "biochar_kg": g / 1000})
    await db.flush()
    return {
        "conversion_id": conv.id, "batch_code": batch_code, "feedstock_kg": round(total_in, 3),
        "biochar_kg": biochar_kg, "yield_pct": conv.actual_yield_pct, "return_share": return_share,
        "allocated_kg": allocated_g / 1000, "allocations": allocations,
        "computation": {
            "formula": "alokasi_i = round_gram(biochar_kg × return_share × input_i / Σ input), largest remainder",
            "invariant": "Σ alokasi_i == biochar_kg × return_share (tepat sampai gram)",
        },
    }


async def wallet_balance(db: AsyncSession, farmer_id: int) -> float:
    total = (await db.execute(
        select(func.coalesce(func.sum(BiocharLedgerEntry.amount_kg), 0.0))
        .where(BiocharLedgerEntry.farmer_id == farmer_id)
    )).scalar_one()
    return round(float(total), 3)


async def mass_balance(db: AsyncSession, harvest_id: int) -> dict:
    h = await load_harvest(db, harvest_id)
    events = (await db.execute(
        select(CustodyEvent).where(CustodyEvent.harvest_id == harvest_id).order_by(CustodyEvent.id)
    )).scalars().all()
    ledger = (await db.execute(
        select(BiocharLedgerEntry).where(BiocharLedgerEntry.harvest_id == harvest_id)
    )).scalars().all()
    return {
        "harvest_id": h.id, "farmer_id": h.farmer_id, "status": _val(h.status), "version": h.version,
        "weights_kg": {"farmer_estimate": h.quantity_kg, "collector_scale": h.verified_kg,
                       "driver_note": h.picked_up_kg, "factory_scale": h.received_kg},
        "shrinkage": {"kg": h.shrinkage_kg, "pct": h.shrinkage_pct, "tolerance_pct": P("sirkular.shrinkage_tolerance_pct"),
                      "flagged": bool(h.discrepancy_flag), "note": h.discrepancy_note},
        "biochar_allocated_kg": round(sum(e.amount_kg for e in ledger), 3),
        "custody_trail": [
            {"stage": e.stage, "from": e.from_status, "to": e.to_status, "weight_kg": e.weight_kg,
             "actor_id": e.actor_id, "actor_role": e.actor_role, "client_event_id": e.client_event_id,
             "verification_code": e.verification_code, "sender_id": e.sender_id, "receiver_id": e.receiver_id,
             "evidence_photo_url": e.evidence_photo_url,
             "device_time": e.client_recorded_at.isoformat() if e.client_recorded_at else None,
             "server_time": e.created_at.isoformat() if e.created_at else None, "note": e.note}
            for e in events
        ],
    }
