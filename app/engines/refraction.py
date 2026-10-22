"""Refraksi berat bayar pengepul multi-komoditas (018) — docs/15 §7.

    kg_bayar = kg_timbang × (1 − max(0, kontaminan − toleransi)) × (1 − MC) / (1 − MC_acuan)

* Tidak ada standar nasional refraksi sekam/tongkol/serbuk; MC acuan & toleransi kontaminan per komoditas ada di
  master biomass_parameters (dapat diubah pabrik), analog HPP gabah Bapanas (KA ≤ 25 %, rafaksi di atasnya).
* Tanpa bonus bila lebih kering dari acuan (cegah klaim alat ukur salah); bonus kering bisa diaktifkan per transaksi.
* Di atas MC tolak: bukan otomatis 0 — kondisi lapangan (pengepul mengeringkan sendiri) diberi opsi eksplisit
  `accept_wet=True` yang dicatat di basis refraksi.
* Ukur MC dengan moisture meter terkalibrasi oven 105 °C (ISO 18134-2).
"""


def refract(gross_kg: float, moisture_pct: float | None, contaminant_pct: float | None, moisture_ref_pct: float,
            moisture_reject_pct: float, contaminant_tol_pct: float, dry_bonus: bool = False,
            accept_wet: bool = False) -> dict:
    if gross_kg <= 0:
        raise ValueError("Berat timbang harus > 0")
    mc = moisture_pct if moisture_pct is not None else moisture_ref_pct
    contam = contaminant_pct or 0.0
    too_wet = mc > moisture_reject_pct
    if too_wet and not accept_wet:
        return {"accepted": False, "payable_kg": 0.0, "refraction_kg": gross_kg,
                "reason": f"Kadar air {mc:g}% > batas tolak {moisture_reject_pct:g}% — tolak, atau terima basah "
                          "(keringkan sendiri) dengan opsi eksplisit"}
    contam_cut = max(0.0, contam - contaminant_tol_pct) / 100
    moist_factor = (1 - mc / 100) / (1 - moisture_ref_pct / 100)
    if not dry_bonus:
        moist_factor = min(1.0, moist_factor)
    payable = round(gross_kg * (1 - contam_cut) * moist_factor, 2)
    return {
        "accepted": True, "payable_kg": payable, "refraction_kg": round(gross_kg - payable, 2),
        "moisture_factor": round(moist_factor, 4), "contaminant_cut_pct": round(contam_cut * 100, 2),
        "basis": {"formula": "kg × (1 − max(0, kontaminan − toleransi)) × (1 − MC)/(1 − MC_acuan)",
                  "moisture_pct": mc, "moisture_measured": moisture_pct is not None, "moisture_ref_pct": moisture_ref_pct,
                  "moisture_reject_pct": moisture_reject_pct, "contaminant_pct": contam,
                  "contaminant_tol_pct": contaminant_tol_pct, "dry_bonus": dry_bonus, "accepted_wet": too_wet},
    }
