"""AUTO-22 (OVL-SMOKE-DAILY, F-199, OPEN-39; decision 0029): the loop tick
runs the opt-in live overlay smoke once a local day while the game is idle.

post_work(tick, rows, work, skipped): never on a dry run, never HALTed. At
  most once per local day (state file ops/runtime/watch/overlay_smoke.json,
  {"day", "verdict", "detail", "ran"}), and only when AshLight's own core
  says the game is idle: the `game_idle` field of its snapshot (decision
  0029, game log staleness). The core is asked on 127.0.0.1 at the port
  of server/al/ports.py (ports.resolve), with the per-start token from the
  runtime folder, after the hello proof, through an opener with no proxy
  (SEC-NO-PROXY). A core that does not answer, or answers without a
  boolean game_idle, is "unknown" and runs nothing; the day is not spent,
  so a later tick may try again. The run is
  `python -m pytest -q tests/test_overlay_smoke.py` with
  AL_OVERLAY_SMOKE=1, hidden, at below-normal priority, under TIME_LIMIT_S.
checklist(tick) -> kit rows: one row ROW_ID for a run of today (green or
  skipped) and for a red verdict until a later run is green. A red smoke is
  that one row and nothing else: the step files no row and writes nothing
  outside its state file.

Seams: tick.d.overlay_smoke_idle(root) -> True | False | None and
tick.d.overlay_smoke_run(root, cmd, env, limit_s) -> (rc, text). When
tick.d lacks one, the default is used only when tick.root is this checkout
(al_loop's ROOT); on any other root the step reads no core and starts
nothing (hermetic rule, tools/loop_steps). The step never looks at other
processes or windows and never sends input (Game ToS floor; decision 0029).
This module never imports al_loop. Python stdlib only.
"""

import datetime as _dt
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
for _p in (str(ROOT), str(TOOLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import loop_base  # noqa: E402

from server.al import hello, paths, ports  # noqa: E402

STATE_REL = Path("ops/runtime/watch/overlay_smoke.json")
SMOKE_TEST = "tests/test_overlay_smoke.py"
SMOKE_ENV = "AL_OVERLAY_SMOKE"
TIME_LIMIT_S = 600
READ_TIMEOUT_S = 3.0
MAX_BODY = 4 * 1024 * 1024
ROW_ID = "overlay-smoke"
DETAIL_MAX = 60
GREEN, RED, SKIPPED = "green", "red", "skipped"
BELOW_NORMAL = 0x00004000  # BELOW_NORMAL_PRIORITY_CLASS
NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW


def _same(a, b):
    try:
        return Path(a).resolve() == Path(b).resolve()
    except (OSError, TypeError, ValueError):
        return False


def live(tick):
    """True only when the tick runs on this checkout (al_loop.ROOT)."""
    return _same(tick.root, ROOT)


def _day(tick):
    return _dt.datetime.fromtimestamp(tick.d.clock()).date().isoformat()


def load_state(root):
    doc = loop_base.read_json(Path(root) / STATE_REL, None)
    return doc if isinstance(doc, dict) else {}


def _save(root, doc):
    loop_base.atomic_write(Path(root) / STATE_REL,
                           json.dumps(doc, indent=1, sort_keys=True) + "\n")


# ---------------------------------------------------------------- default seams

def _token():
    try:
        return paths.token_file().read_text(encoding="ascii").strip()
    except (OSError, ValueError):
        return ""


def read_idle(root=None, opener=None, timeout=READ_TIMEOUT_S):
    """game_idle of the dev host's own core: True, False or None (unknown).
    Loopback only, no proxy, the hello proof before the token is sent."""
    opener = opener or hello.NO_PROXY_OPENER
    token = _token()
    try:
        port = ports.resolve(None, paths.load_local_config())
    except Exception:  # noqa: BLE001 - an unreadable config is "unknown"
        return None
    if not token or not hello.verify(port, token, opener=opener, timeout=timeout):
        return None
    req = urllib.request.Request(f"http://{ports.LOOPBACK}:{int(port)}/api/state",
                                 headers={"X-AL-Token": token})
    try:
        with opener.open(req, timeout=timeout) as r:
            if r.status != 200:
                return None
            data = r.read(MAX_BODY + 1)
        if len(data) > MAX_BODY:
            return None
        doc = json.loads(data)
    except (OSError, ValueError):
        hello.forget(port)
        return None
    idle = doc.get("game_idle") if isinstance(doc, dict) else None
    return idle if isinstance(idle, bool) else None


def run_smoke(root, cmd, env, limit_s):
    """Run the smoke hidden at below-normal priority; (rc, output tail).
    A run past the time limit is rc None."""
    kw = {}
    if os.name == "nt":
        kw["creationflags"] = NO_WINDOW | BELOW_NORMAL
    try:
        p = subprocess.run(cmd, cwd=str(root), env=env, stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=limit_s, **kw)
    except subprocess.TimeoutExpired:
        return None, "time limit"
    return p.returncode, (p.stdout or "")[-2000:]


# ---------------------------------------------------------------- the step

def _seam(tick, name, default):
    fn = getattr(tick.d, name, None)
    if callable(fn):
        return fn
    return default if live(tick) else None


def command():
    return [sys.executable, "-m", "pytest", "-q", SMOKE_TEST]


def smoke_env():
    return dict(os.environ, **{SMOKE_ENV: "1"})


def verdict(rc, text):
    """(verdict, detail) from the run's exit code and pytest's summary line.
    A green exit whose summary counts a skip is SKIPPED: the live test is the
    file's one skippable test (no Electron, not Windows)."""
    last = next((ln.strip() for ln in reversed(str(text or "").splitlines()) if ln.strip()), "")
    if rc is None:
        return RED, "time limit"
    if rc != 0:
        return RED, loop_base.ascii_text(last or f"rc={rc}", DETAIL_MAX)
    if "skipped" in last:
        return SKIPPED, loop_base.ascii_text(last, DETAIL_MAX)
    return GREEN, loop_base.ascii_text(last, DETAIL_MAX)


def post_work(tick, rows=None, work=None, skipped=None):
    if getattr(tick, "dry", False) or getattr(tick, "halted", False):
        return None
    root = Path(tick.root)
    day = _day(tick)
    if load_state(root).get("day") == day:
        return None
    read = _seam(tick, "overlay_smoke_idle", read_idle)
    run = _seam(tick, "overlay_smoke_run", run_smoke)
    if read is None or run is None:
        return None
    idle = read(root)
    if idle is not True:
        return None  # playing (False) or unknown (None): nothing runs, the day is kept
    rc, text = run(root, command(), smoke_env(), TIME_LIMIT_S)
    v, detail = verdict(rc, text)
    _save(root, {"day": day, "verdict": v, "detail": detail, "ran": tick.d.clock()})
    return f"overlay smoke: {v} ({detail})" if detail else f"overlay smoke: {v}"


def checklist(tick):
    doc = load_state(tick.root)
    v = doc.get("verdict")
    if v not in (GREEN, RED, SKIPPED):
        return []
    if v != RED and doc.get("day") != _day(tick):
        return []
    detail = str(doc.get("detail") or "")
    if v == RED:
        task = f"Check the red overlay smoke of {doc.get('day')}: {detail}"
    else:
        task = f"Overlay smoke {v} today: {detail}" if detail else f"Overlay smoke {v} today"
    task = loop_base.ascii_text(task.rstrip(": "), 70)
    kit = getattr(tick.d, "checklist", None)
    if kit is not None and callable(getattr(kit, "item", None)):
        return [kit.item(ROW_ID, task, v, None)]
    return [{"id": ROW_ID, "task": task, "state": v, "eta_s": None}]
