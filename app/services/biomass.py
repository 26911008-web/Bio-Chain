"""Multi-biomassa (018): master, gudang pengepul + ledger stok berefraksi, Poktan, ledger abu agronomi.

Konkurensi: setiap mutasi stok mengunci baris gudang (SELECT ... FOR UPDATE) sehingga dua HP pengepul yang
mengirim antrean offline bersamaan tidak bisa mengeluarkan stok melebihi saldo. Idempoten via client_event_id.
"""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..engines.refraction import refract
from ..models.biomass import (BiomassParameter, CollectorWarehouse, FarmerGroup, IndustrialAshLedger,
                              WarehouseStockMovement)
from ..models.harvest import Harvest
from ..models.user import User
from ..params import P

METALS = ("as", "hg", "pb", "cd", "cr", "ni")
REQUIRED_METALS = ("pb", "cd", "as")                  # minimal untuk status lulus (CHECK DB); Hg/Cr/Ni dinilai bila diukur
EDITABLE = {"name", "is_active", "moisture_typ_pct", "moisture_min_pct", "moisture_max_pct", "ash_pct_db",
            "volatile_pct_db", "fixed_carbon_pct_db", "hhv_db_mj_kg", "lhv_db_mj_kg", "bulk_density_kg_m3",
            "carbon_pct_db", "hydrogen_pct_db", "nitrogen_pct_db", "sulfur_pct_db", "chlorine_pct_db",
            "sio2_pct_ash", "k2o_pct_ash", "na2o_pct_ash", "cao_pct_ash", "mgo_pct_ash", "fe2o3_pct_ash",
            "al2o3_pct_ash", "p2o5_pct_ash", "moisture_ref_pct", "moisture_reject_pct", "contaminant_tol_pct",
            "base_price_per_kg"}


def _aware(d):
    return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)


def _iso(d):
    return _aware(d).isoformat() if d else None


# ---------------------------------------------------------------- master biomassa
def biomass_dict(b: BiomassParameter) -> dict:
    out = {c.name: getattr(b, c.name) for c in BiomassParameter.__table__.columns}
    out["updated_at"] = _iso(b.updated_at)
    return out


async def list_biomass(db: AsyncSession, active_only: bool = True) -> list[dict]:
    q = select(BiomassParameter).order_by(BiomassParameter.name)
    if active_only:
        q = q.where(BiomassParameter.is_active.is_(True))
    return [biomass_dict(b) for b in (await db.execute(q)).scalars()]


async def get_biomass(db: AsyncSession, code: str | None) -> BiomassParameter:
    b = await db.get(BiomassParameter, code or "sekam_padi")
    if b is None or not b.is_active:
        raise HTTPException(422, f"Komoditas '{code}' tidak dikenal atau nonaktif.")
    return b


async def update_biomass(db: AsyncSession, user: User, code: str, changes: dict, source: str) -> dict:
    b = (await db.execute(select(BiomassParameter).where(BiomassParameter.code == code).with_for_update())).scalar_one_or_none()
    if b is None:
        raise HTTPException(404, "Komoditas tidak ditemukan.")
    bad = set(changes) - EDITABLE
    if bad:
        raise HTTPException(422, f"Kolom tidak boleh diubah: {', '.join(sorted(bad))}")
    for k, v in changes.items():
        setattr(b, k, v)
    if (b.moisture_reject_pct or 0) <= (b.moisture_ref_pct or 0):
        raise HTTPException(422, "Kadar air tolak harus lebih besar dari kadar air acuan.")
    stamp = datetime.now(timezone.utc)
    b.source = f"{b.source}\n[{stamp:%Y-%m-%d}] {user.full_name or user.username}: {source.strip()}"[-4000:]
    b.updated_by_id, b.updated_at = user.id, stamp
    await db.flush()
    return biomass_dict(b)


def base_price_for(b: BiomassParameter) -> float | None:
    """Harga beli dasar Rp/kg. Sekam: parameter lama harga_mutu.base_price_per_kg bila master belum diisi."""
    if b.base_price_per_kg is not None:
        return b.base_price_per_kg
    return P("harga_mutu.base_price_per_kg") if b.code == "sekam_padi" else None


# ---------------------------------------------------------------- gudang pengepul
async def _stock_rows(db: AsyncSession, warehouse_ids: list[int]) -> dict[int, list[dict]]:
    if not warehouse_ids:
        return {}
    rows = (await db.execute(select(WarehouseStockMovement.warehouse_id, WarehouseStockMovement.commodity,
                                    func.sum(WarehouseStockMovement.gross_kg), func.sum(WarehouseStockMovement.payable_kg),
                                    func.max(WarehouseStockMovement.created_at))
                             .where(WarehouseStockMovement.warehouse_id.in_(warehouse_ids))
                             .group_by(WarehouseStockMovement.warehouse_id, WarehouseStockMovement.commodity))).all()
    out: dict[int, list[dict]] = {}
    for wid, com, gross, pay, last in rows:
        out.setdefault(wid, []).append({"commodity": com, "gross_kg": round(gross or 0, 2),
                                        "payable_kg": round(pay or 0, 2), "last_movement_at": _iso(last)})
    return out


def warehouse_dict(w: CollectorWarehouse, stock: list[dict]) -> dict:
    return {"id": w.id, "name": w.name, "lat": w.lat, "lon": w.lon, "capacity_m3": w.capacity_m3,
            "is_covered": w.is_covered, "is_active": w.is_active, "stock": stock}


async def list_warehouses(db: AsyncSession, collector: User) -> list[dict]:
    whs = (await db.execute(select(CollectorWarehouse).where(CollectorWarehouse.collector_id == collector.id)
                            .order_by(CollectorWarehouse.id))).scalars().all()
    stock = await _stock_rows(db, [w.id for w in whs])
    return [warehouse_dict(w, stock.get(w.id, [])) for w in whs]


async def create_warehouse(db: AsyncSession, collector: User, data: dict) -> dict:
    w = CollectorWarehouse(collector_id=collector.id, **data)
    db.add(w)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Nama gudang sudah dipakai.")
    return warehouse_dict(w, [])


def movement_dict(m: WarehouseStockMovement) -> dict:
    return {"id": m.id, "warehouse_id": m.warehouse_id, "commodity": m.commodity, "movement": m.movement,
            "gross_kg": m.gross_kg, "payable_kg": m.payable_kg, "refraction_kg": m.refraction_kg,
            "moisture_pct": m.moisture_pct, "contaminant_pct": m.contaminant_pct, "refraction_basis": m.refraction_basis,
            "harvest_id": m.harvest_id, "delivery_ref": m.delivery_ref, "note": m.note, "created_at": _iso(m.created_at)}


async def add_movement(db: AsyncSession, user: User, warehouse_id: int, d: dict) -> dict:
    if d.get("client_event_id"):
        prev = (await db.execute(select(WarehouseStockMovement)
                                 .where(WarehouseStockMovement.client_event_id == d["client_event_id"]))).scalar_one_or_none()
        if prev is not None:
            return {**movement_dict(prev), "replayed": True}
    w = (await db.execute(select(CollectorWarehouse).where(CollectorWarehouse.id == warehouse_id)
                          .with_for_update())).scalar_one_or_none()          # kunci: mutasi per gudang berurutan
    if w is None or w.collector_id != user.id:
        raise HTTPException(404, "Gudang tidak ditemukan.")
    b = await get_biomass(db, d["commodity"])
    kind, kg = d["movement"], float(d["kg"])
    if kg <= 0:
        raise HTTPException(422, "Berat harus > 0.")
    basis, pay, refr = None, 0.0, 0.0
    if kind == "masuk":
        if d.get("harvest_id"):
            h = await db.get(Harvest, d["harvest_id"])
            if h is None or h.collector_id != user.id:
                raise HTTPException(404, "Lot tidak ditemukan pada pembelian Anda.")
            if (h.commodity or "sekam_padi") != b.code:
                raise HTTPException(422, f"Komoditas lot ({h.commodity}) berbeda dengan {b.code}.")
        r = refract(kg, d.get("moisture_pct"), d.get("contaminant_pct"), b.moisture_ref_pct, b.moisture_reject_pct,
                    b.contaminant_tol_pct, accept_wet=bool(d.get("accept_wet")))
        if not r["accepted"]:
            raise HTTPException(422, r["reason"])
        gross, pay, refr, basis = kg, r["payable_kg"], r["refraction_kg"], r["basis"]
    else:
        have = (await db.execute(select(func.coalesce(func.sum(WarehouseStockMovement.gross_kg), 0.0),
                                        func.coalesce(func.sum(WarehouseStockMovement.payable_kg), 0.0))
                                 .where(WarehouseStockMovement.warehouse_id == w.id,
                                        WarehouseStockMovement.commodity == b.code))).one()
        stock_gross, stock_pay = float(have[0]), float(have[1])
        if kg > stock_gross + 1e-6:
            raise HTTPException(409, f"Stok {b.name} di gudang ini hanya {stock_gross:,.1f} kg.")
        gross = -kg
        pay = -round(kg * (stock_pay / stock_gross), 2) if stock_gross > 0 else 0.0   # proporsional saldo berefraksi
        if kind not in ("keluar", "susut"):
            raise HTTPException(422, "Jenis mutasi tidak dikenal.")
    m = WarehouseStockMovement(warehouse_id=w.id, commodity=b.code, movement=kind, gross_kg=gross,
                               moisture_pct=d.get("moisture_pct"), contaminant_pct=d.get("contaminant_pct"),
                               payable_kg=pay, refraction_kg=refr, refraction_basis=basis, harvest_id=d.get("harvest_id"),
                               delivery_ref=d.get("delivery_ref"), note=d.get("note"),
                               client_event_id=d.get("client_event_id"), created_by_id=user.id)
    db.add(m)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Mutasi ini baru saja tercatat (kirim ganda).")
    if kind != "masuk":
        # Periksa ulang SETELAH tulis, di transaksi yang sama: SQLite (mode cadangan lapangan) mengabaikan FOR UPDATE,
        # jadi dua antrean offline yang tiba bersamaan bisa lolos cek awal. Saldo negatif → batalkan.
        after = (await db.execute(select(func.coalesce(func.sum(WarehouseStockMovement.gross_kg), 0.0))
                                  .where(WarehouseStockMovement.warehouse_id == w.id,
                                         WarehouseStockMovement.commodity == b.code))).scalar()
        if after < -1e-6:
            name = b.name
            await db.rollback()                       # objek kedaluwarsa setelah rollback → pakai nama yang disalin
            raise HTTPException(409, f"Stok {name} tidak cukup (diambil transaksi lain bersamaan). Muat ulang saldo.")
    price = base_price_for(b)
    return {**movement_dict(m), "replayed": False,
            "value_rp": round(pay * price) if kind == "masuk" and price is not None else None}


async def list_movements(db: AsyncSession, user: User, warehouse_id: int) -> list[dict]:
    w = await db.get(CollectorWarehouse, warehouse_id)
    if w is None or w.collector_id != user.id:
        raise HTTPException(404, "Gudang tidak ditemukan.")
    rows = (await db.execute(select(WarehouseStockMovement).where(WarehouseStockMovement.warehouse_id == w.id)
                             .order_by(WarehouseStockMovement.id.desc()).limit(200))).scalars()
    return [movement_dict(m) for m in rows]


# ---------------------------------------------------------------- kelompok tani
def group_dict(g: FarmerGroup) -> dict:
    return {"id": g.id, "name": g.name, "simluhtan_id": g.simluhtan_id, "desa": g.desa, "kecamatan": g.kecamatan,
            "kabupaten": g.kabupaten, "leader_user_id": g.leader_user_id, "leader_name": g.leader_name,
            "member_count": g.member_count}


async def create_group(db: AsyncSession, data: dict) -> dict:
    g = FarmerGroup(**data)
    db.add(g)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Nomor Simluhtan sudah terdaftar.")
    return group_dict(g)


async def list_groups(db: AsyncSession) -> list[dict]:
    return [group_dict(g) for g in (await db.execute(select(FarmerGroup).order_by(FarmerGroup.name))).scalars()]


# ---------------------------------------------------------------- ledger abu
def metal_limits() -> dict:
    return {m: P(f"abu.limit_{m}_ppm") for m in METALS}


def assess_metals(values: dict) -> tuple[str, list[str]]:
    """'lulus' bila Pb, Cd, As terukur dan semua logam terukur ≤ batas; 'gagal' bila ada yang melebihi."""
    lim = metal_limits()
    over = [f"{m.capitalize()} {values[m]:g} > {lim[m]:g} mg/kg" for m in METALS
            if values.get(m) is not None and values[m] > lim[m]]
    if over:
        return "gagal", over
    if any(values.get(m) is None for m in REQUIRED_METALS):
        return "belum_uji", ["Pb, Cd dan As wajib diukur"]
    return "lulus", []


def ash_dict(a: IndustrialAshLedger, groups: dict | None = None) -> dict:
    return {
        "id": a.id, "code": a.code, "ash_type": a.ash_type, "source_commodity": a.source_commodity, "batch_id": a.batch_id,
        "quantity_kg": a.quantity_kg, "metals_ppm": {m: getattr(a, f"{m}_ppm") for m in METALS},
        "lab_name": a.lab_name, "lab_report_no": a.lab_report_no, "lab_report_url": a.lab_report_url,
        "limits_snapshot": a.limits_snapshot, "heavy_metal_status": a.heavy_metal_status,
        "agronomy": {"k2o_pct": a.k2o_pct, "cao_pct": a.cao_pct, "sio2_pct": a.sio2_pct, "ph": a.ph},
        "status": a.status, "farmer_group_id": a.farmer_group_id,
        "farmer_group": (groups or {}).get(a.farmer_group_id), "land_lat": a.land_lat, "land_lon": a.land_lon,
        "land_area_ha": a.land_area_ha, "handover_photo_url": a.handover_photo_url, "handed_over_at": _iso(a.handed_over_at),
        "disposal_note": a.disposal_note, "created_at": _iso(a.created_at),
    }


async def _ash_locked(db: AsyncSession, ash_id: int) -> IndustrialAshLedger:
    a = (await db.execute(select(IndustrialAshLedger).where(IndustrialAshLedger.id == ash_id).with_for_update())
         ).scalar_one_or_none()
    if a is None:
        raise HTTPException(404, "Catatan abu tidak ditemukan.")
    return a


async def create_ash(db: AsyncSession, user: User, d: dict) -> dict:
    if d.get("source_commodity"):
        await get_biomass(db, d["source_commodity"])
    now = datetime.now(timezone.utc)
    prefix = f"ASH-{now:%y%m}-"
    n = (await db.execute(select(func.count(IndustrialAshLedger.id)).where(IndustrialAshLedger.code.like(prefix + "%")))).scalar() or 0
    a = IndustrialAshLedger(code=f"{prefix}{n + 1:03d}", factory_id=user.id, created_by_id=user.id, **d)
    db.add(a)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Kode abu bentrok, coba lagi.")
    return ash_dict(a)


async def record_lab(db: AsyncSession, ash_id: int, d: dict) -> dict:
    a = await _ash_locked(db, ash_id)
    if a.status != "tersedia":
        raise HTTPException(409, "Hasil lab hanya bisa diisi sebelum abu dialokasikan/dibuang.")
    for m in METALS:
        if d.get(f"{m}_ppm") is not None:
            setattr(a, f"{m}_ppm", d[f"{m}_ppm"])
    for k in ("lab_name", "lab_report_no", "lab_report_url", "k2o_pct", "cao_pct", "sio2_pct", "ph"):
        if d.get(k) is not None:
            setattr(a, k, d[k])
    status, notes = assess_metals({m: getattr(a, f"{m}_ppm") for m in METALS})
    if status == "lulus" and not a.lab_report_no:
        raise HTTPException(422, "Nomor laporan lab wajib untuk status lulus.")
    a.heavy_metal_status = status
    a.limits_snapshot = {"limits_mg_kg": metal_limits(), "basis": "Kepmentan 261/KPTS/SR.310/M/4/2019",
                         "notes": notes, "assessed_at": datetime.now(timezone.utc).isoformat()}
    await db.flush()
    return ash_dict(a)


async def _cas(db: AsyncSession, a: IndustrialAshLedger, expect: dict, values: dict) -> None:
    """UPDATE bersyarat (compare-and-swap): atomik di PG maupun SQLite (yang mengabaikan FOR UPDATE). Dua permintaan
    alokasi/serah-terima bersamaan → hanya satu yang mengubah baris; yang kalah mendapat 409."""
    res = await db.execute(update(IndustrialAshLedger)
                           .where(IndustrialAshLedger.id == a.id,
                                  *[getattr(IndustrialAshLedger, k) == v for k, v in expect.items()])
                           .values(**values).execution_options(synchronize_session=False))
    if res.rowcount != 1:
        await db.rollback()
        raise HTTPException(409, "Status abu baru saja diubah pengguna lain — muat ulang daftar.")
    await db.refresh(a)


async def allocate_ash(db: AsyncSession, ash_id: int, group_id: int, land_area_ha: float | None) -> dict:
    a = await _ash_locked(db, ash_id)
    if a.heavy_metal_status != "lulus":
        raise HTTPException(409, "Abu belum/tidak lulus uji logam berat — tidak boleh dialokasikan ke lahan petani.")
    if a.status != "tersedia":
        raise HTTPException(409, f"Abu sudah {a.status}.")
    g = await db.get(FarmerGroup, group_id)
    if g is None:
        raise HTTPException(404, "Kelompok tani tidak ditemukan.")
    await _cas(db, a, {"status": "tersedia", "heavy_metal_status": "lulus"},
               {"status": "dialokasikan", "farmer_group_id": g.id, "land_area_ha": land_area_ha})
    return ash_dict(a, {g.id: g.name})


async def handover_ash(db: AsyncSession, user: User, ash_id: int, d: dict) -> dict:
    a = await _ash_locked(db, ash_id)
    if a.status != "dialokasikan":
        raise HTTPException(409, "Hanya abu yang sudah dialokasikan yang bisa diserahkan.")
    vals = {"status": "diserahkan", "handover_photo_url": d["photo_url"], "land_lat": d["lat"], "land_lon": d["lon"],
            "handed_over_at": datetime.now(timezone.utc), "handed_over_by_id": user.id}
    if d.get("land_area_ha"):
        vals["land_area_ha"] = d["land_area_ha"]
    await _cas(db, a, {"status": "dialokasikan"}, vals)
    g = await db.get(FarmerGroup, a.farmer_group_id)
    return ash_dict(a, {g.id: g.name} if g else None)


async def dispose_ash(db: AsyncSession, ash_id: int, note: str) -> dict:
    a = await _ash_locked(db, ash_id)
    if a.status != "tersedia":
        raise HTTPException(409, f"Abu sudah {a.status}.")
    await _cas(db, a, {"status": "tersedia"}, {"status": "dibuang", "disposal_note": note.strip()})
    return ash_dict(a)


async def list_ash(db: AsyncSession, group_leader: User | None = None) -> list[dict]:
    q = select(IndustrialAshLedger).order_by(IndustrialAshLedger.id.desc()).limit(200)
    if group_leader is not None:
        ids = select(FarmerGroup.id).where(FarmerGroup.leader_user_id == group_leader.id)
        q = q.where(IndustrialAshLedger.farmer_group_id.in_(ids))
    rows = (await db.execute(q)).scalars().all()
    gids = {a.farmer_group_id for a in rows if a.farmer_group_id}
    groups = dict((await db.execute(select(FarmerGroup.id, FarmerGroup.name).where(FarmerGroup.id.in_(gids)))).all()) if gids else {}
    return [ash_dict(a, groups) for a in rows]
