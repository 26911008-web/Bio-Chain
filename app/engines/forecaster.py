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

from ..params import P

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

    return ForecastResult(
        predicted_supply_ton=round(predicted, 1),
        seasonal_factor=round(sf, 3),
        base_monthly_ton=round(monthly_base, 1),
        confidence_low=round(predicted * (1 - ci_width), 1),
        confidence_high=round(predicted * (1 + ci_width), 1),
        is_peak_season=is_peak,
        recommendation=rec,
    )
