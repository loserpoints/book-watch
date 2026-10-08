# Design system

## Principles

1. **Clarity over clutter.** If it does not help decide, it is one tap away.
2. **The next tap is obvious** and does what it looks like it does. Back leaves the screen, whatever was done on it.
3. **Say when something is unknown, stale or waiting on a partner.** Unknown is shown at the same weight as known.
4. **Fewest taps to the answer.** Two states are a toggle, not a menu.
5. **A symbol and a short phrase, explained on tap.** The whole row or chip is the target. Nothing lives only on hover.
6. **The covers carry the warmth.** The interface stays neutral.
7. **Phone first.** 44px targets, main actions in thumb reach, safe areas respected.
8. **Dark first, light kept working.**
9. **One accent color**, for what is current or can be acted on.
10. **Quiet when all is well.** A status that is normally fine appears only when something is wrong.
11. **One word, one meaning.** A word the app already uses, such as "limit" for the price limit, is not reused for something else.

## Tokens

Every color, font, text size, space and radius is a token in `src/book_watch/web/tokens.toml`. The [design page](https://book-watch-alan.fly.dev/design) draws each one with its value, in the theme your device uses.

Tests enforce the rules:

- The stylesheet and templates use tokens only, never raw colors or sizes.
- Every color has a dark and a light value, and dark is the default.
- All text meets WCAG AA contrast in both themes.
- Every icon button is a 44px target.
- No template uses `title=` for information.

## Components

Jinja macros in `src/book_watch/web/templates/_ui.html`. Each takes plain values, so a screen maps its data onto them. The [design page](https://book-watch-alan.fly.dev/design) draws every component in every state, and a new component is added there when it is added here. A screen uses these pieces and never builds its own version of one. A control that floats over a screen, such as the + button, sits above every layer of what it floats over, and a test holds it there.

A row that leads somewhere, a book on the want list or a copy on a book's page, is one target: its link stretches over it, and its own controls sit above the link. Pressed, the whole row fills with the sheet color, never the phone's own highlight. The app sets the fill from the touch itself and holds it long enough to see, since a tap that opens another app leaves the browser's own pressed state no time to draw.

A mark that has to read the same size everywhere, such as the caret that says which way a price moved, is drawn as a shape and sized as a share of the text it sits beside. A typed character such as ▾ is as big as each device's font makes it.

Example text in an empty field starts with "e.g.", so in grey it can't pass for a value already filled in.

The app's screens are tabs in a top bar that stays in view: Wanted, for the want list, Bought and Settings. The want list is home. Back from another screen returns to it, and back from it leaves the app. A screen under the want list, such as a book's page, keeps Wanted as its current tab and puts a back to it in place of the app's mark. Tapping the tab of the screen you're on goes back to its top. The tab names the screen, so a screen has no heading of its own.

A tab, and a choice between two ways of seeing the same thing, such as Cheapest or Newest and Title & author or ISBN, look the same: the chosen one bold over a bar in the accent, the others muted. The accent marks what is current. A filter that is on or off is a switch. All keep their 44px targets.
