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

## Tokens

Every color, font, text size, space and radius is a token in `src/book_watch/web/tokens.toml`. The [design page](https://book-watch-alan.fly.dev/design) draws each one with its value, in the theme your device uses.

Tests enforce the rules:

- The stylesheet and templates use tokens only, never raw colors or sizes.
- Every color has a dark and a light value, and dark is the default.
- All text meets WCAG AA contrast in both themes.
- Every icon button is a 44px target.
- No template uses `title=` for information.

## Components

Jinja macros in `src/book_watch/web/templates/_ui.html`. Each takes plain values, so a screen maps its data onto them. The [design page](https://book-watch-alan.fly.dev/design) draws every component in every state, and a new component is added there when it is added here. A screen uses these pieces and never builds its own version of one.
