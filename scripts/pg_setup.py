"""Bootstrap PostgreSQL Bio-Chain: skema dasar → migrasi 002–008 → peran aplikasi tanpa hak bypass RLS.

    py scripts/pg_setup.py                      # container docker "biochain-postgres", port 5433
    py scripts/pg_setup.py --reset              # HAPUS skema public lalu bangun ulang (khusus dev/test)

Migrasi dijalankan lewat psql di dalam container (sama persis dengan instruksi DBA di migrations/README.md),
sehingga perilaku seperti CREATE INDEX CONCURRENTLY (di luar transaksi) teruji apa adanya.
"""

import argparse
import asyncio
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CONTAINER = os.getenv("BIOCHAIN_PG_CONTAINER", "biochain-postgres")
OWNER_URL = os.getenv("BIOCHAIN_PG_OWNER_URL", "postgresql+asyncpg://biochain:biochain_dev_2026@localhost:5433/biochain")
MIGRATIONS = ["002_circular_mass_balance.sql", "003_concurrency_indexes.sql", "004_row_level_security.sql",
              "005_b2b_trade.sql", "006_system_parameters.sql", "007_factory_operations.sql",
              "008_silica_routes_wallet_link.sql", "009_fix_rls_recursion.sql", "010_reporting_warehouse.sql",
              "011_collector_settlements.sql", "012_settlement_events_and_constraints.sql", "013_field_ops_green_logistics.sql",
              "014_field_compliance.sql", "015_farmer_feedback_circular.sql", "016_audit_hardening.sql",
              "017_carbon_claims.sql", "018_multi_biomass_ash.sql", "019_energy_operation_logs.sql",
              "000_app_role.sql"]


def psql(sql_file: pathlib.Path | None = None, command: str | None = None) -> str:
    args = ["docker", "exec", "-i", CONTAINER, "psql", "-U", "biochain", "-d", "biochain", "-v", "ON_ERROR_STOP=1", "-q"]
    if command:
        args += ["-c", command]
    res = subprocess.run(args, input=sql_file.read_bytes() if sql_file else None, capture_output=True)
    if res.returncode != 0:
        raise SystemExit(f"psql gagal ({sql_file or command}):\n{res.stderr.decode(errors='replace')}")
    return res.stdout.decode(errors="replace")


async def create_base_schema():
    from sqlalchemy.ext.asyncio import create_async_engine
    from app import models  # noqa: F401
    from app.database import Base
    eng = create_async_engine(OWNER_URL)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await eng.dispose()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="drop & recreate schema public (dev/test)")
    a = ap.parse_args()
    if a.reset:
        psql(command="DROP SCHEMA public CASCADE; CREATE SCHEMA public AUTHORIZATION biochain;")
        print("• skema public dibuat ulang")
    asyncio.run(create_base_schema())
    print("• skema dasar (model) dibuat")
    for m in MIGRATIONS:
        psql(ROOT / "migrations" / m)
        print(f"• migrasi {m} OK")
    print(psql(command="SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'biochain_app'").strip())


if __name__ == "__main__":
    main()
