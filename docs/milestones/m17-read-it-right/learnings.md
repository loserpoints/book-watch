# M17 · Read it right

## Learnings

- S74's no-results sentence, found on AbeBooks' empty pages, was also hidden in the scripts of every results page, so a results page the app couldn't read would still have read as empty. It was found by luck, on a read made for S76. A mark that tells pages apart is now checked against every kind of page, and only where the page shows it. [CONTRIBUTING](../../../CONTRIBUTING.md#building)
- S74's issue said a misread page showed "No copies on AbeBooks". Planning found it also took the book's AbeBooks copies off the want list's price and the morning email. Planning a wrong answer now asks where else it goes. [Plan slice](../../../.claude/skills/plan-slice/SKILL.md#questions)
- S75 was first planned to reload at whichever redraw came next, which Alan found unpredictable. It settled on the moment he can name, leaving the app and coming back, after Alan asked why the interface couldn't stay fixed for a session: the server draws every piece of screen, so after a deploy only the new version exists. Planning something that happens on its own now asks whether that moment can be named. [Plan slice](../../../.claude/skills/plan-slice/SKILL.md#questions)
- S75 can't be seen from its own deploy, since a page left open holds the code from before it, so its phone check came with S76's deploy. Coming back to the app after a deploy now reloads it, so a phone check can start there as well as from a fresh open. [CONTRIBUTING](../../../CONTRIBUTING.md#testing)
- S76 had no live grouped page to build against: AbeBooks grouped on 2026-10-07 and stopped. The setting that undoes grouping, `rollup=off`, was in every link on AbeBooks' own pages. Looking there first is now a building rule. [CONTRIBUTING](../../../CONTRIBUTING.md#building)
- Reading pages from Fly followed redirects without checking them against robots.txt. Every hop is now checked. [Rate limits](../../rules/rate-limits.md#abebooks-and-biblio)

## Carried forward

- [See what the app does unattended, and hear when something is wrong](https://github.com/loserpoints/book-watch/issues/168)
