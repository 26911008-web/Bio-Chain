"""Engine ⑪ — Ekonomi Pabrik: mass balance 1 input → 3 output + loss, biaya produksi, pricing sekam.

Alur proses per 1 kg sekam diterima (kadar air M, abu A basis kering), 3 jalur bio-silika:

  Sekam ──┬─► lini pellet (s_p) ─ keringkan ─ susut ─────────────────────────► BIO-PELLET
          ├─► pirolisis ──► char (rendemen Y Engine ②) ──┬─► BIOCHAR dijual
          │                                              └─► [jalur "biochar"] ekstraksi alkali ─► BIO-SILIKA
          ├─► [jalur "abu_pembakaran"] tungku (s_x) ─► panas (kredit) + abu ─► ekstraksi ─► BIO-SILIKA
          └─► [jalur "sekam_langsung"] pelindian asam + kalsinasi (s_x) ──────────► BIO-SILIKA (kemurnian tinggi)
  LOSS = air + volatil/syngas (pirolisis) + gas pembakaran/kalsinasi + residu ekstraksi + susut proses

Model tertutup secara konstruksi (Σ output + Σ loss = 1 kg), sehingga selisih pada batch NYATA hanya
berasal dari data timbangan → indikator mutu data (penutupan mass balance).

Harga beli sekam (netback, per kg diterima):
  nilai     = Σ rendemen_p × harga_p × (1 − kontaminan)
  lantai    = nilai − biaya variabel                    (titik tutup jangka pendek)
  plafon    = lantai − biaya tetap per kg (volume rencana)  (impas penuh, Cost-Volume-Profit)
  target    = plafon − margin target × nilai
Koreksi kadar air kontrak memakai basis bahan kering: P = P_acuan × (1 − M)/(1 − M_acuan).
Alokasi biaya bersama ke produk: Net Realizable Value atau unit fisik (Horngren, Cost Accounting).
Semua angka asumsi dibaca dari menu Parameter (kelompok "pabrik", "rendemen", "limbah", "energi").
"""

from dataclasses import dataclass

from pydantic import BaseModel, Field

from ..params import P
from .quality import biochar_yield_db

PRODUCTS = ("bio_pellet", "biochar", "bio_silika")
PRODUCT_LABEL = {"bio_pellet": "Bio-pellet / Briket", "biochar": "Biochar", "bio_silika": "Bio-silika"}
# bio_oil = kondensat/tar pirolisis (bisa dijual sebagai asap cair) — dicatat di neraca massa agar BOM lengkap
LOSS_KINDS = ("air", "volatil_syngas", "gas_pembakaran", "bio_oil", "residu_ekstraksi", "susut_proses")
SILICA_ROUTES = ("biochar", "abu_pembakaran", "sekam_langsung")
_PRICE_KEYS = {"bio_pellet": "pabrik.price_pellet_per_kg", "biochar": "pabrik.price_biochar_per_kg",
               "bio_silika": "pabrik.price_silica_per_kg"}


class PriceMissing(ValueError):
    """Harga jual belum diisi — hasil ekonomi tidak boleh dihitung dengan angka karangan."""


def prices(overrides: dict[str, float | None] | None = None) -> dict[str, float]:
    """Harga jual aktif: isian langsung (override) > menu Parameter. Tanpa angka bawaan."""
    overrides = overrides or {}
    out = {p: overrides.get(p) if overrides.get(p) is not None else P(k) for p, k in _PRICE_KEYS.items()}
    missing = [PRODUCT_LABEL[p] for p, v in out.items() if v is None]
    if missing:
        raise PriceMissing(f"Harga jual belum diisi: {', '.join(missing)}. Isi di menu Parameter → "
                           "Pabrik & Biaya Produksi, atau di kolom harga kalkulator.")
    return out


@dataclass
class YieldSplit:
    """Massa (kg) per 1 kg sekam diterima."""
    outputs: dict[str, float]
    losses: dict[str, float]
    water_dried_kg: float          # air yang diuapkan di pengering (berbiaya), bukan di reaktor
    char_kg: float
    route: str = "biochar"
    heat_recovered_mj: float = 0.0  # panas tungku (jalur abu pembakaran) → kredit biaya pengeringan

    @property
    def closure(self) -> float:
        return sum(self.outputs.values()) + sum(self.losses.values())


def process_yields(moisture_pct: float, ash_pct_db: float, temp_c: float | None = None,
                   pellet_share: float | None = None, silica_share: float | None = None,
                   silica_route: str | None = None, silica_husk_share: float | None = None) -> YieldSplit:
    temp_c = P("limbah.pyrolysis_temp_c") if temp_c is None else temp_c
    route = P("pabrik.silica_route") if silica_route is None else silica_route
    if route not in SILICA_ROUTES:
        raise ValueError(f"Jalur silika tidak dikenal: {route}")
    s_p = P("pabrik.pellet_share") if pellet_share is None else pellet_share
    s_s = (P("pabrik.silica_share_of_biochar") if silica_share is None else silica_share) if route == "biochar" else 0.0
    s_x = 0.0 if route == "biochar" else (P("pabrik.silica_husk_share") if silica_husk_share is None else silica_husk_share)
    if s_p + s_x > 1 + 1e-12:
        raise ValueError("Porsi pellet + porsi silika dari sekam melebihi 1.")
    m, dry = moisture_pct / 100, 1 - moisture_pct / 100
    sio2 = P("rendemen.sio2_fraction_of_ash")
    # Lini pellet: keringkan ke kadar air produk (tidak menambah air bila sudah lebih kering)
    m_p = P("pabrik.pellet_moisture_pct") / 100
    pellet_wet = s_p * dry / (1 - m_p) if m > m_p else s_p
    water_pellet = s_p - pellet_wet
    pellet_loss = pellet_wet * P("pabrik.pellet_process_loss")
    pellet = pellet_wet - pellet_loss
    # Lini silika dari sekam (jalur abu pembakaran / sekam langsung): organik terbakar, abu → silika
    ash_x = s_x * dry * ash_pct_db / 100
    eff_x = P("pabrik.silica_eff_ash") if route == "abu_pembakaran" else P("pabrik.silica_eff_direct")
    silica_x = ash_x * sio2 * eff_x if s_x else 0.0
    combustion_gas = s_x * dry - ash_x                          # bahan organik kering → CO₂ + H₂O (+ panas)
    heat_mj = s_x * dry * P("karbon.husk_hhv_mj_kg") * P("limbah.eta_boiler_heat") if route == "abu_pembakaran" else 0.0
    # Lini pirolisis: seluruh air & volatil keluar; char = bahan kering × rendemen Engine ②
    feed = 1 - s_p - s_x
    y = biochar_yield_db(temp_c, ash_pct_db) / 100
    char = feed * dry * y
    volatiles = feed * dry * (1 - y)
    water_pyro = feed * m
    m_t = P("pabrik.dryer_target_moisture_pct") / 100
    water_dryer = feed * max(0.0, m - dry * m_t / (1 - m_t))     # sisanya menguap di reaktor (panas syngas)
    # Ekstraksi silika dari porsi char: abu tertahan seluruhnya di char
    to_ext = char * s_s
    ash_frac_char = min(0.95, ash_pct_db / 100 / y) if y > 0 else 0.0
    silica_c = to_ext * ash_frac_char * sio2 * P("pabrik.silica_extraction_eff")
    return YieldSplit(
        outputs={"bio_pellet": pellet, "biochar": char - to_ext, "bio_silika": silica_c + silica_x},
        losses={"air": water_pellet + water_pyro + s_x * m, "volatil_syngas": volatiles,
                "gas_pembakaran": combustion_gas, "residu_ekstraksi": (to_ext - silica_c) + (ash_x - silica_x),
                "susut_proses": pellet_loss},
        water_dried_kg=water_pellet + water_dryer, char_kg=char, route=route, heat_recovered_mj=heat_mj)


def variable_cost_per_kg(ys: YieldSplit) -> dict[str, float]:
    """Biaya variabel (Rp) per 1 kg sekam diterima, dirinci."""
    tariff = P("energi.tariff_rp_per_kwh")
    products_kg = sum(ys.outputs.values())
    chem = P("pabrik.chemical_cost_direct_per_kg_silica") if ys.route == "sekam_langsung" \
        else P("pabrik.chemical_cost_per_kg_silica")
    drying_mj = ys.water_dried_kg * P("limbah.drying_mj_per_kg_water")
    return {
        # Panas tungku jalur abu menutup kebutuhan pengering lebih dulu (tidak boleh negatif)
        "pengeringan": max(0.0, drying_mj - ys.heat_recovered_mj) * P("pabrik.drying_cost_rp_per_mj"),
        "listrik_proses": P("pabrik.kwh_per_ton_input") / 1000 * tariff,
        "listrik_pellet": ys.outputs["bio_pellet"] / 1000 * P("limbah.pellet_kwh_per_ton") * tariff,
        "tenaga_kerja": P("pabrik.labor_hours_per_ton") / 1000 * P("pabrik.labor_rate_per_hour"),
        "bahan_kimia_silika": ys.outputs["bio_silika"] * chem,
        "kemasan": products_kg * P("pabrik.packaging_cost_per_kg"),
    }


def fixed_cost_per_month() -> dict[str, float]:
    dep_per_hour = (P("pabrik.machine_value") - P("pabrik.machine_salvage")) / P("pabrik.machine_life_hours")
    return {"depresiasi_mesin": dep_per_hour * P("pabrik.operating_hours_per_month"),
            "biaya_tetap_lain": P("pabrik.other_fixed_cost_per_month")}


class PricingRequest(BaseModel):
    moisture: float = Field(..., ge=0, le=60, description="% basis basah")
    ash: float = Field(18.0, ge=0, le=60, description="% basis kering")
    contamination: float = Field(0, ge=0, le=50)
    pyrolysis_temp_c: float | None = Field(None, ge=300, le=800)
    pellet_share: float | None = Field(None, ge=0, le=1)
    silica_share: float | None = Field(None, ge=0, le=1, description="Jalur biochar: porsi char diekstrak")
    silica_route: str | None = Field(None, pattern="^(biochar|abu_pembakaran|sekam_langsung)$")
    silica_husk_share: float | None = Field(None, ge=0, le=1, description="Jalur abu / sekam langsung")
    price_pellet_per_kg: float | None = Field(None, ge=0, le=100_000, description="Kosong = dari menu Parameter")
    price_biochar_per_kg: float | None = Field(None, ge=0, le=100_000)
    price_silica_per_kg: float | None = Field(None, ge=0, le=500_000)
    sensitivity: bool = True

    def price_overrides(self) -> dict:
        return {"bio_pellet": self.price_pellet_per_kg, "biochar": self.price_biochar_per_kg,
                "bio_silika": self.price_silica_per_kg}

    def route_kw(self) -> dict:
        return {"temp_c": self.pyrolysis_temp_c, "pellet_share": self.pellet_share, "silica_share": self.silica_share,
                "silica_route": self.silica_route, "silica_husk_share": self.silica_husk_share}


def _price_point(moisture, ash, contamination, pr: dict, **kw) -> dict:
    ys = process_yields(moisture, ash, **kw)
    clean = 1 - contamination / 100
    revenue = {p: ys.outputs[p] * pr[p] * clean for p in PRODUCTS}
    value = sum(revenue.values())
    var = variable_cost_per_kg(ys)
    var_total = sum(var.values()) * clean + var["listrik_proses"] * (1 - clean)   # kotoran tetap diproses
    fixed_kg = sum(fixed_cost_per_month().values()) / (P("pabrik.planned_input_ton_per_month") * 1000)
    floor = value - var_total
    ceiling = floor - fixed_kg
    target = ceiling - P("pabrik.target_margin_pct") / 100 * value
    return {"ys": ys, "revenue": revenue, "value": value, "var": var, "var_total": var_total,
            "fixed_kg": fixed_kg, "floor": floor, "ceiling": ceiling, "target": target}


def recommend_price(req: PricingRequest) -> dict:
    """Rekomendasi harga beli sekam (Rp/kg diterima) + rincian & sensitivitas kadar air."""
    if req.moisture >= P("harga_mutu.moisture_reject") or req.contamination >= P("harga_mutu.contamination_reject"):
        return {"accept": False, "reason": "Di atas batas tolak mutu (menu Parameter → Harga & Mutu).",
                "floor_per_kg": 0, "target_per_kg": 0, "ceiling_per_kg": 0}
    pr = prices(req.price_overrides())                       # PriceMissing bila harga belum diisi
    kw = req.route_kw()
    pt = _price_point(req.moisture, req.ash, req.contamination, pr, **kw)
    ys = pt["ys"]
    m_ref = P("pabrik.reference_moisture_pct")
    ref = _price_point(m_ref, req.ash, 0, pr, **kw)
    sens = []
    if req.sensitivity:
        for m in range(8, 22, 2):
            if m < P("harga_mutu.moisture_reject"):
                q = _price_point(m, req.ash, req.contamination, pr, **kw)
                sens.append({"moisture": m, "target_per_kg": round(q["target"], 1), "floor_per_kg": round(q["floor"], 1)})
    return {
        "accept": pt["target"] > 0,
        "floor_per_kg": round(pt["floor"], 1),
        "target_per_kg": round(max(pt["target"], 0), 1),
        "ceiling_per_kg": round(pt["ceiling"], 1),
        "value_per_kg": round(pt["value"], 1),
        "dry_matter_equivalent_per_kg": round(max(ref["target"], 0) * (1 - req.moisture / 100) / (1 - m_ref / 100), 1),
        "yields_kg_per_kg": {k: round(v, 4) for k, v in ys.outputs.items()},
        "losses_kg_per_kg": {k: round(v, 4) for k, v in ys.losses.items()},
        "mass_balance_closure": round(ys.closure, 6),
        "silica_route": ys.route, "heat_recovered_mj_per_kg": round(ys.heat_recovered_mj, 3),
        "prices_used": pr,
        "revenue_per_kg": {k: round(v, 1) for k, v in pt["revenue"].items()},
        "variable_cost_per_kg": {k: round(v, 1) for k, v in pt["var"].items()},
        "fixed_cost_per_kg": round(pt["fixed_kg"], 1),
        "sensitivity_moisture": sens,
        "computation_details": {
            "nilai": "Σ rendemen_produk × harga_jual × (1 − kontaminan)",
            "lantai": "nilai − biaya variabel (beli di bawah ini = rugi variabel)",
            "plafon": "lantai − biaya tetap/kg pada volume rencana (impas penuh, CVP)",
            "target": f"plafon − margin target {P('pabrik.target_margin_pct'):g}% × nilai",
            "setara_basis_kering": f"P_acuan × (1 − M)/(1 − {m_ref:g}%) — pembanding praktik pembelian bahan basah",
            "rendemen_biochar": "Engine ② (suhu, abu) — menu Parameter → Model Rendemen",
            "sumber_angka": "menu Parameter → Pabrik & Biaya Produksi",
        },
    }


def contract_moisture_adjustment(agreed_price: float, moisture_contract: float, moisture_actual: float) -> float:
    """Harga per kg aktual bila sekam lebih basah dari kontrak (basis bahan kering). Lebih kering: tanpa bonus."""
    if moisture_actual <= moisture_contract:
        return agreed_price
    return agreed_price * (1 - moisture_actual / 100) / (1 - moisture_contract / 100)


# ---------------------------------------------------------------- akuntansi biaya batch
def allocate_joint_cost(joint_cost: float, outputs_kg: dict[str, float], separable: dict[str, float],
                        method: str | None = None, pr: dict | None = None) -> dict[str, float]:
    """Alokasi biaya bersama ke produk. NRV: nilai jual − biaya terpisah; fisik: proporsional berat."""
    method = method or P("pabrik.joint_cost_method")
    pr = pr or prices()
    if method == "fisik":
        basis = {p: max(outputs_kg.get(p, 0.0), 0.0) for p in PRODUCTS}
    else:
        basis = {p: max(outputs_kg.get(p, 0.0) * pr[p] - separable.get(p, 0.0), 0.0) for p in PRODUCTS}
    total = sum(basis.values())
    if total <= 0:
        raise ZeroDivisionError("Tidak ada dasar alokasi (output 0 atau NRV ≤ 0).")
    return {p: joint_cost * basis[p] / total for p in PRODUCTS}


def batch_economics(input_kg: float, outputs_kg: dict[str, float], losses_kg: dict[str, float],
                    joint_costs: float, separable_costs: dict[str, float], hours: float | None = None,
                    price_overrides: dict | None = None) -> dict:
    """Mass balance + biaya produksi per ton per produk + volume impas."""
    pr = prices(price_overrides)
    if input_kg <= 0:
        raise ZeroDivisionError("Input batch harus > 0 kg.")
    accounted = sum(outputs_kg.values()) + sum(losses_kg.values())
    closure_err = (input_kg - accounted) / input_kg * 100
    tol = P("pabrik.closure_tolerance_pct")
    fixed_month = fixed_cost_per_month()
    hours = hours if hours is not None else input_kg / 1000 / P("pabrik.planned_input_ton_per_month") \
        * P("pabrik.operating_hours_per_month")
    fixed_batch = sum(fixed_month.values()) * hours / P("pabrik.operating_hours_per_month")
    joint_total = joint_costs + fixed_batch
    alloc = allocate_joint_cost(joint_total, outputs_kg, separable_costs, pr=pr)
    per_product = {}
    for p in PRODUCTS:
        kg = outputs_kg.get(p, 0.0)
        cost = alloc[p] + separable_costs.get(p, 0.0)
        per_product[p] = {
            "label": PRODUCT_LABEL[p], "kg": round(kg, 2), "allocated_joint_rp": round(alloc[p]),
            "separable_rp": round(separable_costs.get(p, 0.0)), "total_cost_rp": round(cost),
            "cost_per_ton_rp": round(cost / kg * 1000) if kg > 0 else None,
            "price_per_ton_rp": round(pr[p] * 1000), "revenue_rp": round(kg * pr[p]),
            "margin_per_ton_rp": round(pr[p] * 1000 - cost / kg * 1000) if kg > 0 else None,
        }
    revenue = sum(v["revenue_rp"] for v in per_product.values())
    total_cost = joint_total + sum(separable_costs.values())
    variable = joint_costs + sum(separable_costs.values())
    contribution_per_kg_input = (revenue - variable) / input_kg
    fixed_month_total = sum(fixed_month.values())
    return {
        "mass_balance": {"input_kg": round(input_kg, 2), "outputs_kg": {k: round(v, 2) for k, v in outputs_kg.items()},
                         "losses_kg": {k: round(v, 2) for k, v in losses_kg.items()},
                         "closure_error_pct": round(closure_err, 3), "tolerance_pct": tol,
                         "closure_ok": abs(closure_err) <= tol + 1e-9},
        "products": per_product,
        "totals": {"revenue_rp": round(revenue), "joint_cost_rp": round(joint_costs), "fixed_allocated_rp": round(fixed_batch),
                   "separable_cost_rp": round(sum(separable_costs.values())), "total_cost_rp": round(total_cost),
                   "profit_rp": round(revenue - total_cost),
                   "cost_per_ton_input_rp": round(total_cost / input_kg * 1000)},
        "prices_used": pr,
        "cvp": {"contribution_per_ton_input_rp": round(contribution_per_kg_input * 1000),
                "fixed_cost_per_month_rp": round(fixed_month_total),
                "break_even_ton_per_month": round(fixed_month_total / (contribution_per_kg_input * 1000), 1)
                if contribution_per_kg_input > 0 else None,
                "planned_ton_per_month": P("pabrik.planned_input_ton_per_month")},
        "computation_details": {
            "alokasi": f"biaya bersama + biaya tetap teralokasi dibagi metode '{P('pabrik.joint_cost_method')}' "
                       "(Horngren); biaya terpisah langsung ke produknya",
            "depresiasi": "(nilai − nilai sisa) / umur jam × jam batch (garis lurus)",
            "impas": "biaya tetap per bulan / kontribusi per ton input (Cost-Volume-Profit)",
            "penutupan": "(input − Σ output − Σ loss) / input",
        },
    }
