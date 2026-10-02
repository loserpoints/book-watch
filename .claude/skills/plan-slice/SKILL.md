---
name: plan-slice
description: Check a book-watch slice before building it, so it covers what its outcome means and not only what it says. Use when starting work on any slice, before writing code, and when drafting a slice in set-milestone.
---

# Plan slice

## Purpose

Before any code, check that a slice covers what its outcome means to the person using the app, not only what its words say.

## Steps

1. Read the slice, and the surface, rules and design-system docs it touches.
2. When the slice changes behavior, reproduce the current behavior in a real browser and confirm its cause before building on it.
3. Answer each question under Rules, from the code and the docs.
4. When the slice changes what a screen shows, render mocks of it under Mocks, with the options worth comparing.
5. Present to Alan: what the slice will do, the mocks, the additions proposed, anything to split off as a new issue, and how it will be checked on the phone. Stop until Alan approves.
6. Write approved additions into the slice's acceptance on GitHub. Open an issue for anything split off.

## Rules

### Questions

- Is the change about one screen, or about a component or pattern? Where else does it appear?
- What does a person see and feel: the tap's feedback, focus, loading, errors, an empty state, both themes and 360px wide?
- Has the current behavior been reproduced, and is its cause confirmed or only guessed?
- What does the original issue say already works? Is the slice still needed without that part?
- What would a literal reading of the outcome miss?
- Does the case it handles happen at all? Check the outside service's own rules before planning to measure it.
- Which docs, design page entries and tests change with it?
- Which requests to eBay, Open Library or Resend does it add, remove or repeat?
- How will Alan check it on the phone after deploy?

### Mocks

- A screen change is planned from mocks, never from a description alone.
- Mocks are rendered by the app itself, with every case the slice handles seeded: each state, the edges, and real-looking amounts. A drawing made apart from the app misses what the app's layout and data do.
- Each mock is shown at 360px in both themes, with the trade-off of each option stated.
- The app runs locally with outbound requests cut off. This environment holds real eBay keys, and a page can search eBay when it opens.

### Scope

- An addition joins the slice only when the outcome isn't true without it, as a person would read the outcome. Anything else becomes a new issue.
