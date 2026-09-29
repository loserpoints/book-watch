# M8 · Always current

## Learnings

- A test passed only because an earlier test had left a book marked as being examined. Process-wide state is now reset between tests. [CONTRIBUTING](../../../CONTRIBUTING.md#testing)
- The daily check's summary line never printed until the production entrypoint was run, because no test starts the thread and the app logged only warnings. [CONTRIBUTING](../../../CONTRIBUTING.md#testing)
- "Throttled" and the daily check pill both appear only when something is wrong, which makes their appearance mean something. [Design system](../../design-system.md#principles)
- "Hit limit" would have read as the price limit, so the Open Library cap became "Throttled". [Design system](../../design-system.md#principles)
- eBay keeps a relisted copy's original listing date, so relists are left out of "new" by date and S38's matching was never built. [Matching](../../rules/matching.md#what-is-new)
- A real daily check over six books spent no Open Library requests. [Rate limits](../../rules/rate-limits.md#open-library)
- Each run's outcome and spend are read from the `Daily check:` line in Fly's logs. [Runbook](../../runbook.md#deploy)
- Checking a change on the phone against live data replaced verifying against a copy of production. [CONTRIBUTING](../../../CONTRIBUTING.md#testing)
- A cited issue number means nothing without its name. [CLAUDE.md](../../../CLAUDE.md#working-rules)
- A milestone's GitHub description is its goal and a link to its folder. [Governance](../../governance.md#workflow)

## Carried forward

- [Stale references left in code comments, two of them missed by the docs check](https://github.com/loserpoints/book-watch/issues/155)
- [Open issues written before the docs migration point at retired docs and decision numbers](https://github.com/loserpoints/book-watch/issues/156)
- [A defect has no way to ship outside a milestone](https://github.com/loserpoints/book-watch/issues/157)
- [Tap anywhere on a want-list row to open its listings](https://github.com/loserpoints/book-watch/issues/159)
- [Back after saving a price limit returns to the want list](https://github.com/loserpoints/book-watch/issues/160)
