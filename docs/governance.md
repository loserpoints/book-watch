# Governance

## Artifacts

Every document in this repository is one of the artifacts below. `scripts/check_docs.py` reads this table and fails CI when a document breaks it, so this table is the only place the rules are written.

| Artifact | Status | Path | Sections |
|---|---|---|---|
| Governance | active | `docs/governance.md` | Artifacts · Workflow · Writing style |
| README | active | `README.md` | Value proposition · What it does · Tech stack · Running it · Repository structure |
| Agent instructions | active | `CLAUDE.md` | Start of session · Working rules |
| Contributing | active | `CONTRIBUTING.md` | Building · Testing · Reviewing |
| Personas | active | `docs/personas.md` | P<n> · <name> [Who (sentence) · How they buy · Jobs (job links)] |
| Jobs | active | `docs/jobs.md` | J<n> · <name> [Persona (persona links) · Job (sentence) · Success signal · Status (met or not met)] |
| Design system | active | `docs/design-system.md` | Principles · Tokens · Components |
| Rules | active | `docs/rules/*.md` | Purpose (sentence) · Rules · Open issues (links) |
| Surface | active | `docs/surfaces/{add-a-book,want-list,active-listings,bought,settings}.md` | Purpose (sentence) · What it shows · What you can do · Open issues (links) |
| Scope | active | `docs/milestones/*/scope.md` | Goal (sentence) · Jobs advanced (job links) · Slices (slice links) |
| Learnings | active | `docs/milestones/*/learnings.md` | Learnings (routed) · Carried forward (links, may be empty) |
| Skill | active | `.claude/skills/*/SKILL.md` | Purpose (sentence) · Steps · Rules |
| Runbook | active | `docs/runbook.md` | Deploy · Roll back · Restore data · Post-deploy checks · Known gaps (links, may be empty) |

**Status.** An *active* artifact is checked. A *migrating* one exists in its old form and is checked once it is rewritten. A *retiring* one is deleted when its migration finishes.

**Sections** are the document's `##` headings, in order, with nothing added. Every document opens with one `#` title.

- *(sentence)*: one sentence.
- *(links)*: a list of GitHub issue or pull request links and nothing else. Problems live as issues, not as prose in a document.
- *(job links)*: a list of links to jobs in `docs/jobs.md`.
- *(persona links)*: a list of links to personas in `docs/personas.md`.
- *(slice links)*: a list of links to issues labeled `slice`. CI reads the labels from GitHub.
- *(routed)*: a list in which every item links the document it changed.
- *(met or not met)*: opens with "Met." or "Not met.", then says why in a sentence or two.
- *may be empty*: the section heading stays, with no list under it.
- *[…]*: `###` headings required under each `##`, in order. `<n>` and `<name>` stand for any value.

A Rules section may group its rules under `###` headings, chosen per document.

**Milestones.** Each milestone is a folder, `docs/milestones/mNN-name/`, created when the milestone starts. There are no planned milestones: what comes next is chosen from the open issues at each close. `scope.md` is written when it starts and kept current: the change that adds, rescopes or drops a slice updates it. A dropped slice stays listed, with "dropped" in its link text. `learnings.md` is added when it closes, and a scope change that taught something is recorded there like any other learning.

**Value proposition, personas and jobs.** The README's value proposition says what the app is for, `docs/personas.md` says who it is built for, and `docs/jobs.md` holds the jobs that deliver it. Each job links the personas it serves, and each persona lists its jobs, so a job two personas share is written once. A change to either checks the other, and its pull request says whether the other had to change. Each job's status says whether its success signal holds today, as Alan judges it on the live app. A job not met is work still owed on what the app promises.

**Current state and history.** Surfaces, rules, the design system and the runbook describe the product as it is now and carry no history. History lives in milestone learnings, and beyond that in git, pull requests and closed issues. Decisions made before these documents existed are in the [decision log](https://github.com/loserpoints/book-watch/blob/537d5ea30621c8756ddfc8c74969d584b2694c62/docs/decisions.md), frozen as it stood when it was retired.

## Workflow

**Issues.** Every issue is one of five types, each with its own template and label. Blank issues are turned off.

| Type | Label | Is | Template asks |
|---|---|---|---|
| Defect | `defect` | The app does something its surface or rules doc says it shouldn't. | What happens · What should happen |
| Enhancement | `enhancement` | Something new I could see or do. | What I could do · Job it advances |
| Tech debt | `tech debt` | An internal change I would never see: code, infrastructure or compliance. | What's wrong · What it costs if left |
| Process gap | `process gap` | How we work is missing something: a doc, a workflow or an operating step. | What went wrong or is missing · Which doc or workflow should change |
| Strategy | `strategy` | A change to what the app is for: its value proposition, its jobs, or who and what it is built for. | What would change · Why it might be worth it |

An enhancement links a job already in `docs/jobs.md`. An idea that fits no job, or would change one, is a strategy issue.

A strategy issue waits for Alan to adopt it and is never ranked against other work. Adopting one is a pull request that changes the value proposition, `docs/personas.md` and `docs/jobs.md` together, and a job it adds starts not met. A persona it adds lists the existing jobs it shares and brings its own.

A stale reference found anywhere, in a doc, in code or in an issue, is logged as a process gap or tech debt issue, not left.

**Slices.** A slice is an issue a milestone has taken on. It keeps its type label, adds the `slice` label and the milestone, and is titled `S## · outcome`. Its body is rewritten in place into four sections:

- **Outcome:** one sentence. What exists after this that didn't before.
- **Acceptance:** a checklist that can be checked mechanically, ending in `scripts/check.sh` passes.
- **Decisions it forces:** what the slice settles. Anything expensive to reverse goes in the rules or surface doc it changes, in the same pull request.
- **External calls:** requests to eBay, Open Library or anything else, how many, and when.

Related issues can become one slice: one is refined, and the others are closed as duplicates of it.

**A slice can ship as several pull requests** when its parts share one outcome and one acceptance list.

**Starting a milestone** uses the `set-milestone` skill. A milestone can start while the one before it waits to close.

**Starting a slice** uses the `plan-slice` skill, before any code.

**Closing a milestone:**

A milestone closes only once its outcome has been checked on the live app. Its close pull request is drafted on its own branch and stays open until then.

1. Bring `scope.md` up to date, with a goal that says what was delivered.
2. Check whether anything the milestone learned changes how a job or its success signal is understood. Expect not. A job is edited only when that understanding changes, or to say why a job not met is still not met. Building something for a job never changes it.
3. Route each learning into the document that should change because of it: `CONTRIBUTING.md`, `CLAUDE.md`, the runbook, a rules or surface doc, the design system, or this file. Make the change, then record the learning in `learnings.md` with a link to where it went. A learning with nowhere to go is dropped.
4. List the issues carried forward.
5. Start the next milestone with the `set-milestone` skill, in a fresh session, if one has not already started.

## Writing style

- Say it once, directly. Length is not a substitute for knowing what you mean.
- Use commas and periods where they work. Save em dashes for the rare case nothing else does.
- State what is true. Avoid "it is not X, it is Y" framing and claims of impact.
- One idea per bullet.
- American spelling.
- Link issues rather than describing problems.
