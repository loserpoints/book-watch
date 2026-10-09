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
- When a slice adds a setting, what reads the value it replaces? #72's default scope ran through the daily check, the want list's price, the email and the counts, and left the slice for #288.
- When the defect is a wrong answer, where else does that answer go: what the app stores, shows elsewhere and emails? S74's wrong "empty" took a book's copies off the want list and the email too, which the issue didn't say.
- When something happens on its own, such as a reload or a redraw, can the person name the moment it happens? S75 was first planned to reload at the next redraw, which Alan found unpredictable, and settled on leaving the app and coming back.
- When a screen shows a change, what is it measured against: the last check, the last visit, or something else? Ask Alan rather than reading it from the issue's words.
- When it keeps a screen current, which ways does a person reach that screen: opening it, going back to it, coming back to the app after time away, and a piece of it redrawing? Each is a case to plan and check.
- Does the case it handles happen at all? Check the outside service's own rules before planning to measure it.
- Does it depend on an outside service? Read that service's terms for this use, by this app and by anyone it might be offered to, before planning the build.
- Which docs, design page entries and tests change with it?
- Which requests to eBay, Open Library or Resend does it add, remove or repeat?
- How will Alan check it on the phone after deploy?

### Mocks

- A screen change is planned from mocks, never from a description alone.
- Mocks are rendered by the app itself, with every case the slice handles seeded: each state, the edges, and real-looking amounts. A drawing made apart from the app misses what the app's layout and data do.
- Seed each field's longest real value, not only its usual one. S82's shop name ran into the book's title only once a mock held a long one, in its third round.
- A copy shows its price in a mock only when it is certainly the book, so seeded copies need a declared ISBN beside them (see [matching](../../../docs/rules/matching.md#which-numbers-are-this-book)).
- A reference Alan brings is mocked in the app's own pieces, beside a close copy. S82's Letterboxd diary read as borrowed until its months became typed headings.
- Before each round, ask Alan for his ideas, and mock them among the options.
- Each mock is shown at 360px in both themes, with the trade-off of each option stated.
- A layout aims for three rounds. Past three, keep going until it's right, and record in the slice why it took more.
- The app runs locally only through `scripts/serve_local.py`, which fakes eBay's search and refuses every request. This environment holds real eBay keys, and the app as built for production searches eBay when a page opens.

### Scope

- An addition joins the slice only when the outcome isn't true without it, as a person would read the outcome. Anything else becomes a new issue.
