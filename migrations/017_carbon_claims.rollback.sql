-- Rollback 017 — hapus alur klaim karbon (data klaim ikut terhapus; serah-terima biochar tidak tersentuh).
BEGIN;
DROP TABLE IF EXISTS carbon_claim_items;
DROP TABLE IF EXISTS carbon_claims;
COMMIT;
