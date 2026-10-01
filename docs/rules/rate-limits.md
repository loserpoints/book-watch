# Rate limits

## Purpose

These rules keep the app's requests to eBay and Open Library small, spaced out and within what each service allows.

## Rules

### Open Library

- Requests are at least 1.5 seconds apart, enforced in the client.
- No more than 500 requests are made in any 24 hours. The count is kept in the database, so it holds across restarts.
- When the ceiling is reached, the request is not made and the work stops. Nothing retries it on a timer.
- Every answer Open Library gives is stored, including "no record of this number". It is asked again only when the app starts reading a new field from it.
- A lookup that fails stores nothing. The number is skipped and the pass carries on, and it is asked again the next time the book has new copies. Two failures in a row stop the pass, since Open Library is most likely down.
- Adding a book costs one request. Examining one book's copies costs roughly ten to fifteen.
- A book's new copies are examined after any check that finds them, one pass per book at a time.
- A book's cover is looked up at most once, in no more than two requests. Cover images load from Open Library's image server, not its API.

### eBay

- The daily allowance is 5,000 calls.
- A search asks for 50 results.
- A search result carries each copy's price and shipping, so a delivered price costs no extra call.
- Opening a book searches eBay only if that book was not searched in the last hour for the same scope. Tapping Checked searches regardless.
- Update searches only the books not searched in the last hour. Check all searches every book.
- Checking several books searches them one at a time, never in parallel.
- Every book is searched once a day at 7am New York time, one at a time, and each book's new copies are examined before the next book is searched. A run the app was down for runs when it starts again. Each run records how many Open Library requests it spent.
- Each listing's details are fetched once, ever. A listing is fetched again only when the app starts reading a new field, and only while it is listed.

### Resend

- At most one request a day, after the daily check, and none on mornings with nothing to send.

### Both

- Opening the want-list makes no requests.
- Every request names the app and links its repository in its User-Agent.

## Open issues

- [S57 · A number Open Library can't answer is skipped, and the rest of the book's copies are still examined](https://github.com/loserpoints/book-watch/issues/61)
- [Create a contact address for the app, and put it in the User-Agent](https://github.com/loserpoints/book-watch/issues/40)
