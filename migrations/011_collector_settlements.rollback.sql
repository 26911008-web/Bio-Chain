-- Rollback migrasi 011 — kembalikan view biaya versi 010 (sumber inbound_qc) lalu hapus tabel settlements.
-- PERHATIAN: catatan pembayaran jalur rute & status lunas akan hilang; ekspor dulu bila sudah dipakai.
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP VIEW IF EXISTS wh_monthly_cost;
CREATE VIEW wh_monthly_cost WITH (security_invoker = true) AS
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
GRANT SELECT ON wh_monthly_cost TO PUBLIC;
DROP TABLE IF EXISTS collector_settlements;
COMMIT;
