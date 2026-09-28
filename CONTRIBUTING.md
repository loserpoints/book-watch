# Contributing

## Building

- Check a fact against the thing itself before building on it: the service's documentation, a real response, or the browser's own tools. Memory and old notes go stale.
- Measure before deciding when a choice turns on a number, and measure again when the data grows.
- Before inventing a proxy for a signal, check whether the code already has the signal and throws it away.
- Decide a design by looking at it on real screens at phone width, and agree beforehand how many rounds a layout gets.
- Migrations run forward only, and a rollback does not undo them. Keep a migration additive, so the previous code still works if its change is reverted.

## Testing

- `scripts/check.sh` is the one definition of passing: lint, formatting, the docs check and the tests. CI runs it on every pull request.
- Read a check's exit status. Piping it through another command hides a failure.
- Run every change to a screen in a real browser at 360px wide, in both themes, and look at it. Tests miss layout, fonts and taps.
- Tests check what a reader sees, not the markup that carries it, so they survive a redesign.
- A check proves nothing until it has been seen to fail. Break the code on purpose, on a committed tree, and confirm the break applied.
- Keep labelled real data in the repository as test fixtures, so a study becomes a regression test.
- Verify a change against a copy of production data as well as a fresh database. Tests start empty and miss what production holds.

## Reviewing

- Open a pull request as soon as a branch has something reviewable. Small and frequent beats large.
- Merging to `main` deploys once CI passes, with nobody watching. Merge only what is ready to be live (see the [runbook](docs/runbook.md#deploy)).
- Before pushing, re-read the diff for what would make CI reject it.
- Review each screen by using it and asking what each part means. That finds defects the tests pass.
