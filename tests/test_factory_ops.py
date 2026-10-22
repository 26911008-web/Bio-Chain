"""Fase 3 — Pabrik: B2B procurement (ajuan, negosiasi, QC masuk), mass balance 1→3+loss,
akuntansi biaya (NRV/fisik, depresiasi, CVP) dan Pricing Engine harga beli sekam."""

import asyncio
import random

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models.harvest import Harvest, HarvestStatus
from app import params
from app.params import P
from app.database import Base, get_db
from app.dependencies import create_access_token
from app.engines.factory_econ import (PriceMissing, PricingRequest, allocate_joint_cost, batch_economics,
                                      contract_moisture_adjustment, process_yields, recommend_price)
from app.main import app
from tests.conftest import isolated_engine
from app.models.user import User, UserRole
from app.routers.auth import hash_password

HASH = hash_password("x")
LAB = {"ash": 18.0, "volatile_matter": 66.0, "fixed_carbon": 16.0}
# Harga jual = INPUT wajib (tanpa default). Tes mengisinya eksplisit seperti operator pabrik.
TEST_PRICES = {"pabrik.price_pellet_per_kg": 1_800.0, "pabrik.price_biochar_per_kg": 3_000.0,
               "pabrik.price_silica_per_kg": 12_000.0}


@pytest.fixture(autouse=True)
def filled_prices():
    params.reset_cache()
    params._values.update(TEST_PRICES)
    yield
    params.reset_cache()


# ---------------------------------------------------------------- engine murni
@pytest.mark.parametrize("seed", range(25))
def test_model_mass_balance_closes_exactly(seed):
    r = random.Random(seed)
    ys = process_yields(r.uniform(5, 24), r.uniform(1, 25), r.uniform(350, 700), r.random(), r.random())
    assert ys.closure == pytest.approx(1.0, abs=1e-12)
    assert all(v >= -1e-12 for v in (*ys.outputs.values(), *ys.losses.values()))


def test_price_ladder_and_moisture_monotonic():
    r = recommend_price(PricingRequest(moisture=11, ash=18))
    assert r["value_per_kg"] > r["floor_per_kg"] > r["ceiling_per_kg"] > r["target_per_kg"] > 0
    sens = [s["target_per_kg"] for s in r["sensitivity_moisture"]]
    assert sens == sorted(sens, reverse=True), "sekam lebih basah harus bernilai lebih rendah"
    assert r["mass_balance_closure"] == pytest.approx(1.0)


def test_contamination_lowers_value_and_reject_threshold():
    clean = recommend_price(PricingRequest(moisture=11, contamination=0))["target_per_kg"]
    dirty = recommend_price(PricingRequest(moisture=11, contamination=5))["target_per_kg"]
    assert dirty < clean
    assert recommend_price(PricingRequest(moisture=30))["accept"] is False


def test_price_follows_parameter_menu():
    base = recommend_price(PricingRequest(moisture=11))["target_per_kg"]
    params._values["pabrik.price_biochar_per_kg"] = 6_000
    assert recommend_price(PricingRequest(moisture=11))["target_per_kg"] > base


def test_sale_prices_have_no_default_and_must_be_entered():
    params.reset_cache()
    with pytest.raises(PriceMissing, match="Harga jual belum diisi"):
        recommend_price(PricingRequest(moisture=11))
    r = recommend_price(PricingRequest(moisture=11, price_pellet_per_kg=1800, price_biochar_per_kg=3000,
                                       price_silica_per_kg=12000))
    assert r["prices_used"] == {"bio_pellet": 1800, "biochar": 3000, "bio_silika": 12000}
    assert all(params.REGISTRY[k].default is None and params.REGISTRY[k].required_input for k in TEST_PRICES)


@pytest.mark.parametrize("route", ["biochar", "abu_pembakaran", "sekam_langsung"])
@pytest.mark.parametrize("seed", range(10))
def test_every_silica_route_closes_mass_balance(route, seed):
    r = random.Random(seed)
    ys = process_yields(r.uniform(5, 24), r.uniform(1, 25), r.uniform(350, 700), r.random() * 0.5, r.random(),
                        route, r.random() * 0.5)
    assert ys.closure == pytest.approx(1.0, abs=1e-12) and ys.route == route
    assert ys.outputs["bio_silika"] > 0


def test_silica_route_physics():
    char = process_yields(11, 18, silica_route="biochar")
    ash = process_yields(11, 18, silica_route="abu_pembakaran", silica_husk_share=0.2)
    direct = process_yields(11, 18, silica_route="sekam_langsung", silica_husk_share=0.2)
    assert ash.heat_recovered_mj > 0 and char.heat_recovered_mj == direct.heat_recovered_mj == 0
    assert ash.losses["gas_pembakaran"] > 0 and char.losses["gas_pembakaran"] == 0
    assert ash.outputs["biochar"] < char.outputs["biochar"]           # sebagian sekam dibakar, bukan dipirolisis
    with pytest.raises(ValueError):
        process_yields(11, 18, pellet_share=0.7, silica_route="sekam_langsung", silica_husk_share=0.5)


def test_contract_moisture_adjustment_is_dry_matter_and_penalty_only():
    assert contract_moisture_adjustment(500, 11, 9) == 500                          # lebih kering: tanpa bonus
    assert contract_moisture_adjustment(500, 11, 15) == pytest.approx(500 * 0.85 / 0.89)


@pytest.mark.parametrize("method", ["nrv", "fisik"])
def test_joint_cost_allocation_sums_to_total(method):
    out = {"bio_pellet": 300, "biochar": 230, "bio_silika": 17}
    alloc = allocate_joint_cost(1_000_000, out, {"bio_silika": 50_000}, method)
    assert sum(alloc.values()) == pytest.approx(1_000_000)
    if method == "fisik":
        assert alloc["bio_pellet"] / alloc["biochar"] == pytest.approx(300 / 230)


def test_batch_economics_flags_bad_closure_and_computes_breakeven():
    ok = batch_economics(1000, {"bio_pellet": 280, "biochar": 235, "bio_silika": 17},
                         {"air": 80, "volatil_syngas": 330, "residu_ekstraksi": 42, "susut_proses": 15}, 600_000, {})
    assert ok["mass_balance"]["closure_ok"] and abs(ok["mass_balance"]["closure_error_pct"]) < 0.5
    assert ok["cvp"]["break_even_ton_per_month"] > 0
    assert sum(p["allocated_joint_rp"] for p in ok["products"].values()) == pytest.approx(
        ok["totals"]["joint_cost_rp"] + ok["totals"]["fixed_allocated_rp"], abs=3)
    bad = batch_economics(1000, {"bio_pellet": 280, "biochar": 235, "bio_silika": 17}, {"air": 80}, 600_000, {})
    assert not bad["mass_balance"]["closure_ok"] and bad["mass_balance"]["closure_error_pct"] > 30


# ---------------------------------------------------------------- alur API (DB terisolasi)
@pytest.fixture
def env(tmp_path):
    engine, drop_schema = isolated_engine(tmp_path, "f.db")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            for i, (name, role) in enumerate((("pabrik", UserRole.PABRIK), ("pengepul", UserRole.PENGEPUL),
                                              ("pengepul2", UserRole.PENGEPUL), ("auditor", UserRole.AUDITOR),
                                              ("petani", UserRole.PETANI), ("supir", UserRole.DRIVER))):
                s.add(User(username=name, phone=f"0813{i:07d}", password_hash=HASH, full_name=name, role=role, is_active=True))
            await s.commit()
            return {u.username: (u.id, u.role.value) for u in (await s.execute(select(User))).scalars()}

    ids = asyncio.run(setup())

    async def override():
        async with Session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override
    client = TestClient(app, raise_server_exceptions=False)
    h = {n: {"Authorization": f"Bearer {create_access_token(uid, role)}"} for n, (uid, role) in ids.items()}

    class E:
        headers = h
        uid = {n: uid for n, (uid, _) in ids.items()}
        session_factory = Session

        def call(self, who, method, path, json=None):
            return client.request(method, f"/api/v1{path}", json=json, headers=h[who])

        def ok(self, who, method, path, json=None, status=200):
            r = self.call(who, method, path, json)
            assert r.status_code == status, f"{who} {method} {path} → {r.status_code}: {r.text}"
            return r.json()

    yield E()
    app.dependency_overrides.pop(get_db, None)
    params.reset_cache()
    asyncio.run(engine.dispose())
    if drop_schema:
        drop_schema()


def submit(env, who="pengepul", kg=5000, price=480, moisture=11):
    return env.ok(who, "POST", "/collector/delivery-requests",
                  {"quantity_kg": kg, "moisture_est": moisture, "ash_est": 18, "proposed_date": "2026-10-20",
                   "proposed_price_per_kg": price}, status=201)


def agreed(env, kg=5000, price=480, moisture=11):
    r = submit(env, kg=kg, price=price, moisture=moisture)
    env.ok("pabrik", "POST", f"/factory/delivery-requests/{r['id']}/respond", {"action": "accept"})
    return r


def test_request_carries_transparent_recommended_price(env):
    preview = env.ok("pengepul", "GET", "/collector/factory-price?moisture=11")
    r = submit(env)
    assert r["recommended_price_per_kg"] == preview["recommended_price_per_kg"] > 0
    assert "ceiling_per_kg" not in preview and "floor_per_kg" not in preview     # posisi tawar pabrik tidak dibuka


def test_negotiation_alternates_and_respects_round_limit(env):
    r = submit(env, price=520)
    rid = r["id"]
    assert env.call("pengepul", "POST", f"/collector/delivery-requests/{rid}/respond",
                    {"action": "accept"}).status_code == 409                       # giliran pabrik
    c = env.ok("pabrik", "POST", f"/factory/delivery-requests/{rid}/respond",
               {"action": "counter", "price_per_kg": 470, "date": "2026-10-22", "note": "kadar air tinggi musim hujan"})
    assert c["pending_party"] == "pengepul" and c["current_offer"] == {"price_per_kg": 470, "date": "2026-10-22"}
    env.ok("pengepul", "POST", f"/collector/delivery-requests/{rid}/respond",
           {"action": "counter", "price_per_kg": 495, "date": "2026-10-22"})
    env.ok("pabrik", "POST", f"/factory/delivery-requests/{rid}/respond",
           {"action": "counter", "price_per_kg": 485, "date": "2026-10-22"})
    over = env.call("pengepul", "POST", f"/collector/delivery-requests/{rid}/respond",
                    {"action": "counter", "price_per_kg": 490, "date": "2026-10-22"})
    assert over.status_code == 409 and "putaran" in over.json()["detail"]
    done = env.ok("pengepul", "POST", f"/collector/delivery-requests/{rid}/respond", {"action": "accept"})
    assert done["status"] == "accepted" and done["agreed"] == {"price_per_kg": 485, "date": "2026-10-22"}


def test_concurrent_factory_responses_only_one_applies(env):
    rid = submit(env)["id"]

    async def race():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await asyncio.gather(
                c.post(f"/api/v1/factory/delivery-requests/{rid}/respond", headers=env.headers["pabrik"], json={"action": "accept"}),
                c.post(f"/api/v1/factory/delivery-requests/{rid}/respond", headers=env.headers["pabrik"], json={"action": "reject"}))

    assert sorted(r.status_code for r in asyncio.run(race())) == [200, 409]


def test_qc_wetter_than_contract_gets_dry_matter_price_and_contaminants_unpaid(env):
    rid = agreed(env, kg=5000, price=480, moisture=11)["id"]
    qc = env.ok("pabrik", "POST", "/factory/qc", {"request_id": rid, "gross_kg": 5300, "tare_kg": 300,
                                                  "moisture": 15, "contamination": 2, **LAB}, status=201)
    assert qc["net_kg"] == 5000 and qc["payable_kg"] == 4900
    assert qc["final_price_per_kg"] == pytest.approx(480 * 0.85 / 0.89, abs=0.01)
    # refraksi kadar air tertulis di nota: kg basis kering setara kadar air acuan 11%
    assert qc["dry_basis_kg"] == pytest.approx(5000 * 0.85 / 0.89, abs=0.01)
    assert qc["refraction_kg"] == pytest.approx(5000 - 5000 * 0.85 / 0.89, abs=0.01)
    assert qc["decision"] == "terima_potongan" and qc["verification_code"].startswith(
        f"TRX-PGP{env.uid['pengepul']:04d}-PBK{env.uid['pabrik']:04d}-")
    assert qc["total_payment_rp"] == round(4900 * qc["final_price_per_kg"])
    assert env.call("pabrik", "POST", "/factory/qc", {"request_id": rid, "gross_kg": 1, "tare_kg": 0, "moisture": 11,
                                                      **LAB}).status_code == 409


def test_qc_rejects_wet_load_without_payment(env):
    rid = agreed(env)["id"]
    qc = env.ok("pabrik", "POST", "/factory/qc", {"request_id": rid, "gross_kg": 5000, "tare_kg": 0, "moisture": 30,
                                                  **LAB}, status=201)
    assert qc["decision"] == "tolak" and qc["total_payment_rp"] == 0 and qc["remaining_kg"] == 0
    assert env.ok("pengepul", "GET", "/collector/delivery-requests")[0]["status"] == "rejected"


def test_qc_requires_agreement_first(env):
    rid = submit(env)["id"]
    assert env.call("pabrik", "POST", "/factory/qc", {"request_id": rid, "gross_kg": 100, "tare_kg": 0, "moisture": 11,
                                                      **LAB}).status_code == 409


def _lot(env, kg=5000, moisture=11):
    rid = agreed(env, kg=kg, moisture=moisture)["id"]
    return env.ok("pabrik", "POST", "/factory/qc", {"request_id": rid, "gross_kg": kg, "tare_kg": 0, "moisture": moisture,
                                                    **LAB}, status=201)


def _model_batch(lot_id, kg, code):
    ys = process_yields(11, 18)
    return {"batch_code": code, "inputs": [{"qc_id": lot_id, "kg": kg}],
            "outputs": {p: round(v * kg, 1) for p, v in ys.outputs.items()},
            "losses": {k: round(v * kg, 1) for k, v in ys.losses.items()},
            "costs": [{"item": "listrik", "amount_rp": 150 * kg / 1000 * 1444.7, "driver_qty": 150 * kg / 1000, "driver_unit": "kWh"},
                      {"item": "tenaga_kerja", "amount_rp": 2 * kg / 1000 * 20000},
                      {"item": "bahan_kimia", "amount_rp": ys.outputs["bio_silika"] * kg * 4000, "product": "bio_silika"}]}


def test_batch_consumes_lot_and_reports_unit_economics(env):
    lot = _lot(env, kg=5000)
    b = env.ok("pabrik", "POST", "/factory/batches", _model_batch(lot["id"], 3000, "B-001"), status=201)
    eco = b["economics"]
    assert b["closure_ok"] and abs(b["closure_error_pct"]) < 0.1
    assert eco["input_quality"]["raw_material_cost_rp"] == pytest.approx(3000 * 480, rel=1e-6)
    assert all(eco["products"][p]["cost_per_ton_rp"] > 0 for p in ("bio_pellet", "biochar", "bio_silika"))
    assert all(abs(v["variance_pct"]) < 1 for v in eco["yield_variance"].values())     # aktual = model
    lots = env.ok("pabrik", "GET", "/factory/qc/lots")
    assert lots[0]["remaining_kg"] == 2000
    assert env.call("pabrik", "POST", "/factory/batches", _model_batch(lot["id"], 2500, "B-002")).status_code == 409


def test_batch_with_unbalanced_weights_is_flagged(env):
    lot = _lot(env)
    body = _model_batch(lot["id"], 1000, "B-BAD")
    body["losses"] = {"air": 10}
    b = env.ok("pabrik", "POST", "/factory/batches", body, status=201)
    assert not b["closure_ok"] and b["closure_error_pct"] > 30


def test_concurrent_batches_cannot_overdraw_a_lot(env):
    lot = _lot(env, kg=1000)

    async def race():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await asyncio.gather(*[
                c.post("/api/v1/factory/batches", headers=env.headers["pabrik"], json=_model_batch(lot["id"], 700, f"R-{i}"))
                for i in range(2)])

    assert sorted(r.status_code for r in asyncio.run(race())) == [201, 409]


@pytest.mark.parametrize("who,method,path,code", [
    ("pengepul", "POST", "/factory/qc", 403), ("petani", "POST", "/collector/delivery-requests", 403),
    ("auditor", "GET", "/factory/batches", 200), ("auditor", "POST", "/factory/batches", 403),
    ("pengepul", "POST", "/factory/pricing/recommend", 403), ("petani", "GET", "/collector/factory-price", 403),
])
def test_factory_rbac(env, who, method, path, code):
    assert env.call(who, method, path, {} if method == "POST" else None).status_code in (
        (code,) if code != 200 else (200,))


def test_other_collector_cannot_answer_my_request(env):
    rid = submit(env)["id"]
    env.ok("pabrik", "POST", f"/factory/delivery-requests/{rid}/respond",
           {"action": "counter", "price_per_kg": 460, "date": "2026-10-25"})
    assert env.call("pengepul2", "POST", f"/collector/delivery-requests/{rid}/respond",
                    {"action": "accept"}).status_code == 404



# ---------------------------------------------------------------- harga wajib di API & rantai ke dompet petani
def test_api_without_prices_returns_clear_422_and_request_still_possible(env):
    params.reset_cache()
    r = env.call("pabrik", "POST", "/factory/pricing/recommend", {"moisture": 11})
    assert r.status_code == 422 and r.json()["code"] == "price_missing"
    preview = env.ok("pengepul", "GET", "/collector/factory-price?moisture=11")
    assert preview["recommended_price_per_kg"] is None
    assert submit(env)["recommended_price_per_kg"] is None


def _farmer_harvest(env, kg, weighed):
    h = env.ok("petani", "POST", "/farmer/harvest", {"quantity_kg": kg}, status=201)
    env.ok("pengepul", "POST", "/collector/verify", {"harvest_id": h["id"], "weighed_kg": weighed, "moisture": 11,
                                                     "contamination": 0, **LAB})
    return h["id"]


def _dr_with(env, ids, kg):
    req = env.ok("pengepul", "POST", "/collector/delivery-requests",
                 {"quantity_kg": kg, "moisture_est": 11, "proposed_date": "2026-10-20", "proposed_price_per_kg": 480,
                  "harvest_ids": ids}, status=201)
    env.ok("pabrik", "POST", f"/factory/delivery-requests/{req['id']}/respond", {"action": "accept"})
    return req


def test_full_chain_farmer_harvest_to_factory_batch_credits_wallet(env):
    h1 = _farmer_harvest(env, 3000, 3000)
    h2 = _farmer_harvest(env, 1000, 1000)
    req = _dr_with(env, [h1, h2], 5000)
    # Lot 5.000 kg: 4.000 kg dari petani (2 harvest) + 1.000 kg stok pengepul sendiri
    qc = env.ok("pabrik", "POST", "/factory/qc", {"request_id": req["id"], "gross_kg": 5000, "tare_kg": 0,
                                                  "moisture": 11, **LAB}, status=201)
    mb = env.ok("auditor", "GET", f"/auditor/mass-balance/{h1}")
    assert mb["status"] == "delivered" and mb["weights_kg"]["factory_scale"] == 3000
    body = _model_batch(qc["id"], 5000, "B-WALLET")
    b = env.ok("pabrik", "POST", "/factory/batches", body, status=201)
    w = b["economics"]["wallet"]
    biochar = body["outputs"]["biochar"]
    assert w["allocated_kg"] + w["untraceable_kg"] == pytest.approx(biochar, abs=0.001)    # habis terbagi
    assert w["allocated_kg"] == pytest.approx(biochar * 4000 / 5000, abs=0.002)
    wallet = env.ok("petani", "GET", "/farmer/wallet")
    assert wallet["balance_kg"] == pytest.approx(w["allocated_kg"], abs=1e-9)
    assert {e["harvest_id"] for e in wallet["entries"]} == {h1, h2}
    assert env.ok("auditor", "GET", f"/auditor/mass-balance/{h1}")["status"] == "converted"
    by_h = {e["harvest_id"]: e["amount_kg"] for e in wallet["entries"]}
    assert by_h[h1] / by_h[h2] == pytest.approx(3.0, rel=1e-3)


def test_shrinkage_is_shared_proportionally_to_farmers(env):
    h1 = _farmer_harvest(env, 2000, 2000)
    h2 = _farmer_harvest(env, 2000, 2000)
    req = _dr_with(env, [h1, h2], 4000)
    env.ok("pabrik", "POST", "/factory/qc", {"request_id": req["id"], "gross_kg": 3800, "tare_kg": 0, "moisture": 11, **LAB},
           status=201)
    for h in (h1, h2):
        mb = env.ok("auditor", "GET", f"/auditor/mass-balance/{h}")
        assert mb["weights_kg"]["factory_scale"] == 1900 and mb["shrinkage"]["pct"] == 5.0


def test_cannot_attach_unverified_or_foreign_harvest(env):
    h = env.ok("petani", "POST", "/farmer/harvest", {"quantity_kg": 500}, status=201)      # belum ditimbang
    body = {"quantity_kg": 500, "moisture_est": 11, "proposed_date": "2026-10-20", "proposed_price_per_kg": 480}
    assert env.call("pengepul", "POST", "/collector/delivery-requests", {**body, "harvest_ids": [h["id"]]}).status_code == 409
    v = _farmer_harvest(env, 500, 500)
    assert env.call("pengepul2", "POST", "/collector/delivery-requests", {**body, "harvest_ids": [v]}).status_code == 409


def test_dispatch_rejects_harvest_already_attached_to_delivery_request(env):
    h = _farmer_harvest(env, 600, 600)
    _dr_with(env, [h], 600)
    res = env.call("pabrik", "POST", "/factory/dispatch", {"driver_id": env.uid["supir"], "harvest_ids": [h]})
    assert res.status_code == 409
    assert "sudah terlampir Delivery Request" in res.json()["detail"]


def test_cannot_attach_harvest_currently_in_active_route_to_delivery_request(env):
    h = env.ok("petani", "POST", "/farmer/harvest", {"quantity_kg": 500}, status=201)
    env.ok("pengepul", "POST", "/collector/verify", {"harvest_id": h["id"], "weighed_kg": 500, "moisture": 11,
                                                     "contamination": 0, **LAB})
    env.ok("pabrik", "POST", "/factory/dispatch", {"driver_id": env.uid["supir"], "harvest_ids": [h["id"]]}, status=201)
    attachable = env.ok("pengepul", "GET", "/collector/attachable-harvests")
    assert all(item["id"] != h["id"] for item in attachable)
    body = {"quantity_kg": 500, "moisture_est": 11, "proposed_date": "2026-10-20", "proposed_price_per_kg": 480,
            "harvest_ids": [h["id"]]}
    res = env.call("pengepul", "POST", "/collector/delivery-requests", body)
    assert res.status_code == 409


def test_cancelled_request_releases_harvests(env):
    h = _farmer_harvest(env, 800, 800)
    body = {"quantity_kg": 800, "moisture_est": 11, "proposed_date": "2026-10-20", "proposed_price_per_kg": 480,
            "harvest_ids": [h]}
    first = env.ok("pengepul", "POST", "/collector/delivery-requests", body, status=201)
    env.ok("pengepul", "POST", f"/collector/delivery-requests/{first['id']}/respond", {"action": "cancel"})
    env.ok("pengepul", "POST", "/collector/delivery-requests", body, status=201)        # bisa dilampirkan ulang


def test_rejected_lot_rejects_linked_harvests(env):
    h = _farmer_harvest(env, 900, 900)
    req = _dr_with(env, [h], 900)
    env.ok("pabrik", "POST", "/factory/qc", {"request_id": req["id"], "gross_kg": 900, "tare_kg": 0, "moisture": 30, **LAB},
           status=201)
    assert env.ok("auditor", "GET", f"/auditor/mass-balance/{h}")["status"] == "rejected"


def test_batch_with_ash_route_records_combustion_gas(env):
    lot = _lot(env, kg=2000)
    ys = process_yields(11, 18, silica_route="abu_pembakaran", silica_husk_share=0.2)
    body = {"batch_code": "B-ASH", "inputs": [{"qc_id": lot["id"], "kg": 2000}], "silica_route": "abu_pembakaran",
            "silica_husk_share": 0.2, "outputs": {k: round(v * 2000, 1) for k, v in ys.outputs.items()},
            "losses": {k: round(v * 2000, 1) for k, v in ys.losses.items()}}
    b = env.ok("pabrik", "POST", "/factory/batches", body, status=201)
    assert b["closure_ok"] and b["economics"]["mass_balance"]["losses_kg"]["gas_pembakaran"] > 0
    assert all(abs(v["variance_pct"]) < 1 for v in b["economics"]["yield_variance"].values())


# ---------------------------------------------------------------- pembayaran pabrik → pengepul (kedua jalur)
def _route_receive(env, kg=1000, received=980, verify_moisture=11, **extra):
    """Jalur armada pabrik: lapor → timbang pengepul → dispatch → jemput supir → timbang terima pabrik."""
    h = env.ok("petani", "POST", "/farmer/harvest", {"quantity_kg": kg}, status=201)
    # Di atas batas tolak pengepul hanya bisa membeli secara eksplisit "untuk dikeringkan" (risiko miliknya)
    env.ok("pengepul", "POST", "/collector/verify", {"harvest_id": h["id"], "weighed_kg": kg, "moisture": verify_moisture,
                                                     "contamination": 0, "beli_untuk_dikeringkan": verify_moisture > 25,
                                                     **LAB})
    route = env.ok("pabrik", "POST", "/factory/dispatch", {"driver_id": env.uid["supir"], "harvest_ids": [h["id"]]},
                   status=201)
    env.ok("supir", "POST", f"/driver/start-route?route_id={route['route_id']}")
    env.ok("supir", "POST", "/driver/confirm-pickup", {"route_stop_id": route["stops"][0]["route_stop_id"],
                                                       "qr_code": h["qr_code"], "actual_ton": kg / 1000})
    env.ok("supir", "POST", f"/driver/complete-route?route_id={route['route_id']}")
    return env.ok("pabrik", "POST", "/factory/receive", {"harvest_id": h["id"], "received_kg": received, **extra})


def test_route_receive_creates_settlement_priced_by_engine(env):
    r = _route_receive(env)
    s = r["settlement"]
    target = recommend_price(PricingRequest(moisture=11, ash=18, sensitivity=False))["target_per_kg"]
    assert s["source"] == "rute" and s["status"] == "terutang" and s["collector_id"] == env.uid["pengepul"]
    assert s["payable_kg"] == 980 and s["price_per_kg"] == pytest.approx(target)
    assert s["amount_rp"] == round(980 * target)


def test_arrivals_list_shows_collected_then_clears_after_receive(env):
    h = env.ok("petani", "POST", "/farmer/harvest", {"quantity_kg": 400}, status=201)
    env.ok("pengepul", "POST", "/collector/verify", {"harvest_id": h["id"], "weighed_kg": 400, "moisture": 11,
                                                     "contamination": 0, **LAB})
    route = env.ok("pabrik", "POST", "/factory/dispatch", {"driver_id": env.uid["supir"], "harvest_ids": [h["id"]]},
                   status=201)
    env.ok("supir", "POST", f"/driver/start-route?route_id={route['route_id']}")
    env.ok("supir", "POST", "/driver/confirm-pickup", {"route_stop_id": route["stops"][0]["route_stop_id"],
                                                       "qr_code": h["qr_code"], "actual_ton": 0.4})
    arrivals = env.ok("pabrik", "GET", "/factory/arrivals")
    assert [a["harvest_id"] for a in arrivals] == [h["id"]]
    assert arrivals[0]["farmer_name"] is not None
    assert arrivals[0]["collector_name"] is not None
    assert env.call("pengepul", "GET", "/factory/arrivals").status_code == 403
    env.ok("pabrik", "POST", "/factory/receive", {"harvest_id": h["id"], "received_kg": 395})
    assert env.ok("pabrik", "GET", "/factory/arrivals") == []


def test_route_receive_with_explicit_price(env):
    s = _route_receive(env, price_per_kg=455)["settlement"]
    assert s["price_per_kg"] == 455 and s["amount_rp"] == 980 * 455 and "diisi pabrik" in s["price_basis"]


def test_route_without_sale_prices_waits_then_price_then_pay_once(env):
    params.reset_cache()                                       # harga jual belum diisi
    s = _route_receive(env)["settlement"]
    assert s["status"] == "menunggu_harga" and s["amount_rp"] is None
    assert env.call("pabrik", "POST", f"/factory/settlements/{s['id']}/pay",
                    {"payment_reference": "TRF-1"}).status_code == 409            # belum berharga
    p = env.ok("pabrik", "POST", f"/factory/settlements/{s['id']}/price", {"price_per_kg": 470, "reason": "kesepakatan"})
    assert p["status"] == "terutang" and p["amount_rp"] == 980 * 470
    paid = env.ok("pabrik", "POST", f"/factory/settlements/{s['id']}/pay", {"payment_reference": "TRF-1"})
    assert paid["status"] == "dibayar" and paid["payment_reference"] == "TRF-1"
    assert env.call("pabrik", "POST", f"/factory/settlements/{s['id']}/pay",
                    {"payment_reference": "TRF-2"}).status_code == 409             # tidak bisa dibayar dua kali
    assert env.call("pabrik", "POST", f"/factory/settlements/{s['id']}/price",
                    {"price_per_kg": 999, "reason": "ubah sesudah lunas"}).status_code == 409


def test_qc_path_creates_payable_settlement_and_reject_creates_none(env):
    lot = _lot(env, kg=2000)
    rows = env.ok("pabrik", "GET", "/factory/settlements")
    assert [(r["source"], r["qc_id"], r["amount_rp"], r["status"]) for r in rows] == \
        [("qc", lot["id"], lot["total_payment_rp"], "terutang")]
    rid = agreed(env)["id"]
    env.ok("pabrik", "POST", "/factory/qc", {"request_id": rid, "gross_kg": 500, "tare_kg": 0, "moisture": 30, **LAB},
           status=201)
    assert len(env.ok("pabrik", "GET", "/factory/settlements")) == 1


def test_collector_sees_only_own_settlements(env):
    _route_receive(env)
    st = env.ok("pengepul", "GET", "/collector/settlements")
    assert len(st) == 1
    assert st[0]["farmer_name"] is not None
    assert env.ok("pengepul2", "GET", "/collector/settlements") == []


@pytest.mark.parametrize("who,method,path,code", [
    ("auditor", "GET", "/factory/settlements", 200), ("pengepul", "GET", "/factory/settlements", 403),
    ("auditor", "POST", "/factory/settlements/1/pay", 403), ("pengepul", "POST", "/factory/settlements/1/price", 403),
    ("petani", "GET", "/collector/settlements", 403),
])
def test_settlement_rbac(env, who, method, path, code):
    body = {"payment_reference": "X-123", "price_per_kg": 1, "reason": "uji akses"} if method == "POST" else None
    assert env.call(who, method, path, body).status_code == code


def test_route_receive_above_moisture_limit_waits_price_not_payable_zero(env):
    """B3: Kadar air 30% (di atas batas tolak) -> status menunggu_harga, bukan terutang Rp 0."""
    r = _route_receive(env, verify_moisture=30)
    s = r["settlement"]
    assert s["status"] == "menunggu_harga"
    assert s["price_per_kg"] is None
    assert s["amount_rp"] is None
    assert "di luar batas mutu" in s["price_basis"]
    assert s["status"] != "terutang"


def test_route_receive_moisture_none_uses_reference_moisture(env):
    """B4: Jika harvest.moisture kosong, gunakan kadar air referensi tanpa teks 'kadar air None%'."""
    h = env.ok("petani", "POST", "/farmer/harvest", {"quantity_kg": 1000}, status=201)
    env.ok("pengepul", "POST", "/collector/verify", {"harvest_id": h["id"], "weighed_kg": 1000, "moisture": 11,
                                                     "contamination": 0, **LAB})
    route = env.ok("pabrik", "POST", "/factory/dispatch", {"driver_id": env.uid["supir"], "harvest_ids": [h["id"]]},
                   status=201)
    env.ok("supir", "POST", f"/driver/start-route?route_id={route['route_id']}")
    env.ok("supir", "POST", "/driver/confirm-pickup", {"route_stop_id": route["stops"][0]["route_stop_id"],
                                                       "qr_code": h["qr_code"], "actual_ton": 1.0})
    env.ok("supir", "POST", f"/driver/complete-route?route_id={route['route_id']}")

    # Kosongkan moisture di database untuk menguji fallback
    async def _clear_moisture():
        async with env.session_factory() as session:
            await session.execute(update(Harvest).where(Harvest.id == h["id"]).values(moisture=None))
            await session.commit()
    asyncio.run(_clear_moisture())

    res = env.ok("pabrik", "POST", "/factory/receive", {"harvest_id": h["id"], "received_kg": 980})
    s = res["settlement"]
    assert s["moisture"] == P("pabrik.reference_moisture_pct")
    assert "None%" not in s["price_basis"]
    assert "kadar air referensi" in s["price_basis"]


def test_settlement_history_audit_trail(env):
    """S2: Jejak audit settlement_events mencatat dibuat -> harga -> dibayar, append-only."""
    r = _route_receive(env, price_per_kg=450)
    sid = r["settlement"]["id"]

    # 1. Jejak awal 'dibuat'
    hist = env.ok("pabrik", "GET", f"/factory/settlements/{sid}/history")
    assert len(hist) == 1
    assert hist[0]["action"] == "dibuat"
    assert hist[0]["new_price"] == 450
    assert hist[0]["new_amount"] == 980 * 450

    # 2. Perubahan harga 'harga'
    env.ok("pabrik", "POST", f"/factory/settlements/{sid}/price", {"price_per_kg": 460, "reason": "koreksi mutu lab"})
    hist2 = env.ok("pabrik", "GET", f"/factory/settlements/{sid}/history")
    assert len(hist2) == 2
    assert hist2[1]["action"] == "harga"
    assert hist2[1]["old_price"] == 450
    assert hist2[1]["new_price"] == 460
    assert hist2[1]["reason"] == "koreksi mutu lab"

    # 3. Pembayaran 'dibayar'
    env.ok("pabrik", "POST", f"/factory/settlements/{sid}/pay", {"payment_reference": "TRF-TEST-999"})
    hist3 = env.ok("pabrik", "GET", f"/factory/settlements/{sid}/history")
    assert len(hist3) == 3
    assert hist3[2]["action"] == "dibayar"
    assert hist3[2]["new_price"] == 460
    assert "TRF-TEST-999" in hist3[2]["reason"]

    # 4. RBAC: pabrik dan auditor bisa baca history lewat /factory/settlements/{sid}/history
    assert env.call("pabrik", "GET", f"/factory/settlements/{sid}/history").status_code == 200
    assert env.call("auditor", "GET", f"/factory/settlements/{sid}/history").status_code == 200
    assert env.call("pengepul", "GET", f"/factory/settlements/{sid}/history").status_code == 403

    # Pengepul bisa membaca history miliknya lewat /collector/settlements/{sid}/history, pengepul lain 404
    assert env.call("pengepul", "GET", f"/collector/settlements/{sid}/history").status_code == 200
    assert env.call("pengepul2", "GET", f"/collector/settlements/{sid}/history").status_code == 404


def test_receive_without_collector_returns_warning(env):
    """S5: Penerimaan sekam tanpa pengepul menghasilkan peringatan eksplisit."""
    h = env.ok("petani", "POST", "/farmer/harvest", {"quantity_kg": 500}, status=201)

    async def _to_collected():
        async with env.session_factory() as session:
            await session.execute(update(Harvest).where(Harvest.id == h["id"]).values(status=HarvestStatus.COLLECTED))
            await session.commit()
    asyncio.run(_to_collected())

    r = env.ok("pabrik", "POST", "/factory/receive", {"harvest_id": h["id"], "received_kg": 490})
    assert r["settlement"] is None
    assert r["warning"] is not None
    assert "tanpa pengepul" in r["warning"]


def test_settlement_paid_without_reference_violates_constraint(env):
    """S3: Model constraint ck_settle_paid_ref menolak status 'dibayar' tanpa payment_reference."""
    from sqlalchemy.exc import IntegrityError
    from app.models.factory_ops import CollectorSettlement, SettlementStatus

    async def _insert_bad():
        async with env.session_factory() as session:
            bad = CollectorSettlement(
                collector_id=env.uid["pengepul"],
                source="qc",
                qc_id=9999,
                payable_kg=100.0,
                status=SettlementStatus.PAID,
                payment_reference=None,
                amount_rp=50000.0,
                created_by_id=env.uid["pabrik"],
            )
            session.add(bad)
            await session.commit()

    with pytest.raises(IntegrityError):
        asyncio.run(_insert_bad())


def test_settlement_model_has_required_check_constraints():
    """S3: Model CollectorSettlement memiliki seluruh check constraint selaras migrasi."""
    from app.models.factory_ops import CollectorSettlement
    c_names = {c.name for c in CollectorSettlement.__table__.constraints if getattr(c, "name", None)}
    for expected in ("ck_settle_status", "ck_settle_paid_ref", "ck_settle_kg", "ck_settle_amount", "ck_settle_source", "ck_settle_priced"):
        assert expected in c_names, f"Constraint {expected} tidak terdaftar di model CollectorSettlement"
