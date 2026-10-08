# Monitoring

## Purpose

These rules say what the app writes to its logs, in one vocabulary, so that Fly's log viewer shows what the app did and why something failed.

## Rules

### Logs and counts

- A log line explains one event: what happened, to which book, and why it failed. A count tracks how often events happen ([S78](https://github.com/loserpoints/book-watch/issues/275)).
- A count that can go bad has a log line for each bad case.
- Every outside call is logged, successes included.
- Logs are read in Fly's log viewer, which keeps their whole history.

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

### Where lines go

- The app's lines go to Fly's logs.
- A GitHub workflow that runs a command on the Fly machine prints only that command's own output and its warnings, to the workflow's public log.

## Open issues

- [S78 · The app publishes its counts for Fly's Grafana](https://github.com/loserpoints/book-watch/issues/275)
- [S80 · Grafana tells me when something goes wrong, chosen from the dashboard](https://github.com/loserpoints/book-watch/issues/277)
