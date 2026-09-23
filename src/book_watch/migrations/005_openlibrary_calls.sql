-- Every request this app makes to Open Library, one row each.
--
-- Two jobs. The first is simply that somebody can answer "how much have we
-- used?" — before this, neither the app nor its author nor anyone reading the
-- code could say. The second is the ceiling in `budget.py`, which needs
-- something to count.
--
-- Open Library publishes no daily figure; the limit they enforce is per
-- second (decision 39). So this is not compliance. It is a bound on our own
-- bugs: paced at 1.5s a runaway loop makes 2,400 calls a day, and a want-list
-- being filled in by hand makes about 160.

CREATE TABLE openlibrary_call (
    id       INTEGER PRIMARY KEY,
    -- Which endpoint, so a runaway can be identified rather than just counted.
    endpoint TEXT NOT NULL,
    at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX openlibrary_call_by_time ON openlibrary_call (at);
