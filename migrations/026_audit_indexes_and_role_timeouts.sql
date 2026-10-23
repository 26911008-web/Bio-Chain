-- Bio-Chain v2 · Migrasi 026 — Indeks yang hilang (audit 23 Okt 2026, docs/29 P-6) + timeout per peran app (P-5)
--
-- NON-BLOCKING: CREATE INDEX CONCURRENTLY tidak boleh di dalam transaksi. Jalankan dengan autocommit
-- sebagai pemilik skema (biochain_owner):
--   psql "$OWNER_URL" -v ON_ERROR_STOP=1 -f migrations/026_audit_indexes_and_role_timeouts.sql
-- Rollback: migrations/026_audit_indexes_and_role_timeouts.rollback.sql

SET lock_timeout = '5s';
SET statement_timeout = 0;

-- Ekspor data pribadi (UU PDP) memfilter custody_events per aktor
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_custody_events_actor_id ON custody_events (actor_id);
-- Ketelusuran sirkular & custody memfilter ledger biochar per panen
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_biochar_ledger_harvest_id ON biochar_ledger (harvest_id);
-- Polling notifikasi (25 s/pengguna): filter pemilik/peran + ORDER BY id DESC
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_notifications_user_id_id ON notifications (user_id, id DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_notifications_role_id ON notifications (target_role, id DESC) WHERE user_id IS NULL;

-- DEFAULT di server untuk SEMUA kolom NOT NULL yang default-nya hanya di Python (model ORM; tabel dibuat
-- lewat create_all). Tanpa ini setiap INSERT lewat SQL/fungsi PL/pgSQL/impor gagal NotNullViolation.
-- Dibangkitkan dari metadata SQLAlchemy (kolom Enum dilewati). Hanya mengubah katalog — tidak menulis ulang tabel.
-- Tabel/kolom yang belum ada di DB tertentu dilewati (NOTICE), bukan menggagalkan migrasi.
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT * FROM (VALUES
    ('feedstock_parameters', 'bulk_density_kg_m3', '150.0'),
    ('feedstock_parameters', 'pb_max_ppm', '50.0'),
    ('feedstock_parameters', 'cd_max_ppm', '2.0'),
    ('feedstock_parameters', 'as_max_ppm', '10.0'),
    ('feedstock_parameters', 'is_active', 'TRUE'),
    ('trx_sequences', 'last_seq', '0'),
    ('users', 'must_change_password', 'FALSE'),
    ('users', 'token_version', '0'),
    ('carbon_claims', 'status', '''diajukan'''),
    ('collector_payment_reputations', 'total_transactions', '0'),
    ('collector_payment_reputations', 'on_time_dp_count', '0'),
    ('collector_payment_reputations', 'on_time_settlement_count', '0'),
    ('collector_payment_reputations', 'avg_dp_delay_hours', '0.0'),
    ('collector_payment_reputations', 'avg_settlement_delay_days', '0.0'),
    ('collector_payment_reputations', 'punctuality_score', '100.0'),
    ('collector_payment_reputations', 'outstanding_debt_rp', '0.0'),
    ('collector_payment_reputations', 'settled_amount_rp', '0.0'),
    ('collector_payment_reputations', 'rating_tier', '''EXCELLENT'''),
    ('consents', 'method', '''aplikasi'''),
    ('data_requests', 'status', '''selesai'''),
    ('delivery_requests', 'rounds', '0'),
    ('delivery_requests', 'pricing_mode', '''AUCTION'''),
    ('delivery_requests', 'version', '1'),
    ('efficiency_actions', 'status', '''rencana'''),
    ('energy_readings', 'production_ton', '0'),
    ('energy_readings', 'building_type', '''ac'''),
    ('energy_readings', 'source', '''meter'''),
    ('loading_ramps', 'max_capacity_kg', '50000.0'),
    ('loading_ramps', 'current_stock_kg', '0.0'),
    ('loading_ramps', 'aggregate_mc', '12.0'),
    ('loading_ramps', 'aggregate_ash', '15.0'),
    ('loading_ramps', 'aggregate_lhv_kcal', '3500.0'),
    ('loading_ramps', 'is_active', 'TRUE'),
    ('manufacturing_batches', 'silica_route', '''biochar'''),
    ('manufacturing_batches', 'silica_husk_share', '0.0'),
    ('biochar_distributions', 'status', '''DISPATCHED'''),
    ('by_product_ledgers', 'quantity_kg', '0.0'),
    ('by_product_ledgers', 'circular_status', '''STORED'''),
    ('by_product_ledgers', 'pb_ppm', '0.0'),
    ('by_product_ledgers', 'cd_ppm', '0.0'),
    ('by_product_ledgers', 'as_ppm', '0.0'),
    ('by_product_ledgers', 'is_safety_passed', 'FALSE'),
    ('inbound_qc', 'tare_kg', '0'),
    ('inbound_qc', 'contamination', '0'),
    ('inbound_qc', 'rejected_kg', '0.0'),
    ('inbound_qc', 'refraction_kg', '0.0'),
    ('stock_listings', 'allow_jemput', 'TRUE'),
    ('stock_listings', 'allow_antar', 'FALSE'),
    ('stock_listings', 'version', '1'),
    ('stock_listings', 'auction_status', '''OPEN'''),
    ('stock_listings', 'logistics_mode', '''PICKUP'''),
    ('stock_listings', 'payment_status', '''UNPAID'''),
    ('bids', 'accepted_kg', '0'),
    ('harvests', 'discrepancy_flag', 'FALSE'),
    ('harvests', 'version', '1'),
    ('harvests', 'logistics_mode', '''PICKUP'''),
    ('harvests', 'payment_status', '''UNPAID'''),
    ('biochar_circular_requests', 'allocated_kg', '0.0'),
    ('biochar_circular_requests', 'delivery_point', '''Lahan Petani'''),
    ('biochar_circular_requests', 'status', '''REQUESTED'''),
    ('biochar_requests', 'allocated_kg', '0.0'),
    ('biochar_requests', 'status', '''REQUESTED'''),
    ('biochar_requests', 'partition_safeguard_verified', 'TRUE'),
    ('collector_ratings', 'punctuality_rating', '5'),
    ('collector_ratings', 'payment_rating', '5'),
    ('collector_ratings', 'overall_rating', '5.0'),
    ('farmer_down_payments', 'status', '''aktif'''),
    ('farmer_payments', 'tax_rp', '0'),
    ('farmer_payments', 'dp_rp', '0'),
    ('notifications', 'status_group', '''PENDING_ACTION'''),
    ('notifications', 'is_read', 'FALSE'),
    ('return_cases', 'location', '''pabrik'''),
    ('return_cases', 'status', '''terbuka'''),
    ('biochar_quality_evaluations', 'grain_size_mesh_rating', '5'),
    ('biochar_quality_evaluations', 'pyrolysis_maturity_rating', '5'),
    ('biochar_quality_evaluations', 'moisture_rating', '5'),
    ('biochar_quality_evaluations', 'soil_impact_rating', '5'),
    ('biochar_quality_evaluations', 'overall_score', '5.0'),
    ('biochar_redemptions', 'pickup_point', '''pabrik'''),
    ('biochar_redemptions', 'status', '''diajukan'''),
    ('gate_receptions', 'logistics_carrier', '''FACTORY_FLEET'''),
    ('gate_receptions', 'tested_lhv_kcal', '3500.0'),
    ('gate_receptions', 'contamination_pct', '0.0'),
    ('gate_receptions', 'qc_decision', '''ACCEPTED'''),
    ('gate_receptions', 'accepted_qty_kg', '0.0'),
    ('gate_receptions', 'rejected_qty_kg', '0.0'),
    ('logistics_charges', 'status', '''terbuka'''),
    ('factory_invoices', 'payment_scheme', '''CASH'''),
    ('factory_invoices', 'dp_paid_amount', '0.0'),
    ('factory_invoices', 'remaining_amount', '0.0'),
    ('factory_invoices', 'is_overdue', 'FALSE'),
    ('factory_invoices', 'status', '''PENDING''')
,
    ('harvests', 'transaction_mode', '''DIRECT'''),
    ('stock_listings', 'transaction_mode', '''DIRECT'''),
    ('delivery_requests', 'biomass_type', '''sekam_padi''')
  ) AS v(tbl, col, dflt) LOOP
    BEGIN
      EXECUTE format('ALTER TABLE %I ALTER COLUMN %I SET DEFAULT %s', r.tbl, r.col, r.dflt);
    EXCEPTION WHEN undefined_table OR undefined_column THEN
      RAISE NOTICE 'lewati %.% (belum ada)', r.tbl, r.col;
    END;
  END LOOP;
END $$;

-- Timeout di level PERAN, bukan startup-parameter asyncpg: lewat Supavisor transaction mode (port 6543)
-- parameter startup tidak dijamin berlaku per transaksi. Butuh hak CREATEROLE/superuser; bila tidak ada,
-- jalankan bagian ini dari SQL Editor Supabase (peran postgres).
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'biochain_app') THEN
    ALTER ROLE biochain_app SET statement_timeout = '15s';
    ALTER ROLE biochain_app SET lock_timeout = '5s';
    ALTER ROLE biochain_app SET idle_in_transaction_session_timeout = '30s';
  END IF;
EXCEPTION WHEN insufficient_privilege THEN
  RAISE NOTICE 'Lewati ALTER ROLE biochain_app (butuh CREATEROLE) — jalankan dari SQL Editor sebagai postgres.';
END $$;
