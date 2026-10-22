"""Router: Pabrik (🏭) — Endpoints analytics-heavy untuk pabrik/end-user."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_role
from ..models.user import User, UserRole
from ..models.harvest import Harvest, HarvestStatus
from ..models.conversion import Conversion, CarbonCredit
from ..engines.carbon import CarbonInput, calculate_carbon_reduction
from ..engines.forecaster import ForecastInput, forecast_supply
from ..engines.quality import FeedstockSample, biochar_yield_db, score_sample, yield_curve
from ..engines.blending import BlendRequest, optimize_blend
from ..params import P
from ..models.ledger import CustodyStage
from ..models.route import Route, RouteStop, RouteStatus
from ..engines.energy import EnergyAnalysisRequest, analyze as analyze_energy
from ..models.energy import EnergyMeterReading
from ..engines.factory_econ import PricingRequest, recommend_price
from ..models.factory_ops import CollectorSettlement, DeliveryRequest, InboundQC, ManufacturingBatch
from ..services import factory_ops
from ..services.custody import convert_and_allocate, load_harvest, mass_balance, shrinkage_fields, transition

router = APIRouter()

_pabrik_dep = require_role(UserRole.PABRIK, UserRole.ADMIN)
# Aksi yang mengubah timbangan / stok hanya oleh operator pabrik (admin tidak, demi pemisahan tugas).
_pabrik_only = require_role(UserRole.PABRIK)
_audit_read = require_role(UserRole.PABRIK, UserRole.ADMIN, UserRole.AUDITOR)


class EnergyReadingIn(BaseModel):
    facility: str = Field(..., min_length=2, max_length=100)
    period: str = Field(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    kwh: float = Field(..., ge=0)
    building_kwh: float | None = Field(None, ge=0)
    production_ton: float = Field(0, ge=0)
    peak_kw: float | None = Field(None, ge=0)
    operating_hours: float | None = Field(None, gt=0, le=744)
    cost_rp: float | None = Field(None, ge=0)
    floor_area_m2: float = Field(..., gt=0)
    building_type: str = Field("ac", pattern="^(ac|non_ac)$")
    note: str | None = Field(None, max_length=500)


class DispatchRequest(BaseModel):
    driver_id: int
    harvest_ids: list[int] = Field(..., min_length=1, max_length=50)
    vehicle_plate: str | None = None
    vehicle_m3: float = Field(30, gt=0)


class ReceiveRequest(BaseModel):
    harvest_id: int
    received_kg: float = Field(..., gt=0, le=50000, description="Timbangan jembatan pabrik (otoritatif)")
    client_event_id: str | None = Field(None, max_length=64)
    note: str | None = None
    evidence_photo_url: str | None = Field(None, max_length=1000)
    price_per_kg: float | None = Field(None, ge=0, le=20_000,
                                       description="Harga beli ke pengepul (Rp/kg). Kosong = rekomendasi netback engine")


class FactoryRejectRequest(BaseModel):
    harvest_id: int
    reason: str = Field(..., min_length=3, max_length=500)
    weighed_kg: float | None = Field(None, gt=0)
    client_event_id: str | None = Field(None, max_length=64)


class ConversionRequest(BaseModel):
    batch_code: str = Field(..., min_length=3, max_length=50)
    harvest_ids: list[int] = Field(..., min_length=1, max_length=500)
    biochar_kg: float = Field(..., gt=0)
    pyrolysis_temp_c: float | None = Field(None, ge=300, le=900)
    farmer_return_share: float | None = Field(None, ge=0, le=1,
                                              description="Default: menu Parameter → sirkular.farmer_return_share")


@router.post("/dispatch", status_code=201)
async def dispatch_route(
    req: DispatchRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Buat rute penjemputan untuk harvest terverifikasi dan tugaskan ke supir."""
    driver = (await db.execute(select(User).where(User.id == req.driver_id))).scalar_one_or_none()
    if not driver or driver.role != UserRole.DRIVER or not driver.is_active:
        raise HTTPException(422, "driver_id bukan supir aktif")
    harvests = (await db.execute(select(Harvest).where(Harvest.id.in_(req.harvest_ids)))).scalars().all()
    bad = sorted(set(req.harvest_ids) - {h.id for h in harvests if h.status == HarvestStatus.VERIFIED})
    if bad:
        raise HTTPException(409, f"Hanya harvest berstatus 'verified' yang bisa dijadwalkan: {bad}")
    busy = (await db.execute(
        select(RouteStop.harvest_id).join(Route, RouteStop.route_id == Route.id)
        .where(RouteStop.harvest_id.in_(req.harvest_ids),
               Route.status.in_([RouteStatus.PLANNED, RouteStatus.IN_PROGRESS]))
    )).scalars().all()
    if busy:
        raise HTTPException(409, f"Harvest sudah ada di rute aktif: {sorted(busy)}")

    order = {hid: i for i, hid in enumerate(req.harvest_ids)}
    harvests = sorted(harvests, key=lambda h: order[h.id])
    total_kg = sum(h.verified_kg or h.quantity_kg for h in harvests)
    route = Route(driver_id=driver.id, vehicle_plate=req.vehicle_plate, status=RouteStatus.PLANNED,
                  vehicle_m3=req.vehicle_m3, total_ton=round(total_kg / 1000, 3))
    db.add(route)
    await db.flush()
    for i, h in enumerate(harvests, start=1):
        kg = h.verified_kg or h.quantity_kg
        db.add(RouteStop(route_id=route.id, harvest_id=h.id, mill_id=h.mill_id, stop_order=i,
                         planned_ton=round(kg / 1000, 3), planned_m3=round(kg / 110, 2)))
    await db.flush()
    stops = (await db.execute(
        select(RouteStop).where(RouteStop.route_id == route.id).order_by(RouteStop.stop_order)
    )).scalars().all()
    return {"route_id": route.id, "driver_id": driver.id,
            "stops": [{"route_stop_id": st.id, "harvest_id": st.harvest_id, "order": st.stop_order} for st in stops]}


@router.post("/receive")
async def receive_harvest(
    req: ReceiveRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Timbang terima di pabrik: COLLECTED → DELIVERED, hitung susut terhadap timbangan pengepul."""
    harvest = await load_harvest(db, req.harvest_id)
    reference = harvest.verified_kg or harvest.quantity_kg
    fields = shrinkage_fields(reference, req.received_kg)
    note = "; ".join(x for x in (fields["discrepancy_note"], req.note) if x) or None
    await transition(
        db, req.harvest_id, HarvestStatus.COLLECTED, HarvestStatus.DELIVERED, user, CustodyStage.FACTORY_RECEIVE,
        weight_kg=req.received_kg, client_event_id=req.client_event_id, note=note,
        evidence_photo_url=req.evidence_photo_url, received_by_id=user.id, delivered_at=datetime.now(timezone.utc), **fields,
    )
    # Jalur rute: catat kewajiban bayar ke pengepul (sebelumnya tidak tercatat → margin pengepul tidak lengkap)
    settlement = await factory_ops.settle_route(db, await load_harvest(db, req.harvest_id), user, req.price_per_kg)
    return {
        "settlement": factory_ops.settlement_dict(settlement) if settlement else None,
        "harvest_id": req.harvest_id, "status": "delivered", "reference_kg": reference,
        "received_kg": req.received_kg, "shrinkage_kg": fields["shrinkage_kg"],
        "shrinkage_pct": fields["shrinkage_pct"], "discrepancy_flag": fields["discrepancy_flag"],
        "computation_details": {
            "formula": "susut% = (timbangan_pengepul − timbangan_pabrik) / timbangan_pengepul × 100",
            "tolerance_pct": P("sirkular.shrinkage_tolerance_pct"),
            "flag_rule": "|susut%| > toleransi → ditandai untuk auditor (penerimaan tetap dicatat)",
        },
    }


@router.post("/reject")
async def factory_reject(
    req: FactoryRejectRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Tolak muatan saat tiba: COLLECTED → REJECTED (atomik; bersaing aman dengan /receive)."""
    await transition(
        db, req.harvest_id, HarvestStatus.COLLECTED, HarvestStatus.REJECTED, user, CustodyStage.FACTORY_REJECT,
        weight_kg=req.weighed_kg, client_event_id=req.client_event_id, note=req.reason,
        rejected_reason=req.reason, rejected_at=datetime.now(timezone.utc), received_kg=req.weighed_kg,
    )
    return {"harvest_id": req.harvest_id, "status": "rejected"}


@router.post("/conversions", status_code=201)
async def create_conversion(
    req: ConversionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Catat batch pirolisis dan kreditkan biochar ke dompet petani pemasok (proporsional berat terima)."""
    share = P("sirkular.farmer_return_share") if req.farmer_return_share is None else req.farmer_return_share
    return await convert_and_allocate(db, user, req.harvest_ids, req.biochar_kg, req.batch_code, share,
                                      req.pyrolysis_temp_c)


@router.get("/mass-balance/{harvest_id}")
async def get_mass_balance(
    harvest_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
):
    """Jejak berat & serah-terima satu harvest dari petani sampai alokasi biochar."""
    return await mass_balance(db, harvest_id)


@router.post("/carbon/calculate")
async def carbon_calculate(
    inp: CarbonInput,
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Hitung pengurangan emisi CO₂ (IPCC Tier 2)."""
    return calculate_carbon_reduction(inp)


@router.post("/forecast")
async def supply_forecast(
    inp: ForecastInput,
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Prediksi pasokan sekam bulanan."""
    return forecast_supply(inp)


@router.get("/forecast/30d")
async def forecast_30_days(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_dep)],
    harvest_area_ha: float | None = None,
):
    """Proyeksi pasokan 30 hari ke depan."""
    from datetime import date, timedelta

    harvest_area_ha = P("proyeksi.harvest_area_ha") if harvest_area_ha is None else harvest_area_ha
    today = date.today()
    points = []
    for i in range(30):
        d = today + timedelta(days=i)
        inp = ForecastInput(
            harvest_area_ha=harvest_area_ha,
            month=d.month,
            year=d.year,
        )
        result = forecast_supply(inp)
        daily = result.predicted_supply_ton / 30  # rough daily estimate
        points.append({
            "date": d.isoformat(),
            "predicted": round(daily, 1),
            "pred_husk_ton": round(daily, 1),
            "low": round(result.confidence_low / 30, 1),
            "high": round(result.confidence_high / 30, 1),
        })
    return {
        "points": points,
        "harvest_area_ha": harvest_area_ha,
        "total_predicted_ton": round(sum(p["predicted"] for p in points), 1),
    }


@router.post("/quality/score")
async def quality_score(
    sample: FeedstockSample,
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Evaluasi kualitas feedstock masuk."""
    return score_sample(sample)


@router.get("/quality/yield-curve")
async def quality_yield(
    user: Annotated[User, Depends(_pabrik_dep)],
    ash: float | None = None,
):
    """Kurva rendemen biochar vs suhu pirolisis (abu default = acuan di menu Parameter)."""
    return yield_curve(ash)


@router.post("/blend/recommend")
async def blend_recommend(
    req: BlendRequest,
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Optimasi campuran feedstock (Engine ③)."""
    if not req.feedstocks:
        raise HTTPException(422, "Minimal satu feedstock.")
    return optimize_blend(req)


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
        "methodology": "IPCC 2006 Tier 2",
    }


@router.get("/supply/overview")
async def supply_overview(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Overview supply saat ini dari semua petani."""
    result = await db.execute(
        select(
            Harvest.status,
            func.count(Harvest.id),
            func.sum(Harvest.quantity_kg),
        )
        .group_by(Harvest.status)
    )
    rows = result.all()
    return {
        "by_status": [
            {"status": r[0].value if hasattr(r[0], "value") else str(r[0]), "count": r[1], "total_kg": round(r[2] or 0, 1)}
            for r in rows
        ]
    }


# ---------------------------------------------------------------- ⑩ Energi (histori dari database)
@router.get("/energy/facilities")
async def energy_facilities(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
):
    rows = (await db.execute(
        select(EnergyMeterReading.facility, func.count(EnergyMeterReading.id),
               func.min(EnergyMeterReading.period), func.max(EnergyMeterReading.period))
        .group_by(EnergyMeterReading.facility))).all()
    return [{"facility": f, "months": n, "from": a, "to": b} for f, n, a, b in rows]


@router.get("/energy/analysis")
async def energy_analysis(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
    facility: str | None = None,
    months: int = 24,
    baseline_months: int = 12,
):
    """IKE, SEC, baseline ISO 50006, anomali/pemborosan & rekomendasi dari histori di database."""
    if facility is None:   # default deterministik: fasilitas dengan histori terpanjang
        facility = (await db.execute(
            select(EnergyMeterReading.facility).group_by(EnergyMeterReading.facility)
            .order_by(func.count(EnergyMeterReading.id).desc(), EnergyMeterReading.facility).limit(1)
        )).scalar_one_or_none()
    rows = (await db.execute(
        select(EnergyMeterReading).where(EnergyMeterReading.facility == facility)
        .order_by(EnergyMeterReading.period.desc()).limit(min(max(months, 6), 240))
    )).scalars().all()
    if len(rows) < 6:
        raise HTTPException(422, "Minimal 6 bulan histori energi diperlukan untuk analisis.")
    rows = rows[::-1]
    latest = rows[-1]
    req = EnergyAnalysisRequest(
        facility=facility, floor_area_m2=latest.floor_area_m2, building_type=latest.building_type,
        baseline_months=min(max(baseline_months, 6), len(rows)),
        readings=[{"period": r.period, "kwh": r.kwh, "building_kwh": r.building_kwh,
                   "production_ton": r.production_ton, "peak_kw": r.peak_kw,
                   "operating_hours": r.operating_hours, "cost_rp": r.cost_rp} for r in rows])
    out = analyze_energy(req)
    out["data_source"] = {"table": "energy_readings", "rows": len(rows),
                          "demo_rows": sum(r.source == "demo" for r in rows),
                          "notes": {r.period: r.note for r in rows if r.note}}
    return out


@router.post("/energy/readings", status_code=201)
async def upsert_energy_reading(
    body: EnergyReadingIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Catat/perbarui pembacaan meter bulanan (satu baris per fasilitas per bulan)."""
    row = (await db.execute(select(EnergyMeterReading).where(
        EnergyMeterReading.facility == body.facility, EnergyMeterReading.period == body.period))).scalar_one_or_none()
    data = body.model_dump()
    if row is None:
        row = EnergyMeterReading(**data, source="manual", recorded_by_id=user.id)
        db.add(row)
    else:
        for k, v in data.items():
            setattr(row, k, v)
        row.source, row.recorded_by_id = "manual", user.id
    await db.flush()
    return {"id": row.id, "facility": row.facility, "period": row.period}


# ---------------------------------------------------------------- ⑪ Procurement, QC masuk, manufaktur sirkular
class NegotiationActionF(BaseModel):
    action: str = Field(..., pattern="^(accept|counter|reject)$")
    price_per_kg: float | None = Field(None, gt=0, le=20_000)
    date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    note: str | None = Field(None, max_length=500)


class InboundQCIn(BaseModel):
    request_id: int
    gross_kg: float = Field(..., gt=0, le=1_000_000)
    tare_kg: float = Field(0, ge=0)
    moisture: float = Field(..., ge=0, le=60)
    ash: float = Field(..., ge=0, le=60)
    volatile_matter: float = Field(..., ge=0, le=100)
    fixed_carbon: float = Field(..., ge=0, le=100)
    contamination: float = Field(0, ge=0, le=50)
    evidence_photo_url: str | None = Field(None, max_length=1000)
    note: str | None = Field(None, max_length=500)


class BatchInputIn(BaseModel):
    qc_id: int
    kg: float = Field(..., gt=0)


class BatchCostIn(BaseModel):
    item: str = Field(..., min_length=2, max_length=40)
    amount_rp: float = Field(..., ge=0)
    cost_type: str = Field("variabel", pattern="^(variabel|tetap)$")
    product: str | None = Field(None, pattern="^(bio_pellet|biochar|bio_silika)$",
                                description="Isi bila biaya terpisah satu produk; kosong = biaya bersama")
    driver_qty: float | None = Field(None, ge=0)
    driver_unit: str | None = Field(None, max_length=20)
    rate: float | None = Field(None, ge=0)


class BatchIn(BaseModel):
    batch_code: str = Field(..., min_length=3, max_length=50)
    inputs: list[BatchInputIn] = Field(..., min_length=1, max_length=200)
    outputs: dict[str, float] = Field(..., description="kg per produk: bio_pellet, biochar, bio_silika")
    losses: dict[str, float] = Field(default_factory=dict,
                                     description="kg per jenis: air, volatil_syngas, residu_ekstraksi, susut_proses")
    costs: list[BatchCostIn] = Field(default_factory=list, max_length=100)
    operating_hours: float | None = Field(None, gt=0, le=744)
    pyrolysis_temp_c: float | None = Field(None, ge=300, le=800)
    pellet_share: float | None = Field(None, ge=0, le=1)
    silica_share_of_biochar: float | None = Field(None, ge=0, le=1)
    silica_route: str | None = Field(None, pattern="^(biochar|abu_pembakaran|sekam_langsung)$")
    silica_husk_share: float | None = Field(None, ge=0, le=1)
    prices: dict[str, float] | None = Field(None, description="Harga jual batch ini (Rp/kg); kosong = menu Parameter")
    note: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def _check(self):
        ids = [i.qc_id for i in self.inputs]
        if len(ids) != len(set(ids)):
            raise ValueError("Lot QC ganda pada input batch")
        bad = set(self.outputs) - {"bio_pellet", "biochar", "bio_silika"}
        if bad or any(v < 0 for v in self.outputs.values()):
            raise ValueError("outputs hanya bio_pellet/biochar/bio_silika dengan kg ≥ 0")
        bad = set(self.losses) - {"air", "volatil_syngas", "gas_pembakaran", "residu_ekstraksi", "susut_proses"}
        if bad or any(v < 0 for v in self.losses.values()):
            raise ValueError("losses hanya air/volatil_syngas/gas_pembakaran/residu_ekstraksi/susut_proses, kg ≥ 0")
        if self.prices and (set(self.prices) - {"bio_pellet", "biochar", "bio_silika"}
                            or any(v < 0 for v in self.prices.values())):
            raise ValueError("prices hanya bio_pellet/biochar/bio_silika dengan Rp/kg ≥ 0")
        return self


@router.post("/pricing/recommend")
async def pricing_recommend(
    req: PricingRequest,
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Rekomendasi harga beli sekam: lantai / target / plafon + rincian netback & sensitivitas kadar air."""
    return recommend_price(req)


@router.get("/delivery-requests")
async def delivery_inbox(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_dep)],
    status: str | None = None,
):
    q = select(DeliveryRequest, User.full_name).join(User, User.id == DeliveryRequest.collector_id)
    if status:
        q = q.where(DeliveryRequest.status == status)
    rows = (await db.execute(q.order_by(DeliveryRequest.id.desc()).limit(200))).all()
    return [{**factory_ops.request_dict(r), "collector": name} for r, name in rows]


@router.post("/delivery-requests/{request_id}/respond")
async def respond_delivery(
    request_id: int,
    body: NegotiationActionF,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Umpan balik pabrik: terima (jadwal & harga), tawar balik, atau tolak."""
    try:
        r = await factory_ops.respond(db, user, request_id, body.action, body.price_per_kg, body.date, body.note)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return factory_ops.request_dict(r)


@router.post("/qc", status_code=201)
async def record_inbound_qc(
    body: InboundQCIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Input Quality Control: timbang (bruto − tara), uji proksimat, keputusan & harga akhir (basis kering)."""
    try:
        qc = await factory_ops.inbound_qc(db, user, body.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return factory_ops.qc_dict(qc)


@router.get("/qc/lots")
async def qc_lots(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
    available_only: bool = True,
):
    q = select(InboundQC).order_by(InboundQC.id.desc()).limit(200)
    if available_only:
        q = q.where(InboundQC.remaining_kg > 0)
    return [factory_ops.qc_dict(x) for x in (await db.execute(q)).scalars().all()]


@router.post("/batches", status_code=201)
async def create_batch(
    body: BatchIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Catat batch manufaktur sirkular: konsumsi lot, output 3 produk + loss, biaya → mass balance & unit economics."""
    try:
        b = await factory_ops.create_batch(db, user, body.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return factory_ops.batch_dict(b)


@router.get("/batches")
async def list_batches(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
    limit: int = 50,
):
    rows = (await db.execute(select(ManufacturingBatch).order_by(ManufacturingBatch.id.desc())
                             .limit(min(max(limit, 1), 200)))).scalars().all()
    return [factory_ops.batch_dict(b) for b in rows]


# ---------------------------------------------------------------- pembayaran ke pengepul (kedua jalur)
class SettlementPrice(BaseModel):
    price_per_kg: float = Field(..., ge=0, le=20_000)
    reason: str = Field(..., min_length=5, max_length=300)


class SettlementPay(BaseModel):
    payment_reference: str = Field(..., min_length=3, max_length=80, description="No. transfer / bukti bayar")


@router.get("/settlements")
async def list_settlements(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
    status: str | None = None,
):
    q = select(CollectorSettlement, User.full_name).join(User, User.id == CollectorSettlement.collector_id)
    if status:
        q = q.where(CollectorSettlement.status == status)
    rows = (await db.execute(q.order_by(CollectorSettlement.id.desc()).limit(300))).all()
    return [{**factory_ops.settlement_dict(s), "collector": name} for s, name in rows]


@router.post("/settlements/{settlement_id}/price")
async def price_settlement(
    settlement_id: int, body: SettlementPrice,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Tetapkan harga untuk pembayaran 'menunggu harga' (atau koreksi sebelum dibayar)."""
    return factory_ops.settlement_dict(await factory_ops.set_settlement_price(db, settlement_id, body.price_per_kg,
                                                                              user, body.reason))


@router.post("/settlements/{settlement_id}/pay")
async def pay_settlement(
    settlement_id: int, body: SettlementPay,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    return factory_ops.settlement_dict(await factory_ops.mark_settlement_paid(db, settlement_id, body.payment_reference))


@router.get("/arrivals")
async def route_arrivals(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Sekam jalur rute yang sudah dijemput supir dan menunggu timbang terima pabrik."""
    rows = (await db.execute(select(Harvest).where(Harvest.status == HarvestStatus.COLLECTED)
                             .order_by(Harvest.id).limit(200))).scalars().all()
    return [{"harvest_id": h.id, "collector_id": h.collector_id, "verified_kg": h.verified_kg, "moisture": h.moisture,
             "ash": h.ash, "grade": h.grade} for h in rows]
