"""Engine ② — Quality & Yield Scorer untuk sekam padi sebagai feedstock pirolisis.

Model rendemen dikalibrasi dari literatur (slow pyrolysis sekam padi: 57,13% pada 300°C
turun ke 37,19% pada 700°C). Koefisien koreksi abu dan fraksi SiO2 adalah asumsi awal
yang akan dikalibrasi ulang dengan data uji batch PT Indmira.
"""

from pydantic import BaseModel, Field

YIELD_300C = 57.13          # % basis kering
YIELD_700C = 37.19
REF_ASH = 18.0              # kadar abu sekam tipikal, % basis kering
ASH_YIELD_COEF = 0.5        # abu tertahan di char -> abu lebih tinggi menaikkan rendemen
SIO2_FRACTION_OF_ASH = 0.90 # abu sekam mengandung ~80-97% SiO2

MOISTURE_REJECT = 25.0
CONTAMINATION_REJECT = 10.0

GRADE_PRICE_MULTIPLIER = {"A": 1.15, "B": 1.05, "C": 1.00, "TOLAK": 0.0}


class FeedstockSample(BaseModel):
    moisture: float = Field(..., ge=0, le=60, description="Kadar air, % basis basah")
    ash: float = Field(..., ge=0, le=40, description="Kadar abu, % basis kering")
    volatile_matter: float = Field(..., ge=0, le=100, description="Volatile matter, % basis kering")
    fixed_carbon: float = Field(..., ge=0, le=100, description="Fixed carbon, % basis kering")
    contamination: float = Field(0, ge=0, le=50, description="Batu/dedak/plastik, % massa")
    pyrolysis_temp_c: float = Field(500, ge=300, le=700, description="Suhu pirolisis target")


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _linear_score(value: float, best: float, worst: float) -> float:
    """100 saat value <= best (atau >= best jika best > worst), 0 saat mencapai worst."""
    if best < worst:
        return _clamp(100 * (worst - value) / (worst - best), 0, 100)
    return _clamp(100 * (value - worst) / (best - worst), 0, 100)


def biochar_yield_db(temp_c: float, ash: float) -> float:
    """Prediksi rendemen biochar (% massa basis kering)."""
    base = YIELD_300C - (YIELD_300C - YIELD_700C) * (temp_c - 300) / 400
    return _clamp(base + ASH_YIELD_COEF * (ash - REF_ASH), 20, 75)


def yield_curve(ash: float = REF_ASH) -> list[dict]:
    return [{"temp_c": t, "yield_pct": round(biochar_yield_db(t, ash), 2)} for t in range(300, 701, 25)]


def score_sample(s: FeedstockSample) -> dict:
    warnings = []
    proximate_sum = s.ash + s.volatile_matter + s.fixed_carbon
    if abs(proximate_sum - 100) > 3:
        warnings.append(f"Abu + VM + FC = {proximate_sum:.1f}% (seharusnya ~100%). Cek ulang hasil uji proksimat.")

    components = {
        "kadar_air": _linear_score(s.moisture, best=10, worst=MOISTURE_REJECT),
        "kontaminasi": _linear_score(s.contamination, best=1, worst=CONTAMINATION_REJECT),
        "kadar_abu": _clamp(100 - 10 * max(0, s.ash - 20, 14 - s.ash), 0, 100),
        "fixed_carbon": _linear_score(s.fixed_carbon, best=17, worst=8),
    }
    weights = {"kadar_air": 0.35, "kontaminasi": 0.30, "kadar_abu": 0.15, "fixed_carbon": 0.20}
    score = sum(components[k] * w for k, w in weights.items())

    if s.moisture > MOISTURE_REJECT or s.contamination > CONTAMINATION_REJECT:
        grade = "TOLAK"
        warnings.append("Melebihi batas penerimaan (air > 25% atau kontaminan > 10%). Perlu pengeringan/penyaringan.")
    elif score >= 80:
        grade = "A"
    elif score >= 60:
        grade = "B"
    else:
        grade = "C"

    dry_factor = (1 - s.moisture / 100) * (1 - s.contamination / 100)
    y = biochar_yield_db(s.pyrolysis_temp_c, s.ash)
    ash_in_char = _clamp(s.ash / y * 100, 0, 95)

    return {
        "grade": grade,
        "score": round(score, 1),
        "components": {k: round(v, 1) for k, v in components.items()},
        "price_multiplier": GRADE_PRICE_MULTIPLIER[grade],
        "pred_biochar_yield_pct_db": round(y, 2),
        "biochar_kg_per_ton_received": round(1000 * dry_factor * y / 100, 1),
        "pred_ash_in_biochar_pct": round(ash_in_char, 1),
        "pred_sio2_in_biochar_pct": round(ash_in_char * SIO2_FRACTION_OF_ASH, 1),
        "sio2_kg_per_ton_received": round(1000 * dry_factor * s.ash / 100 * SIO2_FRACTION_OF_ASH, 1),
        "warnings": warnings,
    }
