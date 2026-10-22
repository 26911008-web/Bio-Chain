"""Header keamanan dari aplikasi — termasuk Content-Security-Policy TANPA 'unsafe-inline' untuk skrip.

Kenapa di aplikasi (bukan hanya nginx): hash importmap dihitung otomatis dari index.html saat start, sehingga CSP
tidak basi ketika file berubah; juga melindungi deployment tanpa nginx dan membuat uji e2e langsung menangkap
pelanggaran CSP. Semua logika halaman ada di /static/*.js; handler HTML memakai data-on* (lihat app.js).
style-src masih 'unsafe-inline' (atribut style & Leaflet) — risiko jauh lebih kecil daripada skrip.
Swagger (/docs, /redoc) dikecualikan karena memakai skrip inline bawaan FastAPI.
"""

import base64
import hashlib
import re
from pathlib import Path

CDN_SCRIPTS = "https://cdnjs.cloudflare.com https://cdn.jsdelivr.net"
EXEMPT_PREFIXES = ("/docs", "/redoc", "/openapi.json")


def _inline_script_hashes(index_html: Path) -> list[str]:
    try:
        html = index_html.read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for body in re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S):
        out.append("'sha256-" + base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode() + "'")
    return out


def build_csp(index_html: Path) -> str:
    hashes = " ".join(_inline_script_hashes(index_html))
    return "; ".join([
        "default-src 'self'",
        f"script-src 'self' {CDN_SCRIPTS} {hashes}".strip(),
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data: blob: https://*.tile.openstreetmap.org",
        "connect-src 'self'",
        "worker-src 'self'",
        "media-src 'self' blob:",
        "frame-ancestors 'self'",
        "base-uri 'self'",
        "form-action 'self'",
        "object-src 'none'",
    ])


class SecurityHeadersMiddleware:
    """ASGI murni (tanpa BaseHTTPMiddleware) agar streaming jawaban AI tidak di-buffer."""

    def __init__(self, app, index_html: Path):
        self.app = app
        self.csp = build_csp(index_html).encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path", "").startswith(EXEMPT_PREFIXES):
            return await self.app(scope, receive, send)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                names = {k.lower() for k, _ in headers}
                for k, v in ((b"content-security-policy", self.csp), (b"x-content-type-options", b"nosniff"),
                             (b"referrer-policy", b"strict-origin-when-cross-origin"),
                             (b"x-frame-options", b"SAMEORIGIN")):
                    if k not in names:
                        headers.append((k, v))
                message["headers"] = headers
            await send(message)

        return await self.app(scope, receive, send_wrapper)
