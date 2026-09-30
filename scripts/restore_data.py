"""Restore the app's data from a Fly volume snapshot (S52).

Run by `.github/workflows/restore.yml`, which holds the Fly token, so a
restore needs a browser and nothing else. Three ways to run it:

    python scripts/restore_data.py              list the snapshots, change nothing
    python scripts/restore_data.py fresh        snapshot now and restore that
    python scripts/restore_data.py vs_ABC123    restore that snapshot

A restore always snapshots the data as it stands first, so the restore itself
can be undone by restoring that snapshot. It then creates a volume from the
chosen snapshot, destroys the machine and destroys the old volume. The deploy
that follows starts a machine, which attaches the one volume left.

The old volume is destroyed rather than kept because Fly volumes can't be
renamed, and two volumes with the same name make the app attach either one at
random. The snapshot taken first holds the same data.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Runs flyctl with these arguments and returns its parsed `--json` output,
#: or None for a command without it.
Fly = Callable[[list[str]], Any]

GONE = {"destroyed", "destroying", "pending_destroy"}
SNAPSHOT_WAIT_SECONDS = 600
GIB = 1024**3


class RestoreError(RuntimeError):
    """The restore stopped. The message says what was changed, if anything."""


@dataclass(frozen=True)
class App:
    name: str
    region: str
    volume: str


def app_from(fly_toml: Path) -> App:
    config = tomllib.loads(fly_toml.read_text())
    return App(config["app"], config["primary_region"], config["mounts"]["source"])


def run_flyctl(args: list[str]) -> Any:
    done = subprocess.run(["flyctl", *args], capture_output=True, text=True)
    if done.returncode != 0:
        raise RestoreError(f"flyctl {' '.join(args)} failed: {done.stderr.strip()}")
    if "--json" in args and done.stdout.strip():
        return json.loads(done.stdout)
    return None


def created_at(snapshot: dict[str, Any]) -> str:
    # flyctl has printed both spellings.
    return snapshot.get("created_at") or snapshot.get("createdAt") or ""


def snapshots(fly: Fly, app: App) -> list[dict[str, Any]]:
    """Every snapshot of the data, newest first, including those of volumes a
    previous restore destroyed."""
    found = []
    volumes = fly(["volumes", "list", "--all", "--app", app.name, "--json"]) or []
    for volume in volumes:
        if volume["name"] != app.volume:
            continue
        try:
            listed = fly(
                [
                    "volumes",
                    "snapshots",
                    "list",
                    volume["id"],
                    "--app",
                    app.name,
                    "--json",
                ]
            )
        except RestoreError:
            continue  # a long-destroyed volume may have nothing left to list
        for snapshot in listed or []:
            found.append({**snapshot, "volume_id": volume["id"]})
    return sorted(found, key=created_at, reverse=True)


def live_volume(fly: Fly, app: App) -> dict[str, Any]:
    volumes = fly(["volumes", "list", "--app", app.name, "--json"]) or []
    live = [
        v for v in volumes if v["name"] == app.volume and v.get("state") not in GONE
    ]
    if len(live) != 1:
        raise RestoreError(
            f"Expected one volume named {app.volume}, found {len(live)}. "
            "Nothing was changed."
        )
    return live[0]


def take_snapshot(
    fly: Fly, app: App, volume_id: str, sleep: Callable[[float], None] = time.sleep
) -> dict[str, Any]:
    """Snapshot the volume now, and wait until the snapshot can be restored."""

    def listed() -> list[dict[str, Any]]:
        args = ["volumes", "snapshots", "list", volume_id, "--app", app.name, "--json"]
        return fly(args) or []

    before = {s["id"] for s in listed()}
    fly(["volumes", "snapshots", "create", volume_id, "--app", app.name])
    waited = 0
    while waited <= SNAPSHOT_WAIT_SECONDS:
        new = [s for s in listed() if s["id"] not in before]
        if new and new[0].get("status") == "created":
            return new[0]
        sleep(10)
        waited += 10
    raise RestoreError("The snapshot taken first never finished. Nothing was changed.")


@dataclass(frozen=True)
class Restored:
    snapshot: dict[str, Any]
    safety: dict[str, Any]
    volume_id: str


def restore(
    fly: Fly, app: App, target: str, sleep: Callable[[float], None] = time.sleep
) -> Restored:
    old = live_volume(fly, app)
    known = {s["id"]: s for s in snapshots(fly, app)}
    if target != "fresh" and target not in known:
        raise RestoreError(f"No snapshot {target}. Nothing was changed.")

    safety = take_snapshot(fly, app, old["id"], sleep)
    chosen = safety if target == "fresh" else known[target]

    # A volume's size is in GB, a snapshot's in bytes. The restored volume
    # must be at least as big as the one the snapshot was taken from.
    snapshot_gb = -(-(chosen.get("volume_size") or 0) // GIB)
    size = max(old.get("size_gb") or 1, snapshot_gb, 1)
    try:
        new = fly(
            ["volumes", "create", app.volume, "--snapshot-id", chosen["id"]]
            + ["--region", app.region, "--size", str(size), "--app", app.name]
            + ["--yes", "--json"]
        )
    except RestoreError as exc:
        raise RestoreError(f"{exc}. The data was not changed.") from exc
    try:
        machines = fly(["machine", "list", "--app", app.name, "--json"]) or []
        for machine in machines:
            fly(["machine", "destroy", machine["id"], "--force", "--app", app.name])
        fly(["volumes", "destroy", old["id"], "--app", app.name, "--yes"])
    except RestoreError as exc:
        # Two volumes with one name must never be left behind: the next
        # deploy would attach either. Removing the new one leaves the data
        # as it was, and a deploy brings the app back on it.
        fly(["volumes", "destroy", new["id"], "--app", app.name, "--yes"])
        raise RestoreError(
            f"{exc}. The restored volume was removed and the data is as it was. "
            "The deploy that follows brings the app back."
        ) from exc
    return Restored(chosen, safety, new["id"])


def listing(found: list[dict[str, Any]]) -> str:
    if not found:
        return "No snapshots found.\n"
    rows = ["| Snapshot | Taken | Status |", "|---|---|---|"]
    rows += [
        f"| `{s['id']}` | {created_at(s)} | {s.get('status', '')} |" for s in found
    ]
    return "\n".join(rows) + "\n"


def report(restored: Restored) -> str:
    return (
        f"Restored snapshot `{restored.snapshot['id']}`, taken "
        f"{created_at(restored.snapshot)}.\n\n"
        f"The data as it stood before the restore is snapshot "
        f"`{restored.safety['id']}`. Restore it to undo this.\n\n"
        "**Alerts emailed since the snapshot was taken may be emailed again**, "
        "because the record of what was sent went back with the data.\n"
    )


def main(argv: list[str], fly: Fly = run_flyctl, root: Path = Path(".")) -> int:
    app = app_from(root / "fly.toml")
    target = argv[0].strip() if argv else ""
    try:
        if not target:
            out = "## Snapshots\n\n" + listing(snapshots(fly, app))
            out += "\nNothing was changed. Run again with a snapshot ID, or `fresh`.\n"
        else:
            out = "## Restored\n\n" + report(restore(fly, app, target))
    except RestoreError as exc:
        out = f"## Restore stopped\n\n{exc}\n"
        status = 1
    else:
        status = 0
    print(out)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(out)
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
