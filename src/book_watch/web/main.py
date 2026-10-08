"""ASGI entry point: `uvicorn book_watch.web.main:app`.

Separate from `create_app` so importing the application factory in tests does
not require the environment to be configured.
"""

from book_watch import abebooks, alerts, daily, enrichment, monitoring
from book_watch.openlibrary import CallBudget
from book_watch.web.app import create_app
from book_watch.web.searching import LazyBrowseSearch
from book_watch.web.wantlist import open_configured_database

# Every line in Fly's log viewer in one format, uvicorn's included, with its
# per-request line replaced by the app's own `page` line
# (docs/rules/monitoring.md).
monitoring.configure()

app = create_app(read_abebooks=abebooks.read)

# The morning check. Here and not in `create_app`, so nothing that builds the
# app for a test starts a thread that searches eBay.
daily.start(
    open_configured_database,
    LazyBrowseSearch(),
    enrichment.configured(open_configured_database),
    CallBudget(open_configured_database).spent,
    notify=lambda: alerts.notify(open_configured_database),
    read_abebooks=abebooks.read,
)
