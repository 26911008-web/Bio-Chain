-- Bio-Chain v2 · Migrasi 008 — 3 jalur bio-silika, rantai Delivery Request → dompet biochar · PostgreSQL 16
-- Expand-only. Rollback: 008_silica_routes_wallet_link.rollback.sql
BEGIN;
SET LOCAL lock_timeout = '5s';

-- Jalur bio-silika per batch
ALTER TABLE manufacturing_batches ADD COLUMN IF NOT EXISTS silica_route VARCHAR(16) NOT NULL DEFAULT 'biochar';
ALTER TABLE manufacturing_batches ADD COLUMN IF NOT EXISTS silica_husk_share DOUBLE PRECISION NOT NULL DEFAULT 0;
DO $$ BEGIN
  ALTER TABLE manufacturing_batches ADD CONSTRAINT ck_batch_silica_route
    CHECK (silica_route IN ('biochar','abu_pembakaran','sekam_langsung'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Jenis loss baru: gas pembakaran/kalsinasi (jalur abu & sekam langsung)
ALTER TABLE batch_losses DROP CONSTRAINT IF EXISTS batch_losses_kind_check;
ALTER TABLE batch_losses DROP CONSTRAINT IF EXISTS ck_batch_losses_kind;
ALTER TABLE batch_losses ADD CONSTRAINT ck_batch_losses_kind
  CHECK (kind IN ('air','volatil_syngas','gas_pembakaran','residu_ekstraksi','susut_proses'));

-- Harvest petani dilampirkan pengepul pada Delivery Request
ALTER TABLE harvests ADD COLUMN IF NOT EXISTS delivery_request_id INTEGER REFERENCES delivery_requests(id);
CREATE INDEX IF NOT EXISTS ix_harvests_delivery_request_id ON harvests (delivery_request_id);

-- Ledger biochar: alokasi dari batch manufaktur (sekali per batch per harvest)
ALTER TABLE biochar_ledger ADD COLUMN IF NOT EXISTS batch_id INTEGER REFERENCES manufacturing_batches(id);
CREATE INDEX IF NOT EXISTS ix_biochar_ledger_batch_id ON biochar_ledger (batch_id);
DO $$ BEGIN
  ALTER TABLE biochar_ledger ADD CONSTRAINT uq_ledger_batch_alloc_once UNIQUE (batch_id, harvest_id, entry_type);
EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL; END $$;

-- Status 'delivered' boleh langsung dari 'verified' (pengepul mengantar sendiri) — tidak ada perubahan CHECK status.
COMMIT;
