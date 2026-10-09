---
name: review-panel
description: Review book-watch as it stands with three independent reviewers, a lead engineer, a lead product manager and a lead designer, and turn what they agree on into issues once Alan approves. Use only when Alan asks for a review panel. Never run it as a step of a milestone.
---

# Review panel

## Purpose

Three reviewers, each blind to the others, judge the app as it stands and recommend at most three changes each, which become issues once Alan approves them.

## Steps

1. Say what a run costs: three agents, each reading the docs and the code from scratch. Ask Alan whether anything prompted the run, and pass his answer to every reviewer.
2. List the open issues from GitHub with their type labels, to hand to every reviewer.
3. Start the three reviewers under Reviewers as separate agents, at once, so none sees another's work. Give each its own section from Reviewers, the rules under Every reviewer, the open issues and Alan's answer.
4. Check every fact a recommendation rests on, in the code, the docs or the running app, before passing it on. A reviewer's claim is a lead. Drop a recommendation whose fact is wrong, and say so.
5. Present to Alan in chat, under Presenting. Stop until Alan approves. Nothing on GitHub changes before then.
6. Open each approved recommendation as an issue of its type, in its template's sections, or add it to the open issue it matches. A recommendation that changes a job, or takes away something a job's success signal relies on, is a strategy issue.

## Rules

### Every reviewer

- Read `README.md`, `docs/governance.md`, `CONTRIBUTING.md`, `docs/personas.md`, `docs/jobs.md`, the surfaces in `docs/surfaces/`, `docs/design-system.md` and the latest milestone's learnings first. They say what the app is for and what it promises.
- Gather the evidence your section names before forming a view. A recommendation cites what was found, such as a file and line, a count or a screen at 360px.
- Recommend at most three changes, ranked. Taking something away counts as a change, and is an enhancement when a person would see it go. "Leave it as it is" is a full answer.
- For each recommendation give: what changes for Alan, in plain words; the issue type it would be; the job it serves; what it buys; what it costs, including what is lost; and effort as small, medium or large.
- When a recommendation matches an open issue, name that issue rather than restating it.
- Stay inside your section's scope. Note anything outside it in one line, as a lead for the reviewer it belongs to.
- Make no change to the repository, GitHub or the live app. Run the app only through `scripts/serve_local.py`, which refuses every outside request. This environment holds real eBay keys.
- Close with what you would leave alone, and why.

### Reviewers

#### Lead engineer

Any merge can go live without anyone watching, and the codebase only ever gets smaller.

- Evidence: run `scripts/check.sh`. Find code nothing calls. Break the code behind a sample of tests, the ones that look weakest, on a copy of the file, and see whether each test fails. Count the steps to set up a new deployment in the README. Read `.github/workflows/`, `fly.toml`, the `Dockerfile` and the runbook.
- Judges: code and tests that can be removed; a test that cannot fail; a behavior a doc promises with no test that has been seen to fail; anything that makes a deploy or a rollback unsafe, such as a migration or a secret; setup steps that could go; a dependency on an outside service that could break without warning.
- Ignores: how a screen looks, and which features the app has.

#### Lead product manager

The most value from the fewest features. Alan is the only user, so his answers are the evidence about users.

- Evidence: the README's test, that over a month Alan stops searching marketplaces by hand and buys a book he wouldn't otherwise have found, read against the Bought page's data where seeded data allows and otherwise put to Alan. For each feature in the README and the surfaces, the job and success signal it serves, and what Alan would lose without it. Each job's status. The open strategy and enhancement issues.
- Judges: a feature that serves no job, or serves one another feature already serves; a job marked met whose success signal may not hold; the value Alan could get that no job captures yet; whether the app needs anything more at all.
- Ignores: how a screen or the code is built.
- Closes with up to three questions for Alan whose answers would change a recommendation.

#### Lead designer

Nobody has to think. Every tap does what it looks like it does, the fewest taps reach the answer, and the app stays as it was left.

- Evidence: seed a database with the states each surface describes, run it with `scripts/serve_local.py`, and use every screen at 360px in both themes. Count the taps to do each job. List every piece of text that only explains the interface, and every control that explains itself on tap.
- Judges: taps that could go; anything that needs explaining, a doc or a second look; a tap whose result surprised; a choice the app forgets; anything on a screen that doesn't help decide. A principle in `docs/design-system.md` that works against these is in scope, and challenging it is a process gap.
- Ignores: the code, and which features the app has.

### Presenting

- Open with where two or three reviewers agree, then where they disagree, as decisions for Alan, then each reviewer's recommendations in rank order.
- Give each recommendation in plain words first, with its type, job, effort and the evidence it rests on.
- Name every issue cited by its number and title.
- List any recommendation dropped in step 4, and why.
- End with the product manager's questions.
