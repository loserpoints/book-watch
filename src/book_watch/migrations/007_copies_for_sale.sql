-- Copies offered for sale, as last seen.
--
-- Decision 30 as amended: the page reads this store, and a refresh writes to
-- it. Re-searching eBay on every page view was the stopgap M1 shipped, and it
-- is not the model.
--
-- Measured, which is what turns that from a preference into a constraint: one
-- eBay search takes about 1.8 seconds and one per-listing detail call about
-- 0.51. A page that fetched details for its own results would take 25 seconds
-- for fifty of them. So the page spends one search at most, and everything
-- else it shows is something already written down.
--
-- "Copy" rather than "listing" because that is what it is: one object, in one
-- seller's hands, at one price. The same edition has many.

CREATE TABLE copy (
    -- eBay's item id. The same copy can be for sale against more than one
    -- book on the want-list — two entries for the same work — so the key is
    -- the pair rather than the item alone.
    item_id     TEXT NOT NULL,
    work_id     INTEGER NOT NULL REFERENCES work(id) ON DELETE CASCADE,

    title       TEXT NOT NULL,
    url         TEXT NOT NULL,

    -- Money is stored as the string eBay sent. Decision 1's reasoning applied
    -- to storage: "8.99" parsed into a float and written back is a different
    -- number, and this column is read to add shipping to a price.
    price       TEXT NOT NULL,
    currency    TEXT NOT NULL,
    -- Three-valued on purpose, as in the search client: null means eBay said
    -- nothing, which is not the same as free.
    shipping    TEXT,

    condition   TEXT,
    seller      TEXT,
    thumbnail   TEXT,
    epid        TEXT,
    listed_at   TEXT,

    seen_at     TEXT NOT NULL DEFAULT (datetime('now')),

    PRIMARY KEY (item_id, work_id)
);

CREATE INDEX copy_by_work ON copy (work_id);

-- When this book's copies were last fetched from a marketplace. Null means
-- never, which is what the page reads to decide whether it owes a search.
ALTER TABLE work ADD COLUMN copies_fetched_at TEXT;
