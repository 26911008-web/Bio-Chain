"""Engine ⑦ — ESG Carbon Calculator.

Menghitung pengurangan emisi CO₂ dari pemanfaatan biomassa sekam padi
vs baseline batu bara, menggunakan metodologi IPCC 2006 Tier 2.

Referensi:
- IPCC 2006 Guidelines Vol.2 Ch.2: Stationary Combustion
- Perpres 98/2021 → Perpres 110/2025: Nilai Ekonomi Karbon Indonesia
- Faktor emisi default IPCC untuk sub-bituminous coal: 96.1 kgCO₂/GJ
"""

from pydantic import BaseModel, Field

from ..params import P

class CarbonInput(BaseModel):
    biomass_ton: float = Field(..., gt=0, description="Massa biomassa sekam (ton)")
    transport_km: float = Field(0, ge=0, description="Jarak angkut total (km)")
    moisture_pct: float = Field(11, ge=0, le=60, description="Kadar air biomassa (%)")
    cofiring_ratio: float = Field(0.20, ge=0.01, le=1.0,
                                   description="Rasio biomassa dalam co-firing")


class CarbonResult(BaseModel):
    biomass_energy_gj: float
    coal_displaced_ton: float
    emission_avoided_tco2: float
    transport_emission_tco2: float
    net_reduction_tco2: float
    carbon_credit_equivalent: float
    srn_ppi_eligible: bool
    methodology: str
    carbon_price_per_tco2_rp: float | None = None
    carbon_value_rp: float | None = None
    carbon_value_note: str | None = None
    computation_details: dict | None = None


def calculate_carbon_reduction(inp: CarbonInput) -> CarbonResult:
    """Hitung pengurangan emisi CO₂ dari substitusi batubara dengan biomassa.

    Formula inti (IPCC Tier 2):
      E_avoided = (M_biomass × HHV_biomass × η) / HHV_coal × EF_coal
      E_transport = M_biomass × D_km × EF_transport
      Net = E_avoided - E_transport
    """
    RICE_HUSK_HHV_MJ_KG, BOILER_EFFICIENCY = P("karbon.husk_hhv_mj_kg"), P("karbon.boiler_efficiency")
    COAL_HHV_MJ_KG, COAL_EF_KG_CO2_PER_GJ = P("karbon.coal_hhv_mj_kg"), P("karbon.coal_ef_kg_co2_per_gj")
    TRANSPORT_EF_KG_CO2_PER_TONKM = P("karbon.transport_ef_kg_co2_per_tkm")
    dry_factor = 1 - inp.moisture_pct / 100
    biomass_energy_gj = (
        inp.biomass_ton * 1000          # kg
        * dry_factor                     # basis kering
        * RICE_HUSK_HHV_MJ_KG          # MJ/kg
        * BOILER_EFFICIENCY             # efisiensi
        / 1000                          # → GJ
    )

    coal_displaced_ton = biomass_energy_gj * 1000 / (COAL_HHV_MJ_KG * 1000)

    emission_avoided = biomass_energy_gj * COAL_EF_KG_CO2_PER_GJ / 1000  # → tCO₂

    transport_emission = (
        inp.biomass_ton * inp.transport_km
        * TRANSPORT_EF_KG_CO2_PER_TONKM / 1000
    )

    net = emission_avoided - transport_emission

    carbon_price = P("karbon.price_per_tco2_rp")
    if carbon_price is not None and carbon_price > 0:
        carbon_value_rp = round(net * carbon_price)
        carbon_value_note = f"Harga karbon: Rp {carbon_price:,.0f}/tCO₂e (menu Parameter)"
    else:
        carbon_value_rp = None
        carbon_value_note = "Isi harga pasar karbon di menu Parameter untuk melihat potensi nilai NEK"

    details = {
        "method": "IPCC 2006 Vol.2 Ch.2 — substitusi bahan bakar (Stationary Combustion)",
        "inputs": {
            "biomass_ton": inp.biomass_ton,
            "transport_km": inp.transport_km,
            "moisture_pct": inp.moisture_pct,
            "cofiring_ratio": inp.cofiring_ratio,
        },
        "steps": [
            {"step": "Energi biomassa", "formula": "ton × (1 - kadar_air%) × HHV_sekam × η", "value": round(biomass_energy_gj, 3), "unit": "GJ"},
            {"step": "Batubara tergantikan", "formula": "Energi biomassa ÷ HHV_batubara", "value": round(coal_displaced_ton, 3), "unit": "ton"},
            {"step": "Emisi dihindari", "formula": "Energi biomassa × EF_batubara ÷ 1000", "value": round(emission_avoided, 4), "unit": "tCO₂"},
            {"step": "Emisi angkut", "formula": "ton × km × EF_angkut ÷ 1000", "value": round(transport_emission, 4), "unit": "tCO₂"},
            {"step": "Pengurangan neto", "formula": "Emisi dihindari − Emisi angkut", "value": round(net, 4), "unit": "tCO₂e"},
        ],
        "parameters_used": [
            "karbon.husk_hhv_mj_kg",
            "karbon.boiler_efficiency",
            "karbon.coal_hhv_mj_kg",
            "karbon.coal_ef_kg_co2_per_gj",
            "karbon.transport_ef_kg_co2_per_tkm",
            "karbon.price_per_tco2_rp",
        ],
        "references": [
            "IPCC (2006) Guidelines Vol. 2 Ch. 2: Stationary Combustion",
            "Perpres 98/2021 & Perpres 110/2025: Nilai Ekonomi Karbon Indonesia",
        ],
    }

    return CarbonResult(
        biomass_energy_gj=round(biomass_energy_gj, 3),
        coal_displaced_ton=round(coal_displaced_ton, 3),
        emission_avoided_tco2=round(emission_avoided, 4),
        transport_emission_tco2=round(transport_emission, 4),
        net_reduction_tco2=round(net, 4),
        carbon_credit_equivalent=round(net, 4),
        srn_ppi_eligible=net > 0,
        methodology="IPCC 2006 Tier 2 — Stationary Combustion (biomass co-firing)",
        carbon_price_per_tco2_rp=carbon_price,
        carbon_value_rp=carbon_value_rp,
        carbon_value_note=carbon_value_note,
        computation_details=details,
    )
