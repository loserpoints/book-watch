"""ASGI entry point: `uvicorn book_watch.web.main:app`.

Separate from `create_app` so importing the application factory in tests does
not require the environment to be configured.
"""

from book_watch.web.ebay_deletion import create_app

app = create_app()
