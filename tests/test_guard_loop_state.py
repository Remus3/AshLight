"""TEST-FLAKE: the live loop tick's own control files are ignored by the
fleet test guard (extra_ignore), the stop sentinels and every other control
file are still watched."""

import fnmatch
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import fleet_test_guard  # noqa: E402
import loop_base  # noqa: E402
import conftest  # noqa: E402
import ledger_rotate  # noqa: E402

IGNORE = fleet_test_guard.IGNORE + conftest.LOOP_TICK_STATE


def ignored(rel):
    return any(fnmatch.fnmatchcase(rel.lower(), g.lower()) for g in IGNORE)


def test_every_tick_state_path_is_ignored():
    rels = [loop_base.ITEMS_REL / "X-1.json", loop_base.WATCH_REL, loop_base.ORDERS_REL,
            loop_base.BACKOFF_REL, loop_base.GATE_CACHE_REL, loop_base.PUSH_WORKER_REL,
            loop_base.PUSH_LAST_REL, loop_base.CONTROL_REL / ledger_rotate.MARKER,
            loop_base.LOCK_REL, loop_base.MERGE_LOCK_REL]
    for rel in rels:
        assert ignored(rel.as_posix()), rel


def test_sentinels_and_other_control_files_stay_watched():
    for rel in ("ops/loop/control/HALT", "ops/loop/control/SESSION_HALT",
                "ops/loop/control/headless_route_override.json",
                "moon_sync_outbox/AL-note.txt"):
        assert not ignored(rel), rel


def test_snapshot_skips_a_mid_suite_loop_item(tmp_path):
    ctl = tmp_path / "ops" / "loop" / "control"
    (ctl / "loop_items").mkdir(parents=True)
    before = fleet_test_guard.snapshot(tmp_path, ignore=IGNORE)
    (ctl / "loop_items" / "TC-DELTA.json").write_text("{}\n", encoding="ascii")
    (ctl / "gate_verdicts.json").write_text("{}\n", encoding="ascii")
    after = fleet_test_guard.snapshot(tmp_path, ignore=IGNORE)
    assert fleet_test_guard.verdict(*fleet_test_guard.compare(before, after)) == ""
    (ctl / "HALT").write_text("", encoding="ascii")
    after = fleet_test_guard.snapshot(tmp_path, ignore=IGNORE)
    assert "created 1" in fleet_test_guard.verdict(*fleet_test_guard.compare(before, after))
