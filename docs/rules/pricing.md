# Pricing

## Purpose

These rules decide what a copy costs, whether it is under a book's limit, and where it sits among the other copies.

## Rules

### Prices

- Every price is a delivered price: the item price plus shipping.
- Shipping is priced to one US ZIP, set as the `SHIP_TO_ZIP` Fly secret. Without it, eBay does not price calculated shipping, and those copies have no delivered price.
- A copy has no delivered price when its shipping is not stated or is in a different currency from its price. eBay requires shipping on every listing except local pickup and freight, so this is rare for a book.
- Every price is an asking price. Nothing claims a copy sold, or sold for a given amount.
- Prices in different currencies are never compared or converted.

### Limits

- A book's limit is a delivered amount in one currency. An empty limit means no limit.
- A copy is under the limit when its delivered price is at or below it.
- A copy is over the limit when its delivered price is above it.
- A copy without a delivered price in the limit's currency is "can't tell". It is never under or over.
- An over copy shows the amount over.
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
- Copies sort by delivered price within their tier.
- Copies without a delivered price sort below every copy with one, by their price alone.

## Open issues

- [Set the ship-to ZIP in the app, not as a Fly secret](https://github.com/loserpoints/book-watch/issues/182)
- [Settings, starting with a default price limit and the US-only default](https://github.com/loserpoints/book-watch/issues/72)
- [Show whether a listing accepts offers](https://github.com/loserpoints/book-watch/issues/74)
