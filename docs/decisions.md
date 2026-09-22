# Decision record

Short entries, one per decision that would be expensive to reverse or annoying
to re-argue. Each states what was chosen, what else was considered, and why.

*Last updated: 2026-09-22*

---

## 1. Python

**Decision.** Python 3.12+, managed with `uv`, linted and formatted with
`ruff`, tested with `pytest`.

**Alternatives.** R, which I already know. TypeScript/Node.

**Why.** This app is almost entirely plumbing — HTTP clients, OAuth, a
scheduler, email, SQLite — and Python's ecosystem for all five is mature and
heavily documented. R is a poor fit for long-running scheduled services, and
its deployment options are narrower and more expensive. TypeScript would be the
better call if the UI were ambitious; it isn't.

The cost is learning a new language. That cost is real but bounded: the R I
know transfers conceptually, and almost nothing here is statistical.

---

## 2. Server-rendered UI, no JavaScript build step

**Decision.** FastAPI with Jinja2 templates and HTMX for interactivity.

**Alternatives.** A React or Svelte single-page app with a JSON API. A CLI. A
plain config file with no UI at all.

**Why.** A separate frontend would double the surface area and introduce a
build toolchain, a second language, and a deployment story — for a tool with
one user and about four screens. HTMX gets dynamic behaviour without any of
that.

A config file would have been the smallest thing that works, and was seriously
considered. The UI was chosen anyway because adding a book needs to take under
thirty seconds or I won't do it, and hand-editing YAML doesn't clear that bar.

---

## 3. SQLite, with the schema in plain SQL

**Decision.** SQLite. Schema defined in a readable `.sql` file. Plain numbered
migrations.

**Alternatives.** Postgres. An ORM — SQLModel or SQLAlchemy's declarative
layer. Alembic for migrations.

**Why.** One user, one writer, a database measured in megabytes. Postgres would
add a service to run and pay for and solve nothing.

Writing the schema as SQL rather than hiding it behind an ORM plays to existing
SQL fluency — the data model stays legible instead of being an emergent
property of Python class definitions. Alembic is real machinery for a problem
one user does not have; numbered migration files are enough.

---

## 4. eBay Browse API as the anchor source

**Decision.** eBay Browse API, OAuth client-credentials flow.

**Alternatives.** eBay's Finding API. Scraping.

**Why.** It's free with no expiry, well documented, and 5,000 calls/day against
an expected ~250 is ample headroom. The Finding API was decommissioned in
February 2025 — any tutorial referencing it is stale.

**Risk, now resolved.** Developer account registration is sometimes rejected.
It wasn't — production keys were issued, so the question the Phase 1 spike
existed to answer is answered. The token exchange was therefore written as real
code (`src/book_watch/ebay/auth.py`) rather than throwaway spike code, and
`spikes/` was removed.

**Cause of the initial failure, now understood.** The issued keys returned
`invalid_client`. The request shape was ruled out first — the same rejection
comes back through httpx's own Basic-auth implementation — and the keyset
turned out to be marked Non Compliant in eBay's console. eBay disables a
production keyset until account-deletion compliance is settled, which is
decision 16. `uv run python -m book_watch.ebay` reports the failure and lists
what to check.

---

## 5. AbeBooks is dropped

**Decision.** Not integrated.

**Why.** The original plan assumed AbeBooks was a slow approval. It isn't — the
public affiliate and search API was deprecated and is closed to new developers,
and the Purchase API is restricted to existing partners. There is no path in.

This matters because AbeBooks holds a lot of the cheap inventory. Biblio
partially covers the gap.

---

## 6. Biblio as the second source, pending terms

**Decision.** Request an API key via the affiliate program. Integrate if the
terms permit.

**Why.** Biblio aggregates independent antiquarian sellers, which is where both
cheap reading copies and collectible editions actually live — a better fit for
this tool than AbeBooks would have been. Keys are granted on request with a 3–5
business day turnaround, so the request goes in first and the wait runs in the
background.

**Risk.** It's an *affiliate* API, which implies an expectation of referral
sales this tool won't generate. If the terms don't fit, fall back to eBay-only
and say so, rather than quietly ignoring them.

**Alibris** was considered and deprioritised: its developer portal launched in
2010 on Mashery, which has since wound down.

---

## 7. Open Library for edition resolution, cached hard

**Decision.** Open Library resolves title/author or ISBN into an edition set.
Results are cached in SQLite and refreshed monthly. Requests send a descriptive
`User-Agent` with contact details.

**Alternatives.** ISBNdb (paid). Google Books API. Resolving nothing and
matching on title strings.

**Why.** Open Library's works-and-editions model matches the actual problem,
and it's free with no key. Title-string matching was rejected outright: it's
precisely what makes existing keyword alert tools useless for this.

**Constraint, not a preference.** Open Library is a non-profit that explicitly
states its APIs are not intended as a backend for third-party services and asks
for caching and low volume. The daily polling loop must read the cache and
never call Open Library directly. Violating this risks being blocked.

---

## 8. In-process scheduling, daily

**Decision.** APScheduler running inside the web application. Daily cadence.

**Alternatives.** System cron. A separate worker process. GitHub Actions on a
schedule.

**Why.** One process is simpler to deploy, monitor and reason about than two.
Used-book inventory doesn't turn over fast enough to justify tighter polling,
and daily keeps API usage trivially inside every free tier.

GitHub Actions was attractive for being free, but the UI needs a persistent
database that Actions can't host.

---

## 9. Resend for email

**Decision.** Resend. Daily digest containing only new listings under
threshold.

**Alternatives.** SendGrid, Postmark, Amazon SES, raw SMTP through a personal
account.

**Why.** Simple API, no credit card, 3,000 emails/month free against expected
usage of about 30. Sending through a personal SMTP account invites deliverability
problems that aren't worth debugging.

---

## 10. Containerised, deployed to Fly.io

**Decision.** Docker container on Fly.io — a 256MB shared-CPU VM with a 1GB
persistent volume for the SQLite file. Roughly $2–3/month.

**Alternatives.** Render's free tier. Railway. Self-hosting on owned hardware.

**Why.** Render's free tier has no persistent disk, so the database would be
wiped on every restart — disqualifying. Fly's own free tier has ended, so
there's no zero-cost cloud option; $2–3 buys not having to care whether a
machine at home is awake.

Because it's containerised, this is cheap to reverse. Self-hosting the same
image on owned hardware is the $0 fallback if the bill ever stops being worth
it.

---

## 11. Secrets in environment variables, never in source

**Decision.** `.env` locally, gitignored, with a committed `.env.example`
documenting the required names. Fly secrets in production.

**Alternatives.** A config file. A secrets manager.

**Why.** Standard practice, and the failure mode is concrete rather than
theoretical: the adjacent `movie-analysis` repo had a database password
committed to a public repository for six years. A secrets manager is
disproportionate for one app with three credentials.

---

## 12. CI from the first commit

**Decision.** GitHub Actions running `ruff` and `pytest` on every push.

**Why.** Free for public repos and near-zero configuration. Partly it catches
mistakes; partly a visible green check is what distinguishes a project from a
folder of scripts, which matters for a repo that's public on purpose.

---

## 13. httpx as the HTTP client

**Decision.** `httpx`, used synchronously.

**Alternatives.** `requests`. `urllib` from the standard library. `aiohttp`.

**Why.** Two reasons, both about testing and the future shape of the app.

`httpx` ships `MockTransport`, a fake transport a client talks to instead of a
socket. The eBay auth tests assert on the exact request that would have gone
out — URL, headers, form body — without a network, a key, or a mocking library
that monkeypatches the client's internals. `requests` needs `responses` or
`requests-mock` to get there.

And `httpx` offers the same API synchronously and asynchronously. FastAPI
(decision 2) is async; when a request handler eventually needs to call eBay,
that's `AsyncClient` with the same method names, not a second library.

**Cost.** A dependency where the standard library would technically do, and a
library with a faster-moving release cadence than `requests`. Sync was chosen
over async now because nothing here is concurrent yet, and async colours every
function that touches it.

---

## 14. Credentials loaded by hand, not by a settings framework

**Decision.** A frozen dataclass reading `os.environ`, with `python-dotenv`
loading `.env` in development. `src/book_watch/config.py`.

**Alternatives.** `pydantic-settings`. Bare `os.environ` with no `.env` at all.

**Why.** It is about twenty lines with no framework behaviour between the code
and an environment variable, which suits a project whose stated point is
feeling the trade-offs directly. `python-dotenv` does not overwrite variables
that are already set, so a real environment variable always beats the file —
which is what makes the same code correct locally and in production.

The credential dataclasses suppress their own `repr`. Objects like these end up
in tracebacks and log lines, and per decision 11 a secret that reaches one has
to be rotated, not deleted.

**Cost.** FastAPI will bring pydantic in anyway, so there will eventually be two
ways of describing configuration in the repo. Accepted: the migration is one
small file if it ever stops being worth it.

---

## 15. Tests that touch the network are opt-in, and CI holds no credentials

**Decision.** Tests hitting a real service carry a `network` marker and are
deselected by default. CI runs `ruff` and the offline suite only, and no eBay
key is stored as a GitHub secret. The live check is run by hand:
`uv run pytest -m network`, or `uv run python -m book_watch.ebay`.

**Alternatives.** Storing the keys as repository secrets and verifying against
the live API on every push.

**Why.** Fewer places a credential exists is fewer places it can leak, and it
keeps a green check from depending on eBay being up. It also honours the
external-services rule in `CLAUDE.md`: every push to a branch would otherwise
be an unrequested request to somebody else's API.

**Cost, and it is a real one.** CI structurally cannot tell you that a key has
been revoked or has expired — only the manual check can. That is the trade
being made, not an oversight.

---

## 16. Receive eBay's account deletion notifications rather than request an exemption

**Decision.** Run an HTTPS endpoint that answers eBay's marketplace account
deletion notifications. Deploy it to Fly.io now, ahead of the rest of the app.

**Alternatives.** Request the exemption eBay offers for applications that
persist no eBay user data. Host the endpoint separately, on a free Cloudflare
Worker.

**Why.** eBay disables a production keyset until one of the two is settled —
this is what was behind the `invalid_client` in decision 4, not a bad
credential. The exemption is not a switch: it opens a request with a stated
reason, and eBay's own wording is that the keyset activates once the opt-out
*succeeds*. A rejected request costs the waiting time and then the endpoint
work anyway, so the endpoint is the path that works under either outcome.

It also buys back a design freedom. The exemption would have permanently
committed the schema to holding no seller identifiers, since that claim is what
the exemption rests on. Receiving notifications instead leaves what to store as
an ordinary design decision.

Fly rather than a Cloudflare Worker because decision 2 chose one language on
purpose. A separate JavaScript service with its own deploy pipeline and its own
copy of the verification token is a poor trade for $2–3/month, and the handler
will eventually need database access to delete anything it stored, which a
detached Worker would not have.

**Cost.** The hosting spend in decision 10 starts now rather than at launch,
and it buys nothing yet beyond compliance. The machine also cannot scale to
zero: eBay re-validates the endpoint on its own schedule and marks the keyset
non-compliant when the check fails, so a cold start that misses the timeout is
expensive in a way a slow request normally isn't.

**Consequence.** The eventual application host now has an uptime obligation
that has nothing to do with the application. If the endpoint moves, its URL is
hashed into every challenge response, so `EBAY_DELETION_ENDPOINT_URL` and
eBay's console copy have to change together.

---

## 17. Notification signatures are not verified yet

**Decision.** The GET challenge is answered properly. The POST notification is
acknowledged without verifying eBay's signature on it.

**Why.** Verifying means fetching eBay's public keys, caching them, and doing
ECDSA on each notification. Today the handler stores nothing and deletes
nothing, so the signature would be guarding a no-op: a forged notification can
cause exactly as much harm as a genuine one, which is none.

**The trigger to revisit, which is not "some day".** The moment the handler
touches the database — the first time it deletes anything — an unauthenticated
POST becomes a way to make this application destroy data on request. Signature
verification has to land in the same change, before that code does.

This is recorded rather than left implicit precisely because it is the kind of
deferral that looks harmless until the day it isn't.
---

## 18. Deploys run from GitHub Actions, not a laptop

**Decision.** A `Deploy` workflow runs `flyctl deploy`, triggered manually from
the Actions tab. Fly's deploy token is a GitHub Actions secret. No deployment
tooling or credential is installed on any personal machine.

Manual rather than on every push to `main`: a push-triggered deploy runs
alongside CI rather than after it, so it can ship a build CI is about to
reject. Deploys here are rare and the endpoint's uptime is load-bearing, so a
button press after CI goes green is the better trade. Automating it later means
making it wait for CI, not just adding the trigger back.

**Alternatives.** Running `fly deploy` locally, which is the normal way.

**Why.** The immediate reason is practical: the work computer is the machine
that is usually to hand, and a personal side project's credentials and payment
method have no business on it. Waiting until a personal machine is free would
gate the project on being at home, which is how hobby projects die.

The durable reason is that it is simply better. Deploys stop depending on one
correctly configured laptop, the deploy token can be revoked from a web page,
and every deploy leaves a log someone can read afterwards.

**What it costs.** Actions minutes are free on a public repository, so nothing
in money. The real cost is that a credential able to deploy to Fly now lives in
GitHub. Scoping the token to this one application rather than the whole
organisation keeps that blast radius to a single $2/month container.

**A consequence worth stating.** The image builds on GitHub's runner
(`--local-only`) rather than on a Fly builder machine, which would be billed as
compute. For an image this size the build time is much the same, and it keeps
the bill to exactly the one machine decision 10 costed.

**The verification step is the real payoff.** After each deploy the workflow
asks the live endpoint for a challenge response and compares it against one it
computes itself. A mismatch fails the build. This catches the failure that is
otherwise invisible — the deployed URL or token not matching what eBay was
given — before eBay ever sees it, and keeps catching it on every future deploy.
It was tested against both ways it can happen: a URL differing by one trailing
slash, and a token differing between Fly and GitHub.

**The general rule this is a case of.** Assume no usable local machine. Work
should be drivable from a browser, privileged actions should run in CI with
credentials held by GitHub or the service itself, and a tool that can only be
driven from a local CLI is carrying a real cost that has to be justified. This
constrains future choices as much as this one, so it is written into
`CLAUDE.md` rather than living only here.