-- Rollback 013 — deploy kode lama DULU (kode lama tidak mengenal stop_status/retur/stok produk).
-- PERINGATAN: data retur, jejak GPS, dan mutasi stok produk ikut terhapus. Cadangkan sebelum menjalankan.
BEGIN;
SET LOCAL lock_timeout = '5s';

DROP FUNCTION IF EXISTS accept_bid_atomic(integer, integer, integer, double precision);
UPDATE bids SET status = 'withdrawn' WHERE status = 'cancelled';
ALTER TABLE bids DROP CONSTRAINT IF EXISTS bids_status_check;
ALTER TABLE bids ADD CONSTRAINT bids_status_check CHECK (status IN ('active', 'withdrawn', 'accepted', 'rejected'));

DROP VIEW IF EXISTS finished_goods_stock;
DROP TABLE IF EXISTS finished_goods_movements;
ALTER TABLE batch_outputs DROP COLUMN IF EXISTS expected_kg;
ALTER TABLE batch_outputs DROP COLUMN IF EXISTS yield_pct;
ALTER TABLE batch_outputs DROP COLUMN IF EXISTS yield_variance_pct;

DROP TABLE IF EXISTS return_cases;
DROP FUNCTION IF EXISTS forbid_resolved_return_update();
ALTER TABLE inbound_qc DROP CONSTRAINT IF EXISTS ck_qc_rejected;
ALTER TABLE inbound_qc DROP COLUMN IF EXISTS rejected_kg;

DROP TABLE IF EXISTS route_track_points;
ALTER TABLE routes DROP COLUMN IF EXISTS optimizer;
ALTER TABLE routes DROP COLUMN IF EXISTS actual_km;
ALTER TABLE routes DROP COLUMN IF EXISTS fuel_l;
ALTER TABLE routes DROP COLUMN IF EXISTS co2e_wtw_kg;
ALTER TABLE routes DROP COLUMN IF EXISTS co2e_per_ton_kg;
ALTER TABLE routes DROP COLUMN IF EXISTS emission_detail;
ALTER TABLE routes DROP COLUMN IF EXISTS cancel_reason;
ALTER TABLE routes DROP COLUMN IF EXISTS cancelled_by_id;
ALTER TABLE routes DROP COLUMN IF EXISTS cancelled_at;

-- Indeks lama mewajibkan harvest unik di SEMUA stop: stop gagal/batal yang dijadwalkan ulang harus dihapus dulu
DELETE FROM route_stops WHERE stop_status IN ('failed', 'cancelled')
  AND harvest_id IN (SELECT harvest_id FROM route_stops WHERE harvest_id IS NOT NULL
                     GROUP BY harvest_id HAVING count(*) > 1);
DROP INDEX IF EXISTS uq_route_stops_harvest_live;
CREATE UNIQUE INDEX IF NOT EXISTS uq_route_stops_harvest ON route_stops (harvest_id) WHERE harvest_id IS NOT NULL;
ALTER TABLE route_stops DROP CONSTRAINT IF EXISTS ck_stop_pickup_consistent;
ALTER TABLE route_stops DROP CONSTRAINT IF EXISTS ck_stop_status;
ALTER TABLE route_stops DROP COLUMN IF EXISTS stop_status;
ALTER TABLE route_stops DROP COLUMN IF EXISTS fail_reason;
ALTER TABLE route_stops DROP COLUMN IF EXISTS fail_note;
ALTER TABLE route_stops DROP COLUMN IF EXISTS failed_at;
COMMIT;
