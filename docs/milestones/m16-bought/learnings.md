# M16 · Bought

## Learnings

- S71's empty price box showed "7.80" in grey, which read on the phone as a price filled in from a copy. Example text now says it's an example. [Design system](../../design-system.md#components)
- S72 was planned twice against "since I last opened the book" before Alan said the want list is read without opening books, so a move is measured against the check before. A change on a screen now asks what it is measured against. [Plan slice](../../../.claude/skills/plan-slice/SKILL.md#questions)
- S72's carets wait on a seller repricing a copy, which nothing can make happen on demand. That was found after the build, not when it was planned. [CONTRIBUTING](../../../CONTRIBUTING.md#testing)
- S73's pressed fill showed in the browser and on the want list, but not on a copy on the phone, whose tap hands the listing to the eBay app. Desktop Chromium shows no pressed state for a touch, so the app now sets it from the touch, and a pressed look is checked on the phone. [CONTRIBUTING](../../../CONTRIBUTING.md#testing), [Design system](../../design-system.md#components)
- Choosing M16, Alan judged the two open AbeBooks defects not bad: each is seen only now and then, and the next check undoes it. [Set milestone](../../../.claude/skills/set-milestone/SKILL.md#priority)
- Closing M16 listed what each job had gained from the milestone, as if features changed jobs. It is the other way round: a close checks whether anything learned changes how a job is understood, and expects not. [Governance](../../governance.md#workflow)
- Closing M16 ran at the end of a long session that had planned and built the whole milestone. The next milestone now starts in a fresh session, which reads the docs as they stand after the close. [Governance](../../governance.md#workflow)
- S72's carets looked right in mocks drawn on desktop and were much smaller on the phone, whose font draws ▾ at its own size. They are now triangles drawn as shapes, the same size on every device. [Design system](../../design-system.md#components)

## Carried forward

- [Sort and filter choices are remembered on the want list and a book's page](https://github.com/loserpoints/book-watch/issues/264)
- [A Bought page, as a compact diary of what I've bought](https://github.com/loserpoints/book-watch/issues/258)
