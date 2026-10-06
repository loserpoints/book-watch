# Runbook

## Deploy

- Merging to `main` deploys. CI runs, and when it passes the Deploy workflow ships the change in about 90 seconds.
- A failed CI run never deploys.
- One deploy runs at a time.
- To redeploy without a commit, for example after changing a secret: Actions → Deploy → Run workflow, on `main`.
- A deploy after 7am New York time, on a day whose daily check has not finished, starts that check as the app boots.
- Each daily check logs one line, `Daily check: ok, 6 books, 0 failed, 0 Open Library requests, 1 emailed`, readable in Fly's log viewer. "Email is off" before it means `RESEND_API_KEY` or `ALERT_EMAIL_TO` is not set on Fly.
- "Shipping for calculated listings is off" in Fly's logs means `SHIP_TO_ZIP` is not set, so copies with calculated shipping show "+ shipping?".
- After setting or changing the Resend key, run Actions → Send a test email. It sends one email from the live app with its real settings, or fails with the reason.
- To see exactly what eBay sends for a search, field by field, run Actions → Search eBay once with a title and author or an ISBN. It makes one search on the Fly machine, the way the app does, and prints eBay's JSON in the run's log.
- To see what an AbeBooks or Biblio page holds when read from Fly, run Actions → Read a marketplace page once with an `https://www.abebooks.com/book-search/...` or `https://www.biblio.com/...` address. It makes one request on the Fly machine and prints the status, the page's count, and the delivered prices on it. Paths the site's robots.txt disallows are refused.
- "AbeBooks check failed" on a book's page has its reason in Fly's logs, `AbeBooks check failed for work 12: grouped rows`. A reason naming the page's shape means AbeBooks changed its page: read the book's search with Read a marketplace page once to see what it serves now. The book's eBay copies, and its AbeBooks copies from the last good check, stay listed meanwhile.

## Roll back

1. On GitHub, open the merged pull request and choose Revert.
2. Merge the revert. CI runs and the previous code deploys.
3. If the revert cannot deploy, run Actions → Deploy → Run workflow on a branch that holds the previous code.

A rollback reverts code, not the database. Migrations run forward only, so a migration that dropped or rewrote data needs a restore.

Code from before migration 025 does not run against the database after it, which keys listings by marketplace. Rolling back past it needs a restore of a snapshot taken before it ran.

A pull request that changes a migration runs Try migrations on production data: it copies the live database to the runner, applies the branch's migrations to the copy, and fails if a migration fails or a table loses rows. The live database is never written, and the log shows row counts only.

## Restore data

- Fly snapshots the data volume daily and keeps five days, so data can be restored to roughly the previous midnight.
- Run Actions → Restore data with the snapshot left empty to list the snapshots. Nothing changes.
- Run it again with a snapshot's ID to restore that snapshot, or with `fresh` to snapshot the data now and restore that, which tests the restore and loses nothing.
- A restore first snapshots the data as it stands, and the run's summary names that snapshot. Restoring it undoes the restore.
- A restore replaces the data volume and destroys the old one, then runs Deploy, whose checks read the restored data. The app is down for a few minutes, the eBay deletion endpoint included.
- Alerts emailed after the restored snapshot was taken may be emailed again, since the record of what was sent goes back with the data.
- Avoid running it around 7am New York time, when the daily check runs.

## Post-deploy checks

Four checks run after every deploy, most specific first:

1. **eBay challenge response.** A failure means the account-deletion endpoint is wrong or unreachable. Fix it first: eBay marks the keyset non-compliant if it stays broken.
2. **Search works.** 500 means eBay keys are missing on Fly. 502 means eBay rejected them.
3. **Want list works.** A failure means storage: an unset `BOOK_WATCH_DB_PATH`, a volume that did not mount, or a failed migration.
4. **Book page works.** A failure means its template, its query, or a migration missing from the image. It skips when the want list is empty.

## Known gaps

- [See what the app does unattended, and hear when something is wrong](https://github.com/loserpoints/book-watch/issues/168)
