"""Bio-Chain v2 — Centralized configuration via Pydantic BaseSettings.

Membaca dari .env file atau environment variables.
"""

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://biochain:biochain_dev_2026@localhost:5433/biochain"
    DATABASE_URL_SYNC: str = "postgresql://biochain:biochain_dev_2026@localhost:5433/biochain"
    ALLOW_SQLITE_FALLBACK: bool = True

    # Pool koneksi (per proses worker). Di produksi letakkan PgBouncer (transaction mode) di depan Postgres.
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT_S: float = 5.0          # gagal cepat → 503 + Retry-After, bukan antre 30 s
    DB_STATEMENT_TIMEOUT_MS: int = 5000     # PostgreSQL: batalkan query/lock yang menggantung
    SQLITE_POOL_SIZE: int = 1               # SQLite = 1 penulis; antre FIFO di pool > busy-wait antar koneksi
    DB_NULLPOOL: bool = False               # True khusus tes: tiap event loop membuka koneksinya sendiri (asyncpg)
    DB_POOL_WARMUP: int = 20                # buka N koneksi (≤ pool) saat start: p95 serbuan awal 1,7 s → ±1,0 s (docs/21)
    AUTO_MIGRATE: bool = True               # False di produksi: skema via migrations/*.sql oleh DBA (peran app tanpa DDL)
    PGBOUNCER: bool = False                 # True → nonaktifkan prepared-statement cache asyncpg

    # Redis
    REDIS_URL: str = "redis://localhost:6381/0"
    JOB_BACKEND: str = "local"              # local | arq. arq wajib diset eksplisit (tidak menebak dari port terbuka)
    REDIS_KEY_PREFIX: str = "biochain:"     # semua kunci Redis Bio-Chain ber-namespace (aman berbagi Redis)

    # Auth
    JWT_SECRET: str = "biochain-dev-secret-change-in-production-2026"
    JWT_ALGORITHM: str = "HS256"
    QR_HMAC_KEY: str = ""          # F14: kunci tanda tangan QR lot; kosong = diturunkan dari JWT_SECRET
    JWT_EXPIRE_MINUTES: int = 480  # 8 jam

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    LOGIN_RATE_LIMIT: int = 10              # percobaan login per IP per jendela (anti brute force)
    TRUSTED_PROXIES: str = "127.0.0.1"      # IP reverse proxy yang boleh mengisi X-Forwarded-For (koma)
    CPU_HEAVY_CONCURRENCY: int = 4          # komputasi berat (PBKDF2, optimasi rute) paralel maksimum

    # Ekonomi sirkular / mass balance
    SHRINKAGE_TOLERANCE_PCT: float = 5.0        # susut pengepul→pabrik di atas ini ditandai untuk audit
    ESTIMATE_TOLERANCE_PCT: float = 10.0        # selisih estimasi petani vs timbangan pengepul
    BIOCHAR_FARMER_RETURN_SHARE: float = 1.0    # porsi output batch yang dialokasikan ke dompet petani
    BASE_PRICE_PER_KG: float = 400.0            # Rp/kg sekam sebelum multiplier grade

    # Asisten AI — semua kunci hanya di server (.env), tidak pernah ke browser
    AI_DEFAULT_PROVIDER: str = "auto"       # auto | ollama | gemini | mistral | groq | openai | openrouter
    AI_TIMEOUT_S: float = 60.0              # jeda maksimum antar potongan teks (streaming)
    AI_MAX_TOKENS: int = 600
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:latest"   # ringan untuk CPU; qwen2.5:14b lebih baik bila ada GPU
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.8-flash"   # 2.5-flash ditutup untuk pengguna baru (cek /providers/gemini/models)
    MISTRAL_API_KEY: str = ""
    MISTRAL_MODEL: str = "mistral-small-latest"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-5-mini"        # cek GET /api/v1/assistant/providers/openai/models
    OPENAI_REASONING_EFFORT: str = "low"     # kosongkan untuk model non-reasoning (mis. gpt-4.1)
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = ""              # kosong → pilih model ':free' di UI

    # CORS — daftar origin dipisah koma (F19). Kosong + DEBUG → origin dev lokal. Produksi: isi domain HTTPS.
    CORS_ORIGINS: str = ""
    # Produksi multi-worker wajib arq+Redis (F16). Setel True HANYA untuk server satu worker.
    ALLOW_LOCAL_JOBS_IN_PROD: bool = False

    # App
    APP_NAME: str = "Bio-Chain API"
    DEBUG: bool = True
    # Mode demo (hackathon / laptop): akun demo publik, seed otomatis, reset data oleh admin.
    # WAJIB False saat dipakai di lapangan — kalau tidak, password admin demo terbuka di /auth/demo-accounts.
    DEMO_MODE: bool = True
    # Content-Security-Policy dari aplikasi (app/security/headers.py). Matikan hanya untuk debugging lokal.
    CSP_ENABLED: bool = True
    # Toleransi jam perangkat (HP murah sering salah jam). Waktu di luar jendela ini ditandai, bukan dipercaya.
    CLIENT_CLOCK_MAX_PAST_HOURS: float = 72.0
    CLIENT_CLOCK_MAX_FUTURE_MINUTES: float = 10.0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def _validate_secrets(self):
        if not self.DEBUG:
            if self.JWT_SECRET.startswith("biochain-dev-secret") or len(self.JWT_SECRET) < 32:
                raise ValueError("JWT_SECRET tidak aman untuk mode produksi (harus diubah dan minimal 32 karakter).")
            # Produksi lapangan: tidak boleh ada akun demo publik / reset data, dan tidak boleh diam-diam
            # pindah ke SQLite lokal (split-brain antar worker, RLS & trigger audit hilang).
            if self.DEMO_MODE:
                raise ValueError("DEMO_MODE harus False saat DEBUG=False (akun demo & reset data terbuka).")
            if self.ALLOW_SQLITE_FALLBACK and "sqlite" not in self.DATABASE_URL.lower():
                raise ValueError("ALLOW_SQLITE_FALLBACK harus False di produksi (cegah split-brain SQLite/PostgreSQL).")
            if self.JOB_BACKEND != "arq" and not self.ALLOW_LOCAL_JOBS_IN_PROD:
                raise ValueError("JOB_BACKEND=arq (+ REDIS_URL) wajib di produksi: job & antrean in-memory tidak terbagi "
                                 "antar worker. Untuk server satu worker setel ALLOW_LOCAL_JOBS_IN_PROD=true.")
            origins = self.cors_origins
            if not origins or "*" in origins:
                raise ValueError("CORS_ORIGINS wajib diisi domain HTTPS eksplisit di produksi (tanpa '*').")
            if any(o.startswith("http://") and "localhost" not in o and "127.0.0.1" not in o for o in origins):
                raise ValueError("CORS_ORIGINS produksi harus https:// (kamera QR, GPS & crypto.randomUUID butuh HTTPS).")
        return self

    @property
    def cors_origins(self) -> list[str]:
        if self.CORS_ORIGINS.strip():
            return [o.strip().rstrip("/") for o in self.CORS_ORIGINS.split(",") if o.strip()]
        if self.DEBUG:
            return ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000", "http://127.0.0.1:8000"]
        return []


settings = Settings()
