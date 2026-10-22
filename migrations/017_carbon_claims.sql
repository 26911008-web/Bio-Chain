-- Migrasi 017 — F11: klaim removal karbon biochar dengan verifikator (empat mata).
--   * carbon_claims: snapshot hasil hitung + SHA-256, hasil lab C-org & H/C-org wajib, putusan auditor
--   * carbon_claim_items: UNIQUE(redemption_id) → satu serah-terima biochar hanya di satu klaim aktif
-- Idempoten & aman diulang.
BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE TABLE IF NOT EXISTS carbon_claims (
  id                 SERIAL PRIMARY KEY,
  code               VARCHAR(24) NOT NULL UNIQUE,
  period_start       TIMESTAMPTZ NOT NULL,
  period_end         TIMESTAMPTZ NOT NULL,
  status             VARCHAR(12) NOT NULL DEFAULT 'diajukan',
  lab_c_org_pct      DOUBLE PRECISION NOT NULL,
  lab_h_corg_ratio   DOUBLE PRECISION NOT NULL,
  lab_name           VARCHAR(120) NOT NULL,
  lab_report_no      VARCHAR(80) NOT NULL,
  lab_report_url     TEXT NOT NULL,
  end_use_kg         DOUBLE PRECISION NOT NULL,
  net_removal_tco2e  DOUBLE PRECISION NOT NULL,
  snapshot           JSON NOT NULL,
  snapshot_sha256    VARCHAR(64) NOT NULL,
  submitted_by_id    INTEGER NOT NULL REFERENCES users(id),
  submitted_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  verified_by_id     INTEGER REFERENCES users(id),
  decided_at         TIMESTAMPTZ,
  decision_note      TEXT,
  CONSTRAINT ck_cclaim_status    CHECK (status IN ('diajukan', 'diverifikasi', 'ditolak')),
  CONSTRAINT ck_cclaim_period    CHECK (period_end > period_start),
  CONSTRAINT ck_cclaim_corg      CHECK (lab_c_org_pct > 0 AND lab_c_org_pct <= 100),
  CONSTRAINT ck_cclaim_hc        CHECK (lab_h_corg_ratio > 0),
  CONSTRAINT ck_cclaim_four_eyes CHECK (verified_by_id IS NULL OR verified_by_id <> submitted_by_id),
  CONSTRAINT ck_cclaim_decided   CHECK (status = 'diajukan' OR (verified_by_id IS NOT NULL AND decision_note IS NOT NULL))
);
-- create_all aplikasi bisa membuat tabel lebih dulu (default hanya di Python) → samakan default server
ALTER TABLE carbon_claims ALTER COLUMN submitted_at SET DEFAULT now();
ALTER TABLE carbon_claims ALTER COLUMN status SET DEFAULT 'diajukan';
CREATE INDEX IF NOT EXISTS ix_carbon_claims_status ON carbon_claims (status);

CREATE TABLE IF NOT EXISTS carbon_claim_items (
  id             SERIAL PRIMARY KEY,
  claim_id       INTEGER NOT NULL REFERENCES carbon_claims(id) ON DELETE CASCADE,
  redemption_id  INTEGER NOT NULL UNIQUE REFERENCES biochar_redemptions(id),
  kg             DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_carbon_claim_items_claim_id ON carbon_claim_items (claim_id);

-- ---------------------------------------------------------------- RLS
-- Pabrik/admin: ajukan & baca. Auditor: baca semua; UPDATE hanya klaim 'diajukan' → putusan atas namanya sendiri;
-- DELETE kunci serah-terima hanya untuk melepas klaim yang ia tolak.
ALTER TABLE carbon_claims ENABLE ROW LEVEL SECURITY; ALTER TABLE carbon_claims FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS cclaim_operator ON carbon_claims;
CREATE POLICY cclaim_operator ON carbon_claims FOR ALL USING (app_is_operator())
  WITH CHECK (app_is_operator() AND status = 'diajukan');
DROP POLICY IF EXISTS cclaim_audit_read ON carbon_claims;
CREATE POLICY cclaim_audit_read ON carbon_claims FOR SELECT USING (app_role() = 'auditor');
DROP POLICY IF EXISTS cclaim_audit_decide ON carbon_claims;
CREATE POLICY cclaim_audit_decide ON carbon_claims FOR UPDATE
  USING (app_role() = 'auditor' AND status = 'diajukan')
  WITH CHECK (app_role() = 'auditor' AND status IN ('diverifikasi', 'ditolak') AND verified_by_id = app_uid());

ALTER TABLE carbon_claim_items ENABLE ROW LEVEL SECURITY; ALTER TABLE carbon_claim_items FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS cclitem_operator ON carbon_claim_items;
CREATE POLICY cclitem_operator ON carbon_claim_items FOR ALL USING (app_is_operator()) WITH CHECK (app_is_operator());
DROP POLICY IF EXISTS cclitem_audit_read ON carbon_claim_items;
CREATE POLICY cclitem_audit_read ON carbon_claim_items FOR SELECT USING (app_role() = 'auditor');
DROP POLICY IF EXISTS cclitem_audit_release ON carbon_claim_items;
CREATE POLICY cclitem_audit_release ON carbon_claim_items FOR DELETE
  USING (app_role() = 'auditor' AND EXISTS (SELECT 1 FROM carbon_claims c WHERE c.id = claim_id AND c.status = 'ditolak'));

COMMIT;
