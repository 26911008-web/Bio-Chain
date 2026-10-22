"""Uji khusus PostgreSQL (dilewati bila DATABASE_URL bukan PostgreSQL).

Dijalankan sebagai peran aplikasi `biochain_app` (NOSUPERUSER, NOBYPASSRLS) agar membuktikan bahwa
RLS (migrasi 004/005/007), trigger append-only (002/006/007), CHECK constraint, dan generator resi atomik
benar-benar bekerja di mesin produksi — bukan hanya di SQLite.

    DATABASE_URL=postgresql+asyncpg://biochain_app:...@localhost:5433/biochain AUTO_MIGRATE=false py -m pytest tests/test_postgres.py
"""

import asyncio
import os

import pytest

URL = os.getenv("DATABASE_URL", "")
pytestmark = pytest.mark.skipif("postgresql" not in URL, reason="butuh DATABASE_URL PostgreSQL")

asyncpg = pytest.importorskip("asyncpg")
DSN = URL.replace("postgresql+asyncpg://", "postgresql://")


def run(coro):
    return asyncio.run(coro)


async def as_identity(conn, role: str, uid: int = 0):
    await conn.execute("SELECT set_config('app.role', $1, true), set_config('app.user_id', $2, true)", role, str(uid))


async def _ids():
    c = await asyncpg.connect(DSN)
    try:
        rows = await c.fetch("SELECT id, username, role FROM users")
        return {r["username"]: r["id"] for r in rows}
    finally:
        await c.close()


@pytest.fixture(scope="module")
def ids():
    """Pastikan app pernah start (seed) — users tidak ber-RLS."""
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app):
        pass
    return run(_ids())


def test_connected_as_non_superuser_without_bypassrls():
    async def go():
        c = await asyncpg.connect(DSN)
        try:
            return await c.fetchrow("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        finally:
            await c.close()
    r = run(go())
    assert r["rolsuper"] is False and r["rolbypassrls"] is False


def test_rls_farmer_sees_only_own_rows_and_no_identity_sees_nothing(ids):
    async def go():
        c = await asyncpg.connect(DSN)
        try:
            async with c.transaction():
                await as_identity(c, "system")
                other = ids["petani_sari"]
                await c.execute("INSERT INTO harvests (uuid, farmer_id, quantity_kg, status, qr_code, contamination, "
                                "incentive_multiplier, discrepancy_flag, version) VALUES "
                                "(gen_random_uuid()::text, $1, 123, 'reported', 'RLS-TEST-1', 0, 1, false, 1)", other)
                total = await c.fetchval("SELECT count(*) FROM harvests")
                await as_identity(c, "petani", ids["petani_sugeng"])
                own = await c.fetchval("SELECT count(*) FROM harvests WHERE farmer_id <> $1", ids["petani_sugeng"])
                await as_identity(c, "", 0)
                anon = await c.fetchval("SELECT count(*) FROM harvests")
                await as_identity(c, "auditor", ids["auditor_esg"])
                audit = await c.fetchval("SELECT count(*) FROM harvests")
                raise asyncpg.exceptions.UniqueViolationError("rollback")   # batalkan data uji
        except asyncpg.exceptions.UniqueViolationError:
            return total, own, anon, audit
        finally:
            await c.close()
    total, own, anon, audit = run(go())
    assert total >= 1 and own == 0 and anon == 0 and audit == total


def test_rls_blocks_farmer_from_crediting_own_wallet(ids):
    async def go():
        c = await asyncpg.connect(DSN)
        try:
            async with c.transaction():
                await as_identity(c, "petani", ids["petani_sugeng"])
                await c.execute("INSERT INTO biochar_ledger (farmer_id, entry_type, amount_kg, created_by_id) "
                                "VALUES ($1, 'allocation', 1000, $1)", ids["petani_sugeng"])
        finally:
            await c.close()
    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):      # new row violates row-level security
        run(go())


@pytest.mark.parametrize("sql", [
    "UPDATE custody_events SET note = 'diubah' WHERE id = (SELECT min(id) FROM custody_events)",
    "DELETE FROM parameter_changes WHERE id = (SELECT min(id) FROM parameter_changes)",
])
def test_audit_tables_are_append_only(ids, sql):
    async def go():
        c = await asyncpg.connect(DSN)
        try:
            async with c.transaction():
                await as_identity(c, "system")
                # pastikan ada baris yang akan disentuh
                await c.execute("INSERT INTO parameter_changes (key, old_value, new_value, changed_by_id, changed_by_role, "
                                "reason) VALUES ('uji', '1', '2', $1, 'admin', 'uji append-only')", ids["admin"])
                hid = await c.fetchval("SELECT min(id) FROM harvests")
                await c.execute("INSERT INTO custody_events (harvest_id, stage, to_status, actor_id, actor_role) "
                                "VALUES ($1, 'uji', 'reported', $2, 'system')", hid, ids["admin"])
                await c.execute(sql)
        finally:
            await c.close()
    with pytest.raises(asyncpg.exceptions.RaiseError, match="append-only"):
        run(go())


def test_check_constraint_delivered_requires_factory_weight(ids):
    async def go():
        c = await asyncpg.connect(DSN)
        try:
            async with c.transaction():
                await as_identity(c, "system")
                await c.execute("INSERT INTO harvests (uuid, farmer_id, quantity_kg, status, qr_code, contamination, "
                                "incentive_multiplier, discrepancy_flag, version) VALUES "
                                "(gen_random_uuid()::text, $1, 10, 'delivered', 'CK-TEST', 0, 1, false, 1)",
                                ids["petani_sugeng"])
        finally:
            await c.close()
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        run(go())


def test_no_infinite_recursion_between_market_policies(ids):
    """stock_listings ↔ bids saling merujuk dalam kebijakan RLS — harus tetap bisa di-query semua peran."""
    async def go():
        c = await asyncpg.connect(DSN)
        try:
            out = {}
            for role, uid in (("petani", ids["petani_sugeng"]), ("pengepul", ids["pengepul_sleman"]),
                              ("pabrik", ids["pabrik_indmira"]), ("auditor", ids["auditor_esg"])):
                async with c.transaction():
                    await as_identity(c, role, uid)
                    out[role] = (await c.fetchval("SELECT count(*) FROM stock_listings"),
                                 await c.fetchval("SELECT count(*) FROM bids"),
                                 await c.fetchval("SELECT count(*) FROM delivery_requests"),
                                 await c.fetchval("SELECT count(*) FROM harvests"))
            return out
        finally:
            await c.close()
    out = run(go())
    assert set(out) == {"petani", "pengepul", "pabrik", "auditor"}


def test_trx_sequence_atomic_under_real_concurrency():
    """60 transaksi serentak di koneksi terpisah → 60 nomor unik berurutan tanpa celah (row lock UPSERT)."""
    async def one(i):
        c = await asyncpg.connect(DSN)
        try:
            return await c.fetchval("SELECT next_trx_seq('PTN9999', 'PGP9999', '9912')")
        finally:
            await c.close()

    async def go():
        c = await asyncpg.connect(DSN)
        await c.execute("DELETE FROM trx_sequences WHERE yymm = '9912'")
        await c.close()
        return await asyncio.gather(*[one(i) for i in range(60)])
    assert sorted(run(go())) == list(range(1, 61))


def test_pengepul_sees_only_own_delivery_requests(ids):
    async def go():
        c = await asyncpg.connect(DSN)
        try:
            async with c.transaction():
                await as_identity(c, "system")
                await c.execute("INSERT INTO delivery_requests (collector_id, quantity_kg, moisture_est, proposed_date, "
                                "proposed_price_per_kg, status, rounds, version) VALUES ($1, 100, 11, '2026-10-20', 400, "
                                "'submitted', 0, 1)", ids["pabrik_indmira"])      # milik "orang lain"
                await as_identity(c, "pengepul", ids["pengepul_sleman"])
                foreign = await c.fetchval("SELECT count(*) FROM delivery_requests WHERE collector_id <> $1",
                                           ids["pengepul_sleman"])
                raise asyncpg.exceptions.UniqueViolationError("rollback")
        except asyncpg.exceptions.UniqueViolationError:
            return foreign
        finally:
            await c.close()
    assert run(go()) == 0


def test_warehouse_views_match_report_api(ids):
    """Dua implementasi independen (Python API vs view SQL) harus menghasilkan angka bulanan yang sama."""
    from fastapi.testclient import TestClient
    from app.main import app
    from tests.conftest import demo_headers
    with TestClient(app) as c:
        rep = c.get("/api/reports/monthly", headers=demo_headers(c, "pabrik")).json()
    months = [m["month"] for m in rep["months"]]

    async def go():
        conn = await asyncpg.connect(DSN)
        try:
            async with conn.transaction():
                await as_identity(conn, "pabrik", ids["pabrik_indmira"])
                sup = {r["month"]: r for r in await conn.fetch("SELECT * FROM wh_monthly_supply WHERE month = ANY($1)", months)}
                cost = {r["month"]: r for r in await conn.fetch("SELECT * FROM wh_monthly_cost WHERE month = ANY($1)", months)}
            return sup, cost
        finally:
            await conn.close()
    sup, cost = run(go())
    for m in rep["months"]:
        v = sup.get(m["month"])
        for api_key, view_key in (("reported_kg", "reported_kg"), ("collector_verified_kg", "collector_verified_kg"),
                                  ("factory_received_kg", "factory_received_kg"), ("rejected_kg", "rejected_kg")):
            assert m["supply"][api_key] == pytest.approx(float(v[view_key]) if v else 0, abs=0.01), (m["month"], api_key)
        k = cost.get(m["month"])
        assert m["cost"]["energy_kwh"] == pytest.approx(float(k["energy_kwh"] or 0) if k else 0, abs=0.01)
        assert m["cost"]["raw_material_rp"] == pytest.approx(float(k["raw_material_rp"] or 0) if k else 0, abs=0.01)
        assert m["cost"]["unpriced_kg"] == pytest.approx(float(k["unpriced_kg"] or 0) if k else 0, abs=0.01)


def test_warehouse_views_respect_rls_via_security_invoker(ids):
    async def go():
        conn = await asyncpg.connect(DSN)
        try:
            async with conn.transaction():
                await as_identity(conn, "pabrik", ids["pabrik_indmira"])
                plant = await conn.fetchval("SELECT coalesce(sum(reported_kg), 0) FROM wh_monthly_supply")
                await as_identity(conn, "petani", ids["petani_sari"])          # petani demo tanpa harvest
                other = await conn.fetchval("SELECT coalesce(sum(reported_kg), 0) FROM wh_monthly_supply")
                await as_identity(conn, "", 0)
                anon = await conn.fetchval("SELECT coalesce(sum(reported_kg), 0) FROM wh_monthly_supply")
            return plant, other, anon
        finally:
            await conn.close()
    plant, other, anon = run(go())
    assert plant > 0 and other == 0 and anon == 0


def test_settlements_rls_collector_reads_own_only_and_cannot_write(ids):
    """Pengepul tidak boleh membuat/menaikkan tagihannya sendiri; hanya membaca miliknya."""
    async def go():
        c = await asyncpg.connect(DSN)
        try:
            async with c.transaction():
                await as_identity(c, "system")
                hid = await c.fetchval("INSERT INTO harvests (uuid, farmer_id, quantity_kg, status, qr_code, contamination, "
                                       "incentive_multiplier, discrepancy_flag, version) VALUES (gen_random_uuid()::text, "
                                       "$1, 10, 'reported', 'CS-RLS', 0, 1, false, 1) RETURNING id", ids["petani_sugeng"])
                await c.execute("INSERT INTO collector_settlements (collector_id, source, harvest_id, payable_kg, price_per_kg, "
                                "amount_rp, status, created_by_id) VALUES ($1, 'rute', $2, 10, 500, 5000, 'terutang', $3)",
                                ids["pabrik_indmira"], hid, ids["pabrik_indmira"])         # milik "orang lain"
                await as_identity(c, "pengepul", ids["pengepul_sleman"])
                foreign = await c.fetchval("SELECT count(*) FROM collector_settlements WHERE collector_id <> $1",
                                           ids["pengepul_sleman"])
                updated = await c.execute("UPDATE collector_settlements SET amount_rp = 1e9")
                await as_identity(c, "auditor", ids["auditor_esg"])
                audit = await c.fetchval("SELECT count(*) FROM collector_settlements WHERE harvest_id = $1", hid)
                raise asyncpg.exceptions.UniqueViolationError("rollback")
        except asyncpg.exceptions.UniqueViolationError:
            return foreign, updated, audit
        finally:
            await c.close()
    foreign, updated, audit = run(go())
    assert foreign == 0 and updated == "UPDATE 0" and audit == 1


def test_settlement_priced_status_is_enforced_by_check(ids):
    async def go():
        c = await asyncpg.connect(DSN)
        try:
            async with c.transaction():
                await as_identity(c, "system")
                hid = await c.fetchval("SELECT min(id) FROM harvests")
                await c.execute("INSERT INTO collector_settlements (collector_id, source, harvest_id, payable_kg, amount_rp, "
                                "status, created_by_id) VALUES ($1, 'rute', $2, 10, NULL, 'terutang', $1)",
                                ids["pabrik_indmira"], hid)
        finally:
            await c.close()
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        run(go())


def test_twenty_concurrent_accepts_never_double_allocate(ids):
    """Chaos: 20 tawaran (100–300 kg, total 4.000 kg) atas SATU stok 1.000 kg diterima serentak lewat 20 koneksi
    terpisah memanggil public.accept_bid_atomic (SELECT … FOR UPDATE). Harus: Σ diterima ≤ 1.000 kg, sisa ≥ 0,
    tidak ada tawaran yang diterima dua kali, dan sisa stok = 1.000 − Σ diterima."""
    import random
    import uuid as _uuid
    farmer = ids["petani_sugeng"]

    async def setup():
        c = await asyncpg.connect(DSN)
        try:
            async with c.transaction():
                await as_identity(c, "system")
                tag = _uuid.uuid4().hex[:6]
                cols = []
                for i in range(20):
                    cid = await c.fetchval(
                        "INSERT INTO users (username, phone, password_hash, full_name, role, is_active, must_change_password,"
                        " token_version) VALUES ($1, $2, 'x', $3, 'pengepul', TRUE, FALSE, 0) RETURNING id",
                        f"race_{tag}_{i}", f"089{_uuid.uuid4().int % 10**9:09d}", f"Race {i}")
                    cols.append(cid)
                lid = await c.fetchval(
                    "INSERT INTO stock_listings (farmer_id, quantity_kg, remaining_kg, allow_jemput, allow_antar, status,"
                    " version, ask_price_jemput) VALUES ($1, 1000, 1000, TRUE, FALSE, 'open', 1, 400) RETURNING id", farmer)
                random.seed(7)
                bids = []
                for cid in cols:
                    q = float(random.choice([100, 150, 200, 250, 300]))
                    bid = await c.fetchval(
                        "INSERT INTO bids (listing_id, collector_id, farmer_id, scheme, price_per_kg, quantity_kg, accepted_kg, status, created_at)"
                        " VALUES ($1, $2, $3, 'jemput', 450, $4, 0, 'active', now()) RETURNING id", lid, cid, farmer, q)
                    bids.append((bid, q))
                return lid, bids
        finally:
            await c.close()

    async def accept(lid, bid, q):
        c = await asyncpg.connect(DSN)
        try:
            async with c.transaction():
                await as_identity(c, "petani", farmer)
                await c.fetchrow("SELECT * FROM public.accept_bid_atomic($1, $2, $3, $4)", lid, bid, farmer, q)
            return q
        except asyncpg.PostgresError:
            return 0.0                              # kalah balapan: stok tidak cukup / listing tertutup
        finally:
            await c.close()

    async def go():
        lid, bids = await setup()
        won = await asyncio.gather(*(accept(lid, b, q) for b, q in bids))
        c = await asyncpg.connect(DSN)
        try:
            async with c.transaction():
                await as_identity(c, "system")
                rem = await c.fetchval("SELECT remaining_kg FROM stock_listings WHERE id = $1", lid)
                acc = await c.fetch("SELECT id, accepted_kg FROM bids WHERE listing_id = $1 AND status = 'accepted'", lid)
        finally:
            await c.close()
        return won, rem, acc

    won, rem, acc = run(go())
    total = sum(won)
    assert total <= 1000 + 1e-6, f"alokasi ganda: {total} kg > stok 1000 kg"
    assert rem >= -1e-6 and abs(rem - (1000 - total)) < 1e-6
    assert abs(sum(r["accepted_kg"] for r in acc) - total) < 1e-6
    assert len(acc) == sum(1 for w in won if w > 0) and len(acc) >= 3     # sebagian menang, sisanya ditolak rapi
