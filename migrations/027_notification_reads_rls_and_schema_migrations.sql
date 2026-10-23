-- Bio-Chain v2 · Migrasi 027 — Status baca notifikasi per pengguna, RLS notifikasi, catatan versi migrasi
-- (audit 23 Okt 2026, docs/29). Jalankan sebagai pemilik skema (biochain_owner):
--   psql "$OWNER_URL" -v ON_ERROR_STOP=1 -f migrations/027_notification_reads_rls_and_schema_migrations.sql
-- Rollback: migrations/027_notification_reads_rls_and_schema_migrations.rollback.sql

BEGIN;
SET LOCAL lock_timeout = '5s';

-- 1. Status baca per pengguna untuk notifikasi siaran / milik orang lain (notifications.is_read hanya untuk pemilik)
CREATE TABLE IF NOT EXISTS notification_reads (
  user_id          integer     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  notification_id  integer     NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
  read_at          timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_notification_reads PRIMARY KEY (user_id, notification_id)
);
CREATE INDEX IF NOT EXISTS ix_notification_reads_notification_id ON notification_reads (notification_id);

-- 2. RLS notifikasi: notifikasi bertuan hanya untuk pemiliknya; siaran per peran; admin/auditor/sistem lihat semua.
--    Semua identitas boleh MEMBUAT notifikasi (aksi petani memberi tahu pengepul, dst.).
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;  ALTER TABLE notifications FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS notif_read ON notifications;
CREATE POLICY notif_read ON notifications FOR SELECT USING (
  app_role() IN ('admin', 'auditor', 'system')
  OR user_id = app_uid()
  OR (user_id IS NULL AND target_role IN (app_role(), 'all')));
DROP POLICY IF EXISTS notif_insert ON notifications;
CREATE POLICY notif_insert ON notifications FOR INSERT WITH CHECK (app_role() IS NOT NULL AND app_role() <> '');
DROP POLICY IF EXISTS notif_update ON notifications;
CREATE POLICY notif_update ON notifications FOR UPDATE
  USING (user_id = app_uid() OR app_role() IN ('admin', 'system'))
  WITH CHECK (user_id = app_uid() OR app_role() IN ('admin', 'system'));
DROP POLICY IF EXISTS notif_delete ON notifications;
CREATE POLICY notif_delete ON notifications FOR DELETE USING (app_role() IN ('admin', 'system'));

ALTER TABLE notification_reads ENABLE ROW LEVEL SECURITY;  ALTER TABLE notification_reads FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS nread_own ON notification_reads;
CREATE POLICY nread_own ON notification_reads FOR ALL
  USING (user_id = app_uid() OR app_role() IN ('admin', 'system'))
  WITH CHECK (user_id = app_uid() OR app_role() IN ('admin', 'system'));


-- 3. Catatan versi migrasi (dulu tidak ada: status DB live hanya bisa ditebak dari keberadaan objek)
CREATE TABLE IF NOT EXISTS schema_migrations (
  version     text        PRIMARY KEY,
  applied_at  timestamptz NOT NULL DEFAULT now(),
  note        text
);
INSERT INTO schema_migrations (version, note) VALUES
  ('026_audit_indexes_and_role_timeouts', 'audit 23 Okt 2026'),
  ('027_notification_reads_rls_and_schema_migrations', 'audit 23 Okt 2026')
ON CONFLICT (version) DO NOTHING;
-- Hak hanya untuk peran aplikasi (bukan PUBLIC: di Supabase itu termasuk anon/authenticated PostgREST)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'biochain_app') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON notification_reads TO biochain_app;
    GRANT SELECT ON schema_migrations TO biochain_app;
  END IF;
END $$;

COMMIT;
