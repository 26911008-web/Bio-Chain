"""018 multi-biomassa: master + refraksi, transaksi multi-komoditas, gudang (FOR UPDATE, idempoten), ledger abu."""
import ast
import asyncio
import re
import uuid
from pathlib import Path

import httpx
import pytest
from sqlalchemy.exc import IntegrityError

from app.biomass_seed import BIOMASS_SEED
from app.engines.refraction import refract
from app.main import app
from app.models.biomass import IndustrialAshLedger
from tests.test_field_ops import PROX, env  # noqa: F401  (fixture)


def test_python_and_sql_seed_match():
    sql = Path("migrations/018_multi_biomass_ash.sql").read_text(encoding="utf-8")
    m = re.search(r"INSERT INTO biomass_parameters \((.*?)\) VALUES\n(.*?)\nON CONFLICT", sql, re.S)
    cols = [c.strip() for c in m.group(1).split(",")]
    rows = [dict(zip(cols, ast.literal_eval(line.strip().rstrip(",").replace("''", "\\'"))))
            for line in m.group(2).strip().split("\n")]
    assert rows == BIOMASS_SEED


def test_refraction_formula_and_field_options():
    r = refract(1000, 18, 5, moisture_ref_pct=12, moisture_reject_pct=20, contaminant_tol_pct=2)
    # 1000 × (1 − 0,03) × 0,82/0,88 = 903,86
    assert r["accepted"] and abs(r["payable_kg"] - 903.86) < 0.01 and abs(r["refraction_kg"] - 96.14) < 0.01
    dry = refract(1000, 8, 0, 12, 20, 2)
    assert dry["payable_kg"] == 1000                                             # tanpa bonus kering
    assert refract(1000, 8, 0, 12, 20, 2, dry_bonus=True)["payable_kg"] > 1000
    wet = refract(1000, 25, 0, 12, 20, 2)
    assert not wet["accepted"] and "terima basah" in wet["reason"]
    ok = refract(1000, 25, 0, 12, 20, 2, accept_wet=True)
    assert ok["accepted"] and ok["basis"]["accepted_wet"] and ok["payable_kg"] < 1000


def test_master_is_seeded_and_editable_by_factory_only(env):
    rows = env.ok("petani", "GET", "/biomass")
    codes = {r["code"] for r in rows}
    assert {"sekam_padi", "tongkol_jagung", "ampas_tebu", "tempurung_kelapa", "sabut_kelapa"} <= codes
    corn = next(r for r in rows if r["code"] == "tongkol_jagung")
    assert corn["base_price_per_kg"] is None and corn["lhv_db_mj_kg"] == 17.0 and "Phyllis2" in corn["source"]
    body = {"changes": {"base_price_per_kg": 650, "k2o_pct_ash": 30}, "source": "Lab BRMP LT-12/2026"}
    assert env.call("pengepul", "PUT", "/biomass/tongkol_jagung", body).status_code == 403
    assert env.call("pabrik", "PUT", "/biomass/tongkol_jagung", {**body, "changes": {"code": "x"}}).status_code == 422
    upd = env.ok("pabrik", "PUT", "/biomass/tongkol_jagung", body)
    assert upd["base_price_per_kg"] == 650 and "LT-12/2026" in upd["source"]


def test_multi_commodity_report_verify_and_auction(env):
    h = env.ok("petani", "POST", "/farmer/harvest",
               {"quantity_kg": 800, "mill_id": env.mill["M01"], "commodity": "tongkol_jagung"}, status=201)
    assert h["commodity"] == "tongkol_jagung"
    assert env.call("petani", "POST", "/farmer/harvest", {"quantity_kg": 1, "commodity": "plastik"}).status_code == 422
    v = env.call("pengepul", "POST", "/collector/verify", {"harvest_id": h["id"], "weighed_kg": 800, "moisture": 18,
                                                            "contamination": 1})
    assert v.status_code == 422 and "Harga dasar" in v.json()["detail"]                  # harga wajib input pabrik
    env.ok("pabrik", "PUT", "/biomass/tongkol_jagung", {"changes": {"base_price_per_kg": 650}, "source": "harga pasar Okt"})
    v = env.ok("pengepul", "POST", "/collector/verify", {"harvest_id": h["id"], "weighed_kg": 800, "moisture": 18,
                                                          "contamination": 1})
    assert v["commodity"] == "tongkol_jagung" and v["grade"] == "B"
    # basis kering terhadap MC acuan 15 %: 800 × 0,82/0,85 × 650 (kotoran dalam toleransi)
    assert abs(v["total_price"] - 800 * (0.82 / 0.85) * 650) < 2           # kotoran 1 % ≤ toleransi 2 %: tidak dipotong
    # sekam tetap lewat jalur lama (kurva mutu Engine ②)
    s = env.ok("petani", "POST", "/farmer/harvest", {"quantity_kg": 500, "mill_id": env.mill["M02"]}, status=201)
    assert s["commodity"] == "sekam_padi"
    assert env.ok("pengepul", "POST", "/collector/verify", {"harvest_id": s["id"], "weighed_kg": 500, **PROX})["commodity"] == "sekam_padi"
    # lelang: listing jagung → harvest mewarisi komoditas
    lst = env.ok("petani", "POST", "/farmer/listings", {"quantity_kg": 600, "commodity": "tongkol_jagung",
                                                         "allow_jemput": True, "ask_price_jemput": 700}, status=201)
    assert lst["commodity"] == "tongkol_jagung"


def _wh(env, name="Gudang Utama"):
    return env.ok("pengepul", "POST", "/collector/warehouses", {"name": name, "lat": -7.7, "lon": 110.3}, status=201)


def test_warehouse_ledger_refraction_idempotent_and_no_overdraft(env):
    w = _wh(env)
    assert env.call("pengepul", "POST", "/collector/warehouses", {"name": "Gudang Utama"}).status_code == 409
    cid = uuid.uuid4().hex
    body = {"commodity": "sekam_padi", "movement": "masuk", "kg": 1000, "moisture_pct": 18, "contaminant_pct": 5,
            "client_event_id": cid}
    m = env.ok("pengepul", "POST", f"/collector/warehouses/{w['id']}/movements", body, status=201)
    assert abs(m["payable_kg"] - 903.86) < 0.01 and m["refraction_basis"]["moisture_ref_pct"] == 12
    assert env.ok("pengepul", "POST", f"/collector/warehouses/{w['id']}/movements", body, status=201)["replayed"]
    env.ok("pengepul", "POST", f"/collector/warehouses/{w['id']}/movements",
           {"commodity": "tongkol_jagung", "movement": "masuk", "kg": 400, "moisture_pct": 14}, status=201)
    over = env.call("pengepul", "POST", f"/collector/warehouses/{w['id']}/movements",
                    {"commodity": "sekam_padi", "movement": "keluar", "kg": 1200})
    assert over.status_code == 409 and "Stok" in over.json()["detail"]
    out = env.ok("pengepul", "POST", f"/collector/warehouses/{w['id']}/movements",
                 {"commodity": "sekam_padi", "movement": "keluar", "kg": 500, "delivery_ref": "DR-1"}, status=201)
    assert abs(out["payable_kg"] + 451.93) < 0.01                                   # proporsional saldo berefraksi
    stock = {s["commodity"]: s for s in env.ok("pengepul", "GET", "/collector/warehouses")[0]["stock"]}
    assert stock["sekam_padi"]["gross_kg"] == 500 and stock["tongkol_jagung"]["gross_kg"] == 400
    assert env.call("pengepul2", "GET", f"/collector/warehouses/{w['id']}/movements").status_code == 404
    wet = env.call("pengepul", "POST", f"/collector/warehouses/{w['id']}/movements",
                   {"commodity": "sekam_padi", "movement": "masuk", "kg": 300, "moisture_pct": 30})
    assert wet.status_code == 422
    env.ok("pengepul", "POST", f"/collector/warehouses/{w['id']}/movements",
           {"commodity": "sekam_padi", "movement": "masuk", "kg": 300, "moisture_pct": 30, "accept_wet": True}, status=201)


def test_parallel_outflows_never_overdraw(env):
    """Dua HP mengirim antrean 'keluar' bersamaan: kunci FOR UPDATE per gudang → total keluar ≤ stok."""
    w = _wh(env, "Gudang Paralel")
    env.ok("pengepul", "POST", f"/collector/warehouses/{w['id']}/movements",
           {"commodity": "tongkol_jagung", "movement": "masuk", "kg": 1000, "moisture_pct": 15}, status=201)

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await asyncio.gather(*[c.post(f"/api/v1/collector/warehouses/{w['id']}/movements",
                                                 headers=env.headers["pengepul"],
                                                 json={"commodity": "tongkol_jagung", "movement": "keluar", "kg": 300})
                                          for _ in range(5)])
    codes = sorted(r.status_code for r in asyncio.run(go()))
    assert codes.count(201) == 3 and all(c in (201, 409) for c in codes)
    stock = env.ok("pengepul", "GET", "/collector/warehouses")[0]["stock"][0]
    assert stock["gross_kg"] == 100


def test_ash_ledger_only_passing_ash_reaches_farmer_group(env):
    g = env.ok("pabrik", "POST", "/factory/farmer-groups", {"name": "Poktan Sri Rejeki", "kecamatan": "Seyegan",
                                                             "kabupaten": "Sleman", "leader_name": "Pak Darmo",
                                                             "leader_user_id": env.uid["petani"]}, status=201)
    bad = env.ok("pabrik", "POST", "/factory/ash", {"ash_type": "fly_ash", "source_commodity": "sekam_padi",
                                                    "quantity_kg": 800}, status=201)
    assert bad["code"].startswith("ASH-") and bad["heavy_metal_status"] == "belum_uji"
    assert env.call("pabrik", "POST", f"/factory/ash/{bad['id']}/allocate", {"farmer_group_id": g["id"]}).status_code == 409
    r = env.ok("pabrik", "POST", f"/factory/ash/{bad['id']}/lab", {"pb_ppm": 72, "cd_ppm": 1, "as_ppm": 3,
                                                                    "lab_report_no": "LAB-9"})
    assert r["heavy_metal_status"] == "gagal" and "Pb 72" in r["limits_snapshot"]["notes"][0]
    assert env.call("pabrik", "POST", f"/factory/ash/{bad['id']}/allocate", {"farmer_group_id": g["id"]}).status_code == 409
    assert env.ok("pabrik", "POST", f"/factory/ash/{bad['id']}/dispose",
                  {"note": "Dikirim ke pengolah limbah berizin PT X"})["status"] == "dibuang"

    good = env.ok("pabrik", "POST", "/factory/ash", {"ash_type": "silica_ash", "quantity_kg": 500}, status=201)
    lab = {"pb_ppm": 12, "cd_ppm": 0.4, "as_ppm": 2.1, "hg_ppm": 0.1, "lab_report_no": "LAB-10", "k2o_pct": 2.5}
    nolab = env.call("pabrik", "POST", f"/factory/ash/{good['id']}/lab", {**lab, "lab_report_no": None})
    assert nolab.status_code == 422 and "Nomor laporan" in nolab.json()["detail"]
    r = env.ok("pabrik", "POST", f"/factory/ash/{good['id']}/lab", lab)
    assert r["heavy_metal_status"] == "lulus" and r["limits_snapshot"]["limits_mg_kg"]["pb"] == 50
    env.ok("pabrik", "POST", f"/factory/ash/{good['id']}/allocate", {"farmer_group_id": g["id"], "land_area_ha": 2})
    assert env.call("pabrik", "POST", f"/factory/ash/{good['id']}/handover", {"lat": -7.7, "lon": 110.3}).status_code == 422
    h = env.ok("pabrik", "POST", f"/factory/ash/{good['id']}/handover",
               {"photo_url": "/uploads/abu-serah.jpg", "lat": -7.71, "lon": 110.31})
    assert h["status"] == "diserahkan" and h["farmer_group"] == "Poktan Sri Rejeki"
    mine = env.ok("petani", "GET", "/farmer/ash")
    assert [a["code"] for a in mine] == [good["code"]]                              # ketua Poktan hanya kelompoknya
    assert env.ok("petani2", "GET", "/farmer/ash") == []
    assert len(env.ok("auditor", "GET", "/factory/ash")) == 2
    assert env.call("auditor", "POST", "/factory/ash", {"ash_type": "fly_ash", "quantity_kg": 1}).status_code == 403


def test_db_check_blocks_unsafe_ash_even_if_app_is_bypassed(env):
    async def go(s):
        s.add(IndustrialAshLedger(code="ASH-RAW-1", factory_id=env.uid["pabrik"], created_by_id=env.uid["pabrik"],
                                  ash_type="bottom_ash", quantity_kg=10, status="dialokasikan", farmer_group_id=None,
                                  heavy_metal_status="belum_uji"))
        await s.commit()
    with pytest.raises(IntegrityError):
        env.q(go)


def test_master_update_is_typed_no_mass_assignment(env):
    """Keamanan: perubahan master bertipe — string HTML ke kolom angka / kolom asing / nama berskrip ditolak."""
    for changes in ({"base_price_per_kg": '"><img src=x onerror=alert(1)>'}, {"source": "x"}, {"code": "baru"},
                    {"name": "<script>alert(1)</script>"}, {"lhv_db_mj_kg": None}, {}):
        r = env.call("pabrik", "PUT", "/biomass/sekam_padi", {"changes": changes, "source": "uji keamanan"})
        assert r.status_code == 422, (changes, r.text)
    ok = env.ok("pabrik", "PUT", "/biomass/sekam_padi", {"changes": {"base_price_per_kg": 470, "name": "Sekam padi IR64"},
                                                          "source": "uji keamanan"})
    assert ok["base_price_per_kg"] == 470 and ok["name"] == "Sekam padi IR64"


def test_dynamic_biomass_creation_and_trade(env):
    """Pengguna dapat mendaftarkan jenis biomassa apa pun secara dinamis dan langsung bertransaksi."""
    # 1. Daftarkan komoditas baru (misal Kulit Kopi)
    coffee = env.ok("petani", "POST", "/biomass", {
        "name": "Kulit Kopi Robusta",
        "base_price_per_kg": 850,
        "moisture_ref_pct": 14.0,
        "moisture_reject_pct": 22.0
    }, status=201)
    assert coffee["code"] == "kulit_kopi_robusta"
    assert coffee["name"] == "Kulit Kopi Robusta"
    assert coffee["base_price_per_kg"] == 850

    # 2. Muncul di daftar biomassa
    all_b = env.ok("petani", "GET", "/biomass")
    assert any(b["code"] == "kulit_kopi_robusta" for b in all_b)

    # 3. Petani lapor panen menggunakan komoditas baru ini
    h = env.ok("petani", "POST", "/farmer/harvest", {
        "quantity_kg": 750,
        "mill_id": env.mill["M01"],
        "commodity": "kulit_kopi_robusta"
    }, status=201)
    assert h["commodity"] == "kulit_kopi_robusta"

    # 4. Pengepul verifikasi mutu komoditas baru ini
    v = env.ok("pengepul", "POST", "/collector/verify", {
        "harvest_id": h["id"],
        "weighed_kg": 750,
        "moisture": 14.0,
        "contamination": 1.0
    })
    assert v["commodity"] == "kulit_kopi_robusta"
    assert v["total_price"] > 0

