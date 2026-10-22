"""Laporan ESG pabrik biochar — dari data operasional NYATA, disusun mengikuti docs/09_RISET_STANDAR_ESG_BIOCHAR.md.

Prinsip pelaporan (GRI 102/103 2027, GHG Protocol LSR, IFRS S2 / PSPK 2 berlaku 1 Jan 2027):
  * emisi bruto, penyimpanan karbon (removal) dan emisi yang DIHINDARI dilaporkan TERPISAH — tidak saling dikurangi;
  * angka karbon adalah estimasi internal sampai diverifikasi pihak ketiga (Puro / VM0044 / Global C-Sink);
  * setiap KPI menyebut rumus, sumber tabel, dan rujukan standar.
Pabrik kecil tidak wajib POJK 51/2017, tetapi struktur Lampiran II-nya dipakai pembeli & bank.
"""

from datetime import datetime, timezone
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..engines.green_scorecard import scorecard
from ..models.circular import BiocharRedemption
from ..models.compliance import Consent, DataRequest, FarmerPayment
from ..models.conversion import CarbonCredit
from ..models.factory_ops import (BatchCost, BatchLoss, BatchOutput, FinishedGoodsMovement, InboundQC,
                                  ManufacturingBatch, ReturnCase)
from ..models.harvest import Harvest, HarvestStatus
from ..models.ledger import CustodyEvent
from ..models.params import ParameterChange
from ..models.route import Route, RouteStatus
from ..models.user import User, UserRole
from ..params import P


def _v(e):
    return e.value if hasattr(e, "value") else e


def _aware(d):
    return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)


def _between(col, start, end):
    conds = []
    if start is not None:
        conds.append(col >= start)
    if end is not None:
        conds.append(col < end)
    return conds


async def scorecard_inputs(db: AsyncSession, start: datetime | None, end: datetime | None = None) -> dict:
    """Kumpulkan batch, rute, retur & sekam diterima pada periode → argumen engine green_scorecard."""
    batches = (await db.execute(select(ManufacturingBatch).where(*_between(ManufacturingBatch.created_at, start, end))
                                )).scalars().all()
    ids = [b.id for b in batches]
    outs, losses, kwh = {}, {}, {}
    if ids:
        for o in (await db.execute(select(BatchOutput).where(BatchOutput.batch_id.in_(ids)))).scalars():
            outs.setdefault(o.batch_id, {})[o.product] = o.quantity_kg
        for lo in (await db.execute(select(BatchLoss).where(BatchLoss.batch_id.in_(ids)))).scalars():
            losses.setdefault(lo.batch_id, {})[lo.kind] = lo.quantity_kg
        for c in (await db.execute(select(BatchCost).where(BatchCost.batch_id.in_(ids)))).scalars():
            if (c.driver_unit or "").lower() == "kwh" and c.driver_qty:
                kwh[c.batch_id] = kwh.get(c.batch_id, 0) + c.driver_qty
    rows = [{"input_kg": b.input_kg, "moisture": (b.economics or {}).get("input_quality", {}).get("moisture_avg"),
             "ash": (b.economics or {}).get("input_quality", {}).get("ash_avg"), "temp_c": b.pyrolysis_temp_c,
             "outputs": outs.get(b.id, {}), "losses": losses.get(b.id, {}), "kwh": kwh.get(b.id)} for b in batches]
    route_objs = (await db.execute(select(Route).where(Route.status == RouteStatus.COMPLETED,
                                                       *_between(Route.completed_at, start, end)))).scalars().all()
    routes = [{"co2e_wtw_kg": r.co2e_wtw_kg, "distance_source": (r.emission_detail or {}).get("distance_source")}
              for r in route_objs]
    returns = [{"quantity_kg": r.quantity_kg, "status": r.status, "disposition": _v(r.disposition)}
               for r in (await db.execute(select(ReturnCase).where(*_between(ReturnCase.created_at, start, end)))).scalars()]
    recv = float((await db.execute(select(func.coalesce(func.sum(Harvest.received_kg), 0.0))
                                   .where(Harvest.received_kg.is_not(None), *_between(Harvest.delivered_at, start, end)))).scalar() or 0)
    qc = float((await db.execute(select(func.coalesce(func.sum(InboundQC.net_kg), 0.0))
                                 .where(InboundQC.decision != "tolak", *_between(InboundQC.created_at, start, end)))).scalar() or 0)
    to_farmers = -float((await db.execute(select(func.coalesce(func.sum(FinishedGoodsMovement.quantity_kg), 0.0))
                                          .where(FinishedGoodsMovement.movement == "alokasi_petani",
                                                 *_between(FinishedGoodsMovement.created_at, start, end)))).scalar() or 0)
    return {"batches": rows, "routes": routes, "route_objs": route_objs, "returns": returns,
            "received_kg": recv + qc, "biochar_to_farmers_kg": to_farmers}


async def green_scorecard_for(db: AsyncSession, start: datetime | None, end: datetime | None = None) -> dict:
    d = await scorecard_inputs(db, start, end)
    return scorecard(d["batches"], d["routes"], d["returns"], d["received_kg"], d["biochar_to_farmers_kg"])


def _kpi(code, name, value, unit, formula, standard, source, note=None):
    return {"code": code, "name": name, "value": value, "unit": unit, "formula": formula, "standard": standard,
            "source": source, **({"note": note} if note else {})}


def _r(x, n=2):
    return round(x, n) if x is not None else None


async def esg_report(db: AsyncSession, start: datetime, end: datetime, label: str) -> dict:
    from .efficiency import efficiency_overview
    d = await scorecard_inputs(db, start, end)
    sc = scorecard(d["batches"], d["routes"], d["returns"], d["received_kg"], d["biochar_to_farmers_kg"])
    c = sc["carbon_tco2e"]
    husk_t = sum(b["input_kg"] for b in d["batches"]) / 1000
    biochar_t = sum(b["outputs"].get("biochar", 0) for b in d["batches"]) / 1000
    outputs_t = sum(sum(b["outputs"].values()) for b in d["batches"]) / 1000
    kwh = sum(b.get("kwh") or 0 for b in d["batches"])
    scope2 = kwh * P("karbon.grid_ef_kg_co2_per_kwh") / 1000
    scope3 = sum(r.get("co2e_wtw_kg") or 0 for r in d["routes"]) / 1000
    fc = P("karbon.biochar_c_org_fraction")
    gross_c = biochar_t * fc * 44 / 12
    durable = c["biochar_sequestration"]
    project_em = scope2 + scope3
    received_t = d["received_kg"] / 1000
    waste_t = sum(sum(b["losses"].values()) for b in d["batches"]) / 1000
    credits = (await db.execute(select(func.coalesce(func.sum(CarbonCredit.emission_avoided_tco2), 0.0))
                                .where(*_between(CarbonCredit.created_at, start, end)))).scalar() or 0

    env = [
        _kpi("E1", "Sekam diterima", _r(received_t), "t", "Σ timbang pabrik (harvest diterima + QC lolos)",
             "POJK 51 Lamp. II; GRI 301-1", "harvests.received_kg, inbound_qc.net_kg"),
        _kpi("E2", "Sekam diolah", _r(husk_t), "t", "Σ input batch", "GRI 301-1", "manufacturing_batches.input_kg"),
        _kpi("E3", "Rendemen produk (valorisasi massa)", sc["circularity"]["mass_valorization_pct"], "%",
             "Σ output ÷ Σ input batch", "GRI 301-1; Puro §6.1", "batch_outputs / batch_inputs"),
        _kpi("E4", "Listrik proses", _r(kwh, 1), "kWh", "Σ kWh biaya batch", "GRI 302-1", "batch_costs (driver kWh)"),
        _kpi("E5", "Intensitas listrik", _r(kwh / biochar_t, 1) if biochar_t else None, "kWh/t biochar",
             "E4 ÷ t biochar", "GRI 302-3", "batch_costs, batch_outputs"),
        _kpi("E6", "Emisi Scope 2 (listrik)", _r(scope2, 3), "tCO₂e", "kWh × faktor grid", "GRI 305-2; IFRS S2 ¶29(a)",
             "parameter karbon.grid_ef_kg_co2_per_kwh"),
        _kpi("E7", "Emisi Scope 3 kat.4 (angkut masuk)", _r(scope3, 3), "tCO₂e", "Σ CO₂e WTW rute selesai (ISO 14083)",
             "GHG Protocol Scope 3 kat.4; GRI 305-3", "routes.co2e_wtw_kg"),
        _kpi("E8", "Intensitas emisi per t sekam", _r((scope2 + scope3) * 1000 / husk_t, 1) if husk_t else None,
             "kgCO₂e/t sekam", "(E6+E7) ÷ E2", "GRI 305-4", "turunan"),
        _kpi("E9", "Karbon tersimpan bruto di biochar", _r(gross_c, 3), "tCO₂e", "t biochar × F_C × 44/12",
             "Puro Biochar Methodology 2025 v2 Eq.5.1", "batch_outputs; karbon.biochar_c_org_fraction",
             "Sekam berabu tinggi: C-organik wajib diukur lab sebelum klaim."),
        _kpi("E10", "Penyimpanan karbon tahan lama (removal)", _r(durable, 3), "tCO₂e", "E9 × F_perm(suhu) — IPCC 2019",
             "IPCC 2019 Ref. Vol.4 Ap.4; GRI 102-9 (2027)", "engines/green_scorecard.py"),
        _kpi("E11", "Removal bersih (removal − emisi proyek)", _r(durable - project_em, 3), "tCO₂e",
             "E10 − (E6 + E7)", "Puro Eq.5.1; GHG Protocol LSR", "turunan",
             "Indikasi internal; belum termasuk kebocoran & emisi Scope 1 BBM pabrik."),
        _kpi("E12", "Emisi DIHINDARI (pembakaran terbuka)", c["avoided_open_burning"], "tCO₂e",
             "t sekam kering × porsi dibakar × CF × (EF_CH4·GWP + EF_N2O·GWP)", "GRI 305-5; IFRS S2 ¶36",
             "engines/green_scorecard.py", "Dilaporkan terpisah — TIDAK boleh mengurangi emisi bruto."),
        _kpi("E13", "Emisi dihindari tercatat (kredit internal)", _r(credits, 3), "tCO₂e", "Σ carbon_credits",
             "GRI 305-5", "carbon_credits", "Status: estimasi internal, belum terdaftar SRN-PPI."),
        _kpi("E14", "Residu & susut proses", _r(waste_t, 3), "t", "Σ batch_losses", "GRI 306-3", "batch_losses"),
        _kpi("E15", "Laju retur sekam", sc["circularity"]["return_rate_pct"], "%", "retur ÷ (diterima + retur)",
             "GRI 306 (proxy)", "return_cases"),
        _kpi("E16", "Biochar kembali ke lahan petani", sc["circularity"]["biochar_returned_to_farmers_pct"], "% biochar",
             "alokasi petani ÷ biochar diproduksi", "Ellen MacArthur MCI (proxy)", "finished_goods_movements"),
    ]

    # ---------------- Sosial
    farmers = (await db.execute(select(func.count(func.distinct(Harvest.farmer_id)))
                                .where(*_between(Harvest.reported_at, start, end)))).scalar() or 0
    pays = (await db.execute(select(FarmerPayment, Harvest.verified_at).join(Harvest, Harvest.id == FarmerPayment.harvest_id)
                             .where(*_between(FarmerPayment.paid_at, start, end)))).all()
    due = int(P("pasar.farmer_payment_due_days") or 0)
    days = [(_aware(p.paid_at) - _aware(v)).total_seconds() / 86400 for p, v in pays if v is not None and p.paid_at]
    on_time = sum(1 for x in days if x <= due + 1e-9)
    assessed = (await db.execute(select(Harvest).where(
        Harvest.status != HarvestStatus.REPORTED,
        (Harvest.verified_at.is_not(None) & Harvest.verified_at.between(start, end))
        | (Harvest.rejected_at.is_not(None) & Harvest.rejected_at.between(start, end))))).scalars().all()
    rejected = [h for h in assessed if _v(h.status) == HarvestStatus.REJECTED.value and h.reject_category != "dibatalkan_pengepul"]
    by_cat = {}
    for h in rejected:
        by_cat[h.reject_category or "lainnya"] = by_cat.get(h.reject_category or "lainnya", 0) + 1
    shr = [h for h in assessed if h.shrinkage_kg is not None and h.verified_kg]
    redeemed = float((await db.execute(select(func.coalesce(func.sum(BiocharRedemption.kg), 0.0))
                                       .where(BiocharRedemption.status == "diserahkan",
                                              *_between(BiocharRedemption.handed_over_at, start, end)))).scalar() or 0)
    soc = [
        _kpi("S1", "Petani pemasok aktif", farmers, "petani", "petani berbeda yang melapor stok", "GRI 2-6",
             "harvests.farmer_id"),
        _kpi("S2", "Pembayaran ke petani", int(sum(p.net_rp for p, _ in pays)), "Rp", "Σ kuitansi BYR bersih",
             "GRI 201-1 / 204", "farmer_payments"),
        _kpi("S3", "Pembayaran tepat waktu", _r(on_time / len(days) * 100, 1) if days else None, "%",
             f"lot dibayar ≤ {due} hari setelah ditimbang ÷ lot dibayar", "GRI 204 (praktik pengadaan)",
             "farmer_payments.paid_at − harvests.verified_at"),
        _kpi("S4", "Median hari hingga dibayar", _r(median(days), 1) if days else None, "hari", "median(paid − verified)",
             "GRI 204", "farmer_payments"),
        _kpi("S5", "Defect / reject rate lot petani", _r(len(rejected) / len(assessed) * 100, 1) if assessed else None, "%",
             "lot ditolak ÷ lot dinilai (tanpa batal sepihak pengepul)", "GRI 308-2 (proxy)", "harvests.reject_category",
             "Penyebab: " + (", ".join(f"{k} {v}" for k, v in sorted(by_cat.items(), key=lambda x: -x[1])) or "–")),
        _kpi("S6", "Susut timbang pengepul→pabrik", _r(sum(h.shrinkage_kg for h in shr) / sum(h.verified_kg for h in shr) * 100, 2)
             if shr else None, "%", "Σ susut ÷ Σ timbang pengepul", "integritas rantai pasok", "harvests.shrinkage_kg"),
        _kpi("S7", "Biochar diserahkan ke sawah petani", _r(redeemed, 1), "kg", "Σ pengambilan diserahkan",
             "ekonomi sirkular (komunitas, GRI 413 proxy)", "biochar_redemptions"),
    ]

    # ---------------- Tata kelola
    petani_total = (await db.execute(select(func.count(User.id)).where(User.role == UserRole.PETANI,
                                                                       User.anonymized_at.is_(None)))).scalar() or 0
    consented = (await db.execute(select(func.count(func.distinct(Consent.user_id))).join(User, User.id == Consent.user_id)
                                  .where(User.role == UserRole.PETANI, Consent.granted.is_(True)))).scalar() or 0
    dreq = (await db.execute(select(func.count(DataRequest.id)).where(*_between(DataRequest.created_at, start, end)))).scalar() or 0
    traced_total = (await db.execute(select(func.count(Harvest.id)).where(*_between(Harvest.reported_at, start, end)))).scalar() or 0
    traced = (await db.execute(select(func.count(func.distinct(CustodyEvent.harvest_id))).join(Harvest, Harvest.id == CustodyEvent.harvest_id)
                               .where(*_between(Harvest.reported_at, start, end)))).scalar() or 0
    pchg = (await db.execute(select(func.count(ParameterChange.id)).where(*_between(ParameterChange.created_at, start, end)))).scalar() or 0
    gov = [
        _kpi("G1", "Cakupan persetujuan data petani", _r(consented / petani_total * 100, 1) if petani_total else None, "%",
             "petani dengan persetujuan aktif ÷ petani aktif", "UU 27/2022 PDP Ps.20–22", "consents"),
        _kpi("G2", "Permintaan hak subjek data dipenuhi", dreq, "permintaan", "ekspor/hapus data selesai",
             "UU PDP Ps.5–11; GRI 418 (proxy)", "data_requests"),
        _kpi("G3", "Insiden kebocoran data", None, "insiden", "log insiden", "GRI 418-1; UU PDP Ps.46", "—",
             "Belum ada log insiden di sistem — catat manual hingga modul insiden dibuat."),
        _kpi("G4", "Keterlacakan lot (chain of custody)", _r(traced / traced_total * 100, 1) if traced_total else None, "%",
             "lot dengan jejak custody ÷ lot dilaporkan", "Puro §3.8; ISO 22095", "custody_events"),
        _kpi("G5", "Perubahan parameter teraudit", pchg, "perubahan", "setiap perubahan asumsi wajib alasan",
             "IFRS S1 (pertimbangan & estimasi)", "parameter_changes"),
        _kpi("G6", "Status verifikasi karbon", "estimasi internal", "", "belum diverifikasi pihak ketiga",
             "Perpres 110/2025 (SRN-PPI); Puro / VM0044 / Global C-Sink", "—"),
    ]
    eff = await efficiency_overview(db, start, end)
    return {
        "title": "Laporan ESG — Pabrik Pirolisis Biochar", "period": label,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": env, "social": soc, "governance": gov,
        "efficiency": {"realized": eff["realized_totals"], "recorded": eff["recorded_totals"],
                       "potential": eff["potential_totals"]},
        "carbon_presentation": {
            "gross_emissions_tco2e": _r(project_em, 3), "removals_durable_tco2e": _r(durable, 3),
            "avoided_tco2e": c["avoided_open_burning"],
            "rule": "Dilaporkan terpisah (GRI 102/103, GHG Protocol LSR, IFRS S2); emisi dihindari tidak mengurangi emisi bruto.",
        },
        "limitations": [
            "Scope 1 (BBM forklift/genset pabrik) dan CO₂ biogenik syngas belum dicatat.",
            "C-organik biochar memakai parameter, bukan hasil lab per batch.",
            "Karbon = estimasi internal; klaim publik/kredit perlu verifikasi pihak ketiga & registrasi SRN-PPI.",
            "Insiden data & kecelakaan kerja belum memiliki log di sistem.",
        ],
        "standards": ["POJK 51/POJK.03/2017 Lampiran II (struktur)", "PSPK 1 & 2 (IFRS S1/S2) — berlaku 1 Jan 2027",
                      "GRI Standards 2021 (+GRI 102/103 efektif 2027)", "GHG Protocol Corporate & Scope 3; Land Sector & Removals",
                      "Perpres 110/2025 Nilai Ekonomi Karbon", "Puro.earth Biochar Methodology 2025 v2; IPCC 2019 Refinement",
                      "docs/09_RISET_STANDAR_ESG_BIOCHAR.md"],
    }
