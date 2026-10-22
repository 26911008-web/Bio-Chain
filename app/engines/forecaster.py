"""Engine ① — Supply Forecaster.

Prediksi pasokan sekam padi berdasarkan musim tanam, luas panen, dan
data historis. Menggunakan model cosinus ganda untuk musim panen Jawa.

Referensi:
- BPS: Produktivitas padi Indonesia rata-rata 5.3 ton/ha
- Rasio sekam terhadap gabah: ~20% (literatur)
- Musim panen utama Jawa: April-Mei & Sept-Okt
"""

import math
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..params import P

class ForecastInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    harvest_area_ha: float | None = Field(None, gt=0, description="Luas panen total (ha)")
    month: int | None = Field(None, ge=1, le=12, description="Bulan target prediksi")
    year: int | None = Field(None, ge=2020, le=2035)
    historical_avg_ton: float | None = Field(
        None, ge=0,
        description="Rata-rata pasokan bulanan historis (ton)"
    )
    date: str | None = Field(None, description="Tanggal acuan prediksi (YYYY-MM-DD)")

    @model_validator(mode="before")
    @classmethod
    def populate_defaults(cls, data: any):
        if isinstance(data, dict):
            now = datetime.now()
            if data.get("date"):
                try:
                    d = date.fromisoformat(str(data["date"])[:10])
                    if not data.get("month"):
                        data["month"] = d.month
                    if not data.get("year"):
                        data["year"] = d.year
                except Exception:
                    pass
            if not data.get("month"):
                data["month"] = now.month
            if not data.get("year"):
                data["year"] = max(2024, now.year)
            if not data.get("harvest_area_ha"):
                data["harvest_area_ha"] = float(P("proyeksi.harvest_area_ha", 50.0) or 50.0)
        return data


class ForecastResult(BaseModel):
    predicted_supply_ton: float
    seasonal_factor: float
    base_monthly_ton: float
    confidence_low: float
    confidence_high: float
    is_peak_season: bool
    recommendation: str
    computation_details: dict | None = None


def seasonal_factor(month: int) -> float:
    """Faktor musiman: superposisi dua gelombang cosinus (dua puncak panen/tahun).

    Factor = 1 + A × max(cos(2π(m-p₁)/12), cos(2π(m-p₂)/12))
    """
    waves = [math.cos(2 * math.pi * (month - p) / 12) for p in _peaks()]
    return 1.0 + P("proyeksi.seasonal_amplitude") * max(waves)


def _peaks() -> list[int]:
    return [int(P("proyeksi.peak_month_1")), int(P("proyeksi.peak_month_2"))]


def forecast_supply(inp: ForecastInput) -> ForecastResult:
    """Prediksi pasokan sekam bulanan.

    Base: Annual_husk = area × productivity × husk_ratio
    Monthly = Annual / 12 × seasonal_factor
    """
    PEAK_MONTHS = _peaks()
    annual_husk = inp.harvest_area_ha * P("proyeksi.productivity_ton_per_ha") * P("proyeksi.husk_ratio")
    monthly_base = annual_husk / 12

    # Blend model dengan data historis jika tersedia
    if inp.historical_avg_ton is not None and inp.historical_avg_ton > 0:
        wh = P("proyeksi.history_weight")
        monthly_base = wh * inp.historical_avg_ton + (1 - wh) * monthly_base

    sf = seasonal_factor(inp.month)
    predicted = monthly_base * sf

    ci_width = P("proyeksi.ci_width_history") if inp.historical_avg_ton else P("proyeksi.ci_width_model")
    is_peak = inp.month in PEAK_MONTHS or inp.month in [p % 12 + 1 for p in PEAK_MONTHS]

    if is_peak:
        rec = "🟢 Musim puncak panen. Siapkan kapasitas gudang & armada maksimal."
    elif sf < 0.8:
        rec = "🔴 Musim paceklik. Aktifkan stok buffer atau cari pemasok alternatif."
    else:
        rec = "🟡 Pasokan normal. Pastikan kontrak petani tetap aktif."

    comp_details = {
        "method": "Dual-Cosine Harmonic Harvest Seasonality & Agronomic Yield Model",
        "inputs": {
            "harvest_area_ha": inp.harvest_area_ha,
            "month": inp.month,
            "year": inp.year,
            "historical_avg_ton": inp.historical_avg_ton,
        },
        "steps": [
            {"step": "Potensi sekam tahunan", "formula": "luas_ha × produktivitas × rasio_sekam", "value": round(annual_husk, 2), "unit": "ton/tahun"},
            {"step": "Basis bulanan model", "formula": "tahunan ÷ 12", "value": round(annual_husk / 12, 2), "unit": "ton/bulan"},
            {"step": "Faktor musim", "formula": "1 + A × max(cos(2π(m-p₁)/12), cos(2π(m-p₂)/12))", "value": round(sf, 3), "unit": "indeks"},
            {"step": "Prediksi pasokan bulanan", "formula": "basis_bulanan × faktor_musim", "value": round(predicted, 1), "unit": "ton"},
        ],
        "parameters_used": [
            "proyeksi.productivity_ton_per_ha",
            "proyeksi.husk_ratio",
            "proyeksi.seasonal_amplitude",
            "proyeksi.peak_month_1",
            "proyeksi.peak_month_2",
            "proyeksi.history_weight",
            "proyeksi.ci_width_history",
            "proyeksi.ci_width_model",
        ],
        "references": [
            "Badan Pusat Statistik (BPS) — Statistik Tanaman Pangan Indonesia",
            "IRRI — Rice Knowledge Bank: By-products of Rice Milling",
        ],
    }

    return ForecastResult(
        predicted_supply_ton=round(predicted, 1),
        seasonal_factor=round(sf, 3),
        base_monthly_ton=round(monthly_base, 1),
        confidence_low=round(predicted * (1 - ci_width), 1),
        confidence_high=round(predicted * (1 + ci_width), 1),
        is_peak_season=is_peak,
        recommendation=rec,
        computation_details=comp_details,
    )
