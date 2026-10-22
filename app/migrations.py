"""Migrasi skema ringan & idempoten (tanpa Alembic).

`Base.metadata.create_all` membuat tabel baru tetapi tidak menambah kolom ke tabel lama, sehingga
`biochain.db` / PostgreSQL yang sudah ada perlu ALTER TABLE. Versi SQL murni untuk DBA:
migrations/002_circular_mass_balance.sql.
"""

from sqlalchemy import inspect, text

# (tabel, kolom, DDL tipe portabel SQLite & PostgreSQL)
ADDED_COLUMNS = [
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
]


# Indeks hot-path (dari profil query load test). IF NOT EXISTS → idempoten.
ADDED_INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_harvests_status_reported ON harvests (status, reported_at)",
    "CREATE INDEX IF NOT EXISTS ix_harvests_farmer_reported ON harvests (farmer_id, reported_at)",
    "CREATE INDEX IF NOT EXISTS ix_route_stops_route_order ON route_stops (route_id, stop_order)",
    "CREATE INDEX IF NOT EXISTS ix_routes_driver_status ON routes (driver_id, status)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_custody_verification_code ON custody_events (verification_code)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_route_stops_harvest ON route_stops (harvest_id) WHERE harvest_id IS NOT NULL",
]


def upgrade_schema(sync_conn) -> list[str]:
    """Tambahkan kolom yang belum ada. Dipanggil via `conn.run_sync(upgrade_schema)` setelah create_all."""
    insp = inspect(sync_conn)
    added = []
    for table, column, ddl in ADDED_COLUMNS:
        if column not in {c["name"] for c in insp.get_columns(table)}:
            sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
            added.append(f"{table}.{column}")
    dup = sync_conn.execute(text(
        "SELECT harvest_id FROM route_stops WHERE harvest_id IS NOT NULL GROUP BY harvest_id HAVING COUNT(*) > 1"
    )).first()
    for ddl in ADDED_INDEXES:
        if "uq_route_stops_harvest" in ddl and dup is not None:
            # Non-breaking: data lama ganda → jangan gagalkan startup; bereskan dulu (lihat migrations/README.md).
            print(f"⚠️  uq_route_stops_harvest dilewati: harvest_id {dup[0]} ada di >1 stop.")
            continue
        sync_conn.execute(text(ddl))
    return added
