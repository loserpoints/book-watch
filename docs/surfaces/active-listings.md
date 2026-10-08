# Active listings

## Purpose

Active listings shows the copies of one book for sale now, so I can judge each copy without opening its listing on eBay or AbeBooks.

## What it shows

- The book's cover, title, author and the ISBN it was added by, with "Still checking." while the app is still working out which copies are this book.
- A warning when the book was added as text rather than an ISBN, since that search finds worse matches.
- Three chips: the book's limit, the scope (US or Everywhere) and how long ago it was checked.
- One line when the book's last AbeBooks check failed, "AbeBooks check failed", or found nothing, "No copies on AbeBooks", which links to the search AbeBooks was asked. eBay's copies show either way.
- One line for every copy, new and used alike, "8 listed now, 12 seen", with a strip of every asking price seen. Each dot is green at or under the limit and red over it, and a blue line marks the limit when it falls among the prices (see [pricing](../rules/pricing.md)).
- How many copies match, then one row per certain copy from either marketplace, in one list (see [matching](../rules/matching.md)).
- Each copy's delivered price, green with ✓ when under the limit, or red when over. A copy with unknown shipping shows its price and "+ shipping?".
- A caret after a copy's price when the latest check that saw it moved it: ▾ down, ▴ up, in the price's color, as on the want list. A new copy has none (see [pricing](../rules/pricing.md#moves)).
- Where each copy sits among the others listed now, as a strip, or why it can't be placed.
- Each copy's condition, by one name per grade whatever the seller wrote: Brand New, Like New, Very Good, Good, Acceptable or Used. A grade without one of those names shows the seller's words.
- Where each copy ships from when outside the US, "takes offers" when the seller accepts Best Offer, and its listing title.
- "new" on a copy that appeared since the book was last opened (see [matching](../rules/matching.md)).
- When eBay first listed each copy, "listed 3w". A copy with no listing date, which is every AbeBooks copy, shows no age.
- "Cheapest · Newest" beside the match count, when there is more than one copy, with the chosen order in bold and the other underlined in blue, as every two-way choice in the app looks.
- What the seller says the copy is: "goodwill_books says: Paperback · Vintage · 1995".
- The seller's condition note, clamped to two lines.
- A photo of each copy, the seller's own or a stock cover, with a count in its top corner when there is more than one.
- Which marketplace each copy is on, as a band across the bottom of its photo or of the photo's placeholder. Screen readers hear it with the copy.
- "N more that might be this book", folded, holding the possible copies.
- "Nothing listed in the US right now" with a link to look everywhere, when there are no copies.

## What you can do

- Tap the limit chip to set or clear the book's limit.
- Tap the scope chip to switch between US sellers and everywhere.
- Tap the checked chip to search eBay and AbeBooks again.
- Tap Newest to see the latest listings first, and Cheapest to go back. The order stays through checking again, changing scope, going back and reloading. Opening a book shows cheapest first.
- Tap a copy's photo to see every photo, swiping between them.
- Tap a condition note to read all of it, and tap again to collapse it.
- Tap a price's caret to see what it was. The next tap anywhere closes it, and does nothing else.
- Tap anywhere on a copy to open its listing on its marketplace. The row fills while pressed. The photo, the condition note and the price's caret keep their own taps. The app remembers which copy was opened, so marking the book bought can offer it. Copies opened from the morning email aren't remembered.
- Tap the fold to see the copies that might be this book.
- Tap "Still checking." to see what it means.
- Press back to return to the want list, whatever was done on the page. With a sheet or photo open, back closes it first.

## Open issues

- [Remember which sellers I trust on condition](https://github.com/loserpoints/book-watch/issues/75)
