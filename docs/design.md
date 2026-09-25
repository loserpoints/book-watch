# Design

*Last updated: 2026-09-25*

How book-watch should look and behave, and why. Read it before building or
changing a screen. The tokens and primitives that implement it are M6's
work; this file is the argument they answer to.

## Where these came from

Three apps Alan uses and likes, each for something specific:

- **nzb360** — the closest in shape: add things to a list, see the list
  cleanly, tap in for detail. It depends entirely on other people's APIs and
  says so honestly. A row gives you everything you need at a glance: artwork,
  title, one line of facts, one line of status as colour and a few characters.
- **Letterboxd** — lists as image grids, and filters that cost one tap. A
  two-state filter is a toggle, never a dropdown that takes two taps to reach
  the obvious choice.
- **Excalidraw** — does its one job and nothing else, gives the content the
  whole screen, and has a signature look that comes from one opinionated
  choice rather than from decoration.

## Principles

1. **Clarity over clutter.** If it does not help decide, it is not on the
   list. It can be one tap away.
2. **The next tap is obvious, and it does what it looks like it does.**
3. **Say when we are waiting on a partner, and when something is stale or
   unknown.** Unknown is shown as a value in the same weight as known values,
   never hidden and never implied. Loading says what it is waiting for.
4. **Fewest taps to the answer.** A toggle beats a dropdown whenever there are
   two states. Filters anticipate the obvious choice.
5. **Collapse to a symbol and a short phrase; explain on tap.** The whole row
   or chip is the target, never a small icon that has to be hit exactly. Hover
   is a desktop bonus and never the only way to reach something, because a
   phone has no hover. How far each sentence collapses is decided case by
   case, and never at the cost of the wording rules in decisions 47, 51 and 53.
6. **It is a tool, and the covers carry the warmth.** The interface stays
   neutral and gets out of the way; the books supply the atmosphere.
7. **Phone first.** Thumb-sized targets, main actions within thumb reach,
   respect the notch and gesture area, behave sensibly offline. Designed as if
   it will be an app, without building as if it will be public.
8. **Dark first, light kept working.** Every colour is a token with both
   values, so light mode is never a redesign — but dark is the one tuned.
9. **One accent colour**, for what is current or can be acted on. Everything
   else is neutral.

## Open

- **A signature.** Something that makes it feel like itself — possibly how
  covers are rendered, a typeface, or the voice of loading and "we don't know"
  states. Principle 3 is a candidate: honesty about partners, written in a
  voice nobody else would use. Not decided; collect candidates as they turn up.
