# Operating it

What to do when something is wrong, written down before it is needed.

Not a decision record — `docs/decisions.md` says why things are the way they
are, and this says what to do about them. Procedures and reasoning rot at
different rates and belong in different files.

## How a deploy happens

Merging to `main` deploys. CI runs on the push; when it goes green, the deploy
workflow fires on `workflow_run` and ships. Merge to live is about 85 seconds,
with nobody watching.

That is deliberate. Deploys used to be manual, and production drifted twelve
slices behind `main` — so the next deploy carried six migrations at once,
including the one that rewrote every want-list row. Small and frequent beats
rare and interesting.

**A red CI does not deploy.** The job refuses anything whose triggering run did
not conclude `success`.

## Rolling back

**Revert the commit on `main`.** CI runs, the deploy fires, and the previous
code is live in about ninety seconds. No flyctl, no local machine, no
credentials anywhere but GitHub. This is the normal path and it should be the
first thing tried.

**If the revert itself will not deploy**, run the Deploy workflow by hand from
the Actions tab and give it an older ref. `workflow_dispatch` is still on the
workflow for exactly this.

**What a rollback does not undo is a migration.** Migrations are forward-only
by decision 3, so reverting the code leaves the schema where it was. That is
usually fine — the old code ignores columns it does not know about — and is
not fine when a migration dropped or rewrote something. Which is why:

## Data

The SQLite file lives on a Fly volume, and Fly snapshots it **daily with five
days of retention** (decision 28, as amended). So a migration that destroys
data is recoverable to roughly the previous midnight, and not more finely than
that.

For a want-list of a few books that is an acceptable amount to lose. It stops
being acceptable at some size, and the honest trigger is the first time losing
a day's work would actually annoy you.

## What the deploy checks, and what each failure means

Four checks run after every deploy. They are ordered so the first one to fail
is the most specific answer.

| Check | A failure means |
|---|---|
| eBay challenge response | The compliance endpoint is wrong or unreachable. eBay marks the keyset non-compliant if this stays broken (decision 16) — fix it first, whatever else is wrong |
| Search works | 500 is missing eBay keys on Fly; 502 is eBay rejecting them |
| The want-list works | Storage. An unset `BOOK_WATCH_DB_PATH`, a volume that did not mount, or a failed migration. It is the only page that opens the database |
| The book page works | Not storage — the want-list already proved that. Its template, its query, or a migration that did not reach the image |

An empty want-list makes the last check skip rather than fail. Nothing on the
list is a perfectly good state.

## What is not checked

**`/health` does not touch the database.** Fly reads it every thirty seconds to
decide whether the machine is alive, and it answers `ok` unconditionally — so
a machine whose volume has detached reports itself healthy and keeps serving.
The deploy catches this at deploy time; nothing catches it afterwards. Making
it deep is not free, because a database failure would then restart the machine
and take the compliance endpoint down with it. Tracked rather than patched.
