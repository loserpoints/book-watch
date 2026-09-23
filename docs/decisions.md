# Decision record

Short entries, one per decision that would be expensive to reverse or annoying
to re-argue. Each states what was chosen, what else was considered, and why.

*Last updated: 2026-09-23*

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

**Amended, 2026-09-23.** "Resolves into an edition set, refreshed monthly" is
no longer what happens, and with the edition set gone there is nothing left
that goes stale monthly. This entry now describes two questions:

1. **What is this book?** Asked once, when a book is added. One request
   returns a handful of candidates for a person to choose from.
2. **What is this number?** Asked once, the first time a seller-declared ISBN
   is seen in a listing. The answer is written down and never asked for again.

**The edition set was dropped because it was measured.** The plan was to pull
every edition of a book when it was added. Against what sellers actually
declared:

| | Editions fetched | Numbers sellers typed | Overlap | Fetched, never seen |
|---|---|---|---|---|
| Crash | 15 | 10 | **4** | 11 |
| Stoner | 46 | 15 | **7** | 39 |

It covered under half of what we met and about 80% of it was dead weight.
Worse, Open Library returns editions in record-creation order, so any cap on
the download is an arbitrary slice — *Pride and Prejudice* has 4,042 and there
is no way to ask for the ones likely to be for sale. And the same book is filed
under several works, so the set is incomplete at any cap. The numbers we care
about accumulate from listings instead: roughly 10–15 per book on its first
search, then almost nothing.

**Two lifetimes, not one.** What a number *is* cannot change, so a found
answer never expires. A **miss** can, because Open Library gains records — but
slowly, and every miss measured was a non-English edition, the population it is
weakest on. Ninety days: four questions a year per unknown number rather than
one a day. Decision 33 requires a miss and a failure to reach Open Library stay
distinguishable, so a miss is recorded and an outage writes nothing.

**No author is resolved, and that leaves a known gap.** Open Library holds
authors as internal references and files one person under several of them, so
turning them into names costs a request per author. Removing the author check
entirely changed zero answers out of 227 hand-labelled listings, because the
eBay search has already filtered by author before anything is looked up. The
gap it leaves: a *different* book with the same title, whose ISBN a seller
declared, would pass. Never seen in the sample, unmeasured beyond it, and
catching it means an author lookup per record. Worth revisiting only if it is
ever actually observed.

**What this costs, and why enrichment cannot run while someone waits.** A new
book's first search is 10–15 Open Library requests in quick succession. A
want-list filled in one evening would be two to three hundred in a few minutes,
which is precisely the volume this entry calls a constraint. So a book is added
and shown immediately, and its numbers are looked up in the background with a
pause between them. The want-list says so while that is happening, and listings
firm up from *possible* to *certain* as it completes.

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

**Superseded, 2026-09-23, by decision 34.** Migration 003 makes an entry name a
work and say which hunt it is on. The cost this entry named — that a reader who
would take any printing sees a fraction of what is for sale — is what decision
33 measured the way out of, and this is the shape it needs.

The stopgap did its job. What resolution has to do was learned from using the
thing: it was the labelling of 227 real listings, not the model, that showed
`epid` over-merges and Open Library's work ids over-split.

**The `mode` column arrived in the migration that first needed it**, exactly as
this entry said it would — though for a reason it did not anticipate. Nothing
reads `collector` yet. It is there because it is the one thing that cannot be
added later without migrating live rows a second time.

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

**Still nothing is stored about bought, 2026-09-23.** Migration 003 met the
condition above, and this entry stands unchanged: no column, no code, no plan.

Removing an entry now deletes the entry and leaves the work and its editions,
which are what was learned from Open Library and eBay rather than something a
person put there. The removal is still irreversible, which is what this entry
chose.

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

**What is not solved.** A volume is storage, not a backup: deleting it or
losing the machine loses the want-list. For a list that can be retyped in an
evening that is an acceptable trade, and it is recorded so it is a trade rather
than an assumption.

**Amended, 2026-09-22, after the volume was actually created.** Fly turned on
scheduled daily snapshots with five-day retention by default, which the entry
above did not know about and was therefore more pessimistic than the truth.
That is a real safety net and it was free. It is still not a backup anybody
here controls — the retention is Fly's, the restore path is Fly's, and neither
has been tested — so the trade stands. But "one copy and no recovery" was
wrong, and a decision record that overstates a risk gets trusted exactly as
much as one that understates it.

---

## 29. ISBNs are validated arithmetically, with an explicit override

**Decision.** An entry's check digit is verified, ISBN-10 is converted to
ISBN-13, and the ISBN-13 form is what gets stored. An entry that fails is
refused with the reason — and offered a second, explicit "add it anyway" that
stores the text exactly as typed.

**Why validate.** A wrong ISBN matches nothing, and on the results page
"nothing is listed" and "you mistyped it" are the same screen. Without a check
digit the tool would be quietly useless for that book and give no hint why. The
check catches every single-digit error, which is the overwhelming majority of
typing mistakes.

**What it misses, stated rather than implied.** ISBN-13's weights alternate 1
and 3, so swapping two adjacent digits shifts the total by twice their
difference — and when that difference is exactly 5, the total moves by 10 and
the check digit does not notice. Every other adjacent transposition is caught.
This is a guard, not a guarantee, and there is a test naming the two cases it
misses for one real ISBN so the claim stays honest.

**What this deliberately does not do.** It does not ask any catalogue whether
a book with that number exists. The override was requested to cover the case
where "the public source we use is missing a legitimate ISBN" — but that case
needs a source, and M1 has none: Open Library resolution is the hard part this
milestone defers on purpose (decision 26). Arithmetic validation cannot be
missing a book, because it never consults a list of them.

**So what is the override for today?** Books that never had an ISBN. The brief
names pre-1970 titles as a real category and manual entry as their escape
hatch, and a check digit cannot tell "this book predates ISBNs" from "you
mistyped". Only the person holding the book knows. The override is a second
click rather than a checkbox on the form, so it is a decision taken about one
specific entry and never the default.

**When resolution lands** the override gains its second meaning — a valid ISBN
the catalogue has never heard of — without the interface changing. That is the
version originally asked for, and it arrives with the source that makes it
possible.

**Cost.** An overridden row holds text in a column named `isbn`, and nothing
downstream may assume that column parses. `wantlist.Book` says so where someone
would look. The alternative — a column recording whether the value is really an
ISBN — was rejected as more schema than a single-user list needs before it has
been used once.

---

## 30. Listings are fetched per page view, until the poll exists

**Decision.** Opening a book searches eBay then and there. Nothing about a
listing is stored.

**Alternatives.** Storing listings from the start, and reading the store.

**Why this is fine now.** A handful of page views a day against 5,000 calls is
nothing, and every listing on screen is certainly current — no cache, so no
stale cache. Building the store first would have meant designing how listings
are keyed, deduplicated across relists and expired before ever having seen a
real response, which is the mistake decision 26 avoids for editions and this
avoids for listings.

**Why it cannot survive.** The brief's whole point is that the tool checks when
I am not looking. A poll that runs daily across a want-list of dozens, storing
what it finds, is what makes the digest possible — and the moment listings are
polled, the page must read what the poll stored rather than search again. Two
paths to the same data, one of them live, is how "new since you last looked"
stops meaning anything.

**The trigger, so it is a plan and not a hope.** The first slice that writes a
listing to the database replaces this in the same change. Not afterwards: a
page that still searches live while a poll is filling a table is a page that
disagrees with the digest it is supposed to match.

**Amended, 2026-09-22.** "Replaces" was too strong a rule drawn from a correct
reason. What must be true is that everything the page displays comes from the
store — not that nothing may ever fetch on demand. A refresh that writes to the
same store is the same path triggered by hand, and it creates no second version
of the truth. So live-on-demand survives, and the milestone gains a memory
rather than trading freshness for one. The rule is: one path in, one path out,
and the page reads the store.

**What this already provides for.** The page states when it fetched. That line
exists so there is somewhere for "last checked on Tuesday" to go, and a page
with nowhere to say so is a page that quietly implies data is fresher than it
is.

---

## 31. The whole path is written down, and reviewed at every milestone close

**Decision.** `docs/milestones.md` carries every milestone that can be named,
not only the current one. Each says why it sits where it does. At the close of
every milestone the remaining ones are reviewed — reordered, merged, split or
dropped — against what the finished one taught.

**This reverses the original rule**, which was that only the current milestone
was written down because later ones are guesses and a roadmap of guesses goes
stale. That reasoning was not wrong about the failure mode. It was wrong about
the remedy.

**Why the new version is better.** Not writing the path down avoids stale
guesses by having no guesses to go stale — and pays for it by having no path at
all. Nothing could be argued with, because nothing was written; the order lived
only in whoever was asked next. Scheduling a review addresses the same failure
directly: the guesses are written, so they can be attacked, and there is a fixed
moment when attacking them is the job.

It also turns finishing a milestone into a decision point rather than a
handover. "What did this teach us, and what does it change about what comes
next" is a question that gets asked at the close or never.

**What is kept from the old rule.** Only the current milestone has its slices
written as issues. A future milestone is one paragraph, because the slices for
work that has not started are the part that really is guesswork.

**Amended, 2026-09-22, on two points the first reorder exposed.**

*Numbering.* The file was ordered by what happens next while the numbers stayed
put, so the second milestone in line was called M6. A number that does not match
its position is a lie with a label on, so reordering now renumbers. Delivered
milestones keep their number permanently and numbers are never reused, and
everywhere outside `milestones.md` a milestone is referred to by name — names
do not move, so a reorder rewrites nothing.

*Delivered milestones stay in the file.* Decision 19 says status never goes in
a file, and this is the narrow exception, so the reason matters. That rule
exists to stop the file tracking things that change constantly and update
themselves elsewhere — issue state, progress bars. A milestone closing is not
that: it happens rarely, it is a deliberate ceremony that already has a ritual
attached, and moving the entry to *Delivered* is part of that ritual rather
than a second copy of something GitHub maintains.

What makes it worth the exception is the archive's actual content: not that a
milestone finished, but **what it taught**. That is the output of the close
review and there is nowhere else it would live. A path you cannot see the
beginning of is also only half a path.

**Cost.** A written order acquires authority it has not earned. Six milestones
in a file look considered whether or not they are, and the fourth one was
written before the second one had started. The mitigation is in the document
rather than in a habit: each entry states the argument for its position, and
*The right book* carries the argument *against* its own position because that
one looks most likely to win.

---

## 32. Editions are matched by eBay's product id, not by the ISBN as a string

**Decision.** The unit a search targets is eBay's `epid` — its own product
identifier — rather than the ISBN text. The ISBN is how an edition is first
found; the `epid` is how its listings are found afterwards, and the mapping
between them is worth storing.

**Why, measured rather than assumed.** Searching for an ISBN only finds
listings whose seller typed it. Plenty do not. Three books, limit 50, against
production:

| Book | `q=ISBN` | carry an `epid` | `epid=` search | found *only* by epid |
|---|---|---|---|---|
| Web of Deceit | 6 | 6 | 5 | 0 |
| Pride and Prejudice (Penguin) | 50 | 43 | 50 | **9** |
| The Da Vinci Code (Anchor) | 50 | 49 | 50 | **2** |

Nearly every used-book listing is matched to eBay's catalogue, and searching
the catalogue id finds copies the ISBN text misses. On a capped result set the
miss was up to 18%, and those are real copies of exactly the edition wanted.

**What a title-and-author search is, and is not.** It finds many editions and
reaches any particular one badly. For *Pride and Prejudice* one result in fifty
shared the target edition's `epid`; for *The Da Vinci Code*, none did. It is a
tool for discovering which editions exist, not for finding copies of one.

**What this does not settle.** A work has many editions and covering them all
still looks like one search each — slow on a page, and wasteful against a
budget that was chosen for headroom. Whether the answer is caching the edition
set, covering only editions that actually have inventory, or a title-level
search filtered by known product ids, is open. It is the first thing *The right
book* has to settle, and it should settle it the way this entry was written: by
measuring.

**Cost.** A second identifier to hold and keep fresh, for a catalogue that is
eBay's and could change under us. An `epid` also says nothing outside eBay, so
a second marketplace needs its own answer to the same question.

**Corrected, 2026-09-22.** The third row was first published as *The Girl with
the Dragon Tattoo*. ISBN 9780307474278 is *The Da Vinci Code*. The number was
picked as "a recent paperback", given a title from memory, and never checked
against a catalogue — so every measurement taken from it was sound and every
label on it was wrong.

It surfaced only because a reference link to the real edition was wanted for
something else, and the link resolved to a different book. Nothing in the
process would otherwise have caught it: the ISBN is valid, its check digit
passes, eBay returned fifty real listings for it, and the numbers in this table
are genuine — they simply describe a different novel.

**What follows from that, beyond the correction.** A valid ISBN that names the
wrong book is invisible to every check this project has. The entry point in
*The right book* must therefore confirm what an ISBN resolves to and show it
back — a book added by number should display the title the catalogue returns,
so a mistyped or misremembered ISBN is caught by the person who typed it rather
than by a coincidence a week later.

**Superseded in part, 2026-09-23.** Decision 33 measured this against hand
labels and `epid` did not survive as *the* unit. It over-merges: distinct
editions of *Crash* share one `epid`, so a match is evidence, not proof. It is
now one of three identifier signals rather than the identifier.

---

## 33. A listing is graded, not filtered — and the grade comes from identifiers, never from text alone

**Decision.** Search wide and cheap on title and author, then grade every
listing into confidence tiers using identifiers. Nothing is thrown away for
being uncertain; it is labelled uncertain and shown lower down. Three signals
produce a **certain** grade, in this order of trust:

1. The seller's declared ISBN is the one on the want-list entry.
2. The seller's declared ISBN belongs to this work — either it is in the
   cached ISBN set for the work, or Open Library resolves it to this title
   and a shared author.
3. The listing's `epid` matches the edition's.

Anything tied to the book only by its listing text is **possible**. In
collectible mode a listing whose `epid` matches but whose declared ISBN names a
*different* edition of the same work is **probable** — the two identifiers
disagree and neither wins.

**Measured against 227 hand labels** across *Pride and Prejudice*, *Crash* and
*Stoner*, classified twice each: is this the book, and is this that edition.

| Reading mode — any edition | listings | certain | possible | recall |
|---|---|---|---|---|
| Crash | 53 | 27 at 96% | 26 at 73% | 100% |
| Stoner | 65 | 51 at 100% | 11 at 100% | 100% |

| Collectible mode — this edition | listings | certain | possible | recall |
|---|---|---|---|---|
| Crash | 53 | 6 at 67% | 25 at 8% | 100% |
| Stoner | 65 | 26 at 96% | 7 at 14% | 100% |

Nothing true was hidden in either mode on either book. The tiers carry the
uncertainty instead.

**Why grading rather than filtering.** Every rule measured was good at one
question and bad at the other. Listing text finds the book at 92–94% precision
and cannot find the edition at all — 12% on *Crash*. `epid` finds the edition
at 92% and misses two thirds of the copies of the book. They fail in opposite
directions, which makes them layers rather than candidates.

**Neither catalogue has an identity key, and they fail in opposite
directions.** eBay's `epid` **over-merges** — several *Crash* editions sit
behind one id, which is what drops its edition precision to 60% on that book.
Open Library's work id **over-splits** — *Crash* is filed under five separate
work ids and *Stoner* under five, and its author keys split too, with John
Williams appearing as both `OL328495A` and `OL587370A` on editions of the same
work. A first version of this rule tested the declared ISBN against the target
work id and threw away 21 of the 45 true *Crash* listings. Resolving the ISBN
to a **title and author** instead took recall to 100%.

**What Open Library is for, then.** Not matching — resolving. It turns a
seller-declared ISBN into a catalogued title, author, publisher, format and
year. Three *Stoner* listings are the Library of America omnibus, *Butcher's
Crossing / Stoner / Augustus*; their titles contain "Stoner", their author is
John Williams, and every eBay signal admits them. Only resolving the declared
ISBN excludes them. eBay has no equivalent signal.

The division that holds: **Open Library describes editions, eBay describes
copies.** Format, publisher, year and page count are edition facts. Condition,
price, signed, inscribed and the photographs are copy facts that exist only on
eBay, and collectible mode lives almost entirely on that side.

**Open Library is not the better source for edition attributes**, which was
worth testing because it looked likely. Its `physical_format` is present on
43–69% of the editions of our three works against eBay's 74%, its values are
uncontrolled — `paperback`, `Paperback`, `Trade Paperback`, `mass market
paperback`, `Brossura`, `gebundene Ausgabe` — and it does not know the target
*Crash* edition is a paperback at all. It is cleaner on publisher and year, and
resolves 31 of 36 declared ISBNs; the five misses are all non-English. Show its
values where it has them, fall back to eBay's aspects, and mark which is which:
Open Library's "Paperback" describes the edition, eBay's describes the object
in the photograph, and the seller can be wrong.

**Ordering follows from the mode, and the two are not the same.**

*Reading* sorts the certain tier by landed cost and collapses **possible**
beneath it. The top ten by price were correct for both books. The errors sink
on their own: the one thing the identifier tier cannot catch — a Gagosian
Gallery exhibition catalogue titled *Crash*, credited to Ballard, with a valid
ISBN — sorts last of 27 at $399.95, because everything we confuse with a cheap
paperback is expensive. That is luck worth taking, not a principle to lean on.

*Collectible* groups by tier first and sorts by price or newness only **within**
a tier. Price-ascending stops protecting anything here: the cheapest certain
*Crash* listing is wrong, and a genuine NYRB first printing sits in **possible**
at $134.99 below three wrong cheaper ones. Inventory is scarce — 6 right copies
in 53 listings — so nothing can be hidden, and the tier label is what makes the
list readable.

**eBay's category is informational and never a rule.** The categories are
sprawling and overlapping, they are localised in the response — `Bücher`,
`Libri antichi e da collezione` — and `Antiquarian & Collectible` is where
collectible inventory actually lives. An early version of this rule excluded on
category and lost seven true listings. Display it; never include or exclude on
it.

**Cost.** The declared ISBN comes from `localizedAspects`, which needs a
`getItem` call per listing — the search response does not carry it. That is
affordable only because an item's aspects never change, so it is one call per
listing ever and the steady state is new listings only, against 5,000 calls a
day. Open Library costs one editions call per work per month plus one lookup
per newly seen ISBN, cached permanently, since an ISBN's identity does not
change.

**What stays broken, and is not a bug to fix later.**

- Three listings declare the exact target ISBN, with eBay's catalogue agreeing
  on format and year, that were labelled *not* that edition. By every
  machine-readable signal they are it. The seller declares one thing and
  photographs another, and no data source reaches that.
- A human cannot reliably tell a hardcover from a paperback in listing
  photographs when the two share a cover. That was established the expensive
  way: 86 labels on *The Girl with the Dragon Tattoo* were discarded because
  its hardcover and paperback carry the same artwork. If a person holding the
  photographs cannot decide, the app must not claim to — collectible mode has
  to surface the ambiguity rather than resolve it.
- Errors in the **possible** tier are almost all the same error: another book
  by the same author whose listing name mentions the target. Sellers list an
  author's famous titles, so *Concrete Island*, *The Atrocity Exhibition* and
  *The Disaster Area* all match "crash" and "ballard". None carries a declared
  ISBN, which is exactly why it falls to the text tier.

> **Corrected, 2026-09-23: a title is not a book.** The rule compared titles
> alone. The author was dropped twice — in S7 and again in S10 — each time on
> a measurement saying it changed no answers, taken across three books whose
> titles are effectively unique in the catalogue. **The sample could not show
> the failure**, which is the same methodological error the corpus caught over
> the text threshold, made again.
>
> In production, three different books called *Breaking and Entering* graded
> certain against each other: Joy Williams's novel, Don Gillmor's novel, and
> Philip Carlson's manual for working actors. Open Library confirmed each
> number was something by that name, because it was. Decision 7 records this
> exact gap and calls it "never seen in the sample" — it has now been seen, by
> the first book added with a common title.
>
> The author eBay's aspects already carry now rejects a match, and only ever
> rejects: two names agreeing proves nothing, since every listing for a famous
> title names its famous author. It rejects only when the listing's own name
> also fails to mention the author, because requiring less hid a real copy of
> *Stoner* whose seller had typed the translator into that field, and a copy
> of *Crash* whose seller had typed "NA".
>
> Scored against the corpus with the declared author added to all 227 rows:
> every tier unchanged, recall still 100% on both hunts on all three books.
> The change costs nothing measurable and fixes what was observed.
>
> **The worse half was in enrichment, not here.** A pass learning which
> numbers belong to a book used the same title-only rule, so Gillmor's ISBN
> became an *edition* of Joy Williams's book — and a known edition makes every
> future listing declaring it certain ahead of any other evidence. That check
> is now the strictest in the app, and deliberately stricter than this one: a
> wrong edition contaminates everything after it, while a rejected right one
> merely has to be recognised the ordinary way.

**An ISBN that does not resolve is absence of evidence, not evidence of
absence.** A declared ISBN that Open Library resolves to a *different* book
excludes the listing. One it cannot resolve at all must not — it falls through
to the text tier like a listing that declared nothing. The five unresolvable
ISBNs in the sample are the German, Italian, Catalan, Chinese and Korean
editions, and all five are genuinely the book. Treating an Open Library miss as
a rejection would systematically hide non-English editions, which is the one
population it is weakest on.

**One grader, not two.** Reading and collectible are the same function with two
parameters: which ISBNs count as the target — every ISBN of the work, or the
single ISBN of one edition — and how weak a text match is worth showing.

> **Corrected, 2026-09-23: one parameter, not two.** The text threshold was
> never real. It was asserted from a measurement that could not see it:
> *Pride and Prejudice* was labelled before aspects were fetched, so it had no
> declared numbers and was never scored on the collectible hunt at all. With
> the labels committed as a test corpus it was, and the stricter floor hid two
> genuine matches — both listings named as plainly as "Pride and Prejudice",
> with no author, no product id and no number. Loosening it hid nothing and
> raised that book's *possible*-tier precision from 10% to 12%, because the
> listings it admits are mostly ones already shown.
>
> So the hunts differ only in which numbers count as the target. This is the
> first thing the committed corpus caught that the original measurement could
> not, which is most of the argument for committing it.
Verified against the labels: the parameterised grader reproduces the reading
numbers exactly and leaves the collectible *certain* tier unchanged, widening
only its *possible* tier by two listings. What genuinely differs between the two
hunts is not the pipeline but the surface: what a want-list entry points at, how
the results are ordered, and what zero results means. Reading mode's ordering
was measured; collectible mode's was not, and should not be assumed from it.

**What this rules out.** A per-edition search. Open Library returns 4,042
editions of *Pride and Prejudice* against 21 for *Crash*, so one search per
edition is not expensive, it is incoherent. The edition set is a matching
resource, not a search plan.

---

## 34. A want-list entry names a work and says which hunt it is on

**Decision.** Three tables where there was one. A **work** is the book in the
abstract, an **edition** is one printing of it, and an **entry** is a row on
the want-list pointing at one or the other depending on the hunt: a reader
takes any edition, a collector wants one. Migration 003.

**Alternatives.** Keeping one row per ISBN and grouping in the application.
Two separate features, reader and collector, with their own tables. Modelling
only the reader case now and adding the collector later.

**Why now, and why both hunts at once.** Decision 33 measured that the two
hunts are one pipeline with two parameters — the same search, the same
resolution, the same grading — differing only in what an entry points at and
how results are shown. Building only the reader case would mean migrating live
rows from ISBN to work now, and from work to work-or-edition again later. The
`hunt` column is the single thing that cannot be added afterwards without a
second migration over real data. Everything else the collector path needs is
deferred, and deliberately: its surface waits on its own labelling exercise,
because decision 33 measured it on six listings and first-edition points — a
number line, a price on a dust jacket — live in photographs rather than in any
catalogue.

That is the rule this project now uses for building ahead: **pay now only for
what a later change would have to migrate.** It is why `hunt` is here and why
the listing-aspects table is not, though S10 will need it — a new table costs
nothing to add later, a column on live rows costs a migration.

**A collector entry points at an edition row, not at an ISBN.** This looked
like over-modelling until the obvious case: a 1965 first edition of *Stoner*
predates ISBNs entirely, and pre-1970 books are exactly what a collector
wants. `edition.isbn` is therefore nullable, and SQLite's rule that NULLs do
not collide in a UNIQUE index gives one row per real number and any quantity of
editions that never had one.

**Editions exist only for printings seen in the wild.** Decision 7 as amended
measured that about 80% of a downloaded edition list is never offered for sale.
This table fills from listings instead.

**`work.openlibrary_work_id` is a reference and never identity**, and is
deliberately not UNIQUE. Decision 33: *Crash* is filed under five Open Library
works, *Stoner* under five, and a title search returns two separate *Pride and
Prejudice* works. Anything that joined on it would be quietly wrong.

**`work.title` is nullable, and a book added with only a number has no title
until something learns one.** Writing the ISBN into the title field would have
kept every work searchable by construction, which was tempting, and it would
have been a lie stored in a column named `title` — one that leaks straight onto
the page as a thirteen-digit heading.

The invariant that actually matters is that every **entry** is searchable, not
every work, and an entry always knows what it was added with. So the search
falls back to that, the screen says the title is unknown rather than inventing
one, and enrichment fills it in.

**Ids are preserved through the migration.** The want-list links to
`/book/{id}`, and renumbering would break every bookmark for every book on the
list.

**Cost.** Three tables and a join where there was one table and a SELECT, on a
list of dozens of books. Two partial unique indexes doing work a single UNIQUE
column used to do, because wanting both a reading copy and a particular
printing of the same book is not a duplicate. And a `collector` value that
nothing reads, which decision 26 rightly warned is how a column quietly stops
meaning what its name says — accepted here only because the alternative is a
second migration over live data, and recorded so the warning is not forgotten.

---

## 35. A book is identified before it goes on the list

**Decision.** Adding a book makes one Open Library request. By title, it
searches and the person picks from a short list. By ISBN, it looks the number
up and puts **the title the catalogue returned** on the list, not the one that
was typed.

**Alternatives.** Adding first and resolving in the background, so nothing
waits. Requiring a confirmation click on the ISBN path. Keeping a typed title
when one was given.

**Why the catalogue's title wins.** This is decision 32's correction, built.
A valid ISBN that names the wrong book passes every check this project has —
the check digit is fine, eBay returns fifty real listings, and nothing looks
wrong. Keeping the typed title would hide the single signal that reveals it:
a number believed to be one book coming back as another. Verified against the
number that caused it: `9780307474278` now reads back as *The Da Vinci Code*
before the entry is created.

**Why it happens inline rather than in the background.** One request, about a
second. The ten to fifteen a book eventually costs are for the numbers sellers
declare in its *listings*, and those still cannot run while someone waits. A
read-back that arrives a minute later is not a read-back.

**Timed, because the brief set a bar.** Adding a book must take under thirty
seconds. Title search 0.9s, ISBN lookup 1.9s including the client's own pause.
Picking from five candidates is more steps than typing thirteen digits and
still nowhere near the bar.

**An ISBN Open Library does not hold is offered, not refused.** It is usually
a mistyped digit and occasionally a real book the catalogue lacks — every
unresolvable number in S6's sample was a non-English edition of the right book.
The person holding it decides, through the same override decision 29 already
built for a failed check digit. Overriding asks Open Library nothing: the
decision has been made, and asking again would be noise on a service that
asks for low volume.

**`resolved_at` is separate from `enriched_at`.** Two different facts: has this
book been identified, and have the numbers in its listings been resolved. One
is a single lookup at add time; the other is ten to fifteen in the background.
Collapsed into one column, a book we just failed to find would be
indistinguishable from one nobody has looked at, and those read as different
news — the first is usually a typo and the reader's to act on. Inferring it
from whether `openlibrary_work_id` is set was the alternative and is what
decision 33 forbids: that column is a reference, never a flag.

**A picked candidate is trusted from the form it was rendered into** rather
than fetched again. That saves a second request, and is safe only because
there is one user and no authentication (decision 25). It is the kind of thing
that stops being safe quietly, so it is written here rather than assumed.

**Cost.** Adding a book now depends on a third party being reachable. When it
is not, the page says so and offers to add anyway — so the dependency degrades
rather than blocks, but a book added during an outage carries no title until
something looks again.

---

## 36. A test that reaches the network fails loudly

**Decision.** `tests/conftest.py` replaces httpx's real transport for every
test not marked `network`. An accidental request raises rather than succeeding.

**Why, and it is not hypothetical.** Adding the Open Library client to the
want-list router gave it a real default. The want-list tests did not pass a
stub. The suite began making live requests to a non-profit on every run, and
**nothing failed** — the only symptom was the suite taking four times as long,
which is not something anyone watches.

Decision 7 calls low volume a constraint rather than a preference, and CI
running on every push is exactly the volume that gets an address blocked. A
mistake that cannot be seen is worse than one that breaks the build.

**Why at the transport and not the client.** The two kinds of faking already
in use — `httpx.MockTransport` and the test client's ASGI transport — are
different classes, so patching `HTTPTransport.handle_request` leaves them
working and stops only a socket that would really open.

**Cost.** One more thing in the way when a test genuinely wants the network,
which is what `@pytest.mark.network` already exists to say (decision 15).

---

## 37. The labelled listings live in the repository

**Decision.** The 227 hand-classified eBay listings from S6 are committed to
`tests/data/labelled_listings.json`, and `tests/test_matching.py` asserts the
numbers they produce.

**Alternatives.** Keeping them in a scratch directory, as they were. Keeping
only the summary numbers in decision 33. Regenerating them on demand.

**Why.** Decision 33's entire argument is a set of measurements, and until now
those lived in a prose record and in one session's memory. A change that
quietly degraded matching would have shipped: nothing in the project could
tell that the rule still did what the rule was chosen for.

They are also irreplaceable in a way that is easy to underrate. Regenerating
them means several hundred eBay calls and, more to the point, a person sitting
down and judging 227 listings twice each — and the judgement is the data.
Leaving that in a temporary directory was one `rm` from gone.

**What is asserted, and what is deliberately not.** The tests pin the *claims*,
with thresholds a little below what the rule achieves: nothing true is ever
hidden, the certain tier can be trusted, the certain tier is large enough to
be worth reading, and identifiers beat text on the edition question. Pinning
exact percentages would fail on every harmless change and get loosened until
it meant nothing.

*Crash* is excluded from the collectible precision test on purpose. Six
right-edition listings is not a sample, and decision 33 already records that
its `epid` over-merges. Pinning a number to it would be pinning noise.

**It paid for itself immediately.** The first run disproved decision 33's claim
that the two hunts differ in two parameters. See the correction there.

**Cost.** 54 KB in the repository, and a corpus that ages: it is a snapshot of
what was for sale on one day in September 2026. It measures whether the rule
still behaves as it did, not whether it works on today's inventory. When the
rule changes on purpose, the expectations have to be re-read rather than
adjusted until green.

---

## 38. Open Library's data dump is the right answer for a second user, and the wrong one for the first

**Decision.** Keep asking Open Library about numbers one at a time, and cache
every answer. Take the monthly editions dump instead the moment this app
serves anybody but its author.

**The numbers for one user.** Measured from the 36 lookups S6 actually made:

| | |
|---|---|
| Average `/isbn/` response | 1,332 bytes |
| Editions dump | 9.2 GB, monthly |
| One dump, in lookups' worth of bytes | **7.4 million** |

A twenty-book want-list costs about 240 lookups **ever** — 312 KB — and then
effectively nothing, because a number's identity does not change and the
answer is written down. Taking the dump to avoid that would replace 312 KB
with 9.2 GB, or 110 GB a year refreshed monthly. Open Library asks people not
to use the API for bulk because it affects their ability to serve patrons;
for a single user, downloading the dump *is* the bulk they are asking us to
avoid, wearing the right hat.

**Why that reverses with a second user, and it is not about bytes.** The
published limit is **1 request per second per IP** (3 if identified). Per IP,
not per user. So every cache miss for every user queues behind the same
one-per-second door, and the ceiling does not move no matter how well the
cache works. Open Library's own guidance draws the same line: the API is for
"real-time, low-volume, high-value use" and is "not intended as a backend."
One person looking a number up now and then is not a backend. A service is,
whatever it weighs.

Byte counts are the right measure for one user and the wrong one for a
service. This entry originally argued the first case and treated it as
settling the second, which it does not.

**The trigger, so it is a condition rather than a judgement.** The second
person to use this app. Not a request count, not a traffic threshold — the
moment a lookup happens on behalf of somebody who is not the author, the
API is being used as a backend.

**What changes when it fires.**

- The notebook stops being a cache of answers and becomes a local catalogue.
- The API becomes the fallback for genuine misses only: editions catalogued
  since the last dump, which is a small and shrinking tail.
- The monthly refresh starts being worth its cost, because it is amortised
  across every user rather than paid by one.
- **Decision 7's dropped edition pre-fetch becomes viable again.** S7 measured
  that fetching every edition of a work through the API is about 80% waste;
  from a local dump it is free, and it is what the collector path wants.

**Cost when it fires.** 9.2 GB downloaded and projected monthly, somewhere
that is not a laptop — there isn't one (CLAUDE.md). Storage for the
projection, against a volume currently sized 1 GB and a budget of $2–3 a
month. Neither is a reason not to; both are reasons it is a slice of its own
rather than a detail.

---

## 39. What Open Library actually limits, and three controls for it

**Decision.** Pace requests process-wide at one every 1.5 seconds, record every
one, and refuse past 500 in a rolling day.

**What they publish**, which nothing in this project had checked until now:

| | |
|---|---|
| Unidentified requests | **1 per second** |
| Identified — User-Agent naming the app and a contact address | **3 per second** |
| Covers endpoint | **100 per IP per 5 minutes**, then 403 |

They describe the intended use as "real-time, low-volume, high-value", say the
API is "not intended as a backend", and that violations "may result in
aggressive rate limiting or blocking".

**1.5 seconds is now a number with a reason.** It was picked by feel in S7 and
happened to be right: 0.67 requests a second is about a third under the lower
published figure, which is what CLAUDE.md means by staying well inside a limit
rather than close to it.

**The pace is per process, not per client object, because the limit is per
address.** Open Library does not care how many clients this process has built;
instance state cannot enforce an address-level rule. This is not theoretical —
S9 shipped a web layer that built a client per request, so each one forgot when
the last had spoken and the pacing silently never happened. Sharing one
instance fixed the symptom. Moving the timestamp to module level fixes the
cause, and the next caller cannot opt out by constructing its own.

**Everything is counted, because nothing could answer "how much have we
used?"** Not the app, not its author, not anyone reading the code. One row per
request, recorded after the pause so the times read as when requests actually
went out rather than when they were decided on.

**The ceiling is a bound on our own bugs, and is not compliance.** They publish
no daily figure, so 500 is ours to justify. Adding a book costs one request;
resolving the numbers in a book's listings costs ten to fifteen. A busy,
entirely legitimate day — ten books added and enriched — is about 160. This is
roughly three times that, and about a fifth of the 2,400 an unattended loop
would manage at this pace. The failure it defends against is not a person
adding books quickly. It is a loop that should have read the cache and didn't.

**Refusing is not the same as being unavailable**, and they are different
exception types. One means they could not answer; the other means we declined
to ask. A caller retrying the second on a timer would be doing precisely what
the ceiling exists to stop.

**The budget is required, with no default.** A default would be a way to opt
out of being counted without noticing, which is exactly how the test suite
quietly started calling Open Library for real (decision 36).

**What this does not cover.** Two machines would have two paces and two
ceilings; the deploy runs `scale count 1`, so today there is one. If that ever
changes, both controls need to move behind something shared.

---

## 40. A page view spends one search and nothing else

**Decision.** Opening a book runs at most one eBay search, and only when that
book has never been searched for or the reader asks to look again. It never
fetches a listing's details. Everything else it shows was written down
earlier.

**Measured, which is what makes this a constraint rather than a preference.**

| | |
|---|---|
| One eBay search | ~1.8s |
| One per-listing detail call | ~0.51s |
| Fifty listings' details | **25.5s** |

The bar is a couple of seconds and the search alone spends most of it. There
is no bounded number of detail calls that fits — even two is over. So the
question S11 left open, whether to fetch details for every result or only the
ones shown, has no version that belongs on a page at all. It belongs in the
background.

**What that costs, honestly.** The first view of a new book grades everything
on its listing name alone, so almost nothing reaches *certain*. Verified on a
real book: twelve copies of *Stoner*, first view nine seconds too slow to
fetch and therefore **0 matches, 12 that might be**. After the same twelve
were examined — six distinct numbers, seven Open Library requests — the same
page read **9 matches, 3 that might be**.

The page says so rather than hiding it. A spinner would claim the list is
still arriving; it is not, it is arriving *less certain than it will be*, and
those are different promises.

**One sentence on the page, the reason on hover.** The page says "Still
digging through the shelves." Why it is slow — that the public catalogues are
asked slowly on purpose, because they are free and we would like them to stay
that way — sits in a `title`. Only the reason may live there: `title` does not
survive a touchscreen and is not reliably read out, so nothing a reader needs
can be hidden behind it.

**Copies are replaced, not merged.** A copy that has stopped appearing has
been sold or withdrawn, and keeping it would turn the store into a list of
things that used to be buyable.

**Second views cost nothing.** Measured at 11ms against 2.6s for the first.

**Cost.** The store can be stale, and a reader cannot tell how stale without
the timestamp — which is why the page carries one and always has. "Look
again" is the manual version of the poll that *Always current* automates.

---

## 41. Examining a book happens after the page, not on a clock

**Decision.** When a book page runs a search and finds copies nobody has
examined, it schedules a background pass and returns. The pass asks eBay what
each seller declared, asks Open Library what those numbers are, and records
both. Nothing waits for it.

**Why not on a clock.** Decision 8 chose in-process daily scheduling, and this
is not that shape. The work exists because somebody just opened a book; a
daily job would mean a new book stayed uncertain until tomorrow, which is the
one moment the reader is actually looking.

**Why not during the request.** Decision 40 measured it: fifty copies is
twenty-five seconds of eBay alone, against a page that owes an answer in two.

**Resumable by construction, not by design.** Every answer is written down the
moment it arrives, so a pass that dies halfway — a restart, an outage, a
ceiling — keeps what it learned and the next one continues. Nothing here is
transactional because nothing here is a transaction. That is also what makes
it safe to trigger from a page view: a second pass on the same book would ask
nothing new, and an in-process guard stops it anyway.

**The ceiling stops it and is never retried.** Decision 39: a caller that
retries `BudgetExhausted` on a timer is the exact failure the ceiling exists
to prevent. An unfinished pass leaves `enriched_at` unset, so the want-list
keeps saying there is work outstanding, which is true.

**Measured, on a real book.** Ten copies of *Crash*: the page answered in
under three seconds with nothing certain, the pass took thirteen seconds — ten
eBay calls and six Open Library ones — and the same page then read six
matches. The want-list said "still digging" throughout and stopped when it
stopped.

**The tag means work outstanding, not work possible.** A book nobody has
opened has no copies, so there is nothing to dig through and the list says
nothing. Advertising work that has not started would be the same lie as a
spinner.

**Cost.** A pass dies with the machine, and nothing retries it on a schedule —
it resumes the next time that book is opened. For a want-list of a few books
read by one person that is fine, and it stops being fine the moment anything
is expected to be current without somebody looking. That is *Always current*'s
problem, and this is the piece it will schedule.
