"""Tes lapisan high-availability: job asinkron, load shedding, isolasi CPU, IP klien di balik proxy."""

import asyncio
import time

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app import concurrency
from app.main import app
from app.middleware import rate_limiter


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _wait_job(client, pabrik, job_id, timeout_s=10):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        st = client.get(f"/api/v1/jobs/{job_id}", headers=pabrik).json()
        if st["status"] in {"done", "failed"}:
            return st
        time.sleep(0.05)
    raise AssertionError("job tidak selesai")


def test_route_job_is_accepted_immediately_and_matches_sync_result(client, pabrik):
    body = {"vehicle_m3": 30, "mode": "heuristic", "time_budget_ms": 50}
    client.post("/api/v1/jobs/routes/optimize", headers=pabrik, json=body)     # inisialisasi backend job (sekali per proses)
    t = time.perf_counter()
    r = client.post("/api/v1/jobs/routes/optimize", headers=pabrik, json=body)
    accept_ms = (time.perf_counter() - t) * 1000
    assert r.status_code == 202 and r.json()["status"] == "queued"
    # Mode tes PostgreSQL memakai NullPool: tiap request membuka koneksi baru (±150 ms handshake+SCRAM,
    # terukur). Produksi memakai pool sehingga biaya itu tidak ada.
    import app.database as dbm
    from app.config import settings
    limit = 200 + (400 if dbm.active_driver == "postgresql" and settings.DB_NULLPOOL else 0)
    assert accept_ms < limit, f"submit harus instan, {accept_ms:.0f} ms"

    st = _wait_job(client, pabrik, r.json()["job_id"])
    assert st["status"] == "done"
    sync = client.post("/api/v1/labs/routes/optimize", headers=pabrik, json=body).json()
    assert st["result"]["summary"]["mills"] == sync["summary"]["mills"]
    assert st["result"]["computation_details"]["mode_used"] == "heuristic"


def test_failed_job_reports_reason_without_crashing(client, pabrik):
    r = client.post("/api/v1/jobs/routes/optimize", headers=pabrik, json={"mode": "exact"})   # 36 titik > batas exact
    st = _wait_job(client, pabrik, r.json()["job_id"])
    assert st["status"] == "failed" and "exact" in st["error"]
    assert client.get("/health").status_code == 200


def test_unknown_job_is_404(client, pabrik):
    assert client.get("/api/v1/jobs/tidak-ada", headers=pabrik).status_code == 404


def test_event_loop_stays_responsive_during_login_storm(client):
    """PBKDF2 berjalan di thread pool: health check tidak ikut antre di belakang login."""
    async def scenario():
        import httpx
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            logins = [c.post("/api/v1/auth/login", json={"identifier": "petani_sugeng", "password": "sekam123"})
                      for _ in range(8)]
            tasks = [asyncio.create_task(x) for x in logins]
            await asyncio.sleep(0.05)
            t = time.perf_counter()
            health = await c.get("/health")
            health_ms = (time.perf_counter() - t) * 1000
            results = await asyncio.gather(*tasks)
            return health, health_ms, results

    health, health_ms, results = asyncio.run(scenario())
    assert health.status_code == 200
    assert health_ms < 250, f"health menunggu {health_ms:.0f} ms → event loop terblokir"
    assert all(r.status_code == 200 for r in results)


def test_cpu_queue_overflow_sheds_with_503(monkeypatch):
    async def scenario():
        monkeypatch.setattr(concurrency.settings, "CPU_HEAVY_CONCURRENCY", 1)
        concurrency._limiters.clear()
        hold = asyncio.create_task(concurrency.run_cpu(time.sleep, 0.5))
        await asyncio.sleep(0.05)
        with pytest.raises(concurrency.Overloaded):
            await concurrency.run_cpu(time.sleep, 0, queue_timeout_s=0.1)
        await hold
    asyncio.run(scenario())
    concurrency._limiters.clear()


def _req(peer, xff=None):
    headers = [(b"x-forwarded-for", xff.encode())] if xff else []
    return Request({"type": "http", "client": (peer, 1234), "headers": headers, "method": "GET", "path": "/"})


@pytest.mark.parametrize("peer,xff,expected", [
    ("127.0.0.1", "203.0.113.7", "203.0.113.7"),                 # lewat Nginx tepercaya
    ("127.0.0.1", "6.6.6.6, 203.0.113.7", "203.0.113.7"),        # entri kiri palsu diabaikan
    ("198.51.100.9", "1.2.3.4", "198.51.100.9"),                 # klien langsung tidak boleh menyamar
    ("127.0.0.1", None, "127.0.0.1"),
])
def test_client_ip_behind_trusted_proxy(peer, xff, expected):
    assert rate_limiter.client_ip(_req(peer, xff)) == expected


def test_job_backend_never_auto_selects_foreign_redis():
    """Regresi: dulu JOB_BACKEND=auto memakai Redis apa pun yang terbuka di 6379 (bisa milik proyek lain)."""
    from app.config import Settings
    assert Settings().JOB_BACKEND in ("local", "arq")
    assert Settings.model_fields["JOB_BACKEND"].default == "local"
    from app.jobs import QUEUE_NAME
    assert QUEUE_NAME.startswith("biochain:")
