-- A refresh stops throwing away what the last one saw.
--
-- `copies.store()` deleted every row for a book and reinserted what eBay had
-- just returned. The page's job made that defensible — what is for sale now
-- is the question it answers — but it meant the record of what a book has
-- cost was being destroyed on every refresh, and J5's cheapest way to judge
-- a price is our own observed history. The clock had never started.
--
-- It is the same mistake S15 fixed pointing the other way: that one kept
-- conclusions and threw away observations. So does this.

-- One row per `store()` call. Everything about "the latest sweep" hangs off
-- this id rather than off a timestamp, because two writes in the same second
-- are indistinguishable by time and are different sweeps. An id is a fact.
CREATE TABLE sweep (
    id      INTEGER PRIMARY KEY,
    work_id INTEGER NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX sweep_by_work ON sweep (work_id, id);

-- What a copy cost at a moment it was seen, written only when it differs
-- from what it cost the last time we looked.
--
-- A row means "from this sweep onward, this is the price", and holds until
-- the next row for the same copy. Recording an unchanged price every sweep
-- would be the same fact written daily forever and answers nothing extra.
--
-- The one case that is not a price change and still needs a row: a copy that
-- was absent and has come back. Without it, a gap with the same price either
-- side reads as one continuous offer, which is a claim we cannot support.
-- `copies.store()` writes a row for a reappearance for that reason.
CREATE TABLE sighting (
    id       INTEGER PRIMARY KEY,
    item_id  TEXT    NOT NULL,
    work_id  INTEGER NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    sweep_id INTEGER NOT NULL REFERENCES sweep(id) ON DELETE CASCADE,

    -- Strings, as everywhere else money is stored. Decision 1: "8.99" parsed
    -- into a float and written back is a different number.
    price    TEXT    NOT NULL,
    currency TEXT    NOT NULL,
    -- Three-valued as in the copy table: null means eBay said nothing, which
    -- is not the same as free.
    shipping TEXT,

    -- Kept because a seller re-grading a copy is a price-relevant event and
    -- costs one short string to notice.
    condition TEXT,

    UNIQUE (item_id, work_id, sweep_id)
);

CREATE INDEX sighting_by_copy ON sighting (work_id, item_id, sweep_id);

-- A copy is no longer deleted when it stops appearing, so the row needs to
-- say when it was first and last seen, and in which sweep.
--
-- No `gone_at` column. "Gone" is `last_sweep_id` not being the work's newest
-- sweep, and `last_seen_at` already holds the fact worth keeping. A stored
-- flag would be a third thing to keep consistent with those two.
ALTER TABLE copy ADD COLUMN first_seen_at TEXT;
ALTER TABLE copy ADD COLUMN last_seen_at  TEXT;
ALTER TABLE copy ADD COLUMN last_sweep_id INTEGER REFERENCES sweep(id);

-- Existing rows were all written by the last sweep of their book, because
-- until now a sweep deleted everything before it. `seen_at` is when that
-- happened, so it is both bounds.
UPDATE copy SET first_seen_at = seen_at, last_seen_at = seen_at;

-- That sweep gets a row, rather than existing copies being left pointing at
-- nothing. It is not invented: `work.copies_fetched_at` is precisely when we
-- last asked eBay about this book, which is what a sweep is. Without it, the
-- page — which shows the newest sweep — would show an empty book until
-- somebody pressed Look again.
INSERT INTO sweep (work_id, at)
SELECT DISTINCT copy.work_id,
       COALESCE(work.copies_fetched_at, copy.seen_at, datetime('now'))
  FROM copy JOIN work ON work.id = copy.work_id;

UPDATE copy
   SET last_sweep_id = (
       SELECT sweep.id FROM sweep WHERE sweep.work_id = copy.work_id
     ORDER BY sweep.id DESC LIMIT 1
   );

-- The price each of those copies is at right now is an observation we paid
-- for and would otherwise never be written down. A copy's first sighting is
-- always a change — from nothing — so this is the same rule the code
-- follows, applied once to what already exists.
INSERT INTO sighting (item_id, work_id, sweep_id, price, currency, shipping, condition)
SELECT item_id, work_id, last_sweep_id, price, currency, shipping, condition
  FROM copy
 WHERE last_sweep_id IS NOT NULL;
