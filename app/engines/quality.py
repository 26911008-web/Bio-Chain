"""Engine ② — Quality & Yield Scorer untuk sekam padi sebagai feedstock pirolisis.

Model rendemen dikalibrasi dari literatur (slow pyrolysis sekam padi: 57,13% pada 300°C
turun ke 37,19% pada 700°C). Koefisien koreksi abu dan fraksi SiO2 adalah asumsi awal
yang akan dikalibrasi ulang dengan data uji batch PT Indmira.
"""

from pydantic import BaseModel, Field

from ..params import P, weights

# Nilai di bawah = DEFAULT registry (app/params.py). Engine membaca nilai aktif via P() saat dijalankan.
YIELD_300C = 57.13          # % basis kering
YIELD_700C = 37.19
REF_ASH = 18.0              # kadar abu sekam tipikal, % basis kering
ASH_YIELD_COEF = 0.5        # abu tertahan di char -> abu lebih tinggi menaikkan rendemen
SIO2_FRACTION_OF_ASH = 0.90 # abu sekam mengandung ~80-97% SiO2

MOISTURE_REJECT = 25.0
CONTAMINATION_REJECT = 10.0

GRADE_PRICE_MULTIPLIER = {"A": 1.15, "B": 1.05, "C": 1.00, "TOLAK": 0.0}

QUALITY_PARAMETERS_USED = [
    "harga_mutu.w_moisture", "harga_mutu.w_contamination", "harga_mutu.w_ash", "harga_mutu.w_fc",
    "harga_mutu.moisture_best", "harga_mutu.moisture_reject",
    "harga_mutu.contamination_best", "harga_mutu.contamination_reject",
    "harga_mutu.ash_ideal_min", "harga_mutu.ash_ideal_max",
    "harga_mutu.fc_best", "harga_mutu.fc_worst",
    "harga_mutu.grade_A_min", "harga_mutu.grade_B_min",
    "rendemen.sio2_fraction_of_ash",
]
QUALITY_REFERENCES = [
    "SNI 8990:2021 — Biochar untuk pembenah tanah",
    "IBI Standardized Product Definition and Product Testing Guidelines for Biochar",
]


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
    y300, y700 = P("rendemen.yield_300c"), P("rendemen.yield_700c")
    base = y300 - (y300 - y700) * (temp_c - 300) / 400
    return _clamp(base + P("rendemen.ash_yield_coef") * (ash - P("rendemen.ref_ash")), 20, 75)


def yield_curve(ash: float | None = None) -> list[dict]:
    ash = P("rendemen.ref_ash") if ash is None else ash
    return [{"temp_c": t, "yield_pct": round(biochar_yield_db(t, ash), 2)} for t in range(300, 701, 25)]


def score_sample(s: FeedstockSample) -> dict:
    MOISTURE_REJECT, CONTAMINATION_REJECT = P("harga_mutu.moisture_reject"), P("harga_mutu.contamination_reject")
    SIO2_FRACTION_OF_ASH = P("rendemen.sio2_fraction_of_ash")
    GRADE_PRICE_MULTIPLIER = {"A": P("harga_mutu.mult_A"), "B": P("harga_mutu.mult_B"), "C": P("harga_mutu.mult_C"),
                              "TOLAK": 0.0}
    ash_lo, ash_hi = P("harga_mutu.ash_ideal_min"), P("harga_mutu.ash_ideal_max")
    warnings = []
    proximate_sum = s.ash + s.volatile_matter + s.fixed_carbon
    if abs(proximate_sum - 100) > 3:
        warnings.append(f"Abu + VM + FC = {proximate_sum:.1f}% (seharusnya ~100%). Cek ulang hasil uji proksimat.")

    components = {
        "kadar_air": _linear_score(s.moisture, best=P("harga_mutu.moisture_best"), worst=MOISTURE_REJECT),
        "kontaminasi": _linear_score(s.contamination, best=P("harga_mutu.contamination_best"), worst=CONTAMINATION_REJECT),
        "kadar_abu": _clamp(100 - 10 * max(0, s.ash - ash_hi, ash_lo - s.ash), 0, 100),
        "fixed_carbon": _linear_score(s.fixed_carbon, best=P("harga_mutu.fc_best"), worst=P("harga_mutu.fc_worst")),
    }
    w = weights("harga_mutu.w_")
    score = (components["kadar_air"] * w["moisture"] + components["kontaminasi"] * w["contamination"]
             + components["kadar_abu"] * w["ash"] + components["fixed_carbon"] * w["fc"])

    if s.moisture > MOISTURE_REJECT or s.contamination > CONTAMINATION_REJECT:
        grade = "TOLAK"
        warnings.append(f"Melebihi batas penerimaan (air > {MOISTURE_REJECT:g}% atau kontaminan > "
                        f"{CONTAMINATION_REJECT:g}%). Perlu pengeringan/penyaringan.")
    elif score >= P("harga_mutu.grade_A_min"):
        grade = "A"
    elif score >= P("harga_mutu.grade_B_min"):
        grade = "B"
    else:
        grade = "C"

    dry_factor = (1 - s.moisture / 100) * (1 - s.contamination / 100)
    y = biochar_yield_db(s.pyrolysis_temp_c, s.ash)
    ash_in_char = _clamp(s.ash / y * 100, 0, 95)

    comp_details = {
        "method": "Multi-Criteria Proximate Quality Scoring & Pyrolysis Yield Model",
        "inputs": {
            "moisture_pct": s.moisture,
            "ash_pct": s.ash,
            "volatile_matter_pct": s.volatile_matter,
            "fixed_carbon_pct": s.fixed_carbon,
            "contamination_pct": s.contamination,
            "pyrolysis_temp_c": s.pyrolysis_temp_c,
        },
        "steps": [
            {"step": "Skor kadar air", "formula": "linear_score(moisture, best, worst)", "value": round(components["kadar_air"], 1), "unit": "poin"},
            {"step": "Skor kontaminasi", "formula": "linear_score(contamination, best, worst)", "value": round(components["kontaminasi"], 1), "unit": "poin"},
            {"step": "Skor kadar abu", "formula": "clamp(100 - 10 × penalty, 0, 100)", "value": round(components["kadar_abu"], 1), "unit": "poin"},
            {"step": "Skor fixed carbon", "formula": "linear_score(fixed_carbon, best, worst)", "value": round(components["fixed_carbon"], 1), "unit": "poin"},
            {"step": "Rendemen biochar kering (db)", "formula": "biochar_yield_db(temp, ash)", "value": round(y, 2), "unit": "%"},
            {"step": "Potensi biochar per ton terima", "formula": "1000 × faktor_kering × y ÷ 100", "value": round(1000 * dry_factor * y / 100, 1), "unit": "kg/ton"},
            {"step": "Skor komposit mutu", "formula": "∑(skor_komponen × bobot)", "value": round(score, 1), "unit": "poin"},
        ],
        "parameters_used": QUALITY_PARAMETERS_USED,
        "references": QUALITY_REFERENCES,
    }

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
        "computation_details": comp_details,
    }
