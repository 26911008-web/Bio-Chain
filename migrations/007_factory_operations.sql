-- Bio-Chain v2 · Migrasi 007 — Pabrik: procurement B2B, QC masuk, manufaktur sirkular, biaya · PostgreSQL 16
-- Expand-only (tabel baru). Rollback: 007_factory_operations.rollback.sql
BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE TABLE IF NOT EXISTS delivery_requests (
  id                       SERIAL PRIMARY KEY,
  collector_id             INTEGER NOT NULL REFERENCES users(id),
  quantity_kg              DOUBLE PRECISION NOT NULL CHECK (quantity_kg > 0),
  moisture_est             DOUBLE PRECISION NOT NULL,
  ash_est                  DOUBLE PRECISION,
  grade_est                VARCHAR(5),
  proposed_date            VARCHAR(10) NOT NULL,
  proposed_price_per_kg    DOUBLE PRECISION NOT NULL,       -- tawaran yang sedang di meja
  recommended_price_per_kg DOUBLE PRECISION,                -- snapshot Pricing Engine
  agreed_price_per_kg      DOUBLE PRECISION,
  agreed_date              VARCHAR(10),
  pending_party            VARCHAR(10) CHECK (pending_party IN ('pabrik','pengepul')),
  rounds                   INTEGER NOT NULL DEFAULT 0,
  status                   VARCHAR(9) NOT NULL DEFAULT 'submitted'
                           CHECK (status IN ('submitted','countered','accepted','delivered','rejected','cancelled')),
  note TEXT, version INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ DEFAULT now(), decided_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_delivery_requests_collector ON delivery_requests (collector_id);
CREATE INDEX IF NOT EXISTS ix_delivery_requests_status ON delivery_requests (status);

CREATE TABLE IF NOT EXISTS negotiation_events (
  id SERIAL PRIMARY KEY, request_id INTEGER NOT NULL REFERENCES delivery_requests(id),
  actor_id INTEGER NOT NULL REFERENCES users(id), actor_role VARCHAR(20) NOT NULL,
  action VARCHAR(20) NOT NULL, price_per_kg DOUBLE PRECISION, date VARCHAR(10), note TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_negotiation_events_request ON negotiation_events (request_id);

CREATE TABLE IF NOT EXISTS inbound_qc (
  id SERIAL PRIMARY KEY,
  request_id INTEGER NOT NULL UNIQUE REFERENCES delivery_requests(id),
  gross_kg DOUBLE PRECISION NOT NULL, tare_kg DOUBLE PRECISION NOT NULL DEFAULT 0,
  net_kg DOUBLE PRECISION NOT NULL, payable_kg DOUBLE PRECISION NOT NULL,
  moisture DOUBLE PRECISION NOT NULL, ash DOUBLE PRECISION NOT NULL,
  volatile_matter DOUBLE PRECISION NOT NULL, fixed_carbon DOUBLE PRECISION NOT NULL,
  contamination DOUBLE PRECISION NOT NULL DEFAULT 0,
  grade VARCHAR(6) NOT NULL, score DOUBLE PRECISION NOT NULL,
  decision VARCHAR(15) NOT NULL CHECK (decision IN ('terima','terima_potongan','tolak')),
  final_price_per_kg DOUBLE PRECISION NOT NULL, total_payment_rp DOUBLE PRECISION NOT NULL,
  remaining_kg DOUBLE PRECISION NOT NULL,
  verification_code VARCHAR(40) UNIQUE, evidence_photo_url TEXT,
  inspector_id INTEGER NOT NULL REFERENCES users(id), note TEXT, created_at TIMESTAMPTZ DEFAULT now(),
  CONSTRAINT ck_qc_weights CHECK (gross_kg >= tare_kg AND tare_kg >= 0),
  CONSTRAINT ck_qc_remaining CHECK (remaining_kg >= 0)
);
CREATE INDEX IF NOT EXISTS ix_inbound_qc_available ON inbound_qc (id) WHERE remaining_kg > 0;

CREATE TABLE IF NOT EXISTS manufacturing_batches (
  id SERIAL PRIMARY KEY, batch_code VARCHAR(50) NOT NULL UNIQUE,
  started_at TIMESTAMPTZ, ended_at TIMESTAMPTZ, operating_hours DOUBLE PRECISION, pyrolysis_temp_c DOUBLE PRECISION,
  pellet_share DOUBLE PRECISION NOT NULL, silica_share_of_biochar DOUBLE PRECISION NOT NULL,
  input_kg DOUBLE PRECISION NOT NULL, closure_error_pct DOUBLE PRECISION NOT NULL, closure_ok INTEGER NOT NULL,
  economics JSONB NOT NULL, operator_id INTEGER NOT NULL REFERENCES users(id), note TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS batch_inputs (
  id SERIAL PRIMARY KEY, batch_id INTEGER NOT NULL REFERENCES manufacturing_batches(id),
  qc_id INTEGER NOT NULL REFERENCES inbound_qc(id), input_kg DOUBLE PRECISION NOT NULL CHECK (input_kg > 0),
  moisture DOUBLE PRECISION NOT NULL, CONSTRAINT uq_batch_lot UNIQUE (batch_id, qc_id)
);
CREATE TABLE IF NOT EXISTS batch_outputs (
  id SERIAL PRIMARY KEY, batch_id INTEGER NOT NULL REFERENCES manufacturing_batches(id),
  product VARCHAR(12) NOT NULL CHECK (product IN ('bio_pellet','biochar','bio_silika')),
  quantity_kg DOUBLE PRECISION NOT NULL CHECK (quantity_kg >= 0), quality JSONB
);
CREATE TABLE IF NOT EXISTS batch_losses (
  id SERIAL PRIMARY KEY, batch_id INTEGER NOT NULL REFERENCES manufacturing_batches(id),
  kind VARCHAR(20) NOT NULL CHECK (kind IN ('air','volatil_syngas','residu_ekstraksi','susut_proses')),
  quantity_kg DOUBLE PRECISION NOT NULL CHECK (quantity_kg >= 0)
);
CREATE TABLE IF NOT EXISTS batch_costs (
  id SERIAL PRIMARY KEY, batch_id INTEGER NOT NULL REFERENCES manufacturing_batches(id),
  cost_type VARCHAR(10) NOT NULL CHECK (cost_type IN ('variabel','tetap')), item VARCHAR(40) NOT NULL,
  driver_qty DOUBLE PRECISION, driver_unit VARCHAR(20), rate DOUBLE PRECISION,
  amount_rp DOUBLE PRECISION NOT NULL CHECK (amount_rp >= 0),
  product VARCHAR(12) CHECK (product IS NULL OR product IN ('bio_pellet','biochar','bio_silika'))
);
CREATE INDEX IF NOT EXISTS ix_batch_inputs_batch ON batch_inputs (batch_id);
CREATE INDEX IF NOT EXISTS ix_batch_outputs_batch ON batch_outputs (batch_id);
CREATE INDEX IF NOT EXISTS ix_batch_losses_batch ON batch_losses (batch_id);
CREATE INDEX IF NOT EXISTS ix_batch_costs_batch ON batch_costs (batch_id);

-- Jejak negosiasi append-only
DROP TRIGGER IF EXISTS trg_negotiation_append_only ON negotiation_events;
CREATE TRIGGER trg_negotiation_append_only BEFORE UPDATE OR DELETE ON negotiation_events
  FOR EACH ROW WHEN (current_setting('biochain.allow_reset', true) IS DISTINCT FROM 'on')
  EXECUTE FUNCTION forbid_mutation();

-- RLS: pengepul hanya melihat ajuannya sendiri; pabrik/admin/system penuh; auditor baca
ALTER TABLE delivery_requests ENABLE ROW LEVEL SECURITY; ALTER TABLE delivery_requests FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dr_rw ON delivery_requests;
CREATE POLICY dr_rw ON delivery_requests FOR ALL
  USING (app_is_operator() OR (app_role() = 'pengepul' AND collector_id = app_uid()))
  WITH CHECK (app_is_operator() OR (app_role() = 'pengepul' AND collector_id = app_uid()));
DROP POLICY IF EXISTS dr_audit ON delivery_requests;
CREATE POLICY dr_audit ON delivery_requests FOR SELECT USING (app_role() = 'auditor');
ALTER TABLE negotiation_events ENABLE ROW LEVEL SECURITY; ALTER TABLE negotiation_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ne_rw ON negotiation_events;
CREATE POLICY ne_rw ON negotiation_events FOR ALL
  USING (app_is_operator() OR app_role() = 'auditor' OR request_id IN (SELECT id FROM delivery_requests))
  WITH CHECK (app_is_operator() OR request_id IN (SELECT id FROM delivery_requests));
COMMIT;
