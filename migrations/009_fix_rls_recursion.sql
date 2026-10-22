-- Bio-Chain v2 · Migrasi 009 — Perbaikan RLS: siklus kebijakan stock_listings ↔ bids · PostgreSQL 16
--
-- Ditemukan saat uji di PostgreSQL sungguhan (tests/test_postgres.py): kebijakan listings_rw (pengepul melihat
-- listing yang pernah ia tawar → subquery bids) dan bids_rw (petani melihat tawaran atas listingnya → subquery
-- stock_listings) saling merujuk → "infinite recursion detected in policy for relation stock_listings" pada
-- SETIAP query pasar. SQLite tidak memiliki RLS sehingga tidak pernah memunculkannya.
--
-- Solusi: denormalisasi bids.farmer_id (pemilik listing, diisi aplikasi saat tawaran dibuat). Kebijakan bids
-- cukup membaca kolom ini; siklus putus. SECURITY DEFINER sengaja tidak dipakai: dengan FORCE ROW LEVEL
-- SECURITY, pemilik tabel non-superuser tetap terkena RLS sehingga siklus akan muncul lagi.
-- Rollback: 009_fix_rls_recursion.rollback.sql
BEGIN;
SET LOCAL lock_timeout = '5s';

ALTER TABLE bids ADD COLUMN IF NOT EXISTS farmer_id INTEGER REFERENCES users(id);
CREATE INDEX IF NOT EXISTS ix_bids_farmer_id ON bids (farmer_id);
-- Isi data lama (dijalankan sebagai pemilik tabel; RLS bids belum direvisi di titik ini)
SET LOCAL app.role = 'system';
UPDATE bids b SET farmer_id = l.farmer_id FROM stock_listings l WHERE l.id = b.listing_id AND b.farmer_id IS NULL;

DROP POLICY IF EXISTS bids_rw ON bids;
CREATE POLICY bids_rw ON bids FOR ALL
  USING (app_is_operator()
         OR (app_role() = 'pengepul' AND collector_id = app_uid())
         OR (app_role() = 'petani' AND farmer_id = app_uid()))
  WITH CHECK (app_is_operator()
              OR (app_role() = 'pengepul' AND collector_id = app_uid())
              OR (app_role() = 'petani' AND farmer_id = app_uid()));
COMMIT;
