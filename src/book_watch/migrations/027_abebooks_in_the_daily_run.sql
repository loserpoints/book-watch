-- How AbeBooks went in each daily check (#229 follow-up).
--
-- The check used to fail a page whose copies were not in strict price order.
-- Real pages are only roughly in order, so the order is measured instead and
-- counted here, where a rising count says AbeBooks has changed how it sorts.
--
-- Additive: code from before this migration ignores the columns.
ALTER TABLE daily_run ADD COLUMN abebooks_read INTEGER NOT NULL DEFAULT 0;
ALTER TABLE daily_run ADD COLUMN abebooks_failed INTEGER NOT NULL DEFAULT 0;
-- Pages with more than a few copies out of price order. See
-- `abebooks.out_of_place`.
ALTER TABLE daily_run ADD COLUMN abebooks_unordered INTEGER NOT NULL DEFAULT 0;
