# M7 · Judge a copy at a glance

## Learnings

- Driving each slice in a browser caught a tap that searched again, an icon in the wrong font and wrapping chips, none of which a test caught. [CONTRIBUTING](../../../CONTRIBUTING.md#testing)
- Chromium's own tools showed the app installs without a service worker, which the project believed it needed. [CONTRIBUTING](../../../CONTRIBUTING.md#building)
- Notes and photos went into the shared copy row instead of the old page, so they were built once. [Design system](../../design-system.md#components)
- Tests that check what a reader sees survived three rebuilt screens with only their wording changed. [CONTRIBUTING](../../../CONTRIBUTING.md#testing)
- A copy whose price alone is over the limit is over, whatever the shipping. [Pricing](../../rules/pricing.md#limits)
- The screens shipped as one slice in three pull requests. [Governance](../../governance.md#workflow)

## Carried forward

- [Copies with unstated shipping sort to the bottom](https://github.com/loserpoints/book-watch/issues/104)
- [Dismiss a copy I've ruled out](https://github.com/loserpoints/book-watch/issues/105)
- [Find an author's books, and add several at once](https://github.com/loserpoints/book-watch/issues/101)
