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

S26 (#94). Settled one screen at a time, in the order they are used, each
recorded here as it lands. Twelve abstract steps were the first plan; a
screen at a time turned out to be the unit a decision can actually be made in.

1. **Inventory** — every fact each screen shows today *(below)*
2. **The want-list** *(in progress, below)*
3. Adding a book
4. The book page, around the copies
5. A copy
6. The mock-up, tying it together

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

### 2. The want-list

Alan's calls, 2026-09-25, against the labelled screenshot:

| # | Call |
|---|---|
| L1 | Too much room for something done occasionally. Collapse it behind a **+** button (as nzb360 does) or an expandable panel. The three fields stay as they are |
| L3 | Keep the total |
| L4 | Keep *Check all*, and keep the hour gate on it |
| L5 | Keep the Open Library credit |
| B3 | "Added" becomes a timeframe ("3 days ago"), using the logic already in an issue |
| B5 | "cheapest used $13.49" collapses to something like "from $13.49" |
| B5 | Under or over the limit is shown by colouring the price, not by words |
| B5 | The seen range becomes a small picture — a distribution, or a bar, with a mark for the current cheapest — to the right of the text rather than in it |
| B5 | "Nothing listed" still has to be said, but shortly — a count of what is listed, for instance |
| B6 | Remove becomes a trash icon, and keeps its "Remove Crash from the list?" confirmation |
| B3 | The ISBN leaves this screen; it stays on the book page |
| B4 | "Still digging" stays: it is the transparency principle 3 asks for. Ideally visual rather than words — how is S27's problem |
| B5 | "Checked 2 hours ago" stays per row, shortened. A single list-wide age was rejected: a book just added makes any one number wrong for the rest |
| B5 | *Checking* and *Couldn't check* are both shown. *Not checked yet* is rare since S23 checks on add, but still real (see below) |
| B5 | No used/new label. Which market the row reports is unchanged — used, falling back to new when there is no used copy (decision 52 still governs what is computed; this only drops the word) |
| B5 | When no copy is certain, the row says so as a count: "2 maybes" |
| B5 | Books with no limit, or whose cheapest copy has unknown shipping, get an uncoloured price |
| B5 | Colour is paired with a symbol, to be chosen in S27. Not an arrow: arrows read as a trend, and this is a comparison with a fixed line |

**Why "not checked yet" survives S23.** Adding a book starts its check from
the page, so closing the tab first leaves it unchecked. A check that fails is
not stored either, so after a reload a failed book reads as unchecked. And
books added before S23 were never checked. Rare, but it has to look different
from "nothing listed", which is a claim about the market.

## Open

- **A signature.** Something that makes it feel like itself — possibly how
  covers are rendered, a typeface, or the voice of loading and "we don't know"
  states. Principle 3 is a candidate: honesty about partners, written in a
  voice nobody else would use. Not decided; collect candidates as they turn up.
