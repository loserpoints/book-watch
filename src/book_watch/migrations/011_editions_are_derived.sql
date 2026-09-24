-- Every row here was a conclusion. Conclusions are derived now.
--
-- Migration 010 moved out the one kind of row that was not a conclusion: the
-- number somebody typed. What is left was written by a pass, under rules that
-- have already changed once and will change again.
--
-- Which numbers count as a book is now worked out on read, from things we
-- observed — what sellers declared, what the catalogue says those numbers
-- are, who sellers say wrote them. All of it already stored, so re-judging
-- every book costs no requests at all.
--
-- The table stays. A collector entry points at a printing a person chose
-- (`entry.edition_id`), and that is input, not inference — *Two kinds of
-- hunt* is where rows start appearing here again, put there by somebody
-- rather than concluded.

DELETE FROM edition;
