# Want list

## Purpose

The want list shows every book I'm watching and whether any copy is worth my attention, without opening a book.

## What it shows

- One row per book, most recently added first.
- The book's title, cover and author. A book with no cover shows its title on a placeholder.
- The cheapest copy's delivered price, as "from $10.49". It is green with ✓ when under the book's limit, and shows the amount over when over (see [pricing](../rules/pricing.md)).
- A strip of every asking price seen, with the limit as a dashed line, when there are at least two different prices.
- How many copies are listed, how many are new since the book was last opened, and how long ago it was checked: "3 listed · 2 new · checked 2h".
- When the book was added: "added 3w".
- "digging" while the app is working out which copies are this book. The row updates itself when that finishes. Tapping it explains.
- "Throttled" when that work is waiting because the day's Open Library requests are used up. Tapping it explains.
- A row's state when there is no price: Checking…, Couldn't check just now, Not checked yet, 2 maybes, or 0 listed.
- A switch between all the books and those with a copy under their limit: "All · Under limit". "Under limit" is greyed out when no book has a copy under its limit.
- Whether any books need checking: "Update 2", or "All current".
- Under those buttons, only when something is wrong with the daily check: "Daily check failed", "Daily check throttled" or "Daily check didn't run". Tapping it says when and why.
- "Nothing on the list yet" when the list is empty.

## What you can do

- Tap anywhere on a book's row to open its active listings. The trash, "digging" and "Throttled" keep their own taps.
- Tap "Under limit" to see only the books whose price is green, and "All" to see every book. The choice stays through opening a book and going back, and opening the app shows all. Adding a book shows all.
- Tap Update to check the books not checked in the last hour.
- Tap Check all to check every book. It asks first when some were checked in the last hour, unless this device was told not to ask again.
- Tap the trash icon to remove a book. It asks first.
- Tap + to add a book (see [adding a book](add-a-book.md)). Adding leaves nothing to go back through.
- Press back to leave the app.

## Open issues

- [Reorder the want-list by recency, lowest price, or by hand](https://github.com/loserpoints/book-watch/issues/131)
- [Drop the "$X over" amount, and make the limit easy to see on the price strip](https://github.com/loserpoints/book-watch/issues/200)
