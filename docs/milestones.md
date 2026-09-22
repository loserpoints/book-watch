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

**Only the current milestone is written down.** Later ones are guesses until
the current one teaches us something, and a roadmap of guesses is the thing
this pattern exists to avoid. **Status is never recorded here** — the GitHub
milestone holds the slices, and a closed issue is the only record that
something is done.

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
placeholder for the cache, not a design — M2 replaces it. If it survives into a
milestone that polls, something has gone wrong.
