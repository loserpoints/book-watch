-- Which cover each book shows. Decision 56.
--
-- Only the id is stored. The image stays on Open Library's cover server and
-- the page points at it, which is what their covers API asks for: it is meant
-- for displaying covers, not for downloading them.
--
-- A work's cover has three states, and they are different news:
--
--   cover_asked_at NULL                      nobody has looked yet
--   cover_asked_at set, cover_id NULL        Open Library holds no cover
--   cover_id set                             this one
--
-- Collapsing the first two would draw the "no cover" placeholder over every
-- book added before this migration — a confident claim about something we
-- never asked. The same reasoning gave a condition class three answers
-- rather than two (decision 52).

ALTER TABLE work ADD COLUMN cover_id INTEGER;

-- Whose cover `cover_id` is. 'work' is Open Library's pick for the book as a
-- whole. 'edition' is the cover of the number the book was added by, standing
-- in because learning the work's would have cost a second request while
-- somebody waited.
ALTER TABLE work ADD COLUMN cover_from TEXT
    CHECK (cover_from IN ('work', 'edition'));

ALTER TABLE work ADD COLUMN cover_asked_at TEXT;

-- A collector hunts one printing, so it shows that printing's cover. Nothing
-- writes collector entries yet (*Two kinds of hunt* does); the column is here
-- so the rule that reads it can be written and tested once.
ALTER TABLE edition ADD COLUMN cover_id INTEGER;
