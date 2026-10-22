"""Observability (F17): log terstruktur + Request-ID.

- `LOG_FORMAT=json` (default saat DEBUG=false) → satu baris JSON per kejadian, siap dikirim ke Loki/ELK/
  CloudWatch; `text` untuk pengembangan.
- Setiap request mendapat `X-Request-ID` (diteruskan dari nginx/klien bila ada, selain itu dibuat) yang ikut di
  setiap baris log dan di header respons — petugas lapangan cukup menyebut ID ini saat melapor error.
- Log akses: method, path (tanpa query string — bisa memuat data pribadi), status, durasi ms, peran.
"""

import json
import logging
import os
import sys
import time
import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
_SKIP = {"/health", "/healthz", "/sw.js"}
_RESERVED = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S") + f".{int(record.msecs):03d}Z",
               "level": record.levelname, "logger": record.name, "msg": record.getMessage(),
               "request_id": request_id_var.get()}
        out.update({k: v for k, v in vars(record).items() if k not in _RESERVED and not k.startswith("_")})
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False, default=str)


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging(debug: bool) -> None:
    fmt = os.getenv("LOG_FORMAT", "text" if debug else "json").lower()
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_RequestIdFilter())
    handler.setFormatter(JsonFormatter() if fmt == "json" else
                         logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"))
    root = logging.getLogger("biochain")
    root.handlers[:] = [handler]
    root.setLevel(level)
    root.propagate = False


access_log = logging.getLogger("biochain.access")


class RequestIdMiddleware:
    """ASGI murni (aman untuk streaming): pasang X-Request-ID & catat log akses."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        incoming = dict(scope.get("headers") or []).get(b"x-request-id", b"").decode("latin-1")
        rid = incoming if 8 <= len(incoming) <= 64 and incoming.replace("-", "").isalnum() else uuid.uuid4().hex[:16]
        token = request_id_var.set(rid)
        started = time.perf_counter()
        status = {"code": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                message.setdefault("headers", [])
                message["headers"] = list(message["headers"]) + [(b"x-request-id", rid.encode())]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            path = scope.get("path", "")
            if path not in _SKIP and not path.startswith("/static/"):
                access_log.info("request", extra={"method": scope.get("method"), "path": path,
                                                  "status": status["code"],
                                                  "duration_ms": round((time.perf_counter() - started) * 1000, 1)})
            request_id_var.reset(token)
