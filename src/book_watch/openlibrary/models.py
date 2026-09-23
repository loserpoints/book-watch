"""What Open Library gives back, reduced to what this app uses."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Candidate:
    """One possible answer to "what is this book?", for a person to choose from.

    `edition_count` is a count Open Library reports, not a list it sends. The
    distinction matters: *Pride and Prejudice* reports 4,042 editions in under
    a kilobyte of response, and this app never asks for them. Decision 7, as
    amended, has the measurement behind that.
    """

    work_id: str
    title: str
    authors: tuple[str, ...]
    first_published: int | None
    edition_count: int | None


@dataclass(frozen=True, slots=True)
class EditionIdentity:
    """What one ISBN *is*, according to Open Library.

    This reports; it never judges. Whether this identity means a listing is
    the book being watched is the grader's question, and keeping it out of
    here is what lets one lookup serve both a reader's hunt and a collector's.

    No author. The matching rule does not use one — removing the author check
    changed zero answers out of 227 hand-labelled listings — and Open Library
    holds authors only as internal references, so turning them into names
    would cost a request per author for something nothing reads. The gap this
    leaves is recorded in decision 7.

    `published` stays a string because Open Library's dates are not a date
    type: "2003", "April 1, 1994" and "xxxx" all appear. Parsing them into
    something tidier would mean inventing precision for two thirds of them.
    """

    isbn: str
    title: str
    work_id: str | None
    publisher: str | None
    published: str | None
    physical_format: str | None
