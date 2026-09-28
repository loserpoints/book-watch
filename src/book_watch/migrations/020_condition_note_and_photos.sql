-- The seller's condition note and every photo of the listing, from the same
-- `getItem` response we already ask for once per listing (decision 58).
--
-- The note is where "ex-library", "price clipped" and "no dust jacket" are
-- usually written. It is stored whole: SQLite's TEXT has no length that
-- matters here, so nothing is cut at write time and any shortening is the
-- page's business.
--
-- The photos are URLs, never images. eBay serves them, and they are fetched
-- only when somebody taps a copy's photo. A JSON array in one column rather
-- than a table: the list is always read whole and never searched.
--
-- No backfill here. Every existing row was captured by code that did not read
-- these fields, and `ebay.declarations.CAPTURE` moving to 2 is what marks it
-- stale, so each is re-asked about once, lazily, inside a pass that already
-- runs (decision 46). NULL until then, and NULL after it when the seller
-- wrote no note or the listing has ended.
ALTER TABLE listing_declaration ADD COLUMN condition_note TEXT;
ALTER TABLE listing_declaration ADD COLUMN photos TEXT;
