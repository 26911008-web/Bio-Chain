"""Engine ⑫ — Optimasi Konversi Multi-Biomassa ke Produk Akhir (Biopellet, Briket, Biochar, Biosilika).

Alat evaluasi komparatif & optimasi alokasi alur produksi pabrik:
1. Evaluasi Komparatif 4 Produk Akhir:
   - Bio-Pellet (standar ISO 17225-2 / ISO 17225-6, cofiring PLTU & boiler industri)
   - Briket Biomassa / Arang (standar SNI 01-6235-2000, shisha/BBQ & industri)
   - Biochar (pembenah tanah agronomi & sertifikat pemindahan karbon permanen C-sink)
   - Bio-Silika Amorf (ekstraksi silika presipitasi kemurnian tinggi dari biomassa kaya silika)

2. Matriks Efisiensi Multi-Dimensi:
   - Efisiensi Rendemen Massa (Yield kg/ton input & neraca massa tertutup)
   - Efisiensi Energi (SEC kWh/ton, thermal drying MJ/ton, Net Energy Ratio)
   - Efisiensi Ekonomi & Nilai Tambah (HPP, Revenue, Gross Margin Rp/ton, Nilai Tambah)
   - Efisiensi Karbon (Emisi proses vs emisi dihindari/disekuestrasi tCO2e/ton)
   - Indeks Kesesuaian Teknis & Rekomendasi (Skor 0-100 & status kelayakan ilmiah)

3. Optimasi Alokasi Stok Multi-Biomassa Pabrik:
   - Solver LP (SciPy HiGHS) untuk mengalokasikan stok multi-biomassa yang masuk ke lini pabrik
   - Objektif: Maksimalkan Keuntungan (Max Profit), Maksimalkan Energi (Max Energy),
     Maksimalkan Karbon (Max Carbon), atau Portofolio Seimbang (Balanced).
"""

from dataclasses import dataclass
from typing import Any, Literal
import numpy as np
from pydantic import BaseModel, Field, model_validator
from scipy.optimize import linprog

from ..params import P
from .biomass_data import biochar_yield_estimate
from .fuel_blend import KCAL_PER_MJ, LATENT


def _p(key: str, fallback: Any = None) -> Any:
    try:
        val = P(key)
        return fallback if val is None else val
    except Exception:
        return fallback

PRODUCTS = ("bio_pellet", "briket", "biochar", "bio_silika")

PRODUCT_META = {
    "bio_pellet": {
        "name": "Bio-Pellet",
        "description": "Pelet silinder densifikasi tinggi untuk cofiring PLTU, boiler industri & ekspor (ISO 17225).",
        "standard": "ISO 17225-2 (Kayu) / ISO 17225-6 (Non-kayu)",
        "default_price_rp_kg": 1800.0,
        "default_kwh_per_ton_product": 95.0,
        "target_moisture_pct": 9.0,
        "loss_rate": 0.025,
    },
    "briket": {
        "name": "Briket Biomassa / Arang",
        "description": "Briket padat berkalori tinggi (karbonisasi arang + binder atau densifikasi press) untuk shisha, BBQ & termal.",
        "standard": "SNI 01-6235-2000 / Standar Ekspor Arang Shisha",
        "default_price_rp_kg": 8500.0,
        "default_kwh_per_ton_product": 75.0,
        "target_moisture_pct": 7.0,
        "binder_ratio": 0.05,  # 5% tapioka starch
        "binder_cost_rp_kg": 8000.0,
        "loss_rate": 0.03,
    },
    "biochar": {
        "name": "Biochar Pembenah Tanah",
        "description": "Arang hayati hasil pirolisis lambat kaya karbon stabil untuk bioremediasi tanah sawah & C-sink removal permanen.",
        "standard": "European Biochar Certificate (EBC) / IBI Standard",
        "default_price_rp_kg": 3500.0,
        "default_kwh_per_ton_product": 45.0,
        "target_moisture_pct": 8.0,
        "pyrolysis_temp_c": 500.0,
        "loss_rate": 0.02,
    },
    "bio_silika": {
        "name": "Bio-Silika Amorf",
        "description": "Silika presipitasi kemurnian tinggi (>90-98% SiO2 amorf) dari abu biomassa kaya silika untuk ban, cat & pupuk tanaman.",
        "standard": "SNI 15-0086-1987 / ASTM D1993 Silika Presipitasi",
        "default_price_rp_kg": 28000.0,
        "default_kwh_per_ton_product": 320.0,
        "target_moisture_pct": 4.0,
        "chemical_cost_per_kg_silica": 4500.0,
        "extraction_eff": 0.88,
        "loss_rate": 0.05,
    },
}

COAL_EF_KG_CO2_PER_GJ = 94.6  # Faktor emisi batubara acuan IPCC
GRID_EF_KG_CO2_PER_KWH = 0.87  # Grid JAMALI Kepmen ESDM 163.K/2021


class FeedstockItem(BaseModel):
    code: str = Field(..., min_length=2, max_length=24)
    name: str = Field(..., min_length=2, max_length=80)
    tonnage: float = Field(..., gt=0, le=100_000_000, description="Tonase pasokan as-received")
    moisture_pct: float = Field(..., ge=0, lt=95, description="Kadar air as-received (%)")
    ash_pct_db: float = Field(..., ge=0, lt=60, description="Kadar abu basis kering (%)")
    volatile_pct_db: float | None = Field(None, ge=0, le=100)
    fixed_carbon_pct_db: float | None = Field(None, ge=0, le=100)
    hhv_db_mj_kg: float | None = Field(None, gt=5, lt=35)
    lhv_db_mj_kg: float | None = Field(None, gt=5, lt=35)
    sio2_pct_ash: float | None = Field(None, ge=0, le=100, description="% SiO2 dalam abu")
    k2o_pct_ash: float | None = Field(None, ge=0, le=100)
    na2o_pct_ash: float | None = Field(None, ge=0, le=100)
    chlorine_pct_db: float | None = Field(None, ge=0, le=5)
    sulfur_pct_db: float | None = Field(None, ge=0, le=5)
    base_price_per_kg: float | None = Field(None, ge=0, le=100_000)


def _safe_lhv_ar(lhv_db: float, mc_pct: float) -> float:
    mc = mc_pct / 100.0
    return max(0.1, lhv_db * (1.0 - mc) - LATENT * mc)


def evaluate_biopellet_pathway(f: FeedstockItem, price_rp_kg: float | None = None) -> dict:
    """Evaluasi teknis & ekonomi pengolahan 1 ton umpan ke Biopellet."""
    price = price_rp_kg if price_rp_kg is not None else PRODUCT_META["bio_pellet"]["default_price_rp_kg"]
    meta = PRODUCT_META["bio_pellet"]
    dry_frac = 1.0 - (f.moisture_pct / 100.0)
    target_mc = meta["target_moisture_pct"] / 100.0
    loss_rate = meta["loss_rate"]

    # 1 ton umpan (1000 kg)
    input_kg = 1000.0
    dry_kg = input_kg * dry_frac

    # Massa basah pada target kadar air
    if f.moisture_pct > meta["target_moisture_pct"]:
        wet_at_target_kg = dry_kg / (1.0 - target_mc)
        water_evaporated_kg = input_kg - wet_at_target_kg
    else:
        wet_at_target_kg = input_kg
        water_evaporated_kg = 0.0

    pellet_produced_kg = wet_at_target_kg * (1.0 - loss_rate)
    process_loss_kg = wet_at_target_kg * loss_rate

    # Mutu produk
    lhv_db = f.lhv_db_mj_kg or 17.5
    hhv_db = f.hhv_db_mj_kg or (lhv_db + 1.2)
    product_lhv_mj = _safe_lhv_ar(lhv_db, meta["target_moisture_pct"])
    product_ash_ar = f.ash_pct_db * (1.0 - target_mc)

    # Energi & SEC
    drying_mj = water_evaporated_kg * _p("limbah.drying_mj_per_kg_water", 3.0)
    kwh_elec = (pellet_produced_kg / 1000.0) * meta["default_kwh_per_ton_product"]
    elec_tariff = _p("energi.tariff_rp_per_kwh", 1444.7)
    heat_cost_mj = _p("pabrik.drying_cost_rp_per_mj", 25.0)

    # Biaya & Ekonomi
    cost_elec = kwh_elec * elec_tariff
    cost_drying = drying_mj * heat_cost_mj
    cost_labor = (input_kg / 1000.0) * _p("pabrik.labor_hours_per_ton", 2.0) * _p("pabrik.labor_rate_per_hour", 20000.0)
    cost_pack = pellet_produced_kg * _p("pabrik.packaging_cost_per_kg", 100.0)
    processing_cost_rp = cost_elec + cost_drying + cost_labor + cost_pack

    feedstock_cost_rp = input_kg * (f.base_price_per_kg or 0.0)
    revenue_rp = pellet_produced_kg * price
    gross_profit_rp = revenue_rp - (feedstock_cost_rp + processing_cost_rp)
    breakeven_price = (feedstock_cost_rp + processing_cost_rp) / max(1.0, pellet_produced_kg)

    # Karbon
    total_energy_gj = (pellet_produced_kg * product_lhv_mj) / 1000.0
    avoided_coal_co2_kg = total_energy_gj * COAL_EF_KG_CO2_PER_GJ
    proc_co2_kg = (kwh_elec * GRID_EF_KG_CO2_PER_KWH) + (drying_mj * 0.06)
    net_co2e_t = (avoided_coal_co2_kg - proc_co2_kg) / 1000.0

    # Skor Kesesuaian & Batas ISO
    score = 95.0
    notes = []
    advantages = []
    disadvantages = []

    # Abu
    if product_ash_ar <= 1.2:
        advantages.append(f"Kadar abu prima ({product_ash_ar:.1f}%): memenuhi ISO 17225-2 Kelas A1/A2.")
    elif product_ash_ar <= 6.0:
        score -= 15.0
        advantages.append(f"Kadar abu {product_ash_ar:.1f}%: lolos ISO 17225-6 Kelas A non-kayu.")
    elif product_ash_ar <= 10.0:
        score -= 30.0
        notes.append(f"Kadar abu {product_ash_ar:.1f}%: hanya lolos Kelas B, perlu pembersihan abu berkala.")
    else:
        score -= 55.0
        disadvantages.append(f"Kadar abu tinggi ({product_ash_ar:.1f}% > 10%): berisiko kerak berat; wajib blending.")

    # Slagging AI
    ai = (f.ash_pct_db * ((f.k2o_pct_ash or 0.0) + (f.na2o_pct_ash or 0.0)) / (10.0 * hhv_db)) if f.k2o_pct_ash else None
    if ai and ai > 0.34:
        score -= 25.0
        disadvantages.append(f"Indeks alkali {ai:.2f} kg/GJ > 0,34: risiko kerak/slagging di pipa boiler.")
    elif ai and ai < 0.17:
        advantages.append("Indeks alkali rendah (<0,17 kg/GJ): ramah tungku dan tahan kerak.")

    # Klorin
    if f.chlorine_pct_db and f.chlorine_pct_db > 0.2:
        score -= 25.0
        disadvantages.append(f"Klorin {f.chlorine_pct_db:.2f}% > 0,2%: risiko korosi HCl pada superheater.")

    # Kadar air
    if f.moisture_pct > 35.0:
        score -= 15.0
        disadvantages.append(f"Kadar air bahan {f.moisture_pct:.1f}%: beban pengeringan tinggi ({drying_mj:.0f} MJ/t).")

    score = max(5.0, min(100.0, score))
    status = ("sangat_direkomendasikan" if score >= 80 else
              "layak" if score >= 60 else
              "kurang_cocok" if score >= 40 else "tidak_layak")

    return {
        "product": "bio_pellet",
        "label": meta["name"],
        "yield_kg_per_ton": round(pellet_produced_kg, 1),
        "yield_pct": round(pellet_produced_kg / 10.0, 1),
        "losses_kg_per_ton": {
            "air_diuapkan": round(water_evaporated_kg, 1),
            "susut_proses": round(process_loss_kg, 1),
        },
        "mass_balance_closure": round((pellet_produced_kg + water_evaporated_kg + process_loss_kg) / input_kg, 6),
        "product_quality": {
            "moisture_pct": round(meta["target_moisture_pct"], 1),
            "ash_pct": round(product_ash_ar, 2),
            "lhv_mj_kg": round(product_lhv_mj, 2),
            "lhv_kcal_kg": round(product_lhv_mj * KCAL_PER_MJ, 0),
            "bulk_density_kg_m3": 650.0,
            "standard_compliance": "ISO 17225" if score >= 60 else "Perlu Blending",
        },
        "energy_metrics": {
            "sec_kwh_per_ton_product": round(meta["default_kwh_per_ton_product"], 1),
            "process_kwh_per_ton_feed": round(kwh_elec, 1),
            "thermal_drying_mj_per_ton_feed": round(drying_mj, 1),
            "net_energy_output_gj": round(total_energy_gj, 2),
            "net_energy_ratio": round((total_energy_gj * 1000.0) / max(1.0, drying_mj + (kwh_elec * 3.6)), 2),
        },
        "economics": {
            "product_price_per_kg": round(price, 0),
            "revenue_per_ton_feed": round(revenue_rp, 0),
            "feedstock_cost_per_ton": round(feedstock_cost_rp, 0),
            "processing_cost_per_ton_feed": round(processing_cost_rp, 0),
            "processing_cost_per_kg_product": round(processing_cost_rp / max(1.0, pellet_produced_kg), 1),
            "gross_profit_per_ton_feed": round(gross_profit_rp, 0),
            "gross_margin_pct": round((gross_profit_rp / max(1.0, revenue_rp)) * 100.0, 1),
            "breakeven_price_per_kg": round(breakeven_price, 1),
        },
        "climate_metrics": {
            "process_co2e_kg_per_ton": round(proc_co2_kg, 1),
            "avoided_co2e_kg_per_ton": round(avoided_coal_co2_kg, 1),
            "net_climate_benefit_tco2e_per_ton": round(net_co2e_t, 3),
        },
        "suitability": {
            "score": round(score, 0),
            "status": status,
            "status_label": ("Sangat Direkomendasikan" if status == "sangat_direkomendasikan" else
                             "Layak Beroperasi" if status == "layak" else
                             "Kurang Cocok" if status == "kurang_cocok" else "Tidak Direkomendasikan"),
            "technical_notes": notes,
            "advantages": advantages,
            "disadvantages": disadvantages,
        },
    }


def evaluate_briket_pathway(f: FeedstockItem, price_rp_kg: float | None = None) -> dict:
    """Evaluasi teknis & ekonomi pengolahan 1 ton umpan ke Briket Arang / Karbonisasi."""
    meta = PRODUCT_META["briket"]
    dry_frac = 1.0 - (f.moisture_pct / 100.0)
    input_kg = 1000.0
    dry_kg = input_kg * dry_frac

    # Rendemen pirolisis arang
    fc = f.fixed_carbon_pct_db or 18.0
    vm = f.volatile_pct_db or 75.0
    y_char_pct = biochar_yield_estimate(fc, vm, f.ash_pct_db, 500.0)
    char_dry_kg = dry_kg * (y_char_pct / 100.0)

    # Tambahan binder tapioka 5% basis kering arang
    binder_kg = char_dry_kg * meta["binder_ratio"]
    target_mc = meta["target_moisture_pct"] / 100.0
    loss_rate = meta["loss_rate"]

    briket_gross_kg = (char_dry_kg + binder_kg) / (1.0 - target_mc)
    briket_produced_kg = briket_gross_kg * (1.0 - loss_rate)
    char_in_briket_kg = char_dry_kg * (1.0 - loss_rate)
    char_loss_kg = char_dry_kg * loss_rate

    # Loss volatil & air umpan
    volatiles_kg = dry_kg * (1.0 - y_char_pct / 100.0)
    water_loss_kg = input_kg * (f.moisture_pct / 100.0)

    # Mutu briket
    char_ash_pct = min(60.0, f.ash_pct_db / max(0.1, y_char_pct / 100.0))
    briket_ash_pct = char_ash_pct * (1.0 - target_mc)
    briket_hhv_mj = 24.0 + (fc * 0.2) - (char_ash_pct * 0.15)
    briket_lhv_mj = max(18.0, briket_hhv_mj - 1.5)

    # Harga pasar berdasar mutu SNI / Standar pasar bila tidak di-override
    if price_rp_kg is not None:
        price = price_rp_kg
    else:
        if briket_ash_pct <= 4.0:
            price = 9500.0  # Premium export / shisha (tempurung kelapa)
        elif briket_ash_pct <= 8.0:
            price = 7000.0  # SNI Grade A BBQ (kayu / tongkol)
        elif briket_ash_pct <= 15.0:
            price = 4500.0  # Komersial lokal
        else:
            price = 1500.0  # Arang boiler industri abu tinggi

    # Energi & SEC
    kwh_elec = (briket_produced_kg / 1000.0) * meta["default_kwh_per_ton_product"]
    elec_tariff = _p("energi.tariff_rp_per_kwh", 1444.7)
    oven_drying_mj = briket_gross_kg * 0.15 * 3.0  # pengeringan briket basah

    # Biaya
    cost_elec = kwh_elec * elec_tariff
    cost_binder = binder_kg * meta["binder_cost_rp_kg"]
    cost_drying = oven_drying_mj * _p("pabrik.drying_cost_rp_per_mj", 25.0)
    cost_labor = (input_kg / 1000.0) * _p("pabrik.labor_hours_per_ton", 2.0) * _p("pabrik.labor_rate_per_hour", 20000.0)
    cost_pack = briket_produced_kg * _p("pabrik.packaging_cost_per_kg", 100.0)
    processing_cost_rp = cost_elec + cost_binder + cost_drying + cost_labor + cost_pack

    feedstock_cost_rp = input_kg * (f.base_price_per_kg or 0.0)
    revenue_rp = briket_produced_kg * price
    gross_profit_rp = revenue_rp - (feedstock_cost_rp + processing_cost_rp)
    breakeven_price = (feedstock_cost_rp + processing_cost_rp) / max(1.0, briket_produced_kg)

    # Karbon
    total_energy_gj = (briket_produced_kg * briket_lhv_mj) / 1000.0
    avoided_coal_co2_kg = total_energy_gj * COAL_EF_KG_CO2_PER_GJ
    proc_co2_kg = (kwh_elec * GRID_EF_KG_CO2_PER_KWH) + (oven_drying_mj * 0.06)
    net_co2e_t = (avoided_coal_co2_kg - proc_co2_kg) / 1000.0

    # Kesesuaian Briket
    score = 80.0
    notes = []
    advantages = []
    disadvantages = []

    if fc >= 20.0 and f.ash_pct_db <= 2.5:
        score += 18.0
        advantages.append(f"Karbon tetap tinggi ({fc:.1f}%) & abu rendah ({f.ash_pct_db:.1f}%): ideal briket shisha premium.")
    elif f.ash_pct_db <= 5.0:
        score += 5.0
        advantages.append(f"Abu sedang ({briket_ash_pct:.1f}%): cocok untuk briket BBQ dan industri.")
    else:
        score -= 45.0
        disadvantages.append(f"Kadar abu bahan tinggi ({f.ash_pct_db:.1f}%), abu briket tembus {briket_ash_pct:.1f}% (standar SNI maks 8%).")

    if f.code == "tempurung_kelapa":
        score = 98.0
        advantages.append("Bahan baku briket terbaik (densitas tinggi, abu putih < 3%, panas tahan lama).")
    elif f.code == "sekam_padi":
        score = 30.0
        disadvantages.append("Sekam menghasilkan arang rapuh dan abu tinggi (>40%); tidak cocok untuk briket komersial.")

    score = max(5.0, min(100.0, score))
    status = ("sangat_direkomendasikan" if score >= 80 else
              "layak" if score >= 60 else
              "kurang_cocok" if score >= 40 else "tidak_layak")

    return {
        "product": "briket",
        "label": meta["name"],
        "yield_kg_per_ton": round(briket_produced_kg, 1),
        "yield_pct": round(briket_produced_kg / 10.0, 1),
        "losses_kg_per_ton": {
            "air_diuapkan": round(water_loss_kg, 1),
            "volatil_pirolisis": round(volatiles_kg, 1),
            "susut_proses_arang": round(char_loss_kg, 1),
        },
        "mass_balance_closure": round((char_in_briket_kg + char_loss_kg + volatiles_kg + water_loss_kg) / input_kg, 6),
        "product_quality": {
            "moisture_pct": round(meta["target_moisture_pct"], 1),
            "ash_pct": round(briket_ash_pct, 2),
            "lhv_mj_kg": round(briket_lhv_mj, 2),
            "lhv_kcal_kg": round(briket_lhv_mj * KCAL_PER_MJ, 0),
            "fixed_carbon_pct": round(min(85.0, fc * 3.5), 1),
            "standard_compliance": "SNI 01-6235-2000" if score >= 60 else "Di Bawah Standar SNI",
        },
        "energy_metrics": {
            "sec_kwh_per_ton_product": round(meta["default_kwh_per_ton_product"], 1),
            "process_kwh_per_ton_feed": round(kwh_elec, 1),
            "thermal_drying_mj_per_ton_feed": round(oven_drying_mj, 1),
            "net_energy_output_gj": round(total_energy_gj, 2),
            "net_energy_ratio": round((total_energy_gj * 1000.0) / max(1.0, oven_drying_mj + (kwh_elec * 3.6)), 2),
        },
        "economics": {
            "product_price_per_kg": round(price, 0),
            "revenue_per_ton_feed": round(revenue_rp, 0),
            "feedstock_cost_per_ton": round(feedstock_cost_rp, 0),
            "processing_cost_per_ton_feed": round(processing_cost_rp, 0),
            "processing_cost_per_kg_product": round(processing_cost_rp / max(1.0, briket_produced_kg), 1),
            "gross_profit_per_ton_feed": round(gross_profit_rp, 0),
            "gross_margin_pct": round((gross_profit_rp / max(1.0, revenue_rp)) * 100.0, 1),
            "breakeven_price_per_kg": round(breakeven_price, 1),
        },
        "climate_metrics": {
            "process_co2e_kg_per_ton": round(proc_co2_kg, 1),
            "avoided_co2e_kg_per_ton": round(avoided_coal_co2_kg, 1),
            "net_climate_benefit_tco2e_per_ton": round(net_co2e_t, 3),
        },
        "suitability": {
            "score": round(score, 0),
            "status": status,
            "status_label": ("Sangat Direkomendasikan" if status == "sangat_direkomendasikan" else
                             "Layak Beroperasi" if status == "layak" else
                             "Kurang Cocok" if status == "kurang_cocok" else "Tidak Direkomendasikan"),
            "technical_notes": notes,
            "advantages": advantages,
            "disadvantages": disadvantages,
        },
    }


def evaluate_biochar_pathway(f: FeedstockItem, price_rp_kg: float | None = None) -> dict:
    """Evaluasi teknis & ekonomi pengolahan 1 ton umpan ke Biochar (Agronomi & C-Sink)."""
    price = price_rp_kg if price_rp_kg is not None else PRODUCT_META["biochar"]["default_price_rp_kg"]
    meta = PRODUCT_META["biochar"]
    dry_frac = 1.0 - (f.moisture_pct / 100.0)
    input_kg = 1000.0
    dry_kg = input_kg * dry_frac

    fc = f.fixed_carbon_pct_db or 18.0
    vm = f.volatile_pct_db or 75.0
    temp_c = meta["pyrolysis_temp_c"]

    y_char_pct = biochar_yield_estimate(fc, vm, f.ash_pct_db, temp_c)
    char_dry_kg = dry_kg * (y_char_pct / 100.0)
    loss_rate = meta["loss_rate"]
    target_mc = meta["target_moisture_pct"] / 100.0

    biochar_produced_kg = (char_dry_kg / (1.0 - target_mc)) * (1.0 - loss_rate)
    char_in_product_kg = char_dry_kg * (1.0 - loss_rate)
    char_loss_kg = char_dry_kg * loss_rate

    volatiles_kg = dry_kg * (1.0 - y_char_pct / 100.0)
    water_loss_kg = input_kg * (f.moisture_pct / 100.0)

    # Mutu biochar
    char_ash_pct = min(60.0, f.ash_pct_db / max(0.1, y_char_pct / 100.0))
    c_organic_pct = max(35.0, 100.0 - char_ash_pct - 15.0)

    # Sekuestrasi karbon permanen (C-sink): ~2.2 tCO2e per ton biochar kering terkarbonisasi
    # IPCC Tier 2 / European Biochar Certificate: C_sink = Biochar_ton * C_org% * F_perm (0.74 pada 100 tahun) * 44/12
    carbon_removal_t = (biochar_produced_kg / 1000.0) * (c_organic_pct / 100.0) * 0.74 * (44.0 / 12.0)

    # SEC & Biaya
    kwh_elec = (biochar_produced_kg / 1000.0) * meta["default_kwh_per_ton_product"]
    elec_tariff = _p("energi.tariff_rp_per_kwh", 1444.7)
    cost_elec = kwh_elec * elec_tariff
    cost_labor = (input_kg / 1000.0) * _p("pabrik.labor_hours_per_ton", 2.0) * _p("pabrik.labor_rate_per_hour", 20000.0)
    cost_pack = biochar_produced_kg * _p("pabrik.packaging_cost_per_kg", 100.0)
    processing_cost_rp = cost_elec + cost_labor + cost_pack

    feedstock_cost_rp = input_kg * (f.base_price_per_kg or 0.0)
    revenue_rp = biochar_produced_kg * price
    gross_profit_rp = revenue_rp - (feedstock_cost_rp + processing_cost_rp)
    breakeven_price = (feedstock_cost_rp + processing_cost_rp) / max(1.0, biochar_produced_kg)

    proc_co2_kg = kwh_elec * GRID_EF_KG_CO2_PER_KWH
    net_co2e_t = carbon_removal_t - (proc_co2_kg / 1000.0)

    # Kesesuaian Biochar
    score = 85.0
    notes = []
    advantages = []
    disadvantages = []

    if f.code == "sekam_padi":
        score = 93.0
        advantages.append("Kaya silika amorf & berpori tinggi: sangat unggul untuk pembenah tanah sawah & CEC tanah.")
    elif f.code == "tempurung_kelapa":
        score = 90.0
        advantages.append("Kadar C-organik tinggi (>75%): kapasitas sekuestrasi karbon stabil & adsorpsi sangat tinggi.")
    elif f.k2o_pct_ash and f.k2o_pct_ash > 20.0:
        advantages.append(f"Kaya kalium K2O ({f.k2o_pct_ash:.1f}% abu): berfungsi sebagai pupuk kalium alami bagi tanaman.")

    if f.moisture_pct > 40.0:
        score -= 15.0
        disadvantages.append(f"Kadar air bahan basah ({f.moisture_pct:.1f}%): butuh pengeringan sebelum masuk retort pirolisis.")

    score = max(5.0, min(100.0, score))
    status = ("sangat_direkomendasikan" if score >= 80 else
              "layak" if score >= 60 else
              "kurang_cocok" if score >= 40 else "tidak_layak")

    return {
        "product": "biochar",
        "label": meta["name"],
        "yield_kg_per_ton": round(biochar_produced_kg, 1),
        "yield_pct": round(biochar_produced_kg / 10.0, 1),
        "losses_kg_per_ton": {
            "air_diuapkan": round(water_loss_kg, 1),
            "volatil_syngas": round(volatiles_kg, 1),
            "susut_proses_char": round(char_loss_kg, 1),
        },
        "mass_balance_closure": round((char_in_product_kg + char_loss_kg + volatiles_kg + water_loss_kg) / input_kg, 6),
        "product_quality": {
            "moisture_pct": round(meta["target_moisture_pct"], 1),
            "ash_pct": round(char_ash_pct, 2),
            "c_organic_pct": round(c_organic_pct, 1),
            "pyrolysis_temp_c": temp_c,
            "standard_compliance": "EBC / IBI Standard",
            "carbon_sink_tco2e_per_ton": round(carbon_removal_t / max(0.001, biochar_produced_kg / 1000.0), 2),
        },
        "energy_metrics": {
            "sec_kwh_per_ton_product": round(meta["default_kwh_per_ton_product"], 1),
            "process_kwh_per_ton_feed": round(kwh_elec, 1),
            "thermal_drying_mj_per_ton_feed": 0.0,  # panas didapat dari pembakaran syngas
            "net_energy_output_gj": round((biochar_produced_kg * 16.0) / 1000.0, 2),
            "net_energy_ratio": round(((biochar_produced_kg * 16.0) / 1000.0) / max(0.1, kwh_elec * 3.6 / 1000.0), 2),
        },
        "economics": {
            "product_price_per_kg": round(price, 0),
            "revenue_per_ton_feed": round(revenue_rp, 0),
            "feedstock_cost_per_ton": round(feedstock_cost_rp, 0),
            "processing_cost_per_ton_feed": round(processing_cost_rp, 0),
            "processing_cost_per_kg_product": round(processing_cost_rp / max(1.0, biochar_produced_kg), 1),
            "gross_profit_per_ton_feed": round(gross_profit_rp, 0),
            "gross_margin_pct": round((gross_profit_rp / max(1.0, revenue_rp)) * 100.0, 1),
            "breakeven_price_per_kg": round(breakeven_price, 1),
        },
        "climate_metrics": {
            "process_co2e_kg_per_ton": round(proc_co2_kg, 1),
            "carbon_removal_co2e_kg_per_ton": round(carbon_removal_t * 1000.0, 1),
            "net_climate_benefit_tco2e_per_ton": round(net_co2e_t, 3),
        },
        "suitability": {
            "score": round(score, 0),
            "status": status,
            "status_label": ("Sangat Direkomendasikan" if status == "sangat_direkomendasikan" else
                             "Layak Beroperasi" if status == "layak" else
                             "Kurang Cocok" if status == "kurang_cocok" else "Tidak Direkomendasikan"),
            "technical_notes": notes,
            "advantages": advantages,
            "disadvantages": disadvantages,
        },
    }


def evaluate_biosilika_pathway(f: FeedstockItem, price_rp_kg: float | None = None) -> dict:
    """Evaluasi teknis & ekonomi pengolahan 1 ton umpan ke Bio-Silika Amorf."""
    price = price_rp_kg if price_rp_kg is not None else PRODUCT_META["bio_silika"]["default_price_rp_kg"]
    meta = PRODUCT_META["bio_silika"]
    dry_frac = 1.0 - (f.moisture_pct / 100.0)
    input_kg = 1000.0
    dry_kg = input_kg * dry_frac

    sio2_frac = (f.sio2_pct_ash or 20.0) / 100.0
    ash_frac = f.ash_pct_db / 100.0
    eff = meta["extraction_eff"]

    # Potensi silika teoritis (kg per ton umpan)
    silica_theoretical_kg = dry_kg * ash_frac * sio2_frac
    silica_produced_kg = silica_theoretical_kg * eff * (1.0 - meta["loss_rate"])
    extraction_residue_kg = dry_kg * ash_frac - silica_produced_kg
    water_loss_kg = input_kg * (f.moisture_pct / 100.0)
    combustion_volatiles_kg = dry_kg * (1.0 - ash_frac)

    # SEC & Biaya
    kwh_elec = (silica_produced_kg / 1000.0) * meta["default_kwh_per_ton_product"]
    elec_tariff = _p("energi.tariff_rp_per_kwh", 1444.7)
    cost_elec = kwh_elec * elec_tariff
    cost_chem = silica_produced_kg * meta["chemical_cost_per_kg_silica"]
    cost_labor = (input_kg / 1000.0) * _p("pabrik.labor_hours_per_ton", 2.0) * _p("pabrik.labor_rate_per_hour", 20000.0)
    cost_pack = silica_produced_kg * _p("pabrik.packaging_cost_per_kg", 250.0)
    processing_cost_rp = cost_elec + cost_chem + cost_labor + cost_pack

    feedstock_cost_rp = input_kg * (f.base_price_per_kg or 0.0)
    revenue_rp = silica_produced_kg * price
    gross_profit_rp = revenue_rp - (feedstock_cost_rp + processing_cost_rp)
    breakeven_price = (feedstock_cost_rp + processing_cost_rp) / max(1.0, silica_produced_kg)

    # Emisi
    proc_co2_kg = (kwh_elec * GRID_EF_KG_CO2_PER_KWH) + (silica_produced_kg * 0.4)
    # Substitusi silika konvensional berbasis pasir kuarsa (carbon footprint ~1.8 kg CO2e/kg silika sintetis)
    avoided_co2_kg = silica_produced_kg * 1.8
    net_co2e_t = (avoided_co2_kg - proc_co2_kg) / 1000.0

    # Kesesuaian Kritis Bio-Silika
    # Rendemen silika > 80 kg/ton umpan = Sangat Layak; < 20 kg/ton = Tidak Ekonomis
    score = 10.0
    notes = []
    advantages = []
    disadvantages = []

    if silica_produced_kg >= 100.0:
        score = 98.0
        advantages.append(f"Rendemen biosilika luar biasa ({silica_produced_kg:.1f} kg/t): nilai tambah tertinggi (Rp {revenue_rp:,.0f}/t umpan).")
        advantages.append(f"Kadar abu {f.ash_pct_db:.1f}% dengan SiO2 {f.sio2_pct_ash or 0:.1f}% di abu: bahan baku ideal biosilika.")
    elif silica_produced_kg >= 40.0:
        score = 75.0
        advantages.append(f"Rendemen silika {silica_produced_kg:.1f} kg/t: layak diproses dengan optimasi bahan kimia.")
    elif silica_produced_kg >= 15.0:
        score = 45.0
        notes.append(f"Rendemen silika marginal ({silica_produced_kg:.1f} kg/t): biaya reagen kimia mendekati margin.")
    else:
        score = 10.0
        disadvantages.append(f"Rendemen silika sangat rendah ({silica_produced_kg:.1f} kg/t): abu/SiO2 terlalu kecil; proses ini RUGI secara ekonomi.")

    status = ("sangat_direkomendasikan" if score >= 80 else
              "layak" if score >= 60 else
              "kurang_cocok" if score >= 40 else "tidak_layak")

    return {
        "product": "bio_silika",
        "label": meta["name"],
        "yield_kg_per_ton": round(silica_produced_kg, 1),
        "yield_pct": round(silica_produced_kg / 10.0, 2),
        "losses_kg_per_ton": {
            "air_diuapkan": round(water_loss_kg, 1),
            "gas_organik_terbakar": round(combustion_volatiles_kg, 1),
            "residu_ekstraksi": round(extraction_residue_kg, 1),
        },
        "mass_balance_closure": round((silica_produced_kg + water_loss_kg + combustion_volatiles_kg + extraction_residue_kg) / input_kg, 6),
        "product_quality": {
            "moisture_pct": round(meta["target_moisture_pct"], 1),
            "sio2_purity_pct": round(min(99.0, max(85.0, (f.sio2_pct_ash or 90.0) * 0.98 + 5.0)), 1),
            "structure": "Amorf (Aman untuk paru-paru)",
            "standard_compliance": "SNI 15-0086-1987" if score >= 60 else "Tidak Memenuhi Ambang Ekonomis",
        },
        "energy_metrics": {
            "sec_kwh_per_ton_product": round(meta["default_kwh_per_ton_product"], 1),
            "process_kwh_per_ton_feed": round(kwh_elec, 1),
            "thermal_drying_mj_per_ton_feed": round(silica_produced_kg * 2.5, 1),
            "net_energy_output_gj": 0.0,  # bukan produk energi
            "net_energy_ratio": 0.0,
        },
        "economics": {
            "product_price_per_kg": round(price, 0),
            "revenue_per_ton_feed": round(revenue_rp, 0),
            "feedstock_cost_per_ton": round(feedstock_cost_rp, 0),
            "processing_cost_per_ton_feed": round(processing_cost_rp, 0),
            "processing_cost_per_kg_product": round(processing_cost_rp / max(1.0, silica_produced_kg), 1),
            "gross_profit_per_ton_feed": round(gross_profit_rp, 0),
            "gross_margin_pct": round((gross_profit_rp / max(1.0, revenue_rp)) * 100.0, 1),
            "breakeven_price_per_kg": round(breakeven_price, 1),
        },
        "climate_metrics": {
            "process_co2e_kg_per_ton": round(proc_co2_kg, 1),
            "avoided_co2e_kg_per_ton": round(avoided_co2_kg, 1),
            "net_climate_benefit_tco2e_per_ton": round(net_co2e_t, 3),
        },
        "suitability": {
            "score": round(score, 0),
            "status": status,
            "status_label": ("Sangat Direkomendasikan" if status == "sangat_direkomendasikan" else
                             "Layak Beroperasi" if status == "layak" else
                             "Kurang Cocok" if status == "kurang_cocok" else "Tidak Direkomendasikan"),
            "technical_notes": notes,
            "advantages": advantages,
            "disadvantages": disadvantages,
        },
    }


def evaluate_feedstock(f: FeedstockItem, price_overrides: dict[str, float] | None = None) -> dict:
    """Mengevaluasi komoditas biomassa terhadap seluruh 4 produk akhir secara komprehensif."""
    pr = price_overrides or {}
    pellet = evaluate_biopellet_pathway(f, pr.get("bio_pellet"))
    briket = evaluate_briket_pathway(f, pr.get("briket"))
    char = evaluate_biochar_pathway(f, pr.get("biochar"))
    silica = evaluate_biosilika_pathway(f, pr.get("bio_silika"))

    products = {
        "bio_pellet": pellet,
        "briket": briket,
        "biochar": char,
        "bio_silika": silica,
    }

    # Penentuan produk terbaik berdasarkan kriteria
    best_profit = max(products.items(), key=lambda it: it[1]["economics"]["gross_profit_per_ton_feed"])
    best_energy = max(products.items(), key=lambda it: it[1]["energy_metrics"]["net_energy_output_gj"])
    best_carbon = max(products.items(), key=lambda it: it[1]["climate_metrics"]["net_climate_benefit_tco2e_per_ton"])
    best_score = max(products.items(), key=lambda it: it[1]["suitability"]["score"])

    # Ringkasan rekomendasi
    summary_parts = []
    if f.code == "sekam_padi":
        summary_parts.append("Sekam padi paling efisien dan menguntungkan diolah menjadi Bio-Silika (margin tertinggi) & Biochar pembenah tanah sawah. Jangan dijadikan biopellet murni tanpa dicampur karena abu 17,5% melanggar standar ISO.")
    elif f.code == "tempurung_kelapa":
        summary_parts.append("Tempurung kelapa merupakan bahan baku emas untuk Briket Arang Shisha/BBQ (abu <3%, kalori >7.200 kcal/kg) & Biochar aktif. Sangat tidak disarankan untuk biosilika karena abu terlalu rendah (<1%).")
    elif "serbuk" in f.code or "kayu" in f.name.lower():
        summary_parts.append("Serbuk gergaji kayu paling efisien diolah menjadi Bio-Pellet standar ekspor (ISO 17225-2 Kelas A1) dan Briket padat. Sangat ramah boiler industri dan bebas risiko kerak.")
    elif f.code == "tongkol_jagung":
        summary_parts.append("Tongkol jagung sangat fleksibel untuk Briket dan Biochar kaya Kalium. Hati-hati indeks alkali jika digunakan untuk cofiring langsung.")
    elif f.code == "ampas_tebu":
        summary_parts.append("Ampas tebu memiliki potensi kalori baik untuk Briket/Pellet setelah melalui pengeringan efisien (memanfaatkan limbah panas syngas/boiler).")
    else:
        summary_parts.append(f"Berdasarkan profil abu {f.ash_pct_db:.1f}% dan kalori, produk dengan kecocokan teknis tertinggi adalah {best_score[1]['label']} (skor {best_score[1]['suitability']['score']}).")

    return {
        "feedstock": f.model_dump(),
        "products": products,
        "rankings": {
            "best_by_profit": {"product": best_profit[0], "label": best_profit[1]["label"], "margin_rp_per_ton": best_profit[1]["economics"]["gross_profit_per_ton_feed"]},
            "best_by_energy": {"product": best_energy[0], "label": best_energy[1]["label"], "energy_gj_per_ton": best_energy[1]["energy_metrics"]["net_energy_output_gj"]},
            "best_by_carbon": {"product": best_carbon[0], "label": best_carbon[1]["label"], "tco2e_per_ton": best_carbon[1]["climate_metrics"]["net_climate_benefit_tco2e_per_ton"]},
            "best_by_suitability": {"product": best_score[0], "label": best_score[1]["label"], "score": best_score[1]["suitability"]["score"]},
        },
        "summary_recommendation": " ".join(summary_parts),
    }


class AllocationCapacity(BaseModel):
    max_pellet_ton: float | None = Field(None, ge=0, description="Kapasitas maksimum lini pellet (ton produk/periode)")
    max_briket_ton: float | None = Field(None, ge=0, description="Kapasitas maksimum lini briket (ton produk/periode)")
    max_biochar_ton: float | None = Field(None, ge=0, description="Kapasitas maksimum lini biochar (ton produk/periode)")
    max_silica_kg: float | None = Field(None, ge=0, description="Kapasitas maksimum lini silika (kg produk/periode)")


class AllocationRequest(BaseModel):
    feedstocks: list[FeedstockItem] = Field(..., min_length=1, max_length=20)
    capacities: AllocationCapacity = Field(default_factory=AllocationCapacity)
    objective: Literal["max_profit", "max_energy", "max_carbon", "balanced"] = "max_profit"
    price_overrides: dict[str, float] | None = None


def optimize_allocation(req: AllocationRequest) -> dict:
    """Mengoptimalkan alokasi stok multi-biomassa ke portofolio produk menggunakan Linear Programming (HiGHS).

    Variabel keputusan:
      x[i, j] = ton biomassa i yang dialokasikan ke lini produk j
      di mana i in feedstocks (0..N-1), j in ("bio_pellet", "briket", "biochar", "bio_silika") (0..3)
    """
    feedstocks = req.feedstocks
    n_feeds = len(feedstocks)
    prod_keys = list(PRODUCTS)
    n_prods = len(prod_keys)
    n_vars = n_feeds * n_prods

    # Evaluasi hasil per ton tiap kombinasi (feedstock, product)
    eval_matrix = []
    for f in feedstocks:
        row = evaluate_feedstock(f, req.price_overrides)
        eval_matrix.append(row["products"])

    # Vektor koefisien objektif c (SciPy linprog melakukan MINIMASI c^T x)
    c = np.zeros(n_vars)
    for i in range(n_feeds):
        for j, p in enumerate(prod_keys):
            idx = i * n_prods + j
            res = eval_matrix[i][p]
            if req.objective == "max_profit":
                # Maksimalkan laba kotor -> minimalkan (-profit)
                profit = res["economics"]["gross_profit_per_ton_feed"]
                c[idx] = -profit
            elif req.objective == "max_energy":
                # Maksimalkan energi bersih GJ
                energy = res["energy_metrics"]["net_energy_output_gj"]
                c[idx] = -energy
            elif req.objective == "max_carbon":
                # Maksimalkan reduksi karbon tCO2e
                carbon = res["climate_metrics"]["net_climate_benefit_tco2e_per_ton"]
                c[idx] = -carbon
            elif req.objective == "balanced":
                # Skala gabungan berbobot kesesuaian teknis & profitabilitas
                score = res["suitability"]["score"]
                margin_norm = res["economics"]["gross_profit_per_ton_feed"] / 5000.0
                c[idx] = -(score * 100.0 + margin_norm)

    # Batas variabel: jika skor kesesuaian teknis < 45, alokasi = 0 agar bahan tidak dipaksakan ke lini yang gagal spek
    bounds = []
    for i in range(n_feeds):
        for j, p in enumerate(prod_keys):
            score = eval_matrix[i][p]["suitability"]["score"]
            if score < 45.0:
                bounds.append((0.0, 0.0))
            else:
                bounds.append((0.0, feedstocks[i].tonnage))

    # Kendala Pertidaksamaan A_ub x <= b_ub
    A_ub = []
    b_ub = []

    # 1. Total alokasi per biomassa tidak boleh melebihi pasokan yang tersedia:
    #    sum_j x[i, j] <= tonnage[i]
    for i in range(n_feeds):
        row = np.zeros(n_vars)
        for j in range(n_prods):
            row[i * n_prods + j] = 1.0
        A_ub.append(row)
        b_ub.append(feedstocks[i].tonnage)

    # 2. Batas kapasitas lini mesin pabrik:
    caps = req.capacities
    # Kapasitas Pellet (ton produk)
    if caps.max_pellet_ton is not None and caps.max_pellet_ton > 0:
        row = np.zeros(n_vars)
        for i in range(n_feeds):
            yield_ton = eval_matrix[i]["bio_pellet"]["yield_kg_per_ton"] / 1000.0
            row[i * n_prods + 0] = yield_ton
        A_ub.append(row)
        b_ub.append(caps.max_pellet_ton)

    # Kapasitas Briket (ton produk)
    if caps.max_briket_ton is not None and caps.max_briket_ton > 0:
        row = np.zeros(n_vars)
        for i in range(n_feeds):
            yield_ton = eval_matrix[i]["briket"]["yield_kg_per_ton"] / 1000.0
            row[i * n_prods + 1] = yield_ton
        A_ub.append(row)
        b_ub.append(caps.max_briket_ton)

    # Kapasitas Biochar (ton produk)
    if caps.max_biochar_ton is not None and caps.max_biochar_ton > 0:
        row = np.zeros(n_vars)
        for i in range(n_feeds):
            yield_ton = eval_matrix[i]["biochar"]["yield_kg_per_ton"] / 1000.0
            row[i * n_prods + 2] = yield_ton
        A_ub.append(row)
        b_ub.append(caps.max_biochar_ton)

    # Kapasitas Bio-Silika (kg produk)
    if caps.max_silica_kg is not None and caps.max_silica_kg > 0:
        row = np.zeros(n_vars)
        for i in range(n_feeds):
            yield_kg = eval_matrix[i]["bio_silika"]["yield_kg_per_ton"]
            row[i * n_prods + 3] = yield_kg
        A_ub.append(row)
        b_ub.append(caps.max_silica_kg)

    # Selesaikan LP dengan HiGHS solver
    A_ub = np.array(A_ub) if A_ub else None
    b_ub = np.array(b_ub) if b_ub else None

    res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")
    if not res.success:
        raise ValueError(f"Optimasi alokasi gagal mencapai solusi optimal: {res.message}")

    x_sol = res.x

    # Strukturkan hasil alokasi
    items = []
    prod_totals_ton = {p: 0.0 for p in prod_keys}
    prod_totals_kg = {p: 0.0 for p in prod_keys}
    total_feed_used = 0.0

    total_revenue_rp = 0.0
    total_feed_cost_rp = 0.0
    total_proc_cost_rp = 0.0
    total_profit_rp = 0.0

    total_elec_kwh = 0.0
    total_drying_mj = 0.0
    total_energy_gj = 0.0
    total_co2e_t = 0.0

    for i in range(n_feeds):
        f = feedstocks[i]
        for j, p in enumerate(prod_keys):
            allocated_t = float(x_sol[i * n_prods + j])
            if allocated_t < 1e-4:
                continue

            allocated_t = round(allocated_t, 2)
            eval_p = eval_matrix[i][p]

            produced_kg = allocated_t * eval_p["yield_kg_per_ton"]
            produced_t = produced_kg / 1000.0 if p != "bio_silika" else produced_kg

            rev = allocated_t * eval_p["economics"]["revenue_per_ton_feed"]
            feed_c = allocated_t * eval_p["economics"]["feedstock_cost_per_ton"]
            proc_c = allocated_t * eval_p["economics"]["processing_cost_per_ton_feed"]
            prof = rev - (feed_c + proc_c)

            elec = allocated_t * eval_p["energy_metrics"]["process_kwh_per_ton_feed"]
            dry = allocated_t * eval_p["energy_metrics"]["thermal_drying_mj_per_ton_feed"]
            en_gj = allocated_t * eval_p["energy_metrics"]["net_energy_output_gj"]
            co2_t = allocated_t * eval_p["climate_metrics"]["net_climate_benefit_tco2e_per_ton"]

            total_feed_used += allocated_t
            prod_totals_kg[p] += produced_kg
            prod_totals_ton[p] += (produced_kg / 1000.0)

            total_revenue_rp += rev
            total_feed_cost_rp += feed_c
            total_proc_cost_rp += proc_c
            total_profit_rp += prof

            total_elec_kwh += elec
            total_drying_mj += dry
            total_energy_gj += en_gj
            total_co2e_t += co2_t

            items.append({
                "feedstock_code": f.code,
                "feedstock_name": f.name,
                "product": p,
                "product_label": PRODUCT_META[p]["name"],
                "allocated_feedstock_ton": allocated_t,
                "produced_qty": round(produced_kg if p == "bio_silika" else produced_t, 1),
                "produced_unit": "kg" if p == "bio_silika" else "ton",
                "revenue_rp": round(rev, 0),
                "feedstock_cost_rp": round(feed_c, 0),
                "processing_cost_rp": round(proc_c, 0),
                "gross_profit_rp": round(prof, 0),
                "net_energy_gj": round(en_gj, 2),
                "co2e_benefit_t": round(co2_t, 2),
                "suitability_score": eval_p["suitability"]["score"],
            })

    # Analisis kapasitas & utilisasi
    cap_util = {}
    if caps.max_pellet_ton:
        cap_util["bio_pellet"] = {
            "capacity": caps.max_pellet_ton,
            "produced": round(prod_totals_ton["bio_pellet"], 2),
            "utilization_pct": round((prod_totals_ton["bio_pellet"] / caps.max_pellet_ton) * 100.0, 1),
        }
    if caps.max_briket_ton:
        cap_util["briket"] = {
            "capacity": caps.max_briket_ton,
            "produced": round(prod_totals_ton["briket"], 2),
            "utilization_pct": round((prod_totals_ton["briket"] / caps.max_briket_ton) * 100.0, 1),
        }
    if caps.max_biochar_ton:
        cap_util["biochar"] = {
            "capacity": caps.max_biochar_ton,
            "produced": round(prod_totals_ton["biochar"], 2),
            "utilization_pct": round((prod_totals_ton["biochar"] / caps.max_biochar_ton) * 100.0, 1),
        }
    if caps.max_silica_kg:
        cap_util["bio_silika"] = {
            "capacity": caps.max_silica_kg,
            "produced": round(prod_totals_kg["bio_silika"], 1),
            "utilization_pct": round((prod_totals_kg["bio_silika"] / caps.max_silica_kg) * 100.0, 1),
        }

    # Wawasan manajerial
    insights = []
    if any(it["product"] == "bio_silika" and "sekam" in it["feedstock_code"] for it in items):
        insights.append("Alokasi sekam padi ke jalur Bio-Silika berhasil merealisasikan nilai tambah tertinggi pabrik.")
    if any(it["product"] == "briket" and "tempurung" in it["feedstock_code"] for it in items):
        insights.append("Tempurung kelapa sepenuhnya diarahkan ke lini Briket Arang untuk meraih harga jual premium shisha/BBQ.")
    if any(it["product"] == "bio_pellet" and ("serbuk" in it["feedstock_code"] or "sengon" in it["feedstock_code"]) for it in items):
        insights.append("Serbuk gergaji kayu dimanfaatkan pada lini Bio-Pellet untuk memenuhi standar ekspor ISO 17225-2.")

    margin_overall = (total_profit_rp / max(1.0, total_revenue_rp)) * 100.0

    return {
        "status": "success",
        "objective": req.objective,
        "objective_label": ("Maksimalkan Keuntungan Bersih (Max Profit)" if req.objective == "max_profit" else
                            "Maksimalkan Energi Bersih (Max Energy)" if req.objective == "max_energy" else
                            "Maksimalkan Reduksi Karbon (Max Carbon)" if req.objective == "max_carbon" else "Portofolio Seimbang"),
        "total_feedstock_input_ton": round(total_feed_used, 2),
        "product_outputs": {
            "bio_pellet_ton": round(prod_totals_ton["bio_pellet"], 2),
            "briket_ton": round(prod_totals_ton["briket"], 2),
            "biochar_ton": round(prod_totals_ton["biochar"], 2),
            "bio_silika_kg": round(prod_totals_kg["bio_silika"], 1),
        },
        "financial_summary": {
            "total_revenue_rp": round(total_revenue_rp, 0),
            "total_feedstock_cost_rp": round(total_feed_cost_rp, 0),
            "total_processing_cost_rp": round(total_proc_cost_rp, 0),
            "total_gross_profit_rp": round(total_profit_rp, 0),
            "overall_gross_margin_pct": round(margin_overall, 1),
        },
        "energy_summary": {
            "total_electricity_kwh": round(total_elec_kwh, 1),
            "total_drying_heat_mj": round(total_drying_mj, 1),
            "plant_sec_kwh_per_ton_input": round(total_elec_kwh / max(0.01, total_feed_used), 1),
            "total_product_energy_gj": round(total_energy_gj, 2),
        },
        "climate_summary": {
            "total_co2e_benefit_ton": round(total_co2e_t, 2),
        },
        "capacity_utilization": cap_util,
        "allocations": items,
        "managerial_insights": insights,
    }
