-- Where a copy physically is, and which question each sweep asked.
--
-- `EBAY_US` is the US *site*, not US sellers: it lists overseas sellers who
-- ship here, which is why a "(UK IMPORT)" copy from a British seller appears
-- in results. Measured on a real search for *State of Grace* — unfiltered
-- returned 17 listings of which one was in Great Britain, and the same search
-- filtered to US item location returned 17 US listings, one of which the
-- unfiltered search never returned at all. The import did not add a row; it
-- displaced a US copy out of the fifty slots we get.

-- Two-letter country code. Null means eBay did not say, which is not
-- "overseas" — a copy is never called an import on a missing field.
ALTER TABLE copy ADD COLUMN located_in TEXT;

-- Which question this sweep asked. 'us' filtered to US item location;
-- 'everywhere' sent no location filter.
--
-- **This is not decoration.** A copy absent from the newest sweep is treated
-- as no longer for sale, and that only holds while consecutive sweeps ask the
-- same question. Same reasoning as the capture version in migration 013,
-- pointed at queries instead of fields.
--
-- Existing rows are 'everywhere', which is the truth rather than a
-- convenience: every sweep before this one sent no location filter.
ALTER TABLE sweep ADD COLUMN scope TEXT NOT NULL DEFAULT 'everywhere'
    CHECK (scope IN ('us', 'everywhere'));

CREATE INDEX sweep_by_work_and_scope ON sweep (work_id, scope, id);

-- The last sweep of each scope that saw this copy.
--
-- `copy.last_sweep_id` held one pointer, which was right while every sweep
-- asked the same question and silently wrong the moment two scopes existed: a
-- US sweep overwrote the pointer, and the copy then vanished from the
-- everywhere view although that sweep had seen it. Membership is per scope,
-- so it cannot live in a single column.
--
-- One row per copy per scope rather than per copy per sweep. Which sweeps saw
-- a copy is a fact we could keep, and keeping it would cost a row on every
-- visit for every copy — the unbounded growth decision 44 avoided by logging
-- only changes. What the page needs is the *latest* per scope, which is
-- bounded at two rows a copy.
CREATE TABLE copy_seen (
    item_id  TEXT    NOT NULL,
    work_id  INTEGER NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    scope    TEXT    NOT NULL CHECK (scope IN ('us', 'everywhere')),
    sweep_id INTEGER NOT NULL REFERENCES sweep(id) ON DELETE CASCADE,

    PRIMARY KEY (item_id, work_id, scope)
);

CREATE INDEX copy_seen_by_sweep ON copy_seen (work_id, scope, sweep_id);

-- Every existing copy was found by an unfiltered sweep, because that is all
-- there was.
INSERT INTO copy_seen (item_id, work_id, scope, sweep_id)
SELECT item_id, work_id, 'everywhere', last_sweep_id
  FROM copy
 WHERE last_sweep_id IS NOT NULL;

-- Dropped rather than left to rot. Two places holding the same fact, one of
-- them no longer maintained, is exactly what migration 010 had to untangle.
ALTER TABLE copy DROP COLUMN last_sweep_id;
