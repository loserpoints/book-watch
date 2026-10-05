"""American spelling throughout, as governance's writing style says (S55, #37).

British forms crept in once because new code matched old code. This fails on
the ones the project has used, so they can't come back that way.
"""

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent

#: British forms seen in this repository before S55, and their families.
BRITISH = re.compile(
    r"catalogue|colour|normalis|recognis|emphasis(?:e|ing)"
    r"|organis(?:e|ed|es|ing|ation)|optimis(?:e|ed|es|ing|ation)"
    r"|tokenis|behaviour|flavour|neighbour|favour|honour|judgement|cancelled"
    r"|labelling|labelled(?!by)|centre|licence|analys(?:e|ed|ing)\b",
    re.IGNORECASE,
)

#: What may keep a British form:
#: - recorded data from eBay and Open Library, which is theirs;
#: - vendored code;
#: - this file, which has to name them.
SKIPPED = ("tests/data/", "src/book_watch/web/static/htmx-", "tests/test_spelling.py")

#: A link to an issue or pull request carries its GitHub title, which is the
#: issue's own.
GITHUB_LINK = re.compile(
    r"\]\(https://github\.com/loserpoints/book-watch/(issues|pull)/"
)

PLACES = ("src", "tests", "docs", "scripts", ".claude", ".github")
SUFFIXES = {".py", ".md", ".html", ".css", ".js", ".toml", ".sql", ".sh", ".yml"}


def project_files():
    yield from (ROOT / name for name in ("README.md", "CONTRIBUTING.md", "CLAUDE.md"))
    yield ROOT / ".env.example"
    for place in PLACES:
        for path in sorted((ROOT / place).rglob("*")):
            if path.suffix in SUFFIXES and "__pycache__" not in path.parts:
                yield path


def test_no_british_spelling():
    found = []
    for path in project_files():
        name = path.relative_to(ROOT).as_posix()
        if name.startswith(SKIPPED):
            continue
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if GITHUB_LINK.search(line):
                continue
            found += [f"{name}:{number}: {m.group(0)}" for m in BRITISH.finditer(line)]

    assert not found, "British spelling:\n" + "\n".join(found)


def test_the_check_finds_a_british_form():
    assert BRITISH.search("normalise the colour")
    assert not BRITISH.search('aria-labelledby="x"')
    assert not BRITISH.search("optimistic programmers organize")
