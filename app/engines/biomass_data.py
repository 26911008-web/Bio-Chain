"""Data & korelasi properti bahan bakar biomassa (dipakai Engine ⑧ dan ⑨).

Nilai preset = nilai TIPIKAL literatur (basis kering kecuali kadar air) — rentang nyata lebar dan
WAJIB diganti hasil uji laboratorium aktual sebelum keputusan investasi.
Sumber umum: basis data Phyllis2 (ECN/TNO); Vassilev et al. (2010) Fuel 89:913-933;
BMP: Angelidaki et al. (2009) Water Sci. Technol. 59(5):927-934 (protokol) & nilai tipikal literatur AD.
"""

from dataclasses import dataclass

from ..params import P
from .quality import biochar_yield_db

LATENT_HEAT_MJ_KG = 2.443        # panas laten penguapan air pada 25 °C
CH4_LHV_MJ_M3 = 35.8             # metana, kondisi normal
REF_HUSK_FC, REF_HUSK_VM = 16.0, 66.0   # komposisi sekam acuan kalibrasi model rendemen Engine ②


@dataclass(frozen=True)
class BiomassPreset:
    id: str
    name: str
    moisture: float            # % basis basah (as received)
    ash: float                 # % basis kering
    volatile_matter: float     # % basis kering
    fixed_carbon: float        # % basis kering
    hydrogen: float            # % basis kering (untuk LHV)
    cn_ratio: float            # rasio C/N
    bmp_m3_ch4_per_t_vs: float  # potensi metana biokimia
    lignocellulosic: bool
    price_rp_per_ton: float = 0.0


def presets() -> dict[str, BiomassPreset]:
    """Preset aktif dari menu Parameter (tabel `biomassa.presets`)."""
    return {r["id"]: BiomassPreset(**{k: r[k] for k in BiomassPreset.__dataclass_fields__ if k in r})
            for r in P("biomassa.presets")}


def hhv_parikh(fc: float, vm: float, ash: float) -> float:
    """HHV basis kering (MJ/kg) dari analisis proksimat — Parikh, Channiwala & Ghosal (2005),
    Fuel 84:487-494: HHV = 0,3536 FC + 0,1559 VM − 0,0078 Ash (R² ≈ 0,94)."""
    return 0.3536 * fc + 0.1559 * vm - 0.0078 * ash


def lhv_as_received(hhv_db: float, moisture_wb: float, hydrogen_db: float = 6.0) -> float:
    """LHV basis diterima (MJ/kg): kurangi energi air bawaan + air hasil oksidasi hidrogen."""
    w, h = moisture_wb / 100, hydrogen_db / 100
    return hhv_db * (1 - w) - LATENT_HEAT_MJ_KG * (w + 9 * h * (1 - w))


def vm_retention(temp_c: float) -> float:
    """Fraksi volatile matter yang tertahan di char, diturunkan dari model rendemen sekam (Engine ②):
    r(T) = (Y_sekam(T) − FC_ref − Ash_ref) / VM_ref. ≈0,27 @400 °C, 0,20 @500 °C, 0,12 @600 °C."""
    ref_ash = P("rendemen.ref_ash")
    return max(0.0, (biochar_yield_db(temp_c, ref_ash) - REF_HUSK_FC - ref_ash) / REF_HUSK_VM)


def biochar_yield_estimate(fc: float, vm: float, ash: float, temp_c: float) -> float:
    """Rendemen biochar basis kering (%) ≈ Ash + FC + r(T)·VM. Asumsi: abu & fixed carbon tertahan
    seluruhnya (konsep fixed-carbon yield, Antal & Grønli 2003, Ind. Eng. Chem. Res. 42:1619)."""
    return min(100.0, ash + fc + vm_retention(temp_c) * vm)
