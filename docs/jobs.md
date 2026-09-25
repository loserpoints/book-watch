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

**Answered 2026-09-25: a copy under the ceiling, and nothing else.** The open
question was what is worth interrupting me for, on the reasoning that a digest
of everything is a digest I stop reading within a week — and then the job has
failed while every part of it still works. The answer is the narrow one. A new
copy under the price ceiling set on that book is worth an email; nothing else
is. On a day when no copy qualifies, no email is sent at all, so an empty inbox
is the ordinary case rather than a failure.

That also settles what this job is *for*. It is a backup for the days I forget
to look, not the way I normally use the tool — the list, checked in one action,
is that. The job's test below is unchanged and still the brief's real success
criterion: hearing about a copy I had not gone looking for is a different thing
from finding one quickly, and only this job delivers it.

**Open questions.** Collectible mode's signal is condition rather than price,
so a ceiling may be the wrong filter for it entirely — that stays open until
*Two kinds of hunt* says what a collectible entry actually wants.

**What it still depends on.** "New" has to mean new to me, which is the relist
identity problem recorded against J2. A relisted copy under the ceiling would
email me about a book I already saw and passed on, which is exactly the failure
that makes an alert worthless.

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
