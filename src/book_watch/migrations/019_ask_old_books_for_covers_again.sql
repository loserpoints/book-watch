-- Take back a "no cover" that was never an answer.
--
-- Migration 018's lookup asked Open Library about a book's *work*, and
-- recorded "no cover" for any book that had no work id to ask about. It meant
-- books added by text alone. It also caught every book added by number before
-- migration 003, which carried the number across and had no work id to carry:
-- *State of Grace* showed a placeholder while Open Library holds two covers
-- for it.
--
-- Those books have an ISBN, and the lookup now asks by it (decision 56). This
-- clears the conclusion for exactly them, so the next view asks. A book whose
-- recorded "no cover" came from asking its work is left alone: that one was
-- an answer.

UPDATE work
   SET cover_asked_at = NULL
 WHERE cover_id IS NULL
   AND cover_asked_at IS NOT NULL
   AND openlibrary_work_id IS NULL
   AND EXISTS (
       SELECT 1 FROM entry
        WHERE entry.work_id = work.id
          AND length(entry.typed) = 13
          AND entry.typed NOT GLOB '*[^0-9]*'
   );
