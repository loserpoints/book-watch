# Matching

## Purpose

These rules decide which eBay listings are copies of the book being watched, and how sure the app is of each one.

## Rules

### Searching

- A book added by ISBN, or by text added anyway, is searched by exactly what was typed, as a keyword. A book picked from a title search is searched by its title and author.
- Searches return copies from US sellers. Searching everywhere is a choice made per view, and is not saved.
- Searches return fixed-price listings only, never auctions (see [pricing](pricing.md#prices)).

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
- A copy with no listing date is new when it was first seen after the visit.
- Nothing is new on a book never opened.

## Open issues

- [A reading copy is searched across every edition](https://github.com/loserpoints/book-watch/issues/130)
