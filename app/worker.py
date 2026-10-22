"""Worker arq untuk job berat. Jalankan terpisah dari API:

    arq app.worker.WorkerSettings

Skala horizontal: tambah proses worker (tiap proses memproses `max_jobs` job paralel di thread).
"""

import asyncio

from arq.connections import RedisSettings

from .config import settings
from .jobs import HANDLERS, QUEUE_NAME


async def run_job(ctx, kind: str, payload: dict):
    # Komputasi di thread agar heartbeat/health worker tetap berjalan selama job panjang.
    return await asyncio.to_thread(HANDLERS[kind], payload)


class WorkerSettings:
    functions = [run_job]
    queue_name = QUEUE_NAME
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = settings.CPU_HEAVY_CONCURRENCY
    job_timeout = 60
    keep_result = 3600
    max_tries = 1          # hasil deterministik; gagal = laporkan, bukan ulang diam-diam
