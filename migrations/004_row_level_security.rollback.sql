-- Rollback migrasi 004 — mematikan RLS & menghapus kebijakan. Tidak ada data yang berubah.
BEGIN;
SET LOCAL lock_timeout = '5s';
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['routes','route_stops','harvests','custody_events','biochar_ledger','conversion_inputs'] LOOP
    EXECUTE format('ALTER TABLE %I NO FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I DISABLE ROW LEVEL SECURITY', t);
  END LOOP;
END $$;
DROP POLICY IF EXISTS routes_rw ON routes;           DROP POLICY IF EXISTS routes_audit ON routes;
DROP POLICY IF EXISTS stops_rw ON route_stops;
DROP POLICY IF EXISTS harvests_rw ON harvests;       DROP POLICY IF EXISTS harvests_audit ON harvests;
DROP POLICY IF EXISTS custody_rw ON custody_events;  DROP POLICY IF EXISTS custody_audit ON custody_events;
DROP POLICY IF EXISTS ledger_rw ON biochar_ledger;   DROP POLICY IF EXISTS ledger_audit ON biochar_ledger;
DROP POLICY IF EXISTS convin_rw ON conversion_inputs; DROP POLICY IF EXISTS convin_audit ON conversion_inputs;
DROP FUNCTION IF EXISTS app_is_operator();
DROP FUNCTION IF EXISTS app_uid();
DROP FUNCTION IF EXISTS app_role();
COMMIT;
