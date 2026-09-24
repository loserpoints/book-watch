-- Ask eBay again about every listing, once.
--
-- Migration 008 added `listing_declaration.author`, and a column added to an
-- existing table is null on every row that predates it. `Declarations.of()`
-- returns what is stored and never asks again — deliberately, since an item's
-- aspects do not change — so those rows would have stayed authorless for
-- good, and the rule that reads the author would have been dead code in
-- production while passing every test.
--
-- There is no way to tell a row that was never asked for an author from one
-- whose seller genuinely left it blank, which is about one listing in ten. So
-- all of them go and are asked again: one eBay call per listing, once, well
-- inside a 5,000-a-day allowance at this size.
--
-- `enriched_at` is cleared for the same reason. A pass that completed under
-- the old rule learned which numbers were a book's editions by comparing
-- titles alone, so its conclusions are exactly the ones now known to be
-- wrong, and every book deserves one more pass.

DELETE FROM listing_declaration;

UPDATE work SET enriched_at = NULL;
