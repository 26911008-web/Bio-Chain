"""F11 — klaim removal karbon: lab wajib, kunci serah-terima (tanpa hitung ganda), empat mata, snapshot SHA-256."""
from datetime import datetime, timezone

from sqlalchemy import update

from app.models.carbon import CarbonClaim
from app.models.circular import BiocharRedemption
from app.models.factory_ops import BatchOutput, ManufacturingBatch
from tests.test_field_ops import env  # noqa: F401  (fixture)

NOW = datetime.now(timezone.utc)
MONTH = f"{NOW:%Y-%m}"
LAB = {"from": MONTH, "to": MONTH, "lab_c_org_pct": 42.0, "lab_h_corg_ratio": 0.35, "lab_name": "Lab Tanah BRMP Bogor",
       "lab_report_no": "LT-2026/118", "lab_report_url": "/uploads/lab-118.jpg"}


def _production(env, biochar_kg=2000.0, temp=550.0, redeem=(300.0, 200.0)):
    async def go(s):
        b = ManufacturingBatch(batch_code=f"B-{len(redeem)}-{biochar_kg:g}-{NOW.timestamp()}", pyrolysis_temp_c=temp,
                               pellet_share=0.3, silica_share_of_biochar=0.0, input_kg=biochar_kg * 3,
                               closure_error_pct=0.5, closure_ok=1, economics={}, operator_id=env.uid["pabrik"])
        s.add(b)
        await s.flush()
        s.add(BatchOutput(batch_id=b.id, product="biochar", quantity_kg=biochar_kg))
        ids = []
        for kg in redeem:
            r = BiocharRedemption(farmer_id=env.uid["petani"], kg=kg, status="diserahkan", handed_over_at=NOW,
                                  handed_over_by_id=env.uid["pabrik"])
            s.add(r)
            await s.flush()
            ids.append(r.id)
        await s.commit()
        return ids
    return env.q(go)


def test_preview_uses_lab_carbon_and_lists_blockers(env):
    _production(env)
    p = env.ok("pabrik", "POST", "/factory/carbon-claims/preview", LAB)
    assert p["blocking"] == [] and p["end_use_kg"] == 500 and p["redemption_count"] == 2
    assert "F_C & H/C_org masih parameter, belum uji lab per batch" not in p["warnings"]
    # 0,5 t × (1 − 10% air) × 0,42 × F_perm 0,80 × 44/12 = 0,5544 tCO₂e bruto
    assert abs(p["carbon_tco2e"]["biochar_sequestration"] - 0.554) < 0.002
    bad = env.ok("pabrik", "POST", "/factory/carbon-claims/preview", {**LAB, "lab_h_corg_ratio": 0.82})
    assert any("H/C-org" in b for b in bad["blocking"])
    assert env.call("pabrik", "POST", "/factory/carbon-claims", {**LAB, "lab_h_corg_ratio": 0.82}).status_code == 422
    assert env.call("pabrik", "POST", "/factory/carbon-claims", {**LAB, "lab_report_url": ""}).status_code == 422


def test_roles_four_eyes_and_no_double_counting(env):
    _production(env)
    assert env.call("auditor", "POST", "/factory/carbon-claims", LAB).status_code == 403
    assert env.call("admin", "POST", "/factory/carbon-claims", LAB).status_code == 403   # admin tidak mengajukan
    c = env.ok("pabrik", "POST", "/factory/carbon-claims", LAB, status=201)
    assert c["status"] == "diajukan" and c["integrity"]["ok"] and c["code"].startswith("CLM-")
    again = env.call("pabrik", "POST", "/factory/carbon-claims", LAB)                       # serah-terima sudah dikunci
    assert again.status_code == 422 and "tumpang-tindih" in again.json()["detail"]
    note = {"decision": "diverifikasi", "note": "Laporan lab & foto serah-terima dicek."}
    assert env.call("pabrik", "POST", f"/auditor/carbon-claims/{c['id']}/decision", note).status_code == 403
    assert env.call("admin", "POST", f"/auditor/carbon-claims/{c['id']}/decision", note).status_code == 403
    assert env.call("auditor", "POST", f"/auditor/carbon-claims/{c['id']}/decision",
                    {"decision": "diverifikasi", "note": "ok"}).status_code == 422             # alasan wajib
    v = env.ok("auditor", "POST", f"/auditor/carbon-claims/{c['id']}/decision", note)
    assert v["status"] == "diverifikasi" and "bukan kredit" in v["status_label"] and v["verified_by"] == "auditor"
    assert env.call("auditor", "POST", f"/auditor/carbon-claims/{c['id']}/decision", note).status_code == 409
    esg = env.ok("auditor", "GET", f"/factory/esg/report?from={MONTH}&to={MONTH}")
    g6 = next(k for k in esg["governance"] if k["code"] == "G6")
    assert g6["value"] == 1 and "bukan kredit" in g6["note"]


def test_rejection_releases_redemptions_for_corrected_claim(env):
    _production(env)
    c = env.ok("pabrik", "POST", "/factory/carbon-claims", LAB, status=201)
    env.ok("auditor", "POST", f"/auditor/carbon-claims/{c['id']}/decision",
           {"decision": "ditolak", "note": "Nomor laporan lab tidak cocok dengan foto."})
    c2 = env.ok("pabrik", "POST", "/factory/carbon-claims", {**LAB, "lab_report_no": "LT-2026/118-R"}, status=201)
    assert c2["end_use_kg"] == 500 and c2["redemption_count"] == 2


def test_tampered_snapshot_cannot_be_verified(env):
    _production(env)
    c = env.ok("pabrik", "POST", "/factory/carbon-claims", LAB, status=201)

    async def tamper(s):
        snap = dict(c and (await s.get(CarbonClaim, c["id"])).snapshot)
        snap["end_use_kg"] = 5000
        await s.execute(update(CarbonClaim).where(CarbonClaim.id == c["id"]).values(snapshot=snap))
        await s.commit()
    env.q(tamper)
    listed = env.ok("auditor", "GET", "/auditor/carbon-claims")
    assert listed[0]["integrity"]["hash_ok"] is False
    r = env.call("auditor", "POST", f"/auditor/carbon-claims/{c['id']}/decision",
                 {"decision": "diverifikasi", "note": "Dicek, tampak wajar."})
    assert r.status_code == 409 and "Integritas" in r.json()["detail"]


def test_no_handover_no_claim(env):
    _production(env, redeem=())
    p = env.ok("pabrik", "POST", "/factory/carbon-claims/preview", LAB)
    assert any("serah-terima" in b for b in p["blocking"])
