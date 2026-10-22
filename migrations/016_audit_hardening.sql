-- Migrasi 016 — Penguatan hasil audit 5 fase:
--   * users.token_version: ganti/reset password mencabut semua token lama
--   * uang muka (DP) petani: farmer_down_payments + farmer_payments.dp_rp (dipotong saat pelunasan)
--   * ongkos jarak kosong / batal sebagai potongan nyata tagihan pengepul: logistics_charges
--   * refraksi kadar air di QC pabrik (kg basis kering terhadap kadar air acuan kontrak)
--   * BOM multi-output: aliran bio-oil/tar dicatat di batch_losses
-- Idempoten & aman diulang.
BEGIN;
SET LOCAL lock_timeout = '5s';

ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0;

-- ---------------------------------------------------------------- DP / uang muka
CREATE TABLE IF NOT EXISTS farmer_down_payments (
  id               SERIAL PRIMARY KEY,
  harvest_id       INTEGER NOT NULL UNIQUE REFERENCES harvests(id),
  farmer_id        INTEGER NOT NULL REFERENCES users(id),
  collector_id     INTEGER NOT NULL REFERENCES users(id),
  amount_rp        NUMERIC(14,0) NOT NULL,
  method           VARCHAR(10) NOT NULL,
  reference        VARCHAR(80),
  receipt_code     VARCHAR(40) NOT NULL UNIQUE,
  status           VARCHAR(24) NOT NULL DEFAULT 'aktif',
  status_note      TEXT,
  client_event_id  VARCHAR(64) UNIQUE,
  paid_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_fdp_amount CHECK (amount_rp > 0),
  CONSTRAINT ck_fdp_method CHECK (method IN ('tunai', 'transfer', 'qris', 'ewallet')),
  CONSTRAINT ck_fdp_status CHECK (status IN ('aktif', 'dipotong', 'hangus_untuk_petani', 'wajib_dikembalikan', 'dikembalikan'))
);
CREATE INDEX IF NOT EXISTS ix_fdp_farmer ON farmer_down_payments (farmer_id);
CREATE INDEX IF NOT EXISTS ix_fdp_collector ON farmer_down_payments (collector_id);

ALTER TABLE farmer_payments ADD COLUMN IF NOT EXISTS dp_rp NUMERIC(14,0) NOT NULL DEFAULT 0;
ALTER TABLE farmer_payments DROP CONSTRAINT IF EXISTS ck_fpay_net;
ALTER TABLE farmer_payments ADD CONSTRAINT ck_fpay_net CHECK (net_rp = gross_rp - tax_rp - dp_rp);
DO $$ BEGIN
  ALTER TABLE farmer_payments ADD CONSTRAINT ck_fpay_dp CHECK (dp_rp >= 0);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ---------------------------------------------------------------- potongan logistik
CREATE TABLE IF NOT EXISTS logistics_charges (
  id               SERIAL PRIMARY KEY,
  kind             VARCHAR(20) NOT NULL,
  collector_id     INTEGER NOT NULL REFERENCES users(id),
  route_id         INTEGER REFERENCES routes(id),
  stop_id          INTEGER REFERENCES route_stops(id),
  harvest_id       INTEGER REFERENCES harvests(id),
  km               DOUBLE PRECISION,
  amount_rp        NUMERIC(14,0) NOT NULL,
  status           VARCHAR(12) NOT NULL DEFAULT 'terbuka',
  settlement_id    INTEGER REFERENCES collector_settlements(id),
  reason           TEXT,
  created_by_id    INTEGER NOT NULL REFERENCES users(id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at      TIMESTAMPTZ,
  CONSTRAINT ck_lch_amount CHECK (amount_rp >= 0),
  CONSTRAINT ck_lch_kind CHECK (kind IN ('batal_pembelian', 'stop_gagal')),
  CONSTRAINT ck_lch_status CHECK (status IN ('terbuka', 'dipotong', 'dibebaskan'))
);
CREATE INDEX IF NOT EXISTS ix_lch_collector_open ON logistics_charges (collector_id) WHERE status = 'terbuka';
CREATE UNIQUE INDEX IF NOT EXISTS uq_lch_stop ON logistics_charges (stop_id) WHERE stop_id IS NOT NULL;

-- ---------------------------------------------------------------- refraksi QC pabrik & BOM
ALTER TABLE inbound_qc ADD COLUMN IF NOT EXISTS refraction_kg DOUBLE PRECISION NOT NULL DEFAULT 0;
ALTER TABLE inbound_qc ADD COLUMN IF NOT EXISTS dry_basis_kg DOUBLE PRECISION;
ALTER TABLE batch_losses DROP CONSTRAINT IF EXISTS batch_losses_kind_check;
ALTER TABLE batch_losses DROP CONSTRAINT IF EXISTS ck_batch_losses_kind;
ALTER TABLE batch_losses ADD CONSTRAINT ck_batch_losses_kind
  CHECK (kind IN ('air','volatil_syngas','gas_pembakaran','bio_oil','residu_ekstraksi','susut_proses'));

-- ---------------------------------------------------------------- RLS
ALTER TABLE farmer_down_payments ENABLE ROW LEVEL SECURITY; ALTER TABLE farmer_down_payments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS fdp_collector ON farmer_down_payments;
CREATE POLICY fdp_collector ON farmer_down_payments FOR ALL
  USING (app_is_operator() OR (app_role() = 'pengepul' AND collector_id = app_uid()))
  WITH CHECK (app_is_operator() OR (app_role() = 'pengepul' AND collector_id = app_uid()));
DROP POLICY IF EXISTS fdp_farmer_read ON farmer_down_payments;
CREATE POLICY fdp_farmer_read ON farmer_down_payments FOR SELECT USING (app_role() = 'petani' AND farmer_id = app_uid());
DROP POLICY IF EXISTS fdp_audit ON farmer_down_payments;
CREATE POLICY fdp_audit ON farmer_down_payments FOR SELECT USING (app_role() = 'auditor');

ALTER TABLE logistics_charges ENABLE ROW LEVEL SECURITY; ALTER TABLE logistics_charges FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS lch_operator ON logistics_charges;
CREATE POLICY lch_operator ON logistics_charges FOR ALL USING (app_is_operator()) WITH CHECK (app_is_operator());
DROP POLICY IF EXISTS lch_collector_read ON logistics_charges;
CREATE POLICY lch_collector_read ON logistics_charges FOR SELECT USING (app_role() = 'pengepul' AND collector_id = app_uid());
DROP POLICY IF EXISTS lch_audit ON logistics_charges;
CREATE POLICY lch_audit ON logistics_charges FOR SELECT USING (app_role() = 'auditor');

COMMIT;
