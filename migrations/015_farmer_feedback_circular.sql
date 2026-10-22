-- Migrasi 015 — Umpan balik petani & ekonomi sirkular:
--   * taksiran kadar air & grade dari petani (OPSIONAL; bukan dasar harga — QC pengepul/pabrik tetap otoritatif)
--   * kategori alasan tolak terstruktur → defect rate & penyebab di laporan bulanan
--   * pengambilan biochar oleh petani untuk sawah (sisi keluar Dompet Biochar), ledger ditulis saat serah-terima
-- Idempoten (IF NOT EXISTS) & aman diulang.
BEGIN;
SET LOCAL lock_timeout = '5s';

ALTER TABLE harvests ADD COLUMN IF NOT EXISTS farmer_moisture_est DOUBLE PRECISION;
ALTER TABLE harvests ADD COLUMN IF NOT EXISTS farmer_grade_est VARCHAR(1);
ALTER TABLE harvests ADD COLUMN IF NOT EXISTS reject_category VARCHAR(20);
DO $$ BEGIN
  ALTER TABLE harvests ADD CONSTRAINT ck_harvest_farmer_est
    CHECK ((farmer_moisture_est IS NULL OR farmer_moisture_est BETWEEN 0 AND 60)
           AND (farmer_grade_est IS NULL OR farmer_grade_est IN ('A', 'B', 'C', 'D')));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
  ALTER TABLE harvests ADD CONSTRAINT ck_harvest_reject_category
    CHECK (reject_category IS NULL OR reject_category IN
           ('basah', 'berjamur', 'kontaminan', 'selisih_berat', 'stok_tidak_ada', 'dibatalkan_pengepul', 'lainnya'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
CREATE INDEX IF NOT EXISTS ix_harvests_farmer_rejected ON harvests (farmer_id, rejected_at) WHERE rejected_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS biochar_redemptions (
  id                 SERIAL PRIMARY KEY,
  farmer_id          INTEGER NOT NULL REFERENCES users(id),
  kg                 DOUBLE PRECISION NOT NULL,
  land_area_ha       DOUBLE PRECISION,
  pickup_point       VARCHAR(10) NOT NULL DEFAULT 'pabrik',
  status             VARCHAR(12) NOT NULL DEFAULT 'diajukan',
  note               TEXT,
  estimate           JSON,
  ledger_entry_id    INTEGER REFERENCES biochar_ledger(id),
  handed_over_by_id  INTEGER REFERENCES users(id),
  handed_over_at     TIMESTAMPTZ,
  cancel_reason      TEXT,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_bredeem_kg_pos  CHECK (kg > 0),
  CONSTRAINT ck_bredeem_area_pos CHECK (land_area_ha IS NULL OR land_area_ha > 0),
  CONSTRAINT ck_bredeem_status  CHECK (status IN ('diajukan', 'diserahkan', 'dibatalkan')),
  CONSTRAINT ck_bredeem_pickup  CHECK (pickup_point IN ('pabrik', 'pengepul'))
);
CREATE INDEX IF NOT EXISTS ix_bredeem_farmer ON biochar_redemptions (farmer_id);
CREATE INDEX IF NOT EXISTS ix_bredeem_status ON biochar_redemptions (status) WHERE status = 'diajukan';

-- Register penghematan & pengurangan dampak lingkungan per proses rantai pasok
CREATE TABLE IF NOT EXISTS efficiency_actions (
  id                  SERIAL PRIMARY KEY,
  process             VARCHAR(20) NOT NULL,
  title               VARCHAR(160) NOT NULL,
  description         TEXT,
  metric              VARCHAR(60),
  baseline_value      DOUBLE PRECISION,
  current_value       DOUBLE PRECISION,
  saving_rp           DOUBLE PRECISION,
  saving_co2e_kg      DOUBLE PRECISION,
  period              VARCHAR(7),
  status              VARCHAR(14) NOT NULL DEFAULT 'rencana',
  evidence            TEXT,
  source_opportunity  VARCHAR(40),
  created_by_id       INTEGER NOT NULL REFERENCES users(id),
  verified_by_id      INTEGER REFERENCES users(id),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_effact_status CHECK (status IN ('rencana', 'berjalan', 'terverifikasi', 'batal')),
  CONSTRAINT ck_effact_rp CHECK (saving_rp IS NULL OR saving_rp >= 0)
);
CREATE INDEX IF NOT EXISTS ix_effact_process ON efficiency_actions (process);
CREATE INDEX IF NOT EXISTS ix_effact_status ON efficiency_actions (status);

-- ---------------------------------------------------------------- RLS
ALTER TABLE efficiency_actions ENABLE ROW LEVEL SECURITY; ALTER TABLE efficiency_actions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS effact_operator ON efficiency_actions;
CREATE POLICY effact_operator ON efficiency_actions FOR ALL USING (app_is_operator()) WITH CHECK (app_is_operator());
DROP POLICY IF EXISTS effact_audit ON efficiency_actions;
CREATE POLICY effact_audit ON efficiency_actions FOR SELECT USING (app_role() = 'auditor');

-- Petani: baca/ajukan/batalkan milik sendiri. Serah-terima (status diserahkan + ledger) hanya operator (pabrik/admin).
ALTER TABLE biochar_redemptions ENABLE ROW LEVEL SECURITY; ALTER TABLE biochar_redemptions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bredeem_operator ON biochar_redemptions;
CREATE POLICY bredeem_operator ON biochar_redemptions FOR ALL USING (app_is_operator()) WITH CHECK (app_is_operator());
DROP POLICY IF EXISTS bredeem_farmer ON biochar_redemptions;
CREATE POLICY bredeem_farmer ON biochar_redemptions FOR ALL
  USING (app_role() = 'petani' AND farmer_id = app_uid())
  WITH CHECK (app_role() = 'petani' AND farmer_id = app_uid() AND status IN ('diajukan', 'dibatalkan')
              AND ledger_entry_id IS NULL);
DROP POLICY IF EXISTS bredeem_audit ON biochar_redemptions;
CREATE POLICY bredeem_audit ON biochar_redemptions FOR SELECT USING (app_role() = 'auditor');

COMMIT;
