-- What I bought, and which copy I last opened (S71, #223).
--
-- Marking a book bought takes its entry off the list the way removing does,
-- so everything that already stops for a removed book, the daily check,
-- Check all and the morning email, stops for a bought one without having to
-- learn a new state. What is kept is a record of the purchase, written once,
-- with what it needs to be shown after the entry has gone.
--
-- Additive: code from before this migration ignores the table and the
-- columns, and a rollback leaves the purchases where they are.
CREATE TABLE purchase (
    id         INTEGER PRIMARY KEY,
    -- The book in the abstract. Null if the work is ever deleted, since the
    -- record stands on the copies of the facts below.
    work_id    INTEGER REFERENCES work(id) ON DELETE SET NULL,
    title      TEXT    NOT NULL,
    author     TEXT,
    -- Open Library's cover id, as the entry had it. Null shows a placeholder.
    cover_id   INTEGER,
    -- Strings, as everywhere else money is stored.
    paid       TEXT    NOT NULL,
    currency   TEXT    NOT NULL,
    -- 'ebay' or 'abebooks', or null with `shop` naming anywhere else.
    marketplace TEXT,
    shop       TEXT,
    -- The day it was bought, as the person picked it: YYYY-MM-DD.
    bought_on  TEXT    NOT NULL,
    -- The book's limit when it was bought, so what was paid can be judged
    -- against it. Both or neither, as on the entry.
    ceiling    TEXT,
    ceiling_currency TEXT,
    recorded_at TEXT   NOT NULL DEFAULT (datetime('now')),

    CHECK ((marketplace IS NULL) != (shop IS NULL)),
    CHECK ((ceiling IS NULL) = (ceiling_currency IS NULL))
);

-- The copy of this book last opened from the app, so marking it bought can
-- offer that copy's marketplace and price.
ALTER TABLE entry ADD COLUMN opened_marketplace TEXT;
ALTER TABLE entry ADD COLUMN opened_item_id TEXT;
ALTER TABLE entry ADD COLUMN opened_at TEXT;
