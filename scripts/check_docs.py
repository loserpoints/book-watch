"""Check every document against the artifact table in docs/governance.md.

    uv run python scripts/check_docs.py

The rules are read from that table, so this file holds how to check and
governance holds what to check. Exit status 1 lists every violation.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import sys
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

GOVERNANCE = Path("docs/governance.md")
ISSUE_LINK = re.compile(
    r"^- \[[^\]]+\]\(https://github\.com/loserpoints/book-watch/(issues|pull)/\d+\)$"
)
JOB_LINK = re.compile(r"^- \[[^\]]+\]\((\.\./)*jobs\.md#j\d+[^)]*\)$")
#: A link to a document in this repository, from a learning to where it went.
DOC_LINK = re.compile(r"\]\((?!https?://)([^)#]+\.md)(#[^)]*)?\)")
REPO_API = "https://api.github.com/repos/loserpoints/book-watch/issues/{}"

#: Given an issue number, its label names.
Labels = Callable[[int], set[str]]
MILESTONE_DIR = re.compile(r"^m\d{2}-[a-z0-9-]+$")
SENTENCE_END = re.compile(r"[.!?](?=\s|$)")
#: "decision 33", "decisions 47, 52", "decisions.md entry 4". The decision
#: log is retired: a reason is stated where it applies, not pointed at. A
#: comment can wrap between the word and its number, so the gap may hold a
#: line break and the next line's comment marker.
GAP = r"(?:\s|#|--|\*|//)+"
DECISION_REF = re.compile(
    rf"\b[Dd]ecisions?(\.md)?(?:{GAP}entry|{GAP}entries)?{GAP}\d+"
)
#: Where decision references are looked for. This file and its tests hold the
#: pattern on purpose.
SOURCE_SUFFIXES = {".py", ".html", ".js", ".css", ".toml", ".sql", ".sh", ".yml"}
SOURCE_SUFFIXES |= {".md", ".json", ".example"}
NOT_SCANNED = {"scripts/check_docs.py", "tests/test_docs.py"}


@dataclass
class Section:
    name: str
    flags: set[str] = field(default_factory=set)
    #: For a repeating section, the `###` sections required under each one.
    children: list[Section] = field(default_factory=list)

    @property
    def pattern(self) -> re.Pattern[str]:
        text = re.escape(self.name)
        text = text.replace(re.escape("<n>"), r"\d+")
        text = text.replace(re.escape("<name>"), r".+")
        return re.compile(f"^{text}$")


@dataclass
class Artifact:
    name: str
    status: str
    paths: list[str]
    sections: list[Section]

    @property
    def repeating(self) -> bool:
        return len(self.sections) == 1 and bool(self.sections[0].children)


def parse_section(text: str) -> Section:
    match = re.fullmatch(r"(.+?)(?: \(([^)]*)\))?", text.strip())
    assert match, text
    flags = {flag.strip() for flag in (match.group(2) or "").split(",") if flag}
    return Section(match.group(1).strip(), flags)


def parse_sections(cell: str) -> list[Section]:
    cell = cell.strip()
    if not cell:
        return []
    # A repeating section: "J<n> · <name> [Job (sentence) · Success signal]".
    repeating = re.fullmatch(r"(.+?) \[(.+)\]", cell)
    if repeating:
        parent = parse_section(repeating.group(1))
        parent.children = [parse_section(p) for p in repeating.group(2).split(" · ")]
        return [parent]
    return [parse_section(part) for part in cell.split(" · ")]


def expand(path: str) -> list[str]:
    """`a/{b,c}.md` -> `a/b.md`, `a/c.md`."""
    braces = re.search(r"\{([^}]*)\}", path)
    if not braces:
        return [path]
    head, tail = path[: braces.start()], path[braces.end() :]
    return [
        p for option in braces.group(1).split(",") for p in expand(head + option + tail)
    ]


def load_artifacts(root: Path) -> list[Artifact]:
    artifacts = []
    for line in (root / GOVERNANCE).read_text().splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 4 or cells[1] not in ("active", "migrating", "retiring"):
            continue
        name, status, path, sections = cells
        artifacts.append(
            Artifact(name, status, expand(path.strip("`")), parse_sections(sections))
        )
    return artifacts


def headings(text: str, level: int) -> list[tuple[str, str]]:
    """(heading, body) pairs at one level, ignoring fenced code."""
    found: list[tuple[str, list[str]]] = []
    fenced = False
    marker = "#" * level + " "
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        if not fenced and line.startswith(marker):
            found.append((line[len(marker) :].strip(), []))
            continue
        if not fenced and re.match(rf"^#{{1,{level}}} ", line):
            found.append(("", []))  # a heading at a higher level ends the body
            continue
        if found:
            found[-1][1].append(line)
    return [(h, "\n".join(body).strip()) for h, body in found if h]


def check_body(
    where: str,
    section: Section,
    body: str,
    *,
    doc: Path | None = None,
    labels: Labels | None = None,
) -> list[str]:
    lines = [line for line in body.splitlines() if line.strip()]
    if not lines:
        if "may be empty" in section.flags:
            return []
        return [f"{where}: '{section.name}' is empty"]
    one_sentence = "\n\n" not in body and len(SENTENCE_END.findall(body)) == 1
    if "sentence" in section.flags and not one_sentence:
        return [f"{where}: '{section.name}' must be one sentence"]
    if "links" in section.flags:
        bad = [line for line in lines if not ISSUE_LINK.match(line)]
        if bad:
            return [
                f"{where}: '{section.name}' holds more than issue links: {bad[0]!r}"
            ]
    if "job links" in section.flags:
        bad = [line for line in lines if not JOB_LINK.match(line)]
        if bad:
            return [f"{where}: '{section.name}' holds more than job links: {bad[0]!r}"]
    if "slice links" in section.flags:
        return check_slices(where, section, lines, labels)
    if "routed" in section.flags:
        return check_routed(where, section, lines, doc)
    return []


def check_slices(
    where: str, section: Section, lines: list[str], labels: Labels | None
) -> list[str]:
    """Issue links only, and each issue labelled `slice` when labels are known."""
    errors = []
    for line in lines:
        match = ISSUE_LINK.match(line)
        if not match or match.group(1) != "issues":
            errors.append(
                f"{where}: '{section.name}' holds more than issue links: {line!r}"
            )
            continue
        number = int(line.rstrip(")").rsplit("/", 1)[1])
        if labels is not None and "slice" not in labels(number):
            errors.append(f"{where}: #{number} is not labelled 'slice'")
    return errors


def check_routed(
    where: str, section: Section, lines: list[str], doc: Path | None
) -> list[str]:
    """Every bullet links the document it changed, and that document exists."""
    errors = []
    for line in lines:
        links = DOC_LINK.findall(line) if line.startswith("- ") else []
        if not links:
            errors.append(
                f"{where}: each learning must link the document it changed: {line!r}"
            )
            continue
        for target, _ in links:
            if doc is not None and not (doc.parent / target).resolve().exists():
                errors.append(f"{where}: '{target}' does not exist")
    return errors


#: A skill opens with YAML frontmatter, which Claude Code reads and the
#: sections check does not.
FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)


def check_file(
    root: Path, rel: str, artifact: Artifact, labels: Labels | None = None
) -> list[str]:
    text = FRONTMATTER.sub("", (root / rel).read_text(), count=1)
    errors = []
    titles = [line for line in text.splitlines() if line.startswith("# ")]
    if not text.lstrip().startswith("# ") or len(titles) != 1:
        errors.append(f"{rel}: must open with one '#' title")
    found = headings(text, 2)

    if artifact.repeating:
        spec = artifact.sections[0]
        if not found:
            errors.append(f"{rel}: needs at least one '{spec.name}' section")
        for heading, body in found:
            if not spec.pattern.match(heading):
                errors.append(f"{rel}: '{heading}' does not match '{spec.name}'")
                continue
            subs = headings(f"## {heading}\n{body}", 3)
            names = [h for h, _ in subs]
            wanted = [child.name for child in spec.children]
            if names != wanted:
                errors.append(f"{rel}: '{heading}' needs {wanted}, has {names}")
                continue
            for child, (_, sub_body) in zip(spec.children, subs, strict=True):
                errors += check_body(
                    f"{rel} › {heading}", child, sub_body, doc=root / rel, labels=labels
                )
        return errors

    names = [heading for heading, _ in found]
    wanted = [section.name for section in artifact.sections]
    if names != wanted:
        errors.append(f"{rel}: sections must be {wanted}, found {names}")
        return errors
    for section, (_, body) in zip(artifact.sections, found, strict=True):
        errors += check_body(rel, section, body, doc=root / rel, labels=labels)
    return errors


def check_milestones(root: Path) -> list[str]:
    base = root / "docs" / "milestones"
    if not base.is_dir():
        return []
    errors = []
    for folder in sorted(p for p in base.iterdir() if p.is_dir()):
        where = f"docs/milestones/{folder.name}"
        if not MILESTONE_DIR.match(folder.name):
            errors.append(f"{where}: folder must be named mNN-name")
        if not (folder / "scope.md").exists():
            errors.append(f"{where}: needs scope.md")
    return errors


def documents(root: Path) -> list[str]:
    found = [
        p.relative_to(root).as_posix()
        for p in (root / "docs").rglob("*")
        if p.is_file()
    ]
    found += [
        p.relative_to(root).as_posix()
        for p in (root / ".claude" / "skills").glob("*/SKILL.md")
    ]
    return sorted(
        found
        + [
            name
            for name in ("README.md", "CLAUDE.md", "CONTRIBUTING.md")
            if (root / name).exists()
        ]
    )


def sources(root: Path) -> list[Path]:
    """Every text file in the repository, skipping hidden directories but
    `.github`, and the environment and caches."""
    skip = {".venv", "__pycache__", "node_modules"}
    found = []
    for path in root.rglob("*"):
        parts = path.relative_to(root).parts
        if any(p in skip or (p.startswith(".") and p != ".github") for p in parts[:-1]):
            continue
        if path.is_file() and (
            path.suffix in SOURCE_SUFFIXES or path.name == "Dockerfile"
        ):
            found.append(path)
    return found


def check_decision_refs(root: Path, retiring: set[str]) -> list[str]:
    errors = []
    for path in sources(root):
        rel = path.relative_to(root).as_posix()
        if rel in NOT_SCANNED or rel in retiring:
            continue
        text = path.read_text(errors="ignore")
        for match in DECISION_REF.finditer(text):
            n = text.count("\n", 0, match.start()) + 1
            errors.append(f"{rel}:{n}: refers to a decision; state the reason")
    return errors


def check(root: Path, labels: Labels | None = None) -> list[str]:
    artifacts = load_artifacts(root)
    errors = []
    for rel in documents(root):
        owner = next(
            (a for a in artifacts if any(fnmatch.fnmatch(rel, p) for p in a.paths)),
            None,
        )
        if owner is None:
            errors.append(f"{rel}: not an artifact in {GOVERNANCE}")
        elif owner.status == "active":
            errors += check_file(root, rel, owner, labels)
    retiring = {
        rel
        for rel in documents(root)
        for a in artifacts
        if a.status == "retiring" and any(fnmatch.fnmatch(rel, p) for p in a.paths)
    }
    return errors + check_milestones(root) + check_decision_refs(root, retiring)


def github_labels(token: str) -> Labels:
    """Read an issue's labels from GitHub, once per issue."""
    seen: dict[int, set[str]] = {}

    def labels(number: int) -> set[str]:
        if number not in seen:
            request = urllib.request.Request(
                REPO_API.format(number),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                seen[number] = {
                    label["name"] for label in json.load(response)["labels"]
                }
        return seen[number]

    return labels


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN")
    if os.environ.get("CI") and not token:
        print("GITHUB_TOKEN is not set, so slice labels cannot be checked")
        return 1
    errors = check(Path.cwd(), github_labels(token) if token else None)
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
