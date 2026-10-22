-- Bio-Chain v2 · Migrasi 010 — Lapisan gudang data (view bulanan) untuk laporan & alat BI · PostgreSQL 16
--
-- Satu sumber kebenaran: view dibangun langsung di atas ledger operasional (tanpa tabel ringkasan yang bisa
-- "beda versi"). Bulan = WIB (Asia/Jakarta), sama dengan resi & API /api/reports/monthly.
-- security_invoker = true (PG ≥ 15): view dievaluasi dengan hak PEMANGGIL sehingga RLS tetap berlaku —
-- tanpa opsi ini view berjalan dengan hak pemiliknya dan MELEWATI RLS.
-- Rollback: 010_reporting_warehouse.rollback.sql
BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE OR REPLACE FUNCTION wib_month(ts timestamptz) RETURNS text LANGUAGE sql IMMUTABLE AS
  $$ SELECT to_char(ts AT TIME ZONE 'Asia/Jakarta', 'YYYY-MM') $$;

-- ---------------------------------------------------------------- volume pasokan
CREATE OR REPLACE VIEW wh_monthly_supply WITH (security_invoker = true) AS
WITH ev AS (
  SELECT wib_month(reported_at) AS month, quantity_kg AS reported_kg, 0::float8 AS verified_kg,
         0::float8 AS received_kg, 0::float8 AS rejected_kg FROM harvests WHERE reported_at IS NOT NULL
  UNION ALL
  SELECT wib_month(verified_at), 0, verified_kg, 0, 0 FROM harvests WHERE verified_kg IS NOT NULL
  UNION ALL   -- jalur rute armada pabrik (lot QC dihitung di bawah, tidak ganda)
  SELECT wib_month(delivered_at), 0, 0, received_kg, 0 FROM harvests
   WHERE received_kg IS NOT NULL AND status IN ('delivered','converted') AND delivery_request_id IS NULL
  UNION ALL
  SELECT wib_month(created_at), 0, 0, CASE WHEN decision <> 'tolak' THEN net_kg ELSE 0 END,
         CASE WHEN decision = 'tolak' THEN net_kg ELSE 0 END FROM inbound_qc
)
SELECT month, sum(reported_kg) AS reported_kg, sum(verified_kg) AS collector_verified_kg,
       sum(received_kg) AS factory_received_kg, sum(rejected_kg) AS rejected_kg
FROM ev GROUP BY month;

-- ---------------------------------------------------------------- konversi biomassa (Material Flow Analysis)
CREATE OR REPLACE VIEW wh_monthly_conversion WITH (security_invoker = true) AS
SELECT wib_month(b.created_at) AS month,
       count(*) AS batches,
       sum(b.input_kg) AS batch_input_kg,
       sum(o.pellet) AS bio_pellet_kg, sum(o.biochar) AS biochar_kg, sum(o.silika) AS bio_silika_kg,
       sum(l.loss) AS loss_kg,
       avg(b.closure_error_pct) AS closure_error_pct_avg,
       100 * sum(o.pellet + o.biochar + o.silika) / NULLIF(sum(b.input_kg), 0) AS product_yield_pct
FROM manufacturing_batches b
LEFT JOIN LATERAL (
  SELECT coalesce(sum(quantity_kg) FILTER (WHERE product = 'bio_pellet'), 0) AS pellet,
         coalesce(sum(quantity_kg) FILTER (WHERE product = 'biochar'), 0)    AS biochar,
         coalesce(sum(quantity_kg) FILTER (WHERE product = 'bio_silika'), 0) AS silika
  FROM batch_outputs WHERE batch_id = b.id) o ON true
LEFT JOIN LATERAL (SELECT coalesce(sum(quantity_kg), 0) AS loss FROM batch_losses WHERE batch_id = b.id) l ON true
GROUP BY 1;

-- ---------------------------------------------------------------- biaya & energi
CREATE OR REPLACE VIEW wh_monthly_cost WITH (security_invoker = true) AS
WITH qc AS (
  SELECT wib_month(created_at) AS month, sum(total_payment_rp) AS raw_material_rp, sum(payable_kg) AS paid_kg
  FROM inbound_qc WHERE decision <> 'tolak' GROUP BY 1
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
       en.energy_kwh, en.energy_kwh / NULLIF(en.energy_ton, 0) AS sec_kwh_per_ton
FROM qc FULL OUTER JOIN bt ON bt.month = qc.month FULL OUTER JOIN en ON en.month = coalesce(qc.month, bt.month);

-- ---------------------------------------------------------------- dompet petani (ekonomi sirkular)
CREATE OR REPLACE VIEW wh_monthly_wallet WITH (security_invoker = true) AS
SELECT wib_month(created_at) AS month, farmer_id, sum(amount_kg) AS biochar_credited_kg
FROM biochar_ledger WHERE entry_type = 'allocation' GROUP BY 1, 2;

-- Indeks pendukung agregasi bulanan
CREATE INDEX IF NOT EXISTS ix_inbound_qc_created ON inbound_qc (created_at);
CREATE INDEX IF NOT EXISTS ix_batches_created ON manufacturing_batches (created_at);
CREATE INDEX IF NOT EXISTS ix_ledger_created ON biochar_ledger (created_at);
CREATE INDEX IF NOT EXISTS ix_harvests_verified_at ON harvests (verified_at);
CREATE INDEX IF NOT EXISTS ix_harvests_delivered_at ON harvests (delivered_at);

GRANT SELECT ON wh_monthly_supply, wh_monthly_conversion, wh_monthly_cost, wh_monthly_wallet TO PUBLIC;
COMMIT;
