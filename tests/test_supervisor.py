"""TEST-SUPERVISOR: the keepalive supervisor's kill / hang / restart and
stop.request paths (decision 0005) beyond tests/test_keepalive.py, and the
run.ps1 / stop.ps1 idempotency contract (decision 0010).

The state-machine tests drive server.al.keepalive.Keepalive with a fake
clock, fake processes and a tmp runtime (World, below). The script tests run
stop.ps1 for real on a tmp runtime (AL_RUNTIME_DIR) and a tmp sidecar, so the
live core is never reached; every scripts/*.ps1 is parsed with Windows
PowerShell 5.1 (FLEET item 8).
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from server.al import __main__ as entry
from server.al import keepalive as ka
from server.al import paths, ports
from tc_live_util import leased_port  # noqa: F401 (a fixture)

# TEST-MARKS (research 0049 R3): the three supervisor files share one
# xdist worker (they start real cores and supervisors).
pytestmark = pytest.mark.xdist_group("supervisor")
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = sorted((ROOT / "scripts").glob("*.ps1"))
STOP = ROOT / "scripts" / "stop.ps1"
RUN = ROOT / "scripts" / "run.ps1"
PS51 = shutil.which("powershell.exe") if sys.platform == "win32" else None
TEST_PORT = ports.PORT_BLOCK[1] - 2  # a number in fake heartbeats only; real starts lease
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)
WIN51 = pytest.mark.skipif(PS51 is None, reason="Windows PowerShell 5.1 only")


class World:
    """Fake processes (pid -> creation time), a fake clock and a heartbeat
    file on a tmp runtime."""

    def __init__(self, tmp_path):
        self.runtime = tmp_path / "runtime"
        self.runtime.mkdir()
        self.t = 1000.0
        self.procs = {}  # pid -> created
        self.health_ok = False
        self.launches = []
        self.terminated = []
        self.can_terminate = True
        self.launch_error = None
        self.next_pid = 700
        self.lines = []

    def now(self):
        return self.t

    def spawn(self, pid=None, created=None):
        if pid is None:
            self.next_pid += 4
            pid = self.next_pid
        self.procs[pid] = created if created is not None else int(self.t * 1000) + pid
        return pid

    def beat(self, pid, created=True, at=None):
        entry.write_heartbeat(self.runtime / "core.alive", pid, TEST_PORT,
                              now=self.t if at is None else at,
                              created=self.procs.get(pid) if created else None)

    def launch(self):
        if self.launch_error:
            raise self.launch_error
        pid = self.spawn()
        self.launches.append((self.t, pid))
        return pid

    def terminate(self, pid):
        self.terminated.append(pid)
        if self.can_terminate:
            self.procs.pop(pid, None)
        return self.can_terminate

    def sup(self, **kw):
        return ka.Keepalive(runtime=self.runtime, port=TEST_PORT, launch=self.launch,
                            pid_alive=lambda p: p in self.procs,
                            health=lambda: self.health_ok, terminate=self.terminate,
                            created=lambda p: self.procs.get(p, 0),
                            now=self.now, log=self.lines.append, **kw)

    def run_until(self, sup, pred, limit_s=600.0, step=ka.POLL_S):
        end = self.t + limit_s
        while self.t < end:
            self.t += step
            result = sup.step()
            if pred(result):
                return result
        return None


# ------------------------------------------------------- state machine paths

def test_heartbeat_pid_reused_by_another_process_is_not_ours(tmp_path):
    # SUP-1: the core died and Windows gave its pid to another process. The
    # supervisor took the leftover heartbeat's pid as a live, hung core: it
    # tried to terminate the unrelated process (killed it when it was any
    # python.exe) and, when that was refused, never relaunched the core.
    w = World(tmp_path)
    core = w.spawn()
    w.beat(core)
    s = w.sup()
    assert s.step() == "ok"
    del w.procs[core]  # crash: core.alive left behind
    w.spawn(pid=core, created=1)  # same pid, another process
    w.can_terminate = False
    w.run_until(s, lambda r: bool(w.launches), limit_s=ka.STALE_S * 3)
    assert w.terminated == [], "an unrelated process was targeted"
    assert w.launches, w.lines
    assert core in w.procs  # the other process is untouched


def test_heartbeat_without_creation_time_keeps_the_old_pid_rule(tmp_path):
    # a core from before the creation time was recorded: pid alone decides
    w = World(tmp_path)
    core = w.spawn()
    w.beat(core, created=False)
    s = w.sup()
    assert s.step() == "ok"
    assert s.pid == core


def test_stop_request_during_backoff_wins(tmp_path):
    w = World(tmp_path)
    core = w.spawn()
    w.beat(core)
    s = w.sup()
    s.step()
    del w.procs[core]  # crash
    w.t += 1
    assert s.step() == "waiting" and s.next_launch is not None
    (w.runtime / ka.STOP_FILE).write_text("stop", encoding="ascii")
    w.t += 0.5
    assert s.step() == "user-stop"
    assert w.launches == []
    assert json.loads((w.runtime / ka.STATE_FILE).read_text("ascii"))["status"] == "user-stop"


def test_hung_core_that_cannot_be_terminated_is_never_duplicated(tmp_path):
    w = World(tmp_path)
    core = w.spawn()
    w.beat(core)
    s = w.sup()
    s.step()
    w.can_terminate = False  # e.g. access denied
    for _ in range(100):
        w.t += ka.STALE_S
        s.step()
    assert w.launches == [], "a second core was started next to a live one"
    assert core in w.procs and w.terminated


def test_start_that_never_beats_is_terminated_and_retried(tmp_path):
    w = World(tmp_path)
    s = w.sup(start_grace_s=30.0)
    w.run_until(s, lambda r: r == "launched")
    first = w.launches[-1][1]
    assert first in w.procs  # alive, but never writes core.alive
    w.run_until(s, lambda r: len(w.launches) == 2)
    assert first in w.terminated
    assert len(w.launches) == 2


def test_launch_failure_backs_off_and_gives_up(tmp_path):
    w = World(tmp_path)
    w.launch_error = OSError("python not found")
    s = w.sup(cap=3, backoff=(1.0, 2.0, 4.0))
    result = w.run_until(s, lambda r: r == "gave-up", limit_s=3600)
    assert result == "gave-up", w.lines
    assert sum("core launch failed" in x for x in w.lines) == 3


def test_restarts_outside_the_window_are_forgotten(tmp_path):
    w = World(tmp_path)
    s = w.sup(cap=2, window_s=100.0, backoff=(1.0,))
    for _ in range(5):  # five crashes, each more than a window apart
        w.run_until(s, lambda r: r == "launched")
        pid = w.launches[-1][1]
        w.beat(pid)
        w.t += 1
        assert s.step() == "ok"
        w.t += 200.0
        w.beat(pid)
        s.step()
        del w.procs[pid]  # crash
    assert len(w.launches) == 5
    assert not any("give up" in x for x in w.lines)


def test_clean_exit_then_stop_request_exit_once(tmp_path):
    w = World(tmp_path)
    core = w.spawn()
    w.beat(core)
    s = w.sup()
    s.step()
    del w.procs[core]
    (w.runtime / "core.alive").unlink()  # clean exit
    assert s.run(poll_s=0, sleep=lambda _: None) == "user-stop"
    assert w.launches == []


def test_second_supervisor_exits_at_once(tmp_path, leased_port):
    held = ka.acquire_lock(tmp_path)
    try:
        r = subprocess.run([sys.executable, "-m", "server.al.keepalive", "--runtime",
                            str(tmp_path), "--port", str(leased_port)], cwd=str(ROOT),
                           env={**os.environ, paths.SIDECAR_ENV: str(tmp_path / "AL")},
                           capture_output=True, timeout=30, creationflags=FLAGS)
        assert r.returncode == 0
        assert not (tmp_path / ka.STATE_FILE).exists()  # it never took over
    finally:
        ka.release_lock(held)


# ------------------------------------------------------------- the scripts

@WIN51
@pytest.mark.parametrize("script", SCRIPTS, ids=[p.name for p in SCRIPTS])
def test_every_script_parses_in_powershell_51(script):
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-Command",
                        "$e=$null; [System.Management.Automation.Language.Parser]::ParseFile("
                        f"'{script}', [ref]$null, [ref]$e) | Out-Null; $e.Count"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "0", (script.name, r.stdout)


def test_run_script_is_idempotent_by_construction():
    text = RUN.read_text(encoding="ascii")
    # every component start is gated: core on health / the plan, supervisor
    # and overlay on the plan from server/al/procs.py
    assert "Test-AlHealth" in text and "server.al.procs', 'plan'" in text
    assert text.count("Start-AlDetached -FilePath") == 3
    assert "-contains 'supervisor'" in text and "-contains 'overlay'" in text
    assert "(no-op)" in text


def _stop(env, timeout_s=1):
    return subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                           "Bypass", "-File", str(STOP), "-TimeoutSec", str(timeout_s)],
                          cwd=str(ROOT), env=env, capture_output=True, text=True,
                          timeout=120, creationflags=FLAGS)


def _tmp_env(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir(exist_ok=True)
    env = dict(os.environ)
    env[paths.RUNTIME_ENV] = str(runtime)
    env[paths.SIDECAR_ENV] = str(tmp_path / "AL")
    env["AL_ELECTRON_DIR"] = str(tmp_path / "no-electron")
    return env, runtime


@WIN51
@pytest.mark.slow
def test_stop_script_twice_with_nothing_running(tmp_path):
    env, runtime = _tmp_env(tmp_path)
    for _ in range(2):
        r = _stop(env)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "core stopped cleanly" in r.stdout
    assert (runtime / "stop.request").exists()


@WIN51
@pytest.mark.slow
def test_stop_script_never_kills_a_python_that_reused_the_core_pid(tmp_path):
    # SUP-2: stop.ps1 force-stopped whatever python process held the pid in
    # a leftover core.alive; the recorded creation time now has to match.
    env, runtime = _tmp_env(tmp_path)
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, creationflags=FLAGS)
    try:
        time.sleep(0.3)
        real = ka.process_created(other.pid)
        assert real
        entry.write_heartbeat(runtime / "core.alive", other.pid, TEST_PORT,
                              created=real - 10_000_000)  # a core from 1 s earlier
        r = _stop(env)
        assert other.poll() is None, "stop.ps1 killed an unrelated python process"
        assert "not the AshLight core" in r.stdout, r.stdout + r.stderr
        assert r.returncode == 0, r.stdout + r.stderr
    finally:
        other.kill()
        other.wait(10)
