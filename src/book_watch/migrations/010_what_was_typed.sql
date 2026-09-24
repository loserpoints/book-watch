-- What a person typed, stored where a person's input belongs.
--
-- `edition` has been holding two kinds of row with nothing to tell them apart:
-- the ISBN somebody typed into the add form, and a number a rule concluded
-- belongs to the book. The first is a fact about intent and can never be
-- wrong; the second is a conclusion from rules that keep changing.
--
-- That ambiguity is why the wrong book could not be unmatched. A pass had
-- concluded that Don Gillmor's ISBN was an edition of Joy Williams's novel,
-- and no repair could delete it without guessing which rows were conclusions.
--
-- With the typed value moved out, `edition` becomes derived-only and can be
-- emptied and rebuilt whenever the rules change — which is what the next
-- slice does, and what makes every later rule change free.
--
-- `search_text` is folded in rather than kept alongside. It held the same
-- thing for the other case: text somebody typed that was never an ISBN
-- (decision 29). One column, one meaning — whether it parses as a number is
-- a question to ask it, not a reason to store it twice.

ALTER TABLE entry ADD COLUMN typed TEXT;

-- The override case, moving as-is.
UPDATE entry SET typed = search_text WHERE search_text IS NOT NULL;

-- The ISBN case. A work added by number has exactly one edition row carrying
-- nothing but the number, because `add()` writes only `(work_id, isbn)`.
-- Anything with a publisher, date or format came from a pass, which reads
-- those from Open Library.
--
-- Residual, stated rather than hidden: a pass that learned a number Open
-- Library knew nothing else about would leave a bare row too, and it would be
-- mistaken here for a typed one. It stays as this entry's typed value and
-- goes on counting as a target. At two books that is checkable by eye; the
-- capture version in a later slice is what makes it unnecessary to check.
UPDATE entry
   SET typed = (
       SELECT edition.isbn FROM edition
        WHERE edition.work_id = entry.work_id
          AND edition.isbn IS NOT NULL
          AND edition.publisher IS NULL
          AND edition.published IS NULL
          AND edition.physical_format IS NULL
     ORDER BY edition.id
        LIMIT 1
   )
 WHERE typed IS NULL;

-- Moved, so no longer duplicated here. Everything left in `edition` is now a
-- conclusion, which is the state the next slice needs.
DELETE FROM edition
 WHERE isbn IN (SELECT typed FROM entry WHERE typed IS NOT NULL)
   AND publisher IS NULL
   AND published IS NULL
   AND physical_format IS NULL;

ALTER TABLE entry DROP COLUMN search_text;
