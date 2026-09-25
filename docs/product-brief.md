# Product brief: book-watch

*Last updated: 2026-09-25*

`docs/jobs.md` is the companion to this file. This one says what the tool is
and why it should exist; that one says what I am trying to get done and how
I'll know each part works.

## Problem

I get most of my books from the library. When an author's work isn't fully
available there, I buy an inexpensive used copy, read it, and donate it.

Finding those copies is the tedious part. Each title means searching several
marketplaces, comparing condition descriptions that don't use consistent
vocabulary, and adding shipping to work out what a copy actually costs. Repeat
per title, and repeat again next week because inventory turns over constantly.
The copy I want often does appear — just not on the day I looked.

Separately, for a handful of favourite authors I collect nice editions. The
search burden is identical; the criteria are inverted.

## Who it's for

Me. One user, a want-list in the dozens rather than thousands, daily polling.
Design decisions should favour simplicity and low running cost over anything
that anticipates scale.

## The two use cases

**Reading copy.** I want to read a specific book, the library doesn't have it,
and I'll donate it afterwards. Optimise for lowest landed cost. Condition needs
only to be readable. Any edition qualifies. A threshold might be "under $8
delivered."

**Collectible.** I want a specific edition of a book by an author I collect.
Condition is the primary signal — dust jacket, printing, signature. Price is a
ceiling rather than a target, and a higher one.

These share a pipeline and differ only in matching and ranking. An entry
carries a `mode` that selects which.

## What it does

1. I keep a want-list of books, each with a mode, a price threshold, and
   optional edition or condition preferences.
2. Daily, it resolves each entry to a set of editions and searches the
   marketplaces for listings matching them.
3. It compares against listings it has already seen, so only genuinely new
   inventory counts.
4. It tells me when a copy appears under my price ceiling, and stays quiet
   when none has.

A small web UI manages the want-list and shows current matches, and one action
checks every book on it.

**The email is a backup, not the channel.** An earlier draft of this called
item 4 a daily digest, which was wrong in a way worth recording: a digest of
everything is a digest I stop reading within a week, and then the job has
failed while every part of it still works. What I want is an interruption only
when something crosses the ceiling I set, and silence otherwise — which means
most days bring no email at all. The thing I actually reach for is the list
itself, checked in one action. The email exists for the days I forget to look.

## Non-goals

- **Buying.** It links out. It never transacts.
- **New-book retail.** Amazon, Bookshop, publisher direct — all out of scope.
- **Reselling or arbitrage.** This is for a reader. That framing is what makes
  it different from the closest existing tools.
- **Multiple users, accounts, or auth.** One user.
- **A mobile app.** Email is the notification channel.

## Success criteria

The tool works if I stop manually searching marketplaces, and if over a month
it surfaces at least one book I actually buy that I wouldn't otherwise have
found. If I still find myself opening AbeBooks by hand, it has failed
regardless of how much of it works.

A secondary criterion: I should be able to add a book to the want-list in under
thirty seconds. Anything slower and I won't bother.

## Market check

Nothing covers this. The closest adjacents, and why each falls short:

| Tool | What it does | Why it isn't this |
|---|---|---|
| [BookFinder](https://www.bookfinder.com/) | Aggregates used-book listings across marketplaces | On-demand search only — no persistent want-list, no alerts |
| [AbeBooks](https://www.abebooks.com/) / [Biblio](https://www.biblio.com/) want-lists | Saved searches with alerts | Each searches only its own inventory |
| [BookScouter](https://bookscouter.com/blog/launched-buyback-price-alerts/) | Price alerts on a watchlist of up to 20 books | Buyback prices — for *selling* books, the opposite direction |
| [BiblioPrice](https://biblioprice.com/) | Scans ISBNs across marketplaces, scheduled | Built for reseller arbitrage: ROI calculations, buy/sell spreads |
| [FlowMarket](https://flow-market.org/blog/best-deal-hunting-apps/) | Multi-marketplace listing alerts | Keyword matching with no concept of an edition or ISBN |
| [camelcamelcamel](https://camelcamelcamel.com/) | Price drop alerts | Amazon only |

The gap is a persistent, edition-aware want-list across *multiple* used-book
marketplaces, built for a reader rather than a reseller.

## The hard part

Not the polling — identity resolution. Turning "this book" into the set of
ISBNs that represent it is genuinely difficult:

- A reading copy and a collectible edition of the same book are different
  ISBNs, so a single ISBN is the wrong unit.
- Books published before roughly 1970 have no ISBN at all.
- Marketplace listings key on ISBN inconsistently, and sellers mistype them.

[Open Library](https://openlibrary.org/developers/api)'s works-and-editions
model is the right backbone. Getting this right is what separates the tool from
a saved keyword search, and it's where the time will go.

## Known risks

- **eBay developer registration can be rejected.** No workaround known. This is
  the anchor source, so the spike tests it before anything is built.
- **Biblio's API is granted through an affiliate program**, which implies an
  expectation of referral traffic this tool won't generate. The terms may not
  fit. If so, fall back to eBay-only rather than quietly ignoring them.
- **Open Library asks not to be used as a backend service.** Resolution must be
  cached hard and refreshed monthly, never called from the polling loop.
- **Pre-ISBN and print-on-demand titles will resolve poorly.** Manual ISBN
  entry is the escape hatch.

## Possible later

Checking library availability first, which is the actual first step in my
workflow — the tool currently assumes I've already determined the library
doesn't have it. Deliberately out of scope for v1.
