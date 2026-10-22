"""Optimasi & efisiensi tiap proses rantai pasok sekam → biochar, dengan penghematan Rp & dampak lingkungan (kgCO₂e).

Tiga lapis, sengaja dipisah agar tidak terhitung ganda:
  1. TEREALISASI OTOMATIS — dihitung dari data operasional (bukan klaim): km dihemat optimasi rute vs baseline,
     biochar yang sudah diserahkan ke sawah, pembakaran terbuka yang dihindari.
  2. TERCATAT — aksi perbaikan yang dicatat manusia di register `efficiency_actions` (dengan bukti & verifikasi).
  3. POTENSI — selisih KPI aktual vs target (parameter) per proses, dikonversi ke Rp & kgCO₂e, plus rekomendasi.
Semua faktor dari menu Parameter (logistik.*, karbon.*, energi.*, harga_mutu.*, pasar.*, evaluasi.*, pabrik.*).
"""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..engines.emission import fuel_factors
from ..models.circular import EFFICIENCY_PROCESSES, EFFICIENCY_STATUSES, BiocharRedemption, EfficiencyAction
from ..models.compliance import FarmerPayment
from ..models.harvest import Harvest, HarvestStatus
from ..models.route import RouteStop
from ..models.user import User
from ..params import P

PROCESS_LABEL = {
    "lapor_stok": "Lapor stok petani", "uji_mutu": "Uji mutu & timbang pengepul", "jemput_rute": "Jemput & rute truk",
    "angkut": "Angkut ke pabrik", "terima_pabrik": "Terima & QC pabrik", "produksi": "Produksi pirolisis",
    "energi": "Energi pabrik", "pembayaran": "Pembayaran petani", "biochar_sawah": "Biochar kembali ke sawah",
    "lainnya": "Lainnya",
}


def _v(e):
    return e.value if hasattr(e, "value") else e


def _aware(d):
    return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)


def _fuel_avg_l_per_km() -> float:
    return (P("logistik.fuel_l_per_km_empty") + P("logistik.fuel_l_per_km_full")) / 2


def action_dict(a: EfficiencyAction) -> dict:
    return {"id": a.id, "process": a.process, "process_label": PROCESS_LABEL.get(a.process, a.process), "title": a.title,
            "description": a.description, "metric": a.metric, "baseline_value": a.baseline_value,
            "current_value": a.current_value, "saving_rp": a.saving_rp, "saving_co2e_kg": a.saving_co2e_kg,
            "period": a.period, "status": a.status, "evidence": a.evidence, "source_opportunity": a.source_opportunity,
            "created_at": a.created_at.isoformat() if a.created_at else None}


async def efficiency_overview(db: AsyncSession, start: datetime, end: datetime) -> dict:
    from .esg import green_scorecard_for, scorecard_inputs
    d = await scorecard_inputs(db, start, end)
    sc = await green_scorecard_for(db, start, end)
    wtw = fuel_factors()["wtw_kg_per_l"]
    l_km = _fuel_avg_l_per_km()
    cost_km = P("logistik.cost_per_km")
    routes = d["route_objs"]
    husk_t = sum(b["input_kg"] for b in d["batches"]) / 1000

    realized, potential = [], []

    # ---- 1. Jemput & rute: km dihemat optimasi (baseline vs rencana) — TEREALISASI
    with_base = [r for r in routes if r.baseline_km and r.total_km is not None]
    km_saved = sum(max(0.0, r.baseline_km - r.total_km) for r in with_base)
    realized.append({"code": "R1", "process": "jemput_rute", "title": "Optimasi rute (OR-Tools/CVRP) vs rute naif",
                     "quantity": round(km_saved, 1), "unit": "km dihemat", "saving_rp": round(km_saved * cost_km),
                     "saving_co2e_kg": round(km_saved * l_km * wtw, 1), "fuel_l_saved": round(km_saved * l_km, 1),
                     "basis": f"{len(with_base)} rute selesai: Σ(baseline_km − total_km) × {cost_km:g} Rp/km; "
                              f"× {l_km:.3f} L/km × {wtw:.3f} kgCO₂e/L (WTW B{fuel_factors()['blend_pct']:.0f})"})

    # ---- 2. Biochar ke sawah — TEREALISASI (manfaat petani + karbon tersimpan)
    red = (await db.execute(select(BiocharRedemption).where(BiocharRedemption.status == "diserahkan",
                                                            BiocharRedemption.handed_over_at >= start,
                                                            BiocharRedemption.handed_over_at < end))).scalars().all()
    red_kg = sum(r.kg for r in red)
    farmer_rp = sum((r.estimate or {}).get("net_benefit_rp") or 0 for r in red)
    c_kg = red_kg * P("biochar_sawah.carbon_frac") * P("biochar_sawah.stable_frac_100y") * 44 / 12
    realized.append({"code": "R2", "process": "biochar_sawah", "title": "Biochar diserahkan ke sawah petani",
                     "quantity": round(red_kg, 1), "unit": "kg biochar", "saving_rp": round(farmer_rp),
                     "saving_co2e_kg": round(c_kg, 1),
                     "basis": "manfaat bersih perkiraan petani (rumus docs/08) + karbon tersimpan F_C×F_perm×44/12 "
                              "— karbon dicatat proyek pabrik, jangan dijual ganda"})

    # ---- 3. Pembakaran terbuka dihindari — TEREALISASI (dampak lingkungan)
    realized.append({"code": "R3", "process": "produksi", "title": "Biomassa diolah, tidak dibakar terbuka",
                     "quantity": round(husk_t, 2), "unit": "t biomassa", "saving_rp": 0,
                     "saving_co2e_kg": round(sc["carbon_tco2e"]["avoided_open_burning"] * 1000, 1),
                     "basis": "IPCC 2006 Vol.4 — CH₄ & N₂O pembakaran residu (dilaporkan terpisah dari emisi bruto)"})

    # ---- Potensi P1: utilisasi bak truk di bawah target
    util = [r.utilization_pct for r in routes if r.utilization_pct]
    target_u = P("evaluasi.vehicle_utilization_min_pct")
    if util:
        avg_u = sum(util) / len(util)
        km_total = sum((r.actual_km or r.total_km or 0) for r in routes)
        gap = max(0.0, 1 - avg_u / target_u) if target_u else 0
        km_pot = km_total * gap
        potential.append({"code": "P1", "process": "jemput_rute", "kpi": "Utilisasi bak rata-rata",
                          "actual": round(avg_u, 1), "target": target_u, "unit": "% volume",
                          "saving_rp": round(km_pot * cost_km), "saving_co2e_kg": round(km_pot * l_km * wtw, 1),
                          "status": "baik" if gap == 0 else "perhatian",
                          "recommendation": "Gabungkan jemputan per klaster desa & tunda lot kecil sampai bak ≥ target; "
                                            "padatkan/press biomassa (bulk density naik) agar trip berkurang."})

    # ---- P2: deviasi GPS (jarak nyata > rencana)
    dev = [(r.actual_km - r.total_km) for r in routes if r.actual_km and r.total_km and r.actual_km > r.total_km * 1.1]
    if routes:
        km_dev = sum(dev)
        potential.append({"code": "P2", "process": "angkut", "kpi": "Jarak nyata melebihi rencana >10%",
                          "actual": len(dev), "target": 0, "unit": "rute", "saving_rp": round(km_dev * cost_km),
                          "saving_co2e_kg": round(km_dev * l_km * wtw, 1), "status": "baik" if not dev else "perhatian",
                          "recommendation": "Ikuti urutan stop dari aplikasi; laporkan jalan rusak/banjir agar matriks jarak "
                                            "diperbarui; cek rute sopir yang sering menyimpang."})

    # ---- P3: stop jemput gagal (trip sia-sia)
    rids = [r.id for r in routes]
    if rids:
        stops = (await db.execute(select(RouteStop).where(RouteStop.route_id.in_(rids)))).scalars().all()
        failed = [s for s in stops if s.stop_status == "failed"]
        km_per_stop = (sum(r.total_km or 0 for r in routes) / len(stops)) if stops else 0
        km_fail = len(failed) * km_per_stop
        potential.append({"code": "P3", "process": "jemput_rute", "kpi": "Stop jemput gagal",
                          "actual": round(len(failed) / len(stops) * 100, 1) if stops else 0,
                          "target": round(100 - P("evaluasi.stop_success_min_pct"), 1), "unit": "% stop",
                          "saving_rp": round(km_fail * cost_km), "saving_co2e_kg": round(km_fail * l_km * wtw, 1),
                          "status": "baik" if not failed else "perhatian",
                          "recommendation": "Konfirmasi stok via WhatsApp H-1 sebelum truk berangkat; petani membatalkan "
                                            "laporan di aplikasi bila stok sudah terjual."})

    # ---- P4: lot ditolak (nilai hilang + angkut sia-sia bila ditolak setelah diangkut)
    rej = (await db.execute(select(Harvest).where(Harvest.status == HarvestStatus.REJECTED, Harvest.rejected_at >= start,
                                                  Harvest.rejected_at < end))).scalars().all()
    rej = [h for h in rej if h.reject_category != "dibatalkan_pengepul"]
    rej_kg = sum(h.verified_kg or h.quantity_kg or 0 for h in rej)
    t_per_t = (sc["carbon_tco2e"]["transport_kg_per_ton_husk"] or 0)
    hauled = [h for h in rej if (h.rejected_reason or "").startswith("QC pabrik")]
    hauled_kg = sum(h.verified_kg or h.quantity_kg or 0 for h in hauled)
    assessed = (await db.execute(select(func.count(Harvest.id)).where(Harvest.verified_at >= start, Harvest.verified_at < end))).scalar() or 0
    rate = len(rej) / (assessed + len(rej)) * 100 if (assessed + len(rej)) else 0
    potential.append({"code": "P4", "process": "uji_mutu", "kpi": "Lot biomassa ditolak",
                      "actual": round(rate, 1), "target": P("evaluasi.reject_max_pct"), "unit": "% lot",
                      "saving_rp": round(rej_kg * P("harga_mutu.base_price_per_kg")),
                      "saving_co2e_kg": round(hauled_kg / 1000 * t_per_t, 1),
                      "status": "baik" if rate <= P("evaluasi.reject_max_pct") else "kritis",
                      "recommendation": "Moisture meter murah di kelompok tani + jemur 1–2 hari; tolak di sumber (sebelum "
                                        "diangkut) agar emisi angkut tidak terbuang. Lihat penyebab di laporan petani."})

    # ---- P5: susut timbang di atas toleransi
    tol = P("sirkular.shrinkage_tolerance_pct")
    sh = (await db.execute(select(Harvest).where(Harvest.shrinkage_pct.is_not(None), Harvest.delivered_at >= start,
                                                 Harvest.delivered_at < end))).scalars().all()
    excess = sum(max(0.0, (h.shrinkage_pct - tol)) / 100 * (h.verified_kg or 0) for h in sh)
    potential.append({"code": "P5", "process": "angkut", "kpi": "Susut di atas toleransi", "actual": round(excess, 1),
                      "target": 0, "unit": "kg", "saving_rp": round(excess * P("pasar.default_resale_price_per_kg")),
                      "saving_co2e_kg": 0, "status": "baik" if excess < 1 else "perhatian",
                      "recommendation": "Karung/terpal penutup bak (tumpahan & angin), timbangan terkalibrasi di kedua sisi, "
                                        "foto timbangan sebagai bukti serah-terima."})

    # ---- P6: energi proses (SEC) di atas target
    kwh = sum(b.get("kwh") or 0 for b in d["batches"])
    target_sec = P("pabrik.kwh_per_ton_input")
    if husk_t > 0 and kwh > 0:
        sec = kwh / husk_t
        ex = max(0.0, sec - target_sec) * husk_t
        potential.append({"code": "P6", "process": "energi", "kpi": "Listrik per ton biomassa (SEC)", "actual": round(sec, 1),
                          "target": target_sec, "unit": "kWh/t", "saving_rp": round(ex * P("energi.tariff_rp_per_kwh")),
                          "saving_co2e_kg": round(ex * P("karbon.grid_ef_kg_co2_per_kwh"), 1),
                          "status": "baik" if ex == 0 else "perhatian",
                          "recommendation": "Pakai syngas pirolisis untuk pengering; jadwalkan batch penuh (hindari start-stop); "
                                            "VFD pada blower & konveyor."})

    # ---- P7: valorisasi massa & residu
    val = sc["circularity"]["mass_valorization_pct"]
    if val is not None:
        potential.append({"code": "P7", "process": "produksi", "kpi": "Valorisasi massa (produk ÷ input)", "actual": val,
                          "target": None, "unit": "%", "saving_rp": None, "saving_co2e_kg": None, "status": "info",
                          "recommendation": "Residu ekstraksi silika → bahan semen/bata; abu terbang → amelioran tanah; "
                                            "catat kg bahan kimia per batch agar E-factor & PMI terukur."})

    # ---- P8: pembayaran petani terlambat (sosial)
    due = int(P("pasar.farmer_payment_due_days") or 0)
    pays = (await db.execute(select(FarmerPayment, Harvest.verified_at).join(Harvest, Harvest.id == FarmerPayment.harvest_id)
                             .where(FarmerPayment.paid_at >= start, FarmerPayment.paid_at < end))).all()
    late = sum(1 for p, v in pays if v and (_aware(p.paid_at) - _aware(v)).days > due)
    potential.append({"code": "P8", "process": "pembayaran", "kpi": "Pembayaran petani terlambat",
                      "actual": late, "target": 0, "unit": "lot", "saving_rp": None, "saving_co2e_kg": None,
                      "status": "baik" if not late else "perhatian",
                      "recommendation": "Bayar via QRIS/transfer saat timbang; kuitansi BYR otomatis; pantau daftar 'Bayar petani'."})

    # ---- Tercatat (register manusia)
    acts = (await db.execute(select(EfficiencyAction).order_by(EfficiencyAction.id.desc()).limit(200))).scalars().all()
    counted = [a for a in acts if a.status in ("berjalan", "terverifikasi")]

    def tot(rows, k):
        return round(sum((r.get(k) if isinstance(r, dict) else getattr(r, k)) or 0 for r in rows))

    return {
        "period": {"from": start.date().isoformat(), "to": end.date().isoformat()},
        "realized": realized, "potential": potential, "actions": [action_dict(a) for a in acts],
        "realized_totals": {"saving_rp": tot(realized, "saving_rp"), "saving_co2e_kg": tot(realized, "saving_co2e_kg")},
        "recorded_totals": {"saving_rp": tot(counted, "saving_rp"), "saving_co2e_kg": tot(counted, "saving_co2e_kg"),
                            "verified": sum(1 for a in counted if a.status == "terverifikasi"), "count": len(counted)},
        "potential_totals": {"saving_rp": tot(potential, "saving_rp"), "saving_co2e_kg": tot(potential, "saving_co2e_kg")},
        "processes": PROCESS_LABEL,
        "notes": ["Terealisasi otomatis dihitung dari data & tidak perlu dicatat ulang di register.",
                  "Register hanya menjumlah aksi berstatus berjalan/terverifikasi.",
                  "Potensi = selisih ke target parameter; bukan janji, prioritaskan yang berstatus kritis."],
    }


async def create_action(db: AsyncSession, user: User, data: dict) -> dict:
    if data["process"] not in EFFICIENCY_PROCESSES:
        raise HTTPException(422, f"process harus salah satu: {', '.join(EFFICIENCY_PROCESSES)}")
    a = EfficiencyAction(**data, created_by_id=user.id)
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return action_dict(a)


async def update_action_status(db: AsyncSession, user: User, action_id: int, status: str, evidence: str | None,
                               saving_rp: float | None, saving_co2e_kg: float | None) -> dict:
    if status not in EFFICIENCY_STATUSES:
        raise HTTPException(422, f"status harus salah satu: {', '.join(EFFICIENCY_STATUSES)}")
    a = (await db.execute(select(EfficiencyAction).where(EfficiencyAction.id == action_id).with_for_update())).scalar_one_or_none()
    if a is None:
        raise HTTPException(404, "Aksi tidak ditemukan")
    if status == "terverifikasi":
        if not (evidence or a.evidence):
            raise HTTPException(422, "Verifikasi wajib menyertakan bukti (foto meter, nota BBM, laporan rute).")
        if a.created_by_id == user.id and _v(user.role) != "admin":
            raise HTTPException(403, "Verifikasi oleh orang lain (empat mata) — minta admin/auditor internal.")
        a.verified_by_id = user.id
    a.status = status
    if evidence:
        a.evidence = evidence
    if saving_rp is not None:
        a.saving_rp = saving_rp
    if saving_co2e_kg is not None:
        a.saving_co2e_kg = saving_co2e_kg
    a.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return action_dict(a)
