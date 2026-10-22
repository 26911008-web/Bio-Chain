-- Migrasi 019 — Prototipe 3: log operasi energi harian/shift (SEC/IKE ternormalisasi & detektor anomali).
-- Idempoten & aman diulang. Rollback: 019_energy_operation_logs.rollback.sql
BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE TABLE IF NOT EXISTS energy_operation_logs (
  id                  SERIAL PRIMARY KEY,
  facility            VARCHAR(100) NOT NULL,
  log_date            VARCHAR(10) NOT NULL,
  shift               VARCHAR(8) NOT NULL DEFAULT 'H',
  kwh_total           DOUBLE PRECISION NOT NULL,
  kwh_dryer           DOUBLE PRECISION,
  kwh_hammer_mill     DOUBLE PRECISION,
  diesel_l            DOUBLE PRECISION NOT NULL DEFAULT 0,
  biomass_fuel_kg     DOUBLE PRECISION NOT NULL DEFAULT 0,
  biomass_fuel_code   VARCHAR(24) REFERENCES biomass_parameters(code),
  operating_hours     DOUBLE PRECISION NOT NULL,
  product_ton         DOUBLE PRECISION NOT NULL,
  feed_moisture_pct   DOUBLE PRECISION,
  rated_capacity_t_h  DOUBLE PRECISION,
  note                TEXT,
  client_event_id     VARCHAR(64) UNIQUE,
  recorded_by_id      INTEGER NOT NULL REFERENCES users(id),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_energy_ops_slot UNIQUE (facility, log_date, shift),
  CONSTRAINT ck_eops_nonneg CHECK (kwh_total >= 0 AND diesel_l >= 0 AND biomass_fuel_kg >= 0),
  CONSTRAINT ck_eops_hours  CHECK (operating_hours > 0 AND operating_hours <= 24),
  CONSTRAINT ck_eops_ton    CHECK (product_ton > 0),
  CONSTRAINT ck_eops_mc     CHECK (feed_moisture_pct IS NULL OR (feed_moisture_pct >= 0 AND feed_moisture_pct < 95))
);
ALTER TABLE energy_operation_logs ALTER COLUMN shift SET DEFAULT 'H';
ALTER TABLE energy_operation_logs ALTER COLUMN diesel_l SET DEFAULT 0;
ALTER TABLE energy_operation_logs ALTER COLUMN biomass_fuel_kg SET DEFAULT 0;
ALTER TABLE energy_operation_logs ALTER COLUMN created_at SET DEFAULT now();
CREATE INDEX IF NOT EXISTS ix_energy_ops_facility_date ON energy_operation_logs (facility, log_date);

ALTER TABLE energy_operation_logs ENABLE ROW LEVEL SECURITY; ALTER TABLE energy_operation_logs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS eops_operator ON energy_operation_logs;
CREATE POLICY eops_operator ON energy_operation_logs FOR ALL USING (app_is_operator()) WITH CHECK (app_is_operator());
DROP POLICY IF EXISTS eops_audit ON energy_operation_logs;
CREATE POLICY eops_audit ON energy_operation_logs FOR SELECT USING (app_role() = 'auditor');

COMMIT;
