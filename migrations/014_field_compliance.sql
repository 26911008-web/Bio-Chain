-- Migrasi 014 — Kepatuhan lapangan: bukti bayar petani (F8), petani tanpa HP (F7), PDP (F12), ganti password (F6).
-- Rupiah pembayaran petani memakai NUMERIC(14,0). Idempoten (IF NOT EXISTS) & aman diulang.
BEGIN;
SET LOCAL lock_timeout = '5s';

ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS managed_by_id INTEGER REFERENCES users(id);
ALTER TABLE users ADD COLUMN IF NOT EXISTS anonymized_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS ix_users_managed_by ON users (managed_by_id) WHERE managed_by_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS farmer_payments (
  id                  SERIAL PRIMARY KEY,
  harvest_id          INTEGER NOT NULL UNIQUE REFERENCES harvests(id),
  farmer_id           INTEGER NOT NULL REFERENCES users(id),
  collector_id        INTEGER NOT NULL REFERENCES users(id),
  gross_rp            NUMERIC(14,0) NOT NULL,
  tax_rp              NUMERIC(14,0) NOT NULL DEFAULT 0,
  net_rp              NUMERIC(14,0) NOT NULL,
  tax_basis           VARCHAR(80),
  method              VARCHAR(10) NOT NULL,
  reference           VARCHAR(80),
  receipt_code        VARCHAR(40) NOT NULL UNIQUE,
  evidence_photo_url  TEXT,
  client_event_id     VARCHAR(64) UNIQUE,
  paid_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_fpay_nonneg CHECK (gross_rp >= 0 AND tax_rp >= 0 AND net_rp >= 0),
  CONSTRAINT ck_fpay_net    CHECK (net_rp = gross_rp - tax_rp),
  CONSTRAINT ck_fpay_method CHECK (method IN ('tunai', 'transfer', 'qris', 'ewallet'))
);
CREATE INDEX IF NOT EXISTS ix_farmer_payments_farmer ON farmer_payments (farmer_id);
CREATE INDEX IF NOT EXISTS ix_farmer_payments_collector ON farmer_payments (collector_id);

CREATE TABLE IF NOT EXISTS consents (
  id              SERIAL PRIMARY KEY,
  user_id         INTEGER NOT NULL REFERENCES users(id),
  purpose         VARCHAR(30) NOT NULL,
  version         VARCHAR(20) NOT NULL,
  granted         BOOLEAN NOT NULL,
  method          VARCHAR(20) NOT NULL DEFAULT 'aplikasi',
  recorded_by_id  INTEGER REFERENCES users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_consent_method CHECK (method IN ('aplikasi', 'lisan_via_pengepul', 'tertulis'))
);
CREATE INDEX IF NOT EXISTS ix_consents_user ON consents (user_id);

CREATE TABLE IF NOT EXISTS data_requests (
  id            SERIAL PRIMARY KEY,
  user_id       INTEGER NOT NULL REFERENCES users(id),
  kind          VARCHAR(10) NOT NULL,
  status        VARCHAR(10) NOT NULL DEFAULT 'selesai',
  receipt_code  VARCHAR(40) NOT NULL,
  note          TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_datareq_receipt UNIQUE (receipt_code)
);
CREATE INDEX IF NOT EXISTS ix_data_requests_user ON data_requests (user_id);

-- ---------------------------------------------------------------- RLS
-- Pembayaran: pengepul pencatat (tulis), petani penerima (baca), operator & auditor (baca/tulis sesuai peran)
ALTER TABLE farmer_payments ENABLE ROW LEVEL SECURITY; ALTER TABLE farmer_payments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS fpay_collector ON farmer_payments;
CREATE POLICY fpay_collector ON farmer_payments FOR ALL
  USING (app_is_operator() OR (app_role() = 'pengepul' AND collector_id = app_uid()))
  WITH CHECK (app_is_operator() OR (app_role() = 'pengepul' AND collector_id = app_uid()));
DROP POLICY IF EXISTS fpay_farmer_read ON farmer_payments;
CREATE POLICY fpay_farmer_read ON farmer_payments FOR SELECT USING (app_role() = 'petani' AND farmer_id = app_uid());
DROP POLICY IF EXISTS fpay_audit ON farmer_payments;
CREATE POLICY fpay_audit ON farmer_payments FOR SELECT USING (app_role() = 'auditor');

-- Persetujuan: milik sendiri; pengepul boleh mencatat persetujuan lisan petani binaan (recorded_by = dirinya)
ALTER TABLE consents ENABLE ROW LEVEL SECURITY; ALTER TABLE consents FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS consent_own ON consents;
CREATE POLICY consent_own ON consents FOR ALL
  USING (app_is_operator() OR user_id = app_uid() OR recorded_by_id = app_uid())
  WITH CHECK (app_is_operator() OR user_id = app_uid() OR (app_role() = 'pengepul' AND recorded_by_id = app_uid()));
DROP POLICY IF EXISTS consent_audit ON consents;
CREATE POLICY consent_audit ON consents FOR SELECT USING (app_role() = 'auditor');

ALTER TABLE data_requests ENABLE ROW LEVEL SECURITY; ALTER TABLE data_requests FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS datareq_own ON data_requests;
CREATE POLICY datareq_own ON data_requests FOR ALL
  USING (app_is_operator() OR user_id = app_uid()) WITH CHECK (app_is_operator() OR user_id = app_uid());
DROP POLICY IF EXISTS datareq_audit ON data_requests;
CREATE POLICY datareq_audit ON data_requests FOR SELECT USING (app_role() = 'auditor');

-- Hak akses biochain_app diberikan oleh 000_app_role.sql (dijalankan terakhir; ALL TABLES + default privileges).

COMMIT;
