-- The app's own settings (S83, #72), one row each by name. The first is the
-- default limit a new book starts with, in whole dollars.
--
-- Limits became whole dollars at the same time, so a limit stored with cents
-- is rounded to the nearest dollar, half up, and never below one. Purchases
-- keep the limit they were bought under, cents and all: that is history.
--
-- Additive for the table; code from before this migration ignores it.
CREATE TABLE setting (
    name  TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

UPDATE entry
   SET ceiling = CAST(MAX(1, CAST(ROUND(CAST(ceiling AS REAL)) AS INTEGER)) AS TEXT)
 WHERE ceiling IS NOT NULL;
