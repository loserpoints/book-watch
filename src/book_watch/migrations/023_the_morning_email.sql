-- The morning email (S40, #143).
--
-- `emailed_copy` is what makes an email say something new: a copy is in at
-- most one email, ever. Keyed like `copy`, since a copy can stand for more
-- than one book.
CREATE TABLE emailed_copy (
    item_id    TEXT NOT NULL,
    work_id    INTEGER NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    emailed_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (item_id, work_id)
);

-- What each daily check sent, and whether sending failed.
ALTER TABLE daily_run ADD COLUMN emailed INTEGER NOT NULL DEFAULT 0;
ALTER TABLE daily_run ADD COLUMN email_failed INTEGER NOT NULL DEFAULT 0;

-- A book not opened since S39 has no visit, and nothing is new on a book
-- with no visit, so it could never alert. Counting now as its visit lets it
-- alert from here on, and keeps anything found before the email existed out
-- of the first one.
UPDATE entry SET looked_at = datetime('now') WHERE looked_at IS NULL;
