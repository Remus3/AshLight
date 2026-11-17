"""SIDECAR rule (operator order 2026-11-16) for the lane driver, and the AL
ROADMAP.md bullet rows the loop dispatches. No git, no spawn, no live state."""

import contextlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import al_lane  # noqa: E402
import al_loop  # noqa: E402


# ---------------------------------------------------------------- sidecar

def test_sidecar_root_env_override_and_off(tmp_path):
    assert al_lane.sidecar_root({"AL_SIDECAR_ROOT": ""}) is None
    assert al_lane.sidecar_root({"AL_SIDECAR_ROOT": "relative"}) is None
    assert al_lane.sidecar_root({"AL_SIDECAR_ROOT": str(tmp_path)}) == tmp_path


def test_sidecar_root_defaults_to_the_kit_sidecar_dir():
    # the suite pins FLEET_SIDECAR_ROOT off (conftest): no kit sidecar, no root
    env = {k: v for k, v in os.environ.items() if k != "AL_SIDECAR_ROOT"}
    assert al_lane.sidecar_root(env) is None


def test_sidecar_temp_env_sets_and_restores_temp(tmp_path):
    env = {"AL_SIDECAR_ROOT": str(tmp_path), "TEMP": "old"}
    with al_lane.sidecar_temp_env(env) as tmp:
        assert tmp == tmp_path / "Temp" and tmp.is_dir()
        assert env["TEMP"] == env["TMP"] == str(tmp_path / "Temp")
    assert env["TEMP"] == "old" and "TMP" not in env


def test_sidecar_temp_env_without_a_sidecar_changes_nothing():
    env = {"AL_SIDECAR_ROOT": "", "TEMP": "old"}
    with al_lane.sidecar_temp_env(env) as tmp:
        assert tmp is None and env == {"AL_SIDECAR_ROOT": "", "TEMP": "old"}


def test_run_lane_spawns_with_temp_under_the_sidecar_and_code_al(tmp_path, monkeypatch):
    side = tmp_path / "side"
    side.mkdir()
    monkeypatch.setenv("AL_SIDECAR_ROOT", str(side))
    before = os.environ.get("TEMP")
    seen = {}

    @contextlib.contextmanager
    def lane_ctx(root, code, name, run_id, cap):
        yield {"worktree": tmp_path / "wt", "index": 0}

    def spawn(root, code, prompt, **kw):
        seen.update(code=code, temp=os.environ.get("TEMP"), tmp=os.environ.get("TMP"))
        return {"rc": 0, "error": None}

    al_lane.run_lane("build", "x", root=tmp_path, lane_ctx=lane_ctx, spawn=spawn,
                     progress=lambda *a, **k: None, record=lambda *a, **k: None)
    assert seen["code"] == "AL"  # the kit child_env(code="AL") sets CLAUDE_CODE_TMPDIR
    assert seen["temp"] == seen["tmp"] == str(side / "Temp")
    assert os.environ.get("TEMP") == before


def test_no_sidecar_literal_in_tracked_loop_sources():
    # public-repo hygiene: the sidecar root is built by the kit, never spelled
    drive_root = "E:" + "\\" + "Sidecars"
    for rel in ("tools/al_lane.py", "tools/al_loop.py", "tools/loop_base.py",
                "tools/lane_samples.py", "config/local.example.json"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert drive_root not in text and drive_root.replace("\\", "/") not in text, rel


# ---------------------------------------------------------------- ROADMAP rows

AL_ROADMAP = """# AshLight ROADMAP

## Lane: build

- [ ] LIVE-1 (build) (priority) Run the core against the real log;
  confirm every pattern. ACCEPT: a fixture per event.
- [ ] OVL-POS (build) Overlay layout editor. ACCEPT: survives restart.
- [x] OLD-1 (build) Done thing -- done 2026-11-16

## Lane: data

- [ ] DATA-NINJA (data) Currency rates with caching.

## Ops

- [ ] OPERATOR: create the remote when the operator wants to publish.
"""


def test_roadmap_rows_parse_bullets_with_continuations():
    rows = {r["id"]: r for r in al_loop.roadmap_rows(AL_ROADMAP)}
    assert list(rows) == ["LIVE-1", "OVL-POS", "OLD-1", "DATA-NINJA"]  # OPERATOR is no row
    live = rows["LIVE-1"]
    assert live["open"] and live["status"] == "[ ] priority" and live["lane"] == "build"
    assert live["title"] == "Run the core against the real log; confirm every pattern."
    assert "ACCEPT: a fixture per event." in live["text"]
    assert rows["OLD-1"]["open"] is False and rows["DATA-NINJA"]["lane"] == "data"


def test_flip_roadmap_marks_the_first_line_done():
    out = al_loop.flip_roadmap(AL_ROADMAP, "LIVE-1", "done 2026-11-17 (loop)")
    assert "- [x] LIVE-1 (build) (priority) Run the core against the real log; -- done " \
           "2026-11-17 (loop)" in out
    assert "  confirm every pattern. ACCEPT: a fixture per event." in out
    assert al_loop.flip_roadmap(out, "LIVE-1", "again") == out  # only open rows flip
    assert not al_loop.roadmap_rows(out)[0]["open"]


def test_work_list_prefers_priority_and_carries_the_lane_hint(tmp_path):
    import al_loopkit as L
    root = L.make_root(tmp_path, roadmap=AL_ROADMAP, handoff="")
    _, work, _ = al_loop.Tick(L.deps(root)).work_list()
    assert [w["id"] for w in work] == ["LIVE-1", "OVL-POS", "DATA-NINJA"]
    data = work[2]
    assert data["lane_hint"] == "data" and al_loop.route_kind(data) == "data"
    assert "ACCEPT" in work[0]["text"]


def test_dispatch_puts_a_row_on_its_hinted_lane(tmp_path):
    import al_loopkit as L
    rm = "- [ ] DATA-NINJA (data) Currency rates.\n- [ ] UX-REVIEW (review) Review.\n"
    root = L.make_root(tmp_path, roadmap=rm, handoff="")
    d = L.deps(root)
    al_loop.tick(deps=d, no_push=True)
    items = al_loop.Items(root)
    assert items.get("DATA-NINJA")["lane"] == "data"
    assert items.get("UX-REVIEW")["lane"] == "review"


def test_resolve_roadmap_keys_bullet_rows_by_id():
    base = "- [ ] A-1 (build) one\n- [ ] B-2 (build) two\n"
    ours = base.replace("- [ ] A-1 (build) one", "- [x] A-1 (build) one -- done")
    theirs = base + "- [ ] C-3 (data) three\n"
    out = al_loop.resolve_roadmap(base, ours, theirs)
    assert "- [x] A-1 (build) one -- done" in out and "- [ ] C-3 (data) three" in out


def test_depends_on_names_row_ids():
    assert al_loop.plan_depends("Depends on: LIVE-1, OVL-POS and 012\n") == \
        ["LIVE-1", "OVL-POS", "012"]
    assert al_loop.plan_depends("Depends on: none\n") == []
