-- Rollback 020
BEGIN;
DROP INDEX IF EXISTS uq_wsm_harvest_in;
COMMIT;
