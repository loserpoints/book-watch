---
name: set-milestone
description: Choose the next book-watch milestone from the open issues, draft it for Alan's approval, then set it up. Use when a milestone closes, when none is in progress, or when Alan asks what comes next.
---

# Set milestone

## Purpose

Choose the next milestone from the open issues by one order of priority, and set it up once Alan approves it.

## Steps

1. List every open issue from GitHub with its type label: defect, enhancement, tech debt, process gap or strategy. Count them from that list, never from memory. An enhancement that links no job in `docs/jobs.md` is fixed first: link its job, or relabel it strategy.
2. Before anything else, show Alan the open strategy issues and ask whether he wants to adopt any. Adopting one is its own pull request, changing the value proposition and `docs/jobs.md` together, and it merges before the milestone is chosen.
3. Read each job's status in `docs/jobs.md`.
4. Choose the milestone's frame by the first rule under Priority that applies, and say which rule chose it and the counts behind it.
5. Choose 3–5 issues for it, judging each by impact and effort.
6. Draft each one as a slice in the four sections `docs/governance.md` gives, asking the questions in the `plan-slice` skill as each is written. Check first whether a doc or skill written since the issue was logged already answers it.
7. Present the draft to Alan: the frame and why, the name, the goal sentence, each slice with its impact and effort, what was left out and why, and how the outcome will be checked on the phone. Stop until Alan approves. Nothing on GitHub changes before then.
8. Turn each approved issue into a slice: keep its type label, add the `slice` label and the milestone, title it `S## · outcome` numbered on from the last slice, and rewrite its body. Close issues folded into a slice as duplicates of it.
9. Create `docs/milestones/mNN-name/` and write `scope.md`.
10. Create the GitHub milestone, titled like `M8 - Always current`, with the goal sentence as its description and a link to its folder on `main`. Create it with `gh api repos/loserpoints/book-watch/milestones -X POST -f title=... -f description=...`, which works in a session even when `gh auth status` reports a failed login. Assign the slices with the milestone's number.
11. Open a pull request with the folder and `scope.md`.

## Rules

### Priority

1. **A bad bug starts the milestone.** A defect is bad when it gives a wrong answer Alan could act on, such as a wrong price, a copy wrongly under or over its limit, or a missed or false email. It is also bad when it loses data, stops the daily check, or causes excessive calls to eBay, Open Library or Resend, or excessive cost. Other bugs that fit its theme, or other small bugs, fill the milestone. A bad bug can be a milestone on its own. A bug seen only now and then, whose harm the next check undoes, is not bad on that ground alone.
2. **Five or more open tech-debt and process-gap issues, counted together, make a cleanup milestone.** Cleanup is done in batches, never one at a time, and never left to pile up. Alan can set cleanup aside for a job not met, and never for an enhancement to a job that is met.
3. **A job not met frames the milestone next.** The issue of highest value toward a job whose status is not met frames it, with a theme built around that job. When its work is blocked, its first slice is the research that either unblocks it or shows it can't be done. When it can't be done, the value proposition and the job are rewritten to stop promising it.
4. **Otherwise, the enhancement of highest value to a met job frames the milestone,** with a theme built from other enhancements around it.

Alan can choose a frame these rules don't pick. The draft then names the rule that applied and what it would have chosen, and the milestone's learnings record the choice. M18 took observability over rule 4's enhancement.

### Filling

- A milestone holds 3–5 slices. Outside that range, the draft says why.
- Small bugs ride along in any milestone when they fit its theme or round it out.
- An issue that isn't ready to be a slice is still a candidate. Its first slice is the design or measurement that makes the rest writable.
- Take part of an issue only when that part doesn't decide how the rest will work. Otherwise the issue stays whole, and its first slice is the design.

### Impact and effort

- Impact is the job in `docs/jobs.md` an issue advances, and how directly it moves that job's success signal.
- Effort is small, medium or large, standing in for tokens spent. It grows with unknowns to measure, screens touched, rounds of review in a browser and new external calls.
- A recurring cost is said separately, whatever the effort.

### Issues

- Before closing an issue as done or stale, check whether an open pull request is set to close it, such as a milestone's close waiting on validation.

### Outcome

- The goal can be checked on the live app within a few days. When it waits on an outside event, a slice adds a way to trigger it on demand.
