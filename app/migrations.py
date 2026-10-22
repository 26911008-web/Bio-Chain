"""Migrasi skema ringan & idempoten (tanpa Alembic).

`Base.metadata.create_all` membuat tabel baru tetapi tidak menambah kolom ke tabel lama, sehingga
`biochain.db` / PostgreSQL yang sudah ada perlu ALTER TABLE. Versi SQL murni untuk DBA:
migrations/002_circular_mass_balance.sql.
"""

from sqlalchemy import inspect, text

# (tabel, kolom, DDL tipe portabel SQLite & PostgreSQL)
ADDED_COLUMNS = [
    # 018 multi-biomassa (FK hanya di PG/DB baru; SQLite lama: divalidasi aplikasi)
    ("harvests", "commodity", "VARCHAR(24) NOT NULL DEFAULT 'sekam_padi'"),
    ("stock_listings", "commodity", "VARCHAR(24) NOT NULL DEFAULT 'sekam_padi'"),
    ("biomass_parameters", "base_price_per_kg", "DOUBLE PRECISION"),
    ("harvests", "verified_kg", "DOUBLE PRECISION"),
    ("harvests", "picked_up_kg", "DOUBLE PRECISION"),
    ("harvests", "received_kg", "DOUBLE PRECISION"),
    ("harvests", "shrinkage_kg", "DOUBLE PRECISION"),
    ("harvests", "shrinkage_pct", "DOUBLE PRECISION"),
    ("harvests", "discrepancy_flag", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("harvests", "discrepancy_note", "TEXT"),
    ("harvests", "rejected_reason", "TEXT"),
    ("harvests", "rejected_at", "TIMESTAMP WITH TIME ZONE"),
    ("harvests", "received_by_id", "INTEGER REFERENCES users(id)"),
    ("harvests", "conversion_id", "INTEGER REFERENCES conversions(id)"),
    ("harvests", "version", "INTEGER NOT NULL DEFAULT 1"),
    ("conversions", "farmer_return_share", "DOUBLE PRECISION"),
    ("conversions", "allocated_biochar_kg", "DOUBLE PRECISION"),
    ("energy_readings", "building_kwh", "DOUBLE PRECISION"),
    ("harvests", "listing_id", "INTEGER REFERENCES stock_listings(id)"),
    ("harvests", "bid_id", "INTEGER REFERENCES bids(id)"),
    ("harvests", "agreed_price_per_kg", "DOUBLE PRECISION"),
    ("harvests", "delivery_scheme", "VARCHAR(10)"),
    ("custody_events", "verification_code", "VARCHAR(40)"),
    ("custody_events", "sender_id", "INTEGER REFERENCES users(id)"),
    ("custody_events", "receiver_id", "INTEGER REFERENCES users(id)"),
    ("custody_events", "evidence_photo_url", "TEXT"),
    ("harvests", "delivery_request_id", "INTEGER REFERENCES delivery_requests(id)"),
    ("biochar_ledger", "batch_id", "INTEGER REFERENCES manufacturing_batches(id)"),
    ("manufacturing_batches", "silica_route", "VARCHAR(16) NOT NULL DEFAULT 'biochar'"),
    ("manufacturing_batches", "silica_husk_share", "DOUBLE PRECISION NOT NULL DEFAULT 0"),
    ("bids", "farmer_id", "INTEGER REFERENCES users(id)"),
    # 013 — pembatalan rute, stop gagal, jejak GPS & emisi, retur, BOM multi-output
    ("route_stops", "stop_status", "VARCHAR(12) NOT NULL DEFAULT 'pending'"),
    ("route_stops", "fail_reason", "VARCHAR(30)"),
    ("route_stops", "fail_note", "TEXT"),
    ("route_stops", "failed_at", "TIMESTAMP WITH TIME ZONE"),
    ("routes", "optimizer", "VARCHAR(40)"),
    ("routes", "actual_km", "DOUBLE PRECISION"),
    ("routes", "fuel_l", "DOUBLE PRECISION"),
    ("routes", "co2e_wtw_kg", "DOUBLE PRECISION"),
    ("routes", "co2e_per_ton_kg", "DOUBLE PRECISION"),
    ("routes", "emission_detail", "JSON"),
    ("routes", "cancel_reason", "TEXT"),
    ("routes", "cancelled_by_id", "INTEGER REFERENCES users(id)"),
    ("routes", "cancelled_at", "TIMESTAMP WITH TIME ZONE"),
    ("inbound_qc", "rejected_kg", "DOUBLE PRECISION NOT NULL DEFAULT 0"),
    ("batch_outputs", "expected_kg", "DOUBLE PRECISION"),
    ("batch_outputs", "yield_pct", "DOUBLE PRECISION"),
    ("batch_outputs", "yield_variance_pct", "DOUBLE PRECISION"),
    # 014 — kepatuhan lapangan: wajib ganti password (F6), petani tanpa HP (F7), anonimisasi PDP (F12)
    ("users", "must_change_password", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("users", "managed_by_id", "INTEGER REFERENCES users(id)"),
    ("users", "anonymized_at", "TIMESTAMP WITH TIME ZONE"),
    # 015 — taksiran petani opsional, kategori tolak (defect rate), pengambilan biochar (tabel baru via create_all)
    ("harvests", "farmer_moisture_est", "DOUBLE PRECISION"),
    ("harvests", "farmer_grade_est", "VARCHAR(1)"),
    ("harvests", "reject_category", "VARCHAR(20)"),
    # 016 — pencabutan token, uang muka (DP), refraksi basis kering, dedup foto
    ("users", "token_version", "INTEGER NOT NULL DEFAULT 0"),
    ("farmer_payments", "dp_rp", "NUMERIC(14,0) NOT NULL DEFAULT 0"),
    ("inbound_qc", "refraction_kg", "DOUBLE PRECISION NOT NULL DEFAULT 0"),
    ("inbound_qc", "dry_basis_kg", "DOUBLE PRECISION"),
]


# Indeks hot-path (dari profil query load test). IF NOT EXISTS → idempoten.
ADDED_INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_harvests_status_reported ON harvests (status, reported_at)",
    "CREATE INDEX IF NOT EXISTS ix_harvests_farmer_reported ON harvests (farmer_id, reported_at)",
    "CREATE INDEX IF NOT EXISTS ix_route_stops_route_order ON route_stops (route_id, stop_order)",
    "CREATE INDEX IF NOT EXISTS ix_routes_driver_status ON routes (driver_id, status)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_custody_verification_code ON custody_events (verification_code)",
    # 013: indeks lama (semua stop) diganti indeks stop hidup → harvest dari stop gagal/batal bisa dijadwalkan ulang
    "DROP INDEX IF EXISTS uq_route_stops_harvest",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_route_stops_harvest_live ON route_stops (harvest_id) "
    "WHERE harvest_id IS NOT NULL AND stop_status IN ('pending', 'picked_up')",
]


def upgrade_schema(sync_conn) -> list[str]:
    """Tambahkan kolom yang belum ada. Dipanggil via `conn.run_sync(upgrade_schema)` setelah create_all."""
    insp = inspect(sync_conn)
    added = []
    for table, column, ddl in ADDED_COLUMNS:
        if column not in {c["name"] for c in insp.get_columns(table)}:
            sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
            added.append(f"{table}.{column}")
    # Data lama: stop yang sudah dipindai → picked_up (kolom baru default 'pending')
    sync_conn.execute(text("UPDATE route_stops SET stop_status = 'picked_up' "
                           "WHERE qr_scanned = TRUE AND stop_status = 'pending'"))
    dup = sync_conn.execute(text(
        "SELECT harvest_id FROM route_stops WHERE harvest_id IS NOT NULL AND stop_status IN ('pending', 'picked_up') "
        "GROUP BY harvest_id HAVING COUNT(*) > 1"
    )).first()
    for ddl in ADDED_INDEXES:
        if "uq_route_stops_harvest_live" in ddl and dup is not None:
            # Non-breaking: data lama ganda → jangan gagalkan startup; bereskan dulu (lihat migrations/README.md).
            print(f"⚠️  uq_route_stops_harvest_live dilewati: harvest_id {dup[0]} ada di >1 stop hidup.")
            continue
        sync_conn.execute(text(ddl))
    if sync_conn.dialect.name == "sqlite":
        _sqlite_refresh_checks(sync_conn, added)
    _seed_biomass(sync_conn, added)
    return added


def _seed_biomass(sync_conn, added: list[str]) -> None:
    """Isi master biomassa yang belum ada (DB baru/SQLite). Baris yang sudah ada — termasuk koreksi lab — tidak disentuh."""
    from .biomass_seed import BIOMASS_SEED
    try:
        with sync_conn.begin_nested():               # PG ber-RLS tanpa identitas operator → lewati, jangan gagalkan start
            _insert_missing_biomass(sync_conn, added, BIOMASS_SEED)
    except Exception as e:  # noqa: BLE001
        print(f"⚠️  seed biomass_parameters dilewati: {e.__class__.__name__}")


def _insert_missing_biomass(sync_conn, added, BIOMASS_SEED) -> None:
    have = {r[0] for r in sync_conn.execute(text("SELECT code FROM biomass_parameters"))}
    for row in BIOMASS_SEED:
        if row["code"] not in have:
            cols = ", ".join(row)
            sync_conn.execute(text(f"INSERT INTO biomass_parameters ({cols}, is_active, updated_at) "
                                   f"VALUES ({', '.join(':' + k for k in row)}, TRUE, CURRENT_TIMESTAMP)"), row)
            added.append(f"biomass_parameters:{row['code']}")


# SQLite tidak bisa ALTER CONSTRAINT; DB lama dari sebelum migrasi PG yang mengubah CHECK tetap memakai versi lama.
# (tabel, CHECK lama, CHECK baru, syarat data lama memenuhi CHECK baru)
SQLITE_CHECK_UPGRADES = [
    ("farmer_payments", "CHECK (net_rp = gross_rp - tax_rp)", "CHECK (net_rp = gross_rp - tax_rp - dp_rp)",
     "SELECT 1 FROM farmer_payments WHERE net_rp != gross_rp - tax_rp - COALESCE(dp_rp, 0) LIMIT 1"),   # 016
]


def _sqlite_refresh_checks(sync_conn, added: list[str]) -> None:
    """Ganti teks CHECK lama via writable_schema (prosedur resmi SQLite untuk perubahan tanpa ubah format disk)."""
    for table, old, new, violation_sql in SQLITE_CHECK_UPGRADES:
        row = sync_conn.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name=:t"),
                                {"t": table}).first()
        if row is None or old not in row[0] or new in row[0]:
            continue
        if sync_conn.execute(text(violation_sql)).first() is not None:
            print(f"⚠️  CHECK {table} tidak diperbarui: ada baris lama yang melanggar `{new}`.")
            continue
        version = sync_conn.execute(text("PRAGMA schema_version")).scalar()
        sync_conn.execute(text("PRAGMA writable_schema = ON"))
        sync_conn.execute(text("UPDATE sqlite_master SET sql = replace(sql, :old, :new) WHERE type='table' AND name=:t"),
                          {"old": old, "new": new, "t": table})
        sync_conn.execute(text(f"PRAGMA schema_version = {int(version) + 1}"))
        sync_conn.execute(text("PRAGMA writable_schema = OFF"))
        added.append(f"{table}:{new}")
