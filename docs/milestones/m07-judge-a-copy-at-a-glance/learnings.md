# M7 · Judge a copy at a glance

## Learnings

- Driving each slice in a browser caught what the tests could not: a tap on a search result that searched again, an icon rendered in the wrong font, and chips that wrapped. Every slice gets run and looked at.
- Ask the platform, not memory. Chromium's own tools showed the app installs without a service worker, which the project had believed it needed.
- Build a piece once, in the design system. Notes and photos went into the shared copy row instead of the old page, and reached the page when the screens were rebuilt.
- Tests should check what a reader sees, not the markup. Tests written that way survived three rebuilt screens with only their wording changed.
- A bound is not a guess. A copy whose price alone is over the limit is over, whatever the shipping.
- One slice can ship as several pull requests when its parts share one outcome and one acceptance list.

## Carried forward

- [Copies with unstated shipping sort to the bottom](https://github.com/loserpoints/book-watch/issues/104)
- [Dismiss a copy I've ruled out](https://github.com/loserpoints/book-watch/issues/105)
- [Find an author's books, and add several at once](https://github.com/loserpoints/book-watch/issues/101)
