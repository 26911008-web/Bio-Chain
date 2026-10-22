"""Engine ① — Supply Forecaster.

Prediksi pasokan sekam padi berdasarkan musim tanam, luas panen, dan
data historis. Menggunakan model cosinus ganda untuk musim panen Jawa.

Referensi:
- BPS: Produktivitas padi Indonesia rata-rata 5.3 ton/ha
- Rasio sekam terhadap gabah: ~20% (literatur)
- Musim panen utama Jawa: April-Mei & Sept-Okt
"""

import math
from pydantic import BaseModel, Field

PRODUCTIVITY_TON_PER_HA = 5.3
HUSK_RATIO = 0.20
SEASONAL_AMPLITUDE = 0.40
PEAK_MONTHS = [4, 9]


class ForecastInput(BaseModel):
    harvest_area_ha: float = Field(..., gt=0, description="Luas panen total (ha)")
    month: int = Field(..., ge=1, le=12, description="Bulan target prediksi")
    year: int = Field(..., ge=2024, le=2035)
    historical_avg_ton: float | None = Field(
        None, ge=0,
        description="Rata-rata pasokan bulanan historis (ton)"
    )


class ForecastResult(BaseModel):
    predicted_supply_ton: float
    seasonal_factor: float
    base_monthly_ton: float
    confidence_low: float
    confidence_high: float
    is_peak_season: bool
    recommendation: str


def seasonal_factor(month: int) -> float:
    """Faktor musiman: superposisi dua gelombang cosinus (dua puncak panen/tahun).

    Factor = 1 + A × max(cos(2π(m-p₁)/12), cos(2π(m-p₂)/12))
    """
    waves = [math.cos(2 * math.pi * (month - p) / 12) for p in PEAK_MONTHS]
    return 1.0 + SEASONAL_AMPLITUDE * max(waves)


def forecast_supply(inp: ForecastInput) -> ForecastResult:
    """Prediksi pasokan sekam bulanan.

    Base: Annual_husk = area × productivity × husk_ratio
    Monthly = Annual / 12 × seasonal_factor
    """
    annual_husk = inp.harvest_area_ha * PRODUCTIVITY_TON_PER_HA * HUSK_RATIO
    monthly_base = annual_husk / 12

    # Blend model dengan data historis jika tersedia
    if inp.historical_avg_ton is not None and inp.historical_avg_ton > 0:
        monthly_base = 0.6 * inp.historical_avg_ton + 0.4 * monthly_base

    sf = seasonal_factor(inp.month)
    predicted = monthly_base * sf

    ci_width = 0.15 if inp.historical_avg_ton else 0.25
    is_peak = inp.month in PEAK_MONTHS or inp.month in [p + 1 for p in PEAK_MONTHS]

    if is_peak:
        rec = "🟢 Musim puncak panen. Siapkan kapasitas gudang & armada maksimal."
    elif sf < 0.8:
        rec = "🔴 Musim paceklik. Aktifkan stok buffer atau cari pemasok alternatif."
    else:
        rec = "🟡 Pasokan normal. Pastikan kontrak petani tetap aktif."

    return ForecastResult(
        predicted_supply_ton=round(predicted, 1),
        seasonal_factor=round(sf, 3),
        base_monthly_ton=round(monthly_base, 1),
        confidence_low=round(predicted * (1 - ci_width), 1),
        confidence_high=round(predicted * (1 + ci_width), 1),
        is_peak_season=is_peak,
        recommendation=rec,
    )
