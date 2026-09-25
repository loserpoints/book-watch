# Design

*Last updated: 2026-09-25*

How book-watch should look and behave, and why. Read it before building or
changing a screen. The tokens and primitives that implement it are M6's
work; this file is the argument they answer to.

## Where these came from

Three apps Alan uses and likes, each for something specific:

- **nzb360** — the closest in shape: add things to a list, see the list
  cleanly, tap in for detail. It depends entirely on other people's APIs and
  says so honestly. A row gives you everything you need at a glance: artwork,
  title, one line of facts, one line of status as colour and a few characters.
- **Letterboxd** — lists as image grids, and filters that cost one tap. A
  two-state filter is a toggle, never a dropdown that takes two taps to reach
  the obvious choice.
- **Excalidraw** — does its one job and nothing else, gives the content the
  whole screen, and has a signature look that comes from one opinionated
  choice rather than from decoration.

## Principles

1. **Clarity over clutter.** If it does not help decide, it is not on the
   list. It can be one tap away.
2. **The next tap is obvious, and it does what it looks like it does.**
3. **Say when we are waiting on a partner, and when something is stale or
   unknown.** Unknown is shown as a value in the same weight as known values,
   never hidden and never implied. Loading says what it is waiting for.
4. **Fewest taps to the answer.** A toggle beats a dropdown whenever there are
   two states. Filters anticipate the obvious choice.
5. **Collapse to a symbol and a short phrase; explain on tap.** The whole row
   or chip is the target, never a small icon that has to be hit exactly. Hover
   is a desktop bonus and never the only way to reach something, because a
   phone has no hover. How far each sentence collapses is decided case by
   case, and never at the cost of the wording rules in decisions 47, 51 and 53.
6. **It is a tool, and the covers carry the warmth.** The interface stays
   neutral and gets out of the way; the books supply the atmosphere.
7. **Phone first.** Thumb-sized targets, main actions within thumb reach,
   respect the notch and gesture area, behave sensibly offline. Designed as if
   it will be an app, without building as if it will be public.
8. **Dark first, light kept working.** Every colour is a token with both
   values, so light mode is never a redesign — but dark is the one tuned.
9. **One accent colour**, for what is current or can be acted on. Everything
   else is neutral.

## What each row says

S26 (#94). Settled one step at a time, in this order, each recorded here as
it lands:

1. **Inventory** — every fact a row shows today *(below)*
2. The copy row's headline
3. The rejection signals: edition, condition, location, seller
4. The photograph
5. The seller's description
6. Uncertainty, compactly
7. The book page's frame
8. The want-list row
9. List or cover grid
10. One-tap toggles
11. Tap-to-explain
12. The mock-up

### 1. Inventory, as of S25

**A copy, on the book page**

| # | Fact | Shown today as |
|---|---|---|
| C1 | The seller's photo | 72×96 thumbnail, or "no image" |
| C2 | The listing's title | Link to eBay, new tab |
| C3 | Against the ceiling | "Under your limit"; "Shipping not stated — can't tell"; "Priced in another currency — can't compare". **Over says nothing** |
| C4 | Condition | eBay's words, or "condition unstated" |
| C5 | Seller | Their eBay name |
| C6 | Where it ships from | "ships from GB", only when not the US |
| C7 | What the seller says it is | "seller states: Hardcover · Vintage · 1995" |
| C8 | Delivered price | "$13.49 delivered", or "$7.00 + shipping unknown" |
| C9 | How that splits | "($7.00 + $6.49 shipping)" or "calculated at checkout" |
| C10 | Where it stands | "Cheapest of 6 used copies", "Tied 2nd…", or which of three reasons it can't be placed |
| C11 | Certain or possible | Position: possible copies sit in a collapsed "N more that might be this book" |

**Around the copies, on the book page**

| # | Fact | Shown today as |
|---|---|---|
| P1 | Title, and the ISBN it was added by | Heading, and a grey line |
| P2 | Searched as text, not ISBN | A warning sentence |
| P3 | The ceiling | An always-open form |
| P4 | How many match | "12 matches." |
| P5 | How fresh | "Checked 4 minutes ago" and "Re-run search" |
| P6 | Scope | "Showing copies in the US. Look everywhere" |
| P7 | Each market | "9 used copies listed now, asking $18–36 delivered across 12 seen." |
| P8 | Still working | "Still digging through the shelves.", reason on hover |
| P9 | Nothing found | A sentence, with "Look everywhere" when the US is empty |

**A book, on the want-list**

| # | Fact | Shown today as |
|---|---|---|
| B1 | Cover | Cover, or the placeholder (S25) |
| B2 | Title | Link to the book page |
| B3 | ISBN it was added by, and when | "9780679723004 · added 2026-09-22" |
| B4 | Still working | "still digging", reason on hover |
| B5 | The glance | "cheapest used $13.49 — under your limit · 6 listed, seen $11.00–$36.00 · checked 2 hours ago", or checking / failed / not checked / nothing listed / N that might be |
| B6 | Remove | A button on every row |

**Around the books, on the want-list**

| # | Fact | Shown today as |
|---|---|---|
| L1 | Add | Title, author and ISBN fields, always open at the top |
| L2 | Candidates | Cover, title, author, year, edition count, "This one" |
| L3 | Count | "2 books." |
| L4 | Check | "Check all" and "Re-check everything" |
| L5 | Credit | "Covers from Open Library." |

## Open

- **A signature.** Something that makes it feel like itself — possibly how
  covers are rendered, a typeface, or the voice of loading and "we don't know"
  states. Principle 3 is a candidate: honesty about partners, written in a
  voice nobody else would use. Not decided; collect candidates as they turn up.
