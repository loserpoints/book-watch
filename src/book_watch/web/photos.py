"""A larger version of a seller's photo, for the enlarged view.

eBay serves each listing image at several sizes, and the size is written into
the file name: `.../s-l225.jpg` is 225px on its long side, `.../s-l1600.jpg`
the largest. The app stores the small one the search returns. Asking for the
large one is the same URL with a different size, so enlarging costs no API
call and no stored data (S30, #110).

The pattern is eBay's convention rather than a documented contract, so this
only rewrites a URL that matches it exactly. Anything else is returned as it
is, and the dialog shows the photo it already has rather than a broken image.
"""

from __future__ import annotations

import re

#: The size segment at the end of an eBay image URL, before the extension.
_SIZED = re.compile(r"^(https://i\.ebayimg\.com/.+/s-l)(\d+)(\.(?:jpe?g|png|webp))$")

LARGEST = 1600


def larger(url: str | None, size: int = LARGEST) -> str | None:
    """The same photo at `size`, or the URL unchanged if it is not eBay's shape."""
    if not url:
        return url
    match = _SIZED.match(url)
    if match is None:
        return url
    return f"{match.group(1)}{size}{match.group(3)}"
