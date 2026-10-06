"""ASGI entry point: `uvicorn book_watch.web.main:app`.

Separate from `create_app` so importing the application factory in tests does
not require the environment to be configured.
"""

import logging

from book_watch import abebooks, alerts, daily, enrichment
from book_watch.openlibrary import CallBudget
from book_watch.web.app import create_app
from book_watch.web.searching import LazyBrowseSearch
from book_watch.web.wantlist import open_configured_database

# The app's own INFO lines, such as each morning's "Daily check: …" summary,
# reach Fly's log viewer. Uvicorn configures only its own loggers, so without
# this only warnings print. Uvicorn's loggers do not propagate, so nothing
# prints twice.
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
# httpx logs every request at INFO. The app's own lines are the ones to read.
logging.getLogger("httpx").setLevel(logging.WARNING)

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
