# Working agreement

This file loads into every session, so keep it short.

## Start here

Read `docs/product-brief.md` and `docs/decisions.md` before doing anything
else. They carry the scope, the two use cases, and why each technical choice
was made. If something here contradicts them, they win — and say so.

## Context

This is a personal hobby project on a Pro account, not an enterprise one.
Be judicious with tokens. Prefer one well-aimed search over three broad
ones, and don't re-derive what the docs already state.

Alan is a product manager, not a professional developer, and is building
this partly to feel the trade-offs directly. **Explain the choice, don't
just implement it** — what the alternatives were and what this one costs.
That's a goal of the project, not an overhead on it.

## Before changing anything

Say what the change buys before making it. Scope creep is the main risk on
a project with no deadline. "I can do this" is not the same as "this is
worth doing."

Don't claim something works without running it.

## Git

- Check a PR is still **open** before pushing to its branch. A merged PR
  cannot track new work — start a fresh branch from the default branch.
- Check prior PRs are merged before building anything that depends on them.
- Never push directly to `main`.

## Secrets

Never commit a key, token or password. Credentials come from environment
variables; `.env` is gitignored, `.env.example` is committed with variable
names and no values.

Anything committed stays in git history after it is removed, so rotating
the credential is the only real remedy. Get it right the first time.

## External services

Single user, no leverage, and a ban is a ban.

- Rate limit every loop that hits an API or a site. Sleep between requests.
- Stay well inside published limits rather than close to them.
- Cache aggressively. Never re-fetch what is already stored.
- Send a descriptive User-Agent with contact details where the service
  expects one.
- **Ask before running anything that makes a real request in bulk.**

Open Library states its API is not intended as a backend for third-party
services. Resolution results are cached in SQLite and refreshed monthly;
the polling loop reads the cache, never Open Library directly.

## Cost

The running budget is roughly $2–3/month, all of it hosting. Anything that
adds a recurring cost should say so explicitly before it is added.

## Keeping the docs true

When a decision changes, update `docs/decisions.md` in the same commit. A
stale decision record is worse than none, because it gets trusted.
