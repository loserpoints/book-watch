# M14 · Every shelf

## Learnings

- S63 and S64 checked the APIs and pages before reading what their terms allowed for this use. The terms ruled out the public app only after that work was done. A slice that depends on an outside service now reads its terms for the use first. [Plan slice](../../../.claude/skills/plan-slice/SKILL.md#questions)
- AbeBooks served a Claude Code session a different version of its search page from the one it served Fly: sorted by relevance, with grouped rows and copies without an ISBN. Only the read from Fly showed what the app would get. [API policies](../../rules/api-policies.md#reading-these-pages)
- S66's order check was written from three pages read from Fly and failed four books on the first Check all, over two rows 2 cents apart and one row $7 off. The order is now measured and counted ([#239](https://github.com/loserpoints/book-watch/pull/239)). [CONTRIBUTING](../../../CONTRIBUTING.md#building)
- A local run of the app searched eBay with this environment's real keys again, as in M13, despite the rule M13 added. A script that cannot make requests replaces the rule. [CONTRIBUTING](../../../CONTRIBUTING.md#testing)
- S65's migration test asserted that 025 was the newest migration and broke when S66 added 026. [CONTRIBUTING](../../../CONTRIBUTING.md#testing)

## Carried forward

- [An AbeBooks page the app can't read says "No copies on AbeBooks" instead of failing](https://github.com/loserpoints/book-watch/issues/242)
- [A want-list row shows "Checking…" and "digging" at once](https://github.com/loserpoints/book-watch/issues/241)
- [A want-list row can show more new copies than listed, and its counts lag behind Update](https://github.com/loserpoints/book-watch/issues/240)
- [Tapping Update doesn't clear its count](https://github.com/loserpoints/book-watch/issues/236)
- [See what the app does unattended, and hear when something is wrong](https://github.com/loserpoints/book-watch/issues/168)
- [Search Biblio as a second marketplace](https://github.com/loserpoints/book-watch/issues/145)
