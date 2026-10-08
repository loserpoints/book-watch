# Monitoring

## Purpose

These rules say what the app writes to its logs, in one vocabulary, so that Fly's log viewer shows what the app did and why something failed.

## Rules

### Logs and counts

- A log line explains one event: what happened, to which book, and why it failed. A count tracks how often events happen.
- A count that can go bad has a log line for each bad case.
- Every outside call is logged, successes included.
- Logs are read in Fly's log viewer, which keeps their whole history. Counts are read in Fly's managed Grafana, which keeps about 15 days.

### The line

- One event per line, in logfmt: `key=value` pairs separated by spaces.
- Every line starts with `level=` and `event=`, then its fields in the same order every time.
- A value with a space, a quote or an equals sign is quoted.
- A yes-or-no field reads `yes` or `no`.
- Units are in the field's name, such as `ms`.
- An empty field is left out.
- A line has no timestamp of its own, since Fly stamps each line.
- Levels: `info` when things went as expected, `warn` when something failed or was skipped and the app carried on, `error` when something crashed. A crash's traceback follows its line.
- A line that fits none of the five events below, such as uvicorn starting, a setting missing or an eBay deletion notice arriving, is written as `event=log` with its `logger` and `msg`.
- No line holds a key, a token or an email address. A service's error is cut to 300 characters with those taken out before it is written as `detail`.

### The vocabulary

| Field | Values |
|---|---|
| `service` | `ebay`, `abebooks`, `openlibrary`, `resend` |
| `endpoint` | eBay `search`, `item`, `token`; AbeBooks `page`; Open Library `search`, `isbn`, `work`; Resend `send` |
| `trigger` | `daily`, `check` (the Check button), `open` (opening a book), `recheck` (a book's checked chip), `add`, `cover` (a cover's first lookup), `test` (a GitHub workflow) |
| `book`, `title` | The want-list book, by its id and its name |
| `outcome` | `ok`, `empty`, `failed`, `skipped` (not asked) |
| `reason` | `timeout`; `refused` (a 4xx answer); `down` (a 5xx answer, or no answer); `unreadable` (an answer the app couldn't read); `blocked` (a path robots.txt disallows); `limit` (past a daily limit); `setup` (a key or setting missing) |
| `ms` | How long, in milliseconds |

- `trigger` is set once where the work starts and carried into the background work and threads it starts. Examining copies carries the trigger of what started it.
- A check or job that fails because a call failed carries that call's `reason`.
- `book` and `title` appear in logs only, never as a count's label.

### The events

- `event=call`: one line per request to an outside service: `service`, `endpoint`, `trigger`, `book`, `title`, `outcome`, `reason`, `status`, what came back, `ms`, `detail`. An eBay search adds `results`, an AbeBooks page `url` and `rows`, an Open Library lookup by number `isbn`.
- `event=check`: one line per marketplace check of a book, the same for eBay and AbeBooks: `marketplace`, `trigger`, `book`, `title`, `outcome`, `reason`, `copies`, `new`, `full`, `ms`. `full` is `yes` when more matched than the page holds, so copies past it went unseen. AbeBooks adds `unordered` and `out_of_place`.
- `event=job`: a `phase=start` and a `phase=end` line for the daily check (`daily`), examining a book's copies (`examine`) and the morning email (`email`). The end line has the job's `outcome` and `ms`, and its own numbers. An email with a setting missing on Fly ends `skipped` with `reason=setup`.
- `event=page`: one line per request to the app: `path`, `status`, `ms`. A 500 is `error`, since only a crash answers it. Another 5xx is `warn`: the app saying a service it needs is down. `/health` writes none, since Fly asks for it every 30 seconds.
- `event=action`: something done in the app: `add`, `bought`, `remove` and `check` (the Check button pressed). An action is its own trigger, so it names none.

### Counts

- The app serves its counts on port 9091 at `/metrics`, named in `fly.toml`'s `[metrics]`, and Fly collects them every 15 seconds. The port is not one outside traffic reaches.
- Every name starts `bookwatch_`. Labels use the vocabulary above. No label holds a book's title or id, and a page's label is its route's pattern, such as `/book/{book_id}`, never its address.
- Counts of events move in the same helper that writes their line, so a line and its count never disagree. They start again from 0 at each deploy or restart, which Grafana's `rate` and `increase` read through.

| Count | Labels |
|---|---|
| `bookwatch_calls_total`, `bookwatch_call_seconds` | `service`, `endpoint`, `trigger`, `outcome`, `reason` (empty when none); the time by `service` and `endpoint` |
| `bookwatch_checks_total` | `marketplace`, `trigger`, `outcome` |
| `bookwatch_check_copies_total`, `bookwatch_check_new_copies_total`, `bookwatch_checks_full_total` | `marketplace` |
| `bookwatch_jobs_total`, `bookwatch_job_seconds` | `name`, `outcome`; the time by `name` |
| `bookwatch_pages_total`, `bookwatch_page_seconds` | `route`, `status`; the time by `route` |
| `bookwatch_actions_total` | `name` |
| `bookwatch_price_moves_total` | `marketplace`, `direction` (`down` or `up`), counting copies whose delivered price a check moved |

- eBay's and Resend's calls against their daily limits are read as `calls_total` over 24 hours. No table records each call: the logs keep every one.
- Counts of state are read from the database when Fly collects them:

| Count | What |
|---|---|
| `bookwatch_openlibrary_calls_last_day` | Open Library requests in the last 24 hours, from the ledger the app enforces its 500 from |
| `bookwatch_daily_last_finished_timestamp_seconds` | When the last daily check finished, labeled with its `outcome` |
| `bookwatch_daily_last` | The last daily check's numbers, by `count`: `books`, `failed`, `openlibrary_spent`, `emailed`, `email_failed`, `abebooks_read`, `abebooks_failed`, `abebooks_unordered` |
| `bookwatch_books`, `bookwatch_books_under_limit`, `bookwatch_books_bought` | Books on the list, those with a copy under their limit, and books bought |
| `bookwatch_copies_listed`, `bookwatch_copies_under_limit` | By `marketplace`: copies certainly a book on the list, listed now from US sellers, and those under their book's limit |
| `bookwatch_db_readable`, `bookwatch_db_writable` | Whether the counts read the database, and whether the last test write reached the disk |
| `bookwatch_db_last_write_timestamp_seconds`, `bookwatch_db_bytes` | When a test write last reached the disk, and the database file's size |
| `bookwatch_volume_size_bytes`, `bookwatch_volume_free_bytes` | The size of the disk the database is on, and the space free on it |
| `bookwatch_version_info`, `process_start_time_seconds` | The version deployed, and when the app started, so restarts can be counted |

- What's found, the books and copies above, is worked out at the first collection and then every 15 minutes, since it changes only when a check runs and is the want list's work over every book. Everything else is read at every collection.
- The test write overwrites one row in `test_write` and commits, at most once a minute. A write that fails publishes `bookwatch_db_writable 0` and writes an `error` line. A write rolled back never reaches the disk, so it can't catch a full volume.
- Free space is read by the app from the disk the database is on. Fly publishes nothing on its volumes in its Grafana.
- The dashboard, `grafana/book-watch.json`, is written by `scripts/build_dashboard.py` and imported into Fly's Grafana by hand ([runbook](../runbook.md#deploy)). Every query names a count above, which a test checks.
- A collection that can't read the database publishes `bookwatch_db_readable 0`, and the counts of events still arrive.

### Where lines go

- The app's lines go to Fly's logs.
- A GitHub workflow that runs a command on the Fly machine prints only that command's own output and its warnings, to the workflow's public log.

## Open issues

- [Hear from Grafana when something goes wrong, and restyle the dashboard once it holds data](https://github.com/loserpoints/book-watch/issues/282)
