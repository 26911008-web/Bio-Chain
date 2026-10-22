"""F11 — Alur klaim removal karbon: pratinjau → diajukan pabrik (snapshot terkunci) → diputus auditor.

Aturan anti hitung-ganda / over-crediting:
  * satu serah-terima biochar (biochar_redemptions) hanya boleh dikunci di satu klaim aktif (UNIQUE di DB);
  * periode klaim aktif (diajukan/diverifikasi) tidak boleh tumpang-tindih — batas produksi biochar per periode
    (end-use ≤ produksi) hanya berlaku bila periode tidak dipakai dua kali;
  * C-org lab menggantikan parameter F_C; H/C-org di atas `karbon.h_corg_max` → tidak boleh diajukan;
  * snapshot hasil hitung + nilai parameter dibekukan dengan SHA-256 → perubahan setelah diajukan terdeteksi.
"""

import hashlib
import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..engines.green_scorecard import scorecard
from ..models.carbon import CarbonClaim, CarbonClaimItem
from ..models.circular import BiocharRedemption
from ..models.user import User
from ..params import P
from .esg import scorecard_inputs

METHOD = "F11-v1 · Puro 2025 / VM0044 end-use · IPCC 2019 Ap.4 F_perm"
ACTIVE = ("diajukan", "diverifikasi")
STATUS_LABEL = {
    "diajukan": "Menunggu verifikasi auditor",
    "diverifikasi": "Terverifikasi auditor internal — belum diverifikasi VVB / terdaftar SRN-PPI (bukan kredit karbon)",
    "ditolak": "Ditolak auditor — serah-terima dilepas, boleh diajukan ulang",
}


def _aware(d):
    return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)


def digest(snapshot: dict) -> str:
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


async def _free_redemptions(db: AsyncSession, start: datetime, end: datetime) -> list[BiocharRedemption]:
    locked = select(CarbonClaimItem.redemption_id)
    return (await db.execute(select(BiocharRedemption).where(
        BiocharRedemption.status == "diserahkan", BiocharRedemption.handed_over_at >= start,
        BiocharRedemption.handed_over_at < end, BiocharRedemption.id.not_in(locked))
        .order_by(BiocharRedemption.id))).scalars().all()


async def _overlapping(db: AsyncSession, start: datetime, end: datetime) -> CarbonClaim | None:
    return (await db.execute(select(CarbonClaim).where(CarbonClaim.status.in_(ACTIVE), CarbonClaim.period_start < end,
                                                       CarbonClaim.period_end > start).limit(1))).scalar_one_or_none()


async def compute(db: AsyncSession, start: datetime, end: datetime, lab: dict) -> dict:
    """Hitung klaim tanpa menyimpan. Hasil memuat `blocking` (wajib kosong untuk diajukan) & `warnings`."""
    reds = await _free_redemptions(db, start, end)
    end_use = sum(r.kg for r in reds)
    d = await scorecard_inputs(db, start, end)
    sc = scorecard(d["batches"], d["routes"], d["returns"], d["received_kg"], d["biochar_to_farmers_kg"],
                   end_use, fc_override=lab["lab_c_org_pct"] / 100)
    c = sc["carbon_tco2e"]
    h_max = P("karbon.h_corg_max")
    blocking = [msg for msg, bad in (
        ("Tidak ada serah-terima biochar ke lahan yang belum diklaim pada periode ini", not reds),
        (f"H/C-org lab {lab['lab_h_corg_ratio']:g} > batas {h_max:g}: karbon belum stabil, tidak boleh diklaim",
         lab["lab_h_corg_ratio"] > h_max),
        ("Removal bersih ≤ 0 setelah dikurangi emisi proyek & potongan ketidakpastian", c["net"] <= 0),
    ) if bad]
    other = await _overlapping(db, start, end)
    if other is not None:
        blocking.append(f"Periode tumpang-tindih dengan klaim {other.code} ({other.status}) — produksi biochar "
                        "satu periode tidak boleh dipakai dua klaim")
    params_used = {k: P(k) for k in sc["computation_details"]["parameters_used"] + ["karbon.h_corg_max"]}
    snapshot = {
        "method": METHOD, "period_start": start.isoformat(), "period_end": end.isoformat(),
        "lab": {k: lab[k] for k in ("lab_c_org_pct", "lab_h_corg_ratio", "lab_name", "lab_report_no", "lab_report_url")},
        "redemptions": [{"id": r.id, "farmer_id": r.farmer_id, "kg": r.kg,
                         "handed_over_at": _aware(r.handed_over_at).isoformat()} for r in reds],
        "end_use_kg": round(end_use, 3), "carbon_tco2e": c, "data_quality": sc["data_quality"],
        "parameters": params_used,
    }
    return {"snapshot": snapshot, "blocking": blocking, "warnings": c["claim_gaps"], "net_tco2e": c["net"],
            "end_use_kg": round(end_use, 3), "redemption_count": len(reds)}


async def submit(db: AsyncSession, user: User, start: datetime, end: datetime, lab: dict) -> dict:
    res = await compute(db, start, end, lab)
    if res["blocking"]:
        raise HTTPException(422, "Klaim belum bisa diajukan: " + "; ".join(res["blocking"]))
    now = datetime.now(timezone.utc)
    prefix = f"CLM-{now:%y%m}-"
    n = (await db.execute(select(func.count(CarbonClaim.id)).where(CarbonClaim.code.like(prefix + "%")))).scalar() or 0
    snap = res["snapshot"]
    claim = CarbonClaim(code=f"{prefix}{n + 1:03d}", period_start=start, period_end=end, status="diajukan",
                        end_use_kg=res["end_use_kg"], net_removal_tco2e=res["net_tco2e"], snapshot=snap,
                        snapshot_sha256=digest(snap), submitted_by_id=user.id, submitted_at=now, **snap["lab"])
    db.add(claim)
    try:
        await db.flush()
        db.add_all([CarbonClaimItem(claim_id=claim.id, redemption_id=r["id"], kg=r["kg"]) for r in snap["redemptions"]])
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Serah-terima pada periode ini baru saja dikunci klaim lain. Muat ulang lalu coba lagi.")
    return await claim_dict(db, claim)


async def integrity(db: AsyncSession, claim: CarbonClaim) -> dict:
    """Snapshot utuh (hash cocok) & kunci serah-terima di DB sama dengan isi snapshot."""
    hash_ok = digest(claim.snapshot) == claim.snapshot_sha256
    ids_db = sorted((await db.execute(select(CarbonClaimItem.redemption_id)
                                      .where(CarbonClaimItem.claim_id == claim.id))).scalars())
    ids_snap = sorted(r["id"] for r in claim.snapshot.get("redemptions", []))
    items_ok = claim.status == "ditolak" or ids_db == ids_snap
    return {"ok": hash_ok and items_ok, "hash_ok": hash_ok, "items_ok": items_ok}


async def decide(db: AsyncSession, auditor: User, claim_id: int, decision: str, note: str) -> dict:
    claim = (await db.execute(select(CarbonClaim).where(CarbonClaim.id == claim_id).with_for_update())).scalar_one_or_none()
    if claim is None:
        raise HTTPException(404, "Klaim tidak ditemukan.")
    if claim.status != "diajukan":
        raise HTTPException(409, f"Klaim sudah diputus ({claim.status}).")
    if claim.submitted_by_id == auditor.id:
        raise HTTPException(403, "Empat mata: pengaju tidak boleh memverifikasi klaimnya sendiri.")
    chk = await integrity(db, claim)
    if decision == "diverifikasi" and not chk["ok"]:
        raise HTTPException(409, "Integritas snapshot gagal (data berubah setelah diajukan) — klaim hanya bisa ditolak.")
    # compare-and-swap: dua auditor memutus bersamaan → hanya satu yang tercatat (SQLite mengabaikan FOR UPDATE)
    res = await db.execute(update(CarbonClaim).where(CarbonClaim.id == claim.id, CarbonClaim.status == "diajukan")
                           .values(status=decision, verified_by_id=auditor.id, decided_at=datetime.now(timezone.utc),
                                   decision_note=note.strip()).execution_options(synchronize_session=False))
    if res.rowcount != 1:
        await db.rollback()
        raise HTTPException(409, "Klaim baru saja diputus auditor lain.")
    await db.refresh(claim)                # status 'ditolak' sudah tersimpan: RLS DELETE kunci memeriksanya (PG)
    if decision == "ditolak":
        for it in (await db.execute(select(CarbonClaimItem).where(CarbonClaimItem.claim_id == claim.id))).scalars():
            await db.delete(it)
    await db.flush()
    return await claim_dict(db, claim)


async def claim_dict(db: AsyncSession, c: CarbonClaim) -> dict:
    names = {}
    ids = [i for i in (c.submitted_by_id, c.verified_by_id) if i]
    if ids:
        names = dict((await db.execute(select(User.id, User.full_name).where(User.id.in_(ids)))).all())
    carbon = (c.snapshot or {}).get("carbon_tco2e", {})
    return {
        "id": c.id, "code": c.code, "status": c.status, "status_label": STATUS_LABEL[c.status],
        "period_start": _aware(c.period_start).isoformat(), "period_end": _aware(c.period_end).isoformat(),
        "lab_c_org_pct": c.lab_c_org_pct, "lab_h_corg_ratio": c.lab_h_corg_ratio, "lab_name": c.lab_name,
        "lab_report_no": c.lab_report_no, "lab_report_url": c.lab_report_url,
        "end_use_kg": c.end_use_kg, "redemption_count": len((c.snapshot or {}).get("redemptions", [])),
        "net_removal_tco2e": c.net_removal_tco2e, "gross_removal_tco2e": carbon.get("biochar_sequestration"),
        "warnings": carbon.get("claim_gaps", []), "method": (c.snapshot or {}).get("method"),
        "snapshot_sha256": c.snapshot_sha256, "integrity": await integrity(db, c),
        "submitted_by": names.get(c.submitted_by_id), "submitted_at": _aware(c.submitted_at).isoformat(),
        "verified_by": names.get(c.verified_by_id), "decided_at": _aware(c.decided_at).isoformat() if c.decided_at else None,
        "decision_note": c.decision_note,
    }


async def list_claims(db: AsyncSession, status: str | None = None) -> list[dict]:
    q = select(CarbonClaim).order_by(CarbonClaim.id.desc()).limit(100)
    if status:
        q = q.where(CarbonClaim.status == status)
    return [await claim_dict(db, c) for c in (await db.execute(q)).scalars()]


async def verified_summary(db: AsyncSession, start: datetime, end: datetime) -> dict:
    """Untuk KPI G6 laporan ESG: klaim terverifikasi auditor yang periodenya di dalam rentang laporan."""
    rows = (await db.execute(select(CarbonClaim.status, func.count(CarbonClaim.id), func.sum(CarbonClaim.net_removal_tco2e))
                             .where(CarbonClaim.period_start >= start, CarbonClaim.period_end <= end)
                             .group_by(CarbonClaim.status))).all()
    return {s: {"count": n, "net_tco2e": round(t or 0, 3)} for s, n, t in rows}
