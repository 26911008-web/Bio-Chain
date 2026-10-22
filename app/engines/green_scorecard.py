"""Engine ⑬ — Green Scorecard: jejak karbon bersih, sirkularitas, dan metrik green chemistry dari DATA NYATA
(batch, rute, retur, dompet petani) — bukan simulasi.

Neraca karbon (per periode, tCO₂e):
  + Pembakaran terbuka dihindari  = t sekam kering × porsi_dibakar × CF × (EF_CH4·GWP_CH4 + EF_N2O·GWP_N2O)
                                   (CO₂ pembakaran biomassa = biogenik → tidak dihitung; IPCC 2006 Vol.4 Ch.2)
  + Sekuestrasi biochar           = t biochar (ke tanah) × F_C × F_perm(T) × 44/12   (IPCC 2019 Refinement Ap.4)
                                   F_perm: 350–<450 °C 0,65 · 450–<600 °C 0,80 · ≥600 °C 0,89
  − Emisi angkut                  = Σ CO₂e WTW rute (Engine ⑫, ISO 14083)
  − Emisi listrik proses          = Σ kWh batch × faktor emisi grid
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
        return 0.80, "suhu batch tidak dicatat — dipakai 0,80 (450–600 °C, asumsi)"
    if temp_c < 450:
        return 0.65, "350–<450 °C"
    if temp_c < 600:
        return 0.80, "450–<600 °C"
    return 0.89, "≥600 °C"


def scorecard(batches: list[dict], routes: list[dict], returns: list[dict], received_kg: float,
              biochar_to_farmers_kg: float) -> dict:
    """batches: [{input_kg, moisture, ash, temp_c, outputs{p: kg}, losses{k: kg}, kwh}]
    routes: [{co2e_wtw_kg, distance_source}] (rute selesai); returns: [{quantity_kg, disposition, status}]."""
    gwp_ch4, gwp_n2o = P("karbon.gwp_ch4"), P("karbon.gwp_n2o")
    ef_burn = (P("karbon.open_burning_ch4_g_per_kg") * gwp_ch4 + P("karbon.open_burning_n2o_g_per_kg") * gwp_n2o) / 1e6
    share, cf = P("karbon.open_burning_share"), P("karbon.open_burning_combustion_factor")
    fc = P("karbon.biochar_c_org_fraction")

    husk_t = sum(b["input_kg"] for b in batches) / 1000
    dry_t = sum(b["input_kg"] * (1 - (b.get("moisture") or 0) / 100) for b in batches) / 1000
    avoided = dry_t * share * cf * ef_burn * 1000                     # t × (kg CO₂e/kg) → t CO₂e
    seq, perm_notes = 0.0, set()
    for b in batches:
        fp, note = f_perm(b.get("temp_c"))
        perm_notes.add(note)
        seq += b["outputs"].get("biochar", 0) / 1000 * fc * fp * 44 / 12
    transport = sum(r.get("co2e_wtw_kg") or 0 for r in routes) / 1000
    kwh = sum(b.get("kwh") or 0 for b in batches)
    electricity = kwh * P("karbon.grid_ef_kg_co2_per_kwh") / 1000
    net = avoided + seq - transport - electricity

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
            "avoided_open_burning": round(avoided, 3),
            "biochar_sequestration": round(seq, 3),
            "transport_emissions": round(-transport, 3),
            "process_electricity": round(-electricity, 3),
            "net": round(net, 3),
            "net_kg_per_ton_husk": round(net * 1000 / husk_t, 1) if husk_t > 0 else None,
            "transport_kg_per_ton_husk": round(transport * 1000 / husk_t, 2) if husk_t > 0 else None,
            "status": "estimasi internal — belum diverifikasi pihak ketiga (bukan kredit karbon)",
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
                "sekuestrasi = t_biochar × F_C × F_perm(T) × 44/12",
                "neto = dihindari + sekuestrasi − angkut − listrik",
                "E-factor padat = limbah padat ÷ produk silika",
            ],
            "parameters_used": ["karbon.open_burning_share", "karbon.open_burning_combustion_factor",
                                "karbon.open_burning_ch4_g_per_kg", "karbon.open_burning_n2o_g_per_kg",
                                "karbon.gwp_ch4", "karbon.gwp_n2o", "karbon.biochar_c_org_fraction",
                                "karbon.grid_ef_kg_co2_per_kwh", "rendemen.sio2_fraction_of_ash"],
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
