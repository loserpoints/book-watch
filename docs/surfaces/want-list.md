# Want list

## Purpose

The want list shows every book I'm watching and whether any copy is worth my attention, without opening a book.

## What it shows

- One row per book, most recently added first, or cheapest first.
- The book's title, cover and author. A book with no cover shows its title on a placeholder.
- The cheapest copy's delivered price, as "from $10.49". It is green with ✓ when under the book's limit, and red when over (see [pricing](../rules/pricing.md)).
- A caret after that price when the latest check moved it: ▾ down, ▴ up, in the price's color (see [pricing](../rules/pricing.md#moves)).
- The book's limit under the price, "your limit: $10", or "no limit set".
- A strip of every asking price seen, when there are at least two different prices. Each dot is green at or under the limit and red over it, with green on top, or blue with no limit. A blue line marks the limit only when it falls among the prices.
- How many copies are listed, how many are new since the book was last opened, and how long ago it was checked: "3 listed · 2 new · checked 2h". Both count the same copies, so new is never more than listed.
- When the book was added: "added 3w".
- "checking" in place of the counts from the moment a book is checked until its copies have been examined, with its last price kept meanwhile. The row updates itself when that finishes. Tapping it explains.
- "Throttled" when that work is waiting because the day's Open Library requests are used up. Tapping it explains.
- A row's state when there is no price: Couldn't check just now, Not checked yet, 2 maybes, or 0 listed.
- Under the title, only when something is wrong with the daily check: "Daily check failed", "Daily check throttled" or "Daily check didn't run", as plain text. Tapping it says when and why.
- One Check button. It reads "Check 2" when two books weren't checked in the last hour, and "Check all" when every book was. While a check runs it says how far it has got, "Checking 2 of 5…", and is greyed out. It counts down as books are checked, and keeps up after adding a book and when a book's copies finish being examined.
- An "Under limit" switch beside it, to show only the books with a copy under their limit. It is greyed out when no book has one. With it on, a book joins or leaves the list once a check finishes.
- Over the rows, how many books show and their order: "6 books · Cheapest · Added". Cheapest goes by each row's "from $X", with books that have no price last. Not shown for a single book.
- The whole list drawn again on going back to it, and on coming back to the app after a minute or more away, unless a check is running.
- "Nothing on the list yet" when the list is empty.
- Below the list, once a book has been bought, a folded "Bought · 3 books · $26.95". Opened, each book bought shows its cover, title and author, where and when it was bought, and what was paid, green at or under the limit the book had then and red over it.

## What you can do

- Tap anywhere on a book's row to open its active listings. The row fills while pressed. The trash, the price's caret, "checking" and "Throttled" keep their own taps.
- Tap the "Under limit" switch to see only the books whose price is green, and again to see every book.
- Tap Cheapest or Added to change the order.
- The switch and the order stay through opening a book and going back. Opening the app shows every book, newest added first, and so does adding a book.
- Tap "Check 2" to check the books not checked in the last hour.
- Tap "Check all" to check every book again. It asks first, unless this device was told not to ask again.
- Tap a price's caret to see what it was, "Was $12.40". The next tap anywhere closes it, and does nothing else.
- Tap the trash icon to take a book off the list. A sheet asks which way: "I bought it" or "I don't want it".
- "I bought it" asks where (eBay, AbeBooks, or elsewhere with the shop's name), what was paid delivered, and the day, with the phone's own date picker. It is filled in from the copy of this book last opened from the app, with that copy's marketplace and delivered price and today's date, and says when that copy was opened. Mark bought, and the book leaves the list for the Bought section and stops being checked and emailed. A bought book can't be put back.
- "I don't want it" removes the book, and nothing is kept.
- Tap + to add a book (see [adding a book](add-a-book.md)). Adding leaves nothing to go back through.
- Press back to leave the app.

## Open issues

- [An app left open through a deploy redraws the new markup without the new styles](https://github.com/loserpoints/book-watch/issues/256)
- [A Bought page, as a compact diary of what I've bought](https://github.com/loserpoints/book-watch/issues/258)
