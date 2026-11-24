SELECT id, name FROM users WHERE id = 1;
DELETE FROM logs WHERE created_at < '2025-01-01';
UPDATE accounts SET active = 0 WHERE id = 2;
DROP TABLE IF EXISTS temp_data;
