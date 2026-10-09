# Settings

## Purpose

Settings holds the choices made once for the whole app: the limit each new book starts with, and the ZIP shipping is priced to.

## What it shows

- The top bar, with Settings as the current tab (see [want list](want-list.md#what-it-shows)).
- One group, "New books", headed as a month is on the [Bought](bought.md) page.
- "Default limit", with "What each new book starts with" under it, and at the right the default, "$10", or "none", with ✎.
- While the default is being typed, an accent underline under it and "Whole dollars. Done saves, empty for none." under the label.
- "Saved" beside the default for a moment once it is saved, or under the row why it wasn't: not whole dollars, not an amount, under $1, or more than three digits.
- With a default set and books on the list with no limit, "3 books on the list have no limit." and a button, "Set $10 on them". Once tapped, "Set $10 on 3 books."
- A second group, "Shipping", with "Ship-to ZIP", "Where delivered prices are priced to" under it, and the ZIP at the right with ✎. Without one, "none", and under the label "Without one, calculated shipping shows “+ shipping?”".
- While the ZIP is being typed, "Five digits. Done saves. Prices follow from the next check." under the label. Anything but five digits is refused under the row with "A ZIP is five digits.", which never repeats what was typed.

## What you can do

- Tap anywhere on the default's row to type a new one, in whole dollars, with the number keyboard. Done, or tapping elsewhere, saves it. An empty default means none. Escape, on a keyboard, puts the saved one back.
- A new book starts with the default as its own limit, and its page can change it (see [pricing](../rules/pricing.md#limits)). Changing the default changes no book already on the list.
- Tap "Set $10 on them" to give the default to every book with no limit, and to no other.
- Tap the ZIP's row to type a new one, five digits, with the number keyboard, saved as the default is. Every eBay search reads it when it runs, so each book's delivered prices follow from its next check, the morning's or the Check button's (see [pricing](../rules/pricing.md#prices)).
- Tap Wanted or Bought in the top bar to go there. Tap Settings while here to go back to the top.
- Press back to return to the want list.

## Open issues

- [Search sellers everywhere by default, not only in the US](https://github.com/loserpoints/book-watch/issues/288)
