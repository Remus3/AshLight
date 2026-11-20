"""Self-test of a laid-out version (REL-INSTALL-SELFTEST, F-050, DEP-09;
docs/plan/05-deployment.md "How an update swaps versions", step 2).

Before any marker write, version <new> (laid out at <home>/app/<new>/)
proves itself in two child processes, both started from ITS payload root
through the one command builder paths.python_cmd (root = that folder):

1. `boot.py server.al --check`: the new code imports and every server .py
   compiles (exit 0).
2. `boot.py server.al --demo <fixture> --port <p>`: a demo core (decision
   0049) on the first free port of ports.SELFTEST_PORTS (8970-8975, never
   8960), with AL_HOME = <home>, so its scratch runtime lands under
   <home>/temp/demo-* and web data is off (the demo fetcher refuses every
   request). Its GET /api/health must answer version == <new> within
   HEALTH_TIMEOUT_S. The fixture is the shipped synthetic log
   server/al/data/selftest/client_selftest.txt of the NEW version (made
   with tools/synth_client.py Session, invented names only, ASCII + LF;
   never a copy of a real Client.txt), copied as Client.txt beside the demo
   marker into a run folder under <home>/temp. A demo core that would open
   a log outside that folder exits 97 (decision 0049), which fails the test.

Gate (FPS floor, decision 0029 signal): the test starts only on the
player's click (clicked=True, e.g. the pasted install line or "Update
now") or while the injected idle() callable answers True: the running
core's own game_idle status. False, None (unknown) or an error waits,
polled every poll_s up to max_wait_s, then the run is deferred (nothing
moved, no report). With no idle callable and no click the run is deferred
at once. No process list is queried and no window is looked at.

Both children run hidden (CREATE_NO_WINDOW) at below-normal priority
(BELOW_NORMAL_PRIORITY_CLASS), with cwd in the run folder under
<home>/temp (never the version folder, so it can be moved), and an
environment without AL_RUNTIME_DIR, AL_SIDECAR_ROOT, AL_PORT or
PYTHONPATH of the caller.

Outcome: run() returns a Result. A pass removes the run folder and the
demo scratch. A failure stops the demo core (stop.request in its scratch
runtime, then terminate on the child handle), moves <home>/app/<new> to
<home>/temp/failed-<new> (an older failed copy of that version is
replaced) and writes ONE report, <home>/logs/reports/selftest-<new>.json,
which names no path. The marker is never read for writing or written here:
a failed self-test never reaches it (no rollback needed).

Runs only in the installer's own process; standard library only.
"""

import json
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from .. import NAME, jsonfile, paths, ports
from . import home as homemod

HEALTH_TIMEOUT_S = 15.0   # /api/health must answer version == <new> within this
CHECK_TIMEOUT_S = 120.0   # `--check` compiles every server .py; generous on slow disks
STOP_GRACE_S = 3.0        # stop.request first, then terminate
POLL_S = 30.0             # gate poll while game_idle is false
MAX_WAIT_S = 6 * 3600.0   # gate: then deferred, retried by the caller later
HEALTH_POLL_S = 0.25
FIXTURE_REL = ("server", "al", "data", "selftest", "client_selftest.txt")
DEMO_MARKER = "ashlight-demo.json"  # demo.MARKER (decision 0049)
DEMO_LOG = "Client.txt"             # demo.LOG_NAME
DEMO_SCRATCH_PREFIX = "demo-"       # demo.SCRATCH_PREFIX
TOKEN_HEADER = "X-AL-Token"         # http.TOKEN_HEADER (pinned by the test)
STOP_FILE = "stop.request"          # __main__.STOP_FILE
EXIT_LOG_OUTSIDE = 97               # demo.EXIT_LOG_OUTSIDE
RUN_PREFIX = "selftest-"
FAILED_PREFIX = "failed-"
REPORT_SCHEMA = 1
# AL_HOME is set to the home; these of the caller never reach the child
DROP_ENV = ("AL_RUNTIME_DIR", "AL_SIDECAR_ROOT", "AL_PORT", "AL_HOME",
            "AL_TC_PINS_FILE", "PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP")
_TOKEN_RE = re.compile(r"#token=([0-9A-Za-z_\-]+)")

PASSED, FAILED, DEFERRED = "passed", "failed", "deferred"


@dataclass
class Result:
    status: str                 # passed | failed | deferred
    version: str
    stage: str = ""             # gate | layout | check | start | health
    reason: str = ""            # short text, no path
    exit_code: object = None    # the failing child's exit code, if any
    port: object = None
    moved: bool = False         # the version folder went to temp/failed-<new>
    report: object = None       # the report Path (failure only)
    waited: int = 0             # gate polls that found game_idle not true
    detail: dict = field(default_factory=dict)

    @property
    def ok(self):
        return self.status == PASSED


def child_flags():
    """Hidden and below-normal priority on Windows; 0 elsewhere."""
    if os.name != "nt":
        return 0
    return (getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x00004000))


def child_env(home, environ=None):
    """The children's environment: the caller's minus DROP_ENV, plus
    AL_HOME = home and hot reload off."""
    env = dict(os.environ if environ is None else environ)
    for key in list(env):
        if key.upper() in DROP_ENV:
            del env[key]
    env[paths.HOME_ENV] = str(home)
    env["AL_HOT_RELOAD"] = "0"
    return env


def probe_free(port):
    """True when 127.0.0.1 can bind port now (closed at once)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((ports.LOOPBACK, int(port)))
    except OSError:
        return False
    finally:
        s.close()
    return True


def free_ports(pair=ports.SELFTEST_PORTS, probe=probe_free):
    """The ports of the block that are free now, low to high; never 8960."""
    return [p for p in ports.block_range(pair) if p != ports.AL_PORT and probe(p)]


def wait_for_gate(idle, clicked, poll_s=POLL_S, max_wait_s=MAX_WAIT_S,
                  sleep=time.sleep, clock=time.monotonic):
    """(go, polls that found game_idle not true). go on a click, or when
    idle() answers True; False, None or an error waits."""
    if clicked:
        return True, 0
    if idle is None:
        return False, 0
    waited = 0
    deadline = clock() + max(0.0, float(max_wait_s))
    while True:
        try:
            state = idle()
        except Exception:  # noqa: BLE001 - an unreadable status is "not idle"
            state = None
        if state is True:
            return True, waited
        waited += 1
        if clock() >= deadline:
            return False, waited
        sleep(poll_s)


def idle_from_status(status):
    """game_idle from a core status document (decision 0029): True only
    when it says so."""
    return isinstance(status, dict) and status.get("game_idle") is True


def command(root, env, *args):
    """paths.python_cmd for the version at root; when the marker's runtime
    has no python.exe (a fresh home, or a test home), the running
    interpreter stands in, as python_cmd does for an unusable marker name
    (in an install that is the same private runtime)."""
    cmd = paths.python_cmd("server.al", *args, root=root, environ=env)
    if not Path(cmd[0]).is_file():
        cmd[0] = sys.executable
    return cmd


def _spawn_default(cmd, **kw):
    return subprocess.Popen(cmd, **kw)


def _reader(stream, out):
    try:
        for raw in iter(stream.readline, b""):
            out.put(raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw)
    except (OSError, ValueError):
        pass
    finally:
        out.put(None)


def _stop_child(proc, scratch):
    """stop.request in the demo scratch runtime, then terminate (our own
    child handle only)."""
    if proc is None:
        return
    if proc.poll() is None and scratch is not None:
        try:
            (scratch / "runtime" / STOP_FILE).write_text("selftest\n", encoding="ascii")
        except OSError:
            pass
        deadline = time.monotonic() + STOP_GRACE_S
        while proc.poll() is None and time.monotonic() < deadline:
            time.sleep(0.1)
    if proc.poll() is None:
        try:
            proc.terminate()
        except OSError:
            pass
    try:
        proc.wait(timeout=10)
    except (subprocess.TimeoutExpired, OSError):
        try:
            proc.kill()
            proc.wait(timeout=5)
        except (subprocess.TimeoutExpired, OSError):
            pass


def _demo_dirs(temp):
    try:
        return {n for n in os.listdir(temp) if n.startswith(DEMO_SCRATCH_PREFIX)}
    except OSError:
        return set()


def _health(port, token, timeout=2.0):
    """The /api/health document, or None when it does not answer yet."""
    req = urllib.request.Request(f"http://{ports.LOOPBACK}:{int(port)}/api/health",
                                 headers={TOKEN_HEADER: token})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - loopback
            doc = json.loads(resp.read(64 * 1024).decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError):
        return None
    return doc if isinstance(doc, dict) else None


def _rmtree(path):
    shutil.rmtree(path, ignore_errors=True)


def _inside(path, parent):
    try:
        Path(os.path.abspath(path)).relative_to(Path(os.path.abspath(parent)))
    except ValueError:
        return False
    return True


def prepare_fixture(version_root, run_dir):
    """Copy the new version's shipped fixture log as Client.txt beside a
    demo marker into run_dir/fixture; returns that folder."""
    src = Path(version_root).joinpath(*FIXTURE_REL)
    folder = Path(run_dir) / "fixture"
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, folder / DEMO_LOG)
    (folder / DEMO_MARKER).write_text(
        json.dumps({"name": NAME, "kind": "install self-test"}) + "\n", encoding="ascii")
    return folder


def write_report(home, result, now=None):
    """The one failure report, <home>/logs/reports/selftest-<new>.json.
    No path in it."""
    lay = homemod.layout(home)
    doc = {"schema": REPORT_SCHEMA, "kind": "selftest", "name": NAME,
           "version": result.version, "status": result.status,
           "stage": result.stage, "reason": result.reason,
           "exit_code": result.exit_code, "port": result.port,
           "moved": result.moved, "at": homemod.now_text(now)}
    path = lay["reports"] / f"selftest-{result.version}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    jsonfile.write_text(path, jsonfile.dumps(doc), backup=False)
    return path


def _fail(home, lay, result, run_dir, now):
    result.status = FAILED
    src = lay["app"] / result.version
    if homemod._is_plain_dir(src):
        dest = lay["temp"] / f"{FAILED_PREFIX}{result.version}"
        try:
            lay["temp"].mkdir(parents=True, exist_ok=True)
            if dest.exists():
                _rmtree(dest)  # an older failed copy: replaceable from its zip
            os.replace(src, dest)
            result.moved = True
        except OSError as exc:
            result.detail["move_error"] = exc.__class__.__name__
    if run_dir is not None:
        _rmtree(run_dir)
    result.report = write_report(home, result, now)
    return result


def run(home, version, ports=ports.SELFTEST_PORTS, idle=None, spawn=None,
        clicked=False, environ=None, poll_s=POLL_S, max_wait_s=MAX_WAIT_S,
        sleep=time.sleep, clock=time.monotonic, probe=probe_free,
        health_timeout_s=HEALTH_TIMEOUT_S, check_timeout_s=CHECK_TIMEOUT_S,
        now=None):
    """Self-test <home>/app/<version>. See the module text. spawn(cmd, **kw)
    returns a Popen-like child (default subprocess.Popen)."""
    port_pair = ports
    spawn = spawn or _spawn_default
    lay = homemod.layout(home)
    home = lay["home"]
    result = Result(status=DEFERRED, version=str(version))
    if not homemod.is_version(version):
        result.status, result.stage, result.reason = FAILED, "layout", "not a version"
        return result
    go, result.waited = wait_for_gate(idle, clicked, poll_s, max_wait_s, sleep, clock)
    if not go:
        result.stage = "gate"
        result.reason = "waiting for game_idle" if idle is not None else "no idle signal"
        return result
    root = lay["app"] / version
    if not homemod._is_plain_dir(root) or not (root / paths.BOOT_NAME).is_file():
        result.stage, result.reason = "layout", "version folder or boot.py missing"
        return _fail(home, lay, result, None, now)
    if not root.joinpath(*FIXTURE_REL).is_file():
        result.stage, result.reason = "layout", "self-test fixture missing"
        return _fail(home, lay, result, None, now)
    env = child_env(home, environ)
    flags = child_flags()
    lay["temp"].mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix=f"{RUN_PREFIX}{version}-", dir=str(lay["temp"])))
    common = {"env": env, "cwd": str(run_dir), "creationflags": flags,
              "stdin": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}

    # 1. --check
    cmd = command(root, env, "--check")
    try:
        proc = spawn(cmd, stdout=subprocess.DEVNULL, **common)
    except OSError as exc:
        result.stage, result.reason = "check", f"could not start ({exc.__class__.__name__})"
        return _fail(home, lay, result, run_dir, now)
    try:
        code = proc.wait(timeout=check_timeout_s)
    except subprocess.TimeoutExpired:
        _stop_child(proc, None)
        result.stage, result.reason = "check", "timed out"
        return _fail(home, lay, result, run_dir, now)
    if code != 0:
        result.stage, result.reason, result.exit_code = "check", "code check failed", code
        return _fail(home, lay, result, run_dir, now)

    # 2. a demo core on a free self-test port; /api/health answers <version>
    try:
        fixture = prepare_fixture(root, run_dir)
    except OSError as exc:
        result.stage, result.reason = "start", f"fixture copy failed ({exc.__class__.__name__})"
        return _fail(home, lay, result, run_dir, now)
    tried = set()
    while True:
        candidates = [p for p in free_ports(port_pair, probe) if p not in tried]
        if not candidates:
            result.stage = "start"
            result.reason = (f"no free port in {port_pair[0]}-{port_pair[1]}"
                             if not tried else result.reason or "demo core did not start")
            return _fail(home, lay, result, run_dir, now)
        port = candidates[0]
        tried.add(port)
        result.port = port
        outcome = _demo_once(spawn, root, fixture, port, version, env, common,
                             lay["temp"], health_timeout_s, result, probe)
        if outcome == "retry":
            continue  # the port was taken between the probe and the bind
        if outcome == PASSED:
            _rmtree(run_dir)
            result.status = PASSED
            result.stage, result.reason = "health", "answered"
            return result
        return _fail(home, lay, result, run_dir, now)


def _demo_once(spawn, root, fixture, port, version, env, common, temp,
               health_timeout_s, result, probe=probe_free):
    """One demo core start on port: PASSED, FAILED (result filled) or
    'retry' (the bind failed because the port was taken meanwhile)."""
    before = _demo_dirs(temp)
    cmd = command(root, env, "--demo", str(fixture), "--port", str(port), "--no-tail")
    try:
        proc = spawn(cmd, stdout=subprocess.PIPE, **common)
    except OSError as exc:
        result.stage, result.reason = "start", f"could not start ({exc.__class__.__name__})"
        return FAILED
    lines = queue.Queue()
    stream = getattr(proc, "stdout", None)
    if stream is not None:
        threading.Thread(target=_reader, args=(stream, lines), daemon=True,
                         name="al-selftest-out").start()
    token = None
    scratch = None
    deadline = time.monotonic() + float(health_timeout_s)
    outcome = None
    try:
        while time.monotonic() < deadline:
            while True:
                try:
                    line = lines.get_nowait()
                except queue.Empty:
                    break
                if line and token is None:
                    m = _TOKEN_RE.search(line)
                    if m:
                        token = m.group(1)
            if scratch is None:
                new = sorted(_demo_dirs(temp) - before)
                if len(new) == 1:
                    scratch = temp / new[0]
            code = proc.poll()
            if code is not None:
                result.exit_code = code
                if code == EXIT_LOG_OUTSIDE:
                    result.stage, result.reason = "start", "demo core refused a log outside its fixture"
                    outcome = FAILED
                elif code == 2 and not probe(port):
                    result.reason = "port taken"
                    outcome = "retry"
                else:
                    result.stage, result.reason = "start", "demo core exited early"
                    outcome = FAILED
                break
            if token is not None:
                doc = _health(port, token)
                if doc is not None:
                    got = doc.get("version")
                    if doc.get("name") == NAME and got == version:
                        outcome = PASSED
                    else:
                        result.stage = "health"
                        result.reason = f"answered version {got!r}, not {version}"
                        outcome = FAILED
                    break
            time.sleep(HEALTH_POLL_S)
        if outcome is None:
            result.stage, result.reason = "health", f"no answer within {health_timeout_s:g} s"
            outcome = FAILED
    finally:
        _stop_child(proc, scratch)
    if scratch is not None and outcome == PASSED and _inside(scratch, temp):
        _rmtree(scratch)
    if outcome != PASSED and scratch is not None:
        result.detail["scratch_kept"] = True
    return outcome


def main(argv=None):
    """`python -m server.al.install.selftest HOME VERSION [--click]`: a
    manual run (the player's click); prints one `selftest: <status>` line."""
    argv = list(sys.argv[1:] if argv is None else argv)
    clicked = "--click" in argv
    rest = [a for a in argv if a != "--click"]
    if len(rest) != 2:
        print("usage: python -m server.al.install.selftest HOME VERSION [--click]",
              file=sys.stderr)
        return 2
    res = run(rest[0], rest[1], clicked=clicked)
    print(f"selftest: {res.status} {res.stage} {res.reason}".rstrip())
    return 0 if res.ok else 1


if __name__ == "__main__":
    sys.exit(main())
