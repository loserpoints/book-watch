-- The "from" price as it stood just before the latest check (S72, #164).
--
-- The want list shows which way a check moved a book's "from" price, so each
-- check notes the price before it stores anything. `checked_from_at` is when
-- the note was taken: set with no price means the book had none before the
-- check, which is different from never having been noted.
--
-- Additive: code from before this migration ignores the columns.
ALTER TABLE entry ADD COLUMN checked_from TEXT;
ALTER TABLE entry ADD COLUMN checked_from_currency TEXT;
ALTER TABLE entry ADD COLUMN checked_from_at TEXT;
