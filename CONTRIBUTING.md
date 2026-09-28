# Contributing

## Building

- Check a fact against the thing itself before building on it: the service's documentation, a real response, or the browser's own tools. Memory and old notes go stale.

## Testing

- `scripts/check.sh` is the one definition of passing: lint, formatting, the docs check and the tests. CI runs it on every pull request.
- Run every change to a screen in a real browser at 360px wide, in both themes, and look at it. Tests miss layout, fonts and taps.
- Tests check what a reader sees, not the markup that carries it, so they survive a redesign.

## Reviewing

- Open a pull request as soon as a branch has something reviewable. Small and frequent beats large.
- Before pushing, re-read the diff for what would make CI reject it.
