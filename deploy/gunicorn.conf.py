"""Gunicorn untuk produksi Linux:  gunicorn -c deploy/gunicorn.conf.py app.main:app

Load test menunjukkan satu proses Python mentok ~100 rps (≈10 ms CPU/request), jadi throughput
diskalakan dengan jumlah proses, bukan thread.
"""

import multiprocessing
import os

bind = os.getenv("BIND", "0.0.0.0:8000")
worker_class = "uvicorn.workers.UvicornWorker"
workers = int(os.getenv("WEB_CONCURRENCY", multiprocessing.cpu_count() * 2 + 1))
backlog = 4096                 # antrean accept TCP saat lonjakan (Linux: naikkan net.core.somaxconn)
keepalive = 5
timeout = 30                   # request > 30 s = macet → worker didaur ulang
graceful_timeout = 20
max_requests = 5000            # daur ulang berkala cegah kebocoran memori
max_requests_jitter = 500
forwarded_allow_ips = os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1")   # IP Nginx
preload_app = False            # tiap worker membuat pool DB sendiri (pool tidak aman di-fork)

# Anggaran koneksi: workers × (DB_POOL_SIZE + DB_MAX_OVERFLOW) harus ≤ default_pool_size PgBouncer.
