"""Gudang data tunggal → laporan bulanan per peran.

Semua angka ditarik dari ledger operasional yang sama (harvests, custody, inbound_qc, manufacturing_batches,
biochar_ledger, energy_readings, routes) — tidak ada tabel ringkasan terpisah yang bisa "berbeda versi".
Model dimensional ala Kimball (fakta bulanan, dimensi waktu WIB & peran); metrik konversi mengikuti
Material Flow Analysis (Brunner & Rechberger); biaya mengikuti cost accounting (Horngren); energi ISO 50006.

Cakupan ditentukan SERVER dari peran (petani/pengepul/driver: data sendiri; pabrik/admin/auditor: seluruh
pabrik). Di PostgreSQL, RLS memberi lapisan perlindungan kedua.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.energy import EnergyMeterReading
from ..models.factory_ops import (BatchLoss, BatchOutput, CollectorSettlement, DeliveryRequest, InboundQC,
                                  ManufacturingBatch)
from ..models.harvest import Harvest, HarvestStatus
from ..models.ledger import BiocharLedgerEntry
from ..models.route import Route, RouteStatus, RouteStop
from ..models.trade import Bid, BidStatus
from ..models.user import User, UserRole

WIB = timezone(timedelta(hours=7))
PLANT_ROLES = {UserRole.PABRIK.value, UserRole.ADMIN.value, UserRole.AUDITOR.value}
MAX_MONTHS = 36

REFERENCES = [
    "Kimball, R. & Ross, M. (2013). The Data Warehouse Toolkit, 3rd ed. Wiley — model dimensional, fakta periodik.",
    "Brunner, P.H. & Rechberger, H. (2016). Handbook of Material Flow Analysis, 2nd ed. CRC Press — neraca massa.",
    "Horngren, C.T., Datar, S.M. & Rajan, M. (2015). Cost Accounting: A Managerial Emphasis, 15th ed. Pearson.",
    "ISO 50006:2014 — Energy baselines & energy performance indicators (SEC kWh/ton).",
    "APICS / ASCM (2017). SCOR Model v12 — metrik keandalan & biaya rantai pasok.",
]


def _v(e):
    return e.value if hasattr(e, "value") else e


def month_of(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:                      # SQLite mengembalikan waktu naif (disimpan UTC)
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(WIB).strftime("%Y-%m")


def month_range(start: str | None, end: str | None) -> list[str]:
    now = datetime.now(WIB)
    end = end or now.strftime("%Y-%m")
    if start is None:
        y, m = map(int, end.split("-"))
        m -= 11
        while m <= 0:
            y, m = y - 1, m + 12
        start = f"{y:04d}-{m:02d}"
    if start > end:
        raise ValueError("Bulan awal setelah bulan akhir.")
    out, (y, m) = [], map(int, start.split("-"))
    while f"{y:04d}-{m:02d}" <= end:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        if len(out) > MAX_MONTHS:
            raise ValueError(f"Rentang maksimum {MAX_MONTHS} bulan.")
    return out


def _window(months: list[str]) -> tuple[datetime, datetime]:
    y, m = map(int, months[0].split("-"))
    lo = datetime(y, m, 1, tzinfo=WIB)
    y, m = map(int, months[-1].split("-"))
    hi = datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=WIB)
    return lo.astimezone(timezone.utc), hi.astimezone(timezone.utc)


def _pct(a: float, b: float) -> float | None:
    return round(a / b * 100, 2) if b else None


def _div(a: float, b: float, nd: int = 1) -> float | None:
    return round(a / b, nd) if b else None


# ---------------------------------------------------------------- spesifikasi kolom per peran (UI generik)
M = lambda key, label, unit, group, chart=False: {"key": key, "label": label, "unit": unit, "group": group,  # noqa: E731
                                                   "chart": chart}
SPEC = {
    "plant": [
        M("supply.reported_kg", "Dilaporkan petani", "kg", "Volume pasokan"),
        M("supply.collector_verified_kg", "Ditimbang pengepul", "kg", "Volume pasokan"),
        M("supply.factory_received_kg", "Diterima pabrik", "kg", "Volume pasokan", True),
        M("supply.rejected_kg", "Ditolak QC", "kg", "Volume pasokan"),
        M("supply.shrinkage_pct", "Susut pengepul→pabrik", "%", "Volume pasokan"),
        M("conversion.batch_input_kg", "Input batch", "kg", "Konversi biomassa", True),
        M("conversion.bio_pellet_pct", "Konversi → bio-pellet", "%", "Konversi biomassa"),
        M("conversion.biochar_pct", "Konversi → biochar", "%", "Konversi biomassa"),
        M("conversion.bio_silika_pct", "Konversi → bio-silika", "%", "Konversi biomassa"),
        M("conversion.product_yield_pct", "Total produk / input", "%", "Konversi biomassa", True),
        M("conversion.closure_error_pct", "Galat penutupan mass balance (rata-rata)", "%", "Konversi biomassa"),
        M("conversion.biochar_to_farmers_kg", "Abu bottom ash ke dompet petani", "kg", "Konversi biomassa"),
        M("cost.raw_material_rp", "Pembelian biomassa", "Rp", "Efisiensi biaya"),
        M("cost.cash_paid_to_collectors_rp", "Kas dibayar ke pengepul (basis kas)", "Rp", "Efisiensi biaya"),
        M("cost.avg_purchase_price_per_kg", "Harga beli rata-rata", "Rp/kg", "Efisiensi biaya"),
        M("cost.unpriced_kg", "Diterima tanpa harga", "kg", "Efisiensi biaya"),
        M("cost.cost_per_ton_input_rp", "Biaya per ton input", "Rp/t", "Efisiensi biaya", True),
        M("cost.revenue_rp", "Nilai produk", "Rp", "Efisiensi biaya"),
        M("cost.profit_rp", "Laba batch", "Rp", "Efisiensi biaya"),
        M("cost.margin_pct", "Margin", "%", "Efisiensi biaya"),
        M("cost.energy_kwh", "Listrik", "kWh", "Efisiensi biaya"),
        M("cost.sec_kwh_per_ton", "SEC (kWh/ton diproses)", "kWh/t", "Efisiensi biaya"),
    ],
    "pengepul": [
        M("supply.bought_kg", "Dibeli dari petani (timbang)", "kg", "Volume pasokan", True),
        M("supply.sold_to_factory_kg", "Diterima pabrik", "kg", "Volume pasokan", True),
        M("supply.rejected_kg", "Ditolak pabrik", "kg", "Volume pasokan"),
        M("supply.shrinkage_pct", "Susut ke pabrik", "%", "Volume pasokan"),
        M("supply.auction_won_kg", "Menang lelang", "kg", "Volume pasokan"),
        M("cost.paid_to_farmers_rp", "Dibayar ke petani", "Rp", "Efisiensi biaya"),
        M("cost.received_from_factory_rp", "Tagihan ke pabrik", "Rp", "Efisiensi biaya"),
        M("cost.cash_received_from_factory_rp", "Kas diterima dari pabrik (basis kas)", "Rp", "Efisiensi biaya"),
        M("cost.outstanding_rp", "Tagihan belum dibayar", "Rp", "Efisiensi biaya"),
        M("cost.unpriced_kg", "Diterima tanpa harga", "kg", "Efisiensi biaya"),
        M("cost.gross_margin_rp", "Margin kotor", "Rp", "Efisiensi biaya", True),
        M("cost.avg_buy_price_per_kg", "Harga beli rata-rata", "Rp/kg", "Efisiensi biaya"),
        M("cost.avg_sell_price_per_kg", "Harga jual rata-rata", "Rp/kg", "Efisiensi biaya"),
    ],
    "petani": [
        M("supply.reported_kg", "Dilaporkan", "kg", "Volume pasokan"),
        M("supply.verified_kg", "Ditimbang pengepul", "kg", "Volume pasokan", True),
        M("supply.factory_received_kg", "Diterima pabrik", "kg", "Volume pasokan"),
        M("supply.auction_sold_kg", "Terjual via lelang", "kg", "Volume pasokan"),
        M("cost.income_rp", "Pendapatan", "Rp", "Efisiensi biaya", True),
        M("cost.avg_price_per_kg", "Harga rata-rata", "Rp/kg", "Efisiensi biaya"),
        M("conversion.biochar_credited_kg", "Biochar masuk dompet", "kg", "Konversi biomassa", True),
    ],
    "driver": [
        M("supply.stops_completed", "Titik dijemput", "stop", "Volume pasokan", True),
        M("supply.picked_kg", "Biomassa diangkut", "kg", "Volume pasokan", True),
        M("supply.routes_completed", "Rute selesai", "rute", "Volume pasokan"),
        M("cost.route_km", "Jarak rute selesai", "km", "Efisiensi biaya"),
        M("cost.kg_per_km", "Muatan per km", "kg/km", "Efisiensi biaya"),
    ],
}


def _nest(flat: dict) -> dict:
    out: dict = defaultdict(dict)
    for k, v in flat.items():
        g, name = k.split(".", 1)
        out[g][name] = v
    return dict(out)


async def monthly_report(db: AsyncSession, user: User, start: str | None = None, end: str | None = None) -> dict:
    role = _v(user.role)
    months = month_range(start, end)
    lo, hi = _window(months)
    kind = "plant" if role in PLANT_ROLES else role
    acc: dict[str, dict] = {m: defaultdict(float) for m in months}

    def add(m, key, val):
        if m in acc and val:
            acc[m][key] += float(val)

    def between(col):
        return (col >= lo) & (col < hi)

    if kind in ("plant", "petani", "pengepul"):
        q = select(Harvest).where(or_(between(Harvest.reported_at), between(Harvest.verified_at),
                                      between(Harvest.delivered_at)))
        if kind == "petani":
            q = q.where(Harvest.farmer_id == user.id)
        elif kind == "pengepul":
            q = q.where(Harvest.collector_id == user.id)
        for h in (await db.execute(q)).scalars().all():
            if kind != "pengepul":
                add(month_of(h.reported_at), "supply.reported_kg", h.quantity_kg)
            vm = month_of(h.verified_at)
            if h.verified_kg:
                add(vm, "supply.verified_kg" if kind == "petani" else
                    "supply.bought_kg" if kind == "pengepul" else "supply.collector_verified_kg", h.verified_kg)
                if kind in ("petani", "pengepul") and h.total_price:
                    add(vm, "cost.income_rp" if kind == "petani" else "cost.paid_to_farmers_rp", h.total_price)
            dm = month_of(h.delivered_at)
            if h.received_kg is not None and _v(h.status) in (HarvestStatus.DELIVERED.value, HarvestStatus.CONVERTED.value):
                if kind == "petani":
                    add(dm, "supply.factory_received_kg", h.received_kg)
                elif kind == "plant" and h.delivery_request_id is None:     # jalur rute pabrik (bukan QC lot)
                    add(dm, "supply.factory_received_kg", h.received_kg)
                if kind == "plant" and h.verified_kg:
                    add(dm, "_shrink_ref", h.verified_kg)
                    add(dm, "_shrink_recv", h.received_kg)

    if kind in ("plant", "pengepul"):
        q = select(InboundQC, DeliveryRequest.collector_id).join(DeliveryRequest, DeliveryRequest.id == InboundQC.request_id) \
            .where(between(InboundQC.created_at))
        if kind == "pengepul":
            q = q.where(DeliveryRequest.collector_id == user.id)
        for qc, _ in (await db.execute(q)).all():
            m = month_of(qc.created_at)
            if _v(qc.decision) == "tolak":
                add(m, "supply.rejected_kg", qc.net_kg)
                continue
            add(m, "supply.factory_received_kg" if kind == "plant" else "supply.sold_to_factory_kg", qc.net_kg)
        # Uang pabrik → pengepul: satu sumber untuk KEDUA jalur (QC lot & rute armada pabrik)
        q = select(CollectorSettlement).where(between(CollectorSettlement.created_at))
        if kind == "pengepul":
            q = q.where(CollectorSettlement.collector_id == user.id)
        for st in (await db.execute(q)).scalars().all():
            m = month_of(st.created_at)
            if st.amount_rp is None:
                add(m, "cost.unpriced_kg", st.payable_kg)
                continue
            add(m, "cost.raw_material_rp" if kind == "plant" else "cost.received_from_factory_rp", st.amount_rp)
            add(m, "_paid_kg" if kind == "plant" else "_sold_paid_kg", st.payable_kg)
            if kind == "pengepul" and _v(st.status) != "dibayar":
                add(m, "cost.outstanding_rp", st.amount_rp)
        # Uang pabrik → pengepul: basis kas (berdasarkan tanggal pelunasan paid_at)
        q_cash = select(CollectorSettlement).where(CollectorSettlement.paid_at.is_not(None),
                                                   between(CollectorSettlement.paid_at))
        if kind == "pengepul":
            q_cash = q_cash.where(CollectorSettlement.collector_id == user.id)
        for st in (await db.execute(q_cash)).scalars().all():
            pm = month_of(st.paid_at)
            if st.amount_rp is not None:
                add(pm, "cost.cash_paid_to_collectors_rp" if kind == "plant" else "cost.cash_received_from_factory_rp",
                    st.amount_rp)
        if kind == "pengepul":   # jalur rute: berat diterima pabrik untuk harvest milik pengepul ini
            rows = (await db.execute(select(Harvest).where(Harvest.collector_id == user.id,
                                                           Harvest.delivery_request_id.is_(None),
                                                           Harvest.received_kg.is_not(None),
                                                           between(Harvest.delivered_at)))).scalars().all()
            for h in rows:
                add(month_of(h.delivered_at), "supply.sold_to_factory_kg", h.received_kg)
        if kind == "pengepul":   # susut beban sendiri: timbangan pengepul vs pabrik, untuk harvest terlampir
            rows = (await db.execute(select(Harvest).where(Harvest.collector_id == user.id,
                                                           Harvest.received_kg.is_not(None),
                                                           between(Harvest.delivered_at)))).scalars().all()
            for h in rows:
                if h.verified_kg:
                    add(month_of(h.delivered_at), "_shrink_ref", h.verified_kg)
                    add(month_of(h.delivered_at), "_shrink_recv", h.received_kg)

    if kind in ("pengepul", "petani"):
        q = select(Bid).where(Bid.status == BidStatus.ACCEPTED, between(Bid.decided_at))
        q = q.where(Bid.collector_id == user.id) if kind == "pengepul" else q.where(Bid.farmer_id == user.id)
        for b in (await db.execute(q)).scalars().all():
            add(month_of(b.decided_at), "supply.auction_won_kg" if kind == "pengepul" else "supply.auction_sold_kg",
                b.accepted_kg)

    if kind == "plant":
        batches = (await db.execute(select(ManufacturingBatch).where(between(ManufacturingBatch.created_at)))).scalars().all()
        ids = {b.id: month_of(b.created_at) for b in batches}
        for b in batches:
            m = ids[b.id]
            add(m, "conversion.batch_input_kg", b.input_kg)
            add(m, "_batches", 1)
            add(m, "_closure_sum", b.closure_error_pct)
            t = (b.economics or {}).get("totals", {})
            add(m, "_batch_cost", t.get("total_cost_rp", 0))
            add(m, "cost.revenue_rp", t.get("revenue_rp", 0))
            add(m, "cost.profit_rp", t.get("profit_rp", 0))
        if ids:
            for o in (await db.execute(select(BatchOutput).where(BatchOutput.batch_id.in_(ids)))).scalars().all():
                add(ids[o.batch_id], f"_out_{o.product}", o.quantity_kg)
            for lo_ in (await db.execute(select(BatchLoss).where(BatchLoss.batch_id.in_(ids)))).scalars().all():
                add(ids[lo_.batch_id], "_loss", lo_.quantity_kg)
        for e in (await db.execute(select(BiocharLedgerEntry).where(
                BiocharLedgerEntry.entry_type == "allocation", between(BiocharLedgerEntry.created_at)))).scalars().all():
            add(month_of(e.created_at), "conversion.biochar_to_farmers_kg", e.amount_kg)
        for r in (await db.execute(select(EnergyMeterReading).where(EnergyMeterReading.period.in_(months)))).scalars().all():
            add(r.period, "cost.energy_kwh", r.kwh)
            add(r.period, "_energy_ton", r.production_ton)

    if kind == "petani":
        for e in (await db.execute(select(BiocharLedgerEntry).where(
                BiocharLedgerEntry.farmer_id == user.id, BiocharLedgerEntry.entry_type == "allocation",
                between(BiocharLedgerEntry.created_at)))).scalars().all():
            add(month_of(e.created_at), "conversion.biochar_credited_kg", e.amount_kg)

    if kind == "driver":
        rows = (await db.execute(select(RouteStop, Route).join(Route, Route.id == RouteStop.route_id)
                                 .where(Route.driver_id == user.id, RouteStop.qr_scanned.is_(True),
                                        between(RouteStop.pickup_at)))).all()
        for st, _ in rows:
            add(month_of(st.pickup_at), "supply.stops_completed", 1)
            add(month_of(st.pickup_at), "supply.picked_kg", (st.actual_ton or 0) * 1000)
        for r in (await db.execute(select(Route).where(Route.driver_id == user.id, Route.status == RouteStatus.COMPLETED,
                                                       between(Route.completed_at)))).scalars().all():
            add(month_of(r.completed_at), "supply.routes_completed", 1)
            add(month_of(r.completed_at), "cost.route_km", r.total_km or 0)

    # ---------------- turunan (rasio) per bulan
    rows = []
    for m in months:
        a = acc[m]
        if kind == "plant":
            inp = a.get("conversion.batch_input_kg", 0)
            for p in ("bio_pellet", "biochar", "bio_silika"):
                a[f"conversion.{p}_pct"] = _pct(a.get(f"_out_{p}", 0), inp)
            a["conversion.product_yield_pct"] = _pct(sum(a.get(f"_out_{p}", 0) for p in ("bio_pellet", "biochar", "bio_silika")), inp)
            a["conversion.closure_error_pct"] = _div(a.get("_closure_sum", 0), a.get("_batches", 0), 3)
            a["cost.cost_per_ton_input_rp"] = _div(a.get("_batch_cost", 0) * 1000, inp, 0)
            a["cost.margin_pct"] = _pct(a.get("cost.profit_rp", 0), a.get("cost.revenue_rp", 0))
            a["cost.avg_purchase_price_per_kg"] = _div(a.get("cost.raw_material_rp", 0), a.get("_paid_kg", 0), 2)
            a["cost.sec_kwh_per_ton"] = _div(a.get("cost.energy_kwh", 0), a.get("_energy_ton", 0), 1)
        if kind in ("plant", "pengepul"):
            ref = a.get("_shrink_ref", 0)
            a["supply.shrinkage_pct"] = _pct(ref - a.get("_shrink_recv", 0), ref)
        if kind == "pengepul":
            a["cost.gross_margin_rp"] = a.get("cost.received_from_factory_rp", 0) - a.get("cost.paid_to_farmers_rp", 0)
            a["cost.avg_buy_price_per_kg"] = _div(a.get("cost.paid_to_farmers_rp", 0), a.get("supply.bought_kg", 0), 2)
            a["cost.avg_sell_price_per_kg"] = _div(a.get("cost.received_from_factory_rp", 0), a.get("_sold_paid_kg", 0), 2)
        if kind == "petani":
            a["cost.avg_price_per_kg"] = _div(a.get("cost.income_rp", 0), a.get("supply.verified_kg", 0), 2)
        if kind == "driver":
            a["cost.kg_per_km"] = _div(a.get("supply.picked_kg", 0), a.get("cost.route_km", 0), 1)
        flat = {s["key"]: (round(a[s["key"]], 2) if isinstance(a.get(s["key"]), float) else a.get(s["key"]))
                for s in SPEC[kind]}
        flat = {k: (0 if v is None and s["unit"] in ("kg", "Rp", "kWh", "stop", "rute", "km") else v)
                for (k, v), s in zip(flat.items(), SPEC[kind])}
        rows.append({"month": m, **_nest(flat)})

    totals = {}
    for s in SPEC[kind]:
        if s["unit"] in ("kg", "Rp", "kWh", "stop", "rute", "km"):
            g, n = s["key"].split(".", 1)
            totals[s["key"]] = round(sum((r.get(g, {}).get(n) or 0) for r in rows), 2)
    return {
        "scope": {"role": role, "kind": kind, "user_id": user.id,
                  "label": "Seluruh pabrik" if kind == "plant" else "Data Anda sendiri"},
        "period": {"from": months[0], "to": months[-1], "months": len(months), "timezone": "WIB (UTC+7)"},
        "columns": SPEC[kind],
        "months": rows,
        "totals": totals,
        "definitions": {
            "factory_received_kg": "QC masuk (berat bersih lot yang diterima) + harvest jalur rute yang diterima pabrik",
            "shrinkage_pct": "(timbangan pengepul − timbangan pabrik) / timbangan pengepul, harvest diterima bulan itu",
            "conversion_pct": "kg produk / kg input batch (Material Flow Analysis)",
            "closure_error_pct": "(input − Σ output − Σ loss) / input, rata-rata batch",
            "cost_per_ton_input_rp": "Σ biaya batch (bahan baku + variabel + tetap teralokasi) / ton input",
            "sec_kwh_per_ton": "kWh / ton diproses (modul Energi ⑩, ISO 50006)",
            "gross_margin_rp": "tagihan ke pabrik (yang sudah berharga) − pembayaran ke petani (pengepul)",
            "pembayaran_pabrik": "Catatan pembayaran pabrik→pengepul (collector_settlements) untuk KEDUA jalur: "
                                 "QC lot (harga kontrak basis kering) dan rute armada pabrik (harga isian pabrik atau "
                                 "rekomendasi netback). Dibukukan pada bulan barang diterima.",
            "unpriced_kg": "kg yang sudah diterima pabrik tetapi harganya belum ditetapkan (status 'menunggu harga') — "
                           "belum masuk Rp, sehingga margin bulan itu masih bisa bertambah",
        },
        "references": REFERENCES,
    }
