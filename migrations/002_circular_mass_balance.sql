-- Bio-Chain v2 · Migrasi 002 — Mass balance, chain-of-custody, ledger biochar, role auditor (PostgreSQL 16)
-- Idempoten: aman dijalankan ulang. Aplikasi juga menambah kolom otomatis saat startup
-- (app/migrations.py); file ini untuk DBA + constraint/trigger yang hanya didukung PostgreSQL.

BEGIN;

-- 1. Timbangan bertingkat & susut di harvests
ALTER TABLE harvests ADD COLUMN IF NOT EXISTS verified_kg      DOUBLE PRECISION;
ALTER TABLE harvests ADD COLUMN IF NOT EXISTS picked_up_kg     DOUBLE PRECISION;
ALTER TABLE harvests ADD COLUMN IF NOT EXISTS received_kg      DOUBLE PRECISION;
ALTER TABLE harvests ADD COLUMN IF NOT EXISTS shrinkage_kg     DOUBLE PRECISION;
ALTER TABLE harvests ADD COLUMN IF NOT EXISTS shrinkage_pct    DOUBLE PRECISION;
ALTER TABLE harvests ADD COLUMN IF NOT EXISTS discrepancy_flag BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE harvests ADD COLUMN IF NOT EXISTS discrepancy_note TEXT;
ALTER TABLE harvests ADD COLUMN IF NOT EXISTS rejected_reason  TEXT;
ALTER TABLE harvests ADD COLUMN IF NOT EXISTS rejected_at      TIMESTAMPTZ;
ALTER TABLE harvests ADD COLUMN IF NOT EXISTS received_by_id   INTEGER REFERENCES users(id);
ALTER TABLE harvests ADD COLUMN IF NOT EXISTS conversion_id    INTEGER REFERENCES conversions(id);
ALTER TABLE harvests ADD COLUMN IF NOT EXISTS version          INTEGER NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS ix_harvests_discrepancy_flag ON harvests (discrepancy_flag) WHERE discrepancy_flag;
CREATE INDEX IF NOT EXISTS ix_harvests_conversion_id ON harvests (conversion_id);

DO $$ BEGIN
  ALTER TABLE harvests ADD CONSTRAINT ck_harvest_weights_nonneg CHECK (
    (verified_kg IS NULL OR verified_kg > 0) AND (received_kg IS NULL OR received_kg >= 0)
    AND (picked_up_kg IS NULL OR picked_up_kg >= 0));
  ALTER TABLE harvests ADD CONSTRAINT ck_harvest_status CHECK (
    status IN ('reported','verified','collected','delivered','converted','rejected'));
  -- Tidak boleh 'delivered'/'converted' tanpa timbangan pabrik
  ALTER TABLE harvests ADD CONSTRAINT ck_harvest_received_weight CHECK (
    status NOT IN ('delivered','converted') OR received_kg IS NOT NULL);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- 2. Porsi biochar untuk petani per batch
ALTER TABLE conversions ADD COLUMN IF NOT EXISTS farmer_return_share  DOUBLE PRECISION
  CHECK (farmer_return_share IS NULL OR farmer_return_share BETWEEN 0 AND 1);
ALTER TABLE conversions ADD COLUMN IF NOT EXISTS allocated_biochar_kg DOUBLE PRECISION;

-- 3. Chain-of-custody (append-only)
CREATE TABLE IF NOT EXISTS custody_events (
  id                 SERIAL PRIMARY KEY,
  harvest_id         INTEGER NOT NULL REFERENCES harvests(id),
  stage              VARCHAR(30) NOT NULL,
  from_status        VARCHAR(20),
  to_status          VARCHAR(20) NOT NULL,
  weight_kg          DOUBLE PRECISION CONSTRAINT ck_custody_weight_nonneg CHECK (weight_kg IS NULL OR weight_kg >= 0),
  actor_id           INTEGER NOT NULL REFERENCES users(id),
  actor_role         VARCHAR(20) NOT NULL,
  client_event_id    VARCHAR(64) UNIQUE,          -- idempotensi antrean offline
  client_recorded_at TIMESTAMPTZ,                 -- waktu di perangkat
  lat                DOUBLE PRECISION,
  lon                DOUBLE PRECISION,
  note               TEXT,
  created_at         TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_custody_events_harvest_id ON custody_events (harvest_id);

-- 4. Input batch pirolisis
CREATE TABLE IF NOT EXISTS conversion_inputs (
  id            SERIAL PRIMARY KEY,
  conversion_id INTEGER NOT NULL REFERENCES conversions(id),
  harvest_id    INTEGER NOT NULL UNIQUE REFERENCES harvests(id),
  farmer_id     INTEGER NOT NULL REFERENCES users(id),
  input_kg      DOUBLE PRECISION NOT NULL CONSTRAINT ck_conv_input_pos CHECK (input_kg > 0),
  share         DOUBLE PRECISION NOT NULL,
  created_at    TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_conversion_inputs_conversion_id ON conversion_inputs (conversion_id);
CREATE INDEX IF NOT EXISTS ix_conversion_inputs_farmer_id ON conversion_inputs (farmer_id);

-- 5. Dompet biochar petani (append-only; saldo = SUM(amount_kg))
CREATE TABLE IF NOT EXISTS biochar_ledger (
  id            SERIAL PRIMARY KEY,
  farmer_id     INTEGER NOT NULL REFERENCES users(id),
  conversion_id INTEGER REFERENCES conversions(id),
  harvest_id    INTEGER REFERENCES harvests(id),
  entry_type    VARCHAR(20) NOT NULL CHECK (entry_type IN ('allocation','redemption','adjustment')),
  amount_kg     DOUBLE PRECISION NOT NULL,
  note          TEXT,
  created_by_id INTEGER NOT NULL REFERENCES users(id),
  created_at    TIMESTAMPTZ DEFAULT now(),
  CONSTRAINT uq_ledger_alloc_once UNIQUE (conversion_id, harvest_id, entry_type)
);
CREATE INDEX IF NOT EXISTS ix_biochar_ledger_farmer_id ON biochar_ledger (farmer_id);

-- 6. Tolak UPDATE/DELETE pada tabel audit (koreksi = entri baru)
CREATE OR REPLACE FUNCTION forbid_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION '% bersifat append-only; buat entri koreksi', TG_TABLE_NAME;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_custody_append_only ON custody_events;
CREATE TRIGGER trg_custody_append_only BEFORE UPDATE OR DELETE ON custody_events
  FOR EACH ROW WHEN (current_setting('biochain.allow_reset', true) IS DISTINCT FROM 'on')
  EXECUTE FUNCTION forbid_mutation();
DROP TRIGGER IF EXISTS trg_ledger_append_only ON biochar_ledger;
CREATE TRIGGER trg_ledger_append_only BEFORE UPDATE OR DELETE ON biochar_ledger
  FOR EACH ROW WHEN (current_setting('biochain.allow_reset', true) IS DISTINCT FROM 'on')
  EXECUTE FUNCTION forbid_mutation();
-- Reset data demo: SET LOCAL biochain.allow_reset = 'on'; sebelum DELETE.

COMMIT;
