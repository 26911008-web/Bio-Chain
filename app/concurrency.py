"""Isolasi komputasi berat (CPU-bound) dari event loop.

`run_cpu` menjalankan fungsi sinkron di thread pool dengan kapasitas terbatas
(settings.CPU_HEAVY_CONCURRENCY). Kerja yang antre terlalu lama dibatalkan dengan `Overloaded`
→ HTTP 503 + Retry-After (load shedding), sehingga health check & request ringan tetap cepat.
hashlib.pbkdf2_hmac dan NumPy melepas GIL, jadi thread benar-benar paralel.
"""

import asyncio

import anyio
from anyio import to_thread

from .config import settings

_limiters: dict[int, anyio.CapacityLimiter] = {}


class Overloaded(Exception):
    """Antrean komputasi berat penuh; klien diminta mencoba lagi."""


def _limiter() -> anyio.CapacityLimiter:
    loop_id = id(asyncio.get_running_loop())          # satu limiter per event loop (aman untuk tes)
    lim = _limiters.get(loop_id)
    if lim is None:
        lim = _limiters[loop_id] = anyio.CapacityLimiter(settings.CPU_HEAVY_CONCURRENCY)
    return lim


async def run_cpu(fn, *args, queue_timeout_s: float = 10.0):
    lim = _limiter()
    try:
        with anyio.fail_after(queue_timeout_s):
            await lim.acquire()
    except TimeoutError as e:
        raise Overloaded("Server sedang sibuk menghitung; coba lagi sebentar.") from e
    try:
        return await to_thread.run_sync(fn, *args)
    finally:
        lim.release()
