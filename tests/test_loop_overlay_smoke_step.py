"""OVL-SMOKE-DAILY (AUTO-22, F-199, OPEN-39; decision 0029): the loop tick's
overlay smoke step runs the opt-in live overlay smoke at most once a local
day and only while AshLight's own core says the game is idle. Every outside
reach is an injected fake; the roots live under tmp_path, so no test touches
127.0.0.1 or starts a process."""

import ast
import datetime as dt
import importlib
import sys
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

step = importlib.import_module("loop_steps.overlay_smoke")
STEP_SRC = Path(step.__file__)

# noon local time, so +/- hours stay on the same local day
NOON = time.mktime(dt.datetime(2026, 11, 21, 12, 0, 0).timetuple())
DAY = 24 * 3600
GREEN_OUT = "....\n5 passed in 41.20s\n"
RED_OUT = ("....F\nFAILED tests/test_overlay_smoke.py::test_live_overlay_smoke_within_budget\n"
           "1 failed, 4 passed in 52.00s\n")


class Kit:
    ROWS_MAX = 20

    @staticmethod
    def item(iid, task, state=None, eta_s=None):
        return {"id": iid, "task": task, "state": state, "eta_s": eta_s}


class Fakes:
    def __init__(self, idle=True, rc=0, out=GREEN_OUT):
        self.idle, self.rc, self.out = idle, rc, out
        self.reads, self.runs = [], []

    def read(self, root):
        self.reads.append(Path(root))
        return self.idle

    def run(self, root, cmd, env, limit_s):
        self.runs.append({"root": Path(root), "cmd": list(cmd), "env": dict(env),
                          "limit": limit_s})
        return self.rc, self.out


def make_tick(root, fakes=None, now=NOON, halted=False, dry=False):
    clock = {"t": now}
    d = types.SimpleNamespace(clock=lambda: clock["t"], checklist=Kit)
    if fakes is not None:
        d.overlay_smoke_idle = fakes.read
        d.overlay_smoke_run = fakes.run
    log = []
    tick = types.SimpleNamespace(root=Path(root), d=d, dry=dry, halted=halted,
                                 step=log.append, log=log)
    tick.clock = clock
    return tick


def test_game_idle_false_runs_nothing(tmp_path):
    f = Fakes(idle=False)
    tick = make_tick(tmp_path, f)
    assert step.post_work(tick, [], [], []) is None
    assert len(f.reads) == 1 and f.runs == []
    assert not (tmp_path / step.STATE_REL).exists()  # the day is not spent
    assert step.checklist(tick) == []
    # a dry run and a HALTed tick do not even ask the core
    for t in (make_tick(tmp_path, f, dry=True), make_tick(tmp_path, f, halted=True)):
        f.idle = True
        assert step.post_work(t, [], [], []) is None
    assert len(f.reads) == 1 and f.runs == []


def test_game_idle_true_runs_it_once_per_local_day(tmp_path):
    f = Fakes(idle=True)
    tick = make_tick(tmp_path, f)
    line = step.post_work(tick, [], [], [])
    assert line == "overlay smoke: green (5 passed in 41.20s)"
    assert len(f.runs) == 1
    run = f.runs[0]
    assert run["cmd"][1:] == ["-m", "pytest", "-q", "tests/test_overlay_smoke.py"]
    assert run["env"]["AL_OVERLAY_SMOKE"] == "1"
    assert run["limit"] == step.TIME_LIMIT_S and 0 < step.TIME_LIMIT_S <= 900
    assert run["root"] == tmp_path
    rows = step.checklist(tick)
    assert len(rows) == 1 and rows[0]["id"] == step.ROW_ID and rows[0]["state"] == "green"
    # later the same local day: nothing, not even a read
    tick.clock["t"] = NOON + 6 * 3600
    assert step.post_work(tick, [], [], []) is None
    assert len(f.runs) == 1 and len(f.reads) == 1
    # the next local day runs again; yesterday's green row is gone
    tick.clock["t"] = NOON + DAY
    assert step.checklist(tick) == []
    step.post_work(tick, [], [], [])
    assert len(f.runs) == 2
    doc = step.load_state(tmp_path)
    assert doc["day"] == dt.date(2026, 11, 22).isoformat() and doc["verdict"] == "green"


def test_core_not_reachable_runs_nothing(tmp_path, monkeypatch):
    # the injected reader says unknown: nothing runs and the day stays open
    f = Fakes(idle=None)
    tick = make_tick(tmp_path, f)
    assert step.post_work(tick, [], [], []) is None
    assert f.runs == [] and not (tmp_path / step.STATE_REL).exists()
    # the default reader: no token, or a failed hello proof, is unknown and
    # the token never leaves; the opener it uses is the proxy-free one
    seen = []
    monkeypatch.setattr(step, "_token", lambda: "")
    assert step.read_idle(opener=object()) is None
    monkeypatch.setattr(step, "_token", lambda: "t" * 32)
    monkeypatch.setattr(step.paths, "load_local_config", lambda: {})
    monkeypatch.setattr(step.hello, "verify",
                        lambda port, token, opener=None, timeout=0: seen.append(
                            (port, opener)) or False)
    assert step.read_idle() is None
    assert seen and seen[0][1] is step.hello.NO_PROXY_OPENER
    assert step.ports.PORT_BLOCK[0] <= seen[0][0] <= step.ports.PORT_BLOCK[1]
    # hermetic rule: a scratch root with no injected seams reads no core
    monkeypatch.setattr(step, "read_idle", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("core read on a scratch root")))
    monkeypatch.setattr(step, "run_smoke", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("process started on a scratch root")))
    bare = make_tick(tmp_path, None)
    assert not step.live(bare)
    assert step.post_work(bare, [], [], []) is None


def test_red_smoke_is_one_checklist_line_and_no_row(tmp_path):
    f = Fakes(idle=True, rc=1, out=RED_OUT)
    tick = make_tick(tmp_path, f)
    line = step.post_work(tick, [], [], [])
    assert line.startswith("overlay smoke: red (1 failed")
    rows = step.checklist(tick)
    assert len(rows) == 1
    assert rows[0]["id"] == step.ROW_ID and rows[0]["state"] == "red"
    assert "\n" not in rows[0]["task"] and rows[0]["task"].isascii()
    # nothing filed: the step's state file is the only file it wrote
    written = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*")
                     if p.is_file())
    assert written == [step.STATE_REL.as_posix()]
    # the red row stays on later days until a green run replaces it
    tick.clock["t"] = NOON + DAY
    assert [r["state"] for r in step.checklist(tick)] == ["red"]
    f.idle = False
    step.post_work(tick, [], [], [])
    assert [r["state"] for r in step.checklist(tick)] == ["red"]
    f.idle, f.rc, f.out = True, 0, GREEN_OUT
    step.post_work(tick, [], [], [])
    assert [r["state"] for r in step.checklist(tick)] == ["green"]
    # a run past the time limit is red too; a skipped live test reads skipped
    assert step.verdict(None, "") == ("red", "time limit")
    assert step.verdict(0, "4 passed, 1 skipped in 3.0s")[0] == "skipped"


def test_step_never_lists_processes_or_sends_input():
    src = STEP_SRC.read_text(encoding="utf-8")
    low = src.lower()
    banned = ("tasklist", "psutil", "wmic", "get-process", "toolhelp32", "enumprocesses",
              "enumwindows", "findwindow", "getforegroundwindow", "sendinput",
              "keybd_event", "mouse_event", "pyautogui", "postmessage", "sendmessage",
              "ctypes", "client.txt", "taskkill")
    assert [b for b in banned if b in low] == []
    tree = ast.parse(src)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            mods.add((node.module or "").split(".")[0])
    assert mods <= {"datetime", "json", "os", "subprocess", "sys", "urllib", "pathlib",
                    "loop_base", "server"}
    assert "al_loop" not in mods
    # one subprocess call, the smoke, hidden at below-normal priority
    assert low.count("subprocess.run(") == 1 and "popen" not in low
    assert step.NO_WINDOW == 0x08000000 and step.BELOW_NORMAL == 0x00004000
    assert step.command()[1:] == ["-m", "pytest", "-q", "tests/test_overlay_smoke.py"]
    # the core is asked only on the loopback address
    assert "ports.LOOPBACK" in src and "0.0.0.0" not in src
