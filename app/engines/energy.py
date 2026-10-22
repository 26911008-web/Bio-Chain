"""Engine ⑩ — Analitik Konsumsi Energi: IKE, SEC, baseline, anomali/pemborosan, rekomendasi efisiensi.

1. IKE (Intensitas Konsumsi Energi) = kWh / luas bangunan, dinilai dengan kriteria Permen ESDM
   No. 13/2012 (gedung ber-AC: <8,5 sangat efisien, 8,5–14 efisien, 14–18,5 cukup efisien, >18,5 boros
   kWh/m²/bulan; non-AC: 3,4 / 5,6 / 7,4).
2. SEC (Specific Energy Consumption) = kWh / ton bahan diproses — indikator utama industri.
3. Baseline energi (ISO 50006:2014): regresi linear kWh = a + b·produksi pada periode acuan. a = beban
   dasar (energi yang terpakai walau tidak berproduksi), b = energi variabel per ton.
4. Anomali: residu (aktual − baseline) dengan robust z-score (median/MAD, Iglewicz & Hoaglin 1993)
   > ambang; tren pemborosan dipantau dengan CUSUM residu.
"""

from statistics import median
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field

from ..params import P

IKE_CRITERIA = {   # kWh/m²/bulan — Permen ESDM 13/2012
    "ac": [(8.5, "Sangat efisien"), (14.0, "Efisien"), (18.5, "Cukup efisien"), (float("inf"), "Boros")],
    "non_ac": [(3.4, "Sangat efisien"), (5.6, "Efisien"), (7.4, "Cukup efisien"), (float("inf"), "Boros")],
}
ROBUST_Z_THRESHOLD = 2.5
MIN_POINTS = 6


class EnergyReading(BaseModel):
    period: str = Field(..., pattern=r"^\d{4}-\d{2}$", description="YYYY-MM")
    kwh: float = Field(..., ge=0, description="Total kWh fasilitas (proses + gedung)")
    building_kwh: float | None = Field(None, ge=0, description="kWh gedung/kantor (penerangan, AC) untuk IKE")
    production_ton: float = Field(0, ge=0)
    peak_kw: float | None = Field(None, ge=0)
    operating_hours: float | None = Field(None, gt=0, le=744)
    cost_rp: float | None = Field(None, ge=0)


class EnergyAnalysisRequest(BaseModel):
    facility: str = "Fasilitas"
    floor_area_m2: float = Field(..., gt=0, description="Luas gedung yang dilayani building_kwh")
    building_type: Literal["ac", "non_ac"] = "ac"
    tariff_rp_per_kwh: float = Field(default_factory=lambda: P("energi.tariff_rp_per_kwh"), gt=0,
                                     description="Tarif rata-rata (Rp/kWh) bila cost_rp kosong")
    baseline_months: int = Field(12, ge=MIN_POINTS, le=60, description="Jumlah bulan awal sebagai periode acuan")
    readings: list[EnergyReading] = Field(..., min_length=MIN_POINTS, max_length=240)


def classify_ike(ike_month: float, building_type: str) -> str:
    labels = ("Sangat efisien", "Efisien", "Cukup efisien")
    limits = [P(f"energi.ike_{building_type}_{i}") for i in (1, 2, 3)]
    return next((lbl for lim, lbl in zip(limits, labels) if ike_month < lim), "Boros")


def _robust_z(values: np.ndarray) -> np.ndarray:
    med = float(np.median(values))
    mad = float(np.median(np.abs(values - med)))
    scale = 1.4826 * mad if mad > 0 else (float(np.std(values)) or 1.0)
    return (values - med) / scale


def analyze(req: EnergyAnalysisRequest) -> dict:
    ROBUST_Z_THRESHOLD = P("energi.anomaly_z")
    rows = sorted(req.readings, key=lambda r: r.period)
    if len({r.period for r in rows}) != len(rows):
        raise ValueError("Periode ganda dalam data.")
    kwh = np.array([r.kwh for r in rows], float)
    ton = np.array([r.production_ton for r in rows], float)
    cost = np.array([r.cost_rp if r.cost_rp is not None else r.kwh * req.tariff_rp_per_kwh for r in rows], float)
    tariff = float(cost.sum() / kwh.sum()) if kwh.sum() > 0 else req.tariff_rp_per_kwh

    # 1. IKE — kriteria Permen ESDM untuk GEDUNG. Bila kWh gedung tidak dipisah, IKE hanya indikatif
    #    (beban mesin proses tidak boleh dinilai dengan kriteria gedung; gunakan SEC).
    has_building = all(r.building_kwh is not None for r in rows)
    ike_basis = np.array([r.building_kwh for r in rows], float) if has_building else kwh
    ike_month = ike_basis / req.floor_area_m2
    last12 = ike_month[-12:]
    ike_avg = float(last12.mean())
    ike_label = classify_ike(ike_avg, req.building_type) if has_building else "Indikatif (termasuk beban proses)"

    # 2. SEC
    sec = np.where(ton > 0, kwh / np.where(ton > 0, ton, 1), np.nan)

    # 3. Baseline regresi pada periode acuan
    nb = min(req.baseline_months, len(rows))
    ref_t, ref_k = ton[:nb], kwh[:nb]
    if np.ptp(ref_t) > 0:
        b, a = np.polyfit(ref_t, ref_k, 1)
        fitted = a + b * ref_t
        ss_res = float(((ref_k - fitted) ** 2).sum())
        ss_tot = float(((ref_k - ref_k.mean()) ** 2).sum())
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        model = "regresi kWh = a + b·ton"
    else:                                         # produksi konstan/kosong → baseline rata-rata
        a, b, r2, model = float(ref_k.mean()), 0.0, 0.0, "rata-rata (produksi tidak bervariasi)"
    expected = a + b * ton
    resid = kwh - expected
    z = _robust_z(resid)
    cusum = np.cumsum(resid)

    anomalies = []
    for i, r in enumerate(rows):
        if z[i] > ROBUST_Z_THRESHOLD:
            anomalies.append({"period": r.period, "kwh": round(float(kwh[i])), "expected_kwh": round(float(expected[i])),
                              "excess_kwh": round(float(resid[i])), "excess_rp": round(float(resid[i]) * tariff),
                              "robust_z": round(float(z[i]), 2)})
        elif z[i] < -ROBUST_Z_THRESHOLD:
            anomalies.append({"period": r.period, "kwh": round(float(kwh[i])), "expected_kwh": round(float(expected[i])),
                              "excess_kwh": round(float(resid[i])), "excess_rp": round(float(resid[i]) * tariff),
                              "robust_z": round(float(z[i]), 2), "type": "di bawah baseline (cek meter/data)"})
    waste = [x for x in anomalies if x["excess_kwh"] > 0]

    # 4. Rekomendasi efisiensi (berbasis bukti dari data)
    recs = []
    mean_kwh = float(kwh.mean())
    base_share = float(a / mean_kwh) if mean_kwh > 0 else 0.0
    if waste:
        total = sum(x["excess_kwh"] for x in waste)
        recs.append({"priority": 1, "title": "Telusuri bulan pemborosan",
                     "detail": f"{len(waste)} bulan melebihi baseline secara signifikan ({', '.join(x['period'] for x in waste)}); "
                               f"kelebihan {total:,.0f} kWh ≈ Rp{total * tariff:,.0f}. Cek kebocoran udara tekan, "
                               "motor/blower yang menyala saat tidak produksi, dan log perawatan bulan tersebut.",
                     "potential_kwh_per_year": round(total * 12 / len(rows))})
    if base_share > P("energi.base_load_alert_share"):
        save = 0.2 * a * 12
        recs.append({"priority": 2, "title": "Turunkan beban dasar (base load)",
                     "detail": f"Beban dasar {a:,.0f} kWh/bulan = {base_share:.0%} konsumsi rata-rata — energi terpakai "
                               "walau tanpa produksi. Terapkan jadwal mati otomatis (blower, kompresor, penerangan), "
                               "dan audit peralatan standby. Asumsi penghematan 20% beban dasar.",
                     "potential_kwh_per_year": round(save)})
    valid_sec = sec[~np.isnan(sec)]
    if len(valid_sec) >= MIN_POINTS:
        trend = np.polyfit(np.arange(len(valid_sec)), valid_sec, 1)[0]
        if trend > 0 and trend * 12 / float(np.mean(valid_sec)) > 0.03:
            recs.append({"priority": 3, "title": "SEC memburuk dari waktu ke waktu",
                         "detail": f"SEC naik ≈{trend * 12:,.1f} kWh/ton per tahun. Indikasi penurunan kinerja peralatan "
                                   "(bearing, sabuk, filter tersumbat) atau umpan lebih basah; jadwalkan perawatan "
                                   "preventif & pantau kadar air umpan.", "potential_kwh_per_year": None})
    peaks = [(r.peak_kw, r.kwh, r.operating_hours) for r in rows if r.peak_kw and r.operating_hours]
    if peaks:
        lf = float(np.mean([k / (p * h) for p, k, h in peaks]))
        if lf < 0.5:
            recs.append({"priority": 4, "title": "Ratakan beban puncak",
                         "detail": f"Faktor beban rata-rata {lf:.2f} (< 0,5): puncak jauh di atas rata-rata. Geser start "
                                   "motor besar bergiliran (soft starter/VSD) untuk menurunkan biaya kVA/daya terpasang.",
                         "potential_kwh_per_year": None})
    if ike_label in ("Cukup efisien", "Boros"):
        recs.append({"priority": 5, "title": f"IKE kategori {ike_label}",
                     "detail": f"IKE rata-rata {ike_avg:.1f} kWh/m²/bulan. Prioritaskan audit energi rinci "
                               "(SNI 6196:2011) pada sistem pendingin, penerangan, dan motor listrik.",
                     "potential_kwh_per_year": None})
    if not recs:
        recs.append({"priority": 9, "title": "Kinerja stabil",
                     "detail": "Tidak ada pemborosan signifikan. Lanjutkan pemantauan CUSUM bulanan.",
                     "potential_kwh_per_year": None})

    series = [{"period": r.period, "kwh": round(float(kwh[i])), "production_ton": float(ton[i]),
               "expected_kwh": round(float(expected[i])), "residual_kwh": round(float(resid[i])),
               "cusum_kwh": round(float(cusum[i])), "sec_kwh_per_ton": None if np.isnan(sec[i]) else round(float(sec[i]), 1),
               "ike_kwh_m2": round(float(ike_month[i]), 2), "robust_z": round(float(z[i]), 2),
               "is_anomaly": abs(float(z[i])) > ROBUST_Z_THRESHOLD} for i, r in enumerate(rows)]
    return {
        "facility": req.facility,
        "summary": {
            "months": len(rows), "total_kwh": round(float(kwh.sum())), "total_cost_rp": round(float(cost.sum())),
            "ike_kwh_m2_month_avg_12m": round(ike_avg, 2), "ike_kwh_m2_year": round(float(last12.sum()) * 12 / len(last12), 1),
            "ike_category": ike_label, "building_type": req.building_type, "ike_basis": "kWh gedung"
            if has_building else "kWh total (pisahkan kWh gedung untuk penilaian resmi)",
            "sec_kwh_per_ton_avg": round(float(np.nanmean(sec)), 1) if len(valid_sec) else None,
            "sec_kwh_per_ton_median": round(float(median(valid_sec)), 1) if len(valid_sec) else None,
            "anomaly_months": len(anomalies), "waste_kwh": round(sum(x["excess_kwh"] for x in waste)),
            "waste_rp": round(sum(x["excess_rp"] for x in waste)),
        },
        "baseline": {"model": model, "base_load_kwh_per_month": round(float(a)), "kwh_per_ton": round(float(b), 2),
                     "r2": round(float(r2), 3), "reference_months": nb, "base_load_share": round(base_share, 3)},
        "anomalies": anomalies,
        "recommendations": sorted(recs, key=lambda r: r["priority"]),
        "series": series,
        "computation_details": {
            "ike": f"IKE = kWh gedung / {req.floor_area_m2:g} m²; kriteria Permen ESDM 13/2012 ({req.building_type}). "
                   "Beban proses dinilai dengan SEC, bukan IKE.",
            "sec": "SEC = kWh / ton bahan diproses",
            "baseline": f"OLS pada {nb} bulan acuan (ISO 50006:2014)",
            "anomaly": f"robust z = (residu − median) / (1,4826·MAD) > {ROBUST_Z_THRESHOLD} (Iglewicz & Hoaglin 1993)",
            "cusum": "Σ(aktual − baseline): kemiringan naik = pemborosan berkelanjutan",
            "tariff_rp_per_kwh": round(tariff, 1),
        },
    }
