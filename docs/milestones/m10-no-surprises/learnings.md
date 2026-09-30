# M10 · No surprises

## Learnings

- eBay's search leaves the shipping cost out of calculated-shipping listings unless the request says where the book ships to, and it ignores that location unless it is URL-encoded. [Pricing](../../rules/pricing.md#prices)
- A form post that redirects back to its own page adds a history entry, so back showed the book again. Actions on a page now take its place in the history. [Design system](../../design-system.md#principles)
- S45's guessed cause was wrong. Reproducing it in a browser found the real one and three more cases, and the slice was rescoped, which two scope files could not record. [Governance](../../governance.md#artifacts)
- S47's problem went away after the eBay app was opened, before anything was built. [CONTRIBUTING](../../../CONTRIBUTING.md#building)
- Bare issue numbers in chat were unreadable, though CLAUDE.md already asked for names. [CLAUDE.md](../../../CLAUDE.md#working-rules)

## Carried forward

- [A missing Fly secret says to copy .env.example](https://github.com/loserpoints/book-watch/issues/180)
- [Set the ship-to ZIP in the app, not as a Fly secret](https://github.com/loserpoints/book-watch/issues/182)
- [On iPhone, a listing opens in the eBay app, where I'm logged in and can buy](https://github.com/loserpoints/book-watch/issues/176)
- [Unknown shipping may not exist once eBay knows where a book ships to](https://github.com/loserpoints/book-watch/issues/189)
