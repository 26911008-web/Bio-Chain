"""Menu Parameter Asumsi: semua angka asumsi dapat diubah, tervalidasi, teraudit, dan benar-benar dipakai engine."""

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app import models  # noqa: F401
from app import params
from app.database import Base, get_db
from app.dependencies import create_access_token
from app.engines.energy import classify_ike
from app.engines.forecaster import ForecastInput, forecast_supply
from app.engines.incentive import DeliveryEvent, calculate_incentive
from app.engines.quality import FeedstockSample, score_sample
from app.engines.routing import road_km
from app.main import app
from tests.conftest import isolated_engine
from app.models.user import User, UserRole
from app.routers.auth import hash_password
from app.schemas.routing import RouteRequest

HASH = hash_password("x")


@pytest.fixture
def env(tmp_path):
    engine, drop_schema = isolated_engine(tmp_path, "p.db")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            for i, r in enumerate((UserRole.PABRIK, UserRole.PETANI, UserRole.AUDITOR, UserRole.ADMIN, UserRole.PENGEPUL)):
                s.add(User(username=r.value, phone=f"0812{i:07d}", password_hash=HASH, full_name=r.value, role=r, is_active=True))
            await s.commit()
            return {u.username: u.id for u in (await s.execute(select(User))).scalars()}

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
    params.reset_cache()
    client = TestClient(app, raise_server_exceptions=False)
    h = {name: {"Authorization": f"Bearer {create_access_token(uid, name)}"} for name, uid in ids.items()}

    class E:
        def put(self, who, key, value, reason="uji perubahan asumsi"):
            return client.put(f"/api/v1/params/{key}", headers=h[who], json={"value": value, "reason": reason})

        def get(self, who, path="/api/v1/params"):
            return client.get(path, headers=h[who])

        def post(self, who, path, json):
            return client.post(path, headers=h[who], json=json)

    yield E()
    app.dependency_overrides.pop(get_db, None)
    params.reset_cache()                       # tes lain kembali memakai default
    asyncio.run(engine.dispose())
    if drop_schema:
        drop_schema()


# ---------------------------------------------------------------- registry
def test_every_default_is_valid_and_consistent():
    for d in params.DEFS:
        if d.required_input:                         # harga jual: sengaja tanpa angka bawaan
            assert d.default is None and params.validate(d, 1500) == 1500
            continue
        params.validate(d, d.default)
        params.cross_check(d.key, d.default)
    assert len(params.DEFS) >= 90 and set(d.group for d in params.DEFS) == set(params.GROUPS)


def test_physical_constants_are_not_editable():
    assert not any("earth" in k or "latent" in k or "ch4_lhv" in k for k in params.REGISTRY)


# ---------------------------------------------------------------- API & RBAC
def test_all_roles_can_read_only_factory_admin_can_edit(env):
    for who, can in (("petani", False), ("pengepul", False), ("auditor", False), ("pabrik", True), ("admin", True)):
        body = env.get(who).json()
        assert body["can_edit"] is can and body["groups"]
    assert env.put("petani", "harga_mutu.base_price_per_kg", 999).status_code == 403
    assert env.put("auditor", "harga_mutu.base_price_per_kg", 999).status_code == 403
    assert env.put("pabrik", "harga_mutu.base_price_per_kg", 450).status_code == 200


@pytest.mark.parametrize("key,value,phrase", [
    ("harga_mutu.base_price_per_kg", -5, "harus di antara"),
    ("harga_mutu.base_price_per_kg", "abc", "harus angka"),
    ("harga_mutu.grade_B_min", 85, "Grade B harus lebih kecil"),
    ("rendemen.yield_700c", 60, "Rendemen @700"),
    ("insentif.tier_emas_xp", 50, "Ambang XP tier"),
    ("energi.ike_ac_2", 30, "Batas IKE ac"),
])
def test_invalid_values_rejected(env, key, value, phrase):
    r = env.put("pabrik", key, value)
    assert r.status_code == 422 and phrase in r.json()["detail"]


def test_reason_is_mandatory(env):
    assert env.put("pabrik", "harga_mutu.base_price_per_kg", 420, reason="").status_code == 422


def test_changes_are_audited_and_reset_restores_default(env):
    env.put("pabrik", "logistik.cost_per_km", 5000, reason="harga BBM naik Oktober")
    r = env.post("admin", "/api/v1/params/logistik.cost_per_km/reset", {"reason": "kembali ke asumsi awal"})
    assert r.status_code == 200 and r.json()["value"] == 4000 and r.json()["modified"] is False
    hist = env.get("auditor", "/api/v1/params/history?key=logistik.cost_per_km").json()
    assert [h["reason"] for h in hist] == ["kembali ke asumsi awal", "harga BBM naik Oktober"]
    assert hist[1]["old_value"] == 4000 and hist[1]["new_value"] == 5000 and hist[0]["reset_to_default"]
    assert env.get("petani", "/api/v1/params/history").status_code == 403


# ---------------------------------------------------------------- nilai baru benar-benar dipakai engine
def _sample(moisture):
    return FeedstockSample(moisture=moisture, ash=18, volatile_matter=66, fixed_carbon=16, contamination=1)


def test_quality_thresholds_and_price_multiplier_follow_menu(env):
    assert score_sample(_sample(20))["grade"] != "TOLAK"
    env.put("pabrik", "harga_mutu.moisture_best", 8)
    env.put("pabrik", "harga_mutu.moisture_reject", 18)
    assert score_sample(_sample(20))["grade"] == "TOLAK"
    env.put("pabrik", "harga_mutu.mult_A", 1.30)
    assert score_sample(_sample(9))["price_multiplier"] == 1.30


def test_logistics_assumptions_follow_menu(env):
    a, b = (-7.70, 110.35), (-7.76, 110.40)
    base = road_km(a, b)
    env.put("pabrik", "logistik.road_factor", 1.6)
    assert road_km(a, b) == pytest.approx(base * 1.6 / 1.3)
    env.put("pabrik", "logistik.vehicle_m3", 24)
    assert RouteRequest().vehicle_m3 == 24


def test_forecast_incentive_energy_follow_menu(env):
    f0 = forecast_supply(ForecastInput(harvest_area_ha=500, month=6, year=2026)).predicted_supply_ton
    env.put("pabrik", "proyeksi.productivity_ton_per_ha", 10.6)
    assert forecast_supply(ForecastInput(harvest_area_ha=500, month=6, year=2026)).predicted_supply_ton == pytest.approx(2 * f0, rel=0.01)

    ev = DeliveryEvent(farmer_xp=0, quantity_ton=5, grade="A", on_time=False)
    assert calculate_incentive(ev).tier.value == "pemasok_aktif"            # 150 XP ≥ 100
    env.put("pabrik", "insentif.tier_aktif_xp", 200)
    assert calculate_incentive(ev).tier.value == "pemula"

    assert classify_ike(12, "ac") == "Efisien"
    env.put("pabrik", "energi.ike_ac_1", 12.5)
    env.put("pabrik", "energi.ike_ac_2", 15)
    assert classify_ike(12, "ac") == "Sangat efisien"


def test_table_parameter_adds_new_biomass_preset(env):
    rows = env.get("pabrik").json()
    presets = next(p for g in rows["groups"] for p in g["params"] if p["key"] == "biomassa.presets")["value"]
    new = presets + [{"id": "kulit_kopi", "name": "Kulit kopi", "moisture": 12, "ash": 6, "volatile_matter": 74,
                      "fixed_carbon": 20, "hydrogen": 6, "cn_ratio": 30, "bmp_m3_ch4_per_t_vs": 180,
                      "lignocellulosic": True, "price_rp_per_ton": 350000}]
    assert env.put("pabrik", "biomassa.presets", new).status_code == 200
    listed = env.get("pabrik", "/api/v1/labs/biomass/presets").json()
    assert "kulit_kopi" in {p["id"] for p in listed}
    r = env.post("pabrik", "/api/v1/labs/waste-energy/advise", {"preset": "kulit_kopi", "ton_per_day": 5})
    assert r.status_code == 200 and r.json()["stream"] == "Kulit kopi"
    dup = new + [dict(new[-1])]
    assert env.put("pabrik", "biomassa.presets", dup).status_code == 422


def test_topsis_weights_from_menu_change_ranking(env):
    body = {"purpose": "pellet", "feedstocks": [{"id": "sekam", "preset": "sekam_padi", "cost_per_ton": 100000},
                                                 {"id": "serbuk", "preset": "serbuk_gergaji", "cost_per_ton": 900000}]}
    first = env.post("pabrik", "/api/v1/labs/feedstock/compare", body).json()["ranking"][0]["id"]
    for k, v in (("feedstock.pellet_w_ash", 0), ("feedstock.pellet_w_lhv", 0), ("feedstock.pellet_w_moisture", 0),
                 ("feedstock.pellet_w_cost", 1)):
        env.put("pabrik", k, v)
    after = env.post("pabrik", "/api/v1/labs/feedstock/compare", body).json()
    assert after["ranking"][0]["id"] == "sekam" and first == "serbuk"
    assert after["computation_details"]["criteria"][3]["weight"] == 1.0
