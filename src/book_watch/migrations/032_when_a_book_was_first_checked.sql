-- When a book's first check finished (S85, #264): the moment examining its
-- copies first completed. Until then a new book shows at the top of the want
-- list whatever its order, and takes its place once it has a price.
-- `work.enriched_at` cannot say this, since every check clears it.
--
-- Every book already on the list has been checked, or as near as matters,
-- so each is marked now and none jumps to the top.
ALTER TABLE entry ADD COLUMN first_checked_at TEXT;

UPDATE entry SET first_checked_at = datetime('now');
