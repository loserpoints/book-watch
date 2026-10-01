---
name: set-milestone
description: Choose the next book-watch milestone from the open issues, draft it for Alan's approval, then set it up. Use when a milestone closes, when none is in progress, or when Alan asks what comes next.
---

# Set milestone

## Purpose

Choose the next milestone from the open issues by one order of priority, and set it up once Alan approves it.

## Steps

1. List every open issue from GitHub with its type label: defect, enhancement, tech debt or process gap. Count them from that list, never from memory.
2. Choose the milestone's frame by the first rule under Priority that applies, and say which rule chose it and the counts behind it.
3. Choose 3–5 issues for it, judging each by impact and effort.
4. Draft each one as a slice in the four sections `docs/governance.md` gives, asking the questions in the `plan-slice` skill as each is written. Check first whether a doc or skill written since the issue was logged already answers it.
5. Present the draft to Alan: the frame and why, the name, the goal sentence, each slice with its impact and effort, what was left out and why, and how the outcome will be checked on the phone. Stop until Alan approves. Nothing on GitHub changes before then.
6. Turn each approved issue into a slice: keep its type label, add the `slice` label and the milestone, title it `S## · outcome` numbered on from the last slice, and rewrite its body. Close issues folded into a slice as duplicates of it.
7. Create `docs/milestones/mNN-name/` and write `scope.md`.
8. Create the GitHub milestone, titled like `M8 - Always current`, with the goal sentence as its description and a link to its folder on `main`. If the tools can't create milestones, ask Alan to.
9. Open a pull request with the folder and `scope.md`.

## Rules

### Priority

1. **A bad bug starts the milestone.** A defect is bad when it gives a wrong answer Alan could act on, such as a wrong price, a copy wrongly under or over its limit, or a missed or false email. It is also bad when it loses data, stops the daily check, or causes excessive calls to eBay, Open Library or Resend, or excessive cost. Other bugs that fit its theme, or other small bugs, fill the milestone. A bad bug can be a milestone on its own.
2. **Five or more open tech-debt and process-gap issues, counted together, make a cleanup milestone.** Cleanup is done in batches, never one at a time, and never left to pile up.
3. **Otherwise, the enhancement of highest value frames the milestone,** with a theme built from other enhancements around it.

### Filling

- A milestone holds 3–5 slices. Outside that range, the draft says why.
- Small bugs ride along in any milestone when they fit its theme or round it out.
- An issue that isn't ready to be a slice is still a candidate. Its first slice is the design or measurement that makes the rest writable.
- Take part of an issue only when that part doesn't decide how the rest will work. Otherwise the issue stays whole, and its first slice is the design.

### Impact and effort

- Impact is the job in `docs/jobs.md` an issue advances, and how directly it moves that job's success signal.
- Effort is small, medium or large, standing in for tokens spent. It grows with unknowns to measure, screens touched, rounds of review in a browser and new external calls.
- A recurring cost is said separately, whatever the effort.

### Outcome

- The goal can be checked on the live app within a few days. When it waits on an outside event, a slice adds a way to trigger it on demand.
