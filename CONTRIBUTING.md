# Contributing

## Building

- Check a fact against the thing itself before building on it: the service's documentation, a real response, or the browser's own tools. Memory and old notes go stale.
- Measure before deciding when a choice turns on a number, and measure again when the data grows.
- Before inventing a proxy for a signal, check whether the code already has the signal and throws it away.
- Decide a design by looking at it on real screens at phone width, and agree beforehand how many rounds a layout gets.
- Migrations run forward only, and a rollback does not undo them. Keep a migration additive, so the previous code still works if its change is reverted.
- Every step runs from a browser. Deploys and other privileged actions run in CI, with credentials in GitHub or Fly secrets. Say so before building on anything that needs a local install or a local credential.
- Never commit a key, token or password. Credentials come from environment variables. `.env` is gitignored and `.env.example` lists the names with no values. A committed secret stays in git history, so the only remedy is rotating it.
- Running cost is about $2–3 a month, all hosting. Say so before adding anything with a recurring cost.
- Every request to an outside service follows the [rate limits](docs/rules/rate-limits.md).

## Testing

- `scripts/check.sh` is the one definition of passing: lint, formatting, the docs check and the tests. CI runs it on every pull request.
- Read a check's exit status. Piping it through another command hides a failure.
- Run every change to a screen in a real browser at 360px wide, in both themes, and look at it. Tests miss layout, fonts and taps.
- Tests check what a reader sees, not the markup that carries it, so they survive a redesign.
- A check proves nothing until it has been seen to fail. Break the code on purpose, on a committed tree, and confirm the break applied.
- Keep labelled real data in the repository as test fixtures, so a study becomes a regression test.
- Tests start empty and miss what production holds. After a change deploys, Alan checks it on his phone against the live data, and its pull request says what to check.

## Reviewing

- Open a pull request as soon as a branch has something reviewable. Small and frequent beats large.
- Merging to `main` deploys once CI passes, with nobody watching. Merge only what is ready to be live (see the [runbook](docs/runbook.md#deploy)).
- Before pushing, re-read the diff for what would make CI reject it.
- Review each screen by using it and asking what each part means. That finds defects the tests pass.
- Never push to `main`. Before pushing to a branch, check its pull request is still open. A merged pull request cannot take new work, so start a new branch from `main`.
- Before building on another pull request, check it has merged.
- When a change makes a doc untrue, update the doc in the same pull request.
