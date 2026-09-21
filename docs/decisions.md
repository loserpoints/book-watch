# Decision record

Short entries, one per decision that would be expensive to reverse or annoying
to re-argue. Each states what was chosen, what else was considered, and why.

*Last updated: 2026-09-21*

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

**Risk.** Developer account registration is sometimes rejected. The Phase 1
spike tests this before anything is built on top of it.

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
