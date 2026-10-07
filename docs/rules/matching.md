# Matching

## Purpose

These rules decide which eBay listings are copies of the book being watched, and how sure the app is of each one.

## Rules

### Searching

- A book added by ISBN, or by text added anyway, is searched by exactly what was typed, as a keyword. A book picked from a title search is searched by its title and author.
- Searches return copies from US sellers. Searching everywhere is a choice made per view, and is not saved.
- Searches return fixed-price listings only, never auctions (see [pricing](pricing.md#prices)).
- AbeBooks is searched by the book's main title, before any colon, and its author, written as AbeBooks writes them in a path: lowercase, punctuation dropped, words joined by hyphens. A book with no title is searched by the ISBN it was added by.
- AbeBooks answers with the 30 cheapest copies by delivered price, across editions and sellers worldwide. An edition whose copies all cost more than the 30th is not seen, and neither is any copy the seller gave no ISBN: the page served to the app leaves them out.
- AbeBooks' search also returns other books that share the title. Each copy is graded by the rules below, as eBay's are.
- An AbeBooks page that is a bot challenge, has grouped rows, has copies but no count, or has a copy without a price, shipping, id or link fails the check. Nothing is guessed from it, and the copies from the last good check stay listed.
- Price order is measured, not required. Real pages are only roughly cheapest first: page 1 of *Geronimo Rex* on 2026-10-06 had two neighbors 2 cents out of order and a French edition last at $32.53 among copies near $39.50. A copy is out of place when it is more than $1 cheaper than a copy above it, and a page with more than 3 out of place is out of order. Out-of-order pages are still read, logged, and counted in the daily check.
- An empty AbeBooks result links to the search that was read, so a book with no copies can be told from a search written wrong.

### Which listing it is

- A listing is identified by its marketplace and its id there, everywhere it is stored. Two marketplaces may use the same id for different listings.
- What is listed now is each marketplace's own newest search, so a search of one marketplace never hides another's copies.
- Only eBay's listings are ever sent to eBay to ask what a seller declared. Another marketplace's declarations are stored with the search that found them.
- One search that returns US and foreign sellers together feeds both views: everywhere shows every copy, and US-only shows the copies whose seller is in the US.
- Condition is stored on eBay's scale whatever the marketplace, with the marketplace's own words kept beside it. A copy's tag names its grade on that scale, so eBay's "New" and AbeBooks' "New" both read "Brand New", and "new" is left to copies new since the last visit. AbeBooks: New is New; As New and Fine are Like New; Near Fine and Very Good are Very Good; Good is Good; Fair and Poor are Acceptable. Near Fine maps down, so a grade undersells rather than oversells. A bare Used is eBay's generic Used, and shows only "Used".
- AbeBooks writes a seller's country at the end of their location. A copy whose country is not recognized is shown under everywhere and never under US-only.

### Which numbers are this book

- The ISBN a book was added by always counts as this book.
- An ISBN a seller declared counts when Open Library's title for it is this book's title, alone or followed by more words, and the seller names no other author.
- An eBay product id counts only when a listing carrying it also declared a number that counts.
- These numbers are worked out from stored observations each time a book is viewed, never stored as conclusions.
- An Open Library work id is never used to decide whether two editions are the same book.

### Grading

- Every listing is graded certain, possible or excluded. On a collector's hunt it can also be probable.
- A listing is certain when its declared ISBN is a number that counts, or its product id is one that counts.
- A listing is excluded when the seller names another author and the listing title does not mention this book's author.
- A listing is excluded when Open Library names its declared ISBN as a different book.
- A declared ISBN that Open Library names as this book, under a number not yet connected to it, makes the listing certain on a reader's hunt. On a collector's hunt it is probable if its product id counts, and excluded otherwise.
- A listing with no identifier that counts is possible when its title holds every significant word of the book's title, and excluded otherwise.
- Text alone never makes a listing certain.
- A number Open Library does not hold, or has not been asked about yet, excludes nothing.

### What is shown

- Certain copies are listed, and only they count toward prices and ranks.
- Possible and probable copies are folded under "might be this book".
- Excluded copies are not shown.

### What is new

- Opening a book records a visit. Opening it again within 30 minutes is the same visit.
- On a book's page, a copy is new when it was first seen after the previous visit began and eBay listed it no more than a day before that.
- On the want list, the count is of copies certainly this book that are new since the latest visit.
- A copy's listing date is the date eBay first listed it, which eBay keeps when an item is relisted (`itemOriginDate`).
- A relisted copy gets a new item id and keeps its original listing date, so it is not new.
- The day's margin covers eBay's search showing a listing after it was listed. A copy relisted within a day of first being listed shows as new.
- A copy with no listing date is new when it was first seen after the visit. AbeBooks gives no listing date, so this is how every AbeBooks copy is judged, and a relisted AbeBooks copy shows as new.
- Nothing is new on a book never opened.

## Open issues

- [A reading copy is searched across every edition](https://github.com/loserpoints/book-watch/issues/130)
