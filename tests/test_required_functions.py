"""Uji penerimaan 3 fungsi wajib (kriteria hackathon), lewat HTTP seperti dipakai pengguna:

1. Menerima parameter feedstock biomassa → analisis/perbandingan + rekomendasi awal pemilihan/blending.
2. Menerima karakteristik/volume limbah → rekomendasi teknologi konversi + estimasi potensi energi.
3. Menerima data historis konsumsi energi → IKE, deteksi anomali/pemborosan, rekomendasi efisiensi.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import demo_headers


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

FEEDSTOCKS = [
    {"id": "sekam", "name": "Sekam padi", "moisture": 11, "ash": 18, "volatile_matter": 64, "fixed_carbon": 18,
     "cost_per_ton": 400_000, "stock_ton": 120},
    {"id": "tongkol", "name": "Tongkol jagung", "moisture": 12, "ash": 2, "volatile_matter": 80, "fixed_carbon": 18,
     "cost_per_ton": 650_000, "stock_ton": 40},
    {"id": "tempurung", "name": "Tempurung kelapa", "moisture": 10, "ash": 1, "volatile_matter": 75,
     "fixed_carbon": 24, "cost_per_ton": 2_000_000, "stock_ton": 15},
]


def test_fungsi_1_perbandingan_feedstock_dan_rekomendasi_blending(client):
    h = demo_headers(client, "pabrik")
    r = client.post("/api/v1/labs/feedstock/compare", headers=h, json={"feedstocks": FEEDSTOCKS, "purpose": "biochar"})
    assert r.status_code == 200, r.text
    body = r.json()
    ranks = [x["rank"] for x in body["ranking"]]
    assert sorted(ranks) == [1, 2, 3] and body["recommendation"]
    # Rekomendasi awal BLENDING: LP biaya minimum dengan kendala mutu produk
    defaults = client.get("/api/v1/labs/blend/defaults", headers=h).json()
    spec = defaults["products"]["biochar_tanah"]["spec"]
    blend = client.post("/api/v1/labs/blend/recommend", headers=h,
                        json={"feedstocks": defaults["feedstocks"], "spec": spec, "target_ton": 50})
    assert blend.status_code == 200, blend.text
    mix = blend.json()
    assert mix and str(mix).count("ton") > 0


def test_fungsi_2_rekomendasi_teknologi_limbah_dan_potensi_energi(client):
    h = demo_headers(client, "pabrik")
    for stream, expect_thermo in (({"name": "Sekam", "preset": "sekam_padi", "ton_per_day": 20}, True),
                                  ({"name": "Kotoran sapi", "preset": "kotoran_sapi", "ton_per_day": 15}, False)):
        r = client.post("/api/v1/labs/waste-energy/advise", headers=h, json=stream)
        assert r.status_code == 200, r.text
        b = r.json()
        ep = b["energy_potential"]
        assert ep["energi_primer_gj_per_tahun"] > 0 or (ep["listrik_teknologi_terbaik_mwh_per_tahun"] or 0) > 0
        assert b["technologies"] and b["recommendation"]
        top = b["technologies"][0]["technology"].lower()
        thermo = any(k in top for k in ("pirolisis", "pembakaran", "gasifikasi", "boiler", "pellet"))
        assert thermo == expect_thermo, top                       # kering → termokimia; basah → biokimia


def test_fungsi_3_ike_anomali_dan_rekomendasi_efisiensi(client):
    h = demo_headers(client, "pabrik")
    readings = [{"period": f"2025-{m:02d}", "kwh": 40_000 + m * 500 + (9_000 if m == 7 else 0),
                 "production_ton": 200 + m * 3, "building_kwh": 3_000} for m in range(1, 13)]
    readings += [{"period": f"2026-{m:02d}", "kwh": 42_000 + m * 500 + (12_000 if m == 5 else 0),
                  "production_ton": 210 + m * 3, "building_kwh": 3_100} for m in range(1, 10)]
    r = client.post("/api/v1/labs/energy/analyze", headers=h,
                    json={"facility": "Pabrik uji", "floor_area_m2": 1_200, "readings": readings})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["summary"]["ike_kwh_m2_year"] > 0 and b["summary"]["ike_category"]
    assert {a["period"] for a in b["anomalies"]} >= {"2025-07", "2026-05"}     # pemborosan yang disuntikkan
    assert b["recommendations"] and b["recommendations"][0]["title"]
