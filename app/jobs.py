"""Antrean job untuk komputasi berat — pola 202 Accepted + polling.

Request web hanya memvalidasi & memasukkan job (milidetik); perhitungan berjalan di worker, sehingga
lonjakan permintaan optimasi tidak memakan slot request/koneksi DB API.

Backend:
- ArqJobs   : Redis + worker terpisah (`arq app.worker.WorkerSettings`). Wajib bila API > 1 proses.
- LocalJobs : asyncio task + thread pool terbatas di proses API (dev / satu proses, tanpa Redis).
- InlineJobs: serverless (Vercel) — dihitung di dalam request submit lalu langsung `done`, karena polling
              berikutnya bisa mendarat di instance lain yang tidak punya memori job tersebut.
`JOB_BACKEND=arq` harus diset eksplisit; port Redis yang kebetulan terbuka (bisa milik proyek lain)
tidak pernah dipakai otomatis. Antrean arq memakai nama ber-namespace (QUEUE_NAME).
"""

import time
import uuid
import asyncio
from typing import Any

from .concurrency import run_cpu
from .config import settings

JOB_TTL_S = 3600
QUEUE_NAME = f"{settings.REDIS_KEY_PREFIX}arq:queue"


# ---------------------------------------------------------------- handler (murni, dapat di-pickle)
def route_optimize_job(payload: dict) -> dict:
    from .engines.routing import plan_routes
    from .schemas.routing import RouteRequest
    return plan_routes(payload["depot"], payload["mills"], RouteRequest(**payload["request"]))


HANDLERS = {"route_optimize": route_optimize_job}


def _public_error(exc: Exception) -> str:
    from .engines.routing import SolverLimitError
    if isinstance(exc, (SolverLimitError, ValueError, ZeroDivisionError)):
        return str(exc)
    return "Perhitungan gagal di worker; silakan ulangi."


# ---------------------------------------------------------------- backend lokal
class LocalJobs:
    name = "local"

    def __init__(self):
        self._jobs: dict[str, dict[str, Any]] = {}
        self._tasks: set[asyncio.Task] = set()

    async def submit(self, kind: str, payload: dict) -> str:
        self._gc()
        job_id = uuid.uuid4().hex
        self._jobs[job_id] = {"job_id": job_id, "kind": kind, "status": "queued", "created_at": time.time()}
        task = asyncio.create_task(self._run(job_id, kind, payload))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job_id

    async def _run(self, job_id: str, kind: str, payload: dict):
        job = self._jobs[job_id]
        job.update(status="running", started_at=time.time())
        try:
            job["result"] = await run_cpu(HANDLERS[kind], payload, queue_timeout_s=60)
            job["status"] = "done"
        except Exception as e:                       # job gagal tidak boleh menjatuhkan proses API
            job.update(status="failed", error=_public_error(e))
        job["finished_at"] = time.time()

    async def get(self, job_id: str) -> dict | None:
        return self._jobs.get(job_id)

    def _gc(self):
        cutoff = time.time() - JOB_TTL_S
        for jid in [j for j, v in self._jobs.items() if v.get("finished_at", time.time()) < cutoff]:
            del self._jobs[jid]


class InlineJobs(LocalJobs):
    name = "inline"

    async def submit(self, kind: str, payload: dict) -> str:
        self._gc()
        job_id = uuid.uuid4().hex
        self._jobs[job_id] = {"job_id": job_id, "kind": kind, "status": "queued", "created_at": time.time()}
        await self._run(job_id, kind, payload)
        return job_id


# ---------------------------------------------------------------- backend arq / Redis
class ArqJobs:
    name = "arq"

    def __init__(self, pool):
        self._pool = pool

    @classmethod
    async def connect(cls) -> "ArqJobs":
        from arq import create_pool
        from arq.connections import RedisSettings
        return cls(await create_pool(RedisSettings.from_dsn(settings.REDIS_URL)))

    async def submit(self, kind: str, payload: dict) -> str:
        job_id = uuid.uuid4().hex
        await self._pool.enqueue_job("run_job", kind, payload, _job_id=job_id, _queue_name=QUEUE_NAME)
        return job_id

    async def get(self, job_id: str) -> dict | None:
        from arq.jobs import Job, JobStatus
        job = Job(job_id, self._pool, _queue_name=QUEUE_NAME)
        status = await job.status()
        if status == JobStatus.not_found:
            return None
        out = {"job_id": job_id, "kind": "route_optimize"}
        if status in (JobStatus.deferred, JobStatus.queued):
            return {**out, "status": "queued"}
        if status == JobStatus.in_progress:
            return {**out, "status": "running"}
        info = await job.result_info()
        if info is None:
            return {**out, "status": "running"}
        if info.success:
            return {**out, "status": "done", "result": info.result}
        return {**out, "status": "failed", "error": _public_error(info.result)}


_backend: LocalJobs | InlineJobs | ArqJobs | None = None
_lock = asyncio.Lock()


async def get_job_backend() -> LocalJobs | InlineJobs | ArqJobs:
    """Dependency FastAPI: backend job tunggal per proses."""
    global _backend
    if _backend is None:
        async with _lock:
            if _backend is None:
                if settings.JOB_BACKEND == "arq":
                    _backend = await ArqJobs.connect()
                else:
                    _backend = InlineJobs() if settings.JOB_BACKEND == "inline" else LocalJobs()
    return _backend
