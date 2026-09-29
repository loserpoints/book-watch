-- When each book was last opened, so copies that appeared since can be
-- marked new (S39, #142).
--
-- Two columns, because the page marks copies against the visit *before* this
-- one: `looked_at` is when this visit began and `looked_before` when the
-- previous one did. Opening a book again within a short window is the same
-- visit, so tapping a chip on the page does not clear what it just marked.
-- NULL in both means the book was never opened, and nothing is new.
ALTER TABLE entry ADD COLUMN looked_at TEXT;
ALTER TABLE entry ADD COLUMN looked_before TEXT;
