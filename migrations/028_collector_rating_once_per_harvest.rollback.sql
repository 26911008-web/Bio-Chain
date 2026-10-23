BEGIN;
DROP INDEX IF EXISTS uq_collector_rating_farmer_harvest;
DELETE FROM schema_migrations WHERE version = '028_collector_rating_once_per_harvest';
COMMIT;
