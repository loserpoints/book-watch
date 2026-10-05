# M13 · What I can buy

## Learnings

- S59, S60 and S62 were described, built and only then shown, and S61's layout took five rounds against two agreed. It settled once the mocks were rendered by the app with every case seeded. A screen change is now planned from those mocks. [Plan slice](../../../.claude/skills/plan-slice/SKILL.md#mocks)
- S39 had confirmed that eBay keeps a relisted copy's date, but the code read `itemCreationDate`, the relist's own date, rather than `itemOriginDate`. A relist could count as new and be emailed until S62. [CONTRIBUTING](../../../CONTRIBUTING.md#building)
- S59 and S62 asked Alan to look up a documentation page named from memory, which didn't exist. The endpoint and field names from the code found it. [CONTRIBUTING](../../../CONTRIBUTING.md#building)
- A local run of the app searched eBay with this environment's real keys and examined about 50 copies, because the seeded book was over an hour old. [CONTRIBUTING](../../../CONTRIBUTING.md#testing)
- S60's fix for a wrapping row stopped its width changing but made it wider, so the row Alan saw then wrapped every time. It was measured for the change, not for the phone where it broke. [CONTRIBUTING](../../../CONTRIBUTING.md#testing)
- The start of M13 closed #141 as stale while M8's close pull request was set to close it. [Set milestone](../../../.claude/skills/set-milestone/SKILL.md#issues)
- Checking a field the app drops needed a search run on Fly, where the eBay keys are. The Search eBay once workflow does that from a browser. [Runbook](../../runbook.md#deploy)

## Carried forward

- [The book page uses "new" for both the new-copy market and copies new since I last looked](https://github.com/loserpoints/book-watch/issues/213)
- [Rethink the header controls, and make the two-way choices one component](https://github.com/loserpoints/book-watch/issues/217)
