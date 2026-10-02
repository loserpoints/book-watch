"""The restore workflow's script, against a fake Fly.

A restore destroys a volume, so what matters most is the order: nothing
changes until the data has been snapshotted, and two volumes with one name
are never left behind.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import restore_data  # noqa: E402

#: Fly gives a snapshot's volume size in bytes: 1073741824 for a 1GB volume.
GIB = 1073741824

APP = restore_data.App("book-watch-alan", "iad", "book_watch_data")


class FakeFly:
    """Volumes, snapshots and machines, changed by the commands the script
    runs, which it records in order."""

    def __init__(self, volumes=None, fail_on=None):
        self.volumes = volumes or [
            {
                "id": "vol_old",
                "name": "book_watch_data",
                "state": "created",
                "size_gb": 1,
            }
        ]
        self.snaps = {
            "vol_old": [
                {
                    "id": "vs_mon",
                    "created_at": "2026-09-28T00:10:00Z",
                    "status": "created",
                    "volume_size": GIB,
                },
                {
                    "id": "vs_tue",
                    "created_at": "2026-09-29T00:10:00Z",
                    "status": "created",
                    "volume_size": GIB,
                },
            ]
        }
        self.machines = [{"id": "m_1"}]
        self.fail_on = fail_on
        self.ran = []

    def __call__(self, args):
        self.ran.append(" ".join(args))
        if self.fail_on and args[:2] == self.fail_on:
            raise restore_data.RestoreError(f"flyctl {' '.join(args)} failed")
        match args:
            case ["volumes", "list", "--all", *_]:
                return self.volumes
            case ["volumes", "list", *_]:
                return [v for v in self.volumes if v["state"] != "destroyed"]
            case ["volumes", "snapshots", "list", volume_id, *_]:
                return list(self.snaps.get(volume_id, []))
            case ["volumes", "snapshots", "create", volume_id, *_]:
                self.snaps[volume_id].append(
                    {
                        "id": "vs_now",
                        "created_at": "2026-09-30T19:00:00Z",
                        "status": "created",
                        "volume_size": GIB,
                    }
                )
            case ["volumes", "create", name, "--snapshot-id", _, *_]:
                self.volumes.append(
                    {"id": "vol_new", "name": name, "state": "created", "size_gb": 1}
                )
                return {"id": "vol_new"}
            case ["machine", "list", *_]:
                return self.machines
            case ["machine", "destroy", machine_id, *_]:
                self.machines = [m for m in self.machines if m["id"] != machine_id]
            case ["volumes", "destroy", volume_id, *_]:
                for v in self.volumes:
                    if v["id"] == volume_id:
                        v["state"] = "destroyed"
        return None

    def live(self):
        return [v["id"] for v in self.volumes if v["state"] != "destroyed"]

    def changed_anything(self):
        return any(" create " in f" {r} " or " destroy " in f" {r} " for r in self.ran)


def no_wait(_seconds):
    pass


def test_listing_shows_every_snapshot_newest_first_and_changes_nothing():
    fly = FakeFly()

    found = restore_data.snapshots(fly, APP)

    assert [s["id"] for s in found] == ["vs_tue", "vs_mon"]
    assert not fly.changed_anything()


def test_listing_includes_snapshots_of_a_volume_an_earlier_restore_destroyed():
    fly = FakeFly()
    restore_data.restore(fly, APP, "vs_mon", no_wait)

    found = restore_data.snapshots(fly, APP)

    assert {"vs_mon", "vs_tue", "vs_now"} <= {s["id"] for s in found}


def test_fresh_snapshots_now_and_restores_that():
    fly = FakeFly()

    restored = restore_data.restore(fly, APP, "fresh", no_wait)

    assert restored.snapshot["id"] == "vs_now"
    assert any("--snapshot-id vs_now" in r for r in fly.ran)


def test_a_chosen_snapshot_is_restored_after_the_data_is_snapshotted():
    fly = FakeFly()

    restored = restore_data.restore(fly, APP, "vs_mon", no_wait)

    assert restored.snapshot["id"] == "vs_mon"
    assert restored.safety["id"] == "vs_now"
    first_change = next(r for r in fly.ran if " create" in r or " destroy" in r)
    assert first_change.startswith("volumes snapshots create vol_old")


def test_the_old_volume_goes_only_after_the_new_one_exists_and_the_machine_is_gone():
    fly = FakeFly()

    restore_data.restore(fly, APP, "fresh", no_wait)

    order = [r.split(" --")[0] for r in fly.ran]
    assert (
        order.index("volumes create book_watch_data")
        < order.index("machine destroy m_1")
        < order.index("volumes destroy vol_old")
    )
    assert fly.live() == ["vol_new"]
    assert fly.machines == []


def test_the_new_volume_is_sized_in_gigabytes_not_bytes():
    # The first live restore passed --size 1073741824, and Fly refused it.
    fly = FakeFly()

    restore_data.restore(fly, APP, "fresh", no_wait)

    [create] = [r for r in fly.ran if r.startswith("volumes create")]
    assert " --size 1 " in create


def test_a_volume_fly_refuses_to_create_says_the_data_is_unchanged():
    fly = FakeFly(fail_on=["volumes", "create"])

    with pytest.raises(restore_data.RestoreError, match="data was not changed"):
        restore_data.restore(fly, APP, "fresh", no_wait)

    assert fly.live() == ["vol_old"]
    assert fly.machines == [{"id": "m_1"}]


def test_an_unknown_snapshot_stops_before_anything_changes():
    fly = FakeFly()

    with pytest.raises(restore_data.RestoreError, match="Nothing was changed"):
        restore_data.restore(fly, APP, "vs_typo", no_wait)

    assert not fly.changed_anything()


def test_two_volumes_with_the_name_stop_before_anything_changes():
    fly = FakeFly()
    fly.volumes.append(
        {"id": "vol_extra", "name": "book_watch_data", "state": "created", "size_gb": 1}
    )

    with pytest.raises(restore_data.RestoreError, match="found 2"):
        restore_data.restore(fly, APP, "fresh", no_wait)

    assert not fly.changed_anything()


def test_a_failure_after_the_new_volume_exists_removes_it_and_keeps_the_data():
    fly = FakeFly(fail_on=["machine", "destroy"])

    with pytest.raises(restore_data.RestoreError, match="data is as it was"):
        restore_data.restore(fly, APP, "fresh", no_wait)

    assert fly.live() == ["vol_old"]


def test_the_report_names_the_snapshot_the_undo_and_the_repeated_alerts():
    fly = FakeFly()

    said = restore_data.report(restore_data.restore(fly, APP, "vs_tue", no_wait))

    assert "`vs_tue`, taken 2026-09-29T00:10:00Z" in said
    assert "`vs_now`. Restore it to undo this." in said
    assert "may be emailed again" in said


def test_the_app_is_read_from_fly_toml():
    assert restore_data.app_from(ROOT / "fly.toml") == APP
