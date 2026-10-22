"""Engine ⑩b — Prototipe 3 (fase 4): pemantauan SEC/IKE ternormalisasi & detektor anomali (ISO 50001/50006).

Data: log operasi per hari/shift — kWh (total, pengering, hammer mill), solar (L), bahan bakar biomassa (kg),
jam operasi, ton produk, kadar air umpan, kapasitas terpasang.

1. Energi masuk  E [MJ] = kWh·3,6 + solar[L]·NCV_solar + biomassa[kg]·LHV_ar,bahan bakar
   SEC_aktual = E / ton produk  (protokol)
2. Baseline energi (ISO 50006:2023, relevant variables): E ≈ β_h·jam + β_t·ton + β_w·air_diuapkan  (NNLS, β ≥ 0)
   β_h = beban tetap per jam operasi → SEC mentah wajar NAIK saat beban parsial (utilisasi rendah);
   EnPI = E_aktual / E_model menormalkan efek itu → tidak ada alarm palsu saat mesin di bawah beban penuh.
3. Anomali: residual relatif r = E/E_model − 1 dibanding rata-rata bergerak (jendela N) ± 2σ (peringatan) / ± 3σ (aksi)
   (Montgomery 2019) + CUSUM residual (Page 1954; k = 0,5σ, h = 5σ) untuk degradasi pelan (hammer aus, die aus).
4. Indikator pemborosan:
   - bahan basah: energi pengeringan akibat kadar air di atas acuan = β_w·(W − W_acuan) — "wajar" secara model
     (MC adalah relevant variable) tetapi dapat dikendalikan di hulu (refraksi pengepul, jemur, gudang beratap);
   - hammer mill: kWh/t vs median baseline (& literatur 13–20 kWh/t saringan 6,4 mm; 22–35 kWh/t 3,2 mm —
     Naimi & Sokhansanj 2018) → aus/gesekan bila naik tanpa kenaikan kadar air.
5. Rekomendasi audit energi mengacu klausul ISO 50001:2018 (6.3 tinjauan energi, 6.6 rencana pengumpulan data,
   8.1 pengendalian operasional, 9.1 pemantauan, 10.2 perbaikan berkelanjutan).
"""

from statistics import median

import numpy as np
from pydantic import BaseModel, Field
from scipy.optimize import nnls

KWH_MJ = 3.6
HAMMER_REF_KWH_T = (13.0, 20.0)          # saringan 6,4 mm — Naimi & Sokhansanj 2018 (docs/15 §8)


class OpsLog(BaseModel):
    label: str = Field(..., max_length=24, description="Tanggal/shift, mis. 2026-10-01 S1")
    kwh_total: float = Field(..., ge=0)
    kwh_dryer: float | None = Field(None, ge=0)
    kwh_hammer_mill: float | None = Field(None, ge=0)
    diesel_l: float = Field(0, ge=0)
    biomass_fuel_kg: float = Field(0, ge=0)
    operating_hours: float = Field(..., gt=0, le=24)
    product_ton: float = Field(..., gt=0)
    feed_moisture_pct: float | None = Field(None, ge=0, lt=95)
    rated_capacity_t_h: float | None = Field(None, gt=0)


class OpsAnalysisRequest(BaseModel):
    logs: list[OpsLog] = Field(..., min_length=8, max_length=2000)
    baseline_n: int = Field(14, ge=6, le=500, description="Jumlah log awal sebagai periode acuan (EnB)")
    window: int = Field(7, ge=3, le=60, description="Jendela rata-rata bergerak")
    sigma_warn: float = Field(2.0, gt=0, le=6)
    sigma_action: float = Field(3.0, gt=0, le=8)
    diesel_mj_per_l: float = Field(36.0, gt=0, le=60)
    biomass_fuel_mj_per_kg: float = Field(12.3, gt=0, le=35)
    product_moisture_pct: float = Field(10.0, ge=0, lt=60, description="Kadar air keluar pengering")
    reference_feed_moisture_pct: float | None = Field(None, ge=0, lt=95, description="MC acuan pembelian (refraksi)")
    tariff_rp_per_kwh: float = Field(1444.7, gt=0)
    drying_mj_per_kg_water: float = Field(3.0, ge=2.443, le=10, description="β_w fisika: energi pengering per kg air")
    idle_kw: float | None = Field(None, ge=0, le=100_000, description="Daya saat mesin jalan kosong (tang ampere) → beban tetap/jam")


def _water_t(product_ton: float, mc_in: float | None, mc_out: float) -> float:
    if mc_in is None or mc_in <= mc_out:
        return 0.0
    dry = product_ton * (1 - mc_out / 100)
    return dry * (mc_in / (100 - mc_in) - mc_out / (100 - mc_out))


def analyse(req: OpsAnalysisRequest) -> dict:
    logs = req.logs
    n = len(logs)
    nb = min(req.baseline_n, n - 2)
    E = np.array([l.kwh_total * KWH_MJ + l.diesel_l * req.diesel_mj_per_l + l.biomass_fuel_kg * req.biomass_fuel_mj_per_kg
                  for l in logs])
    H = np.array([l.operating_hours for l in logs])
    T = np.array([l.product_ton for l in logs])
    W = np.array([_water_t(l.product_ton, l.feed_moisture_pct, req.product_moisture_pct) for l in logs])
    # β_w dari fisika pengeringan (bukan regresi): kadar air acuan jarang bervariasi cukup untuk diestimasi
    beta_w = req.drying_mj_per_kg_water * 1000                      # MJ per ton air
    use_w = bool(W.any())
    E_adj = E - beta_w * W
    util_cv = float(np.std(T[:nb] / H[:nb]) / np.mean(T[:nb] / H[:nb]))
    notes = []
    if req.idle_kw is not None:                                       # beban tetap terukur → hanya β_t yang difit
        beta_h = req.idle_kw * KWH_MJ
        beta_t = max(0.0, float(np.sum((E_adj[:nb] - beta_h * H[:nb]) * T[:nb]) / np.sum(T[:nb] ** 2)))
        split = "daya idle terukur"
    elif util_cv >= 0.10:                                             # utilisasi cukup bervariasi → NNLS jam & ton
        (beta_h, beta_t), _ = nnls(np.column_stack([H[:nb], T[:nb]]), E_adj[:nb])
        split = "regresi (utilisasi acuan bervariasi)"
    else:
        beta_h, beta_t = 0.0, float(np.sum(E_adj[:nb]) / np.sum(T[:nb]))
        split = "tidak teridentifikasi"
        notes.append("Utilisasi di periode acuan hampir konstan dan daya idle tidak diisi: beban tetap tidak bisa dipisah, "
                     "sehingga log beban parsial bisa memicu alarm palsu. Ukur daya mesin saat jalan kosong (tang ampere) "
                     "dan isi 'daya idle', atau sertakan hari beban rendah di periode acuan.")
    beta = np.array([beta_h, beta_t, beta_w])
    expected = beta_h * H + beta_t * T + beta_w * W
    expected = np.where(expected > 1e-9, expected, np.nan)
    rel = E / expected - 1
    base_sd = float(np.nanstd(rel[:nb], ddof=1)) or 0.01
    base_r2 = 1 - float(np.nansum((E[:nb] - expected[:nb]) ** 2)) / float(np.sum((E[:nb] - E[:nb].mean()) ** 2) or 1)

    mc_list = [l.feed_moisture_pct for l in logs[:nb] if l.feed_moisture_pct is not None]
    mc_ref = req.reference_feed_moisture_pct if req.reference_feed_moisture_pct is not None else (median(mc_list) if mc_list else None)
    hm = [l.kwh_hammer_mill / l.product_ton for l in logs[:nb] if l.kwh_hammer_mill is not None]
    hm_ref = median(hm) if hm else None

    rows, alerts, cusum, k, h = [], [], 0.0, 0.5 * base_sd, 5 * base_sd
    accepted = [float(x) for x in rel[:nb] if not np.isnan(x)]           # residual "normal" (tanpa log beralarm)
    for i, l in enumerate(logs):
        past = np.array(accepted[-req.window:]) if i >= nb else np.array(accepted)
        ma, sd = (float(past.mean()), float(past.std(ddof=1))) if len(past) >= 3 else (0.0, base_sd)
        sd = max(sd, base_sd)                                        # jendela tenang tidak boleh mempersempit batas
        r = float(rel[i]) if not np.isnan(rel[i]) else 0.0
        level = "aksi" if r > ma + req.sigma_action * sd else ("peringatan" if r > ma + req.sigma_warn * sd else None)
        if i >= nb:
            cusum = max(0.0, cusum + r - k)
            if level is None:
                accepted.append(r)
        recent = [float(v) for v in rel[max(nb, i - 4):i + 1] if not np.isnan(v)]
        # median 5 log terakhir > 1σ: lonjakan tunggal tidak menggeser median, pergeseran nyata menggesernya
        persistent = i >= nb and len(recent) >= 3 and median(recent) > base_sd
        util = (l.product_ton / (l.rated_capacity_t_h * l.operating_hours)) if l.rated_capacity_t_h else None
        wet_mj = float(beta[2]) * max(0.0, W[i] - _water_t(l.product_ton, mc_ref, req.product_moisture_pct)) if use_w and mc_ref is not None else 0.0
        hm_kwh_t = l.kwh_hammer_mill / l.product_ton if l.kwh_hammer_mill is not None else None
        causes = []
        if level:
            excess_mj = float(E[i] - expected[i])
            causes.append({"code": "konsumsi_di_atas_baseline", "detail": f"Energi {r:+.1%} di atas model (batas {ma + req.sigma_warn * sd:+.1%}); "
                           f"kelebihan ≈ {excess_mj:,.0f} MJ ≈ Rp{excess_mj / KWH_MJ * req.tariff_rp_per_kwh:,.0f} (ekuivalen listrik)"})
        wet_feed = mc_ref is not None and l.feed_moisture_pct is not None and l.feed_moisture_pct >= mc_ref + 3
        if wet_feed and wet_mj > 0.05 * E[i]:
            causes.append({"code": "pengering_bahan_basah", "detail": f"Kadar air umpan {l.feed_moisture_pct:g} % vs acuan {mc_ref:g} %: "
                           f"±{wet_mj:,.0f} MJ ({wet_mj / E[i]:.0%} energi) habis untuk menguapkan air berlebih"})
        if hm_kwh_t is not None and hm_ref and hm_kwh_t > 1.25 * hm_ref:
            causes.append({"code": "hammer_mill_basah" if wet_feed else "hammer_mill_gesekan",
                           "detail": f"Hammer mill {hm_kwh_t:.1f} kWh/t vs baseline {hm_ref:.1f} (literatur 13–20 kWh/t saringan 6,4 mm)"
                                     + (" — bahan basah memperberat penggilingan" if wet_feed else
                                        " — kadar air normal: indikasi hammer tumpul, saringan sobek/tersumbat, bearing/sabuk aus")})
        if cusum > h and persistent and not any(a["code"] == "cusum_drift" for a in alerts):
            causes.append({"code": "cusum_drift", "detail": f"CUSUM residual melewati h = 5σ: pergeseran efisiensi persisten sejak ±{logs[max(nb, i - req.window)].label}"})
        row = {"label": l.label, "energy_mj": round(float(E[i]), 1), "expected_mj": round(float(expected[i]), 1),
               "sec_mj_per_t": round(float(E[i] / T[i]), 1), "sec_expected_mj_per_t": round(float(expected[i] / T[i]), 1),
               "enpi": round(float(E[i] / expected[i]), 3), "residual_pct": round(r * 100, 2),
               "band_warn_pct": round((ma + req.sigma_warn * sd) * 100, 2), "band_action_pct": round((ma + req.sigma_action * sd) * 100, 2),
               "moving_avg_pct": round(ma * 100, 2), "cusum": round(cusum, 4), "utilization": round(util, 3) if util is not None else None,
               "feed_moisture_pct": l.feed_moisture_pct, "wet_feed_mj": round(wet_mj, 1),
               "hammer_mill_kwh_t": round(hm_kwh_t, 2) if hm_kwh_t is not None else None,
               "alert": level, "baseline_period": i < nb, "causes": causes}
        rows.append(row)
        if causes and (level or any(c["code"] != "konsumsi_di_atas_baseline" for c in causes)):
            for c in causes:
                alerts.append({"label": l.label, "level": level or "indikator", **c})

    codes = {a["code"] for a in alerts}
    recs = _recommendations(codes, rows, mc_ref)
    sec_raw = [r["sec_mj_per_t"] for r in rows]
    return {
        "baseline": {"model": "E = β_h·jam + β_t·ton + β_w·air_diuapkan",
                     "beta_mj_per_hour": round(float(beta[0]), 2), "beta_mj_per_ton": round(float(beta[1]), 2),
                     "beta_mj_per_t_water": round(float(beta[2]), 1), "fixed_load_basis": split,
                     "utilization_cv_baseline": round(util_cv, 3), "notes": notes, "r2": round(base_r2, 3),
                     "n": nb, "residual_sd_pct": round(base_sd * 100, 2), "feed_moisture_ref_pct": mc_ref,
                     "hammer_mill_ref_kwh_t": round(hm_ref, 2) if hm_ref else None},
        "summary": {"logs": n, "alerts_action": sum(1 for r in rows if r["alert"] == "aksi"),
                    "alerts_warning": sum(1 for r in rows if r["alert"] == "peringatan"),
                    "sec_raw_mj_per_t_median": round(median(sec_raw), 1),
                    "enpi_last": rows[-1]["enpi"], "wet_feed_mj_total": round(sum(r["wet_feed_mj"] for r in rows), 0),
                    "cusum_last": rows[-1]["cusum"]},
        "rows": rows, "alerts": alerts, "recommendations": recs,
        "computation_details": {
            "energy": f"E = kWh·3,6 + solar·{req.diesel_mj_per_l:g} MJ/L + biomassa·{req.biomass_fuel_mj_per_kg:g} MJ/kg",
            "baseline": "EnB ISO 50006:2023: β_w = energi pengeringan per kg air (fisika, Thek & Obernberger 2004); "
                        "β_h dari daya idle terukur atau NNLS bila utilisasi acuan bervariasi; β_t dari regresi",
            "normalisation": "EnPI = E_aktual/E_model; SEC_expected = E_model/ton (beban parsial → SEC mentah naik, EnPI tetap)",
            "anomaly": f"residual relatif > rata-rata bergerak ({req.window}) + {req.sigma_warn:g}σ peringatan / {req.sigma_action:g}σ aksi",
            "cusum": "S_i = max(0, S_{i−1} + r_i − 0,5σ); alarm bila S > 5σ dan median 5 log terakhir > 1σ (Page 1954)",
            "references": ["ISO 50001:2018", "ISO 50006:2023", "Montgomery (2019) Intro. Statistical Quality Control 8th ed.",
                           "Page (1954) Biometrika 41:100–115", "Naimi & Sokhansanj (2018) hammer mill SEC",
                           "Thek & Obernberger (2004) Biomass Bioenergy 27:671 — pengering 2,9–4,0 MJ/kg air"],
        },
    }


def _recommendations(codes: set, rows: list, mc_ref) -> list[dict]:
    recs = []
    if "pengering_bahan_basah" in codes:
        recs.append({"priority": 1, "iso50001": "8.1 Pengendalian operasional · 6.3 Tinjauan energi (SEU pengering)",
                     "title": "Tekan kadar air bahan masuk",
                     "action": f"Perketat refraksi kadar air di pengepul (acuan {mc_ref:g} %), jemur di gudang beratap sebelum kirim, "
                               "dan tolak/turunkan harga lot basah — energi pengering dibayar pabrik untuk air, bukan biomassa.",
                     "kpi": "MJ pengering per kg air diuapkan & % lot di atas MC acuan"})
    if "hammer_mill_gesekan" in codes:
        recs.append({"priority": 2, "iso50001": "8.1 Pengendalian operasional · 10.2 Perbaikan berkelanjutan",
                     "title": "Perawatan hammer mill",
                     "action": "Balik/ganti hammer tumpul, periksa saringan sobek/tersumbat, cek bearing & ketegangan sabuk; "
                               "pasang magnet/penyaring batu di umpan (kotoran mempercepat aus).",
                     "kpi": "kWh/t hammer mill (target ≤ baseline; literatur 13–20 kWh/t saringan 6,4 mm)"})
    if "hammer_mill_basah" in codes:
        recs.append({"priority": 2, "iso50001": "8.1 Pengendalian operasional",
                     "title": "Keringkan sebelum digiling",
                     "action": "Urutan proses: pengering → hammer mill; SEC penggilingan naik tajam pada MC > 15 % (Liu dkk. 2016).",
                     "kpi": "kWh/t hammer mill pada MC umpan"})
    if "konsumsi_di_atas_baseline" in codes:
        recs.append({"priority": 3, "iso50001": "9.1 Pemantauan, pengukuran, analisis · 10.1 Ketidaksesuaian & tindakan korektif",
                     "title": "Investigasi log anomali",
                     "action": "Telusuri shift beranomali: motor/blower menyala saat idle, kebocoran udara tekan, start-stop berulang, "
                               "kesalahan pencatatan meter. Catat akar masalah & tindakan korektif.",
                     "kpi": "Jumlah log di atas batas 2σ per bulan"})
    if "cusum_drift" in codes:
        recs.append({"priority": 4, "iso50001": "10.2 Perbaikan berkelanjutan · 6.5 EnB (tinjau ulang baseline)",
                     "title": "Degradasi efisiensi persisten",
                     "action": "CUSUM terus naik: jadwalkan perawatan preventif menyeluruh (die pelet, isolasi pengering, burner). "
                               "Bila ada perubahan peralatan permanen, lakukan penyesuaian non-rutin baseline (ISO 50006).",
                     "kpi": "Kemiringan CUSUM"})
    low_util = [r for r in rows if r["utilization"] is not None and r["utilization"] < 0.6]
    if len(low_util) >= max(3, len(rows) // 4):
        recs.append({"priority": 5, "iso50001": "6.2 Sasaran energi · 8.1 Pengendalian operasional",
                     "title": "Kumpulkan bahan dulu, operasikan penuh",
                     "action": f"{len(low_util)} log beroperasi < 60 % kapasitas: beban tetap per jam membuat SEC mentah tinggi. "
                               "Jadwalkan produksi batch saat stok cukup (konsolidasi pasokan pengepul) daripada jalan setengah beban.",
                     "kpi": "Utilisasi kapasitas & SEC mentah"})
    if not recs:
        recs.append({"priority": 9, "iso50001": "9.1 Pemantauan", "title": "Kinerja energi stabil",
                     "action": "Tidak ada anomali signifikan. Lanjutkan pencatatan harian & tinjau baseline tiap 12 bulan.",
                     "kpi": "EnPI ≈ 1"})
    return sorted(recs, key=lambda r: r["priority"])
