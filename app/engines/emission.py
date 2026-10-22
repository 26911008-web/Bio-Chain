"""Engine ⑫ — Emisi Logistik Hijau (ISO 14083:2023 / GLEC Framework v3.2).

Menghitung jejak karbon angkutan sekam dari JARAK NYATA (jejak GPS yang tersinkron setelah offline) atau,
bila jejak tidak ada, dari urutan stop rencana. Pendekatan berbasis bahan bakar (fuel-based, data primer
diutamakan ISO 14083):

  BBM_segmen (L)   = km × [f_kosong + (f_penuh − f_kosong) × muatan/muatan_maks]      (linear, GLEC/HBEFA)
  EF_campuran      = (1−b)·(TTW_solar + WTT_solar) + b·WTW_FAME        (b = porsi biodiesel, mis. B40)
  CO₂e_WTW (kg)    = Σ BBM × EF_campuran
  Intensitas       = CO₂e_WTW ÷ t·km bermuatan  (perjalanan kosong TETAP dihitung & dibebankan ke t·km bermuatan)
  Per ton sekam    = CO₂e_WTW ÷ ton sekam terangkut

Pembersihan jejak GPS (praktik umum; ambang dari menu Parameter):
  1. buang titik dengan radius akurasi > gps_max_accuracy_m;
  2. buang titik yang menyiratkan kecepatan > gps_max_speed_kmh dari titik sah sebelumnya (glitch);
  3. abaikan langkah < gps_min_step_m (jitter saat diam);
  4. celah > 5 menit tanpa titik (GPS/aplikasi mati) diisi jarak lurus × faktor jalan, ditandai estimasi.

Modul murni komputasi: tidak bergantung FastAPI/DB.
"""

import math
from dataclasses import dataclass
from datetime import datetime

from ..params import P

EARTH_RADIUS_KM = 6371.0088          # radius rerata IUGG
GAP_SECONDS = 300                    # celah jejak yang diisi estimasi (bukan asumsi lapangan → bukan parameter)

REFERENCES = [
    "ISO 14083:2023 — Quantification and reporting of GHG emissions arising from transport chain operations.",
    "Smart Freight Centre (2025). GLEC Framework v3.2 for Logistics Emissions Accounting and Reporting.",
    "Kepmen ESDM 341.K/EK.01/MEM.E/2024 — mandatori biodiesel B40.",
    "Bektaş, T. & Laporte, G. (2011). The Pollution-Routing Problem. Transportation Research Part B 45(8):1232-1250.",
]
PARAMETERS_USED = [
    "logistik.fuel_l_per_km_empty", "logistik.fuel_l_per_km_full", "logistik.vehicle_payload_kg",
    "logistik.gps_max_accuracy_m", "logistik.gps_max_speed_kmh", "logistik.gps_min_step_m",
    "logistik.gps_gap_road_factor", "logistik.road_factor",
    "karbon.diesel_ttw_kg_co2e_per_l", "karbon.diesel_wtt_kg_co2e_per_l", "karbon.fame_wtw_kg_co2e_per_l",
    "karbon.biodiesel_blend_pct",
]


@dataclass(frozen=True)
class TrackPoint:
    t: datetime
    lat: float
    lon: float
    accuracy_m: float | None = None


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, h)))


def fuel_factors() -> dict:
    """Faktor emisi per liter solar campuran (B-mandatori)."""
    b = P("karbon.biodiesel_blend_pct") / 100
    ttw_fossil, wtt_fossil = P("karbon.diesel_ttw_kg_co2e_per_l"), P("karbon.diesel_wtt_kg_co2e_per_l")
    ttw = (1 - b) * ttw_fossil                               # CO₂ biogenik FAME = 0
    wtw = (1 - b) * (ttw_fossil + wtt_fossil) + b * P("karbon.fame_wtw_kg_co2e_per_l")
    return {"blend_pct": b * 100, "ttw_kg_per_l": round(ttw, 4), "wtw_kg_per_l": round(wtw, 4)}


def fuel_l_per_km(load_kg: float) -> float:
    cap = P("logistik.vehicle_payload_kg")
    f0, f1 = P("logistik.fuel_l_per_km_empty"), P("logistik.fuel_l_per_km_full")
    frac = max(0.0, min(1.0, load_kg / cap)) if cap > 0 else 0.0
    return f0 + (f1 - f0) * frac


def clean_track(points: list[TrackPoint]) -> tuple[list[TrackPoint], dict]:
    """Saring titik GPS; kembalikan titik sah (urut waktu) + statistik pembuangan."""
    max_acc, vmax, min_step = P("logistik.gps_max_accuracy_m"), P("logistik.gps_max_speed_kmh"), P("logistik.gps_min_step_m")
    pts = sorted(points, key=lambda p: p.t)
    kept: list[TrackPoint] = []
    dropped = {"accuracy": 0, "speed": 0, "jitter": 0}
    for p in pts:
        if p.accuracy_m is not None and p.accuracy_m > max_acc:
            dropped["accuracy"] += 1
            continue
        if kept:
            prev = kept[-1]
            d_km = haversine_km((prev.lat, prev.lon), (p.lat, p.lon))
            dt_h = max((p.t - prev.t).total_seconds(), 0) / 3600
            if dt_h > 0 and d_km / dt_h > vmax:
                dropped["speed"] += 1
                continue
            if d_km * 1000 < min_step:
                dropped["jitter"] += 1
                continue
        kept.append(p)
    return kept, {"raw_points": len(pts), "kept_points": len(kept), "dropped": dropped}


def _load_at(t: datetime, pickups: list[tuple[datetime, float]]) -> float:
    return sum(kg for at, kg in pickups if at <= t)


def emissions_from_track(points: list[TrackPoint], pickups: list[tuple[datetime, float]]) -> dict:
    """Jarak & emisi dari jejak GPS nyata. `pickups` = [(waktu scan, kg dimuat)] — muatan bertambah per stop."""
    kept, stats = clean_track(points)
    gap_factor = P("logistik.gps_gap_road_factor")
    segments, est_km = [], 0.0
    for a, b in zip(kept, kept[1:]):
        km = haversine_km((a.lat, a.lon), (b.lat, b.lon))
        if (b.t - a.t).total_seconds() > GAP_SECONDS:
            km *= gap_factor                     # celah: jarak lurus × faktor jalan (estimasi)
            est_km += km
        segments.append((km, _load_at(a.t, pickups)))
    res = _summarize(segments, sum(kg for _, kg in pickups), source="gps")
    res["track"] = {**stats, "estimated_gap_km": round(est_km, 3)}
    return res


def emissions_from_plan(legs: list[tuple[float, float]], delivered_kg: float) -> dict:
    """Fallback tanpa GPS: legs = [(km, muatan_kg_selama_leg)] dari depot → stop … → depot."""
    return _summarize(legs, delivered_kg, source="rencana")


def _summarize(segments: list[tuple[float, float]], delivered_kg: float, source: str) -> dict:
    ff = fuel_factors()
    total_km = sum(km for km, _ in segments)
    empty_km = sum(km for km, load in segments if load <= 1e-9)
    fuel = sum(km * fuel_l_per_km(load) for km, load in segments)
    tkm = sum(km * load / 1000 for km, load in segments)
    wtw, ttw = fuel * ff["wtw_kg_per_l"], fuel * ff["ttw_kg_per_l"]
    ton = delivered_kg / 1000
    return {
        "distance_source": source,
        "total_km": round(total_km, 3),
        "empty_km": round(empty_km, 3),
        "laden_km": round(total_km - empty_km, 3),
        "tkm": round(tkm, 3),
        "fuel_l": round(fuel, 3),
        "co2e_wtw_kg": round(wtw, 3),
        "co2e_ttw_kg": round(ttw, 3),
        "intensity_g_per_tkm": round(wtw * 1000 / tkm, 1) if tkm > 1e-9 else None,
        "co2e_kg_per_ton_husk": round(wtw / ton, 3) if ton > 1e-9 else None,
        "fuel_factors": ff,
        "computation_details": {
            "method": "ISO 14083:2023 / GLEC v3.2 — fuel-based, well-to-wheel; perjalanan kosong ikut dihitung",
            "formulas": [
                "BBM = Σ km × [f_kosong + (f_penuh − f_kosong) × muatan/muatan_maks]",
                "EF = (1−b)(TTW+WTT)_solar + b·WTW_FAME",
                "CO₂e = BBM × EF;  intensitas = CO₂e ÷ t·km;  per ton = CO₂e ÷ ton terangkut",
            ],
            "parameters_used": PARAMETERS_USED,
            "references": REFERENCES,
        },
    }
