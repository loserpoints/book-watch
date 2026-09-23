-- What a seller said about their own copy.
--
-- eBay's search response does not carry any of this; it takes a second call
-- per listing. That is affordable only because an item's aspects never
-- change, so this is fetched once per item and kept for good. Decision 33
-- measured that the declared ISBN is the strongest signal available for
-- deciding whether a listing is the book.
--
-- What is here is what the *seller* claims, prefilled by eBay's catalogue
-- where their listing matched it and typed by hand where it did not. It is
-- evidence, not fact: decision 33 records three listings that declared the
-- exact right number while photographing something else.

CREATE TABLE listing_declaration (
    -- eBay's item id, as it appears in a search result.
    item_id     TEXT PRIMARY KEY,

    -- Normalized to ISBN-13 where the seller gave anything parseable. Null is
    -- ordinary: roughly half of listings for one book in the measured sample
    -- declared no number at all.
    isbn        TEXT,

    -- Displayed, never matched on. "Trade Paperback" and "books" and
    -- "198x130x17 mm" all occur, because this is prefilled when the listing
    -- matched eBay's catalogue and typed freehand when it did not.
    format      TEXT,
    publisher   TEXT,
    published   TEXT,

    -- Display only, and this is a rule rather than a preference. Decision 33:
    -- eBay's categories are localized and overlapping — "Bücher", "Libri
    -- antichi e da collezione" — and "Antiquarian & Collectible" is where
    -- collectible inventory lives. An early version of the matching rule
    -- excluded on this and lost seven true listings.
    category    TEXT,

    fetched_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX listing_declaration_by_isbn ON listing_declaration (isbn);
