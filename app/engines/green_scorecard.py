"""Engine ⑬ — Green Scorecard: jejak karbon bersih, sirkularitas, dan metrik green chemistry dari DATA NYATA
(batch, rute, retur, dompet petani) — bukan simulasi.

Neraca karbon (per periode, tCO₂e):
  + Pembakaran terbuka dihindari  = t sekam kering × porsi_dibakar × CF × (EF_CH4·GWP_CH4 + EF_N2O·GWP_N2O)
                                   (CO₂ pembakaran biomassa = biogenik → tidak dihitung; IPCC 2006 Vol.4 Ch.2)
  Removal (DAPAT DIKLAIM) = t biochar KERING yang terbukti diserahkan ke lahan × F_C × F̄_perm × 44/12
                            − Scope 1 (solar/LPG batch) − CH₄ reaktor − listrik − angkut,  lalu × (1 − potongan ketidakpastian)
  Potensi                 = seluruh biochar kering produksi × F_C × F̄_perm × 44/12  (informasi, BUKAN klaim)
  F_perm (IPCC 2019 Ap.4): 350–<450 °C 0,65 · 450–<600 °C 0,80 · ≥600 °C 0,89 · suhu tak tercatat → 0 (tak boleh diklaim)
  Emisi DIHINDARI (pembakaran terbuka) dilaporkan TERPISAH dan TIDAK PERNAH dijumlahkan ke removal
  (Puro.earth = removal-only; VM0044 baseline sourcing = 0; GHG Protocol LSR).
  Bio-pellet yang dibakar BUKAN sekuestrasi (karbonnya kembali ke atmosfer) → tidak dihitung di sini; manfaat
  substitusi batu bara dilaporkan terpisah (Engine ⑦) agar tidak hitung ganda.

Sirkularitas: valorisasi massa, porsi biochar kembali ke petani, laju retur & porsi retur yang dipulihkan.
Green chemistry (lini silika): E-factor padat (Sheldon) = limbah padat ÷ produk; efisiensi ekstraksi SiO₂.
"""

from ..params import P

REFERENCES = [
    "IPCC (2006) Guidelines Vol.4 Ch.2 Tabel 2.5–2.6 — emisi non-CO₂ pembakaran residu pertanian.",
    "IPCC (2019) Refinement Vol.4 Ch.2 Appendix 4 — biochar: F_C, F_perm menurut suhu produksi.",
    "ISO 14083:2023 / GLEC Framework v3.2 — emisi rantai transport.",
    "Sheldon, R.A. (2017). The E factor 25 years on. Green Chemistry 19:18-43.",
    "Ellen MacArthur Foundation (2019). Circularity Indicators — Material Circularity Indicator.",
]


def f_perm(temp_c: float | None) -> tuple[float, str]:
    if temp_c is None:
        return 0.0, "suhu batch tidak dicatat — F_perm 0 (tidak boleh diklaim)"
    if temp_c < 450:
        return 0.65, "350–<450 °C"
    if temp_c < 600:
        return 0.80, "450–<600 °C"
    return 0.89, "≥600 °C"


def scorecard(batches: list[dict], routes: list[dict], returns: list[dict], received_kg: float,
              biochar_to_farmers_kg: float, biochar_end_use_kg: float = 0.0, fc_override: float | None = None) -> dict:
    """batches: [{input_kg, moisture, ash, temp_c, outputs{p: kg}, losses{k: kg}, kwh}]
    routes: [{co2e_wtw_kg, distance_source}] (rute selesai); returns: [{quantity_kg, disposition, status}].
    fc_override: fraksi C-org hasil lab (klaim F11) menggantikan parameter karbon.biochar_c_org_fraction."""
    gwp_ch4, gwp_n2o = P("karbon.gwp_ch4"), P("karbon.gwp_n2o")
    ef_burn = (P("karbon.open_burning_ch4_g_per_kg") * gwp_ch4 + P("karbon.open_burning_n2o_g_per_kg") * gwp_n2o) / 1e6
    share, cf = P("karbon.open_burning_share"), P("karbon.open_burning_combustion_factor")
    fc = fc_override if fc_override is not None else P("karbon.biochar_c_org_fraction")

    husk_t = sum(b["input_kg"] for b in batches) / 1000
    dry_t = sum(b["input_kg"] * (1 - (b.get("moisture") or 0) / 100) for b in batches) / 1000
    avoided = dry_t * share * cf * ef_burn * 1000                     # t × (kg CO₂e/kg) → t CO₂e
    dry_char = 1 - P("karbon.biochar_moisture_pct") / 100
    potential, perm_notes, char_dry_t, perm_weighted = 0.0, set(), 0.0, 0.0
    for b in batches:
        fp, note = f_perm(b.get("temp_c"))
        perm_notes.add(note)
        t = b["outputs"].get("biochar", 0) / 1000 * dry_char
        char_dry_t += t
        perm_weighted += t * fp
        potential += t * fc * fp * 44 / 12
    fp_avg = perm_weighted / char_dry_t if char_dry_t > 0 else 0.0
    # Hanya biochar yang TERBUKTI diserahkan ke lahan (serah-terima tercatat) yang boleh diklaim (Puro/VM0044 end-use)
    end_use_dry_t = min(biochar_end_use_kg / 1000 * dry_char, char_dry_t) if char_dry_t > 0 else 0.0
    seq = end_use_dry_t * fc * fp_avg * 44 / 12
    transport = sum(r.get("co2e_wtw_kg") or 0 for r in routes) / 1000
    kwh = sum(b.get("kwh") or 0 for b in batches)
    electricity = kwh * P("karbon.grid_ef_kg_co2_per_kwh") / 1000
    from .emission import fuel_factors
    diesel_l = sum(b.get("diesel_l") or 0 for b in batches)
    lpg_kg = sum(b.get("lpg_kg") or 0 for b in batches)
    scope1 = (diesel_l * fuel_factors()["wtw_kg_per_l"] + lpg_kg * P("karbon.lpg_ef_kg_co2e_per_kg")) / 1000
    ch4_rate = P("karbon.pyrolysis_ch4_kg_per_t_biochar")
    pyro_ch4 = char_dry_t * ch4_rate * gwp_ch4 / 1000
    project = transport + electricity + scope1 + pyro_ch4
    u = P("karbon.uncertainty_deduction_pct") / 100
    net = (seq - project) * (1 - u) if seq - project > 0 else seq - project
    net_potential = (potential - project) * (1 - u) if potential - project > 0 else potential - project

    products = sum(sum(b["outputs"].values()) for b in batches)
    input_kg = husk_t * 1000
    biochar_kg = sum(b["outputs"].get("biochar", 0) for b in batches)
    ret_kg = sum(r["quantity_kg"] for r in returns)
    recovered = sum(r["quantity_kg"] for r in returns if r.get("disposition") in
                    ("keringkan_ulang", "turun_grade", "bahan_bakar_boiler", "kembalikan_ke_pengirim"))
    resolved = sum(r["quantity_kg"] for r in returns if r.get("status") == "selesai")

    silica = sum(b["outputs"].get("bio_silika", 0) for b in batches)
    solid_waste = sum(b["losses"].get("residu_ekstraksi", 0) + b["losses"].get("susut_proses", 0) for b in batches)
    sio2_theory = sum(b["input_kg"] * (1 - (b.get("moisture") or 0) / 100) * (b.get("ash") or 0) / 100
                      * P("rendemen.sio2_fraction_of_ash") for b in batches)
    gps_routes = sum(1 for r in routes if r.get("distance_source") == "gps")

    def pct(a, b):
        return round(100 * a / b, 2) if b > 1e-9 else None

    return {
        "carbon_tco2e": {
            "avoided_open_burning": round(avoided, 3),          # dilaporkan terpisah, TIDAK masuk net
            "biochar_sequestration": round(seq, 3),             # hanya biochar end-use terbukti
            "biochar_sequestration_potential": round(potential, 3),
            "transport_emissions": round(-transport, 3),
            "process_electricity": round(-electricity, 3),
            "scope1_fuel": round(-scope1, 3),
            "pyrolysis_ch4": round(-pyro_ch4, 3),
            "uncertainty_deduction_pct": round(u * 100, 1),
            "net": round(net, 3),                                # = removal bersih yang dapat diklaim
            "net_potential": round(net_potential, 3),
            "net_kg_per_ton_husk": round(net * 1000 / husk_t, 1) if husk_t > 0 else None,
            "transport_kg_per_ton_husk": round(transport * 1000 / husk_t, 2) if husk_t > 0 else None,
            "biochar_dry_t": round(char_dry_t, 3), "biochar_end_use_dry_t": round(end_use_dry_t, 3),
            "f_perm_weighted": round(fp_avg, 3),
            "status": "estimasi internal — belum diverifikasi pihak ketiga (bukan kredit karbon)",
            "claim_gaps": [g for g, bad in (
                ("CH₄ reaktor belum diukur (karbon.pyrolysis_ch4_kg_per_t_biochar = 0)", ch4_rate == 0),
                ("F_C & H/C_org masih parameter, belum uji lab per batch", fc_override is None),
                ("Ada batch tanpa suhu pirolisis → F_perm 0", any(b.get("temp_c") is None for b in batches)),
                ("Belum ada serah-terima biochar ke lahan pada periode ini", biochar_end_use_kg <= 0 and char_dry_t > 0),
            ) if bad],
        },
        "circularity": {
            "husk_processed_ton": round(husk_t, 3),
            "mass_valorization_pct": pct(products, input_kg),
            "biochar_returned_to_farmers_pct": pct(biochar_to_farmers_kg, biochar_kg),
            "return_rate_pct": pct(ret_kg, received_kg + ret_kg),
            "returns_recovered_pct": pct(recovered, resolved),
        },
        "green_chemistry": {
            "silica_e_factor_solid": round(solid_waste / silica, 3) if silica > 0 else None,
            "silica_extraction_efficiency_pct": pct(silica, sio2_theory),
            "note": ("E-factor padat = (residu ekstraksi + susut) ÷ bio-silika. Pemakaian NaOH/asam belum dicatat "
                     "dalam kg → PMI & emisi hulu bahan kimia belum bisa dihitung (lihat rekomendasi)."),
        },
        "data_quality": {
            "routes_completed": len(routes), "routes_with_gps_distance": gps_routes,
            "batches": len(batches), "f_perm_basis": sorted(perm_notes),
            "electricity_kwh_recorded": round(kwh, 1),
        },
        "recommendations": recommendations(transport, husk_t, gps_routes, len(routes), silica, solid_waste,
                                           pct(biochar_to_farmers_kg, biochar_kg), pct(ret_kg, received_kg + ret_kg)),
        "computation_details": {
            "formulas": [
                "dihindari = t_kering × porsi_dibakar × CF × (EF_CH4·GWP_CH4 + EF_N2O·GWP_N2O)",
                "removal = t_biochar_kering_end_use × F_C × F̄_perm × 44/12",
                "proyek = angkut + listrik + Scope 1 (solar/LPG) + CH₄ reaktor × GWP",
                "neto = (removal − proyek) × (1 − potongan ketidakpastian)  ·  emisi dihindari dilaporkan terpisah",
                "E-factor padat = limbah padat ÷ produk silika",
            ],
            "parameters_used": ["karbon.open_burning_share", "karbon.open_burning_combustion_factor",
                                "karbon.open_burning_ch4_g_per_kg", "karbon.open_burning_n2o_g_per_kg",
                                "karbon.gwp_ch4", "karbon.gwp_n2o", "karbon.biochar_c_org_fraction",
                                "karbon.grid_ef_kg_co2_per_kwh", "rendemen.sio2_fraction_of_ash",
                                "karbon.biochar_moisture_pct", "karbon.uncertainty_deduction_pct",
                                "karbon.pyrolysis_ch4_kg_per_t_biochar", "karbon.lpg_ef_kg_co2e_per_kg"],
            "references": REFERENCES,
        },
    }


def recommendations(transport_t, husk_t, gps_routes, n_routes, silica, solid_waste, returned_pct, return_rate) -> list[dict]:
    rec = []
    if n_routes and gps_routes < n_routes:
        rec.append({"area": "green supply chain", "action": "Aktifkan GPS di semua rute (store & forward) agar emisi "
                    "angkut memakai jarak nyata, bukan estimasi — syarat data primer ISO 14083."})
    if husk_t > 0 and transport_t * 1000 / husk_t > 15:
        rec.append({"area": "green supply chain", "action": "Emisi angkut > 15 kg CO₂e/t sekam: pakai dispatch "
                    "OR-Tools multi-supir, naikkan utilisasi bak (pemadatan/baling sekam), jadwalkan jemput per klaster."})
    if silica > 0 and solid_waste / silica > 1:
        rec.append({"area": "green chemistry", "action": "E-factor silika > 1: daur ulang larutan induk (mother liquor) "
                    "NaOH, presipitasi dengan CO₂ gas buang (karbonasi) menggantikan H₂SO₄/HCl, catat kg bahan kimia "
                    "per batch agar PMI terukur."})
    rec.append({"area": "green chemistry", "action": "Pakai syngas pirolisis untuk pengering & kalsinasi (kurangi "
                "listrik/LPG); pertimbangkan pelindian asam sitrat (biodegradable) untuk jalur silika kemurnian tinggi."})
    if returned_pct is not None and returned_pct < 5:
        rec.append({"area": "ekonomi sirkular", "action": "Porsi biochar kembali ke petani < 5%: naikkan "
                    "sirkular.farmer_return_share atau tautkan lebih banyak lot ke panen petani (ketertelusuran)."})
    if return_rate is not None and return_rate > 5:
        rec.append({"area": "ekonomi sirkular", "action": "Laju retur > 5%: subsidi terpal/karung anti-hujan & "
                    "prioritas jemput sekam berisiko jamur (kadar air > ambang) ≤ 48 jam."})
    rec.append({"area": "MRV karbon", "action": "Ukur C organik & rasio H/C_org biochar per batch di lab (Puro.earth "
                "mensyaratkan H/C_org < 0,7) dan verifikasi pihak ketiga sebelum klaim kredit."})
    return rec
