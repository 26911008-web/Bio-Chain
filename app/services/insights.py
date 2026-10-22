"""Evaluasi & Optimasi per peran — KPI deterministik + daftar prioritas optimasi.

Prinsip:
- Semua angka berasal dari ledger yang sama dengan Laporan Bulanan (`monthly_report`, cakupan per peran
  ditentukan server) ditambah beberapa query langsung yang sama cakupannya. Tidak ada angka karangan:
  KPI tanpa data diberi status `data_kurang` beserta apa yang perlu diisi.
- Target dibaca dari menu Parameter (grup "Target Evaluasi & Optimasi" + parameter domain yang sudah ada),
  sehingga operator bisa menyesuaikan dengan kondisi lapangan.
- Prioritas diurutkan dari tingkat keparahan lalu perkiraan dampak (Rp/kg) yang dihitung dari data nyata.
- AI (assistant router) hanya MENJELASKAN hasil ini dan menyusun langkah — tidak menghitung ulang.
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..ai.context import build_context
from ..models.harvest import Harvest, HarvestStatus
from ..models.route import Route, RouteStop
from ..models.user import User, UserRole
from ..params import P
from .reports import PLANT_ROLES, WIB, _v, month_range, monthly_report

STATUS_POINTS = {"baik": 100, "perhatian": 60, "kritis": 20}
SEVERITY = {"kritis": 2, "perhatian": 1}


def _months_back(n: int) -> list[str]:
    end = datetime.now(WIB).strftime("%Y-%m")
    y, m = map(int, end.split("-"))
    m -= n - 1
    while m <= 0:
        y, m = y - 1, m + 12
    return month_range(f"{y:04d}-{m:02d}", end)


def _get(row: dict, key: str):
    g, n = key.split(".", 1)
    return (row.get(g) or {}).get(n)


def _sum(rows: list[dict], key: str) -> float:
    return float(sum((_get(r, key) or 0) for r in rows))


def _mean(rows: list[dict], key: str) -> float | None:
    vals = [v for v in (_get(r, key) for r in rows) if v is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def _ratio(a: float, b: float, scale: float = 100.0, nd: int = 2) -> float | None:
    return round(a / b * scale, nd) if b else None


def _status(value, target, direction: str) -> str:
    """direction 'min' = makin besar makin baik (value ≥ target); 'max' = makin kecil makin baik."""
    if value is None:
        return "data_kurang"
    if target is None:
        return "info"
    band = P("evaluasi.warn_band_pct") / 100.0
    if direction == "min":
        if value >= target:
            return "baik"
        return "perhatian" if value >= target * (1 - band) else "kritis"
    if value <= target:
        return "baik"
    # target 0 (mis. kg tanpa harga): pita absolut tidak bermakna → langsung perhatian
    limit = target * (1 + band) if target else 0
    return "perhatian" if value <= limit or target == 0 else "kritis"


def _kpi(key, label, unit, value, target=None, direction="min", prev=None, target_src=None,
         need=None, action=None, impact=None, weight=1.0, fmt_target=None, breakdown=None):
    st = _status(value, target, direction)
    if st == "data_kurang" and not need:
        need = "Belum ada data pada jendela evaluasi — muncul otomatis setelah transaksi tercatat."
    if fmt_target is None and target is not None:
        u = "" if unit in ("%",) else f" {unit}"
        fmt_target = f"{'≥' if direction == 'min' else '≤'} {target:g}{'%' if unit == '%' else u}"
    trend = None
    if value is not None and prev not in (None, 0):
        trend = round((value - prev) / abs(prev) * 100, 1)
    return {
        "key": key, "label": label, "unit": unit, "value": value, "prev": prev, "trend_pct": trend,
        "target": target, "direction": direction, "target_source": target_src, "status": st,
        "weight": weight, "need": need if st == "data_kurang" else None,
        "action": action if st in ("perhatian", "kritis") else None,
        "impact": impact if st in ("perhatian", "kritis") else None,
        "target_label": fmt_target,
        "breakdown": breakdown or [],
    }


def _impact(kind: str, amount: float | None, note: str) -> dict | None:
    if amount is None or amount <= 0:
        return None
    return {"kind": kind, "amount": round(amount, 0 if kind == "rp" else 1), "note": note}


async def _harvest_quality(db: AsyncSession, farmer_id: int, lo, hi) -> dict:
    rows = (await db.execute(select(Harvest).where(
        Harvest.farmer_id == farmer_id, Harvest.verified_at.is_not(None),
        Harvest.verified_at >= lo, Harvest.verified_at < hi))).scalars().all()
    graded = [h for h in rows if h.grade is not None]
    moist = [h.moisture for h in rows if h.moisture is not None]
    est = [(h.quantity_kg, h.verified_kg) for h in rows if h.quantity_kg and h.verified_kg]

    # Breakdown per komoditas
    by_com: dict[str, dict] = {}
    for h in rows:
        c = h.commodity or "sekam_padi"
        if c not in by_com:
            by_com[c] = {"rows": [], "graded": [], "moist": [], "est": [], "priced": []}
        by_com[c]["rows"].append(h)
        if h.grade is not None:
            by_com[c]["graded"].append(h)
        if h.moisture is not None:
            by_com[c]["moist"].append(h.moisture)
        if h.quantity_kg and h.verified_kg:
            by_com[c]["est"].append((h.quantity_kg, h.verified_kg))
        if h.total_price and h.verified_kg:
            by_com[c]["priced"].append((h.total_price, h.verified_kg))

    from ..models.biomass import BiomassParameter
    bp_rows = (await db.execute(select(BiomassParameter.code, BiomassParameter.name))).all()
    names = {r[0]: r[1] for r in bp_rows}

    breakdown = {}
    for c, d in by_com.items():
        priced_tot = sum(p for p, _ in d["priced"])
        kg_tot = sum(k for _, k in d["priced"])
        avg_p = round(priced_tot / kg_tot, 1) if kg_tot else None
        breakdown[c] = {
            "commodity": c,
            "name": names.get(c, c.replace("_", " ").title()),
            "lots": len(d["rows"]),
            "grade_a_pct": _ratio(sum(1 for h in d["graded"] if _v(h.grade) == "A"), len(d["graded"])),
            "avg_moisture": round(sum(d["moist"]) / len(d["moist"]), 2) if d["moist"] else None,
            "estimate_gap_pct": _ratio(sum(abs(q - v) for q, v in d["est"]), sum(v for _, v in d["est"])),
            "avg_price": avg_p,
            "verified_kg": kg_tot,
        }

    return {
        "lots": len(rows),
        "grade_a_pct": _ratio(sum(1 for h in graded if _v(h.grade) == "A"), len(graded)),
        "avg_moisture": round(sum(moist) / len(moist), 2) if moist else None,
        "estimate_gap_pct": _ratio(sum(abs(q - v) for q, v in est), sum(v for _, v in est)),
        "rejected": sum(1 for h in rows if _v(h.status) == HarvestStatus.REJECTED.value),
        "breakdown": breakdown,
    }


async def _collector_commodity_breakdowns(db: AsyncSession, collector_id: int, lo, hi) -> dict:
    from ..models.biomass import BiomassParameter
    from ..models.factory_ops import DeliveryRequest, InboundQC, CollectorSettlement

    bp_rows = (await db.execute(select(BiomassParameter.code, BiomassParameter.name))).all()
    names = {r[0]: r[1] for r in bp_rows}

    by_com: dict[str, dict] = {}
    def _init(c):
        if c not in by_com:
            by_com[c] = {
                "name": names.get(c, c.replace("_", " ").title()),
                "bought_kg": 0.0, "paid_rp": 0.0,
                "sold_kg": 0.0, "received_rp": 0.0,
                "shrink_ref_kg": 0.0, "shrink_recv_kg": 0.0,
                "rejected_kg": 0.0,
                "outstanding_rp": 0.0, "billed_rp": 0.0,
                "unpriced_kg": 0.0,
            }
        return by_com[c]

    # 1. Pembelian dari petani yang diverifikasi
    h_rows = (await db.execute(select(Harvest).where(
        Harvest.collector_id == collector_id,
        Harvest.verified_at.is_not(None),
        Harvest.verified_at >= lo, Harvest.verified_at < hi
    ))).scalars().all()
    for h in h_rows:
        c = h.commodity or "sekam_padi"
        d = _init(c)
        if h.verified_kg:
            d["bought_kg"] += h.verified_kg
            if h.total_price:
                d["paid_rp"] += h.total_price

    # 2. Pengiriman via rute armada ke pabrik
    delivered_harvests = (await db.execute(select(Harvest).where(
        Harvest.collector_id == collector_id,
        Harvest.delivered_at.is_not(None),
        Harvest.delivered_at >= lo, Harvest.delivered_at < hi
    ))).scalars().all()
    for h in delivered_harvests:
        c = h.commodity or "sekam_padi"
        d = _init(c)
        if h.received_kg:
            d["sold_kg"] += h.received_kg
            if h.verified_kg:
                d["shrink_ref_kg"] += h.verified_kg
                d["shrink_recv_kg"] += h.received_kg

    # 3. Pengiriman lewat InboundQC pabrik
    qc_rows = (await db.execute(
        select(InboundQC, DeliveryRequest)
        .join(DeliveryRequest, DeliveryRequest.id == InboundQC.request_id)
        .where(DeliveryRequest.collector_id == collector_id,
               InboundQC.created_at >= lo, InboundQC.created_at < hi)
    )).all()
    for qc, dr in qc_rows:
        c_found = (await db.execute(select(Harvest.commodity).where(
            Harvest.delivery_request_id == dr.id
        ).limit(1))).scalar_one_or_none()
        c = c_found or "sekam_padi"
        d = _init(c)
        if _v(qc.decision) == "tolak":
            d["rejected_kg"] += (qc.net_kg or 0.0)
        else:
            d["sold_kg"] += (qc.net_kg or 0.0)

    # 4. Tagihan settlement ke pabrik
    st_rows = (await db.execute(
        select(CollectorSettlement).where(
            CollectorSettlement.collector_id == collector_id,
            CollectorSettlement.created_at >= lo, CollectorSettlement.created_at < hi
        )
    )).scalars().all()
    for st in st_rows:
        c = "sekam_padi"
        if st.source == "rute" and st.harvest_id:
            h_c = (await db.execute(select(Harvest.commodity).where(Harvest.id == st.harvest_id))).scalar_one_or_none()
            if h_c: c = h_c
        elif st.source == "qc" and st.qc_id:
            dr_id = (await db.execute(select(InboundQC.request_id).where(InboundQC.id == st.qc_id))).scalar_one_or_none()
            if dr_id:
                h_c = (await db.execute(select(Harvest.commodity).where(Harvest.delivery_request_id == dr_id).limit(1))).scalar_one_or_none()
                if h_c: c = h_c
        d = _init(c)
        if st.amount_rp is None:
            d["unpriced_kg"] += (st.payable_kg or 0.0)
        else:
            d["billed_rp"] += st.amount_rp
            d["received_rp"] += st.amount_rp
            if _v(st.status) != "dibayar":
                d["outstanding_rp"] += st.amount_rp

    if not by_com:
        for code in ["sekam_padi", "tongkol_jagung"]:
            if code in names:
                _init(code)

    out = {}
    for c, d in by_com.items():
        buy_p = round(d["paid_rp"] / d["bought_kg"], 1) if d["bought_kg"] > 0 and d["paid_rp"] > 0 else None
        sell_p = round(d["received_rp"] / d["sold_kg"], 1) if d["sold_kg"] > 0 and d["received_rp"] > 0 else None
        margin = round(sell_p - buy_p, 1) if (sell_p is not None and buy_p is not None) else None

        shrink_pct = None
        if d["shrink_ref_kg"] > 0:
            diff = d["shrink_ref_kg"] - d["shrink_recv_kg"]
            shrink_pct = round(max(0.0, (diff / d["shrink_ref_kg"]) * 100), 2)

        tot_handled = d["sold_kg"] + d["rejected_kg"]
        reject_pct = round((d["rejected_kg"] / tot_handled) * 100, 2) if tot_handled > 0 else (0.0 if d["sold_kg"] > 0 else None)
        outstanding_pct = round((d["outstanding_rp"] / d["billed_rp"]) * 100, 1) if d["billed_rp"] > 0 else None

        out[c] = {
            "commodity": c,
            "name": d["name"],
            "margin_per_kg": margin,
            "shrinkage_pct": shrink_pct,
            "reject_pct": reject_pct,
            "outstanding_pct": outstanding_pct,
            "outstanding_rp": round(d["outstanding_rp"]) if d["outstanding_rp"] > 0 else None,
            "unpriced_kg": round(d["unpriced_kg"], 1) if d["unpriced_kg"] > 0 else (0.0 if d["sold_kg"] > 0 else None),
        }
    return out


async def _stop_stats(db: AsyncSession, driver_id: int, lo, hi) -> dict:
    rows = (await db.execute(
        select(RouteStop.stop_status, func.count(RouteStop.id))
        .join(Route, Route.id == RouteStop.route_id)
        .where(Route.driver_id == driver_id, Route.planned_at >= lo, Route.planned_at < hi)
        .group_by(RouteStop.stop_status))).all()
    c = {str(_v(s)): n for s, n in rows}
    util = (await db.execute(select(func.avg(Route.utilization_pct)).where(
        Route.driver_id == driver_id, Route.planned_at >= lo, Route.planned_at < hi))).scalar_one()
    return {"picked": c.get("picked_up", 0), "failed": c.get("failed", 0), "cancelled": c.get("cancelled", 0),
            "avg_util": round(float(util), 1) if util is not None else None}


def _rp_impact(k: dict) -> float:
    imp = k.get("impact") or {}
    return float(imp.get("amount") or 0) if imp.get("kind") == "rp" else 0.0


def _window_bounds(months: list[str]):
    from .reports import _window
    return _window(months)


async def evaluate(db: AsyncSession, user: User, window_months: int | None = None) -> dict:
    role = _v(user.role)
    n = int(window_months or P("evaluasi.window_months"))
    n = max(1, min(n, 24))
    months = _months_back(2 * n)
    rep = await monthly_report(db, user, months[0], months[-1])
    rows = rep["months"]
    prev_rows, cur_rows = rows[:n], rows[n:]
    lo_cur, hi_cur = _window_bounds(months[n:])
    lo_prev, hi_prev = _window_bounds(months[:n])
    ctx = await build_context(db, user)
    kpis: list[dict] = []
    tol_shrink = P("sirkular.shrinkage_tolerance_pct")

    if role == UserRole.PETANI.value:
        q_cur = await _harvest_quality(db, user.id, lo_cur, hi_cur)
        q_prev = await _harvest_quality(db, user.id, lo_prev, hi_prev)
        income, kg = _sum(cur_rows, "cost.income_rp"), _sum(cur_rows, "supply.verified_kg")
        avg_price = _ratio(income, kg, 1)
        prev_price = _ratio(_sum(prev_rows, "cost.income_rp"), _sum(prev_rows, "supply.verified_kg"), 1)
        base = P("harga_mutu.base_price_per_kg")
        m_best = P("harga_mutu.moisture_best")

        bd = q_cur.get("breakdown", {})
        price_bd = [{"commodity": c, "name": d["name"], "value": d["avg_price"], "unit": "Rp/kg"}
                    for c, d in bd.items() if d.get("avg_price") is not None]
        grade_bd = [{"commodity": c, "name": d["name"], "value": d["grade_a_pct"], "unit": "%"}
                    for c, d in bd.items() if d.get("grade_a_pct") is not None]
        moist_bd = [{"commodity": c, "name": d["name"], "value": d["avg_moisture"], "unit": "%"}
                    for c, d in bd.items() if d.get("avg_moisture") is not None]
        est_bd = [{"commodity": c, "name": d["name"], "value": d["estimate_gap_pct"], "unit": "%"}
                  for c, d in bd.items() if d.get("estimate_gap_pct") is not None]

        kpis += [
            _kpi("harga_rata", "Harga rata-rata diterima", "Rp/kg", avg_price, base, "min", prev_price,
                 "harga_mutu.base_price_per_kg", need="Belum ada sekam yang ditimbang pengepul pada jendela ini.",
                 action="Naikkan mutu (kadar air ≤ target) atau pasang listing lelang agar pengepul bersaing harga.",
                 impact=_impact("rp", (base - (avg_price or 0)) * kg, "selisih ke harga dasar × kg ditimbang"),
                 weight=1.5, fmt_target=f"≥ harga dasar Rp{base:,.0f}/kg", breakdown=price_bd),
            _kpi("grade_a", "Porsi lot Grade A", "%", q_cur["grade_a_pct"], P("evaluasi.grade_a_share_min_pct"), "min",
                 q_prev["grade_a_pct"], "evaluasi.grade_a_share_min_pct",
                 need="Belum ada lot yang dinilai mutunya.",
                 action="Jemur sekam tipis sebelum pengepul datang; simpan di bawah atap/terpal agar tidak lembap.",
                 weight=1.2, breakdown=grade_bd),
            _kpi("kadar_air", "Kadar air rata-rata saat ditimbang", "%", q_cur["avg_moisture"], m_best, "max",
                 q_prev["avg_moisture"], "harga_mutu.moisture_best", need="Kadar air belum tercatat pada timbangan.",
                 action="Kadar air di atas target menurunkan harga basis kering — keringkan hingga ≤ target.",
                 fmt_target=f"≤ {m_best:g}%", breakdown=moist_bd),
            _kpi("akurasi_taksiran", "Selisih taksiran vs timbangan", "%", q_cur["estimate_gap_pct"],
                 P("sirkular.estimate_tolerance_pct"), "max", q_prev["estimate_gap_pct"],
                 "sirkular.estimate_tolerance_pct", need="Belum ada lot yang ditimbang.",
                 action="Hitung jumlah karung × berat rata-rata per karung saat melapor agar armada tidak salah muat.",
                 breakdown=est_bd),
            _kpi("biochar_masuk", "Biochar masuk dompet", "kg", _sum(cur_rows, "conversion.biochar_credited_kg"),
                 None, "min", _sum(prev_rows, "conversion.biochar_credited_kg")),
        ]

    elif role == UserRole.PENGEPUL.value:
        bought = _sum(cur_rows, "supply.bought_kg")
        sold = _sum(cur_rows, "supply.sold_to_factory_kg")
        rejected = _sum(cur_rows, "supply.rejected_kg")
        billed = _sum(cur_rows, "cost.received_from_factory_rp")
        outstanding = _sum(cur_rows, "cost.outstanding_rp")
        unpriced = _sum(cur_rows, "cost.unpriced_kg")
        # Harga rata-rata dari laporan: harga jual hanya atas kg yang SUDAH berharga (settlement), sehingga
        # kg 'menunggu harga' tidak membuat margin tampak negatif.
        buy = _ratio(_sum(cur_rows, "cost.paid_to_farmers_rp"), bought, 1)
        sell = _mean(cur_rows, "cost.avg_sell_price_per_kg")
        margin = round(sell - buy, 1) if sell is not None and buy is not None else None
        pbuy = _ratio(_sum(prev_rows, "cost.paid_to_farmers_rp"), _sum(prev_rows, "supply.bought_kg"), 1)
        psell = _mean(prev_rows, "cost.avg_sell_price_per_kg")
        pmargin = round(psell - pbuy, 1) if psell is not None and pbuy is not None else None
        tgt_margin = P("pasar.default_margin_per_kg")
        shrink = _mean(cur_rows, "supply.shrinkage_pct")
        reject_pct = _ratio(rejected, sold + rejected)
        col_bd = await _collector_commodity_breakdowns(db, user.id, lo_cur, hi_cur)
        margin_bd = [{"commodity": c, "name": d["name"], "value": d["margin_per_kg"] if d["margin_per_kg"] is not None else 0.0, "unit": "Rp/kg"}
                     for c, d in col_bd.items()]
        susut_bd = [{"commodity": c, "name": d["name"], "value": d["shrinkage_pct"] if d["shrinkage_pct"] is not None else 0.0, "unit": "%"}
                    for c, d in col_bd.items()]
        ditolak_bd = [{"commodity": c, "name": d["name"], "value": d["reject_pct"] if d["reject_pct"] is not None else 0.0, "unit": "%"}
                      for c, d in col_bd.items()]
        piutang_bd = [{"commodity": c, "name": d["name"], "value": d["outstanding_pct"] if d["outstanding_pct"] is not None else 0.0, "unit": "%"}
                      for c, d in col_bd.items()]
        unpriced_bd = [{"commodity": c, "name": d["name"], "value": d["unpriced_kg"] if d["unpriced_kg"] is not None else 0.0, "unit": "kg"}
                       for c, d in col_bd.items()]

        kpis += [
            _kpi("margin_per_kg", "Margin per kg (jual − beli)", "Rp/kg", margin, tgt_margin, "min", pmargin,
                 "pasar.default_margin_per_kg", need="Butuh pembelian dari petani DAN tagihan berharga ke pabrik.",
                 action="Gunakan Bid Advisor agar tawaran tidak melewati batas atas; tagih harga kontrak basis kering.",
                 impact=_impact("rp", (tgt_margin - (margin or 0)) * sold, "selisih margin × kg terjual"),
                 weight=1.5, fmt_target=f"≥ Rp{tgt_margin:,.0f}/kg", breakdown=margin_bd),
            _kpi("susut", "Susut timbangan ke pabrik", "%", shrink, tol_shrink, "max",
                 _mean(prev_rows, "supply.shrinkage_pct"), "sirkular.shrinkage_tolerance_pct",
                 need="Belum ada muatan yang ditimbang ulang pabrik.",
                 action="Kalibrasi timbangan tiap awal shift, tutup bak dengan terpal, kurangi waktu tunggu di gudang.",
                 impact=_impact("rp", ((shrink or 0) - tol_shrink) / 100 * sold * (sell or 0),
                                "kg susut di atas toleransi × harga jual"), weight=1.3,
                 fmt_target=f"≤ {tol_shrink:g}%", breakdown=susut_bd),
            _kpi("ditolak", "Porsi biomassa ditolak pabrik", "%", reject_pct, P("evaluasi.reject_max_pct"), "max",
                 _ratio(_sum(prev_rows, "supply.rejected_kg"),
                        _sum(prev_rows, "supply.sold_to_factory_kg") + _sum(prev_rows, "supply.rejected_kg")),
                 "evaluasi.reject_max_pct", need="Belum ada lot yang diperiksa QC pabrik.",
                 action="Uji kadar air sebelum muat; pisahkan lot basah (beli untuk dikeringkan) dari lot siap kirim.",
                 impact=_impact("kg", rejected, "kg ditolak pada jendela ini"), breakdown=ditolak_bd),
            _kpi("piutang", "Tagihan pabrik belum dibayar", "%", _ratio(outstanding, billed),
                 P("evaluasi.collector_outstanding_max_pct"), "max", None, "evaluasi.collector_outstanding_max_pct",
                 need="Belum ada tagihan berharga ke pabrik.",
                 action="Tindak lanjuti tagihan berstatus 'terutang' dengan operator pabrik.",
                 impact=_impact("rp", outstanding, "Rp tertahan di pabrik"), breakdown=piutang_bd),
            _kpi("tanpa_harga", "Diterima pabrik tanpa harga", "kg", unpriced, 0.0, "max", None, None,
                 action="Minta pabrik menetapkan harga settlement agar margin bulan ini final.",
                 impact=_impact("kg", unpriced, "kg menunggu harga"), fmt_target="0 kg", breakdown=unpriced_bd),
        ]
        q = ctx.get("antrean_verifikasi") or {}
        kpis.append(_kpi("antrean", "Antrean laporan petani menunggu verifikasi", "laporan",
                         q.get("jumlah_laporan"), None))

    elif role == UserRole.DRIVER.value:
        s_cur = await _stop_stats(db, user.id, lo_cur, hi_cur)
        s_prev = await _stop_stats(db, user.id, lo_prev, hi_prev)
        succ = _ratio(s_cur["picked"], s_cur["picked"] + s_cur["failed"])
        psucc = _ratio(s_prev["picked"], s_prev["picked"] + s_prev["failed"])
        km = _sum(cur_rows, "cost.route_km")
        kgkm = _ratio(_sum(cur_rows, "supply.picked_kg"), km, 1, 1)
        pkgkm = _ratio(_sum(prev_rows, "supply.picked_kg"), _sum(prev_rows, "cost.route_km"), 1, 1)
        kpis += [
            _kpi("stop_berhasil", "Stop berhasil dijemput", "%", succ, P("evaluasi.stop_success_min_pct"), "min", psucc,
                 "evaluasi.stop_success_min_pct", need="Belum ada stop yang selesai/gagal pada jendela ini.",
                 action="Hubungi penggilingan sebelum berangkat; laporkan alasan gagal agar pabrik bisa menata ulang rute.",
                 impact=_impact("kg", None, ""), weight=1.4),
            _kpi("utilisasi", "Utilisasi bak truk (rencana)", "%", s_cur["avg_util"],
                 P("evaluasi.vehicle_utilization_min_pct"), "min", s_prev["avg_util"],
                 "evaluasi.vehicle_utilization_min_pct", need="Belum ada rute yang direncanakan untuk Anda.",
                 action="Minta pabrik menggabungkan titik berdekatan agar bak terisi; susun karung rapat.",
                 weight=1.2),
            _kpi("kg_per_km", "Muatan per km", "kg/km", kgkm, None, "min", pkgkm),
            _kpi("km_rute", "Jarak rute selesai", "km", round(km, 1), None, "min",
                 round(_sum(prev_rows, "cost.route_km"), 1)),
        ]
        if (succ is not None and succ < P("evaluasi.stop_success_min_pct")) and s_cur["failed"]:
            kpis[0]["impact"] = {"kind": "stop", "amount": s_cur["failed"], "note": "stop gagal pada jendela ini"}

    elif role in PLANT_ROLES:
        recv = _sum(cur_rows, "supply.factory_received_kg")
        rejected = _sum(cur_rows, "supply.rejected_kg")
        revenue = _sum(cur_rows, "cost.revenue_rp")
        profit = _sum(cur_rows, "cost.profit_rp")
        margin = _ratio(profit, revenue)
        pmargin = _ratio(_sum(prev_rows, "cost.profit_rp"), _sum(prev_rows, "cost.revenue_rp"))
        tgt_margin = P("pabrik.target_margin_pct")
        shrink = _mean(cur_rows, "supply.shrinkage_pct")
        closure = _mean(cur_rows, "conversion.closure_error_pct")
        tol_closure = P("pabrik.closure_tolerance_pct")
        sec = _mean(cur_rows, "cost.sec_kwh_per_ton")
        sec_plan = P("pabrik.kwh_per_ton_input")
        cap = _ratio(recv / n, P("pabrik.planned_input_ton_per_month") * 1000)
        pcap = _ratio(_sum(prev_rows, "supply.factory_received_kg") / n, P("pabrik.planned_input_ton_per_month") * 1000)
        avg_buy = _mean(cur_rows, "cost.avg_purchase_price_per_kg")
        unpriced = _sum(cur_rows, "cost.unpriced_kg")
        tariff = P("energi.tariff_rp_per_kwh")
        kpis += [
            _kpi("margin", "Margin batch", "%", margin, tgt_margin, "min", pmargin, "pabrik.target_margin_pct",
                 need="Belum ada batch produksi dengan nilai produk (isi harga jual produk di Parameter).",
                 action="Jalankan Blending HiGHS untuk umpan termurah yang memenuhi spesifikasi; tinjau porsi pellet/silika.",
                 impact=_impact("rp", (tgt_margin - (margin or 0)) / 100 * revenue, "selisih margin × nilai produk"),
                 weight=1.5, fmt_target=f"≥ {tgt_margin:g}%"),
            _kpi("kapasitas", "Pemenuhan rencana input", "%", cap, P("evaluasi.plant_capacity_min_pct"), "min", pcap,
                 "evaluasi.plant_capacity_min_pct", need="Belum ada sekam diterima.",
                 action="Buka listing/DR lebih awal di musim gadu; gunakan proyeksi pasokan untuk kontrak pengepul.",
                 weight=1.3),
            _kpi("susut", "Susut pengepul→pabrik", "%", shrink, tol_shrink, "max", _mean(prev_rows, "supply.shrinkage_pct"),
                 "sirkular.shrinkage_tolerance_pct", need="Belum ada muatan rute yang ditimbang ulang.",
                 action="Audit pengepul dengan susut tertinggi (menu Auditor) dan cek kalibrasi jembatan timbang.",
                 impact=_impact("rp", ((shrink or 0) - tol_shrink) / 100 * recv * (avg_buy or 0),
                                "kg susut di atas toleransi × harga beli rata-rata"),
                 weight=1.2, fmt_target=f"≤ {tol_shrink:g}%"),
            _kpi("penutupan_massa", "Galat penutupan mass balance", "%", closure, tol_closure, "max",
                 _mean(prev_rows, "conversion.closure_error_pct"), "pabrik.closure_tolerance_pct",
                 need="Belum ada batch produksi tercatat.",
                 action="Timbang semua output & loss per batch (debu siklon, abu) agar neraca menutup."),
            _kpi("sec", "Energi spesifik (SEC)", "kWh/t", sec, sec_plan, "max", _mean(prev_rows, "cost.sec_kwh_per_ton"),
                 "pabrik.kwh_per_ton_input", need="Isi pembacaan meter listrik bulanan (modul Energi ⑩).",
                 action="Jalankan analisis Energi ⑩ untuk anomali beban dasar; jadwalkan mesin di luar beban puncak.",
                 impact=_impact("rp", ((sec or 0) - sec_plan) * recv / 1000 * tariff, "kWh berlebih × tarif"),
                 fmt_target=f"≤ {sec_plan:g} kWh/t"),
            _kpi("ditolak", "Porsi sekam ditolak QC", "%", _ratio(rejected, recv + rejected), P("evaluasi.reject_max_pct"),
                 "max", None, "evaluasi.reject_max_pct", need="Belum ada lot QC.",
                 action="Umumkan spesifikasi kadar air ke pengepul; beri harga basis kering agar sekam basah tidak dikirim.",
                 impact=_impact("kg", rejected, "kg ditolak")),
            _kpi("tanpa_harga", "Diterima tanpa harga settlement", "kg", unpriced, 0.0, "max", None, None,
                 action="Tetapkan harga settlement (rekomendasi netback tersedia) agar pengepul segera dibayar.",
                 impact=_impact("kg", unpriced, "kg menunggu harga"), fmt_target="0 kg"),
        ]
        nm = ctx.get("neraca_massa") or {}
        kpis.append(_kpi("selisih_ditandai", "Harvest ditandai selisih timbangan", "lot",
                         nm.get("harvest_ditandai_selisih"), 0, "max", None, "sirkular.shrinkage_tolerance_pct",
                         action="Tinjau daftar selisih di menu Auditor dan tutup dengan catatan investigasi.",
                         fmt_target="0 lot"))
        if role == UserRole.ADMIN.value:
            pending = (await db.execute(select(func.count(User.id)).where(User.is_active.is_(False)))).scalar_one()
            kpis.append(_kpi("akun_menunggu", "Akun menunggu aktivasi", "akun", pending, 0, "max", None, None,
                             action="Verifikasi akun pengepul/driver/pabrik baru di Panel Admin.", fmt_target="0 akun"))

    scored = [k for k in kpis if k["status"] in STATUS_POINTS]
    score = None
    if scored:
        tw = sum(k["weight"] for k in scored)
        score = round(sum(STATUS_POINTS[k["status"]] * k["weight"] for k in scored) / tw)
    priorities = sorted(
        [k for k in kpis if k["status"] in SEVERITY],
        key=lambda k: (-SEVERITY[k["status"]], -_rp_impact(k), -k["weight"]))
    counts = {s: sum(1 for k in kpis if k["status"] == s) for s in ("baik", "perhatian", "kritis", "data_kurang", "info")}
    series = {k: [{"month": r["month"], "value": _get(r, k)} for r in rows]
              for k in [c["key"] for c in rep["columns"] if c.get("chart")]}
    flow = None
    if role in PLANT_ROLES:
        inp = _sum(cur_rows, "conversion.batch_input_kg")
        flow = {"input_kg": inp,
                "shares_pct": {p: _mean(cur_rows, f"conversion.{p}_pct")
                               for p in ("biochar", "bio_pellet", "bio_silika")},
                "closure_error_pct": closure,
                "biochar_to_farmers_kg": _sum(cur_rows, "conversion.biochar_to_farmers_kg")}
    return {
        "role": role,
        "scope": rep["scope"],
        "window": {"months": months[n:], "compare_to": months[:n], "length": n},
        "score": score,
        "grade": None if score is None else ("A" if score >= 85 else "B" if score >= 70 else "C" if score >= 50 else "D"),
        "counts": counts,
        "kpis": kpis,
        "priorities": [{"key": k["key"], "label": k["label"], "status": k["status"], "value": k["value"],
                        "unit": k["unit"], "target": k["target"], "target_label": k["target_label"],
                        "action": k["action"], "impact": k["impact"]} for k in priorities],
        "series": series,
        "flow": flow,
        "params_hint": "",
    }


def deterministic_markdown(ev: dict) -> str:
    """Ringkasan tanpa AI (dipakai saat provider AI tidak tersedia)."""
    lines = [f"### Ringkasan evaluasi ({', '.join(ev['window']['months'])})"]
    if ev["score"] is None:
        lines.append("Data belum cukup untuk memberi skor. Lengkapi data berikut:")
    else:
        lines.append(f"Skor kesehatan **{ev['score']}/100** (grade {ev['grade']}) — "
                     f"{ev['counts']['baik']} baik, {ev['counts']['perhatian']} perhatian, {ev['counts']['kritis']} kritis.")
    if ev["priorities"]:
        lines.append("\n### Prioritas optimasi")
        for i, p in enumerate(ev["priorities"], 1):
            imp = p["impact"]
            imp_s = ""
            if imp:
                imp_s = f" — dampak ±{'Rp' if imp['kind'] == 'rp' else ''}{imp['amount']:,.0f}" \
                        f"{'' if imp['kind'] == 'rp' else ' ' + imp['kind']} ({imp['note']})"
            lines.append(f"{i}. **{p['label']}**: {p['value']} {p['unit']} (target {p['target_label'] or p['target']})"
                         f"{imp_s}. {p['action'] or ''}")
    gaps = [k for k in ev["kpis"] if k["status"] == "data_kurang"]
    if gaps:
        lines.append("\n### Data yang perlu dilengkapi")
        lines += [f"- {k['label']}: {k['need']}" for k in gaps]
    return "\n".join(lines)
