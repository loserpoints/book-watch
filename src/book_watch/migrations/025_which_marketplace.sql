-- Which marketplace a listing is on (S65, #228).
--
-- Until now every listing was an eBay listing, so a listing was its eBay item
-- id. A second marketplace has ids of its own, and a listing is identified by
-- the pair: the marketplace and its id there. The pair is the key everywhere a
-- listing is, rather than trusting that two marketplaces' ids never look
-- alike.
--
-- SQLite cannot change a table's key in place, so the five tables keyed by a
-- listing are rebuilt with every row, and every existing row is eBay's. No
-- foreign key points at any of them, so dropping the old table is safe with
-- foreign keys on.
--
-- Not additive: code from before this migration does not run against the
-- rebuilt tables. Rolling back past it means restoring the database too. See
-- the runbook.

-- A sweep is one search of one marketplace for one book. "What is listed now"
-- is the newest sweep of a marketplace in a scope, so a sweep of one
-- marketplace never hides another's copies.
ALTER TABLE sweep ADD COLUMN marketplace TEXT NOT NULL DEFAULT 'ebay'
    CHECK (marketplace IN ('ebay', 'abebooks'));

DROP INDEX sweep_by_work_and_scope;
CREATE INDEX sweep_by_work_marketplace_scope ON sweep (work_id, marketplace, scope, id);


CREATE TABLE copy_new (
    marketplace TEXT NOT NULL DEFAULT 'ebay'
        CHECK (marketplace IN ('ebay', 'abebooks')),
    -- The listing's id on its marketplace. The same copy can be for sale
    -- against more than one book on the want-list, so the key includes the
    -- book.
    item_id     TEXT NOT NULL,
    work_id     INTEGER NOT NULL REFERENCES work(id) ON DELETE CASCADE,

    title       TEXT NOT NULL,
    url         TEXT NOT NULL,

    -- Money is stored as the string the marketplace sent: "8.99" parsed into a
    -- float and written back is a different number, and this column is read to
    -- add shipping to a price.
    price       TEXT NOT NULL,
    currency    TEXT NOT NULL,
    -- Three-valued on purpose: null means the marketplace said nothing, which
    -- is not the same as free.
    shipping    TEXT,

    -- The marketplace's own words, kept as they came.
    condition   TEXT,
    seller      TEXT,
    thumbnail   TEXT,
    -- eBay's product id. Null on other marketplaces, which have none.
    epid        TEXT,
    -- When eBay says the listing was first listed. Null on marketplaces that
    -- give no date.
    listed_at   TEXT,

    seen_at       TEXT NOT NULL DEFAULT (datetime('now')),
    first_seen_at TEXT,
    last_seen_at  TEXT,
    located_in    TEXT,
    -- On eBay's scale whatever the marketplace: another marketplace's
    -- condition is mapped onto eBay's codes when the copy is stored. See the
    -- matching rules.
    condition_id  TEXT,
    buying_options TEXT,

    PRIMARY KEY (marketplace, item_id, work_id)
);

INSERT INTO copy_new (
    item_id, work_id, title, url, price, currency, shipping, condition, seller,
    thumbnail, epid, listed_at, seen_at, first_seen_at, last_seen_at,
    located_in, condition_id, buying_options
)
SELECT
    item_id, work_id, title, url, price, currency, shipping, condition, seller,
    thumbnail, epid, listed_at, seen_at, first_seen_at, last_seen_at,
    located_in, condition_id, buying_options
FROM copy;

DROP TABLE copy;
ALTER TABLE copy_new RENAME TO copy;
CREATE INDEX copy_by_work ON copy (work_id);


CREATE TABLE copy_seen_new (
    marketplace TEXT    NOT NULL DEFAULT 'ebay'
        CHECK (marketplace IN ('ebay', 'abebooks')),
    item_id  TEXT    NOT NULL,
    work_id  INTEGER NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    scope    TEXT    NOT NULL CHECK (scope IN ('us', 'everywhere')),
    sweep_id INTEGER NOT NULL REFERENCES sweep(id) ON DELETE CASCADE,

    PRIMARY KEY (marketplace, item_id, work_id, scope)
);

INSERT INTO copy_seen_new (item_id, work_id, scope, sweep_id)
SELECT item_id, work_id, scope, sweep_id FROM copy_seen;

DROP TABLE copy_seen;
ALTER TABLE copy_seen_new RENAME TO copy_seen;
CREATE INDEX copy_seen_by_sweep ON copy_seen (work_id, scope, sweep_id);


CREATE TABLE sighting_new (
    id       INTEGER PRIMARY KEY,
    marketplace TEXT NOT NULL DEFAULT 'ebay'
        CHECK (marketplace IN ('ebay', 'abebooks')),
    item_id  TEXT    NOT NULL,
    work_id  INTEGER NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    sweep_id INTEGER NOT NULL REFERENCES sweep(id) ON DELETE CASCADE,

    -- Strings, as everywhere else money is stored: "8.99" parsed
    -- into a float and written back is a different number.
    price    TEXT    NOT NULL,
    currency TEXT    NOT NULL,
    -- Three-valued as in the copy table: null means the marketplace said
    -- nothing, which is not the same as free.
    shipping TEXT,

    -- Kept because a seller re-grading a copy is a price-relevant event and
    -- costs one short string to notice.
    condition TEXT,

    UNIQUE (marketplace, item_id, work_id, sweep_id)
);

INSERT INTO sighting_new (
    id, item_id, work_id, sweep_id, price, currency, shipping, condition
)
SELECT id, item_id, work_id, sweep_id, price, currency, shipping, condition
FROM sighting;

DROP TABLE sighting;
ALTER TABLE sighting_new RENAME TO sighting;
CREATE INDEX sighting_by_copy ON sighting (work_id, marketplace, item_id, sweep_id);


CREATE TABLE emailed_copy_new (
    marketplace TEXT NOT NULL DEFAULT 'ebay'
        CHECK (marketplace IN ('ebay', 'abebooks')),
    item_id    TEXT NOT NULL,
    work_id    INTEGER NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    emailed_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (marketplace, item_id, work_id)
);

INSERT INTO emailed_copy_new (item_id, work_id, emailed_at)
SELECT item_id, work_id, emailed_at FROM emailed_copy;

DROP TABLE emailed_copy;
ALTER TABLE emailed_copy_new RENAME TO emailed_copy;


-- What a listing declares about itself. One row per listing, whichever book
-- it was found for: a fact about the listing, not about the pairing.
CREATE TABLE listing_declaration_new (
    marketplace TEXT NOT NULL DEFAULT 'ebay'
        CHECK (marketplace IN ('ebay', 'abebooks')),
    item_id     TEXT NOT NULL,

    -- Normalized to ISBN-13 where the seller gave anything parseable. Null is
    -- ordinary.
    isbn        TEXT,

    -- Displayed, never matched on.
    format      TEXT,
    publisher   TEXT,
    published   TEXT,

    -- Display only, and this is a rule rather than a preference: eBay's
    -- categories are localized and overlapping, and an early matching rule
    -- that excluded on this lost seven true listings.
    category    TEXT,

    fetched_at  TEXT NOT NULL DEFAULT (datetime('now')),
    author      TEXT,
    captured_by INTEGER NOT NULL DEFAULT 1,
    condition_note TEXT,
    photos      TEXT,

    PRIMARY KEY (marketplace, item_id)
);

INSERT INTO listing_declaration_new (
    item_id, isbn, format, publisher, published, category, fetched_at, author,
    captured_by, condition_note, photos
)
SELECT
    item_id, isbn, format, publisher, published, category, fetched_at, author,
    captured_by, condition_note, photos
FROM listing_declaration;

DROP TABLE listing_declaration;
ALTER TABLE listing_declaration_new RENAME TO listing_declaration;
CREATE INDEX listing_declaration_by_isbn ON listing_declaration (isbn);
CREATE INDEX listing_declaration_by_capture ON listing_declaration (captured_by);
