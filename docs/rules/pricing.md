# Pricing

## Purpose

These rules decide what a copy costs, whether it is under a book's limit, and where it sits among the other copies.

## Rules

### Prices

- Every price is a delivered price: the item price plus shipping.
- A copy has no delivered price when its shipping is not stated or is in a different currency from its price.
- Every price is an asking price. Nothing claims a copy sold, or sold for a given amount.
- Prices in different currencies are never compared or converted.

### Limits

- A book's limit is a delivered amount in one currency. An empty limit means no limit.
- A copy is under the limit when its delivered price is at or below it.
- A copy is over the limit when its delivered price is above it, or when shipping is unknown and its price alone is above it.
- Any other copy with a limit set is "can't tell", and says whether shipping is unknown or the currency differs.
- An over copy shows the amount over. When shipping is unknown, the amount is a minimum and carries a plus: "$2+ over".
- A limit marks copies and never hides them.

### Markets and ranks

- New and used copies are separate markets and are never counted together.
- Only certain copies count in ranks, ranges and the want-list's price (see [matching](matching.md)).
- A copy's rank is its place by delivered price among certain copies of its market listed now. Copies at the same price share a rank.
- A market's range spans every certain copy of that market ever seen, one price per copy.
- A copy without a delivered price or a condition code is not ranked, and says why.
- A range is drawn only when it holds at least two different prices.

### Order

- The want-list shows each book's cheapest certain copy in its leading market. Used leads when it has copies listed; otherwise new.
- Copies sort by delivered price within their tier. A copy without one sorts by its price alone.

### The morning email

- A copy is in the morning email when its book has a limit, it is certain, it is under the limit, it is new since the book was last opened (see [matching](matching.md)), and it has never been in an email.
- A copy with unknown shipping is never in the email.
- One email a morning at most, sent after the daily check. No such copy, no email.
- A copy is in at most one email, ever. A failed send records nothing, so the next morning tries the same copies.

## Open issues

- [Copies with unstated shipping sort to the bottom](https://github.com/loserpoints/book-watch/issues/104)
- [A default price limit per hunt, inherited by new books](https://github.com/loserpoints/book-watch/issues/107)
- [Show whether a listing accepts offers](https://github.com/loserpoints/book-watch/issues/74)
