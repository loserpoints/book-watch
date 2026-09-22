#!/usr/bin/env bash
# Every check CI runs, in the order CI runs them.
#
# This file exists so there is exactly one definition of "does this pass".
# CI calls it, and the slice issue template tells you to run it, so the
# checklist you validate against cannot drift from what the pipeline
# actually enforces. It has drifted once already: an acceptance list that
# named two of the three checks let a formatting failure reach CI.
#
#   scripts/check.sh              lint, formatting, and the offline suite
#   scripts/check.sh -k listing   the same, passing arguments to pytest
#
# Network tests stay opt-in and are never run here — CI holds no eBay
# credentials, by decision 15. Run those by hand:
#
#   uv run pytest -m network

set -euo pipefail

echo "==> ruff check"
uv run ruff check .

echo "==> ruff format --check"
uv run ruff format --check .

echo "==> pytest"
uv run pytest "$@"
