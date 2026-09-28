# M3 · Keep what we saw, derive the rest

## Learnings

- Storing conclusions as facts was why a shipped fix did nothing. Deriving them on read re-judges every book at no cost. [Matching](../../rules/matching.md#which-numbers-are-this-book)
- The code already told an ended listing from a live one, and was throwing the difference away. [CONTRIBUTING](../../../CONTRIBUTING.md#building)
- Every real finding came from running the change against a copy of production. Tests start empty and could not see any of them. [CONTRIBUTING](../../../CONTRIBUTING.md#testing)
- Uncommitted work was lost while undoing a deliberate break. [CONTRIBUTING](../../../CONTRIBUTING.md#testing)

## Carried forward

- [Stop re-asking Open Library about numbers that never resolve](https://github.com/loserpoints/book-watch/issues/61)
