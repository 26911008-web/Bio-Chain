"""Fase 4 — Laporan bulanan dari gudang data tunggal: angka per peran harus sama dengan transaksi sumbernya."""

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app import models  # noqa: F401
from app import params
from app.database import Base, get_db
from app.dependencies import create_access_token
from app.engines.factory_econ import process_yields
from app.main import app
from app.models.user import User, UserRole
from app.routers.auth import hash_password
from app.services.reports import WIB, month_of, month_range
from tests.conftest import isolated_engine

LAB = {"ash": 18.0, "volatile_matter": 66.0, "fixed_carbon": 16.0, "contamination": 0}
PEOPLE = {"petani_a": UserRole.PETANI, "petani_b": UserRole.PETANI, "pengepul": UserRole.PENGEPUL,
          "supir": UserRole.DRIVER, "pabrik": UserRole.PABRIK, "auditor": UserRole.AUDITOR}
HASH = hash_password("x")
NOW = datetime.now(WIB).strftime("%Y-%m")


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    """Satu bulan operasi lengkap di DB terisolasi; dipakai bersama oleh semua tes modul ini."""
    engine, drop = isolated_engine(tmp_path_factory.mktemp("rep"), "rep.db")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            for i, (n, r) in enumerate(PEOPLE.items()):
                s.add(User(username=n, phone=f"0815{i:07d}", password_hash=HASH, full_name=n, role=r, is_active=True,
                           lat=-7.70 - i * 0.01, lon=110.35))
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
    params.reset_cache()
    params._values.update({"pabrik.price_pellet_per_kg": 1800.0, "pabrik.price_biochar_per_kg": 3000.0,
                           "pabrik.price_silica_per_kg": 12000.0})
    c = TestClient(app, raise_server_exceptions=False)
    H = {n: {"Authorization": f"Bearer {create_access_token(uid, role)}"} for n, (uid, role) in ids.items()}

    def ok(who, method, path, json=None, status=200):
        r = c.request(method, f"/api/v1{path}", json=json, headers=H[who])
        assert r.status_code == status, f"{who} {path} → {r.status_code}: {r.text}"
        return r.json()

    def harvest(farmer, kg):
        h = ok(farmer, "POST", "/farmer/harvest", {"quantity_kg": kg}, 201)
        v = ok("pengepul", "POST", "/collector/verify", {"harvest_id": h["id"], "weighed_kg": kg, "moisture": 11, **LAB})
        return h, v

    facts = {}
    # 1) Jalur Delivery Request → QC → batch → dompet (petani A 3.000 kg + B 1.000 kg, susut 5%)
    (ha, va), (hb, vb) = harvest("petani_a", 3000), harvest("petani_b", 1000)
    dr = ok("pengepul", "POST", "/collector/delivery-requests",
            {"quantity_kg": 4000, "moisture_est": 11, "proposed_date": "2026-10-20", "proposed_price_per_kg": 480,
             "harvest_ids": [ha["id"], hb["id"]]}, status=201)
    ok("pabrik", "POST", f"/factory/delivery-requests/{dr['id']}/respond", {"action": "accept"})
    qc = ok("pabrik", "POST", "/factory/qc", {"request_id": dr["id"], "gross_kg": 3800, "tare_kg": 0, "moisture": 11, **LAB},
            status=201)
    ys = process_yields(11, 18)
    out = {k: round(v * 3800, 1) for k, v in ys.outputs.items()}
    batch = ok("pabrik", "POST", "/factory/batches", {
        "batch_code": "REP-1", "inputs": [{"qc_id": qc["id"], "kg": 3800}], "outputs": out,
        "losses": {k: round(v * 3800, 1) for k, v in ys.losses.items()},
        "costs": [{"item": "listrik", "amount_rp": 800_000}]}, status=201)
    # 2) Jalur rute armada pabrik: petani A 500 kg dijemput supir, diterima 490 kg
    (hr, vr) = harvest("petani_a", 500)
    route = ok("pabrik", "POST", "/factory/dispatch", {"driver_id": ids["supir"][0], "harvest_ids": [hr["id"]]}, 201)
    ok("supir", "POST", f"/driver/start-route?route_id={route['route_id']}")
    ok("supir", "POST", "/driver/confirm-pickup", {"route_stop_id": route["stops"][0]["route_stop_id"],
                                                   "qr_code": hr["qr_code"], "actual_ton": 0.5})
    ok("supir", "POST", f"/driver/complete-route?route_id={route['route_id']}")
    recv = ok("pabrik", "POST", "/factory/receive", {"harvest_id": hr["id"], "received_kg": 490})
    # 3) Lelang: petani B menjual 300 kg ke pengepul
    lst = ok("petani_b", "POST", "/farmer/listings", {"quantity_kg": 300, "allow_jemput": True, "ask_price_jemput": 400}, 201)
    bid = ok("pengepul", "POST", "/collector/bids", {"listing_id": lst["id"], "scheme": "jemput", "price_per_kg": 420,
                                                     "quantity_kg": 300}, 201)
    ok("petani_b", "POST", f"/farmer/listings/{lst['id']}/accept", {"bid_id": bid["bid_id"], "quantity_kg": 300})
    # 4) Energi bulan ini
    ok("pabrik", "POST", "/factory/energy/readings", {"facility": "Pabrik Uji", "period": NOW, "kwh": 60_000,
                                                      "building_kwh": 3_000, "production_ton": 400, "floor_area_m2": 300},
       status=201)

    facts.update(qc=qc, batch=batch, out=out, paid={"a": va["total_price"] + vr["total_price"], "b": vb["total_price"]},
                 dr_paid=va["total_price"] + vb["total_price"], route_settle=recv["settlement"],
                 factory_paid=qc["total_payment_rp"] + recv["settlement"]["amount_rp"])
    wallet_a = ok("petani_a", "GET", "/farmer/wallet")["balance_kg"]
    wallet_b = ok("petani_b", "GET", "/farmer/wallet")["balance_kg"]
    facts.update(wallet_a=wallet_a, wallet_b=wallet_b)

    def report(who, query=f"?from={NOW}&to={NOW}"):
        r = c.get(f"/api/reports/monthly{query}", headers=H[who])
        return r

    yield {"report": report, "facts": facts, "client": c, "H": H}
    app.dependency_overrides.pop(get_db, None)
    params.reset_cache()
    asyncio.run(engine.dispose())
    if drop:
        drop()


def row(rep):
    assert len(rep["months"]) == 1 and rep["months"][0]["month"] == NOW
    return rep["months"][0]


# ---------------------------------------------------------------- pabrik (seluruh pabrik)
def test_plant_supply_volume_matches_sources(world):
    r = row(world["report"]("pabrik").json())
    s = r["supply"]
    # 3.000 + 1.000 + 500 laporan langsung + 300 harvest hasil lelang (listing dihitung sekali, saat menjadi kontrak)
    assert s["reported_kg"] == 3000 + 1000 + 500 + 300
    assert s["collector_verified_kg"] == 4500
    assert s["factory_received_kg"] == 3800 + 490                      # lot QC + jalur rute, tanpa hitung ganda
    assert s["shrinkage_pct"] == pytest.approx((4500 - 4290) / 4500 * 100, abs=0.01)


def test_plant_conversion_percentages(world):
    f = world["facts"]
    c = row(world["report"]("pabrik").json())["conversion"]
    assert c["batch_input_kg"] == 3800
    for p in ("bio_pellet", "biochar", "bio_silika"):
        assert c[f"{p}_pct"] == pytest.approx(f["out"][p] / 3800 * 100, abs=0.01)
    assert c["biochar_to_farmers_kg"] == pytest.approx(f["wallet_a"] + f["wallet_b"], abs=0.001)
    assert abs(c["closure_error_pct"]) < 0.1


def test_plant_cost_efficiency(world):
    f = world["facts"]
    k = row(world["report"]("pabrik").json())["cost"]
    assert k["raw_material_rp"] == pytest.approx(f["factory_paid"])          # QC lot + jalur rute
    assert k["unpriced_kg"] == 0
    assert k["cost_per_ton_input_rp"] == pytest.approx(f["batch"]["economics"]["totals"]["total_cost_rp"] * 1000 / 3800, abs=1)
    assert k["margin_pct"] == pytest.approx(f["batch"]["economics"]["totals"]["profit_rp"]
                                            / f["batch"]["economics"]["totals"]["revenue_rp"] * 100, abs=0.01)
    assert k["energy_kwh"] == 60_000 and k["sec_kwh_per_ton"] == 150


def test_auditor_sees_same_plant_numbers_as_factory(world):
    assert world["report"]("auditor").json()["months"] == world["report"]("pabrik").json()["months"]


# ---------------------------------------------------------------- cakupan per peran
def test_farmer_sees_only_own_data(world):
    f = world["facts"]
    a = world["report"]("petani_a").json()
    b = world["report"]("petani_b").json()
    assert a["scope"]["label"] == "Data Anda sendiri" and len(a["columns"]) < 10
    ra, rb = row(a), row(b)
    assert ra["supply"]["verified_kg"] == 3500 and rb["supply"]["verified_kg"] == 1000
    assert ra["cost"]["income_rp"] == pytest.approx(f["paid"]["a"]) and rb["cost"]["income_rp"] == pytest.approx(f["paid"]["b"])
    assert ra["conversion"]["biochar_credited_kg"] == pytest.approx(f["wallet_a"])
    assert rb["supply"]["auction_sold_kg"] == 300 and ra["supply"]["auction_sold_kg"] == 0
    assert "cost_per_ton_input_rp" not in ra["cost"]                    # data pabrik tidak bocor ke petani


def test_collector_margin_and_volumes(world):
    f = world["facts"]
    r = row(world["report"]("pengepul").json())
    assert r["supply"]["bought_kg"] == 4500 and r["supply"]["sold_to_factory_kg"] == 3800 + 490
    assert r["supply"]["auction_won_kg"] == 300
    # celah ditutup: pembayaran jalur rute armada pabrik ikut terhitung
    assert f["route_settle"]["source"] == "rute" and f["route_settle"]["amount_rp"] > 0
    assert r["cost"]["received_from_factory_rp"] == pytest.approx(f["factory_paid"])
    assert r["cost"]["outstanding_rp"] == pytest.approx(f["factory_paid"])        # belum ada yang dibayar
    assert r["cost"]["gross_margin_rp"] == pytest.approx(f["factory_paid"] - (f["paid"]["a"] + f["paid"]["b"]))
    assert r["supply"]["shrinkage_pct"] == pytest.approx((4500 - 4290) / 4500 * 100, abs=0.01)


def test_driver_sees_only_trips(world):
    r = world["report"]("supir").json()
    m = row(r)
    assert m["supply"] == {"stops_completed": 1, "picked_kg": 500, "routes_completed": 1}
    assert set(m) == {"month", "supply", "cost"}


# ---------------------------------------------------------------- periode, CSV, validasi
def test_month_bucketing_uses_wib():
    assert month_of(datetime(2026, 10, 31, 18, 0, tzinfo=timezone.utc)) == "2026-11"
    assert month_of(datetime(2026, 10, 31, 16, 59)) == "2026-10"        # naif = UTC (SQLite)
    assert month_range("2025-11", "2026-02") == ["2025-11", "2025-12", "2026-01", "2026-02"]
    assert len(month_range(None, "2026-10")) == 12


@pytest.mark.parametrize("query,code", [("?from=2026-12&to=2026-01", 422), ("?from=2020-01&to=2026-10", 422),
                                        ("?from=2026-13", 422), ("?format=pdf", 422)])
def test_invalid_periods_rejected(world, query, code):
    assert world["report"]("pabrik", query).status_code == code


def test_empty_months_are_zero_not_missing(world):
    rep = world["report"]("pabrik", "?from=2026-01&to=2026-03").json()
    assert [m["month"] for m in rep["months"]] == ["2026-01", "2026-02", "2026-03"]
    assert rep["months"][0]["supply"]["factory_received_kg"] == 0
    assert rep["months"][0]["conversion"]["biochar_pct"] is None        # rasio tanpa penyebut = kosong, bukan 0


def test_csv_export_matches_json(world):
    r = world["report"]("pabrik", f"?from={NOW}&to={NOW}&format=csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    lines = r.text.lstrip("﻿").splitlines()
    assert lines[0].startswith("bulan,") and lines[1].startswith(NOW)
    assert len(lines[0].split(",")) == 1 + len(world["report"]("pabrik").json()["columns"])


def test_alias_and_v1_paths_equivalent(world):
    c, H = world["client"], world["H"]
    a = c.get(f"/api/reports/monthly?from={NOW}&to={NOW}", headers=H["pabrik"]).json()
    b = c.get(f"/api/v1/reports/monthly?from={NOW}&to={NOW}", headers=H["pabrik"]).json()
    assert a["months"] == b["months"] and c.get("/api/reports/monthly").status_code == 401
