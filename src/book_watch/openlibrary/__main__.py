"""See what Open Library says: `uv run python -m book_watch.openlibrary --isbn ...`.

Makes exactly one request. Needs no configuration and no database — it counts
that request against a budget it keeps in memory and throws away — so it works
on a fresh checkout with nothing set up.

That budget therefore resets on every run, which is honest for a probe that
makes one request and exits. Anything long-running must be given a budget
backed by the real database, or the ceiling means nothing.

    uv run python -m book_watch.openlibrary --title stoner --author "john williams"
    uv run python -m book_watch.openlibrary --isbn 9781590171998
"""

from __future__ import annotations

import argparse
import sys

from book_watch import db
from book_watch.openlibrary.budget import CallBudget
from book_watch.openlibrary.client import OpenLibraryClient
from book_watch.openlibrary.errors import OpenLibraryUnavailable

EXIT_OK = 0
EXIT_UNAVAILABLE = 1
EXIT_MISUSE = 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="book_watch.openlibrary")
    parser.add_argument("--title", help="ask what book this is")
    parser.add_argument("--author", help="narrows a title search")
    parser.add_argument("--isbn", help="ask what this number is")
    args = parser.parse_args(argv)

    if bool(args.title) == bool(args.isbn):
        print("Give exactly one of --title or --isbn.", file=sys.stderr)
        return EXIT_MISUSE

    try:
        with OpenLibraryClient(CallBudget(_throwaway_database)) as client:
            if args.isbn:
                return _report_isbn(client, args.isbn)
            return _report_title(client, args.title, args.author)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_MISUSE
    except OpenLibraryUnavailable as exc:
        print(f"Could not reach Open Library: {exc}", file=sys.stderr)
        return EXIT_UNAVAILABLE


def _throwaway_database():
    """A migrated database in memory, discarded when the probe exits."""
    connection = db.connect(":memory:")
    db.migrate(connection)
    return connection


def _report_isbn(client: OpenLibraryClient, isbn: str) -> int:
    identity = client.identify_isbn(isbn)
    if identity is None:
        print(f"{isbn}: Open Library has no record of this number.")
        print("  That is an answer, not a failure — it does not mean the")
        print("  listing is the wrong book. See decision 33.")
        return EXIT_OK
    print(f"{identity.isbn}")
    print(f"  title      {identity.title}")
    print(f"  publisher  {identity.publisher or '—'}")
    print(f"  published  {identity.published or '—'}")
    print(f"  format     {identity.physical_format or '—'}")
    print(f"  work       {identity.work_id or '—'}  (a reference, not an identity)")
    return EXIT_OK


def _report_title(client: OpenLibraryClient, title: str, author: str | None) -> int:
    candidates = client.search_works(title, author)
    if not candidates:
        print("No candidates. Try fewer words, or add an author.")
        return EXIT_OK
    for candidate in candidates:
        authors = ", ".join(candidate.authors) or "—"
        editions = (
            "—" if candidate.edition_count is None else f"{candidate.edition_count}"
        )
        print(
            f"  {candidate.work_id:<18}{candidate.title[:38]:<40}"
            f"{authors[:22]:<24}{candidate.first_published or '—':>6}  "
            f"{editions} editions"
        )
    print()
    print("Edition counts are reported, never fetched. See decision 7.")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
