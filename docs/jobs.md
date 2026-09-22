# Jobs

The companion to `docs/product-brief.md`. The brief says what this is and why
it exists; this file says what I am actually trying to get done, and how I will
know each one is finished.

Six jobs. They change rarely — a job is a thing I want, not a thing I am
building, so it survives being re-planned. Each has a test that can **fail**,
because "how I'll know it's done" is worthless if every possible outcome
passes it.

Nothing here records status. A job is never "done" in the way a task is; what
ships against it lives on the GitHub milestones, and `docs/milestones.md` says
which milestone advances which job.

---

## J1 · Keep looking so I don't have to

**When** the library doesn't have a book I want and I've decided to buy a used
copy, **I want** to hand the title to something that keeps checking, **so
that** finding a copy doesn't depend on me remembering to search again next
week.

**How I'll know it's done.** A title sits on the list for a fortnight. When I
open the app on day nine, the results are already there and already dated — the
app didn't start searching when I arrived — and it can tell me which copies
turned up since I last looked. If opening the app is what triggers the search,
this isn't done.

**Open questions.** What a list entry actually *is*: a work ("Ballard, *Crash*,
any copy") or a specific edition ("the 1973 Cape first"). Reading mode wants
the first, collectible mode the second. Whether that's one entity carrying a
mode or two different entities is the first real schema decision, and the first
slice that writes to the database forces it.

---

## J2 · Narrow the pile to the few worth my attention

**When** a title has forty copies listed and most of them are wrong, **I want**
the few worth looking at to come to the top and the ones I've already rejected
to stay out of the way, **so that** I'm not re-reading the same bad listings
every morning.

**How I'll know it's done.** I open a title with dozens of listings and find
what I want in the first handful. A copy I rejected yesterday is not back at
the top today. This fails when I scroll past something good, and it fails when
the same ex-library copy greets me for the fifth day running.

**Open questions.** How to tell a genuinely new copy from a relisted one. The
concept is settled — new to *me*, not new to eBay — but eBay issues a fresh
item id when a seller relists, so identity across relists isn't free and the
cheap implementation gets this wrong in exactly the way that makes the job
fail.

---

## J3 · Judge one copy without opening the listing

**When** I'm looking at a candidate copy, **I want** its condition, what it
will actually cost me delivered, and a photograph in one place, **so that** I
can rule out five copies in six without opening a tab.

**How I'll know it's done.** I can reject a bad copy — ex-library, wrong
edition, a clipped jacket — from the results list alone, and I only click
through to copies I'm seriously considering. If I'm opening listings to find
out what they are, this isn't done however much data is on the page.

**Open questions.** How much of a seller's description is worth showing, and
where it comes from. It's arbitrary HTML — sometimes a single photograph,
sometimes a wall of shipping policy — and it may need a per-item call rather
than arriving with the search results, which would make it an API budget
question rather than a display one.

---

## J4 · Tell me when a copy appears

**When** a copy I'd want shows up, **I want** to hear about it without having
gone looking, **so that** finding it doesn't depend on me remembering to open
anything.

**How I'll know it's done.** I buy a book I didn't know was for sale until
something told me. The brief's own success criterion — that I stop opening
marketplaces by hand — is really this job's test rather than J1's, and it's the
job the first milestone deliberately doesn't touch.

**Open questions.** What is worth interrupting me for. A digest of everything
is a digest I stop reading within a week, and then the job has failed while
every part of it still works. A price threshold is the obvious filter and is
probably enough for reading copies; collectible mode's signal is condition
rather than price, so it may need something else entirely.

---

## J5 · Buy without wondering if I overpaid

**When** I've found a copy of an edition I collect, at a price high enough that
being wrong would annoy me, **I want** some sense of whether it's reasonable
for that book in that condition, **so that** I can decide now rather than defer
to go and check.

**How I'll know it's done.** I act on a listing without opening a second tab to
sanity-check the price. The failure this targets is specific and I've done it:
hesitate, go and check, come back, it's sold.

**Open questions.** The mechanism, deliberately — this job is recorded, not
designed. It is explicitly **not** committed to eBay's sold-listing data. Four
candidates, none chosen:

| Approach | Cost | What it actually tells me |
|---|---|---|
| Rank within current listings for the same edition | Free, no new API | Cheapest of what's listed *now* — not what it's worth |
| eBay Marketplace Insights (sold data) | Limited release, separate application, ~90 days | The real answer, if they grant it |
| Biblio or another aggregator's asking prices | Depends on decision 6 terms | Broad asking prices, not sold prices |
| Our own observed history | A table and patience | What copies of *the books I watch* have actually been listed at |

The last one is worth noticing: if every listing we see is recorded from the
first poll onward, then in a year there's a price series nobody can revoke,
specific to the few dozen books I care about, costing one table and zero extra
API calls. Useless on day one and compounding after that — which is an argument
for the table landing early even while the job stays unbuilt.

---

## J6 · Take a book off the list when I'm done with it

**When** I've bought a copy, or decided I don't want the book after all, **I
want** it off the list, **so that** the list stays a list of things I still
want rather than a log of things I once wanted.

**How I'll know it's done.** The list I open is one I trust — everything on it
is something I'd still buy today. It fails the moment I'm mentally filtering
out entries I know are stale.

**Open questions.** Whether "bought" and "gave up" need to be different states.
Bought may want to stay visible somewhere, because *did I already buy this?* is
a question I will ask. Gave up almost certainly doesn't.
