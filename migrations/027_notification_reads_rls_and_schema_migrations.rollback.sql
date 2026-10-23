-- Rollback migrasi 027
BEGIN;
DROP POLICY IF EXISTS notif_read ON notifications;
DROP POLICY IF EXISTS notif_insert ON notifications;
DROP POLICY IF EXISTS notif_update ON notifications;
DROP POLICY IF EXISTS notif_delete ON notifications;
ALTER TABLE notifications NO FORCE ROW LEVEL SECURITY;
ALTER TABLE notifications DISABLE ROW LEVEL SECURITY;
DROP TABLE IF EXISTS notification_reads;
DELETE FROM schema_migrations WHERE version = '027_notification_reads_rls_and_schema_migrations';
COMMIT;
