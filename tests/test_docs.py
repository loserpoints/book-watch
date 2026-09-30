"""The docs check fails when a document breaks docs/governance.md.

Each test builds a small repository around the real governance file, so the
rules under test are the ones actually in force.
"""

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_docs  # noqa: E402

ISSUE = "- [Dismiss a copy](https://github.com/loserpoints/book-watch/issues/105)"
PR = "- [S34 book page](https://github.com/loserpoints/book-watch/pull/119)"


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "docs").mkdir()
    shutil.copy(ROOT / "docs" / "governance.md", tmp_path / "docs" / "governance.md")
    return tmp_path


def write(repo, rel, text):
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def rules_doc(purpose="Decides whether a copy is under the limit.", issues=ISSUE):
    return (
        f"# Pricing\n\n## Purpose\n\n{purpose}\n\n"
        f"## Rules\n\n- Every price is delivered.\n\n## Open issues\n\n{issues}\n"
    )


def test_the_repository_passes():
    assert check_docs.check(ROOT) == []


def test_a_valid_rules_document_passes(repo):
    write(repo, "docs/rules/pricing.md", rules_doc())

    assert check_docs.check(repo) == []


def test_a_document_that_is_no_artifact_fails(repo):
    write(repo, "docs/notes.md", "# Notes\n")

    assert any("not an artifact" in e for e in check_docs.check(repo))


def test_a_missing_or_extra_section_fails(repo):
    write(repo, "docs/rules/pricing.md", rules_doc().replace("## Rules", "## Why"))

    assert any("sections must be" in e for e in check_docs.check(repo))


def test_sections_out_of_order_fail(repo):
    text = "# P\n\n## Rules\n\n- A.\n\n## Purpose\n\nOne.\n\n## Open issues\n\n" + ISSUE
    write(repo, "docs/rules/pricing.md", text)

    assert any("sections must be" in e for e in check_docs.check(repo))


def test_purpose_must_be_one_sentence(repo):
    write(repo, "docs/rules/pricing.md", rules_doc(purpose="It prices. It ranks."))

    assert any("one sentence" in e for e in check_docs.check(repo))


def test_open_issues_hold_links_and_nothing_else(repo):
    prose = ISSUE + " which we should fix soon"
    write(repo, "docs/rules/pricing.md", rules_doc(issues=prose))

    assert any("more than issue links" in e for e in check_docs.check(repo))


def test_open_issues_may_not_be_empty_unless_allowed(repo):
    write(repo, "docs/rules/pricing.md", rules_doc(issues=""))

    assert any("is empty" in e for e in check_docs.check(repo))


def test_a_known_gaps_section_may_be_empty(repo):
    text = "# Runbook\n\n" + "".join(
        f"## {s}\n\nStep.\n\n"
        for s in ("Deploy", "Roll back", "Restore data", "Post-deploy checks")
    )
    write(repo, "docs/runbook.md", text + "## Known gaps\n")

    assert check_docs.check(repo) == []


def scope(slices):
    return (
        "# Always current\n\n## Goal\n\nThe list re-checks itself daily.\n\n"
        "## Jobs advanced\n\n"
        "- [J1](../../jobs.md#j1--keep-looking-so-i-dont-have-to)\n\n"
        f"## Slices\n\n{slices}\n"
    )


def test_a_milestone_in_progress_is_its_scope_alone(repo):
    write(repo, "docs/milestones/m08-always-current/scope.md", scope(ISSUE))

    assert check_docs.check(repo) == []


def test_a_scope_names_its_slices(repo):
    """No planned milestones: a folder exists once a milestone has started,
    and by then its issues have become slices."""
    write(repo, "docs/milestones/m08-always-current/scope.md", scope(""))

    assert any("'Slices' is empty" in e for e in check_docs.check(repo))


def test_a_milestone_needs_its_scope(repo):
    folder = "docs/milestones/m07-judge-a-copy"
    write(
        repo,
        f"{folder}/learnings.md",
        "# L\n\n## Learnings\n\n- One.\n\n## Carried forward\n",
    )

    assert any("needs scope.md" in e for e in check_docs.check(repo))


def test_a_milestone_folder_is_named_by_number(repo):
    write(repo, "docs/milestones/always-current/scope.md", scope(""))

    assert any("mNN-name" in e for e in check_docs.check(repo))


def test_jobs_advanced_link_to_jobs_only(repo):
    text = scope("").replace(
        "(../../jobs.md#j1--keep-looking-so-i-dont-have-to)", "(x.md)"
    )
    write(repo, "docs/milestones/m08-always-current/scope.md", text)

    assert any("more than job links" in e for e in check_docs.check(repo))


def test_each_job_has_its_two_parts(repo):
    governance = repo / "docs" / "governance.md"
    governance.write_text(
        governance.read_text().replace("| Jobs | migrating |", "| Jobs | active |")
    )
    good = (
        "## J1 · Keep looking\n\n### Job\n\nWatch for me.\n\n"
        "### Success signal\n\nI stop searching.\n"
    )
    write(repo, "docs/jobs.md", "# Jobs\n\n" + good)
    assert check_docs.check(repo) == []

    write(
        repo,
        "docs/jobs.md",
        "# Jobs\n\n" + good.replace("### Success signal", "### Signal"),
    )
    assert any("needs ['Job', 'Success signal']" in e for e in check_docs.check(repo))


def retire(repo, path):
    """Add a retiring row to this repository's copy of governance."""
    governance = repo / "docs" / "governance.md"
    text = governance.read_text()
    runbook = next(line for line in text.splitlines() if line.startswith("| Runbook |"))
    governance.write_text(
        text.replace(runbook, f"{runbook}\n| Old notes | retiring | `{path}` | |")
    )


def test_retiring_and_migrating_documents_are_known_but_not_checked(repo):
    governance = repo / "docs" / "governance.md"
    governance.write_text(
        governance.read_text().replace(
            "| Agent instructions | active |", "| Agent instructions | migrating |"
        )
    )
    retire(repo, "docs/decisions.md")
    write(repo, "docs/decisions.md", "no title, no sections")
    write(repo, "CLAUDE.md", "# Anything\n\n## Whatever\n")

    assert check_docs.check(repo) == []


def test_headings_inside_code_blocks_do_not_count(repo):
    text = rules_doc().replace(
        "- Every price is delivered.", "```\n## Not a heading\n```"
    )
    write(repo, "docs/rules/pricing.md", text)

    assert check_docs.check(repo) == []


# --- workflow: slices and routed learnings -----------------------------------


def learnings(bullet):
    return f"# M7\n\n## Learnings\n\n{bullet}\n\n## Carried forward\n"


def test_a_learning_must_link_the_document_it_changed(repo):
    folder = "docs/milestones/m07-judge-a-copy"
    write(repo, f"{folder}/scope.md", scope(ISSUE))
    write(repo, f"{folder}/learnings.md", learnings("- Tests missed layout."))

    assert any("must link the document" in e for e in check_docs.check(repo))


def test_a_learning_links_a_document_that_exists(repo):
    folder = "docs/milestones/m07-judge-a-copy"
    write(repo, f"{folder}/scope.md", scope(ISSUE))
    bullet = "- Tests missed layout. [Contributing](../../../CONTRIBUTING.md#testing)"
    write(repo, f"{folder}/learnings.md", learnings(bullet))

    assert any("does not exist" in e for e in check_docs.check(repo))

    write(
        repo,
        "CONTRIBUTING.md",
        "# C\n\n## Building\n\n- A.\n\n## Testing\n\n- B.\n\n## Reviewing\n\n- C.\n",
    )
    assert check_docs.check(repo) == []


def test_contributing_is_checked(repo):
    write(repo, "CONTRIBUTING.md", "# Contributing\n\n## Testing\n\n- A.\n")

    assert any("CONTRIBUTING.md: sections must be" in e for e in check_docs.check(repo))


def test_slices_are_issues_not_pull_requests(repo):
    write(repo, "docs/milestones/m08-always-current/scope.md", scope(PR))

    assert any("more than issue links" in e for e in check_docs.check(repo))


def test_slices_carry_the_slice_label(repo):
    write(repo, "docs/milestones/m08-always-current/scope.md", scope(ISSUE))

    unlabelled = check_docs.check(repo, labels=lambda number: {"bug"})
    labelled = check_docs.check(repo, labels=lambda number: {"slice"})

    assert any("#105 is not labelled 'slice'" in e for e in unlabelled)
    assert labelled == []


# --- the retired decision log -------------------------------------------------


def test_code_that_points_at_a_decision_number_fails(repo):
    write(repo, "src/app.py", "# Stored as a string (decision 1).\n")

    assert check_docs.check(repo) == [
        "src/app.py:1: refers to a decision; state the reason"
    ]


def test_code_that_states_the_reason_passes(repo):
    write(repo, "src/app.py", "# Stored as a string: a float changes the price.\n")

    assert check_docs.check(repo) == []


def test_the_retiring_log_may_number_its_decisions(repo):
    retire(repo, "docs/decisions.md")
    write(repo, "docs/decisions.md", "## 1. Python\n\nSee decision 2.\n")

    assert check_docs.check(repo) == []


# --- skills -------------------------------------------------------------------


def skill(purpose="Choose the next milestone.", sections=("Steps", "Rules")):
    body = "".join(f"## {s}\n\n- One.\n\n" for s in sections)
    return (
        "---\nname: set-milestone\ndescription: Choose the next milestone.\n---\n\n"
        f"# Set milestone\n\n## Purpose\n\n{purpose}\n\n{body}"
    )


def test_a_skill_with_frontmatter_passes(repo):
    write(repo, ".claude/skills/set-milestone/SKILL.md", skill())

    assert check_docs.check(repo) == []


def test_a_skill_is_checked_like_any_document(repo):
    write(repo, ".claude/skills/set-milestone/SKILL.md", skill(sections=("Steps",)))

    assert any("SKILL.md: sections must be" in e for e in check_docs.check(repo))


def test_a_skills_purpose_is_one_sentence(repo):
    write(
        repo, ".claude/skills/plan-slice/SKILL.md", skill(purpose="Plan. Then build.")
    )

    assert any("one sentence" in e for e in check_docs.check(repo))
