-- What we have learned from Open Library, so we never ask twice.
--
-- This is the notebook described in decision 7 as amended: one line per ISBN
-- we have met in a listing, written the first time we meet it. Matching reads
-- this table and never Open Library.
--
-- It holds only numbers seen in the wild. An earlier plan downloaded every
-- edition of a book when it was added; measured against what sellers actually
-- declare, roughly 80% of that was never seen for sale, and Open Library
-- returns editions in record-creation order so any cap on the download was an
-- arbitrary slice of 4,042.

CREATE TABLE openlibrary_edition (
    isbn            TEXT    PRIMARY KEY,

    -- 1: Open Library holds this number. 0: it told us it does not.
    --
    -- A recorded 0 is an answer, not a failure, and it is why this column
    -- exists rather than the row simply being absent. Decision 33: a number
    -- Open Library does not hold must not exclude a listing, and re-asking on
    -- every poll is the behaviour they ask people not to have.
    --
    -- Failing to *reach* Open Library writes nothing at all. That case has to
    -- stay distinguishable from this one.
    found           INTEGER NOT NULL CHECK (found IN (0, 1)),

    title           TEXT,

    -- A reference for looking something up by hand, never identity: the same
    -- book is filed under several of these. Nothing may join on it.
    work_id         TEXT,

    publisher       TEXT,

    -- Open Library's dates are not dates. "2003", "April 1, 1994" and "xxxx"
    -- all occur, so this stays the string they sent.
    published       TEXT,

    physical_format TEXT,

    asked_at        TEXT    NOT NULL DEFAULT (datetime('now')),

    -- A found record without a title would be indistinguishable from a miss
    -- at read time, and the title is the whole basis of the matching rule.
    CHECK (found = 0 OR title IS NOT NULL)
);
