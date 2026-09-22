-- The want-list.
--
-- One row is one ISBN I would accept a copy of. That is deliberately not the
-- same as "one book": a reading copy and a collectible edition of the same
-- title are different ISBNs, and until edition resolution lands a title I
-- would take in any edition means several rows. See docs/decisions.md entry
-- 26 for why that is the right stopgap rather than the model.
--
-- No `mode` column. M1 does not distinguish reading from collectible, and a
-- column nothing reads is a column that silently stops meaning anything.
-- It arrives in the migration that first needs it.

CREATE TABLE book (
    id       INTEGER PRIMARY KEY,
    -- UNIQUE because adding the same ISBN twice is a mistake rather than an
    -- intention, and the database is a better place to say so than the form.
    isbn     TEXT NOT NULL UNIQUE,
    -- Nullable: typed in by hand today, filled in by Open Library later.
    title    TEXT,
    added_at TEXT NOT NULL DEFAULT (datetime('now'))
);
