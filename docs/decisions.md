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

**Resolved, 2026-09-22.** The issued keys initially returned `invalid_client`.
The request shape was ruled out first — the same rejection comes back through
httpx's own Basic-auth implementation — and the keyset turned out to be marked
Non Compliant in eBay's console. eBay disables a production keyset until
account-deletion compliance is settled, which is decision 16. Once the deletion
endpoint was deployed and registered, the token exchange succeeded:
a two-hour application token on the `api_scope` scope. The Browse API is
available. `uv run python -m book_watch.ebay` is the check, and it passes.

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

**One machine, not Fly's default pair.** A first deploy creates a running
machine and a stopped standby. The standby costs little — rootfs only, pennies
a month — but it buys availability that a single user would never notice, and
it is a second thing that can drift out of step with the first. The deploy
workflow passes `--ha=false` and enforces `scale count 1`. Adding redundancy
back should be a deliberate act, not a default nobody chose.

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
deferral that looks harmless until the day it isn't. It is also tracked as
[issue 6](https://github.com/loserpoints/book-watch/issues/6), because this
record can say what was decided but not whether it is still owed.
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
GitHub.

The token was organisation-scoped for the first deploy only, because an
app-scoped token cannot create the app it is scoped to, and creating the app
through Fly's dashboard instead would have set up Fly's own GitHub deployment —
a second pipeline building this repo from its own branch. A short-lived broad
token was the lesser problem.

Once the app existed an app-scoped token became possible, so `FLY_API_TOKEN` is
now one, and the organisation token was revoked. The workflow needs no change
for this: its create-the-app step checks whether the app exists first, and with
an app-scoped token simply skips.

That token does not expire. Expiry is the wrong control here — a narrow token
on a project that deploys rarely would fail months later looking exactly like a
misconfiguration, and revocation from the dashboard is the control that
actually matters.

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

---

## 19. Work is tracked in the repo and in GitHub, split by what changes

**Decision.** Three layers, with a hard rule about where each lives.

| Layer | Lives in | Holds |
|---|---|---|
| Job | `docs/jobs.md` | Why work exists, and the test for whether it worked |
| Milestone | `docs/milestones.md` + a GitHub milestone | A usable subset of value, and why it comes now |
| Slice | One GitHub issue | Roughly one pull request of work |

**Status is never written to a file.** A closed issue is the only record that
something is done. The repo holds intent, which changes slowly; GitHub holds
state, which changes constantly.

A slice links to its milestone and nothing else. A milestone names the jobs it
advances. A slice's relationship to a job is therefore transitive.

**Alternatives.** Jira or Trello, rejected on sight — the point of this project
is to work without the apparatus of an organisation. A GitHub Project board,
which is genuinely good and is the obvious answer; rejected because its state
lives outside the repository, and because it is the tool being escaped from
wearing a different hat. A committed `ROADMAP.md` with checkboxes, which was
the first design and is the one worth explaining.

**Why not the roadmap file.** It duplicates state that GitHub already holds, so
within about two weeks it disagrees with the issues and then quietly lies. This
is the failure this record already warns about at the top of the file: a stale
record is worse than none, because it gets trusted. The rule that falls out of
it — never write status into a file — is what shaped everything above.

**Why slices don't carry a job label.** They did in the first draft. The
problem showed up immediately on the least interesting slice in M1: a `book`
table and a migration runner serve whatever gets built next, not any one job,
and labelling it `job:J1` would have polluted the "everything serving J1" view
with infrastructure. A derived link is honest about being approximate; a
declared one asserts a precision that isn't there. Losing the per-job view is
the cost, and for one person and six jobs it is not worth much.

**What the sections had to survive.** Two were cut for the same reason after
being written. A "what this isn't" section on each job: the set of things
something is not is unbounded, so what gets written is whatever the author
happened to worry about that morning, and the one genuinely useful case — the
boundary against a sibling job — belongs in the doneness test where it can
actually fail. A "not in this slice" section: the milestone already lists the
neighbouring slices, so the exclusion restates the boundary and then rots when
the neighbour is re-cut. What bounds a slice is its acceptance list. Wanting to
write an exclusion is a signal that list is too loose.

**Cost.** Seeing where a job stands takes a query rather than a glance, since
nothing aggregates it. Milestones beyond the current one aren't written down,
so there is no roadmap to show anyone — deliberate, but it is a real thing
given up. And the pattern itself is unproven: it is being built at the same
time as the thing it tracks, which is the point but also the risk.

---

## 20. "No price history" is removed as a non-goal

**Decision.** The brief's non-goal — *"Price history or trend charts. I want to
know a copy exists at my price, not what copies have cost over time"* — is
struck. It is replaced by J5 in `docs/jobs.md`: *buy without wondering if I
overpaid*.

**The mechanism is explicitly undecided, and is not committed to eBay's sold
listings.** Four candidates are recorded against J5 with their costs; none is
chosen. J5 remains a nice-to-have with no milestone.

**Why the reversal.** The non-goal rejected a *solution* and lost a *job* on
the way past. Price history charts genuinely aren't wanted. But the question
underneath — *am I about to overpay?* — is real, and it bites hardest in
collectible mode, where there is no reference price to work from. The failure
is concrete: hesitate on a copy, go and check elsewhere, come back, it's sold.

**Why this is recorded rather than quietly edited.** Reading decision 4 in six
months against a brief that no longer agrees with itself is exactly the
confusion this file exists to prevent. The non-goal was right about charts and
wrong about the need.

**Cost.** One fewer boundary. "Don't overpay" is open-ended in a way "find a
copy under $8" is not, and it is the most plausible source of scope creep in
the project. It stays unscheduled for that reason. The cheapest candidate
answer — showing where a listing sits among current listings for the same
edition — needs no new API and no new data, and is the one to reach for first
if it ever gets built.

---

## 21. ISBN searches go in `q`, not `gtin`

**Decision.** `item_summary/search` is called with the ISBN as a keyword in
`q`. The `gtin` parameter is supported by the client but is not the default.

**Alternatives.** `gtin`, which is the parameter eBay provides for exactly this
purpose and is the obvious choice on paper.

**Why.** Measured rather than assumed. Three ISBNs, each searched both ways
against production, limit 50:

| ISBN | `q` | `gtin` |
|---|---|---|
| 9780099448396 | 6 | 0 |
| 9780141439518 | 50 (the limit) | 4 |
| 9780307474278 | 50 (the limit) | 3 |

Used-book sellers put the ISBN in the title and the description and mostly
leave eBay's structured product fields empty. `gtin` searches the field they
didn't fill in.

**What this measures, and what it doesn't.** Recall, not precision. `q` finds
far more listings; whether the extra ones are the right book is not
established, and a keyword search for a number will happily match a different
edition that happens to quote it. Precision is J2's problem and nothing here
answers it.

**Cost.** The default is now the noisy option, so matching and filtering have
real work to do. The brief already said as much — it calls identity resolution
the hard part — but this makes it concrete rather than anticipated. `gtin`
stays available as the high-precision fallback for a title where keyword search
turns out to be hopeless.

---

## 22. Landed cost comes from the search response, not a call per listing

**Decision.** Shipping cost is read from `shippingOptions` in the search
results, taking the cheapest stated option. No `getItem` call per listing.

**Alternatives.** `getItem` for each result, which returns fuller shipping
detail.

**Why.** Shipping is already in the search response. It did not have to be, and
the question this slice existed to settle was whether ranking on landed cost
would cost one API call or fifty-one. At 5,000 calls a day against an expected
~250 (decision 4), a per-item call would turn a single 50-result page into a
tenth of the daily budget, and would make the eventual daily poll the dominant
consumer of a quota that was chosen for having ample headroom.

**The three-valued rule this forces.** A shipping option with no
`shippingCost` means calculated at checkout — not free. `Listing.shipping_cost`
is therefore `Money | None`, where zero and unknown are different answers, and
`landed_cost` returns `None` rather than a number when shipping is unstated or
is in a different currency from the price. Collapsing those cases would rank an
expensive copy first and never look wrong on screen, which is the worst kind of
bug this app can have: silent, plausible, and in the one number the brief says
to optimise for.

**Cost.** The cheapest stated option is not always the one a buyer would pick —
it may be slow, or be local pickup that isn't usable. Good enough to rank on,
and the brief optimises for landed cost rather than delivery speed. If a copy
turns out to be worth buying, the real shipping detail is one click away on the
listing itself.

---

## 23. One definition of "does this pass", in `scripts/check.sh`

**Decision.** CI runs `scripts/check.sh`, and the slice issue template's
acceptance list tells you to run the same script. Three named CI steps became
one.

**Alternatives.** Leaving the three steps and repeating them in the template,
which is the status quo. A `Makefile` with a `check` target. A task runner such
as `poethepoet`.

**Why.** The two copies had already drifted, and it cost a red build. The
template seeded every acceptance list with `ruff check` and `pytest`; CI also
ran `ruff format --check`; a slice validated against its own checklist, passed,
and failed CI on formatting. The checklist was not wrong about the code. It was
wrong about what "passes" means, and no amount of care could have caught that
while two definitions existed — which is the same argument decision 19 makes
for never writing status into a file, applied to a different kind of
duplication.

A `Makefile` would do the same job and is more conventional for this, but make
brings its own tab-sensitive syntax to a repo with no other use for it. A task
runner adds a dependency to run three commands a five-line script already runs.

**Cost, and it is a real one.** A failure now appears in GitHub's job list as
`Check` rather than as `Lint`, `Check formatting` or `Test`, so seeing which
stage broke means opening the log. The script echoes each stage, so the log
says plainly which one — but the at-a-glance signal is gone. Granularity in the
UI, traded for a definition that cannot drift.

**Why a shell script is enough here.** Only two things ever run it: CI, and an
agent working in a container. Decision 18 assumes no usable local machine, so
the portability a contributor-facing script would need is not a cost this one
has to carry.

---

## 24. The web application boots without eBay search credentials

**Decision.** `create_app` loads the deletion endpoint's configuration eagerly
and the eBay search credentials not at all. The Browse client is built on the
first search (`listings.LazyBrowseSearch`), so a missing key fails that request
rather than the process.

**Alternatives.** Loading both at startup, which is what decision 14's
fail-fast-with-a-clear-message argument suggests, and what the deletion config
already does.

**Why the asymmetry.** Production does not have the eBay keys. Fly holds
`EBAY_VERIFICATION_TOKEN` and `EBAY_DELETION_ENDPOINT_URL` — the deploy
workflow sets exactly those two — and nothing else. An application that read
`EBAY_CLIENT_ID` while booting would crash on the next deploy, and what it
would take down is the compliance endpoint: the one thing running there that
carries an uptime obligation, which eBay re-validates on its own schedule and
whose failure marks the keyset Non Compliant (decision 16). The application
would be down for want of a credential that nothing deployed actually uses.

Failing fast is right when the thing that fails is the thing that is broken.
Here it would fail something else entirely.

**What this defers, and it is not small.** Search does not work in production
and will not until the eBay keys reach Fly. That is its own decision rather
than this one: decision 15 deliberately keeps eBay credentials out of GitHub,
and the deploy workflow takes Fly's secrets from GitHub, so putting search in
production means either revisiting 15 or setting that secret on Fly by some
other route. It needs settling before any milestone depends on the deployed
application rather than a local one.

**Cost.** A misconfiguration surfaces as a broken page rather than a refused
startup, which is the weaker signal and is exactly what decision 14 argued
against. Accepted here because the alternative is worse, and there is a test
asserting that startup does not read the search credentials — "make it eager,
it's tidier" is a very natural change for someone to make later, and it would
be discovered in production.

---

## 25. Where each credential lives

**Decision.** One table, because the answer was previously only inferable by
reading three other entries.

| Credential | GitHub secret | Fly secret | Read by |
|---|---|---|---|
| `FLY_API_TOKEN` | yes | no | the deploy workflow |
| `EBAY_VERIFICATION_TOKEN` | yes | yes | the app, and the deploy workflow's verification step |
| `EBAY_DELETION_ENDPOINT_URL` | no | yes, set by the workflow | the app |
| `EBAY_CLIENT_ID` | **no** | yes, set by hand | the app |
| `EBAY_CLIENT_SECRET` | **no** | yes, set by hand | the app |

**Why the eBay keys are not in GitHub.** Nothing in GitHub reads them. Routing
them through a GitHub secret so the deploy workflow could forward them to Fly
would put a second copy in a second system that never uses it — leak surface
for no benefit. Decision 15 stands untouched: CI holds no eBay key and still
cannot run the network tests.

**Why the verification token is in both, and that is not the same mistake.** It
has to be. The deploy step computes the expected challenge response itself and
compares it against the live endpoint's, which is only a meaningful check if
GitHub holds the same token the app does. Two copies with a job to do, rather
than two copies by habit.

**Why typing the eBay keys into Fly's dashboard does not contradict decision
18.** That entry says nothing is typed into Fly's dashboard, for one specific
reason: `EBAY_DELETION_ENDPOINT_URL` is hashed into every challenge response
and must equal eBay's console copy exactly, so it is derived from `fly.toml`
where it cannot drift. The eBay keys have one copy and nothing to drift
against, so the rationale does not reach them.

**An open question this raised, now settled.** The deployed search page is
publicly reachable and unauthenticated, and every request spends one of 5,000
daily eBay calls. Nobody is likely to find the URL, but "unlikely to be found"
is not "safe", and an exhausted quota breaks the tool quietly.

**Resolved, 2026-09-22: no authentication, for now.** The brief's non-goals
rule out accounts and auth, and for one user behind an unadvertised hostname
the realistic risk is close to nil. The deciding argument is that this is cheap
to reverse: HTTP basic auth is roughly ten lines and one Fly secret, touches no
schema, needs no migration, and can be added the day anything suggests it is
wanted.

What that day looks like, so it is recognised rather than rationalised: eBay
reporting call volume nobody made, the search page answering slowly for no
reason, or the hostname becoming discoverable — linked publicly, or indexed.
Nothing links to it today, and search engines find pages by following links.

**Cost.** Secrets set by hand are not in version control, so nothing reviews or
recreates them: rebuilding the app from scratch means re-entering two values
from eBay's console. `.env.example` is the record of which names are needed,
which is what makes that recoverable rather than archaeology.

---

## 26. A want-list entry is one ISBN, not one book

**Decision.** `book` holds one row per ISBN. A title I would accept in any
edition is several rows until edition resolution exists.

**Alternatives.** Modelling works and editions now — a `work` table with
`edition` rows hanging off it — and typing a single ISBN into that shape.

**Why.** Open Library's works-and-editions model is the intended backbone
(decision 7), and building a local mirror of it before having called the API
once would be guessing at a join whose shape is the very thing that makes
resolution hard. The brief calls identity resolution the hard part and manual
ISBN entry the escape hatch; M1 takes the escape hatch first deliberately, so
that what resolution has to do is learned from using the thing rather than
imagined.

**What it costs, and the cost is real.** Searching by one ISBN finds copies of
one edition. Someone hunting a cheap reading copy — who would happily take any
of a dozen editions — sees a fraction of what is actually for sale. That is not
a rough edge to polish; it is the gap that makes this a better saved search
rather than the tool the brief describes, and closing it is what edition
resolution is for.

**No `mode` column either.** M1 does not distinguish reading from collectible,
and a column nothing reads is a column that quietly stops meaning what its name
says. It arrives in the migration that first needs it.

---

## 27. Removing a book deletes the row

**Decision.** Removing a book from the want-list is a `DELETE`. No status
column, no soft delete, no archive.

**Alternatives.** A `status` column — wanted, bought, abandoned. Or a split:
keep the rows for books that were bought, delete the ones simply given up on.

**Why.** There is exactly one question that keeping rows would answer: *do I
already own this?* It is a real question for a list of dozens of books that get
read and donated. But it is a question about a **book**, and by decision 26 a
row is an **edition**. Marking one ISBN bought leaves the other editions of the
same title on the list, still wanted — so the answer is least reliable in
precisely the situation where it would be asked. The feature is worth much less
than it looks until resolution groups editions together.

The third state is also the one that genuinely resists definition. *Bought* is
obvious. *Didn't buy it and no longer want it listed* has no clear meaning yet,
and inventing one now and then living with the invention is worse than using
the simple version and finding out from use what the distinction should be.

**Cost.** Removal is irreversible, so a mistaken tap loses the entry. Re-adding
takes seconds, which is the brief's own bar for adding a book at all, so the
loss is bounded and small.

**Revisit when** edition resolution groups editions under a work. At that point
*bought* becomes a statement about a book rather than about one ISBN among
several, and starts being worth recording.

---

## 28. The SQLite file lives on a mounted Fly volume

**Decision.** A 1GB Fly volume named `book_watch_data`, mounted at `/data`,
with `BOOK_WATCH_DB_PATH=/data/book-watch.db`. The deploy workflow creates the
volume if it is absent and leaves it alone otherwise.

**Why this is an entry rather than a footnote to decision 10.** Entry 10 costed
a 1GB volume and then nothing mounted one. A machine's own filesystem is
rebuilt on every deploy, so a want-list written there would have survived
exactly until the next release — working perfectly in testing, losing
everything in use, and giving no error either time. The gap between a decision
and its implementation is invisible in a way the decision itself is not, which
is the argument for writing down the mount rather than assuming entry 10 covers
it.

**What mounting a volume constrains.** A Fly volume attaches to one machine.
That suits this app, which is pinned at a single machine on purpose (entry 10),
but it turns that pin into a correctness requirement rather than a cost
preference: a second machine would not share this database, it would have none.
`--ha=false` and `scale count 1` were about spending less. They are now also
about the want-list being in one place.

**Why creation is conditional, and why that check is not decoration.** Fly does
not object to a second volume of the same name. It would be given to a second
machine, and the list would appear to lose and regain entries depending on
which machine answered. The workflow counts volumes by name and creates one
only when none exists.

**Cost.** Fly bills volumes per GB-month on top of the machine. 1GB is far more
than a want-list in the dozens will ever use — a database of a few thousand
listings is measured in megabytes — but it is Fly's usual minimum and the
smallest thing worth having. A volume also cannot be shrunk, only grown, so
starting small costs nothing later.

**What is not solved.** A volume is storage, not a backup: it is one copy, and
deleting it or losing the machine loses the want-list. For a list that can be
retyped in an evening that is an acceptable trade, and it is recorded so it is
a trade rather than an assumption.
