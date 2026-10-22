"""Kebijakan akses berbasis prefix — lapisan RBAC pertama, deny-by-default.

Setiap request `/api/*` dicocokkan ke ROUTE_POLICY (prefix terpanjang menang) SEBELUM handler
berjalan. Path `/api/*` yang tidak terdaftar ditolak 403, sehingga endpoint baru yang lupa diberi
guard tidak otomatis menjadi publik. `require_role` di tiap router tetap berlaku sebagai lapisan
kedua (dan memeriksa status aktif user di DB; middleware ini hanya membaca klaim JWT).
"""

import json

import jwt

from ..config import settings
from ..models.user import UserRole as R

PUBLIC = frozenset({"*public*"})
ANY_USER = frozenset(r.value for r in R)


def _roles(*roles: R) -> frozenset[str]:
    return frozenset(r.value for r in roles)


ROUTE_POLICY: list[tuple[str, frozenset[str]]] = [
    ("/api/v1/system/status",      PUBLIC),
    ("/api/v1/auth/login",         PUBLIC),
    ("/api/v1/auth/register",      PUBLIC),
    ("/api/v1/auth/demo-accounts", PUBLIC),          # akun demo sengaja terbuka untuk semua penguji
    ("/api/v1/auth/me",            ANY_USER),
    ("/api/v1/assistant/",         ANY_USER),
    ("/api/v1/reports/",           ANY_USER),        # cakupan data dibatasi per peran di server
    ("/api/reports/",              ANY_USER),        # alias sesuai spesifikasi /api/reports/monthly
    ("/api/v1/params",             ANY_USER),        # baca: semua; ubah: Pabrik/Admin (require_role)
    ("/api/v1/params/",            ANY_USER),        # konteks data asisten dibatasi per peran di server
    ("/api/v1/auth/reset-demo",    _roles(R.ADMIN)),
    ("/api/v1/farmer/",            _roles(R.PETANI)),
    ("/api/v1/collector/",         _roles(R.PENGEPUL)),
    ("/api/v1/driver/",            _roles(R.DRIVER)),
    ("/api/v1/factory/",           _roles(R.PABRIK, R.ADMIN)),
    ("/api/v1/factory/mass-balance/", _roles(R.PABRIK, R.ADMIN, R.AUDITOR)),
    ("/api/v1/factory/energy/",    _roles(R.PABRIK, R.ADMIN, R.AUDITOR)),
    ("/api/v1/factory/batches",    _roles(R.PABRIK, R.ADMIN, R.AUDITOR)),    # tulis: khusus pabrik (require_role)
    ("/api/v1/factory/qc/lots",    _roles(R.PABRIK, R.ADMIN, R.AUDITOR)),
    ("/api/v1/factory/settlements", _roles(R.PABRIK, R.ADMIN, R.AUDITOR)),   # tulis: khusus pabrik (require_role)
    ("/api/v1/labs/",              _roles(R.PABRIK, R.ADMIN)),
    ("/api/v1/jobs/",              _roles(R.PABRIK, R.ADMIN)),
    ("/api/v1/auditor/",           _roles(R.AUDITOR, R.ADMIN)),
    ("/api/v1/admin/",             _roles(R.ADMIN)),
]

# Endpoint lab lama yang dulu publik di root → 410 Gone + lokasi baru.
LEGACY_MOVED = {
    "/quality/score": "/api/v1/labs/quality/score",
    "/quality/yield-curve": "/api/v1/labs/quality/yield-curve",
    "/blend/defaults": "/api/v1/labs/blend/defaults",
    "/blend/recommend": "/api/v1/labs/blend/recommend",
    "/supply/mills": "/api/v1/labs/supply/mills",
    "/routes/optimize": "/api/v1/labs/routes/optimize",
    "/carbon/calculate": "/api/v1/labs/carbon/calculate",
    "/forecast/supply": "/api/v1/labs/forecast/supply",
    "/incentive/calculate": "/api/v1/labs/incentive/calculate",
}


def policy_for(path: str) -> frozenset[str] | None:
    """Peran yang boleh mengakses `path`; None = tidak terdaftar (ditolak)."""
    best = None
    for prefix, roles in ROUTE_POLICY:
        exact = not prefix.endswith("/")
        if (path == prefix if exact else path.startswith(prefix)) and (best is None or len(prefix) > len(best[0])):
            best = (prefix, roles)
    return best[1] if best else None


def role_from_token(auth_header: str | None) -> str | None:
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return None
    try:
        payload = jwt.decode(auth_header[7:], settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload.get("role")
    except jwt.PyJWTError:
        return None


class RoutePolicyMiddleware:
    """ASGI murni (tanpa BaseHTTPMiddleware) agar overhead per request minimal."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] == "OPTIONS":   # preflight CORS tanpa token
            return await self.app(scope, receive, send)
        path = scope["path"]

        if path in LEGACY_MOVED:
            return await _json(send, 410, {"detail": "Endpoint dipindah dan kini memerlukan login Pabrik/Admin.",
                                           "location": LEGACY_MOVED[path]})
        if not path.startswith("/api/"):
            return await self.app(scope, receive, send)

        allowed = policy_for(path)
        if allowed is None:
            return await _json(send, 403, {"detail": "Endpoint tidak terdaftar di kebijakan akses."})
        if allowed is PUBLIC:
            return await self.app(scope, receive, send)

        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        role = role_from_token(headers.get("authorization"))
        if role is None:
            return await _json(send, 401, {"detail": "Token diperlukan"})
        if role not in allowed:
            return await _json(send, 403, {"detail": f"Akses ditolak untuk peran '{role}'."})
        return await self.app(scope, receive, send)


async def _json(send, status: int, body: dict):
    data = json.dumps(body).encode()
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(data)).encode())]})
    await send({"type": "http.response.body", "body": data})
