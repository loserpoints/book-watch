# Milestones

A milestone is a set of work that delivers usable value by advancing at least
one job in `docs/jobs.md`. A slice is a technical deliverable that gets a
milestone closer to done, and lives as a GitHub issue on that milestone.

```
job  ──advanced by──  milestone  ──delivered by──  slice
 why                   value                        work
```

A slice links to its milestone and no further. Its relationship to a job is
transitive, and deliberately so: a migration runner serves whatever comes next,
and stamping a job on it would assert a precision that isn't there.

The aim is one slice per milestone. Some will straddle two — when that happens,
split it if both halves ship independently, and give it to the earlier
milestone if they don't.

## How to read the ones that haven't started

Everything past the current milestone is a **path of travel, not a plan**. The
order is an argument, and the argument is written down so it can be disagreed
with. Each entry says why it sits where it does; that reasoning is the part
worth attacking.

**At the close of every milestone, the remaining ones get reviewed** — reordered,
merged, split or dropped, based on what the finished one actually taught. A
milestone that survives three reviews unchanged was probably right. One that
keeps sliding was probably never a milestone.

**Status is not recorded here.** Which of these are finished, and how far along
the current one is, lives on the GitHub milestones. Writing it in both places is
how the two start disagreeing — and only one of them updates itself.

Only the current milestone gets its slices written as issues. The rest stay as
one paragraph until they are next.

**The numbers are names, not positions.** This file is ordered by what happens
next, and that order changes at reviews — renumbering each time would break
every reference to a milestone from a decision, an issue or a conversation. So
M2 sits fourth and that is not a mistake. Read down the page.

---

## M1 · See what's for sale

**Goal.** Add a book by ISBN and see the eBay listings for it right now.

**Jobs advanced.**

- **J1**, in part. The list remembers a title, though nothing re-runs on its
  own yet.
- **J3**, in part. Listings arrive with condition, cost and an image.
- **J6.** An entry can be removed.

**Why this first.** It turns the two biggest unknowns into facts: what eBay's
search response actually contains, and whether shipping cost comes with it or
needs a second call per item. The second answers whether ranking by landed cost
is nearly free or an API budget problem, and that shapes every milestone after
this one. It is also the smallest thing that is genuinely usable — one book, one
list, real listings.

**What it deliberately isn't.** No edition resolution: ISBNs are typed in by
hand, which the brief already names as the escape hatch. No stored listings, no
modes, no ranking, no email.

Taking the escape hatch first inverts the brief, which calls resolution the hard
part. That is the point. A working product in five slices instead of a dozen,
and the shape of the resolution problem learned by being annoyed at typing
ISBNs rather than guessed at up front. The cost is real and accepted: some of
what M1 builds will be rewritten once resolution lands.

**One temporary state worth naming.** M1 calls eBay when a page loads. At a
handful of page views a day that is nothing against 5,000 calls, but it is a
placeholder for the cache, not a design — M2 replaces it (decision 30).

---

## M4 · The right book, in any edition

**Goal.** A want-list entry means a book rather than one ISBN. It can be added
by title and author, not only by ISBN. The set of editions that count is known,
and listings that are not one of them are rejected.

**Jobs advanced.**

- **J1**, properly. "Ballard, *Crash*, any copy" becomes one entry rather than
  a dozen.
- **J2**, completed. Precision, not just ranking: the wrong book stops
  appearing.

**Why first.** Automating something that returns the wrong books only sends the
wrong books daily. Matching is what everything after this is worth doing on top
of, and it is the part that is genuinely hard rather than merely unbuilt. It is
also the biggest change to the data model, since decision 26 currently makes a
row an ISBN.

**What is already measured.** Searching eBay for an ISBN string is not the same
as finding copies of that edition. Nearly every used-book listing carries an
`epid` — eBay's own product id — and searching by it finds listings the ISBN
search misses, because plenty of sellers never type the ISBN at all. Decision
32 has the numbers. Searching by title and author instead finds many editions
but reaches any *specific* one poorly.

**The open question, and it is the real one.** A work has many editions, and
covering all of them looks like one search per edition — which is both slow on
a page and wasteful of the call budget. Whether that is solved by caching the
edition set hard, by covering only the editions that actually have inventory,
or by a title-level search filtered on known product ids, is not known. This is
what the first slice of M4 exists to settle, and it should settle it by
measuring rather than by choosing.

**It will pull storage forward.** Whatever the answer, re-searching every
edition on every page view is not it — so some of M2's caching arrives here.

---

## M6 · What I will pay, and whether this is fair

**Goal.** A price ceiling per book, and enough context to act on a listing
without opening a second tab to sanity-check it.

**Jobs advanced.**

- **J5**, which is recorded and unscheduled until here.
- **J2**, in part: a threshold is the bluntest and most useful filter there is.

**Why here.** A threshold — "under $8 delivered" — and *is this a fair price*
are the same question at two resolutions, and splitting them across milestones
would mean building price judgement twice. Both also depend on M4: comparing a
listing against others of the same edition is only meaningful once editions are
a thing the system understands.

**The open question.** The mechanism is genuinely undecided — four candidates
are recorded against J5 and none is chosen. It is also the most open-ended
thing in the project and the likeliest source of scope creep, which is why the
concrete half (the threshold) is worth shipping first and on its own.

**What M2 will quietly buy it.** Once listings are stored daily, the tool
accumulates its own record of what copies of *these* books have been listed at.
In a year that is a price history nobody can revoke, specific to the books I
actually watch, costing one table and no extra API calls. Useless on day one,
compounding after — an argument for the storage being right in M2, not for
building anything here early.

---

## M5 · Two kinds of hunt

**Goal.** An entry is a reading copy or a collectible, and the mode changes what
matches and how it ranks: lowest landed cost and a readable floor for one,
edition and condition quality for the other.

**Jobs advanced.**

- **J2** and **J3**, for the collectible case, which until now has been served
  by machinery designed around price.

**Why here.** The brief describes two use cases sharing a pipeline and differing
only in matching and ranking — so the pipeline has to be right first. Collectible
mode is also the one that most needs edition resolution: wanting *the 1973 Cape
first* is an edition-level statement, and M4 is what makes editions a thing the
system understands.

**The open question.** Condition is the collectible signal, and eBay's condition
codes are far too coarse for it — jacket, printing and signature live in
free-text seller prose. Whether that is parseable, or whether collectible mode
is really "show me everything and let me read", is not yet known.

---

## M2 · Always current, without my looking

**Goal.** The daily poll runs, listings are stored, and opening a book shows
what is there — already fetched, already dated, with what is new since I last
looked marked as new.

**Jobs advanced.**

- **J1**, completed. The list re-runs itself. Opening the app no longer starts
  the search.
- **J2**, in large part. Sorting by landed cost, and dismissing a listing so it
  stops coming back.

**Why here, rather than earlier.** The digest cannot exist without it: "new
listings" needs a record of the old ones, and "new" has to mean new *to me*
rather than new to eBay, which is a stored fact and not a computed one. So it
sits immediately before M3 and could reasonably merge with it.

It is also the point at which the tool stops depending on my attention, which
is the brief's whole argument for existing — and that is the argument for
pulling it earlier. It loses to a simpler one: a tool that checks every day on
my behalf is worth having only once it is checking for the right thing. M4, M6
and M5 are what make it the right thing.

**Some of this arrives early regardless.** M4 cannot re-search every edition of
a book on every page view, so caching turns up there whether or not the poll
does. What is left here is the daily cadence and the memory it builds.

**Stored does not mean stale.** Everything the page shows comes from the store,
and a refresh updates the store — so live-on-demand survives and the memory is
gained rather than traded for. Decision 30 originally said the page must stop
searching, which was too strong a rule drawn from a correct reason; it is
amended.

**The hard part.** Identity across relists. eBay issues a fresh item id when a
seller relists, so the cheap implementation will call the same copy new every
few days — and that is exactly the failure that makes "what's new" worthless.
J2's open question.

**Probably the largest milestone here**, and the most likely to split at its
first review: the poll, the listing schema, seen-state, ranking and dismissal
are five separable things.

---

## M3 · Tell me, so I stop looking

**Goal.** A daily email containing only listings that are new since the last
one and inside the price ceiling set in M6. Nothing arrives on a day when
nothing qualifies.

**Jobs advanced.**

- **J4.** The job M1 deliberately left empty.

**Why last.** It is the brief's actual success criterion — *I stop manually
searching marketplaces* — so it is tempting to pull forward, and that temptation
is the trap. A digest is a daily statement that these listings are worth your
attention. Send it before matching is right and it is a daily demonstration
that they are not, which is a habit that takes far longer to undo than it took
to form.

Everything before this exists to make the email worth opening.

---

## Not scheduled

Real, wanted, and not yet worth a position in the order.

- **Biblio as a second source.** The brief's market argument rests on searching
  *multiple* marketplaces, and eBay-only is a nicer saved search. Blocked on
  whether the affiliate terms fit (decision 6), which is not a scheduling
  question.
- **Seller descriptions in the app.** J3 wants condition detail without clicking
  through, and S1 established the price: descriptions are not in the search
  response, so this costs one `getItem` call per listing. That is an API budget
  decision, and it wants making after M2 shows what the poll actually spends.
- **Relative dates** — [issue 22](https://github.com/loserpoints/book-watch/issues/22).
- **Checking the library first**, which the brief names as the real first step
  in the workflow and puts out of scope for v1.
