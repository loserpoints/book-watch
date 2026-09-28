# M1 · See what's for sale

## Learnings

- Searching an ISBN as a keyword finds far more copies than eBay's structured ISBN filter, because sellers fill in titles and not fields. [Matching](../../rules/matching.md#searching)
- Shipping arrives in the search response, so a delivered price costs no extra call. [Rate limits](../../rules/rate-limits.md#ebay)
- The deploy config claimed a storage volume nothing had ever mounted. Found by checking the claim, not by a test. [CONTRIBUTING](../../../CONTRIBUTING.md#building)

## Carried forward

- [Verify eBay notification signatures before the deletion handler touches the database](https://github.com/loserpoints/book-watch/issues/6)
