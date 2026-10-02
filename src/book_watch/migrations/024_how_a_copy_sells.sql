-- How each copy is sold (S59, #74).
--
-- eBay's `buyingOptions` for the copy, as a JSON list such as
-- ["FIXED_PRICE", "BEST_OFFER"]. Null until the copy's next search, which the
-- daily check runs within a day: unknown, not "takes no offers".
--
-- The whole list rather than a yes/no for Best Offer, so a collector's search,
-- which will want auctions (#144), reads the same column.
ALTER TABLE copy ADD COLUMN buying_options TEXT;
