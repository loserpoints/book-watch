# Active listings

## Purpose

Active listings shows the copies of one book for sale now, so I can judge each copy without opening its eBay listing.

## What it shows

- The book's cover, title, author and the ISBN it was added by, with "digging" while the app is still working out which copies are this book.
- A warning when the book was added as text rather than an ISBN, since that search finds worse matches.
- Three chips: the book's limit, the scope (US or Everywhere) and how long ago it was checked.
- One line per market, "3 used listed now, 12 seen", with a strip of every asking price seen. Each dot is green at or under the limit and red over it, and a blue line marks the limit when it falls among the prices (see [pricing](../rules/pricing.md)).
- How many copies match, then one row per certain copy (see [matching](../rules/matching.md)).
- Each copy's delivered price, green with ✓ when under the limit, or red when over. A copy with unknown shipping shows its price and "+ shipping?".
- Where each copy sits among the others of its kind, as a strip, or why it can't be placed.
- Each copy's condition, where it ships from when outside the US, "takes offers" when the seller accepts Best Offer, and its eBay listing title.
- "new" on a copy that appeared since the book was last opened (see [matching](../rules/matching.md)).
- When eBay first listed each copy, "listed 3w". A copy with no listing date shows no age.
- A switch between cheapest first and newest first, when there is more than one copy.
- What the seller says the copy is: "goodwill_books says: Paperback · Vintage · 1995".
- The seller's condition note, clamped to two lines.
- A photo of each copy, with a count when there is more than one.
- "N more that might be this book", folded, holding the possible copies.
- "Nothing listed in the US right now" with a link to look everywhere, when there are no copies.

## What you can do

- Tap the limit chip to set or clear the book's limit.
- Tap the scope chip to switch between US sellers and everywhere.
- Tap the checked chip to search eBay again.
- Tap Newest to see the latest listings first, and Cheapest to go back. The order stays through checking again, changing scope, going back and reloading. Opening a book shows cheapest first.
- Tap a copy's photo to see every photo, swiping between them.
- Tap a condition note to read all of it, and tap again to collapse it.
- Tap a listing title to open it on eBay.
- Tap the fold to see the copies that might be this book.
- Tap "digging" to see what it means.
- Press back to return to the want list, whatever was done on the page. With a sheet or photo open, back closes it first.

## Open issues

- [Dismiss a copy I've ruled out](https://github.com/loserpoints/book-watch/issues/105)
- [Remember which sellers I trust on condition](https://github.com/loserpoints/book-watch/issues/75)
