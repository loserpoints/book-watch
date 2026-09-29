-- Each morning's check of the whole list (S37, #141).
--
-- Kept so the want list can say when the last run failed, stopped at the
-- Open Library ceiling, or did not happen, and so a run that a restart
-- interrupted is known to be missing and is run again.
--
-- `outcome` is NULL while the run is going, then 'ok', 'failed' (at least
-- one book could not be searched) or 'throttled' (examining stopped at the
-- Open Library ceiling). `openlibrary_spent` is what the run cost against
-- that ceiling, which is the number to watch as the list grows.
CREATE TABLE daily_run (
    id                INTEGER PRIMARY KEY,
    started_at        TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at       TEXT,
    outcome           TEXT,
    books             INTEGER NOT NULL DEFAULT 0,
    failed            INTEGER NOT NULL DEFAULT 0,
    openlibrary_spent INTEGER NOT NULL DEFAULT 0
);
