# Pricing

## Purpose

These rules decide what a copy costs, whether it is under a book's limit, and where it sits among the other copies.

## Rules

### Prices

- Every price is a delivered price: the item price plus shipping.
- Shipping is priced to one US ZIP, five digits, set in [Settings](../surfaces/settings.md) and read by every eBay search when it runs. Without it, eBay does not price calculated shipping, and those copies have no delivered price. A changed ZIP reprices nothing at once: each book's delivered prices follow from its next check.
- AbeBooks prices shipping to a country, the US for the app, not to a ZIP. A delivered price from AbeBooks and one from eBay are compared as they stand, though AbeBooks' can be off for a given address where a seller charges by distance.
- A copy has no delivered price when its shipping is not stated or is in a different currency from its price. eBay requires shipping on every listing except local pickup and freight, so this is rare for a book.
- Every price is an asking price. Nothing claims a copy sold, or sold for a given amount.
- Searches find fixed-price listings only. An auction's price is its current bid, which nobody can pay, so auctions are never found.
- A copy that takes Best Offer says so. It is still under or over its limit by its asking price.
- Prices in different currencies are never compared or converted.

### Limits

- A book's limit is a delivered amount in whole dollars, from $1 to $999. An empty limit means no limit.
- A new book starts with the default limit set in [Settings](../surfaces/settings.md), if there is one, as its own. Changing the default changes no book already on the list. Settings can set the default on the books that have no limit, and on no other.
- A purchase keeps the limit its book had when it was bought.
- A copy is under the limit when its delivered price is at or below it.
- A copy is over the limit when its delivered price is above it.
- A copy without a delivered price in the limit's currency is "can't tell". It is never under or over.
- An over copy is shown in red, with no ✓ and no amount over.
- A limit marks copies and never hides them.

### Ranks and ranges

- New and used copies are counted together. Condition is shown on each copy, and is not a separate market.
- Only certain copies count in ranks, ranges and the want-list's price (see [matching](matching.md)).
- A copy's rank is its place by delivered price among the certain copies listed now in its currency. Copies at the same price share a rank.
- A book's range spans every certain copy ever seen in one currency, one price per copy.
- A copy without a delivered price is not ranked, and says why. A copy with no stated condition is ranked like any other.
- A range is drawn only when it holds at least two different prices.

### Moves

- Each check notes a book's "from" price just before it stores anything. Stores within ten minutes of each other, eBay's and AbeBooks', for US sellers and everywhere, are one check and share one note. Only a US search takes it, since only US copies feed the want list.
- The want list compares the "from" price now with that note. Lower is a move down and higher a move up, by any amount. The same price, no note, or no price before or now is no move. The next check that leaves the price where it was clears the move.
- Copies examined after the search count toward the same check.
- A copy moved when the latest check that saw it changed its delivered price, read from its price history. A copy whose shipping isn't known on either side has no move. A copy new since the last visit shows as new, not moved.

### Order

- The want-list shows each book's cheapest certain copy, new or used. When copies are listed in more than one currency, a currency with a copy under the limit leads; otherwise the one with the most copies listed.
- Copies sort by delivered price within their tier, or newest first when asked, by the date eBay first listed them (see [matching](matching.md#what-is-new)). Newest first puts copies with no listing date last.
- Copies without a delivered price sort below every copy with one, by their price alone.

## Open issues

- [Set the ship-to ZIP in the app, not as a Fly secret](https://github.com/loserpoints/book-watch/issues/182)
- [Settings, starting with a default price limit and the US-only default](https://github.com/loserpoints/book-watch/issues/72)
