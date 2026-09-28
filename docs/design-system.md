# Design system

## Principles

1. **Clarity over clutter.** If it does not help decide, it is one tap away.
2. **The next tap is obvious** and does what it looks like it does.
3. **Say when something is unknown, stale or waiting on a partner.** Unknown is shown at the same weight as known.
4. **Fewest taps to the answer.** Two states are a toggle, not a menu.
5. **A symbol and a short phrase, explained on tap.** The whole row or chip is the target. Nothing lives only on hover.
6. **The covers carry the warmth.** The interface stays neutral.
7. **Phone first.** 44px targets, main actions in thumb reach, safe areas respected.
8. **Dark first, light kept working.**
9. **One accent color**, for what is current or can be acted on.

## Tokens

Every color, font, text size, space and radius is a token in `src/book_watch/web/tokens.toml`. `/design` on the running app draws them all.

- **Color:** `bg`, `surface`, `fg`, `muted`, `line`, `accent`, `on-accent`, `under`, `over`, `placeholder-bg`, `placeholder-fg`, `shadow`, `spine`. Each has a dark and a light value and a line saying what it is for.
- **Font:** Courier Prime for titles and prices, IBM Plex Sans for everything else. Both are served by the app.
- **Text:** one scale, `xxs` to `xxl`.
- **Space:** `1` to `6`.
- **Radius:** `sm`, `md`, `lg`, `pill`.

Tests enforce the rules:

- The stylesheet and templates use tokens only, never raw colors or sizes.
- Every color has both themes, and dark is the default.
- All text meets WCAG AA contrast in both themes.
- Every icon button is a 44px target.
- No template uses `title=` for information.

## Components

Jinja macros in `src/book_watch/web/templates/_ui.html`. Each takes plain values, and `/design` draws every state from samples.

- **Book row:** one book on the want-list, with cover, price and range strip.
- **Copy row:** one copy on active listings, with photo, price, rank strip, condition, seller's claim and condition note.
- **Candidate row:** one search result when adding a book. The whole row adds it.
- **Market line:** a market's count and its range strip.
- **Strips:** range (every asking price seen, the limit dashed) and rank (this copy among its kind). Drawn as SVG by `web/strips.py`.
- **Price:** colored under or over, with ✓ or the amount over.
- **Cover:** the image over a placeholder showing the title.
- **Chip, tag, button, fab (the round +), field, switch.**
- **Sheet:** a bottom sheet, a native `<dialog>`.
- **Photo view:** every photo of a copy, swiped through, with dots.
- **Explain and digging:** a short phrase that expands in place on tap.
- **Fold:** a collapsed group, such as the maybes.
