"""Bio-Chain v2 — Centralized configuration via Pydantic BaseSettings.

Membaca dari .env file atau environment variables.
"""

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
    AUTO_MIGRATE: bool = True               # False di produksi: skema via migrations/*.sql oleh DBA (peran app tanpa DDL)
    PGBOUNCER: bool = False                 # True → nonaktifkan prepared-statement cache asyncpg

    # Redis
    REDIS_URL: str = "redis://localhost:6381/0"
    JOB_BACKEND: str = "local"              # local | arq. arq wajib diset eksplisit (tidak menebak dari port terbuka)
    REDIS_KEY_PREFIX: str = "biochain:"     # semua kunci Redis Bio-Chain ber-namespace (aman berbagi Redis)

    # Auth
    JWT_SECRET: str = "biochain-dev-secret-change-in-production-2026"
    JWT_ALGORITHM: str = "HS256"
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
    AI_DEFAULT_PROVIDER: str = "auto"       # auto | ollama | gemini | mistral | groq | openrouter
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
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = ""              # kosong → pilih model ':free' di UI

    # App
    APP_NAME: str = "Bio-Chain API"
    DEBUG: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
