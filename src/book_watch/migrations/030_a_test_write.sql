-- One row the app overwrites at most once a minute, to prove a write still
-- reaches the disk (S78, #275). The likeliest failure is the volume filling:
-- reads keep working while writes fail, so only a committed write can tell.
--
-- Additive: code from before this migration ignores the table.
CREATE TABLE test_write (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    at TEXT    NOT NULL
);
