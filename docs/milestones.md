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

## M6 · Judge a copy at a glance

**Goal.** A visual language the whole app is built in, so a copy can be ruled
out from the list without reading it word by word.

**Jobs advanced.**

- **J3**, which is substantially a presentation problem: *reject a bad copy —
  ex-library, wrong edition, a clipped jacket — from the results list alone.*
  Everything that judgement needs is now on the page, and it is on the page as
  undifferentiated text.
- **J2** and **J6** follow from the same work: what comes to the top has to
  *look* like it came to the top, and a list is only trusted if it is legible.

**Why here, rather than at the end.** Because everything after it is more
screens. *Two kinds of hunt* adds a mode, a second ranking and condition
preferences; *Always current* adds what-is-new marking; *Tell me* adds an
email, which is a rendering surface with far harsher rules than a web page.
Building the system first means those are built inside it rather than restyled
afterwards, and it is the difference between one design pass and four.

**Why not earlier.** There was not enough of the app to generalise from. Four
screens with one kind of thing on them is not a design system, it is a
stylesheet — and a system derived from too little is one you fight later.

**The open question, answered.** Whether decision 2's no-build-step rule
still fits. It does, for new reasons recorded under decision 2: the platform
now carries what a build step used to, and nothing in the design needs a
framework. The principles the system is built to live in `docs/design.md`.

**Covers come first.** The reference apps lean on artwork, and the want-list
has no cover for a book. Open Library already returns cover ids in responses
the app makes and discards, so the first slice stores them and caches the
images, and the tokens and primitives are then designed around real covers
and real gaps rather than a mock-up.

---


## M7 · Two kinds of hunt

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

## M8 · Always current, without my looking

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

There is now a lead on it. A relist **preserves the original listing date**
(decision 44), so two item ids sharing a seller, a price and a listed date are
very likely one copy. That is a heuristic rather than an identity key and it
belongs to this milestone to measure, but it is a better starting point than
treating every new id as a new copy.

**A pass is scheduled by somebody opening a book's page, and by nothing else.**
So a book nobody opens never gets examined, and a book that failed to resolve
stays unresolved until a person happens to look at it — *Keep what we saw*
found one in exactly that state. That is tolerable while a human drives every
page view and stops being tolerable the moment the tool is supposed to run
without attention. A poll that examines on its own schedule is the fix, and it
is this milestone's, not a bug to patch before it.

**Probably the largest milestone here**, and the most likely to split at its
first review: the poll, the listing schema, seen-state, ranking and dismissal
are five separable things.

---

## M9 · Tell me, so I stop looking

**Goal.** An email when a copy appears under the ceiling set in *What I will
pay*, and no email otherwise. Not a digest — J4's open question was answered on
2026-09-25 and the answer was the narrow one, so most days bring nothing at
all.

**Jobs advanced.**

- **J4.** The job *See what's for sale* deliberately left empty.

**Why last.** It is the brief's actual success criterion — *I stop manually
searching marketplaces* — so it is tempting to pull forward, and that
temptation is the trap. An alert is a standing claim that what it interrupts
you for is worth your attention. Send it before matching is right and it is a
recurring demonstration that it is not, which is a habit that takes far longer
to undo than it took to form.

**It is a backup, and that is a demotion made deliberately.** *The whole list,
in one look* is how the tool is actually used; this is for the days nobody
looks. That lowers its priority and does not lower its bar — an alert that
fires wrongly is worse than no alert, because the list is still there and still
trustworthy.

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

### M3 · Keep what we saw, derive the rest

**Delivered 2026-09-24.** Observations are kept and never rewritten;
everything else is derived on read. Which ISBNs are a book's editions is now a
query over what sellers declared and what the catalogue says those numbers
are, so a matching rule change re-judges every book on the list at the next
page view, for no requests. A refresh adds to what is for sale instead of
replacing it, and what a copy has cost over time is queryable. Every stored
observation records which version of the code captured it, so the one case
that genuinely costs requests — a rule needing a field we never fetched — can
re-ask about only the rows that lack it.

Four slices rather than the three estimated. Separating what somebody typed
from what a rule concluded had to come first, and was not visible until the
first slice was planned in detail.

**What it taught.**

- **This was filed as an invariant and was really a bug with a deadline.** Two
  of the four slices repaired things that were actively wrong in production,
  not merely inelegant. "The system stores conclusions as though they were
  facts" sounded like an architectural preference and was the reason a shipped
  fix did nothing.
- **What grows is what you stop deleting, not what you start writing.** The
  slice was designed around sighting rows being the term to worry about.
  Measured on the real database, a sighting is **40 bytes** and a copy is
  **490** — and copies are the ones that now accumulate forever. The entire
  cost analysis had been pointed at the wrong table, and one query corrected
  it.
- **Slices interacted in ways neither issue predicted.** Keeping copies
  forever made the ended-listing rule in the next slice load-bearing rather
  than an edge case: after it, most rows eligible for re-asking belong to
  listings eBay answers 404 for. Shipped in the other order, a recapture pass
  would have quietly destroyed good declarations across the whole want-list.
- **The signal was already in the code, being thrown away.** Deciding what to
  do when a re-ask returns less than what is stored produced a plausible
  heuristic — never overwrite a non-null with a null — and the real answer was
  that `detail.py` had always known the difference between 404 and 200 and was
  collapsing both into an empty answer. Worth checking whether a distinction is
  being discarded before inventing a proxy for it.
- **Deriving on read is cheap, and now measured rather than assumed.** 0.199ms
  to 0.265ms per page assembly, against a two-second budget of which one eBay
  search spends 300–500. The first draft of that decision asserted "page time
  did not move" without having run anything.
- **Keeping a production-shaped database was the thing that made verification
  real.** Every slice was checked against a copy of the live file, not a fresh
  one. Both production bugs that opened this milestone were invisible to tests
  precisely because tests start empty — a fresh database cannot contain a
  conclusion drawn under an older rule.

**What it got wrong.**

- **A migration that guesses.** 010 identified a typed ISBN as "the edition row
  with nothing else in it", which is right for every row we have and stated its
  residual in the file. It is still a guess in a migration, and the capture
  version that makes guessing unnecessary arrived three slices later.
- **A decision entry claimed a timing nobody had measured**, caught before the
  commit rather than after, which is the same failure M2 recorded and not yet a
  habit that has stopped happening.
- **Uncommitted work was reverted with `git checkout`** while undoing a
  deliberate mutation test. Recovered from a copy, one file redone. Mutation
  testing on a dirty tree needs the tree committed first.
- **"Stuck" is still a state only a person can clear.** A pass is scheduled by
  opening a book's page and by nothing else, so a book nobody opens never
  heals. It happened to be fine — the book in question healed the moment it was
  opened — and the design flaw is real and belongs to *Always current*.

The pattern worth keeping: **the cheapest check in this milestone was a copy of
production and a script that grades it.** Every real finding came from running
the new code against the actual file — the stored wrong conclusion, the 490-byte
row, the zero-stale migration. None of them were reachable from the test suite,
and all of them were reachable in under a minute.

---

### M4 · What I will pay, and whether this is fair

**Delivered 2026-09-25.** A delivered-cost ceiling per book that marks rather
than hides, searches scoped to copies in the US with a peek at everywhere, a
page that shows what is listed *now* rather than what was listed once, and each
copy placed among the others of its kind.

**What it taught.**

- **There is no sale data, and the wording is where that gets lost.** eBay
  answers 404 for an ended item and says nothing about why; Marketplace
  Insights is a limited release that is not open to new users. "Sold for" and
  "went for" are conclusions, "was listed at" and "stopped appearing" are
  observations (decision 47). The milestone's own re-read made this error three
  days after shipping a milestone about exactly this distinction.
- **A clever exception can be worse than no signal.** A listing with quantity
  above one exposes real sales — and fires almost entirely on bulk sellers,
  which is the opposite of the population this tool watches. A biased sample
  does not merely fail to help; it compounds into a more confident error. It
  survived one round of argument and not the second.
- **The page had swept once, ever.** Decision 40's "search only on the first
  view" travelled along with a correct measurement without being argued for,
  and produced a watcher that did not watch. A correct answer to the question
  you happened to ask is the easiest kind of wrong thing to ship.
- **`total` is scoped to the query, not to the market** — found by running a
  real search rather than by reading the documentation, which had been read and
  had not said so.
- **An overseas listing does not add a row, it displaces one.** Filtering at
  the API rather than on read was worth measuring: the unfiltered search lost a
  US copy it never returned at all (decision 49).
- **New and used are two markets rather than two grades** (decision 52), and
  the samples are smaller than they look once split. *State of Grace* has zero
  used copies. "Not enough to say" is the common path.
- **Every price is a delivered price** (decision 51), stated as a theme after
  the question had been answered three times locally. Shipping is where a
  seller can park margin so it does not show up in a sort.
- **Mutation testing earns its keep.** Two bad tests were found by breaking the
  code and watching nothing fail — a ceiling test that fetched its entry before
  setting the ceiling, and a range rule tested on the function but never on the
  page it is wired into.

J5's four candidates resolved without a decision being forced: **rank within
current listings** is what shipped, because it needs no floor, works at two
observations, and claims nothing about value. Our own observed history is
accumulating underneath it and is still the compounding asset it was argued to
be — it is simply not yet old enough to say anything.

---

### M5 · The whole list, in one look

**Delivered 2026-09-25.** The want-list shows each book's cheapest copy, what
its market has asked, and whether anything is under the ceiling. *Check all*
walks the shelf one book at a time; a book added checks itself. The range moved
off every copy and above the list it describes.

**What it taught.**

- **A range belongs to the class, not the copy.** Shipping it per copy — which
  is what the slice specified — rendered the same nine-word clause eight times
  on a twelve-copy book, crowding out the one thing that varies. Reading the
  result was the only way to see it; the spec looked right.
- **The walk skipped its first book, silently.** The step that starts a run
  rendered book one as "checking" and pointed the chain at book two, so book
  one sat in that state for ever, was never searched, and the run reported one
  book too few while otherwise looking correct. The first step has nothing to
  report and only a book to start — treating it as though it had finished
  something is what cost the book.
- **A row has four states and three are easy to say wrongly.** Nobody has
  looked, nothing is listed, copies are listed but none can be compared, and
  here is the cheapest one. "Nothing listed in the US" over a book nobody has
  searched for is a confident claim about a market we never asked about, and it
  is what the obvious implementation says. It is also wrong over copies in the
  *might be this book* tier: those copies exist.
- **Driving the thing before writing its tests found all three.** None came
  from the suite, and a test written from the spec would plausibly have missed
  the first two.
- **The debt was not where it was expected.** The refactor survey was prompted
  by the reasonable guess that early code would be the worst; the early modules
  are the best in the repo. Early boundaries were drawn when each job was
  genuinely small, and early mistakes did not survive — *Keep what we saw*
  rewrote the stored conclusions and migrations 010, 012 and 015 dropped
  superseded columns. What needs watching is any file that grew 60% in three
  days.
- **There was no performance problem to find.** Ten books with twelve copies
  each render in 12.2ms over 72 queries. The duplication that was removed was
  removed for legibility, and saying so kept the sweep honest about its own
  value.
- **Moving code is how two dead tests were found.** One existed to stop the
  search client being made eager — its docstring said so — and had been passing
  while patching a module the client had left. Neither turned up by looking for
  them; both turned up because a refactor forced them to move.
- **Mutation testing keeps earning its place, and one mutation lied.** A string
  replacement silently failed to apply and the "pass" meant nothing. A mutation
  result is only evidence once the source is confirmed changed.

**Twice now, on process.** Uncommitted work was reverted with `git checkout`
while undoing a mutation — the same mistake *Keep what we saw* recorded — and
a `check.sh` run was piped through `grep`, which masks its exit code, so a
failing lint read as green. Mutation testing needs a committed tree, and a
check's exit status needs reading.
