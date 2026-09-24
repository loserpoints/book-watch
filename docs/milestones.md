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

**The numbers are positions, and they move.** A number that does not match
where a milestone sits is just a lie with a label on it, so reordering
renumbers. Two rules keep that from costing anything:

- A **delivered** milestone keeps its number for good. Numbers are never
  reused, so M1 means one thing forever.
- Everywhere outside this file — a decision entry, an issue, a conversation —
  a milestone is referred to **by name**. Names do not move, so nothing has to
  be rewritten when the order changes.

---

## M3 · Keep what we saw, derive the rest

**Goal.** One invariant: **observations are kept and never rewritten;
everything else is derived on read.** A change to the matching rules then
applies to every book already on the list, for free, without a migration and
without asking anybody for anything twice.

**Jobs advanced.**

- **J2**, permanently rather than once. Every future improvement to precision
  reaches the books already on the list instead of only new ones.
- **J5**, by starting its clock. Its cheapest candidate — our own record of
  what copies have been listed at — needs observations to accumulate, and they
  currently do not.

**Why this exists.** *The right book* shipped a matching fix that did nothing
in production. A pass had earlier concluded that a number belonged to a book,
stored that conclusion in `edition`, and the grader reads a known edition
ahead of every other signal — so Don Gillmor's novel stayed matched to Joy
Williams's, behind the check written to reject it. Nothing could clean it up,
because `edition` holds two kinds of row with nothing to tell them apart: an
ISBN a person typed, and an ISBN a rule inferred.

The shape of that is the milestone. The system stores **conclusions** as
though they were facts, and discards **observations** as though they were
disposable:

| | | |
|---|---|---|
| **Observations** | what a seller declared · what Open Library says a number is · what was for sale | cost a request, cannot be re-derived, should only ever be appended to |
| **Conclusions** | which ISBNs are this book's editions · what tier a copy is · whether a book has been identified | derived by rules that will keep changing, and should be recomputed rather than kept |

Confidence tiers already work this way — `grade()` runs on every page view, so
a rule change reaches every book instantly. This milestone is that treatment
applied everywhere it is missing.

**Why before *What I will pay*.** Because it is the same bug pointing the other
way. A refresh **deletes** a book's copies and replaces them, so the price
history J5 depends on has never started accumulating: we are throwing away
observations while carefully preserving conclusions. Fixing that here settles
*What I will pay*'s one urgent question as a consequence rather than as a
separate decision, which is the sign the boundary is in the right place.

**What it changes, roughly three slices.**

- **The edition set is derived, not stored.** It is already a pure function of
  things on disk: which numbers declared on this book's copies does the
  catalogue call this title, by an author the sellers do not contradict. A
  join over data we have already paid for — **zero requests** — so a rule
  change re-derives every book on the next page view.
- **Copies are appended, not replaced.** What is for sale *now* stays a
  question the page answers; what was seen stops being destroyed to answer it.
- **Observations record what was captured.** The one genuinely expensive case
  is a rule needing a field we never fetched — which just happened with the
  seller's author, and cost re-asking about *every* listing because there was
  no way to tell a row captured before the field from one whose seller left it
  blank. A capture version makes that exact: re-ask only the rows that are
  actually stale.

**What this is not.** A way to edit the database by hand. That was the first
answer reached for and it is a diagnostic, not a fix — optimising the matching
is the main way this product improves, so the logic changing is the normal
case and has to be cheap by design rather than repairable by exception.

**Cost.** Kept observations grow without bound, on a volume of 1 GB — small
per row and worth watching rather than solving now. Deriving on read costs a
join per page view against tens of rows, which is nothing at this size and is
a real question at a thousand books.

---

## M4 · What I will pay, and whether this is fair

**Goal.** A price ceiling per book, and enough context to act on a listing
without opening a second tab to sanity-check it.

**Jobs advanced.**

- **J5**, which is recorded and unscheduled until here.
- **J2**, in part: a threshold is the bluntest and most useful filter there is.

**Why here.** A threshold — "under $8 delivered" — and *is this a fair price*
are the same question at two resolutions, and splitting them across milestones
would mean building price judgement twice. Both also depend on *The right
book*, which is now delivered: comparing a listing against others of the same
edition is only meaningful once editions are a thing the system understands,
and they are.

**The open question.** The mechanism is genuinely undecided — four candidates
are recorded against J5 and none is chosen. It is also the most open-ended
thing in the project and the likeliest source of scope creep, which is why the
concrete half (the threshold) is worth shipping first and on its own.

**Re-read after *The right book*, 2026-09-23.** Four things changed, and one of
them is urgent.

**The threshold is now nearly free.** Landed cost is already computed, stored
and sorted on, and a copy already carries the condition and what its seller
declared. "Under $8 delivered" is a filter over data that exists, not a feature
that needs data built for it.

**Price judgement may only use the certain tier, and that is measured rather
than cautious.** The *possible* tier ran at 8–14% precision on the edition
question. An average asking price computed across it would be an average of
mostly other books — the wrong number, confidently displayed, which is worse
than no number. Whatever mechanism wins, its input is the certain tier alone.

**The samples are smaller than they look.** *Crash* had six right-edition
copies among fifty-three listings. A fairness judgement on six observations is
a feeling with a decimal point on it. This milestone has to be able to say "not
enough copies to tell" and mean it, and that is a design requirement rather
than an edge case.

**The price history is being deleted, right now, on every refresh.** This is
the urgent one. J5's fourth candidate — our own observed history, "one table
and zero extra API calls", useless on day one and compounding after — assumed
listings would be recorded from the first poll onward. The table exists as of
*The right book*. But a refresh **replaces** a book's copies rather than adding
to them (decision 40), because the page's job is to show what is buyable now,
and a copy that stopped appearing has been sold.

So the clock on that candidate has not started. Every refresh since the page
shipped has thrown away what the previous one saw. Keeping it means a second,
append-only table — the same rows, never deleted — which is genuinely one table
and no extra calls, and which is worth nothing until it is worth a great deal.

**That urgency is what put *Keep what we saw* in front of this one.** Whether
to start recording was worth deciding immediately, because the cost of
deciding later is measured in months of data that will not exist — and it
turned out to be the same bug as the one that made a matching fix do nothing
in production, pointing the other way. Copies stop being deleted there, so by
the time this milestone starts the record has been accumulating for however
long it took to get here.

What to *do* with the record still waits, and should: J5's mechanism is four
candidates and none of them is chosen.

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
first* is an edition-level statement, and The right book is what makes editions a thing the
system understands.

**The open question.** Condition is the collectible signal, and eBay's condition
codes are far too coarse for it — jacket, printing and signature live in
free-text seller prose. Whether that is parseable, or whether collectible mode
is really "show me everything and let me read", is not yet known.

---

## M6 · Always current, without my looking

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
sits immediately before *Tell me* and could reasonably merge with it.

It is also the point at which the tool stops depending on my attention, which
is the brief's whole argument for existing — and that is the argument for
pulling it earlier. It loses to a simpler one: a tool that checks every day on
my behalf is worth having only once it is checking for the right thing. *The right book*, *What I will pay*
and *Two kinds of hunt* are what make it the right thing.

**Some of this arrives early regardless.** *The right book* cannot re-search every edition of
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

## M7 · Tell me, so I stop looking

**Goal.** A daily email containing only listings that are new since the last
one and inside the price ceiling set in *What I will pay*. Nothing arrives on a day when
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
  response, so this costs one `getItem` call per listing. *The right book* has
  since made that call anyway, for the seller's declared number — so the
  marginal cost of a description is now zero requests and one more stored
  field. What it still wants is *Always current* showing what a poll actually
  spends per day before anything else is added to it.
- **Relative dates** — [issue 22](https://github.com/loserpoints/book-watch/issues/22).
- **Checking the library first**, which the brief names as the real first step
  in the workflow and puts out of scope for v1.

---

## Delivered

Kept because what a milestone *taught* is the most useful thing it leaves
behind, and because a path you cannot see the start of is half a path. These
keep their numbers for good.

### M1 · See what's for sale

**Delivered 2026-09-22.** Add a book by ISBN, open it, see what is for sale
with condition, seller and landed cost, click through to buy.

**What it taught.**

- Shipping cost is in eBay's search response, so ranking on landed cost costs
  one call rather than one per listing (decision 22). The expensive branch was
  the one we did not get.
- Searching an ISBN as a keyword beats eBay's GTIN filter decisively, because
  sellers fill in the title and not the structured fields (decision 21).
- Descriptions are **not** in the search response, so J3's "read the condition
  without clicking through" has a known price of one call per listing. Still
  unscheduled.
- Every listing carries an `epid`, and searching it finds copies the ISBN text
  misses (decision 32). That finding is the reason *The right book* went first.
- Taking the escape hatch first paid: a usable tool in five slices, and the
  resolution problem now understood from use rather than imagined.

**What it got wrong.** `fly.toml` claimed a persistent volume that decision 10
had costed and nothing had ever mounted; a database written there would have
vanished on the next deploy, silently. Found while writing the schema, not by a
test. Three of the five slices turned up a defect of that shape — none of which
any test would have caught, because each was a gap between what a document
claimed and what existed.

---

### M2 · The right book, in any edition

**Delivered 2026-09-23.** Add a book by title and pick it from the catalogue,
or by number and read back what that number actually is. Open it and see every
copy for sale, grouped by how sure we are that it is the book, cheapest first.
The uncertain ones are shown, not hidden. What is still being worked out says
so, and stops saying so when it stops being true.

**What it taught.**

- **The hard problem was measurable, and measuring it changed the answer three
  times.** One search per edition turned out to be incoherent rather than
  expensive — *Pride and Prejudice* has 4,042 of them. `epid` turned out to
  over-merge. The stricter text floor for a collector turned out not to exist.
  None of those were arguable in advance and all three were cheap to check.
- **Neither catalogue has an identity key, and they fail in opposite
  directions.** eBay's product id over-merges; Open Library files one book
  under five work ids. That single finding shaped every slice after it, and a
  rule built on either would have been quietly wrong rather than loudly broken.
- **Grading beats filtering.** Nothing is discarded for being uncertain, which
  is why recall was 100% on both hunts on all three books. The uncertainty went
  into a label instead of into a judgement call.
- **Committing 227 hand labels turned a study into a regression net**, and it
  disproved a published decision on its first run. The labelling was a day's
  work; leaving it in a temporary directory would have thrown that away.
- **A stopwatch settled a design argument.** "Should the page fetch each
  listing's details?" had no version that fit a two-second page — even two
  calls was over — so the question dissolved rather than being compromised on.
- **Open Library's data dump is the wrong answer for one user and the right
  one for two**, and the reason flips from bytes to a per-address rate limit.
  Worth knowing that an argument can invert on scale rather than degrade.

**What it got wrong.** Five things, and four of them are the same thing:

- `docs/decisions.md` carried a claim nobody had measured — that the two hunts
  differ in two parameters — for several slices. **The decision record was the
  check, and it did not check.**
- The test suite called Open Library for real on every CI run. **Nothing
  failed**; the only symptom was the suite getting four times slower.
- `/health` answered `ok` without opening the database, so a machine with no
  storage reported itself well. Still true, tracked as its own issue.
- Two edits in the last slice silently did nothing. Tests passed, and the
  feature was simply absent from the page.
- And separately: production sat twelve slices behind `main`, so the migration
  that rewrote every want-list row shipped alongside five others instead of
  alone.

The pattern in the first four is worth more than the list: **a check that
exists is not a check that checks.** Each was caught by looking at the real
thing — the running page, the clock, the committed data — rather than by the
mechanism meant to catch it. Deploying on every merge, the network guard in
`conftest.py`, and asserting on rendered HTML rather than on the property
behind it are all responses to that, and none of them would have been obvious
before.
