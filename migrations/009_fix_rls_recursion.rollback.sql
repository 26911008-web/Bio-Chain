-- Rollback migrasi 009 — mengembalikan kebijakan bids versi 005 (PERINGATAN: siklus RLS kembali; query pasar
-- akan gagal di PostgreSQL). Hanya untuk mengembalikan kondisi persis sebelum 009.
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP POLICY IF EXISTS bids_rw ON bids;
CREATE POLICY bids_rw ON bids FOR ALL
  USING (app_is_operator()
         OR (app_role() = 'pengepul' AND collector_id = app_uid())
         OR (app_role() = 'petani' AND listing_id IN (SELECT id FROM stock_listings WHERE farmer_id = app_uid())))
  WITH CHECK (app_is_operator()
              OR (app_role() = 'pengepul' AND collector_id = app_uid())
              OR (app_role() = 'petani' AND listing_id IN (SELECT id FROM stock_listings WHERE farmer_id = app_uid())));
DROP INDEX IF EXISTS ix_bids_farmer_id;
ALTER TABLE bids DROP COLUMN IF EXISTS farmer_id;
COMMIT;
