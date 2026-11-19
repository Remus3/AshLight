"""AUTO-01 (LOOP-PREFLIGHT core): the hand-off session line, the dry run past
HALT and the tick step seam tools/loop_steps/.

load() and run() are driven with a scratch step folder; the two real steps
(the GGG docs watch and the TC-DRIFT check) are checked only through tick
behaviour - their Deps seams called in the right phase - never by module
name, so a later package can replace those modules without editing this file.
Every tick here runs on a scratch root with the network seams stubbed."""

import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import al_loop  # noqa: E402
import loop_steps  # noqa: E402
from al_loopkit import deps, isolate_git, make_root  # noqa: E402

NOW = 1_790_000_000.0


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch):
    isolate_git(monkeypatch)


def progress(root):
    return json.loads((root / "ops/loop/control/progress/loop.json").read_text())


def halt(root):
    p = root / al_loop.HALT_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("", encoding="ascii")


def steps_dir(tmp_path, files):
    d = tmp_path / "steps"
    d.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (d / name).write_text(text, encoding="ascii", newline="\n")
    return d


RECORDER = (
    "def pre_halt(tick):\n"
    "    tick.d.seen_steps.append(('pre_halt', tick.halted))\n"
    "def work(tick):\n"
    "    tick.d.seen_steps.append(('work',))\n"
    "    return 'rec work line'\n"
    "def post_work(tick, rows, work, skipped):\n"
    "    tick.d.seen_steps.append(('post_work', [w['id'] for w in work]))\n"
    "def checklist(tick):\n"
    "    tick.d.seen_steps.append(('checklist',))\n"
    "    return [tick.d.checklist.item('WATCH-1', 'Read the watch finding')]\n"
)


def fake_tick():
    log = []
    return types.SimpleNamespace(step=log.append, dry=False, log=log)


# ---------------------------------------------------------------- session line

def test_handoff_session_reads_the_live_line_shape():
    live = "AL NEXT SESSION\nSESSION: 7   (FLEET item 13 counter; /done writes n+1)\n"
    assert al_loop.handoff_session(live) == 7
    assert al_loop.handoff_session("x\nSESSION: 34\ny\n") == 34
    assert al_loop.handoff_session("SESSION:12 (tight)") == 12
    assert al_loop.handoff_session("SESSION: 7x") is None
    assert al_loop.handoff_session("no counter\n  SESSION: 3") is None
    assert al_loop.handoff_session(None) is None
    real = (ROOT / "AL-NEXT-SESSION.txt").read_text(encoding="utf-8")
    assert isinstance(al_loop.handoff_session(real), int)


# ---------------------------------------------------------------- --ignore-halt

def test_ignore_halt_needs_dry_run(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        al_loop.main(["tick", "--ignore-halt"])
    assert exc.value.code == 2
    assert "--ignore-halt" in capsys.readouterr().err
    root = make_root(tmp_path)
    d = deps(root)
    with pytest.raises(ValueError):
        al_loop.tick(deps=d, ignore_halt=True)
    assert d.spawn.calls == [] and not (root / "ops/loop/control").exists()
    # the accept line: the real CLI refuses before any tick runs
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "al_loop.py"), "tick",
                        "--ignore-halt"], capture_output=True, text=True, timeout=120)
    assert r.returncode != 0


@pytest.mark.git
def test_dry_run_ignore_halt_lists_would_dispatch_under_halt(tmp_path, monkeypatch, capsys):
    root = make_root(tmp_path, handoff="")
    halt(root)
    calls = []
    d = deps(root, seen_steps=[],
             docs_watch=lambda r, now: calls.append("docs") or "ggg docs: 6/6",
             drift=lambda r, now: calls.append("drift") or "tc drift: x")
    monkeypatch.setattr(loop_steps, "DIR", steps_dir(tmp_path, {"rec.py": RECORDER}))
    doc = al_loop.tick(dry_run=True, no_push=True, deps=d, ignore_halt=True)
    would = [x for x in doc["log"] if ": would dispatch to lane " in x]
    assert [x.split(":")[0] for x in would] == ["012", "013"]
    # no record, no status, no progress file, no spawn, no launch, no step
    assert not (root / al_loop.ITEMS_REL).exists() or \
        not list((root / al_loop.ITEMS_REL).iterdir())
    assert not (root / "ops/loop/control/progress/loop.json").exists()
    assert not (root / "ops/loop/control/inbox_status.json").exists()
    assert d.spawn.calls == [] and d.seen["launch"] == [] and d.seen["record"] == []
    assert calls == [] and d.seen_steps == []
    assert (root / al_loop.HALT_REL).exists()
    # without --ignore-halt the same dry run stops at HALT
    assert al_loop.tick(dry_run=True, no_push=True, deps=d)["state"] == "halted"
    # the CLI prints the would-dispatch lines, then the state
    real = al_loop.tick
    monkeypatch.setattr(al_loop, "tick", lambda dry, nop, ignore_halt=False:
                        real(dry, nop, deps=d, ignore_halt=ignore_halt))
    capsys.readouterr()
    assert al_loop.main(["tick", "--dry-run", "--ignore-halt", "--no-push"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[-1] == "loop: halted"
    assert [x.split(":")[0] for x in out[:-1] if "would dispatch" in x] == ["012", "013"]
    assert calls == [] and d.seen_steps == []


# ---------------------------------------------------------------- the seam

@pytest.mark.git
def test_steps_run_in_name_order_and_a_fault_is_one_tick_line(tmp_path, monkeypatch):
    sd = steps_dir(tmp_path, {
        "b_second.py": "def work(tick):\n    return 'b'\n",
        "a_first.py": "def work(tick):\n    return ['a1', None, 'a2']\n",
        "c_boom.py": "def work(tick):\n    raise RuntimeError('broke')\n",
        "d_broken.py": "raise ImportError('no such dep')\n",
        "e_quiet.py": "def checklist(tick):\n    return []\n",
        "tc_drift.py": "def work(tick):\n    return None\n",
        "_private.py": "raise SystemExit('never imported')\n",
    })
    errors = []
    mods = loop_steps.load(sd, errors)
    assert [m.__name__ for m in mods] == ["loop_steps.a_first", "loop_steps.b_second",
                                          "loop_steps.c_boom", "loop_steps.e_quiet",
                                          "loop_steps.tc_drift"]
    assert [e[0] for e in errors] == ["d_broken"]
    t = fake_tick()
    assert loop_steps.run("work", t, directory=sd) == ["a1", "a2", "b"]
    assert t.log == ["step d_broken: import failed: ImportError: no such dep",
                     "step c_boom: RuntimeError: broke"]
    loop_steps.run("work", t, directory=sd)  # the modules load once per tick
    assert sum("d_broken" in x for x in t.log) == 1
    assert sum("c_boom" in x for x in t.log) == 2
    assert loop_steps.run("post_work", t, 1, 2, 3, directory=sd) == []
    # the folder is never on sys.path: a step named like a tools module never
    # shadows it, and the default folder loads no scratch module
    assert str(sd) not in sys.path and str(loop_steps.DIR) not in sys.path
    import tc_drift
    assert Path(tc_drift.__file__).resolve() == (ROOT / "tools" / "tc_drift.py").resolve()
    assert all(Path(m.__file__).parent == loop_steps.DIR for m in loop_steps.load())
    # a dry tick calls no step
    t.dry = True
    assert loop_steps.lines("work", t) == [] and loop_steps.rows(t, [1]) == [1]
    # through a real tick: the fault is one line and the tick ends normally
    root = make_root(tmp_path)
    monkeypatch.setattr(loop_steps, "DIR", sd)
    d = deps(root)
    doc = al_loop.tick(deps=d, no_push=True)
    assert doc["state"] in ("running", "idle") and progress(root)["status"] == "done"
    log = progress(root)["log"]
    assert "step c_boom: RuntimeError: broke" in log
    assert log.index("a1") < log.index("a2") < log.index("b")
    assert sum(x.startswith("step d_broken") for x in log) == 1


@pytest.mark.git
def test_pre_halt_steps_run_under_halt_and_not_on_a_dry_run(tmp_path, monkeypatch):
    root = make_root(tmp_path, handoff="")
    halt(root)
    calls = []
    d = deps(root, docs_watch=lambda r, now: calls.append(("docs", r, now)) or "ggg docs: 6/6",
             drift=lambda r, now: calls.append(("drift", r, now)) or "tc drift: none")
    doc = al_loop.tick(deps=d, no_push=True)
    assert doc["state"] == "halted"
    assert calls == [("docs", root, NOW)]  # the work phase never runs HALTed
    assert progress(root)["log"] == ["ggg docs: 6/6", "HALT file present"]
    al_loop.tick(dry_run=True, deps=d, no_push=True)
    assert len(calls) == 1  # a dry run calls no step
    (root / al_loop.HALT_REL).unlink()
    al_loop.tick(deps=d, no_push=True)
    assert [c[0] for c in calls] == ["docs", "docs", "drift"]
    assert calls[-1] == ("drift", root, NOW)
    log = progress(root)["log"]
    assert log.index("ggg docs: 6/6") < log.index("tc drift: none")
    al_loop.tick(dry_run=True, deps=d, no_push=True)
    assert len(calls) == 3
    # scratch steps: tick.halted is set before pre_halt; work and post_work
    # never run HALTed or dry; post_work sees the work list
    monkeypatch.setattr(loop_steps, "DIR", steps_dir(tmp_path, {"rec.py": RECORDER}))
    d = deps(root, seen_steps=[])
    al_loop.tick(deps=d, no_push=True)
    assert d.seen_steps == [("pre_halt", False), ("work",), ("post_work", ["012", "013"]),
                            ("checklist",)]
    assert "rec work line" in progress(root)["log"]
    halt(root)
    d = deps(root, seen_steps=[])
    al_loop.tick(deps=d, no_push=True)
    assert d.seen_steps == [("pre_halt", True), ("checklist",)]
    d = deps(root, seen_steps=[])
    al_loop.tick(dry_run=True, deps=d, no_push=True)
    assert d.seen_steps == []


@pytest.mark.git
def test_checklist_steps_reach_a_halted_tick(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    halt(root)
    monkeypatch.setattr(loop_steps, "DIR", steps_dir(tmp_path, {"rec.py": RECORDER}))
    d = deps(root, seen_steps=[])
    al_loop.tick(deps=d, no_push=True)
    doc = progress(root)
    assert doc["state"] == "halted"
    assert [r["id"] for r in doc["checklist"]] == ["WATCH-1"]
    assert doc["checklist"][0]["task"] == "Read the watch finding"
    # a running tick: the step rows come after the tick's own rows
    (root / al_loop.HALT_REL).unlink()
    al_loop.tick(deps=deps(root, seen_steps=[]), no_push=True)
    ids = [r["id"] for r in progress(root)["checklist"]]
    assert ids[-1] == "WATCH-1" and "012" in ids and ids.index("012") < ids.index("WATCH-1")
    # past the kit cap the rows are cut and counted, never silent; non-rows dropped
    cap = d.checklist.ROWS_MAX
    many = ("def checklist(tick):\n"
            "    return ['not a row', None] + [tick.d.checklist.item('W-%d' % i, 'row %d' % i)"
            " for i in range(" + str(cap + 5) + ")]\n")
    monkeypatch.setattr(loop_steps, "DIR", steps_dir(tmp_path / "x", {"many.py": many}))
    halt(root)
    al_loop.tick(deps=deps(root), no_push=True)
    doc = progress(root)
    assert len(doc["checklist"]) == cap and doc["checklist_dropped"] == 5
    assert doc["checklist"][0]["id"] == "W-0"
