"""The two price strips, drawn as SVG on the server.

Both put prices on one horizontal scale, the way a dot plot does:

- **The range strip** shows every asking price seen for a book,
  with the lowest and highest labeled under the ends in
  whole dollars and the limit as a dashed guide. Every dot is the same
  color: the cheapest is always the left end, so emphasizing it would say
  nothing (S27).
- **The rank strip** shows the copies of one kind listed now,
  with this copy as the large dot. It replaces "2nd of 3",
  which did not say it was about price.

Drawn in Python rather than in the browser, so they appear on first paint and
need no JavaScript. The email *Tell me* sends cannot use SVG and will need its
own treatment.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from markupsafe import Markup, escape

Number = Decimal | float | int

#: Room at each end so a dot on the extreme is not cut in half.
PAD = 5.0


@dataclass(frozen=True, slots=True)
class Scale:
    """Maps a price onto a horizontal position between two pixel bounds."""

    low: float
    high: float
    width: float
    pad: float = PAD

    def x(self, value: Number) -> float:
        span = self.high - self.low
        usable = self.width - 2 * self.pad
        if span == 0:
            return round(self.pad + usable / 2, 1)
        return round(self.pad + (float(value) - self.low) / span * usable, 1)


def scale_for(values: Sequence[Number], width: float) -> Scale:
    floats = [float(v) for v in values]
    return Scale(min(floats), max(floats), width)


def whole(value: Number, symbol: str = "$") -> str:
    """$10.49 -> "$10". The ends only mark the range; the headline keeps cents."""
    rounded = Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return f"{symbol}{rounded}"


def range_strip(
    seen: Sequence[Number],
    limit: Number | None = None,
    *,
    width: int = 104,
    height: int = 16,
    labeled: bool = True,
    symbol: str = "$",
) -> Markup:
    """Every asking price seen, each judged against the limit, and the range.

    The scale spans the prices alone, so a limit far from them never squeezes
    the dots together (S61, #200). A dot is green at or under the limit and
    red over it, like a price; with no limit it keeps the accent color. A
    dashed line marks the limit only when it falls among the prices: with no
    line, a ✓ beside the price means every copy is under, and none means every
    copy is over. That reading needs no color.
    """
    if not seen:
        return Markup("")
    scale = scale_for(seen, width)
    mid = height / 2
    low, high = min(seen, key=float), max(seen, key=float)
    parts = [
        f'<line class="strip-axis" x1="{PAD}" x2="{width - PAD}" '
        f'y1="{mid}" y2="{mid}"/>'
    ]
    if limit is not None and float(low) <= float(limit) <= float(high):
        x = scale.x(limit)
        parts.append(
            f'<line class="strip-limit" x1="{x}" x2="{x}" y1="2" y2="{height - 2}"/>'
        )
    parts += [
        f'<circle class="{_dot_class(v, limit)}" cx="{scale.x(v)}" cy="{mid}" r="2.6"/>'
        for v in seen
    ]
    total = height
    if labeled:
        total = height + 12
        parts.append(
            f'<text class="strip-label" x="{scale.x(low)}" y="{height + 10}" '
            f'text-anchor="start">{escape(whole(low, symbol))}</text>'
        )
        parts.append(
            f'<text class="strip-label" x="{scale.x(high)}" y="{height + 10}" '
            f'text-anchor="end">{escape(whole(high, symbol))}</text>'
        )
    label = (
        f"{len(seen)} asking prices seen, {whole(low, symbol)} to {whole(high, symbol)}"
    )
    if limit is not None:
        under = sum(1 for v in seen if float(v) <= float(limit))
        label += f", {under} at or under the limit of {whole(limit, symbol)}"
    return Markup(
        f'<svg class="strip" width="{width}" height="{total}" '
        f'viewBox="0 0 {width} {total}" role="img" aria-label="{escape(label)}">'
        + "".join(parts)
        + "</svg>"
    )


def _dot_class(value: Number, limit: Number | None) -> str:
    """A price's dot, judged as the price itself would be."""
    if limit is None:
        return "strip-dot"
    if float(value) <= float(limit):
        return "strip-dot strip-dot-under"
    return "strip-dot strip-dot-over"


def rank_strip(
    peers: Sequence[Number], mine: Number, *, width: int = 64, height: int = 14
) -> Markup:
    """Where this copy sits among the copies of its kind listed now."""
    if len(peers) < 2:
        return Markup("")
    scale = scale_for(peers, width)
    mid = height / 2
    others = list(peers)
    others.remove(mine)
    place = sorted(float(p) for p in peers).index(float(mine)) + 1
    parts = [
        f'<line class="strip-axis" x1="{PAD}" x2="{width - PAD}" '
        f'y1="{mid}" y2="{mid}"/>',
        *(
            f'<circle class="strip-peer" cx="{scale.x(v)}" cy="{mid}" r="2.4"/>'
            for v in others
        ),
        f'<circle class="strip-mine" cx="{scale.x(mine)}" cy="{mid}" r="4"/>',
    ]
    label = f"{place} of {len(peers)} by price among copies listed now"
    return Markup(
        f'<svg class="strip" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{label}">'
        + "".join(parts)
        + "</svg>"
    )
