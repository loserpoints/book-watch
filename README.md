# book-watch

## Value proposition

I get most of my books from the library. When it doesn't have one, I buy a cheap used copy, read it and donate it. Finding that copy means searching marketplaces title by title, reading condition notes that use no common vocabulary, adding shipping to learn the real price, and doing it again next week because stock turns over. The copy I want often appears, just not on the day I looked.

book-watch keeps a want list of books and shows every copy for sale, judged against a price limit I set, so I stop searching by hand.

Nothing else covers this:

| Tool | Why it isn't this |
|---|---|
| [BookFinder](https://www.bookfinder.com/) | Searches on demand. No want list, no alerts. |
| [AbeBooks](https://www.abebooks.com/) and [Biblio](https://www.biblio.com/) want lists | Each searches only its own stock. |
| [BookScouter](https://bookscouter.com/) | Alerts on buyback prices, for selling books. |
| [BiblioPrice](https://biblioprice.com/) | Built for reseller arbitrage. |
| Marketplace keyword alerts | No idea what an edition is. |

It works if, over a month, I stop searching marketplaces by hand and it finds at least one book I buy that I wouldn't otherwise have found. The [jobs](docs/jobs.md) say what it has to get done to earn that.

## What it does

- Adds a book by title and author, or by ISBN, in a few taps ([add a book](docs/surfaces/add-a-book.md)).
- Works out which editions are the same book, using Open Library's works and editions ([matching](docs/rules/matching.md)).
- Searches eBay for every copy of each book, and prices each one delivered, against the book's limit ([pricing](docs/rules/pricing.md)).
- Shows the whole list at a glance, with the cheapest copy of each book and whether it is under the limit ([want list](docs/surfaces/want-list.md)).
- Shows every copy of one book with its condition, the seller's note and its photos, so I can judge it without opening the listing ([active listings](docs/surfaces/active-listings.md)).
- Checks every book at 7am New York time, and marks the copies that are new since I last opened each book.
- Emails me the next morning when a new copy is under its book's limit, and sends nothing on mornings with none ([alerts](docs/rules/alerts.md)).
- Installs on a phone as an app.
- Stays well inside what eBay and Open Library allow ([rate limits](docs/rules/rate-limits.md)).

Collectible editions, where condition matters more than price, are not built.

## Tech stack

| Piece | Choice | Why |
|---|---|---|
| App | Python, FastAPI, Jinja templates, htmx | Server-rendered pages with no JavaScript build step. |
| Data | SQLite on a Fly volume | One user and one file. Snapshotted daily by Fly. |
| Hosting | Fly.io | About $2–3 a month, the project's whole running cost. |
| Listings | eBay Browse API | Free, 5,000 calls a day, and prices shipping per copy. |
| Email | Resend | Free, and its shared sending address needs no domain. It delivers only to the Resend account's own address, which is the one reader. |
| Editions | Open Library | Free, with a works and editions model. Every answer is cached. |
| CI and deploy | GitHub Actions | Every step runs from a browser, with credentials held as secrets. |

AbeBooks closed its API to new developers, so eBay is the only marketplace for now.

## Running it

It runs at [book-watch-alan.fly.dev](https://book-watch-alan.fly.dev). Merging to `main` deploys it ([runbook](docs/runbook.md)).

To work on it, with [uv](https://docs.astral.sh/uv/) installed:

```sh
uv sync                              # create the environment
cp .env.example .env                 # then fill in the eBay keys
scripts/check.sh                     # lint, format, docs check and offline tests
uv run python -m book_watch.ebay     # check the eBay keys work (one request)
```

Setting up a new deployment, once:

1. **Fly:** create an organisation-scoped deploy token under Account → Access Tokens. An app-scoped token cannot create its own app.
2. **GitHub:** add two repository secrets: `FLY_API_TOKEN`, the Fly token, and `EBAY_VERIFICATION_TOKEN`, a string you invent of 32–80 letters, digits, `_` or `-`.
3. **Fly:** set `app` in `fly.toml` and run Actions → Deploy. It creates the app, deploys, and checks the eBay endpoint answers correctly.
4. **Fly:** add `EBAY_CLIENT_ID` (the production App ID) and `EBAY_CLIENT_SECRET` (its Cert ID) under the app's Secrets. Nothing in GitHub reads them, so they live only on Fly. Add `SHIP_TO_ZIP`, the ZIP the books ship to, so eBay prices calculated shipping. Without it, those copies show "+ shipping?".
5. **eBay:** under Alerts & Notifications → Marketplace Account Deletion, enter the endpoint URL and the token, and save. eBay disables a production keyset until this works.
6. **Resend:** sign up with the address the email should go to, and create an API key with "Sending access" only. On Fly, add it as `RESEND_API_KEY`, and that address as `ALERT_EMAIL_TO`. Without either, the app runs and sends no email. Then run Actions → Send a test email to check both.

## Repository structure

```
src/book_watch/            the app
  ebay/                    eBay client
  openlibrary/             Open Library client
  web/                     pages, templates, design tokens
  migrations/              database schema, applied in order
tests/                     offline by default; `-m network` makes real requests
scripts/                   check.sh, the docs check, icon rendering
docs/
  governance.md            what each doc holds and how work flows
  jobs.md                  what the app must get done
  design-system.md         principles and components
  surfaces/                each screen, as it is now
  rules/                   pricing, matching, rate limits
  milestones/              what each milestone set out to do, did, and learned
  runbook.md               deploy, roll back, restore
CONTRIBUTING.md            how to build, test and review
.claude/skills/            set-milestone and plan-slice, used at the steps governance names
LICENSE                    MIT
```
