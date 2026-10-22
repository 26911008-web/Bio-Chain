"""RBAC: tiap peran hanya bisa membuka modulnya sendiri (Fase 1 — IAM surgery)."""

import re

import pytest
from fastapi.testclient import TestClient

from app.dependencies import create_access_token
from app.main import app
from app.security.policy import LEGACY_MOVED, PUBLIC, policy_for
from tests.conftest import demo_headers

# Satu endpoint baca representatif per modul
MODULES = {
    "farmer":    ("GET", "/api/v1/farmer/harvests"),
    "collector": ("GET", "/api/v1/collector/available-harvests"),
    "driver":    ("GET", "/api/v1/driver/active-route"),
    "factory":   ("GET", "/api/v1/factory/esg/summary"),
    "labs":      ("GET", "/api/v1/labs/blend/defaults"),
    "jobs":      ("GET", "/api/v1/jobs/contoh"),
    "auditor":   ("GET", "/api/v1/auditor/summary"),
    "admin":     ("GET", "/api/v1/admin/stats"),
}
ALLOWED = {
    "petani":   {"farmer"},
    "pengepul": {"collector"},
    "driver":   {"driver"},
    "pabrik":   {"factory", "labs", "jobs"},
    "auditor":  {"auditor"},
    "admin":    {"factory", "labs", "jobs", "auditor", "admin"},
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_every_api_route_has_an_explicit_policy():
    missing = []
    for route in app.routes:
        path = getattr(route, "path", "")
        if path.startswith("/api/"):
            concrete = re.sub(r"\{[^}]+\}", "1", path)
            if policy_for(concrete) is None:
                missing.append(path)
    assert not missing, f"Rute tanpa kebijakan akses (akan ditolak 403): {missing}"


@pytest.mark.parametrize("role", list(ALLOWED))
@pytest.mark.parametrize("module", list(MODULES))
def test_role_module_matrix(client, role, module):
    method, path = MODULES[module]
    status = client.request(method, path, headers=demo_headers(client, role)).status_code
    if module in ALLOWED[role]:
        assert status not in (401, 403), f"{role} seharusnya boleh membuka {module} (dapat {status})"
    else:
        assert status == 403, f"{role} TIDAK boleh membuka {module} (dapat {status})"


@pytest.mark.parametrize("path", ["/api/v1/labs/quality/yield-curve", "/api/v1/factory/esg/summary",
                                  "/api/v1/jobs/x", "/api/v1/farmer/harvests"])
def test_anonymous_is_401(client, path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("old,new", list(LEGACY_MOVED.items()))
def test_legacy_public_lab_paths_are_gone(client, old, new):
    r = client.post(old, json={})
    assert r.status_code == 410 and r.json()["location"] == new


def test_unregistered_api_path_is_denied_by_default(client):
    r = client.get("/api/v1/rahasia/baru", headers=demo_headers(client, "admin"))
    assert r.status_code == 403


def test_public_endpoints_stay_public(client):
    assert policy_for("/api/v1/auth/demo-accounts") is PUBLIC
    assert client.get("/api/v1/auth/demo-accounts").status_code == 200
    assert client.get("/api/v1/system/status").status_code == 200


@pytest.mark.parametrize("gate,ok", [("petani", True), ("pabrik", False), ("driver", False)])
def test_login_gate_must_match_account_role(client, gate, ok):
    r = client.post("/api/v1/auth/login",
                    json={"identifier": "petani_sugeng", "password": "sekam123", "expected_role": gate})
    assert (r.status_code == 200) is ok
    if not ok:
        assert r.status_code == 403


def test_forged_role_claim_is_rejected(client):
    """Token petani yang klaim role-nya dipalsukan jadi 'pabrik' lolos prefix, tapi ditolak cek DB."""
    me = client.get("/api/v1/auth/me", headers=demo_headers(client, "petani")).json()
    forged = {"Authorization": f"Bearer {create_access_token(me['user_id'], 'pabrik')}"}
    assert client.get("/api/v1/labs/blend/defaults", headers=forged).status_code == 401


@pytest.mark.parametrize("role", ["petani", "driver", "pengepul", "pabrik", "auditor"])
def test_only_admin_can_wipe_demo_data(client, role):
    assert client.post("/api/v1/auth/reset-demo", headers=demo_headers(client, role)).status_code == 403


def test_cors_preflight_is_not_blocked(client):
    r = client.options("/api/v1/farmer/harvests", headers={
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert r.status_code == 200
