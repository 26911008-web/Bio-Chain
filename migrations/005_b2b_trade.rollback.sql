-- Rollback migrasi 005. PERINGATAN: menghapus data lelang & penghitung resi. Ekspor dulu:
--   pg_dump "$DATABASE_URL_SYNC" -t stock_listings -t bids -t trx_sequences > backup_005.sql
-- Kode resi yang sudah tercetak di custody_events dipertahankan sebagai teks (jejak audit tidak dihapus).
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP POLICY IF EXISTS bids_rw ON bids;              DROP POLICY IF EXISTS bids_audit ON bids;
DROP POLICY IF EXISTS listings_rw ON stock_listings; DROP POLICY IF EXISTS listings_audit ON stock_listings;

ALTER TABLE custody_events DROP CONSTRAINT IF EXISTS ck_verification_code_format;
ALTER TABLE harvests DROP COLUMN IF EXISTS bid_id, DROP COLUMN IF EXISTS listing_id,
                     DROP COLUMN IF EXISTS agreed_price_per_kg, DROP COLUMN IF EXISTS delivery_scheme;
DROP TABLE IF EXISTS trx_sequences;
DROP TABLE IF EXISTS bids;
DROP TABLE IF EXISTS stock_listings;
COMMIT;
