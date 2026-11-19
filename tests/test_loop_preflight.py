"""LOOP-PREFLIGHT-CMD: tools/loop_preflight.py runs the loop gates once in a
claimed lane worktree and reports one line per gate; --handoff prints only
the hand-off count. Fakes stand in for the lane claim and the gate runner: no
git, no suite, no headless run."""

import contextlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import al_lane  # noqa: E402
import loop_preflight  # noqa: E402

GATES = "# comment\npython -m pytest -q\nnpm test --prefix app\npython tools/leak_sweep.py --tree\n"


class LaneRefused(RuntimeError):
    pass


def fake_lanes(tmp_path, busy=()):
    calls = []

    @contextlib.contextmanager
    def ctx(root, code, lane, run_id, cap=None):
        calls.append(("claim", lane, run_id))
        if lane in busy:
            raise LaneRefused(f"{lane} busy")
        wt = tmp_path / f"lane-{lane}"
        (wt / "ops" / "loop").mkdir(parents=True, exist_ok=True)
        (wt / "ops" / "loop" / "gates.txt").write_text(GATES, encoding="utf-8")
        try:
            yield {"worktree": str(wt), "index": 0}
        finally:
            calls.append(("release", lane))

    return ctx, calls


def fake_runner(rcs):
    ran = []

    def run(argv, cwd):
        ran.append((tuple(argv), Path(cwd).name))
        return rcs.get(len(ran), 0), "tail line\n"

    return run, ran


def test_preflight_runs_each_gate_once_and_reports(tmp_path):
    ctx, calls = fake_lanes(tmp_path)
    run, ran = fake_runner({})
    lines = []
    rc = loop_preflight.preflight(tmp_path, lane_ctx=ctx, out=lines.append,
                                  gates=lambda wt: loop_preflight.run_gates(wt, run=run))
    assert rc == 0
    assert len(ran) == 3 and all(cwd == "lane-build" for _, cwd in ran)
    # the whole pytest suite goes through the kit suite gate, like the loop's gates
    assert "fleet_suite_gate.py" in " ".join(ran[0][0])
    assert ran[2][0][-2:] == ("tools/leak_sweep.py", "--tree")
    gate_lines = [ln for ln in lines if ln.startswith(("PASS ", "FAIL "))]
    assert len(gate_lines) == 3 and all(ln.startswith("PASS ") for ln in gate_lines)
    assert lines[-1] == "preflight: green (3 gates)"
    assert calls == [("claim", "build", "preflight"), ("release", "build")]


def test_preflight_red_gate_exits_1(tmp_path):
    ctx, calls = fake_lanes(tmp_path)
    run, ran = fake_runner({2: 1})
    lines = []
    rc = loop_preflight.preflight(tmp_path, lane_ctx=ctx, out=lines.append,
                                  gates=lambda wt: loop_preflight.run_gates(wt, run=run))
    assert rc == 1
    assert len(ran) == 3  # a red gate does not hide the later ones
    assert [ln.split()[0] for ln in lines if ln.startswith(("PASS", "FAIL"))] == \
        ["PASS", "FAIL", "PASS"]
    assert lines[-1] == "preflight: red (3 gates)"
    assert calls[-1] == ("release", "build")
    # a busy lane set exits 1 with the reason and runs no gate
    ctx2, calls2 = fake_lanes(tmp_path, busy=al_lane.LANES)
    run2, ran2 = fake_runner({})
    lines2 = []
    rc2 = loop_preflight.preflight(tmp_path, lane_ctx=ctx2, out=lines2.append,
                                   gates=lambda wt: loop_preflight.run_gates(wt, run=run2))
    assert rc2 == 1 and ran2 == []
    assert lines2[-1].startswith("preflight: no lane free:") and "build busy" in lines2[-1]
    # no gate list fails closed
    empty = tmp_path / "bare"
    empty.mkdir()
    rows = loop_preflight.run_gates(empty, run=run2)
    assert len(rows) == 1 and rows[0][1] is False and ran2 == []


def test_handoff_flag_prints_only_the_count(tmp_path):
    (tmp_path / "AL-NEXT-SESSION.txt").write_text(
        "SESSION: 7\n\nCarried forward\n- LOOP: Fix the thing in tools.\n"
        "- LOOP: OPERATOR: paste the hook block.\n- LOOP: Build the other thing\n"
        "  over two lines.\n- Not loop work.\n"
        "\nNext section\n- not counted\n", encoding="utf-8")
    lines = []
    rc = loop_preflight.main(["--handoff"], root=tmp_path, out=lines.append)
    assert rc == 0
    assert lines == ["hand-off loop items: 2"]


def test_preflight_never_spawns_a_headless_run(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("headless spawn attempted")

    class NoKit:
        spawn = staticmethod(boom)
        write_progress = staticmethod(boom)

    monkeypatch.setattr(al_lane, "kit", lambda: NoKit)
    monkeypatch.setattr(al_lane, "run_lane", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    ctx, _ = fake_lanes(tmp_path)
    run, ran = fake_runner({})
    lines = []
    rc = loop_preflight.preflight(tmp_path, lane_ctx=ctx, out=lines.append,
                                  gates=lambda wt: loop_preflight.run_gates(wt, run=run))
    assert rc == 0 and len(ran) == 3
    src = (ROOT / "tools" / "loop_preflight.py").read_text(encoding="ascii")
    assert "spawn(" not in src and "Popen" not in src and "fleet_headless" not in src
