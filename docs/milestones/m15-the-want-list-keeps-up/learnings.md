# M15 · The want list keeps up

## Learnings

- S67 took a second pull request. The first made the header current after a check, but going back to the list and waking the phone still showed the old one. A slice that keeps a screen current now plans every way a person reaches it. [Plan slice](../../../.claude/skills/plan-slice/SKILL.md#questions)
- S68 found that a second check during a running examination lost copies for good. Greying out the buttons would have left the 7am check open, so the examination itself now goes round again for copies that arrive while it runs. [CONTRIBUTING](../../../CONTRIBUTING.md#building)
- S69's browser run found that switching "Under limit" off had kept the list filtered since S60. The tests asked for the list without the header htmx sends with it. [CONTRIBUTING](../../../CONTRIBUTING.md#testing)
- S69's first check on the phone showed the new layout unstyled, because the app had stayed open through the deploy. Closing and reopening it fixed it. [CONTRIBUTING](../../../CONTRIBUTING.md#testing)
- S69 asked Alan for his ideas before each round of mocks and finished in three rounds, the goal set at the start of M15. [CONTRIBUTING](../../../CONTRIBUTING.md#building)
- Setting up M15 stalled on creating the GitHub milestone, which `gh api` can do from a session. [Set milestone](../../../.claude/skills/set-milestone/SKILL.md)

## Carried forward

- [AbeBooks now groups an edition's cheapest copies into one row, and the check fails on those books](https://github.com/loserpoints/book-watch/issues/253)
- [An AbeBooks page the app can't read says "No copies on AbeBooks" instead of failing](https://github.com/loserpoints/book-watch/issues/242)
- [See what the app does unattended, and hear when something is wrong](https://github.com/loserpoints/book-watch/issues/168)
