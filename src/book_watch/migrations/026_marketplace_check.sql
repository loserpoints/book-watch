-- How each book's last check of a marketplace went (S66, #229).
--
-- A sweep records what a search found, so a search that found nothing usable
-- leaves no sweep, and the copies from the last good one stay listed as of
-- then. This records the outcome itself, so the book page can say when a
-- marketplace's check failed or came back empty. eBay's failures are already
-- shown where they happen; this is read for marketplaces read from their
-- pages, where a page can change shape without notice.
--
-- One row per book and marketplace, replaced by each check. The reason is for
-- the log and for looking up by hand, never shown whole.
CREATE TABLE marketplace_check (
    work_id     INTEGER NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    marketplace TEXT    NOT NULL CHECK (marketplace IN ('ebay', 'abebooks')),
    checked_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    outcome     TEXT    NOT NULL CHECK (outcome IN ('ok', 'empty', 'failed')),
    reason      TEXT,

    PRIMARY KEY (work_id, marketplace)
);
