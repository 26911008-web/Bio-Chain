-- Bio-Chain v2 · Migrasi 004 — Row-Level Security per peran (PostgreSQL 16)
--
-- Lapisan RBAC ketiga, setelah middleware prefix (app/security/policy.py) dan require_role:
-- walaupun ada bug query di API, database hanya mengembalikan baris milik identitas yang login.
-- Identitas diset aplikasi per transaksi: set_config('app.user_id'|'app.role', ..., true)
-- (app/security/rls.py) → aman untuk PgBouncer transaction pooling.
--
-- Prasyarat: aplikasi TIDAK login sebagai superuser. FORCE ROW LEVEL SECURITY membuat pemilik tabel
-- pun tunduk pada kebijakan. Tabel users sengaja tanpa RLS (login perlu mencari akun sebelum
-- identitas diketahui); aksesnya dijaga di level API (/api/v1/admin khusus admin).
-- Rollback: migrations/004_row_level_security.rollback.sql

BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE OR REPLACE FUNCTION app_role() RETURNS text LANGUAGE sql STABLE AS
  $$ SELECT current_setting('app.role', true) $$;
CREATE OR REPLACE FUNCTION app_uid() RETURNS integer LANGUAGE sql STABLE AS
  $$ SELECT NULLIF(current_setting('app.user_id', true), '')::integer $$;
-- Peran dengan akses lintas pengguna: tulis penuh / baca saja
CREATE OR REPLACE FUNCTION app_is_operator() RETURNS boolean LANGUAGE sql STABLE AS
  $$ SELECT app_role() IN ('pabrik', 'admin', 'system') $$;

-- ---------------------------------------------------------------- routes & route_stops
ALTER TABLE routes ENABLE ROW LEVEL SECURITY;      ALTER TABLE routes FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS routes_rw ON routes;
CREATE POLICY routes_rw ON routes FOR ALL
  USING (app_is_operator() OR (app_role() = 'driver' AND driver_id = app_uid()))
  WITH CHECK (app_is_operator() OR (app_role() = 'driver' AND driver_id = app_uid()));
DROP POLICY IF EXISTS routes_audit ON routes;
CREATE POLICY routes_audit ON routes FOR SELECT USING (app_role() = 'auditor');

ALTER TABLE route_stops ENABLE ROW LEVEL SECURITY; ALTER TABLE route_stops FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS stops_rw ON route_stops;
CREATE POLICY stops_rw ON route_stops FOR ALL       -- subquery ikut terfilter RLS routes
  USING (route_id IN (SELECT id FROM routes)) WITH CHECK (route_id IN (SELECT id FROM routes));

-- ---------------------------------------------------------------- harvests
ALTER TABLE harvests ENABLE ROW LEVEL SECURITY;    ALTER TABLE harvests FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS harvests_rw ON harvests;
CREATE POLICY harvests_rw ON harvests FOR ALL
  USING (
    app_is_operator()
    OR (app_role() = 'petani'   AND farmer_id = app_uid())
    OR (app_role() = 'pengepul' AND (status = 'reported' OR collector_id = app_uid()))
    OR (app_role() = 'driver'   AND id IN (SELECT harvest_id FROM route_stops WHERE harvest_id IS NOT NULL)))
  WITH CHECK (
    app_is_operator()
    OR (app_role() = 'petani'   AND farmer_id = app_uid())
    OR (app_role() = 'pengepul' AND collector_id = app_uid())
    OR (app_role() = 'driver'   AND id IN (SELECT harvest_id FROM route_stops WHERE harvest_id IS NOT NULL)));
DROP POLICY IF EXISTS harvests_audit ON harvests;
CREATE POLICY harvests_audit ON harvests FOR SELECT USING (app_role() = 'auditor');

-- ---------------------------------------------------------------- custody_events (jejak serah-terima)
ALTER TABLE custody_events ENABLE ROW LEVEL SECURITY; ALTER TABLE custody_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS custody_rw ON custody_events;
CREATE POLICY custody_rw ON custody_events FOR ALL   -- terlihat bila harvest-nya terlihat
  USING (app_is_operator() OR harvest_id IN (SELECT id FROM harvests))
  WITH CHECK (app_is_operator() OR (actor_id = app_uid() AND harvest_id IN (SELECT id FROM harvests)));
DROP POLICY IF EXISTS custody_audit ON custody_events;
CREATE POLICY custody_audit ON custody_events FOR SELECT USING (app_role() = 'auditor');

-- ---------------------------------------------------------------- dompet biochar & input batch
ALTER TABLE biochar_ledger ENABLE ROW LEVEL SECURITY; ALTER TABLE biochar_ledger FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ledger_rw ON biochar_ledger;
CREATE POLICY ledger_rw ON biochar_ledger FOR ALL
  USING (app_is_operator() OR (app_role() = 'petani' AND farmer_id = app_uid()))
  WITH CHECK (app_is_operator());                    -- petani tidak bisa mengkredit dompetnya sendiri
DROP POLICY IF EXISTS ledger_audit ON biochar_ledger;
CREATE POLICY ledger_audit ON biochar_ledger FOR SELECT USING (app_role() = 'auditor');

ALTER TABLE conversion_inputs ENABLE ROW LEVEL SECURITY; ALTER TABLE conversion_inputs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS convin_rw ON conversion_inputs;
CREATE POLICY convin_rw ON conversion_inputs FOR ALL
  USING (app_is_operator() OR (app_role() = 'petani' AND farmer_id = app_uid()))
  WITH CHECK (app_is_operator());
DROP POLICY IF EXISTS convin_audit ON conversion_inputs;
CREATE POLICY convin_audit ON conversion_inputs FOR SELECT USING (app_role() = 'auditor');

COMMIT;

-- Verifikasi cepat (harus 0 baris milik petani lain):
--   BEGIN; SELECT set_config('app.role','petani',true), set_config('app.user_id','5',true);
--   SELECT count(*) FROM harvests WHERE farmer_id <> 5;  ROLLBACK;
