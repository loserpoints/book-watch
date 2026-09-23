-- What the seller said the author is.
--
-- Already in the response we pay for: `getItem` returns it under
-- `localizedAspects` on about nine listings in ten, and 006 stored the format,
-- publisher and year from the same payload while throwing this away.
--
-- It is here because the grader was comparing titles alone, and a title is
-- not a book. Three different books called "Breaking and Entering" were all
-- graded certain against each other — Joy Williams's novel, Don Gillmor's
-- novel, and Philip Carlson's manual for working actors — because Open
-- Library confirmed each number was something called "Breaking and Entering",
-- which it was.
--
-- Claimed, not verified: eBay prefills this where its catalogue matched the
-- listing and lets the seller type it otherwise. Good enough to *contradict*
-- a match, which is all it is used for.

ALTER TABLE listing_declaration ADD COLUMN author TEXT;
