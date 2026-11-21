"""PUB-DEPBOT-TICK (F-081, GP-14): the loop tick launches the Dependabot
re-apply worker once a day.

loop_check(root, now, git, popen, pid_alive) is called from the tick's daily
seam (al_loop._drift_check, which the pob-release source of the upstream
watch frame calls on every tick that is not HALTed). It returns one summary
line or None and never raises:

- HALT present (ops/loop/control/HALT)     -> None; a session runs the tool.
- no origin remote                          -> None.
- a worker launched earlier is still alive  -> 'depbot worker in flight'.
- the last launch is under 24 h old         -> None.
- else: start `pythonw tools/dependabot_reapply.py run` in the root,
  detached with no console (loop_base's _NO_WINDOW / _DETACHED / _BREAKAWAY),
  write {"launched": <epoch>, "pid": <pid>} to STATE_REL and return one line.

Hermetic rule: the real git, Popen and pid check are used only when `root` is
this checkout; on any other root a missing seam means None (no process, no
git call). The state file is gitignored runtime state beside tc_drift.json.
This module never imports al_loop (tests/test_loop_split.py). Python stdlib
only.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from loop_base import _BREAKAWAY, _DETACHED, _NO_WINDOW, atomic_write, read_json  # noqa: E402

STATE_REL = "ops/runtime/depbot.json"
HALT_REL = "ops/loop/control/HALT"
WORKER_REL = "tools/dependabot_reapply.py"
PERIOD_S = 24 * 3600
IN_FLIGHT_MAX_S = 2 * PERIOD_S  # past this an alive pid is taken as reused


def _same(a, b):
    try:
        return Path(a).resolve() == Path(b).resolve()
    except (OSError, TypeError, ValueError):
        return False


def _pythonw():
    p = Path(sys.executable).with_name("pythonw.exe")
    return str(p if p.exists() else sys.executable)


def _real_git(root):
    def git(args):
        p = subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True,
                           timeout=60, creationflags=_NO_WINDOW)
        return p.returncode, (p.stdout or "").strip()
    return git


def _real_pid_alive(pid):
    import al_lane
    return bool(al_lane.lanes().pid_alive(pid))


def has_origin(git):
    """True when `git remote get-url origin` names a remote."""
    rc, out = git(["remote", "get-url", "origin"])
    return rc == 0 and bool(str(out).strip())


def launch(root, popen=subprocess.Popen):
    """Start the worker detached in `root`; returns its pid."""
    argv = [_pythonw(), str(Path(root) / WORKER_REL), "run"]
    kw = dict(cwd=str(root), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
              stderr=subprocess.DEVNULL, close_fds=True)
    flags = _NO_WINDOW | _DETACHED
    try:
        return popen(argv, creationflags=flags | _BREAKAWAY, **kw).pid
    except OSError:
        return popen(argv, creationflags=flags, **kw).pid


def load_state(root):
    doc = read_json(Path(root) / STATE_REL, {})
    return doc if isinstance(doc, dict) else {}


def _check(root, now, git, popen, pid_alive):
    root = Path(root)
    live = _same(root, ROOT)
    if not live and (git is None or popen is None or pid_alive is None):
        return None
    if (root / HALT_REL).exists():
        return None
    git = git or _real_git(root)
    if not has_origin(git):
        return None
    st = load_state(root)
    try:
        last = float(st["launched"])
    except (KeyError, TypeError, ValueError):
        last = None  # never launched (or an unreadable record): launch now
    pid = st.get("pid")
    age = None if last is None else now - last
    if age is not None and 0 <= age < IN_FLIGHT_MAX_S and isinstance(pid, int) and pid > 0:
        if (pid_alive or _real_pid_alive)(pid):
            return "depbot worker in flight"
    if age is not None and 0 <= age < PERIOD_S:
        return None
    try:
        new_pid = launch(root, popen or subprocess.Popen)
    except OSError as exc:
        atomic_write(root / STATE_REL, json.dumps({"launched": now, "pid": None}))
        return f"depbot: worker launch failed: {exc}"
    atomic_write(root / STATE_REL, json.dumps({"launched": now, "pid": new_pid}))
    return f"depbot: re-apply worker launched (pid {new_pid})"


def loop_check(root, now, git=None, popen=None, pid_alive=None):
    """One summary line or None; never raises (see the module text)."""
    try:
        return _check(root, now, git, popen, pid_alive)
    except Exception as exc:  # noqa: BLE001 - a depbot fault must not stop the tick
        return f"depbot: {type(exc).__name__}: {exc}"


def join(a, b):
    """Two optional summary lines as one, or None when both are empty."""
    parts = [str(x) for x in (a, b) if x is not None and str(x).strip()]
    return "; ".join(parts) if parts else None
