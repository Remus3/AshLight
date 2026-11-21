"""LOOP-USAGE-LABEL: the row id reaches the usage line's note; the lock id stays lane-<lane>."""
import contextlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import al_lane  # noqa: E402


def _world(tmp_path):
    seen = {"spawn": [], "lane": []}
    wt = tmp_path / "al-worktrees" / "lane-1"

    @contextlib.contextmanager
    def lane_ctx(root, code, name, run_id, cap):
        seen["lane"].append((name, run_id))
        yield {"worktree": wt, "index": 1}

    def spawn(root, code, prompt, **kw):
        seen["spawn"].append(kw)
        return {"rc": 0, "error": None}

    fakes = dict(lane_ctx=lane_ctx, spawn=spawn, progress=lambda *a, **k: None,
                 record=lambda *a, **k: None)
    return seen, fakes


def test_usage_label_holds_the_row_id(tmp_path):
    seen, f = _world(tmp_path)
    al_lane.run_lane("build", "x", root=tmp_path, sample_label="ROW-42", **f)
    assert seen["spawn"][0]["note"] == "ROW-42"


def test_lane_lock_id_stays_the_lane_name(tmp_path):
    seen, f = _world(tmp_path)
    al_lane.run_lane("build", "x", root=tmp_path, sample_label="ROW-42", **f)
    assert seen["lane"] == [("build", "lane-build")]
    al_lane.run_lane("data", "x", root=tmp_path, **f)
    assert seen["spawn"][1]["note"] == "lane-data"
