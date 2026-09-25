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
2. **The want-list** *(below)*
3. **Adding a book** *(below)*
4. **The book page, around the copies** *(below)*
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

**Checking, intent only — names and form tabled.** Three needs, no settled
design:

1. A way to check the books that have gone stale
2. It has to be clear that a book checked within the hour is skipped, and
   why — before the tap, not only after it
3. A separate control that overrides the hour and checks everything

Candidates looked at and not chosen: *Update (2)* / *Check all*, where the
count says how many are stale and reads *All current* at zero; *Refresh* /
*Refresh everything*; *Check what's stale* / *Check all now*. Revisit in S27
or S30, with the look in front of us.

**Why "not checked yet" survives S23.** Adding a book starts its check from
the page, so closing the tab first leaves it unchecked. A check that fails is
not stored either, so after a reload a failed book reads as unchecked. And
books added before S23 were never checked. Rare, but it has to look different
from "nothing listed", which is a claim about the market.

### 3. Adding a book

Alan's calls, 2026-09-25: the content is right and only the styling changes.
One addition: say plainly which fields can be used together, so it does not
look as though all three are needed.

**What the form actually accepts**, which that wording has to match rather
than flatter:

- **a title**, optionally with an author to narrow it — searches Open Library
  and offers candidates
- **an ISBN**, which takes over: a title typed beside it is used only as the
  name if the number is added anyway
- **an author alone is refused** ("Enter a title, or an ISBN.")

So "any combination" is not true today. The copy says what is true — title,
optionally with author, or an ISBN — unless an author-only search is built,
which is a behaviour change and not M6's.

Further calls, same day:

- **Title and author by default, ISBN behind a switch.** An ISBN is a hard
  match and a title is a search; they are two different ways in, and the form
  should look like it. The panel opens on title-and-author, with a control to
  flip to ISBN.
- **The whole candidate row is the tap target**, not only "This one"
  (principle 5). The small button already caused a mis-tap in production.
- **Author-only search, adding several books at once**: wanted, and a
  behaviour change, so it is #101 rather than M6.

**Open question: does adding close the panel?** Closing it shows the new row
checking itself. Keeping it open is what adding several books by one author
(#101) needs. Alan leans towards keeping it open; settle it with #101.

### 4. The book page, around the copies

Alan's call, 2026-09-25: every fact P1–P9 is right, and there is far too much
text before the first copy. Keep all of it and consolidate it visually, so the
copies start near the top of a phone screen.

Found on the way:

- **The P2 warning shows on every book added by title**, where it is false —
  #102. It should show only for text added in place of an ISBN.
- **That text lives in the ISBN field**, which accepts anything after one
  refusal. A better home is the title search, when it finds nothing — logged
  on #101.

## Open

- **A signature.** Something that makes it feel like itself — possibly how
  covers are rendered, a typeface, or the voice of loading and "we don't know"
  states. Principle 3 is a candidate: honesty about partners, written in a
  voice nobody else would use. Not decided; collect candidates as they turn up.
