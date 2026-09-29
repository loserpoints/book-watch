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

-- What each daily check sent, and whether sending failed. Kept for the
-- record only: a failed send is logged, and never shown in the app.
ALTER TABLE daily_run ADD COLUMN emailed INTEGER NOT NULL DEFAULT 0;
ALTER TABLE daily_run ADD COLUMN email_failed INTEGER NOT NULL DEFAULT 0;
