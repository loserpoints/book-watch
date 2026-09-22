# book-watch

A personal tool that watches a want-list of specific books across used-book
marketplaces and emails me when a copy appears under my price threshold.

## Why this exists

I get most of my books from the library. When an author's work isn't fully
available there, I buy an inexpensive used copy, read it, and donate it.
Finding those copies means searching several marketplaces title by title,
comparing condition, price and shipping — every time, for every title.

Separately, for a handful of favourite authors I collect nice editions. Same
search burden, opposite criteria.

Nothing existing covers this. BookFinder aggregates but keeps no watchlist.
AbeBooks and Biblio have want-lists, but each only searches its own inventory.
BookScouter alerts on *selling* books. BiblioPrice is built for reseller
arbitrage. General marketplace alert tools are keyword-based and have no
concept of an edition.

## The two modes

A want-list entry is either:

| Mode | Optimises for | Condition | Edition |
|---|---|---|---|
| `reading` | Lowest landed cost (price + shipping) | Floor: readable | Any |
| `collectible` | Edition quality — printing, jacket, signature | Primary signal | Specific |

Same fetch, same duplicate detection, same email. Different matching and
ranking.

## Status

**Early.** Repository tooling is in place and the eBay OAuth token exchange is
written and tested. Nothing else is built: no want-list, no polling, no UI.
See `docs/` for the product brief and the decision record.

The eBay keys currently return `invalid_client` from the token endpoint. The
client code is not the cause — see decision 4.

## Sources

| Source | Status |
|---|---|
| eBay Browse API | Anchor source. Free, 5,000 calls/day. |
| Biblio | Second source. API key granted on request via their affiliate program. |
| Open Library | Edition and ISBN resolution. Free, no key. Cached aggressively — see below. |
| AbeBooks | **Not viable.** Public API deprecated and closed to new developers. |
| Alibris | Deprioritised. Developer portal appears stale. |

Open Library is a non-profit that asks not to be used as a backend service, so
edition resolution is cached in SQLite and refreshed monthly. The daily polling
loop never calls it directly.

## Stack

Python, FastAPI + Jinja2 + HTMX (server-rendered, no JS build step), SQLite,
APScheduler for the daily poll, Resend for email. Containerised, deployable to
Fly.io or self-hosted. Running cost is roughly $2–3/month, all of it hosting.

## Layout

```
docs/              product brief and decision record
src/book_watch/    the application
tests/             offline by default; `-m network` opts into real requests
```

## Running it

Requires [uv](https://docs.astral.sh/uv/). It installs the right Python itself.

```sh
uv sync                              # create the environment
cp .env.example .env                 # then fill in your eBay keys
uv run ruff check . && uv run pytest # lint and the offline suite
uv run python -m book_watch.ebay     # verify the eBay keys work (one request)
```

The last command makes a real call to eBay. Everything above it is offline.

## License

MIT
