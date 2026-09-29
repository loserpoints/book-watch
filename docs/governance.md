# Governance

## Artifacts

Every document in this repository is one of the artifacts below. `scripts/check_docs.py` reads this table and fails CI when a document breaks it, so this table is the only place the rules are written.

| Artifact | Status | Path | Sections |
|---|---|---|---|
| Governance | active | `docs/governance.md` | Artifacts · Workflow · Writing style |
| README | active | `README.md` | Value proposition · What it does · Tech stack · Running it · Repository structure |
| Agent instructions | active | `CLAUDE.md` | Start of session · Working rules |
| Contributing | active | `CONTRIBUTING.md` | Building · Testing · Reviewing |
| Jobs | active | `docs/jobs.md` | J<n> · <name> [Job (sentence) · Success signal] |
| Design system | active | `docs/design-system.md` | Principles · Tokens · Components |
| Rules | active | `docs/rules/*.md` | Purpose (sentence) · Rules · Open issues (links) |
| Surface | active | `docs/surfaces/{add-a-book,want-list,active-listings}.md` | Purpose (sentence) · What it shows · What you can do · Open issues (links) |
| Original scope | active | `docs/milestones/*/original-scope.md` | Goal (sentence) · Jobs advanced (job links) · Slices (slice links) |
| Delivered scope | active | `docs/milestones/*/delivered-scope.md` | Goal (sentence) · Jobs advanced (job links) · Slices (links) |
| Learnings | active | `docs/milestones/*/learnings.md` | Learnings (routed) · Carried forward (links, may be empty) |
| Runbook | active | `docs/runbook.md` | Deploy · Roll back · Restore data · Post-deploy checks · Known gaps (links, may be empty) |

**Status.** An *active* artifact is checked. A *migrating* one exists in its old form and is checked once it is rewritten. A *retiring* one is deleted when its migration finishes.

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

**Current state and history.** Surfaces, rules, the design system and the runbook describe the product as it is now and carry no history. History lives in milestone learnings, and beyond that in git, pull requests and closed issues. Decisions made before these documents existed are in the [decision log](https://github.com/loserpoints/book-watch/blob/537d5ea30621c8756ddfc8c74969d584b2694c62/docs/decisions.md), frozen as it stood when it was retired.

## Workflow

**Issues.** Every issue is one of four types, each with its own template and label. Blank issues are turned off.

| Type | Label | Is | Template asks |
|---|---|---|---|
| Defect | `defect` | The app does something its surface or rules doc says it shouldn't. | What happens · What should happen |
| Enhancement | `enhancement` | Something new I could see or do. | What I could do · Job it advances |
| Tech debt | `tech debt` | An internal change I would never see: code, infrastructure or compliance. | What's wrong · What it costs if left |
| Process gap | `process gap` | How we work is missing something: a doc, a workflow or an operating step. | What went wrong or is missing · Which doc or workflow should change |

**Slices.** A slice is an issue a milestone has taken on. It keeps its type label, adds the `slice` label and the milestone, and is titled `S## · outcome`. Its body is rewritten in place into four sections:

- **Outcome:** one sentence. What exists after this that didn't before.
- **Acceptance:** a checklist that can be checked mechanically, ending in `scripts/check.sh` passes.
- **Decisions it forces:** what the slice settles. Anything expensive to reverse goes in the rules or surface doc it changes, in the same pull request.
- **External calls:** requests to eBay, Open Library or anything else, how many, and when.

Related issues can become one slice: one is refined, and the others are closed as duplicates of it. An issue that still needs design waits until it can be written as a slice.

**A slice can ship as several pull requests** when its parts share one outcome and one acceptance list.

**Starting a milestone:**

1. Choose its issues from the open issues.
2. Turn them into slices.
3. Create its folder and write `original-scope.md`.
4. Create its GitHub milestone, titled `M8 - Always current`, with the goal sentence as its description, followed by a link to its folder on `main`.

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
