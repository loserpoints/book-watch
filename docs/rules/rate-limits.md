# Rate limits

## Purpose

These rules keep the app's requests to eBay and Open Library small, spaced out and within what each service allows.

## Rules

### Open Library

- Requests are at least 1.5 seconds apart, enforced in the client.
- No more than 500 requests are made in any 24 hours. The count is kept in the database, so it holds across restarts.
- When the ceiling is reached, the request is not made and the work stops. Nothing retries it on a timer.
- Every answer Open Library gives is stored, including "no record of this number". It is asked again only when the app starts reading a new field from it.
- A request that fails to reach Open Library stores nothing, so the question is asked again on the next pass.
- Adding a book costs one request. Examining one book's copies costs roughly ten to fifteen.
- A book's cover is looked up at most once, in no more than two requests. Cover images load from Open Library's image server, not its API.

### eBay

- The daily allowance is 5,000 calls.
- A search asks for 50 results.
- A search result carries each copy's price and shipping, so a delivered price costs no extra call.
- Opening a book searches eBay only if that book was not searched in the last hour for the same scope. Tapping Checked searches regardless.
- Update searches only the books not searched in the last hour. Check all searches every book.
- Checking several books searches them one at a time, never in parallel.
- Each listing's details are fetched once, ever. A listing is fetched again only when the app starts reading a new field, and only while it is listed.

### Both

- Opening the want-list makes no requests.
- Every request names the app and links its repository in its User-Agent.

## Open issues

- [Stop re-asking Open Library about numbers that never resolve](https://github.com/loserpoints/book-watch/issues/61)
- [Create a contact address for the app, and put it in the User-Agent](https://github.com/loserpoints/book-watch/issues/40)
