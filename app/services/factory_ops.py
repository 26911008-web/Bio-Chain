"""Service operasi pabrik: Delivery Request + negosiasi, QC masuk, batch manufaktur & biaya.

Semua perubahan status = compare-and-swap (status + version + pihak yang wajib menjawab), konsumsi stok lot
= UPDATE ... WHERE remaining_kg >= kg. Dua klik/aktor serentak tidak bisa menyepakati dua harga atau
memakai stok yang sama dua kali.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..engines.factory_econ import (LOSS_KINDS, PRODUCTS, PricingRequest, batch_economics,
                                    contract_moisture_adjustment, process_yields, recommend_price)
from ..models.harvest import Harvest, HarvestStatus
from ..models.ledger import BiocharLedgerEntry, CustodyStage
from .custody import allocate_grams, shrinkage_fields, transition
from ..engines.quality import FeedstockSample, score_sample
from ..models.factory_ops import (BatchCost, BatchInput, BatchLoss, BatchOutput, CollectorSettlement, DeliveryRequest,
                                  FinishedGoodsMovement, InboundQC, ManufacturingBatch, NegotiationEvent, QCDecision, RequestStatus,
                                  SettlementEvent, SettlementStatus)
from ..models.user import User, UserRole
from ..params import P
from ..models.route import Route, RouteStatus, RouteStop
from .custody import TransitionConflict
from .trx_code import new_verification_code

OPEN = (RequestStatus.SUBMITTED, RequestStatus.COUNTERED)


def _v(e):
    return e.value if hasattr(e, "value") else e


def _party(user: User) -> str:
    return "pabrik" if _v(user.role) in (UserRole.PABRIK.value, UserRole.ADMIN.value) else "pengepul"


def request_dict(r: DeliveryRequest) -> dict:
    return {"id": r.id, "collector_id": r.collector_id, "quantity_kg": r.quantity_kg, "moisture_est": r.moisture_est,
            "ash_est": r.ash_est, "grade_est": r.grade_est, "status": _v(r.status), "pending_party": r.pending_party,
            "rounds": r.rounds, "current_offer": {"price_per_kg": r.proposed_price_per_kg, "date": r.proposed_date},
            "recommended_price_per_kg": r.recommended_price_per_kg,
            "agreed": {"price_per_kg": r.agreed_price_per_kg, "date": r.agreed_date} if r.agreed_price_per_kg else None,
            "logistics_carrier": getattr(r, "logistics_carrier", "FACTORY_FLEET") or "FACTORY_FLEET",
            "mill_id": getattr(r, "mill_id", None),
            "biomass_type": getattr(r, "biomass_type", "sekam_padi") or "sekam_padi",
            "pricing_mode": getattr(r, "pricing_mode", "AUCTION") or "AUCTION",
            "note": r.note, "created_at": r.created_at.isoformat() if r.created_at else None}


def factory_price_preview(moisture: float, ash: float | None, contamination: float = 0) -> dict:
    """Ringkasan harga rekomendasi untuk pengepul (target saja — lantai/plafon pabrik tidak dibuka)."""
    from ..engines.factory_econ import PriceMissing
    try:
        r = recommend_price(PricingRequest(moisture=moisture, ash=P("rendemen.ref_ash") if ash is None else ash,
                                           contamination=contamination, sensitivity=False))
    except PriceMissing:
        return {"recommended_price_per_kg": None, "accept": True,
                "basis": "pabrik belum mengisi harga jual produk — rekomendasi belum tersedia"}
    return {"recommended_price_per_kg": r["target_per_kg"] if r["accept"] else 0.0, "accept": r["accept"],
            "basis": "netback produk (bio-pellet, biochar, bio-silika) − biaya − margin pabrik",
            **({"reason": r["reason"]} if "reason" in r else {})}


async def _event(db, req_id, actor: User, action, price=None, date=None, note=None):
    db.add(NegotiationEvent(request_id=req_id, actor_id=actor.id, actor_role=_v(actor.role), action=action,
                            price_per_kg=price, date=date, note=note))


async def submit_request(db: AsyncSession, collector: User, data: dict) -> DeliveryRequest:
    rec = factory_price_preview(data["moisture_est"], data.get("ash_est"))
    r = DeliveryRequest(
        collector_id=collector.id,
        quantity_kg=data["quantity_kg"],
        moisture_est=data["moisture_est"],
        ash_est=data.get("ash_est"),
        grade_est=data.get("grade_est"),
        proposed_date=data["proposed_date"],
        proposed_price_per_kg=data["proposed_price_per_kg"],
        recommended_price_per_kg=rec["recommended_price_per_kg"],
        pending_party="pabrik",
        status=RequestStatus.SUBMITTED,
        logistics_carrier=data.get("logistics_carrier") or "FACTORY_FLEET",
        mill_id=data.get("mill_id"),
        biomass_type=data.get("biomass_type") or "sekam_padi",
        pricing_mode=data.get("pricing_mode") or "AUCTION",
        note=data.get("note")
    )
    db.add(r)
    await db.flush()
    ids = sorted(set(data.get("harvest_ids") or []))
    if ids:
        # Hanya harvest yang SUDAH ditimbang pengepul ini, belum terlampir di ajuan lain,
        # dan tidak sedang dalam rute aktif (PLANNED atau IN_PROGRESS) (CAS per baris)
        active_route_harvests = (
            select(RouteStop.harvest_id)
            .join(Route, RouteStop.route_id == Route.id)
            .where(
                RouteStop.harvest_id.is_not(None),
                Route.status.in_([RouteStatus.PLANNED, RouteStatus.IN_PROGRESS]),
            )
        )
        res = await db.execute(update(Harvest).where(
            Harvest.id.in_(ids), Harvest.collector_id == collector.id, Harvest.status == HarvestStatus.VERIFIED,
            Harvest.delivery_request_id.is_(None),
            ~Harvest.id.in_(active_route_harvests)).values(delivery_request_id=r.id)
            .execution_options(synchronize_session=False))
        if res.rowcount != len(ids):
            raise TransitionConflict("Sebagian harvest bukan milik Anda, belum ditimbang (verified), sedang dalam rute aktif, "
                                     "atau sudah terlampir di ajuan lain.")
    await _event(db, r.id, collector, "submit", r.proposed_price_per_kg, r.proposed_date,
                 (data.get("note") or "") + (f" | harvest {ids}" if ids else ""))
    await db.flush()
    return r


async def respond(db: AsyncSession, actor: User, request_id: int, action: str, price: float | None = None,
                  date: str | None = None, note: str | None = None) -> DeliveryRequest:
    """Jawab ajuan yang sedang menunggu pihak `actor`: accept | counter | reject (| cancel oleh pengepul)."""
    party = _party(actor)
    r = (await db.execute(select(DeliveryRequest).where(DeliveryRequest.id == request_id)
                          .execution_options(populate_existing=True))).scalar_one_or_none()
    if r is None or (party == "pengepul" and r.collector_id != actor.id):
        raise LookupError("Delivery request tidak ditemukan")
    now = datetime.now(timezone.utc)
    where = [DeliveryRequest.id == r.id, DeliveryRequest.version == r.version, DeliveryRequest.status.in_(OPEN)]

    if action == "cancel":
        if party != "pengepul":
            raise ValueError("Hanya pengepul yang dapat membatalkan ajuannya.")
        values = {"status": RequestStatus.CANCELLED, "pending_party": None, "decided_at": now}
    else:
        if r.pending_party != party:
            raise TransitionConflict(f"Menunggu jawaban {r.pending_party}, bukan {party}.")
        where.append(DeliveryRequest.pending_party == party)
        if action == "accept":
            values = {"status": RequestStatus.ACCEPTED, "agreed_price_per_kg": r.proposed_price_per_kg,
                      "agreed_date": r.proposed_date, "pending_party": None, "decided_at": now}
        elif action == "counter":
            if price is None or price <= 0 or not date:
                raise ValueError("Tawaran balik wajib berisi harga > 0 dan tanggal.")
            if r.rounds >= P("pabrik.max_negotiation_rounds"):
                raise TransitionConflict(f"Batas {P('pabrik.max_negotiation_rounds'):g} putaran tercapai — "
                                         "terima atau tolak tawaran terakhir.")
            values = {"status": RequestStatus.COUNTERED, "proposed_price_per_kg": price, "proposed_date": date,
                      "pending_party": "pengepul" if party == "pabrik" else "pabrik", "rounds": r.rounds + 1}
        elif action == "reject":
            values = {"status": RequestStatus.REJECTED, "pending_party": None, "decided_at": now}
        else:
            raise ValueError("Aksi tidak dikenal.")
    res = await db.execute(update(DeliveryRequest).where(*where)
                           .values(**values, version=DeliveryRequest.version + 1)
                           .execution_options(synchronize_session=False))
    if res.rowcount != 1:
        raise TransitionConflict("Ajuan sudah diubah pihak lain — muat ulang.")
    if values.get("status") in (RequestStatus.CANCELLED, RequestStatus.REJECTED):
        await db.execute(update(Harvest).where(Harvest.delivery_request_id == r.id)
                         .values(delivery_request_id=None).execution_options(synchronize_session=False))
    await _event(db, r.id, actor, action, price, date, note)
    await db.flush()
    return (await db.execute(select(DeliveryRequest).where(DeliveryRequest.id == r.id)
                             .execution_options(populate_existing=True))).scalar_one()


async def inbound_qc(db: AsyncSession, inspector: User, data: dict) -> InboundQC:
    """Timbang + uji mutu saat tiba. Harga kontrak disesuaikan basis kering; kontaminan tidak dibayar."""
    r = (await db.execute(select(DeliveryRequest).where(DeliveryRequest.id == data["request_id"])
                          .execution_options(populate_existing=True))).scalar_one_or_none()
    if r is None:
        raise LookupError("Delivery request tidak ditemukan")
    if _v(r.status) != RequestStatus.ACCEPTED.value:
        raise TransitionConflict(f"Hanya ajuan berstatus 'accepted' yang dapat di-QC (kini '{_v(r.status)}').")
    gross_net = data["gross_kg"] - data["tare_kg"]
    if gross_net <= 0:
        raise ValueError("Berat bersih harus > 0 (bruto − tara).")
    sorted_out = float(data.get("rejected_kg") or 0.0)
    if sorted_out >= gross_net - 1e-9:
        raise ValueError("Karung disortir ≥ berat bersih: tolak seluruh lot (isi kadar air/kontaminan aktual).")
    # Sortir di gerbang: karung basah/berjamur dipisah & dikarantina; sisanya dinilai & dibayar
    net = gross_net - sorted_out
    q = score_sample(FeedstockSample(moisture=data["moisture"], ash=data["ash"], volatile_matter=data["volatile_matter"],
                                     fixed_carbon=data["fixed_carbon"], contamination=data.get("contamination", 0)))
    rejected = q["grade"] == "TOLAK"
    payable = 0.0 if rejected else net * (1 - data.get("contamination", 0) / 100)
    # Refraksi kadar air: berat basis kering setara kadar air acuan kontrak (harga sudah disetarakan basis kering;
    # angka ini ditulis di nota agar petugas lapangan melihat "potongan air" dalam kg).
    m_ref = P("pabrik.reference_moisture_pct")
    dry_basis = net if data["moisture"] <= m_ref else net * (1 - data["moisture"] / 100) / (1 - m_ref / 100)
    refraction = 0.0 if rejected else max(0.0, net - dry_basis)
    # Harga dibulatkan ke sen dulu, lalu total dihitung dari harga yang tertera (yang tampil = yang dibayar)
    price = 0.0 if rejected else round(contract_moisture_adjustment(r.agreed_price_per_kg, r.moisture_est,
                                                                    data["moisture"]), 2)
    decision = (QCDecision.REJECT if rejected else
                QCDecision.ACCEPT_PENALTY if price < r.agreed_price_per_kg - 1e-9 or data.get("contamination", 0) > 0
                else QCDecision.ACCEPT)
    res = await db.execute(update(DeliveryRequest)
                           .where(DeliveryRequest.id == r.id, DeliveryRequest.status == RequestStatus.ACCEPTED)
                           .values(status=RequestStatus.REJECTED if rejected else RequestStatus.DELIVERED,
                                   version=DeliveryRequest.version + 1)
                           .execution_options(synchronize_session=False))
    if res.rowcount != 1:
        raise TransitionConflict("Ajuan sudah di-QC oleh proses lain.")
    collector = await db.get(User, r.collector_id)
    qc = InboundQC(request_id=r.id, gross_kg=data["gross_kg"], tare_kg=data["tare_kg"], net_kg=net, payable_kg=payable,
                   moisture=data["moisture"], ash=data["ash"], volatile_matter=data["volatile_matter"],
                   fixed_carbon=data["fixed_carbon"], contamination=data.get("contamination", 0),
                   grade=q["grade"], score=q["score"], decision=decision, final_price_per_kg=price,
                   total_payment_rp=round(payable * price), remaining_kg=0.0 if rejected else net,
                   verification_code=await new_verification_code(db, collector, inspector),
                   evidence_photo_url=data.get("evidence_photo_url"), inspector_id=inspector.id, note=data.get("note"),
                   rejected_kg=gross_net if rejected else sorted_out,
                   refraction_kg=round(refraction, 2), dry_basis_kg=None if rejected else round(dry_basis, 2))
    db.add(qc)
    await _event(db, r.id, inspector, "qc", price, None,
                 f"{_v(decision)}: grade {q['grade']}, air {data['moisture']}% (kontrak {r.moisture_est}%)")
    await db.flush()
    from .logistics import reason_from_quality as _rq
    await _receive_linked_harvests(db, inspector, r.id, net, rejected, qc.verification_code,
                                   _rq(data["moisture"], data.get("contamination", 0)) if rejected else None,
                                   gross_kg=data.get("gross_kg"), tare_kg=data.get("tare_kg"),
                                   slip_url=data.get("evidence_photo_url"))
    await settle_qc(db, qc, r.collector_id, inspector)
    from .logistics import open_return, reason_from_quality
    if rejected:
        await open_return(db, inspector, stage="qc_pabrik", request_id=r.id, qc_id=qc.id, quantity_kg=gross_net,
                          reason_code=reason_from_quality(data["moisture"], data.get("contamination", 0)),
                          moisture=data["moisture"], note=f"Lot ditolak QC ({qc.verification_code})",
                          evidence_photo_url=data.get("evidence_photo_url"))
    elif sorted_out > 0:
        await open_return(db, inspector, stage="qc_pabrik", request_id=r.id, qc_id=qc.id, quantity_kg=sorted_out,
                          reason_code=data.get("rejected_reason") or "berjamur", moisture=None,
                          note=f"Sortir sebagian lot {qc.verification_code}: {sorted_out:g} kg dipisah, tidak dibayar",
                          evidence_photo_url=data.get("evidence_photo_url"))
    return qc


async def _receive_linked_harvests(db, inspector: User, request_id: int, net_kg: float, rejected: bool, lot_code: str,
                                   reject_category: str | None = None, gross_kg: float | None = None,
                                   tare_kg: float | None = None, slip_url: str | None = None):
    """Teruskan hasil QC lot ke harvest petani yang terlampir: berat diterima dibagi proporsional timbangan
    pengepul (susut merata; kelebihan berat = stok milik pengepul sendiri, tidak dibagikan)."""
    linked = (await db.execute(select(Harvest).where(Harvest.delivery_request_id == request_id)
                               .execution_options(populate_existing=True))).scalars().all()
    if not linked:
        return
    total_verified = sum(h.verified_kg or h.quantity_kg for h in linked)
    factor = min(1.0, net_kg / total_verified) if total_verified > 0 else 0.0
    now = datetime.now(timezone.utc)
    for h in linked:
        ref = h.verified_kg or h.quantity_kg
        if rejected:
            await transition(db, h.id, HarvestStatus.VERIFIED, HarvestStatus.REJECTED, inspector,
                             CustodyStage.FACTORY_REJECT, note=f"QC lot ditolak ({lot_code})",
                             rejected_reason="QC pabrik: lot ditolak", rejected_at=now,
                             reject_category=reject_category or "lainnya",
                             gross_weight=gross_kg, tare_weight=tare_kg, net_weight=net_kg,
                             weighbridge_slip_url=slip_url)
            continue
        received = round(ref * factor, 3)
        await transition(db, h.id, HarvestStatus.VERIFIED, HarvestStatus.DELIVERED, inspector,
                         CustodyStage.FACTORY_RECEIVE, weight_kg=received, note=f"QC lot {lot_code}",
                         received_by_id=inspector.id, delivered_at=now,
                         gross_weight=gross_kg, tare_weight=tare_kg, net_weight=net_kg,
                         weighbridge_slip_url=slip_url,
                         **shrinkage_fields(ref, received))


def qc_dict(q: InboundQC) -> dict:
    return {"id": q.id, "request_id": q.request_id, "net_kg": q.net_kg, "payable_kg": round(q.payable_kg, 2),
            "rejected_kg": round(q.rejected_kg or 0.0, 2),
            "refraction_kg": round(q.refraction_kg or 0.0, 2), "dry_basis_kg": q.dry_basis_kg,
            "remaining_kg": round(q.remaining_kg, 2), "moisture": q.moisture, "ash": q.ash,
            "contamination": q.contamination, "grade": q.grade, "score": q.score, "decision": _v(q.decision),
            "final_price_per_kg": q.final_price_per_kg, "total_payment_rp": q.total_payment_rp,
            "verification_code": q.verification_code, "evidence_photo_url": q.evidence_photo_url,
            "created_at": q.created_at.isoformat() if q.created_at else None}


async def create_batch(db: AsyncSession, operator: User, data: dict) -> ManufacturingBatch:
    """Catat batch: konsumsi lot QC (atomik), output 3 produk, loss, biaya → mass balance & unit economics."""
    if not data["inputs"]:
        raise ValueError("Minimal satu lot input.")
    lots, input_kg, raw_cost, w_moist, w_ash = [], 0.0, 0.0, 0.0, 0.0
    for it in data["inputs"]:
        res = await db.execute(update(InboundQC)
                               .where(InboundQC.id == it["qc_id"], InboundQC.remaining_kg >= it["kg"] - 1e-9,
                                      InboundQC.decision != QCDecision.REJECT)
                               .values(remaining_kg=InboundQC.remaining_kg - it["kg"])
                               .execution_options(synchronize_session=False))
        if res.rowcount != 1:
            raise TransitionConflict(f"Lot QC #{it['qc_id']} tidak ada, ditolak, atau stoknya kurang dari {it['kg']:g} kg.")
        lot = await db.get(InboundQC, it["qc_id"])
        lots.append((lot, it["kg"]))
        input_kg += it["kg"]
        raw_cost += it["kg"] * lot.final_price_per_kg * (lot.payable_kg / lot.net_kg if lot.net_kg else 1)
        w_moist += it["kg"] * lot.moisture
        w_ash += it["kg"] * lot.ash
    moisture, ash = w_moist / input_kg, w_ash / input_kg

    outputs = {p: float(data["outputs"].get(p, 0.0)) for p in PRODUCTS}
    losses = {k: float(data.get("losses", {}).get(k, 0.0)) for k in LOSS_KINDS}
    costs = data.get("costs", [])
    joint = raw_cost + sum(c["amount_rp"] for c in costs if not c.get("product"))
    separable = {p: sum(c["amount_rp"] for c in costs if c.get("product") == p) for p in PRODUCTS}
    eco = batch_economics(input_kg, outputs, losses, joint, separable, data.get("operating_hours"),
                          price_overrides=data.get("prices"))

    # Varians rendemen: aktual vs model (Engine ⑪ dengan kadar air/abu rata-rata lot)
    s_p = P("pabrik.pellet_share") if data.get("pellet_share") is None else data["pellet_share"]
    s_s = (P("pabrik.silica_share_of_biochar") if data.get("silica_share_of_biochar") is None
           else data["silica_share_of_biochar"])
    route = data.get("silica_route") or P("pabrik.silica_route")
    s_x = P("pabrik.silica_husk_share") if data.get("silica_husk_share") is None else data["silica_husk_share"]
    model = process_yields(moisture, ash, data.get("pyrolysis_temp_c"), s_p, s_s, route, s_x)
    eco["yield_variance"] = {p: {"model_kg": round(model.outputs[p] * input_kg, 1), "actual_kg": outputs[p],
                                 "variance_pct": round((outputs[p] / (model.outputs[p] * input_kg) - 1) * 100, 1)
                                 if model.outputs[p] > 0 else None} for p in PRODUCTS}
    eco["input_quality"] = {"moisture_avg": round(moisture, 2), "ash_avg": round(ash, 2),
                            "raw_material_cost_rp": round(raw_cost)}
    eco["parameters_snapshot"] = {k: P(k) for k in ("pabrik.price_pellet_per_kg", "pabrik.price_biochar_per_kg",
                                                    "pabrik.price_silica_per_kg", "pabrik.joint_cost_method",
                                                    "pabrik.closure_tolerance_pct")}

    batch = ManufacturingBatch(
        batch_code=data["batch_code"], operating_hours=data.get("operating_hours"),
        pyrolysis_temp_c=data.get("pyrolysis_temp_c"), pellet_share=s_p, silica_share_of_biochar=s_s,
        silica_route=route, silica_husk_share=s_x if route != "biochar" else 0.0,
        input_kg=input_kg, closure_error_pct=eco["mass_balance"]["closure_error_pct"],
        closure_ok=int(eco["mass_balance"]["closure_ok"]), economics=eco, operator_id=operator.id,
        note=data.get("note"), started_at=datetime.now(timezone.utc))
    db.add(batch)
    await db.flush()
    for lot, kg in lots:
        db.add(BatchInput(batch_id=batch.id, qc_id=lot.id, input_kg=kg, moisture=lot.moisture))
    for p, kg in outputs.items():
        exp = model.outputs[p] * input_kg
        db.add(BatchOutput(batch_id=batch.id, product=p, quantity_kg=kg, quality=data.get("quality", {}).get(p),
                           expected_kg=round(exp, 3), yield_pct=round(100 * kg / input_kg, 3),
                           yield_variance_pct=round((kg / exp - 1) * 100, 2) if exp > 0 else None))
        if kg > 0:
            db.add(FinishedGoodsMovement(product=p, movement="produksi", quantity_kg=kg, batch_id=batch.id,
                                         reference=batch.batch_code, actor_id=operator.id))
    for k, kg in losses.items():
        db.add(BatchLoss(batch_id=batch.id, kind=k, quantity_kg=kg))
    db.add(BatchCost(batch_id=batch.id, cost_type="variabel", item="bahan_baku_sekam", driver_qty=input_kg,
                     driver_unit="kg", rate=raw_cost / input_kg, amount_rp=raw_cost))
    for c in costs:
        db.add(BatchCost(batch_id=batch.id, cost_type=c.get("cost_type", "variabel"), item=c["item"],
                         driver_qty=c.get("driver_qty"), driver_unit=c.get("driver_unit"), rate=c.get("rate"),
                         amount_rp=c["amount_rp"], product=c.get("product")))
    await db.flush()
    eco["wallet"] = await _allocate_biochar_to_wallets(db, operator, batch, lots, input_kg, outputs["biochar"])
    if eco["wallet"]["allocated_kg"] > 0:     # biochar milik dompet petani keluar dari stok jual pabrik
        db.add(FinishedGoodsMovement(product="biochar", movement="alokasi_petani",
                                     quantity_kg=-eco["wallet"]["allocated_kg"], batch_id=batch.id,
                                     reference=batch.batch_code, actor_id=operator.id,
                                     note="Porsi sirkular dikembalikan ke dompet biochar petani"))
    batch.economics = {**eco}                      # simpan ringkasan alokasi di snapshot batch
    await db.flush()
    return batch


async def _allocate_biochar_to_wallets(db, operator: User, batch: ManufacturingBatch, lots, input_kg: float,
                                       biochar_kg: float) -> dict:
    """Kreditkan biochar batch ke dompet petani yang sekamnya ikut diolah — proporsional berat diterima
    pabrik per harvest, tepat sampai gram (largest remainder). Bagian dari sekam yang tidak tertelusur ke
    petani (stok pengepul sendiri) dilaporkan, tidak dibagikan."""
    share = P("sirkular.farmer_return_share")
    pool_g = round(biochar_kg * share * 1000)
    buckets: list[tuple[Harvest | None, float]] = []
    # Batch-load all linked harvests across lots in a single query (eliminates N+1 query)
    request_ids = list({lot.request_id for lot, _ in lots if lot.request_id is not None})
    harvests_by_req: dict[int, list[Harvest]] = {rid: [] for rid in request_ids}
    if request_ids:
        all_linked = (await db.execute(
            select(Harvest)
            .where(Harvest.delivery_request_id.in_(request_ids), Harvest.received_kg.is_not(None))
            .execution_options(populate_existing=True)
        )).scalars().all()
        for h in all_linked:
            if h.delivery_request_id in harvests_by_req:
                harvests_by_req[h.delivery_request_id].append(h)

    for lot, kg_used in lots:
        linked = harvests_by_req.get(lot.request_id, [])
        traced = sum(h.received_kg for h in linked)
        frac_used = kg_used / lot.net_kg if lot.net_kg else 0.0
        for h in linked:
            buckets.append((h, h.received_kg * frac_used))
        buckets.append((None, max(0.0, lot.net_kg - traced) * frac_used))
    weights = [w for _, w in buckets]
    if pool_g <= 0 or sum(weights) <= 0:
        return {"allocated_kg": 0.0, "untraceable_kg": round(biochar_kg * share, 3), "farmers": []}
    grams = allocate_grams(pool_g, weights)
    per_farmer: dict[int, float] = {}
    untraceable_g = 0
    for (h, w), g in zip(buckets, grams):
        if h is None:
            untraceable_g += g
            continue
        if g > 0:
            db.add(BiocharLedgerEntry(farmer_id=h.farmer_id, batch_id=batch.id, harvest_id=h.id,
                                      entry_type="allocation", amount_kg=g / 1000, created_by_id=operator.id,
                                      note=f"Batch {batch.batch_code}: {w:,.1f} kg sekam × {biochar_kg:g} kg biochar "
                                           f"÷ {input_kg:,.0f} kg input × porsi {share:g}"))
            per_farmer[h.farmer_id] = per_farmer.get(h.farmer_id, 0) + g
        if _v(h.status) == HarvestStatus.DELIVERED.value:          # pertama kali diolah → CONVERTED
            await transition(db, h.id, HarvestStatus.DELIVERED, HarvestStatus.CONVERTED, operator,
                             CustodyStage.CONVERSION, weight_kg=round(w, 3), note=f"Batch {batch.batch_code}")
    await db.flush()
    return {"allocated_kg": round(sum(per_farmer.values()) / 1000, 3), "untraceable_kg": round(untraceable_g / 1000, 3),
            "return_share": share,
            "farmers": [{"farmer_id": f, "biochar_kg": g / 1000} for f, g in sorted(per_farmer.items())],
            "method": "biochar × porsi petani × (kg sekam petani dalam batch ÷ kg input), largest remainder per gram"}


def batch_dict(b: ManufacturingBatch) -> dict:
    return {"id": b.id, "batch_code": b.batch_code, "input_kg": b.input_kg, "closure_error_pct": b.closure_error_pct,
            "closure_ok": bool(b.closure_ok), "pellet_share": b.pellet_share,
            "silica_share_of_biochar": b.silica_share_of_biochar, "economics": b.economics,
            "created_at": b.created_at.isoformat() if b.created_at else None}


# ---------------------------------------------------------------- pembayaran pabrik → pengepul (kedua jalur)
def settlement_dict(s) -> dict:
    return {"id": s.id, "collector_id": s.collector_id, "source": s.source, "qc_id": s.qc_id, "harvest_id": s.harvest_id,
            "payable_kg": round(s.payable_kg, 2), "moisture": s.moisture, "price_per_kg": s.price_per_kg,
            "amount_rp": s.amount_rp, "price_basis": s.price_basis, "status": _v(s.status),
            "payment_reference": s.payment_reference,
            **({"deducted_rp": s.deducted_rp, "net_transfer_rp": s.net_transfer_rp} if hasattr(s, "deducted_rp") else {}),
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "paid_at": s.paid_at.isoformat() if s.paid_at else None}


async def settle_qc(db: AsyncSession, qc: InboundQC, collector_id: int, actor: User):
    """Jalur QC: harga kontrak (sudah disetarakan basis kering) × kg terbayar → langsung terutang."""
    if _v(qc.decision) == QCDecision.REJECT.value:
        return None
    s = CollectorSettlement(collector_id=collector_id, source="qc", qc_id=qc.id, payable_kg=qc.payable_kg,
                            moisture=qc.moisture, price_per_kg=qc.final_price_per_kg, amount_rp=qc.total_payment_rp,
                            price_basis="harga kontrak Delivery Request, disetarakan basis kering saat QC",
                            status=SettlementStatus.PAYABLE, created_by_id=actor.id,
                            priced_at=datetime.now(timezone.utc))
    db.add(s)
    await db.flush()
    ev = SettlementEvent(settlement_id=s.id, action="dibuat", old_price=None, new_price=qc.final_price_per_kg,
                         old_amount=None, new_amount=qc.total_payment_rp,
                         reason="Jalur QC: harga kontrak disetarakan mutu inbound", actor_id=actor.id)
    db.add(ev)
    await db.flush()
    return s


async def settle_route(db: AsyncSession, harvest: Harvest, actor: User, price_override: float | None = None):
    """Jalur rute armada pabrik: kewajiban bayar ke pengepul atas berat diterima pabrik (kontaminan tidak dibayar).
    Harga: isian pabrik > rekomendasi netback engine (kadar air/abu timbangan pengepul) > 'menunggu harga'."""
    if harvest.collector_id is None or harvest.received_kg is None:
        return None
    kg = harvest.received_kg * (1 - (harvest.contamination or 0) / 100)
    now = datetime.now(timezone.utc)
    used_moisture = harvest.moisture if harvest.moisture is not None else P("pabrik.reference_moisture_pct")
    is_ref_moisture = harvest.moisture is None
    used_ash = harvest.ash if harvest.ash is not None else P("rendemen.ref_ash")
    ref_suffix = " (kadar air referensi)" if is_ref_moisture else ""
    if price_override is not None:
        price, basis = price_override, "harga diisi pabrik saat timbang terima"
    else:
        from ..engines.factory_econ import PriceMissing
        try:
            r = recommend_price(PricingRequest(moisture=used_moisture, ash=used_ash, sensitivity=False))
            if r["accept"]:
                price = r["target_per_kg"]
                basis = f"rekomendasi netback (target) untuk kadar air {used_moisture}%{ref_suffix} — menu Parameter"
            else:
                price = None
                basis = f"di luar batas mutu (kadar air {used_moisture}%{ref_suffix}) — perlu keputusan harga manual"
        except PriceMissing:
            price, basis = None, "menunggu harga: harga jual produk belum diisi di menu Parameter"

    status = SettlementStatus.PENDING_PRICE if price is None else SettlementStatus.PAYABLE
    amount_rp = None if price is None else round(kg * price)
    s = CollectorSettlement(
        collector_id=harvest.collector_id, source="rute", harvest_id=harvest.id, payable_kg=kg,
        moisture=used_moisture, price_per_kg=price, amount_rp=amount_rp,
        price_basis=basis, status=status,
        created_by_id=actor.id, priced_at=None if price is None else now)
    db.add(s)
    await db.flush()
    ev = SettlementEvent(settlement_id=s.id, action="dibuat", old_price=None, new_price=price,
                         old_amount=None, new_amount=amount_rp, reason=basis, actor_id=actor.id)
    db.add(ev)
    await db.flush()
    return s


async def set_settlement_price(db: AsyncSession, settlement_id: int, price: float, actor: User, reason: str):
    """Tetapkan/koreksi harga sebelum dibayar (CAS: yang sudah dibayar tidak dapat diubah)."""
    s = await db.get(CollectorSettlement, settlement_id)
    if s is None:
        raise LookupError("Catatan pembayaran tidak ditemukan")
    old_price = s.price_per_kg
    old_amount = s.amount_rp
    new_amount = round(s.payable_kg * price)
    res = await db.execute(update(CollectorSettlement)
                           .where(CollectorSettlement.id == settlement_id,
                                  CollectorSettlement.status.in_([SettlementStatus.PENDING_PRICE, SettlementStatus.PAYABLE]))
                           .values(price_per_kg=price, amount_rp=new_amount,
                                   status=SettlementStatus.PAYABLE, priced_at=datetime.now(timezone.utc),
                                   price_basis=f"ditetapkan {actor.full_name}: {reason}")
                           .execution_options(synchronize_session=False))
    if res.rowcount != 1:
        raise TransitionConflict("Pembayaran sudah lunas — harga tidak dapat diubah.")
    ev = SettlementEvent(settlement_id=settlement_id, action="harga", old_price=old_price, new_price=price,
                         old_amount=old_amount, new_amount=new_amount, reason=reason, actor_id=actor.id)
    db.add(ev)
    await db.flush()
    return await db.get(CollectorSettlement, settlement_id, populate_existing=True)


async def mark_settlement_paid(db: AsyncSession, settlement_id: int, reference: str, actor: User | None = None):
    s = await db.get(CollectorSettlement, settlement_id)
    if s is None:
        raise LookupError("Catatan pembayaran tidak ditemukan")
    res = await db.execute(update(CollectorSettlement)
                           .where(CollectorSettlement.id == settlement_id,
                                  CollectorSettlement.status == SettlementStatus.PAYABLE)
                           .values(status=SettlementStatus.PAID, payment_reference=reference,
                                   paid_at=datetime.now(timezone.utc))
                           .execution_options(synchronize_session=False))
    if res.rowcount != 1:
        raise TransitionConflict("Hanya pembayaran berstatus 'terutang' yang dapat ditandai lunas "
                                 "(harga harus ditetapkan dulu; tidak bisa dibayar dua kali).")
    actor_id = actor.id if actor else s.created_by_id
    # Potongan logistik terbuka milik pengepul ini (ongkos jarak kosong) dipotong dari pembayaran ini, sebatas nilainya
    from ..models.factory_ops import LogisticsCharge
    open_ch = (await db.execute(select(LogisticsCharge).where(LogisticsCharge.collector_id == s.collector_id,
                                                              LogisticsCharge.status == "terbuka")
                                .order_by(LogisticsCharge.id).with_for_update())).scalars().all()
    room, deducted, now = float(s.amount_rp or 0), 0.0, datetime.now(timezone.utc)
    for c in open_ch:
        amt = float(c.amount_rp)
        if amt > room + 1e-6:
            break
        c.status, c.settlement_id, c.resolved_at = "dipotong", settlement_id, now
        room -= amt
        deducted += amt
    ev = SettlementEvent(settlement_id=settlement_id, action="dibayar", old_price=s.price_per_kg,
                         new_price=s.price_per_kg, old_amount=s.amount_rp, new_amount=s.amount_rp,
                         reason=f"Lunas transfer ref: {reference}"
                                + (f" · dipotong ongkos logistik Rp{deducted:,.0f} → transfer Rp{(s.amount_rp or 0) - deducted:,.0f}"
                                   if deducted else ""), actor_id=actor_id)
    db.add(ev)
    await db.flush()
    out = await db.get(CollectorSettlement, settlement_id, populate_existing=True)
    out.deducted_rp, out.net_transfer_rp = round(deducted), round((out.amount_rp or 0) - deducted)
    return out


def settlement_event_dict(e: SettlementEvent, actor_name: str | None = None) -> dict:
    return {
        "id": e.id, "settlement_id": e.settlement_id, "action": e.action,
        "old_price": e.old_price, "new_price": e.new_price,
        "old_amount": e.old_amount, "new_amount": e.new_amount,
        "reason": e.reason, "actor_id": e.actor_id, "actor_name": actor_name,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


async def settlement_history(db: AsyncSession, settlement_id: int) -> list[dict]:
    q = (select(SettlementEvent, User.full_name)
         .outerjoin(User, User.id == SettlementEvent.actor_id)
         .where(SettlementEvent.settlement_id == settlement_id)
         .order_by(SettlementEvent.id.asc()))
    rows = (await db.execute(q)).all()
    return [settlement_event_dict(ev, actor_name=name) for ev, name in rows]



# ---------------------------------------------------------------- stok produk jadi (biochar, bio-silika, pellet)
async def inventory_balance(db: AsyncSession) -> dict:
    rows = (await db.execute(select(FinishedGoodsMovement.product, func.sum(FinishedGoodsMovement.quantity_kg))
                             .group_by(FinishedGoodsMovement.product))).all()
    bal = {p: 0.0 for p in PRODUCTS}
    bal.update({p: round(float(kg or 0), 3) for p, kg in rows})
    return bal


async def record_goods_movement(db: AsyncSession, actor: User, product: str, movement: str, quantity_kg: float,
                                unit_price_rp: float | None, reference: str | None, note: str | None):
    """Keluar/masuk stok produk jadi. Keluar tidak boleh membuat saldo negatif; dua penjualan serentak
    diserialkan dengan advisory lock per produk (PostgreSQL) / writer tunggal (SQLite)."""
    if product not in PRODUCTS:
        raise ValueError("Produk hanya bio_pellet / biochar / bio_silika")
    sign = -1 if movement == "penjualan" else 1
    qty = sign * abs(quantity_kg) if movement in ("penjualan", "retur_pelanggan") else quantity_kg
    if db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"fg:{product}"})
    bal = (await inventory_balance(db))[product]
    if bal + qty < -1e-9:
        raise TransitionConflict(f"Stok {product} hanya {bal:g} kg; tidak cukup untuk {abs(qty):g} kg.")
    m = FinishedGoodsMovement(product=product, movement=movement, quantity_kg=qty, unit_price_rp=unit_price_rp,
                              reference=reference, note=note, actor_id=actor.id)
    db.add(m)
    await db.flush()
    if qty < 0 and db.bind.dialect.name != "postgresql":
        # SQLite: tidak ada advisory lock & cek awal bisa lolos serentak → periksa ulang setelah tulis (transaksi sama)
        after = (await inventory_balance(db))[product]
        if after < -1e-9:
            await db.rollback()
            raise TransitionConflict(f"Stok {product} tidak cukup (diambil transaksi lain bersamaan).")
    return {"id": m.id, "product": product, "movement": movement, "quantity_kg": qty,
            "balance_kg": round(bal + qty, 3)}
