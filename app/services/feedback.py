"""Umpan balik mutu untuk petani: kurva bulanan QC pengepul & QC pabrik, defect rate dan penyebabnya.

- QC pengepul = per lot (harvests.quality_score/moisture/grade) — paling dekat dengan praktik petani.
- QC pabrik   = per muatan pengepul (inbound_qc lewat harvests.delivery_request_id). Satu muatan bisa berisi lot
  beberapa petani, jadi nilainya ditandai "muatan gabungan" — indikasi, bukan nilai lot petani itu sendiri.
- Defect = lot ditolak pengepul/pabrik + kasus retur (return_cases). Penyebab memakai kategori terstruktur;
  data lama tanpa kategori dikelompokkan dari kata kunci alasan bebas.
Pengelompokan bulan dikerjakan di Python agar sama di SQLite & PostgreSQL.
"""

from collections import Counter, defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.factory_ops import InboundQC, ReturnCase
from ..models.harvest import Harvest, HarvestStatus

CAUSE_LABELS = {
    "basah": "Terlalu basah (kadar air tinggi)", "berjamur": "Berjamur / berbau", "kontaminan": "Kontaminan (pasir, jerami, plastik)",
    "selisih_berat": "Selisih berat vs taksiran", "stok_tidak_ada": "Stok tidak ada saat dijemput",
    "dibatalkan_pengepul": "Dibatalkan pengepul", "lainnya": "Lainnya",
}
_KEYWORDS = (("jamur", "berjamur"), ("basah", "basah"), ("air", "basah"), ("lembap", "basah"), ("kontam", "kontaminan"),
             ("pasir", "kontaminan"), ("kotor", "kontaminan"), ("berat", "selisih_berat"), ("tidak ada", "stok_tidak_ada"),
             ("dibatalkan_pengepul", "dibatalkan_pengepul"))
TIPS = {
    "basah": "Jemur sekam 1–2 hari terik & simpan beralas terpal/palet; target kadar air ≤ 12% (Grade A).",
    "berjamur": "Jangan simpan sekam basah > 3 hari dalam karung tertutup; beri sirkulasi udara di gudang.",
    "kontaminan": "Pisahkan sekam dari debu lantai/jerami; gunakan karung bersih, jangan disapu dari tanah.",
    "selisih_berat": "Timbang ulang sebelum lapor atau isi taksiran lebih hati-hati; selisih besar menurunkan kepercayaan.",
    "stok_tidak_ada": "Batalkan laporan lewat aplikasi bila stok sudah terjual, agar truk tidak berangkat sia-sia.",
}


def _v(e):
    return e.value if hasattr(e, "value") else e


def _aware(d: datetime | None) -> datetime | None:
    return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)


def _cause(category: str | None, reason: str | None) -> str:
    if category:
        return category
    text = (reason or "").lower()
    for kw, cat in _KEYWORDS:
        if kw in text:
            return cat
    return "lainnya"


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 1) if xs else None


async def farmer_quality_feedback(db: AsyncSession, farmer_id: int, months: int = 6) -> dict:
    now = datetime.now(timezone.utc)
    idx = now.year * 12 + now.month - 1 - (months - 1)            # aritmetika bulan (bukan pengurangan hari)
    first = datetime(idx // 12, idx % 12 + 1, 1, tzinfo=timezone.utc)
    keys = []
    y, m = first.year, first.month
    for _ in range(months):
        keys.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)

    hs = (await db.execute(select(Harvest).where(Harvest.farmer_id == farmer_id, Harvest.reported_at >= first))).scalars().all()
    req_ids = {h.delivery_request_id for h in hs if h.delivery_request_id}
    qcs = {q.request_id: q for q in (await db.execute(select(InboundQC).where(InboundQC.request_id.in_(req_ids)))).scalars()} \
        if req_ids else {}
    rets = (await db.execute(select(ReturnCase).where(ReturnCase.harvest_id.in_([h.id for h in hs])))).scalars().all() \
        if hs else []
    ret_by_h = defaultdict(list)
    for r in rets:
        ret_by_h[r.harvest_id].append(r)

    b = {k: {"col_scores": [], "col_moist": [], "fac_scores": [], "fac_moist": [], "assessed": 0, "defects": 0,
             "assessed_kg": 0.0, "defect_kg": 0.0, "grades": Counter(), "est_err": []} for k in keys}
    causes, cause_by_month = Counter(), defaultdict(Counter)
    for h in hs:
        when = _aware(h.verified_at or h.rejected_at or h.reported_at)
        k = when.strftime("%Y-%m") if when else None
        if k not in b:
            continue
        st = _v(h.status)
        row = b[k]
        if st == HarvestStatus.REPORTED.value:
            continue                                   # belum dinilai siapa pun
        if st == HarvestStatus.REJECTED.value and _cause(h.reject_category, h.rejected_reason) == "dibatalkan_pengepul":
            continue                                   # batal sepihak pengepul ≠ cacat mutu petani
        row["assessed"] += 1
        kg = h.verified_kg or h.quantity_kg or 0
        row["assessed_kg"] += kg
        if h.quality_score is not None:
            row["col_scores"].append(h.quality_score)
        if h.moisture is not None:
            row["col_moist"].append(h.moisture)
            if h.farmer_moisture_est is not None:
                row["est_err"].append(abs(h.farmer_moisture_est - h.moisture))
        if h.grade:
            row["grades"][_v(h.grade)] += 1
        q = qcs.get(h.delivery_request_id)
        if q is not None:
            row["fac_scores"].append(q.score)
            row["fac_moist"].append(q.moisture)
        defect_causes = []
        if st == HarvestStatus.REJECTED.value:
            defect_causes.append(_cause(h.reject_category, h.rejected_reason))
        defect_causes += [_v(r.reason_code) for r in ret_by_h.get(h.id, [])]
        if defect_causes:
            row["defects"] += 1
            row["defect_kg"] += kg
            for c in set(defect_causes):
                causes[c] += 1
                cause_by_month[k][c] += 1

    series = []
    for k in keys:
        r = b[k]
        series.append({
            "month": k, "lots_assessed": r["assessed"],
            "collector_qc_score": _avg(r["col_scores"]), "collector_moisture": _avg(r["col_moist"]),
            "factory_qc_score": _avg(r["fac_scores"]), "factory_moisture": _avg(r["fac_moist"]),
            "defect_lots": r["defects"],
            "defect_rate_pct": round(r["defects"] / r["assessed"] * 100, 1) if r["assessed"] else None,
            "defect_rate_kg_pct": round(r["defect_kg"] / r["assessed_kg"] * 100, 1) if r["assessed_kg"] else None,
            "grade_mix": dict(r["grades"]),
            "estimate_moisture_error": _avg(r["est_err"]),
            "causes": dict(cause_by_month[k]),
        })
    total_assessed = sum(s["lots_assessed"] for s in series)
    total_defects = sum(s["defect_lots"] for s in series)
    top = [{"cause": c, "label": CAUSE_LABELS.get(c, c), "lots": n, "tip": TIPS.get(c)} for c, n in causes.most_common()]
    return {
        "months": keys, "series": series,
        "summary": {"lots_assessed": total_assessed, "defect_lots": total_defects,
                    "defect_rate_pct": round(total_defects / total_assessed * 100, 1) if total_assessed else None},
        "causes": top,
        "notes": ["QC pabrik dinilai per muatan pengepul (bisa gabungan beberapa petani) — dipakai sebagai indikasi.",
                  "Defect = lot ditolak + kasus retur. Persentase dihitung dari lot yang sudah dinilai."],
    }
