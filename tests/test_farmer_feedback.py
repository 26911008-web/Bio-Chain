"""Modul petani & pengepul (Okt 2026): taksiran opsional, menu pembayaran, umpan balik mutu + defect rate,
pengambilan biochar untuk sawah (+ rumus ekonomi sirkular), margin pengepul dalam persen, data proxy setara."""

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import demo_headers


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _report(client, hdr, kg=900, **kw):
    r = client.post("/api/v1/farmer/harvest", headers=hdr, json={"quantity_kg": kg, **kw})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _credit_wallet(farmer_id: int, kg: float):
    from app.database import db_manager
    from app.models.ledger import BiocharLedgerEntry

    from app.security.rls import SYSTEM_IDENTITY, bind_identity

    async def go():
        async with db_manager.async_session() as s:
            bind_identity(s, *SYSTEM_IDENTITY)            # penyesuaian saldo = tugas sistem (RLS: petani tak bisa kredit sendiri)
            s.add(BiocharLedgerEntry(farmer_id=farmer_id, entry_type="adjustment", amount_kg=kg,
                                     note="tes", created_by_id=farmer_id))
            await s.commit()
    asyncio.run(go())


def test_farmer_estimates_are_optional_and_validated(client):
    hp = demo_headers(client, "petani")
    _report(client, hp)                                           # tanpa taksiran tetap boleh
    _report(client, hp, moisture_est=13.5, grade_est="B")
    assert client.post("/api/v1/farmer/harvest", headers=hp,
                       json={"quantity_kg": 100, "grade_est": "Z"}).status_code == 422
    assert client.post("/api/v1/farmer/harvest", headers=hp,
                       json={"quantity_kg": 100, "moisture_est": 75}).status_code == 422


def test_payment_overview_buckets(client):
    hp, hc = demo_headers(client, "petani"), demo_headers(client, "pengepul")
    hid = _report(client, hp, 800)
    v = client.post("/api/v1/collector/verify", headers=hc,
                    json={"harvest_id": hid, "weighed_kg": 780, "moisture": 11.0})
    assert v.status_code == 200, v.text
    o = client.get("/api/v1/farmer/payments/overview", headers=hp).json()
    assert any(w["harvest_id"] == hid and w["net_rp"] > 0 for w in o["waiting"]["items"])
    assert o["unweighed"]["count"] >= 1 and o["due_days"] >= 0
    pay = client.post(f"/api/v1/collector/harvests/{hid}/pay-farmer", headers=hc, json={"method": "tunai"})
    assert pay.status_code == 201, pay.text
    o2 = client.get("/api/v1/farmer/payments/overview", headers=hp).json()
    assert not any(w["harvest_id"] == hid for w in o2["waiting"]["items"])
    assert o2["paid"]["count"] == o["paid"]["count"] + 1


def test_reject_category_feeds_defect_rate(client):
    hp, hc = demo_headers(client, "petani"), demo_headers(client, "pengepul")
    hid = _report(client, hp, 500, moisture_est=12)
    r = client.post("/api/v1/collector/reject", headers=hc,
                    json={"harvest_id": hid, "reason": "sekam basah sekali", "category": "basah"})
    assert r.status_code == 200, r.text
    assert client.post("/api/v1/collector/reject", headers=hc,
                       json={"harvest_id": hid, "reason": "x yz", "category": "ngawur"}).status_code == 422
    fb = client.get("/api/v1/farmer/quality-feedback?months=3", headers=hp).json()
    assert len(fb["series"]) == 3
    cur = fb["series"][-1]
    assert cur["defect_lots"] >= 1 and cur["defect_rate_pct"] > 0
    basah = next(c for c in fb["causes"] if c["cause"] == "basah")
    assert basah["lots"] >= 1 and basah["tip"]
    # pengepul/supir tidak boleh membaca umpan balik petani
    assert client.get("/api/v1/farmer/quality-feedback", headers=hc).status_code == 403


def test_biochar_estimate_formula_monotonic_and_capped(client):
    hp = demo_headers(client, "petani")
    lo = client.get("/api/v1/farmer/biochar/estimate?kg=500&land_area_ha=0.5", headers=hp).json()
    hi = client.get("/api/v1/farmer/biochar/estimate?kg=5000&land_area_ha=0.5", headers=hp).json()
    assert lo["rate_t_ha"] == 1.0 and hi["rate_t_ha"] == 10.0
    assert 0 < lo["yield_gain_pct"] < hi["yield_gain_pct"]
    # jenuh: 10× dosis tidak memberi 10× kenaikan hasil
    assert hi["yield_gain_pct"] < 10 * lo["yield_gain_pct"]
    assert lo["carbon_stored_tco2e"] > 0 and "hitung ganda" in lo["carbon_note"]
    assert client.get("/api/v1/farmer/biochar/estimate?kg=0&land_area_ha=1", headers=hp).status_code == 422


def test_biochar_redemption_holds_balance_and_handover_once(client):
    hp, hf = demo_headers(client, "petani"), demo_headers(client, "pabrik")
    fid = client.get("/api/v1/farmer/wallet", headers=hp).json()["farmer_id"]
    _credit_wallet(fid, 300)
    w = client.get("/api/v1/farmer/wallet", headers=hp).json()
    avail = w["available_kg"]
    assert avail >= 300
    assert client.post("/api/v1/farmer/biochar/redeem", headers=hp,
                       json={"kg": avail + 1, "land_area_ha": 0.5}).status_code == 409
    r = client.post("/api/v1/farmer/biochar/redeem", headers=hp, json={"kg": 200, "land_area_ha": 0.25})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    assert r.json()["estimate"]["rate_t_ha"] == 0.8
    w2 = client.get("/api/v1/farmer/wallet", headers=hp).json()
    assert w2["held_kg"] >= 200 and w2["balance_kg"] == w["balance_kg"]          # ditahan, ledger belum berubah
    # petani tidak bisa menyerahkan sendiri
    assert client.post(f"/api/v1/factory/biochar-redemptions/{rid}/handover", headers=hp, json={}).status_code == 403
    assert any(x["id"] == rid for x in client.get("/api/v1/factory/biochar-redemptions", headers=hf).json())
    h = client.post(f"/api/v1/factory/biochar-redemptions/{rid}/handover", headers=hf, json={"kg": 180})
    assert h.status_code == 200, h.text
    assert h.json()["status"] == "diserahkan" and h.json()["kg"] == 180
    assert client.post(f"/api/v1/factory/biochar-redemptions/{rid}/handover", headers=hf, json={}).status_code == 409
    w3 = client.get("/api/v1/farmer/wallet", headers=hp).json()
    assert round(w3["balance_kg"], 2) == round(w["balance_kg"] - 180, 2)
    assert any(e["type"] == "redemption" and e["amount_kg"] == -180 for e in w3["entries"])
    # batal: hanya yang masih diajukan
    r2 = client.post("/api/v1/farmer/biochar/redeem", headers=hp, json={"kg": 10, "pickup_point": "pengepul"}).json()
    assert client.post(f"/api/v1/farmer/biochar/redemptions/{r2['id']}/cancel", headers=hp).json()["status"] == "dibatalkan"
    assert client.post(f"/api/v1/farmer/biochar/redemptions/{rid}/cancel", headers=hp).status_code == 409


def test_bid_advisor_accepts_margin_percent(client):
    hp, hc = demo_headers(client, "petani"), demo_headers(client, "pengepul")
    lst = client.post("/api/v1/farmer/listings", headers=hp,
                      json={"quantity_kg": 1500, "allow_jemput": False, "allow_antar": True, "ask_price_antar": 400}).json()
    lid = lst.get("id") or lst.get("listing_id")
    base = {"listing_id": lid, "scheme": "antar", "resale_price_per_kg": 600}
    a = client.post("/api/v1/collector/bid-advisor", headers=hc, json={**base, "margin_pct": 10}).json()
    assert a["margin_per_kg"] == 60 and a["max_bid_per_kg"] == 540 and a["margin_pct"] == 10
    b = client.post("/api/v1/collector/bid-advisor", headers=hc, json={**base, "margin_pct": 5}).json()
    assert b["max_bid_per_kg"] == 570
    assert client.post("/api/v1/collector/bid-advisor", headers=hc, json={**base, "margin_pct": -1}).status_code == 422


def test_proxy_farmer_and_harvest_capture_same_fields_as_farmer(client):
    hc = demo_headers(client, "pengepul")
    f = client.post("/api/v1/collector/proxy-farmers", headers=hc,
                    json={"full_name": f"Mbah {uuid.uuid4().hex[:5]}", "kecamatan": "Moyudan", "kabupaten": "Sleman",
                          "lat": -7.77, "lon": 110.24, "consent_given": True})
    assert f.status_code == 201, f.text
    mills = client.get("/api/v1/farmer/mills", headers=hc).json()          # pengepul boleh (lapor proxy)
    r = client.post("/api/v1/collector/proxy-harvest", headers=hc,
                    json={"farmer_id": f.json()["id"], "quantity_kg": 400, "mill_id": mills[0]["id"],
                          "moisture_est": 14, "grade_est": "B"})
    assert r.status_code == 201, r.text
    assert client.post("/api/v1/collector/proxy-harvest", headers=hc,
                       json={"farmer_id": f.json()["id"], "quantity_kg": 400, "grade_est": "X"}).status_code == 422


# ------------------------------------------------------------------ Pabrik: laporan ESG & register penghematan
def test_esg_report_structure_and_rbac(client):
    hf = demo_headers(client, "pabrik")
    r = client.get("/api/v1/factory/esg/report", headers=hf)
    assert r.status_code == 200, r.text
    d = r.json()
    codes = {k["code"] for pillar in ("environment", "social", "governance") for k in d[pillar]}
    assert {"E7", "E10", "E12", "S3", "S5", "G1", "G4"} <= codes
    for pillar in ("environment", "social", "governance"):
        assert all(k["standard"] and k["formula"] is not None for k in d[pillar])
    # emisi dihindari dilaporkan terpisah, tidak mengurangi emisi bruto
    cp = d["carbon_presentation"]
    assert {"gross_emissions_tco2e", "removals_durable_tco2e", "avoided_tco2e"} <= set(cp) and "terpisah" in cp["rule"]
    assert client.get("/api/v1/factory/esg/report", headers=demo_headers(client, "auditor")).status_code == 200
    for role in ("petani", "driver", "pengepul"):
        assert client.get("/api/v1/factory/esg/report", headers=demo_headers(client, role)).status_code == 403
    csv = client.get("/api/v1/factory/esg/report.csv?from=2026-01&to=2026-10", headers=hf)
    assert csv.status_code == 200 and "Pilar;Kode;KPI" in csv.text
    assert client.get("/api/v1/factory/esg/report?from=2026-13", headers=hf).status_code == 422


def test_efficiency_overview_and_action_register_four_eyes(client):
    hf, ha = demo_headers(client, "pabrik"), demo_headers(client, "admin")
    o = client.get("/api/v1/factory/efficiency", headers=hf).json()
    assert {x["code"] for x in o["realized"]} == {"R1", "R2", "R3"}
    assert any(p["code"] == "P4" and p["recommendation"] for p in o["potential"])
    body = {"process": "energi", "title": "Pengering pakai syngas", "metric": "kWh/t", "baseline_value": 180,
            "current_value": 150, "saving_rp": 1_300_000, "saving_co2e_kg": 780, "period": "2026-10", "status": "berjalan"}
    assert client.post("/api/v1/factory/efficiency/actions", headers=hf, json={**body, "process": "ngawur"}).status_code == 422
    a = client.post("/api/v1/factory/efficiency/actions", headers=hf, json=body)
    assert a.status_code == 201, a.text
    aid = a.json()["id"]
    # verifikasi: wajib bukti, dan bukan oleh pembuatnya sendiri
    assert client.patch(f"/api/v1/factory/efficiency/actions/{aid}", headers=ha, json={"status": "terverifikasi"}).status_code == 422
    assert client.patch(f"/api/v1/factory/efficiency/actions/{aid}", headers=hf,
                        json={"status": "terverifikasi", "evidence": "/uploads/meter.jpg"}).status_code == 403
    v = client.patch(f"/api/v1/factory/efficiency/actions/{aid}", headers=ha,
                     json={"status": "terverifikasi", "evidence": "/uploads/meter.jpg"})
    assert v.status_code == 200 and v.json()["status"] == "terverifikasi"
    o2 = client.get("/api/v1/factory/efficiency", headers=hf).json()
    assert o2["recorded_totals"]["saving_rp"] >= 1_300_000 and o2["recorded_totals"]["verified"] >= 1
    assert client.post("/api/v1/factory/efficiency/actions", headers=demo_headers(client, "petani"), json=body).status_code == 403


def test_carbon_claim_submit_and_reject_through_rls(client):
    """F11 lewat identitas aplikasi (PG: RLS aktif): pabrik mengajukan, auditor menolak → kunci serah-terima dilepas.
    Ditolak di akhir agar tes bisa diulang (periode klaim aktif tidak boleh tumpang-tindih)."""
    from datetime import datetime, timezone

    from app.database import db_manager
    from app.models.factory_ops import BatchOutput, ManufacturingBatch
    from app.security.rls import SYSTEM_IDENTITY, bind_identity

    hp, hf, ha = demo_headers(client, "petani"), demo_headers(client, "pabrik"), demo_headers(client, "auditor")
    pid = client.get("/api/v1/auth/me", headers=hf).json()["user_id"]

    async def produce():
        async with db_manager.async_session() as s:
            bind_identity(s, *SYSTEM_IDENTITY)
            b = ManufacturingBatch(batch_code=f"T-CLM-{uuid.uuid4().hex[:8]}", pyrolysis_temp_c=550, pellet_share=0.3,
                                   silica_share_of_biochar=0, input_kg=9000, closure_error_pct=0.5, closure_ok=1,
                                   economics={}, operator_id=pid)
            s.add(b)
            await s.flush()
            s.add(BatchOutput(batch_id=b.id, product="biochar", quantity_kg=3000))
            await s.commit()
    asyncio.run(produce())
    fid = client.get("/api/v1/farmer/wallet", headers=hp).json()["farmer_id"]
    _credit_wallet(fid, 400)
    rid = client.post("/api/v1/farmer/biochar/redeem", headers=hp, json={"kg": 400, "land_area_ha": 0.5}).json()["id"]
    assert client.post(f"/api/v1/factory/biochar-redemptions/{rid}/handover", headers=hf, json={}).status_code == 200
    month = f"{datetime.now(timezone.utc):%Y-%m}"
    body = {"from": month, "to": month, "lab_c_org_pct": 45, "lab_h_corg_ratio": 0.3, "lab_name": "Lab Uji",
            "lab_report_no": "T-1", "lab_report_url": "/uploads/t.jpg"}
    r = client.post("/api/v1/factory/carbon-claims", headers=hf, json=body)
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["integrity"]["ok"] and c["end_use_kg"] >= 400
    assert any(x["id"] == c["id"] for x in client.get("/api/v1/auditor/carbon-claims", headers=ha).json())
    d = client.post(f"/api/v1/auditor/carbon-claims/{c['id']}/decision", headers=ha,
                    json={"decision": "ditolak", "note": "Tes otomatis: tolak agar kunci dilepas."})
    assert d.status_code == 200, d.text
    p = client.post("/api/v1/factory/carbon-claims/preview", headers=hf, json=body).json()
    assert p["end_use_kg"] >= 400                                         # serah-terima kembali tersedia


def test_multibiomass_warehouse_and_ash_through_rls(client):
    """018 lewat identitas aplikasi (PG: RLS aktif): stok gudang pengepul & abu lulus uji → Poktan."""
    hc, hf, hp = demo_headers(client, "pengepul"), demo_headers(client, "pabrik"), demo_headers(client, "petani")
    w = client.post("/api/v1/collector/warehouses", headers=hc, json={"name": f"Gudang {uuid.uuid4().hex[:6]}"})
    assert w.status_code == 201, w.text
    m = client.post(f"/api/v1/collector/warehouses/{w.json()['id']}/movements", headers=hc,
                    json={"commodity": "tongkol_jagung", "movement": "masuk", "kg": 500, "moisture_pct": 20,
                          "client_event_id": uuid.uuid4().hex})
    assert m.status_code == 201, m.text
    assert m.json()["payable_kg"] < 500
    pid = client.get("/api/v1/auth/me", headers=hp).json()["user_id"]
    g = client.post("/api/v1/factory/farmer-groups", headers=hf,
                    json={"name": f"Poktan {uuid.uuid4().hex[:6]}", "kecamatan": "Sleman", "kabupaten": "Sleman",
                          "leader_name": "Ketua", "leader_user_id": pid})
    assert g.status_code == 201, g.text
    a = client.post("/api/v1/factory/ash", headers=hf, json={"ash_type": "bottom_ash", "quantity_kg": 100}).json()
    lab = client.post(f"/api/v1/factory/ash/{a['id']}/lab", headers=hf,
                      json={"pb_ppm": 5, "cd_ppm": 0.2, "as_ppm": 1, "lab_report_no": "T-ASH"})
    assert lab.json()["heavy_metal_status"] == "lulus", lab.text
    assert client.post(f"/api/v1/factory/ash/{a['id']}/allocate", headers=hf,
                       json={"farmer_group_id": g.json()["id"]}).status_code == 200
    assert any(x["id"] == a["id"] for x in client.get("/api/v1/farmer/ash", headers=hp).json())
