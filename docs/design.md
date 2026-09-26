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
5. **A copy** *(below)*
6. ~~The mock-up~~ — skipped by Alan's call: S27 restyles whatever a plain mock-up
   would show, so the directions are drawn straight from the calls here

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

### 5. A copy

Alan's calls, 2026-09-25: the facts are right, and the row is far too
text-heavy. It has to get more visual.

| # | Call |
|---|---|
| C1 | Tapping the photo enlarges it |
| C9 | The price/shipping split goes. The delivered price alone is enough (both stay stored, decision 51) |
| C3 | "Can't tell" copies sort below every copy with a known delivered price, rather than by their price alone — #104 |
| C3 | A copy whose price alone is already over the limit is over, whatever the postage — #103 |
| C3 | Over the limit must be marked. It is computed and never rendered — a bug against decision 50, #103 |
| new | Dismiss a copy into a collapsed *Dismissed* group — #105. Imperfect across relists, and accepted as such |
| C1 | Confirmed: tapping the photo enlarges it — and with #106, shows every photo |
| C9 | Confirmed: the split is stored and not displayed |
| J3 | Ex-library and jacket condition: a modal with the full listing is barely better than opening eBay. What would beat it is the seller's condition note and all the photos, which the item call already made once per listing returns and we drop — #106 |
| J3 | The listing description is out: long, arbitrary HTML, full of seller banners. #106 keeps only the short condition note and the photo URLs — no extra calls, a few hundred bytes a copy, nothing loaded until a photo is tapped |

### What S26 hands to S27

Every screen came back with the same note: the right facts, far too much
text. That is S27's brief. The specific open visual questions, collected:

- **The under/over symbol**, paired with a coloured price. Not an arrow
- **"Still digging" as something visual** rather than words
- **The seen range as a small picture** beside the want-list row (#76)
- **Checking**: the stale-only control, the hour rule made visible, and the
  override — three needs, no names yet
- **The book page frame** (P1–P9) consolidated so copies start near the top
- **The copy row** made visual: price as the headline, the rest compact
- **The add panel**: + button or expanding panel, title-and-author with an
  ISBN switch
- **The cover placeholder**, deferred from S25

## The direction (S27, #95)

Three directions were drawn on the same S26 content and published as a page
to open on a phone: **A · Shelf** (warm, serif, amber), **B · Wall**
(Letterboxd-style cover grid, cool, green) and **C · Catalogue** (library
card catalogue, typewriter, violet date-stamp).
[The page](https://claude.ai/artifact/FNuEVupwmv4LiGL1R1UwJb) keeps all three
for reference.

**Chosen: A's shelf with C's typewriter.** Warm dark ground, amber accent,
covers with a spine edge and a shadow, Courier Prime for titles and prices,
IBM Plex Sans for everything else, and a round + in thumb reach.

**Round-one calls on the chosen direction, 2026-09-26:**

- **Price strips label their ends.** The lowest and highest asking price sit
  under the two ends of the strip, which brings the range back without taking
  more room. The dashed line is the limit, and the larger dot is the cheapest
  copy listed now.
- **Long titles take the full width of the row.** The price and strip sit
  below the title, on the right.
- **Check all asks first:** *"Check all 7 books? 5 of them were checked within
  the last hour and will be searched again. To check only the 2 that are out
  of date, use Update."* It has a *Don't ask me again* box. This settles the
  checking question S26 tabled: *Update (n)* checks only the stale books, and
  *Check all* overrides the hour and asks first.
- **Too concise in two places:** *"checked just now"*, not *"now"*, and
  *"only new listing"*, not *"only new"*.
- **Put back what the first drawing dropped:** "added 3w" on the list; each
  copy's eBay listing title, which is also the link to eBay and often says
  "ex-library" itself; and *"Seller says:"* before the edition line, because
  decision 33 treats that line as the seller's claim, not a fact.

**Rounds two and three, same day:**

- **Strip ends are rounded to whole dollars.** The headline price keeps its
  cents; the strip's labels only mark the range.
- **Check all's sheet offers Update, not Cancel.** The cheaper action is the
  alternative, and tapping outside the sheet closes it.
- **"asking, delivered" is gone from the book page.** By then every price is
  known to be delivered, and the label confused more than it told.
- **On the want-list, the title sits above the cover**, full width. The cover
  then sits beside author, counts, price and strip, which are about its
  height, so long titles no longer push text below the cover.
- **"added 2d ago"**, with "still digging" shown as the three dots alone on
  the list so the line fits on a phone (measured at 390px wide: exactly
  fits). Tapping the dots gives the words. The book page keeps the word.
- **A copy's text wraps under its photo** and uses the full width once past
  it. Centring the photo against the text was tried and was worse.
- **The seller's condition note** (#106) shows as a quoted line on the copy,
  clamped to two lines. Tapping expands it in place, which beats a modal
  because the copy stays in view. Sellers do write paragraphs here.

**Round four, reversing two round-three calls:**

- **Back to "added 2d", with no "ago".** "2d" is the shortest the age gets,
  and "10mo ago" would force a wrap. "Still digging" becomes the word
  *digging* with a slow shimmer, instead of three dots. At 390px wide,
  "added 2d · digging" fits exactly, and "added 10mo · digging" overflows by
  about 8px. That is a rare pair; S30 decides how the line gives way.
- **The copy's text sits beside the photo again.** Only the condition note
  runs full width underneath. Wrapping everything under the photo looked bad.
- **"1st of 3" becomes a small strip beside the price**, because the old
  wording did not say it was about price. Every dot is a copy of the same
  kind listed now, and this copy is the large dot. That is decision 53's rank
  population, drawn rather than counted. A copy with unknown shipping says
  "can't place: shipping unknown", and the only copy of its kind keeps its
  words ("only new listing").
- **The want-list strip's dots are all one colour.** The cheapest is always
  the left end, so emphasising it said nothing. The strip is for the spread,
  and the limit line stays.
- **The accent is one of Alan's.** It was amber, carried over from nzb360.
  Dodger blue (`#1e90ff` dark, `dodgerblue4` `#104e8b` light) and dark orange
  (`#ff8c00` dark, `#b35900` light) are both on the page to compare. Leaning
  blue: an orange accent sits too close to the coral that means "over".
- **Notes collapse again:** tap to expand, tap to collapse. A note short
  enough to fit in two lines has nothing to expand.

**Round five, and the direction settled:**

- **The accent is dodger blue:** `#1e90ff` in dark mode and `dodgerblue4`
  `#104e8b` in light, Alan's own colours from his charts. Every dot on the
  want-list strips is blue.
- **The seller's claim is attributed by name:** "goodwill_books says:
  Paperback · Vintage · 1995". The separate seller line goes. This line and
  the condition note below it run full width under the photo; the price,
  condition, listing title and dismiss sit beside the photo. It is the
  compact layout the earlier rounds were reaching for.

**Where it came from, noted for the record.** Alan's charts in
`movie-analysis` and `hockey-analysis` use dot-and-range plots with an
emphasised point, dashed guide lines at reference values, and an italic
subtitle that explains the guides. The price strip is the same idea: dots
for every asking price, a dashed guide at the limit, the cheapest copy
emphasised. The charts mostly use Trebuchet MS, with IBM Plex Sans through
`theme_ipsum_ps`. Trebuchet is not on Android or Google Fonts, so Plex Sans
stays.

## Open

- **A signature.** Something that makes it feel like itself — possibly how
  covers are rendered, a typeface, or the voice of loading and "we don't know"
  states. Principle 3 is a candidate: honesty about partners, written in a
  voice nobody else would use. Not decided; collect candidates as they turn up.
