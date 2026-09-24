-- What each stored observation was captured by, so a rule change can re-ask
-- about only the rows that actually lack what it needs.
--
-- The case this exists for already happened. *The right book* added a rule
-- reading the author eBay declares; migration 008 added the column; every row
-- that predated it was null, and `Declarations.of()` never re-asks by design.
-- The rule was dead code in production while passing every test.
--
-- Migration 009 fixed that by deleting every declaration and asking again,
-- because there is no way to tell a row captured before the author existed
-- from one whose seller genuinely left it blank — about one listing in ten.
-- At two books and forty calls that was the right trade. At fifty books it is
-- not, and re-asking is the only part of a logic change that is not free.
--
-- Deriving is free (decision 43). This makes the one thing that is not
-- as small as it can be.

-- Existing rows are stamped 1 rather than 0, and that is knowable rather than
-- optimistic: migration 009 emptied this table, so every surviving row was
-- written by code that already read the author, which is everything the
-- current code reads. Nothing is stale on the day this ships and no request
-- is spent proving it.
ALTER TABLE listing_declaration ADD COLUMN captured_by INTEGER NOT NULL DEFAULT 1;

-- Same reasoning, separately versioned. What we read from an edition has not
-- changed since the table was created, so every row is current.
ALTER TABLE openlibrary_edition ADD COLUMN captured_by INTEGER NOT NULL DEFAULT 1;

CREATE INDEX listing_declaration_by_capture ON listing_declaration (captured_by);
CREATE INDEX openlibrary_edition_by_capture ON openlibrary_edition (captured_by);
