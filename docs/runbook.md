# Runbook

## Deploy

- Merging to `main` deploys. CI runs, and when it passes the Deploy workflow ships the change in about 90 seconds.
- A failed CI run never deploys.
- One deploy runs at a time.
- To redeploy without a commit, for example after changing a secret: Actions → Deploy → Run workflow, on `main`.
- A deploy after 7am New York time, on a day whose daily check has not finished, starts that check as the app boots.
- Each daily check logs one line, `Daily check: ok, 6 books, 0 failed, 0 Open Library requests, 1 emailed`, readable in Fly's log viewer. "Email is off" before it means `RESEND_API_KEY` or `ALERT_EMAIL_TO` is not set on Fly.
- After setting or changing the Resend key, run Actions → Send a test email. It sends one email from the live app with its real settings, or fails with the reason.

## Roll back

1. On GitHub, open the merged pull request and choose Revert.
2. Merge the revert. CI runs and the previous code deploys.
3. If the revert cannot deploy, run Actions → Deploy → Run workflow on a branch that holds the previous code.

A rollback reverts code, not the database. Migrations run forward only, so a migration that dropped or rewrote data needs a restore.

## Restore data

- Fly snapshots the data volume daily and keeps five days, so data can be restored to roughly the previous midnight.
- Restoring currently needs `flyctl` on a machine with Fly credentials: list the volume's snapshots, create a volume from the chosen one, and move the app onto it.

## Post-deploy checks

Four checks run after every deploy, most specific first:

1. **eBay challenge response.** A failure means the account-deletion endpoint is wrong or unreachable. Fix it first: eBay marks the keyset non-compliant if it stays broken.
2. **Search works.** 500 means eBay keys are missing on Fly. 502 means eBay rejected them.
3. **Want list works.** A failure means storage: an unset `BOOK_WATCH_DB_PATH`, a volume that did not mount, or a failed migration.
4. **Book page works.** A failure means its template, its query, or a migration missing from the image. It skips when the want list is empty.

## Known gaps

- [`/health` says ok without checking anything](https://github.com/loserpoints/book-watch/issues/49)
- [Restore the database from a snapshot without a local machine](https://github.com/loserpoints/book-watch/issues/148)
