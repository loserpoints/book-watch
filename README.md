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

**Early.** Repository tooling, the eBay OAuth token exchange, and eBay's
account-deletion compliance endpoint. Nothing else: no want-list, no polling,
no UI. See `docs/` for the product brief and the decision record.

The production keyset is disabled until the deletion endpoint is deployed and
registered with eBay — see decision 16 and the checklist below.

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
docs/                  product brief and decision record
src/book_watch/ebay/   eBay API client
src/book_watch/web/    FastAPI app; currently just the compliance endpoint
tests/                 offline by default; `-m network` opts into real requests
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

## eBay compliance endpoint

eBay disables a production keyset until the application either receives
marketplace account deletion notifications or is granted an exemption. This
repo takes the first route (decision 16), which means the endpoint has to be
live before the API works at all.

The endpoint URL is hashed into every response eBay validates against, so it
must be settled first and must match eBay's copy exactly.

```sh
# 1. Generate a verification token (32-80 chars, [A-Za-z0-9_-])
python -c "import secrets; print(secrets.token_urlsafe(48))"

# 2. Tell Fly about both values. The URL follows the app name in fly.toml.
fly secrets set \
  EBAY_VERIFICATION_TOKEN='<the token>' \
  EBAY_DELETION_ENDPOINT_URL='https://<app>.fly.dev/ebay/deletion'

# 3. Deploy
fly deploy

# 4. Check the challenge response before touching eBay's console
curl "https://<app>.fly.dev/ebay/deletion?challenge_code=test123"
```

That last response should equal:

```sh
python -c "import hashlib; print(hashlib.sha256(('test123' + '<the token>' + 'https://<app>.fly.dev/ebay/deletion').encode()).hexdigest())"
```

If it matches, enter the URL and the token in eBay's developer console under
**Alerts & Notifications → Marketplace Account Deletion** and save. The keyset
should stop reporting *Non Compliant*, after which
`uv run python -m book_watch.ebay` is the check that it worked.

## License

MIT
