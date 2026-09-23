-- A want-list entry names a book, and says which hunt it is on.
--
-- This supersedes the model in 001, where one row was one ISBN. Decision 26
-- called that a stopgap and named the cost: searching one ISBN finds copies of
-- one edition, so someone who would happily take any printing sees a fraction
-- of what is for sale. Decision 33 measured the way out of that, and this is
-- the shape it needs.
--
-- Three tables, because the old `book` meant three things at once:
--
--   work     the book in the abstract — Stoner, by John Williams
--   edition  one printing of it — NYRB Classics, 2006, trade paperback
--   entry    a row on the want-list, pointing at one of the two
--
-- Existing rows are carried across rather than dropped. There is real data on
-- the mounted volume, and this is the first change in this project that could
-- destroy any.

CREATE TABLE work (
    id       INTEGER PRIMARY KEY,

    -- Nullable. A book added by number alone has no title until Open Library
    -- or a person supplies one, and writing the number here instead would put
    -- a thirteen-digit heading on the want-list.
    --
    -- What has to be searchable is an entry, not a work, and an entry always
    -- knows what it was added with. See `Entry.search_query`.
    title    TEXT,

    -- Null until Open Library or a person supplies one. Decision 33: the eBay
    -- search uses title and author together, so this is worth having.
    author   TEXT,

    -- A reference for looking something up by hand, and nothing else.
    --
    -- Decision 33: Open Library files the same book under several of these —
    -- Crash under five, Stoner under five — and a title search returns two
    -- separate Pride and Prejudice works. Anything that joined on this, or
    -- treated it as unique per book, would be quietly wrong. It is not
    -- UNIQUE, deliberately.
    openlibrary_work_id TEXT,

    -- When a full enrichment pass last finished for this work. NULL means one
    -- has never completed, which is what the want-list reads to say it is
    -- still working.
    --
    -- Decision 7 as amended: a new book costs 10-15 Open Library requests and
    -- they cannot run while someone waits, so a book is added and shown
    -- immediately with this still null.
    enriched_at TEXT
);

CREATE TABLE edition (
    id        INTEGER PRIMARY KEY,
    work_id   INTEGER NOT NULL REFERENCES work(id) ON DELETE CASCADE,

    -- Nullable, and this is the point rather than an oversight. The brief
    -- names pre-1970 books as a real category and they have no ISBN at all —
    -- a 1965 first edition of Stoner is exactly the thing a collector wants
    -- and exactly the thing an ISBN-shaped model cannot hold.
    --
    -- UNIQUE, with SQLite's rule that NULLs do not collide: one row per real
    -- number, any quantity of editions that never had one.
    isbn      TEXT UNIQUE,

    publisher TEXT,

    -- The string Open Library sent. Its dates are not dates: "2003",
    -- "April 1, 1994" and "xxxx" all occur.
    published TEXT,

    physical_format TEXT
);

CREATE INDEX edition_by_work ON edition (work_id);

CREATE TABLE entry (
    id      INTEGER PRIMARY KEY,
    work_id INTEGER NOT NULL REFERENCES work(id) ON DELETE CASCADE,

    -- Which hunt this entry is on. Decision 33 measured that the two share a
    -- pipeline and differ in what an entry points at, so this is decided here
    -- rather than migrated over live rows a second time later.
    --
    -- Only 'reader' is written today. 'collector' is storable and nothing
    -- reads it — the surface for it waits on its own labelling exercise,
    -- because it was measured on six listings and first-edition points live
    -- in photographs rather than in any catalogue.
    hunt    TEXT NOT NULL CHECK (hunt IN ('reader', 'collector')),

    -- A collector wants one printing; a reader will take any. So this is
    -- required for one and forbidden for the other, which the CHECK below
    -- says rather than leaving to the code.
    edition_id INTEGER REFERENCES edition(id) ON DELETE RESTRICT,

    -- What was typed, when it was not an ISBN. Decision 29: some books never
    -- had one, and those entries are searched for as written.
    search_text TEXT,

    added_at TEXT NOT NULL DEFAULT (datetime('now')),

    CHECK (
        (hunt = 'reader'    AND edition_id IS NULL)
     OR (hunt = 'collector' AND edition_id IS NOT NULL)
    )
);

-- One reader entry per book, one collector entry per edition. A partial index
-- rather than a UNIQUE column, because wanting both a reading copy and a
-- particular printing of the same book is not a duplicate — it is the two
-- hunts working as intended.
CREATE UNIQUE INDEX one_reader_entry_per_work ON entry (work_id)
    WHERE hunt = 'reader';
CREATE UNIQUE INDEX one_collector_entry_per_edition ON entry (edition_id)
    WHERE hunt = 'collector';

-- Carry the existing rows across.
--
-- Ids are preserved: the want-list links to /book/{id}, and a migration that
-- silently repointed every link would be a broken bookmark for every book on
-- the list.
--
-- A stored value is a real ISBN if it is thirteen digits. Anything else is an
-- override typed by hand under decision 29 — it becomes the entry's search
-- text and gets no edition row, because it is not one.

INSERT INTO work (id, title)
SELECT id, NULLIF(TRIM(title), '') FROM book;

INSERT INTO edition (work_id, isbn)
SELECT id, isbn FROM book
WHERE length(isbn) = 13 AND isbn NOT GLOB '*[^0-9]*';

INSERT INTO entry (id, work_id, hunt, edition_id, search_text, added_at)
SELECT
    id,
    id,
    'reader',
    NULL,
    CASE
        WHEN length(isbn) = 13 AND isbn NOT GLOB '*[^0-9]*' THEN NULL
        ELSE isbn
    END,
    added_at
FROM book;

DROP TABLE book;
