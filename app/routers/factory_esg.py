"""Sub-router pabrik: ESG, klaim karbon, efisiensi & biaya tambahan pabrik.

Dipisah dari app/routers/factory.py (audit 23 Okt 2026, CLAUDE.md §3.1) dan di-mount olehnya.
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_role
from ..models.user import User, UserRole
from ..models.conversion import CarbonCredit
from ..engines.quality import biochar_yield_db
from ..params import P
from ..security.url import EvidenceUrl

router = APIRouter()

def _period(from_: str | None, to: str | None) -> tuple[datetime, datetime, str]:
    """Bulan YYYY-MM inklusif → [awal bulan from, awal bulan setelah to). Default 12 bulan terakhir."""
    now = datetime.now(timezone.utc)

    def parse(x):
        try:
            y, m = (int(v) for v in x.split("-"))
            return datetime(y, m, 1, tzinfo=timezone.utc)
        except (ValueError, AttributeError) as e:
            raise HTTPException(422, "Format bulan harus YYYY-MM") from e
    end_m = parse(to) if to else datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    end = datetime(end_m.year + (end_m.month == 12), end_m.month % 12 + 1, 1, tzinfo=timezone.utc)
    if from_:
        start = parse(from_)
    else:
        idx = end_m.year * 12 + end_m.month - 1 - 11
        start = datetime(idx // 12, idx % 12 + 1, 1, tzinfo=timezone.utc)
    if start >= end:
        raise HTTPException(422, "Bulan awal harus sebelum bulan akhir")
    return start, end, f"{start:%Y-%m} s.d. {end_m:%Y-%m}"


_pabrik_dep = require_role(UserRole.PABRIK, UserRole.ADMIN)
# Aksi yang mengubah timbangan / stok hanya oleh operator pabrik (admin tidak, demi pemisahan tugas).
_pabrik_only = require_role(UserRole.PABRIK)
_audit_read = require_role(UserRole.PABRIK, UserRole.ADMIN, UserRole.AUDITOR)



router = APIRouter()


@router.get("/esg/report")
async def esg_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
    from_: Annotated[str | None, Query(alias="from")] = None,
    to: str | None = None,
):
    """Laporan ESG (E/S/G + karbon terpisah + penghematan) dari data nyata. Struktur: docs/09_RISET_STANDAR_ESG_BIOCHAR.md."""
    from ..services.esg import esg_report as _esg
    start, end, label = _period(from_, to)
    return await _esg(db, start, end, label)


class CarbonClaimRequest(BaseModel):
    """F11: periode bulan YYYY-MM (inklusif) + hasil lab biochar periode tersebut (wajib)."""
    from_: str = Field(..., alias="from", pattern=r"^\d{4}-\d{2}$")
    to: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    lab_c_org_pct: float = Field(..., gt=0, le=100)
    lab_h_corg_ratio: float = Field(..., gt=0, le=2)
    lab_name: str = Field(..., min_length=3, max_length=120)
    lab_report_no: str = Field(..., min_length=2, max_length=80)
    lab_report_url: EvidenceUrl = Field(..., min_length=9)       # wajib: foto/scan laporan lab

    model_config = {"populate_by_name": True}

    def lab(self) -> dict:
        return self.model_dump(include={"lab_c_org_pct", "lab_h_corg_ratio", "lab_name", "lab_report_no",
                                        "lab_report_url"})


@router.post("/carbon-claims/preview")
async def carbon_claim_preview(req: CarbonClaimRequest, db: Annotated[AsyncSession, Depends(get_db)],
                               user: Annotated[User, Depends(_pabrik_only)]):
    """Pratinjau klaim removal (tidak menyimpan): hasil hitung dengan C-org lab + daftar penghalang & celah."""
    from ..services import carbon_claims
    start, end, label = _period(req.from_, req.to)
    res = await carbon_claims.compute(db, start, end, req.lab())
    return {"period": label, **{k: v for k, v in res.items() if k != "snapshot"},
            "carbon_tco2e": res["snapshot"]["carbon_tco2e"]}


@router.post("/carbon-claims", status_code=201)
async def carbon_claim_submit(req: CarbonClaimRequest, db: Annotated[AsyncSession, Depends(get_db)],
                              user: Annotated[User, Depends(_pabrik_only)]):
    """Ajukan klaim: snapshot dibekukan (SHA-256) & serah-terima biochar dikunci; diputus auditor (empat mata)."""
    from ..services import carbon_claims
    start, end, _ = _period(req.from_, req.to)
    return await carbon_claims.submit(db, user, start, end, req.lab())


@router.get("/carbon-claims")
async def carbon_claim_list(db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(_audit_read)]):
    from ..services import carbon_claims
    return await carbon_claims.list_claims(db)


@router.get("/esg/report.csv")
async def esg_report_csv(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
    from_: Annotated[str | None, Query(alias="from")] = None,
    to: str | None = None,
):
    import csv
    import io
    from fastapi.responses import Response
    from ..services.esg import esg_report as _esg
    start, end, label = _period(from_, to)
    r = await _esg(db, start, end, label)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Pilar", "Kode", "KPI", "Nilai", "Satuan", "Rumus", "Standar", "Sumber data", "Catatan"])
    for pillar, key in (("Lingkungan", "environment"), ("Sosial", "social"), ("Tata kelola", "governance")):
        for k in r[key]:
            w.writerow([pillar, k["code"], k["name"], "" if k["value"] is None else k["value"], k["unit"], k["formula"],
                        k["standard"], k["source"], k.get("note", "")])
    for name, t in r["efficiency"].items():
        w.writerow(["Efisiensi", name, f"Penghematan {name}", t.get("saving_rp"), "Rp", "", "", "services/efficiency.py",
                    f"{t.get('saving_co2e_kg')} kgCO2e"])
    fname = f"laporan-esg-{start:%Y%m}-{(end):%Y%m}.csv"
    return Response("\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@router.get("/efficiency")
async def efficiency(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
    from_: Annotated[str | None, Query(alias="from")] = None,
    to: str | None = None,
):
    """Optimasi & efisiensi per proses: penghematan terealisasi, tercatat, dan potensi (Rp & kgCO₂e) + rekomendasi."""
    from ..services.efficiency import efficiency_overview
    start, end, _ = _period(from_, to)
    return await efficiency_overview(db, start, end)


class EfficiencyActionIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    process: str = Field(..., max_length=20)
    title: str = Field(..., min_length=3, max_length=160)
    description: str | None = Field(None, max_length=2000)
    metric: str | None = Field(None, max_length=60)
    baseline_value: float | None = None
    current_value: float | None = None
    saving_rp: float | None = Field(None, ge=0, le=1e12)
    saving_co2e_kg: float | None = Field(None, ge=-1e9, le=1e9)
    period: str | None = Field(None, pattern=r"^\d{4}-\d{2}$")
    status: str = Field("rencana", pattern="^(rencana|berjalan)$")
    evidence: str | None = Field(None, max_length=1000)
    source_opportunity: str | None = Field(None, max_length=40)


class EfficiencyStatusIn(BaseModel):
    status: str = Field(..., pattern="^(rencana|berjalan|terverifikasi|batal)$")
    evidence: str | None = Field(None, max_length=1000)
    saving_rp: float | None = Field(None, ge=0, le=1e12)
    saving_co2e_kg: float | None = Field(None, ge=-1e9, le=1e9)


@router.post("/efficiency/actions", status_code=201)
async def create_efficiency_action(
    body: EfficiencyActionIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Catat aksi penghematan / pengurangan dampak (status awal: rencana atau berjalan)."""
    from ..services.efficiency import create_action
    return await create_action(db, user, body.model_dump())


@router.patch("/efficiency/actions/{action_id}")
async def update_efficiency_action(
    action_id: int,
    body: EfficiencyStatusIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Ubah status; 'terverifikasi' wajib bukti & diverifikasi orang lain (empat mata)."""
    from ..services.efficiency import update_action_status
    return await update_action_status(db, user, action_id, body.status, body.evidence, body.saving_rp, body.saving_co2e_kg)


@router.get("/charges")
async def logistics_charges(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
    status: str = "terbuka",
):
    """Potongan logistik pengepul (dipotong otomatis saat tagihan ditandai lunas)."""
    from ..models.factory_ops import LogisticsCharge
    from ..services.logistics import charge_dict
    q = select(LogisticsCharge).order_by(LogisticsCharge.id.desc()).limit(200)
    if status != "semua":
        q = q.where(LogisticsCharge.status == status)
    return [charge_dict(c) for c in (await db.execute(q)).scalars().all()]


class WaiveChargeRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=300)


@router.post("/charges/{charge_id}/waive")
async def waive_charge(
    charge_id: int,
    body: WaiveChargeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Bebaskan potongan (mis. jalan putus/bencana — bukan kesalahan pengepul). Alasan wajib, tercatat."""
    from ..models.factory_ops import LogisticsCharge
    from ..services.logistics import charge_dict
    c = (await db.execute(select(LogisticsCharge).where(LogisticsCharge.id == charge_id).with_for_update())).scalar_one_or_none()
    if c is None:
        raise HTTPException(404, "Potongan tidak ditemukan")
    if c.status != "terbuka":
        raise HTTPException(409, f"Potongan sudah {c.status}.")
    from sqlalchemy import update as _update
    res = await db.execute(_update(LogisticsCharge).where(LogisticsCharge.id == c.id, LogisticsCharge.status == "terbuka")
                           .values(status="dibebaskan", resolved_at=datetime.now(timezone.utc),
                                   reason=f"{c.reason or ''} · dibebaskan oleh #{user.id}: {body.reason}".strip(" ·"))
                           .execution_options(synchronize_session=False))
    if res.rowcount != 1:                      # baru saja dipotong saat pelunasan tagihan → jangan klaim "dibebaskan"
        await db.rollback()
        raise HTTPException(409, "Potongan ini baru saja dipotong pada pelunasan tagihan.")
    await db.commit()
    await db.refresh(c)
    return charge_dict(c)


@router.get("/esg/summary")
async def esg_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Ringkasan ESG: total emisi dihindari, kredit karbon."""
    result = await db.execute(
        select(
            func.count(CarbonCredit.id),
            func.sum(CarbonCredit.biomass_ton),
            func.sum(CarbonCredit.emission_avoided_tco2),
            func.sum(CarbonCredit.net_reduction_tco2),
        )
    )
    row = result.one()
    return {
        "total_records": row[0] or 0,
        "total_biomass_ton": round(row[1] or 0, 2),
        "total_emission_avoided_tco2": round(row[2] or 0, 4),
        "net_carbon_credits_tco2": round(row[3] or 0, 4),
        # Estimasi biochar dari model rendemen AKTIF (menu Parameter), bukan angka tertanam
        "estimated_biochar_ton": round((row[1] or 0) * biochar_yield_db(P("limbah.pyrolysis_temp_c"),
                                                                        P("rendemen.ref_ash")) / 100, 2),
        # Potensi SiO2 = biomassa x abu referensi x fraksi SiO2 dalam abu (parameter aktif, sama dengan engine mutu)
        "estimated_sio2_ton": round((row[1] or 0) * P("rendemen.ref_ash") / 100
                                    * P("rendemen.sio2_fraction_of_ash"), 2),
        "methodology": "IPCC 2006 Tier 2",
    }
