-- Migrasi 011 — Pembayaran pabrik → pengepul untuk KEDUA jalur pasokan (menutup celah laporan).
-- Sebelumnya hanya jalur Delivery Request + QC yang punya catatan uang; sekam yang diangkut armada pabrik
-- (jalur rute) diterima tanpa kewajiban bayar tercatat → margin pengepul & biaya bahan baku pabrik kurang.
BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE TABLE IF NOT EXISTS collector_settlements (
  id                 SERIAL PRIMARY KEY,
  collector_id       INTEGER NOT NULL REFERENCES users(id),
  source             VARCHAR(4) NOT NULL,                        -- qc | rute
  qc_id              INTEGER UNIQUE REFERENCES inbound_qc(id),
  harvest_id         INTEGER UNIQUE REFERENCES harvests(id),
  payable_kg         DOUBLE PRECISION NOT NULL,
  moisture           DOUBLE PRECISION,
  price_per_kg       DOUBLE PRECISION,
  amount_rp          DOUBLE PRECISION,
  price_basis        TEXT,
  status             VARCHAR(14) NOT NULL,                       -- menunggu_harga | terutang | dibayar
  payment_reference  VARCHAR(80),
  created_by_id      INTEGER NOT NULL REFERENCES users(id),
  created_at         TIMESTAMPTZ DEFAULT now(),
  priced_at          TIMESTAMPTZ,
  paid_at            TIMESTAMPTZ,
  CONSTRAINT ck_settle_kg CHECK (payable_kg >= 0),
  CONSTRAINT ck_settle_amount CHECK (amount_rp IS NULL OR amount_rp >= 0),
  CONSTRAINT ck_settle_source CHECK ((source = 'qc' AND qc_id IS NOT NULL) OR (source = 'rute' AND harvest_id IS NOT NULL)),
  CONSTRAINT ck_settle_priced CHECK ((status = 'menunggu_harga') = (amount_rp IS NULL)),
  CONSTRAINT ck_settle_status CHECK (status IN ('menunggu_harga', 'terutang', 'dibayar')),
  CONSTRAINT ck_settle_paid_ref CHECK (status <> 'dibayar' OR payment_reference IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS ix_collector_settlements_collector_id ON collector_settlements (collector_id);
CREATE INDEX IF NOT EXISTS ix_collector_settlements_status ON collector_settlements (status);
CREATE INDEX IF NOT EXISTS ix_collector_settlements_created ON collector_settlements (created_at);

-- RLS: pabrik/admin/sistem tulis-baca semua; pengepul HANYA baca miliknya; auditor baca.
ALTER TABLE collector_settlements ENABLE ROW LEVEL SECURITY; ALTER TABLE collector_settlements FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS cs_operator ON collector_settlements;
CREATE POLICY cs_operator ON collector_settlements FOR ALL USING (app_is_operator()) WITH CHECK (app_is_operator());
DROP POLICY IF EXISTS cs_own_read ON collector_settlements;
CREATE POLICY cs_own_read ON collector_settlements FOR SELECT
  USING (app_role() = 'pengepul' AND collector_id = app_uid());
DROP POLICY IF EXISTS cs_audit ON collector_settlements;
CREATE POLICY cs_audit ON collector_settlements FOR SELECT USING (app_role() = 'auditor');

-- Gudang data: biaya bahan baku sekarang dari settlements (kedua jalur) + kg yang belum berharga
DROP VIEW IF EXISTS wh_monthly_cost;
CREATE VIEW wh_monthly_cost WITH (security_invoker = true) AS
WITH qc AS (
  SELECT wib_month(created_at) AS month, sum(amount_rp) AS raw_material_rp,
         sum(payable_kg) FILTER (WHERE amount_rp IS NOT NULL) AS paid_kg,
         coalesce(sum(payable_kg) FILTER (WHERE amount_rp IS NULL), 0) AS unpriced_kg
  FROM collector_settlements GROUP BY 1
), bt AS (
  SELECT wib_month(created_at) AS month, sum(input_kg) AS input_kg,
         sum((economics->'totals'->>'total_cost_rp')::float8) AS batch_cost_rp,
         sum((economics->'totals'->>'revenue_rp')::float8) AS revenue_rp,
         sum((economics->'totals'->>'profit_rp')::float8) AS profit_rp
  FROM manufacturing_batches GROUP BY 1
), en AS (
  SELECT period AS month, sum(kwh) AS energy_kwh, sum(production_ton) AS energy_ton FROM energy_readings GROUP BY 1
)
SELECT coalesce(qc.month, bt.month, en.month) AS month,
       qc.raw_material_rp, qc.raw_material_rp / NULLIF(qc.paid_kg, 0) AS avg_purchase_price_per_kg,
       bt.batch_cost_rp * 1000 / NULLIF(bt.input_kg, 0) AS cost_per_ton_input_rp,
       bt.revenue_rp, bt.profit_rp, 100 * bt.profit_rp / NULLIF(bt.revenue_rp, 0) AS margin_pct,
       en.energy_kwh, en.energy_kwh / NULLIF(en.energy_ton, 0) AS sec_kwh_per_ton,
       qc.unpriced_kg
FROM qc FULL OUTER JOIN bt ON bt.month = qc.month FULL OUTER JOIN en ON en.month = coalesce(qc.month, bt.month);
GRANT SELECT ON wh_monthly_cost TO PUBLIC;

-- Backfill: lot QC lama (diterima) mendapat catatan 'terutang' sesuai harga kontraknya
INSERT INTO collector_settlements (collector_id, source, qc_id, payable_kg, moisture, price_per_kg, amount_rp,
                                   price_basis, status, created_by_id, created_at, priced_at)
SELECT dr.collector_id, 'qc', q.id, q.payable_kg, q.moisture, q.final_price_per_kg, q.total_payment_rp,
       'backfill migrasi 011 dari QC masuk', 'terutang', q.inspector_id, q.created_at, q.created_at
FROM inbound_qc q JOIN delivery_requests dr ON dr.id = q.request_id
WHERE q.decision <> 'tolak'
ON CONFLICT (qc_id) DO NOTHING;
COMMIT;
