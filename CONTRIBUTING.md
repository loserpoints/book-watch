# Contributing

## Building

- Check a fact against the thing itself before building on it: the service's documentation, a real response, or the browser's own tools. Memory and old notes go stale.
- When a service's documentation confirms a behavior, name the field that carries it, and check the code reads that field. S39 relied on eBay keeping a relisted copy's date and read the field that doesn't keep it.
- When a session can't reach a service's documentation, ask Alan to allow its domain and its subdomains, such as `fly.io` and `*.fly.io`, rather than building on memory.
- eBay's developer and help pages refuse a session's requests whatever the network allows. Ask Alan to read the page, and give him the endpoint and field names from the code, never a page title from memory.
- Measure before deciding when a choice turns on a number, and measure again when the data grows.
- Before inventing a proxy for a signal, check whether the code already has the signal and throws it away.
- Decide a design by looking at it on real screens at phone width.
- Ask Alan for his ideas before each round of mocks, and mock them among the options. A round of options that leaves out Alan's idea is usually followed by one that mocks it.
- A layout aims for three rounds. Past three, it keeps going until the design is right, and its slice records why it took more.
- Migrations run forward only, and a rollback does not undo them. Keep a migration additive, so the previous code still works if its change is reverted.
- Reproduce a phone or platform behavior on the phone again before building around it. S47's fallback to the browser went away once the eBay app had been opened.
- Every step runs from a browser. Deploys and other privileged actions run in CI, with credentials in GitHub or Fly secrets. Say so before building on anything that needs a local install or a local credential.
- A one-off command that needs the app's secrets runs inside the live Fly machine, from a workflow through `flyctl ssh console`. The deploy token allows it, and the secrets never enter GitHub.
- The app runs only on Fly, so a message it shows gives the fix on Fly, not on a laptop.
- Never commit a key, token or password. Credentials come from environment variables. `.env` is gitignored and `.env.example` lists the names with no values. A committed secret stays in git history, so the only remedy is rotating it.
- Actions logs are public, like the repository. A workflow prints nothing that holds an address or a key.
- Running cost is about $2–3 a month, all hosting. Say so before adding anything with a recurring cost.
- Every request to an outside service follows the [rate limits](docs/rules/rate-limits.md).
- Make work that can overlap harmless where it happens, rather than blocking the ways in. S68 found a second check during a running examination lost copies for good. Greying out the buttons would have left the 7am check, and any path not yet thought of, still losing them.
- A check on data the app reads from outside fails only what the app can't read correctly. A property it can read through, such as a page's price order, is measured and counted instead. A rule drawn from a few samples fails real data, as AbeBooks' order check did on its first day.

## Testing

- `scripts/check.sh` is the one definition of passing: lint, formatting, the docs check and the tests. CI runs it on every pull request.
- Read a check's exit status. Piping it through another command hides a failure.
- A feature that acts on an outside event, such as an email sent when a copy appears, needs a way to trigger it on demand, built in its slice. Otherwise nothing proves it works until the event comes.
- When the event can't be made on demand, such as a seller repricing a copy, the slice says so when it is planned, and names the nearest check and how long it may wait. S72's carets waited on a real price move.
- A trigger on demand proves the plumbing, not the choice of what to act on. Check that on the live app with data that makes the event likely, such as a book with many listings and a generous limit.
- Run every change to a screen in a real browser at 360px wide, in both themes, and look at it. Tests miss layout, fonts and taps.
- Desktop Chromium shows no pressed state for a touch, even emulating a phone, so a pressed look is checked on the phone. S73's fill showed in the browser and not on a copy on the phone.
- Test a layout fix in the case that broke: the phone width and the data where it happened. A fix that only measures what changed can miss that the layout no longer fits.
- This environment holds real eBay keys. Run the app locally only with `uv run python scripts/serve_local.py <database> [port]`, which fakes eBay's search, never reads AbeBooks, and refuses every request. The app as built for production searches eBay when a book page opens and examines every copy it finds.
- Tests check what a reader sees, not the markup that carries it, so they survive a redesign.
- A test of a request htmx makes sends what htmx sends with it, such as `HX-Current-URL`. From S60 to S69, switching "Under limit" off kept the list filtered, because the tests asked for the list without the page it came from.
- A check proves nothing until it has been seen to fail. Break the code on purpose, on a committed tree, and confirm the break applied.
- A migration's test checks that its own migration ran, not that it is the newest. S65's test assumed 025 was the last and broke when 026 arrived.
- Reset process-wide state between tests. A test that passes only because another ran first proves nothing.
- Run the production entrypoint before trusting what only it starts, such as the daily check. No test starts it.
- Keep labeled real data in the repository as test fixtures, so a study becomes a regression test.
- A fake of an outside service answers with what the real one sends, field names and units included, taken from a real response or the service's own source. A fake built from memory passes the tests and fails the first real run.
- Tests start empty and miss what production holds. After a change deploys, Alan checks it on his phone against the live data, and its pull request says what to check.
- That check starts from a fresh open of the app. An app left open through a deploy redraws in new markup with the stylesheet it loaded before, as S69 did on its first check.

## Reviewing

- Open a pull request as soon as a branch has something reviewable. Small and frequent beats large.
- Merging to `main` deploys once CI passes, with nobody watching. Merge only what is ready to be live (see the [runbook](docs/runbook.md#deploy)).
- Before pushing, re-read the diff for what would make CI reject it.
- Review each screen by using it and asking what each part means. That finds defects the tests pass.
- Never push to `main`. Before pushing to a branch, check its pull request is still open. A merged pull request cannot take new work, so start a new branch from `main`.
- Before building on another pull request, check it has merged.
- When a change makes a doc untrue, update the doc in the same pull request.
