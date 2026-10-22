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
    # F9: abu/VM/FC hanya terukur di lab/NIR — boleh kosong di lapangan (skor dari kadar air & kontaminan)
    ash: float | None = Field(None, ge=0, le=40, description="Kadar abu, % basis kering (opsional)")
    volatile_matter: float | None = Field(None, ge=0, le=100, description="Volatile matter, % basis kering (opsional)")
    fixed_carbon: float | None = Field(None, ge=0, le=100, description="Fixed carbon, % basis kering (opsional)")
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
    measured = s.ash is not None and s.fixed_carbon is not None
    if s.ash is not None and s.volatile_matter is not None and s.fixed_carbon is not None:
        proximate_sum = s.ash + s.volatile_matter + s.fixed_carbon
        if abs(proximate_sum - 100) > 3:
            warnings.append(f"Abu + VM + FC = {proximate_sum:.1f}% (seharusnya ~100%). Cek ulang hasil uji proksimat.")
    if not measured:
        warnings.append("Uji proksimat (abu/FC) tidak diukur — grade dihitung dari kadar air & kontaminan saja; "
                        "rendemen memakai abu acuan. Lakukan uji lab untuk lot besar/kontrak.")

    components = {
        "kadar_air": _linear_score(s.moisture, best=P("harga_mutu.moisture_best"), worst=MOISTURE_REJECT),
        "kontaminasi": _linear_score(s.contamination, best=P("harga_mutu.contamination_best"), worst=CONTAMINATION_REJECT),
    }
    if s.ash is not None:
        components["kadar_abu"] = _clamp(100 - 10 * max(0, s.ash - ash_hi, ash_lo - s.ash), 0, 100)
    if s.fixed_carbon is not None:
        components["fixed_carbon"] = _linear_score(s.fixed_carbon, best=P("harga_mutu.fc_best"), worst=P("harga_mutu.fc_worst"))
    w = weights("harga_mutu.w_")
    key_w = {"kadar_air": w["moisture"], "kontaminasi": w["contamination"], "kadar_abu": w["ash"], "fixed_carbon": w["fc"]}
    total_w = sum(key_w[k] for k in components) or 1.0          # bobot dinormalisasi atas komponen yang terukur
    score = sum(components[k] * key_w[k] for k in components) / total_w

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
    ash_used = s.ash if s.ash is not None else P("rendemen.ref_ash")
    y = biochar_yield_db(s.pyrolysis_temp_c, ash_used)
    ash_in_char = _clamp(ash_used / y * 100, 0, 95)

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
            {"step": "Skor kadar abu", "formula": "clamp(100 - 10 × penalty, 0, 100)", "value": round(components["kadar_abu"], 1) if "kadar_abu" in components else None, "unit": "poin"},
            {"step": "Skor fixed carbon", "formula": "linear_score(fixed_carbon, best, worst)", "value": round(components["fixed_carbon"], 1) if "fixed_carbon" in components else None, "unit": "poin"},
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
        "sio2_kg_per_ton_received": round(1000 * dry_factor * ash_used / 100 * SIO2_FRACTION_OF_ASH, 1),
        "proximate_measured": measured,
        "warnings": warnings,
        "computation_details": comp_details,
    }


def farmgate_price(base_price: float, weighed_kg: float, moisture: float, contamination: float, grade: str,
                   grade_multiplier: float, reference_moisture: float | None = None, wetter_only: bool = False,
                   method: str | None = None) -> dict:
    """Harga beli sekam dari petani, terikat langsung pada kadar air (Engine ② → verifikasi pengepul).

    basis_kering (default, sama dengan rumus QC pabrik):
        harga/kg  = harga_dasar × (1 − M) / (1 − M_acuan)        (M lebih basah → bahan kering lebih sedikit)
        kg_bayar  = timbangan × (1 − kontaminan)                  (batu/plastik tidak dibayar)
        total     = kg_bayar × harga/kg;   TOLAK → 0
      Pengali grade TIDAK dipakai: kadar air sudah dihargai kontinu (menghindari hitung ganda & 'tebing harga'
      di batas grade). Bonus mutu petani tetap lewat Engine ⑥ (insentif/XP).
    pengali_grade (lama): total = timbangan × harga_dasar × pengali_grade.
    wetter_only=True (kontrak lelang): hanya potongan bila lebih basah dari kadar air kontrak, tanpa bonus kering.
    """
    method = method or P("harga_mutu.pricing_method")
    m_ref = P("harga_mutu.reference_moisture_pct") if reference_moisture is None else reference_moisture
    mold_risk = moisture > P("harga_mutu.moisture_mold_risk_pct")
    if grade == "TOLAK":
        price, payable_kg, formula = 0.0, 0.0, "Grade TOLAK → tidak dibeli (kembalikan / keringkan dulu)"
    elif method == "pengali_grade":
        price, payable_kg = base_price * grade_multiplier, weighed_kg
        formula = f"timbangan × Rp{base_price:g} × pengali {grade_multiplier:g}"
    else:
        factor = (1 - moisture / 100) / (1 - m_ref / 100)
        if wetter_only:
            factor = min(1.0, factor)
        price = base_price * factor
        payable_kg = weighed_kg * (1 - contamination / 100)
        formula = (f"Rp{base_price:g} × (1 − {moisture:g}%) ÷ (1 − {m_ref:g}%) = Rp{price:,.2f}/kg; "
                   f"kg bayar = {weighed_kg:g} × (1 − {contamination:g}%)")
    price = round(price, 2)
    return {
        "method": method, "price_per_kg": price, "payable_kg": round(payable_kg, 3),
        "total_price": round(payable_kg * price), "reference_moisture_pct": m_ref,
        "mold_risk": mold_risk,
        "mold_advice": ("Kadar air di atas ambang risiko jamur: angkut ≤ 48 jam atau keringkan; jangan simpan "
                        "tertutup.") if mold_risk else None,
        "formula": formula,
        "parameters_used": ["harga_mutu.pricing_method", "harga_mutu.reference_moisture_pct",
                            "harga_mutu.moisture_mold_risk_pct", "harga_mutu.base_price_per_kg"],
    }
