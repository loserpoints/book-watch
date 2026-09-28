# Governance

## Artifacts

Every document in this repository is one of the artifacts below. `scripts/check_docs.py` reads this table and fails CI when a document breaks it, so this table is the only place the rules are written.

| Artifact | Status | Path | Sections |
|---|---|---|---|
| Governance | active | `docs/governance.md` | Artifacts · Workflow · Writing style |
| README | active | `README.md` | Value proposition · What it does · Tech stack · Running it · Repository structure |
| Agent instructions | migrating | `CLAUDE.md` | Start of session · Working rules |
| Contributing | active | `CONTRIBUTING.md` | Building · Testing · Reviewing |
| Jobs | active | `docs/jobs.md` | J<n> · <name> [Job (sentence) · Success signal] |
| Design system | active | `docs/design-system.md` | Principles · Tokens · Components |
| Rules | active | `docs/rules/*.md` | Purpose (sentence) · Rules · Open issues (links) |
| Surface | active | `docs/surfaces/{add-a-book,want-list,active-listings}.md` | Purpose (sentence) · What it shows · What you can do · Open issues (links) |
| Original scope | active | `docs/milestones/*/original-scope.md` | Goal (sentence) · Jobs advanced (job links) · Slices (slice links) |
| Delivered scope | active | `docs/milestones/*/delivered-scope.md` | Goal (sentence) · Jobs advanced (job links) · Slices (links) |
| Learnings | active | `docs/milestones/*/learnings.md` | Learnings (routed) · Carried forward (links, may be empty) |
| Runbook | active | `docs/runbook.md` | Deploy · Roll back · Restore data · Post-deploy checks · Known gaps (links, may be empty) |
| Decision log | retiring | `docs/decisions.md` | |
| Milestone log | retiring | `docs/milestones.md` | |
| Design notes | retiring | `docs/design.md` | |
| Operating notes | retiring | `docs/operating.md` | |
| Product brief | retiring | `docs/product-brief.md` | |

**Status.** An *active* artifact is checked. A *migrating* one exists in its old form and is checked once it is rewritten. A *retiring* one is deleted when the migration finishes. Only active remains after that.

**Sections** are the document's `##` headings, in order, with nothing added. Every document opens with one `#` title.

- *(sentence)*: one sentence.
- *(links)*: a list of GitHub issue or pull request links and nothing else. Problems live as issues, not as prose in a document.
- *(job links)*: a list of links to jobs in `docs/jobs.md`.
- *(slice links)*: a list of links to issues labelled `slice`. CI reads the labels from GitHub.
- *(routed)*: a list in which every item links the document it changed.
- *may be empty*: the section heading stays, with no list under it.
- *[…]*: `###` headings required under each `##`, in order. `<n>` and `<name>` stand for any value.

A Rules section may group its rules under `###` headings, chosen per document.

**Milestones.** Each milestone is a folder, `docs/milestones/mNN-name/`, created when the milestone starts. There are no planned milestones: what comes next is chosen from the open issues at each close. `delivered-scope.md` and `learnings.md` are added together when it closes. The two scope files share their sections so they can be compared.

**Current state and history.** Surfaces, rules, the design system and the runbook describe the product as it is now and carry no history. History lives in milestone learnings, and beyond that in git, pull requests and closed issues.

## Workflow

**Issues and slices.** An issue is anything noticed: a bug, a want, an outcome worth having. A slice is an issue a milestone has taken on. It carries the `slice` label and the milestone, is titled `S## · outcome`, and follows the slice template: Outcome in one sentence, Acceptance ending in `scripts/check.sh`, and Decisions it forces.

**An issue becomes a slice** when a milestone takes it on, by editing it in place into the slice template. Related issues can become one slice: one is edited, and the others are closed as duplicates of it. An issue that still needs design waits until it can be written as a slice.

**A slice can ship as several pull requests** when its parts share one outcome and one acceptance list.

**Starting a milestone:**

1. Choose its issues from the open issues.
2. Turn them into slices.
3. Create its folder and write `original-scope.md`.

**Closing a milestone:**

1. Write `delivered-scope.md`.
2. Route each learning into the document that should change because of it: `CONTRIBUTING.md`, `CLAUDE.md`, the runbook, a rules or surface doc, the design system, or this file. Make the change, then record the learning in `learnings.md` with a link to where it went. A learning with nowhere to go is dropped.
3. List the issues carried forward.
4. Choose the next milestone from the open issues.

## Writing style

- Say it once, directly. Length is not a substitute for knowing what you mean.
- Use commas and periods where they work. Save em dashes for the rare case nothing else does.
- State what is true. Avoid "it is not X, it is Y" framing and claims of impact.
- One idea per bullet.
- American spelling.
- Link issues rather than describing problems.
