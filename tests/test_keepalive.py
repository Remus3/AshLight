"""CORE-KEEPALIVE: a core that dies unexpectedly is back within 2 minutes with
no operator input; a clean, user-requested stop is never restarted; a crash
loop backs off and gives up (logged) at a cap.

Unit tests drive server.al.keepalive.Keepalive with fakes. The end-to-end
test runs the real supervisor and the real core against a tmp runtime dir
(AL_RUNTIME_DIR) and a tmp sidecar (AL_SIDECAR_ROOT) on the top port of the
assigned block, so the live install is never touched.
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

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "scripts" / "run.ps1"
STOP = ROOT / "scripts" / "stop.ps1"
PS51 = shutil.which("powershell.exe") if sys.platform == "win32" else None
TEST_PORT = ports.PORT_BLOCK[1]  # never the live core's port


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


class World:
    """Fake processes + heartbeat file for the supervisor."""

    def __init__(self, tmp_path):
        self.runtime = tmp_path / "runtime"
        self.runtime.mkdir()
        self.clock = Clock()
        self.alive = set()
        self.health_ok = False  # nothing answers /api/health unless a test says so
        self.launches = []
        self.terminated = []
        self.next_pid = 500
        self.lines = []

    def beat(self, pid, at=None):
        entry.write_heartbeat(self.runtime / "core.alive", pid, TEST_PORT,
                              now=self.clock.t if at is None else at)

    def launch(self):
        self.next_pid += 1
        self.alive.add(self.next_pid)
        self.launches.append((self.clock.t, self.next_pid))
        return self.next_pid

    def terminate(self, pid):
        self.terminated.append(pid)
        self.alive.discard(pid)
        return True

    def crash(self, pid):
        self.alive.discard(pid)  # core.alive is left behind

    def clean_exit(self, pid):
        self.alive.discard(pid)
        (self.runtime / "core.alive").unlink()

    def sup(self, **kw):
        return ka.Keepalive(runtime=self.runtime, port=TEST_PORT, launch=self.launch,
                            pid_alive=lambda p: p in self.alive,
                            health=lambda: self.health_ok, terminate=self.terminate,
                            now=self.clock, log=self.lines.append, **kw)


def test_defaults_meet_the_two_minute_budget():
    # worst case: one poll to notice + the first backoff step
    assert ka.POLL_S + ka.BACKOFF_S[0] <= 30
    # a hung core (alive, stale heartbeat) is noticed and relaunched in time
    assert ka.STALE_S + ka.POLL_S + ka.BACKOFF_S[0] <= 120
    assert ka.STALE_S > entry.HEARTBEAT_S * 2  # two missed beats are not a hang
    assert list(ka.BACKOFF_S) == sorted(ka.BACKOFF_S)
    assert ka.CAP >= 3


def test_healthy_core_is_left_alone(tmp_path):
    w = World(tmp_path)
    w.alive.add(42)
    w.beat(42)
    s = w.sup()
    for _ in range(5):
        w.clock.t += ka.POLL_S
        w.beat(42)
        assert s.step() == "ok"
    assert w.launches == [] and w.terminated == []


def test_crash_is_restarted_within_two_minutes(tmp_path):
    w = World(tmp_path)
    w.alive.add(42)
    w.beat(42)
    s = w.sup()
    assert s.step() == "ok"
    died = w.clock.t
    w.crash(42)
    while not w.launches and w.clock.t - died < 300:
        w.clock.t += ka.POLL_S
        s.step()
    assert w.launches, w.lines
    assert w.launches[0][0] - died <= 120
    assert any("crash" in x for x in w.lines)


def test_clean_exit_is_not_restarted(tmp_path):
    w = World(tmp_path)
    w.alive.add(42)
    w.beat(42)
    s = w.sup()
    assert s.step() == "ok"
    w.clean_exit(42)
    w.clock.t += ka.POLL_S
    assert s.step() == "user-stop"
    assert w.launches == []
    assert any("stop" in x for x in w.lines)


def test_stop_request_wins_over_leftover_heartbeat(tmp_path):
    # stop.ps1 force-killed a core that did not exit in time: the heartbeat
    # is left behind, but stop.request says the user asked for it
    w = World(tmp_path)
    w.alive.add(42)
    w.beat(42)
    s = w.sup()
    assert s.step() == "ok"
    (w.runtime / ka.STOP_FILE).write_text("stop\n", encoding="ascii")
    w.crash(42)
    w.clock.t += ka.POLL_S
    assert s.step() == "user-stop"
    assert w.launches == []


def test_no_core_at_start_with_leftover_heartbeat_is_launched(tmp_path):
    w = World(tmp_path)
    w.beat(42)  # dead pid, heartbeat left by a crash before supervision began
    s = w.sup()
    t0 = w.clock.t
    while not w.launches and w.clock.t - t0 < 120:
        s.step()
        w.clock.t += ka.POLL_S
    assert w.launches


def test_crash_loop_backs_off_then_gives_up(tmp_path):
    w = World(tmp_path)
    w.alive.add(42)
    w.beat(42)
    s = w.sup()
    s.step()
    w.crash(42)
    result = None
    for _ in range(10000):
        w.clock.t += 1.0
        result = s.step()
        if result == "gave-up":
            break
        if w.launches and w.launches[-1][1] in w.alive:
            pid = w.launches[-1][1]
            w.beat(pid)
            w.clock.t += 1.0
            s.step()
            w.crash(pid)  # dies right after it starts
    assert result == "gave-up", w.lines
    assert len(w.launches) == ka.CAP
    gaps = [b[0] - a[0] for a, b in zip(w.launches, w.launches[1:])]
    assert gaps == sorted(gaps) and gaps[-1] > gaps[0]
    assert any("give up" in x for x in w.lines)
    state = json.loads((w.runtime / ka.STATE_FILE).read_text(encoding="ascii"))
    assert state["status"] == "gave-up"


def test_failed_start_without_heartbeat_counts_as_crash(tmp_path):
    w = World(tmp_path)
    s = w.sup()
    s.step()  # nothing there: launch
    w.clock.t += ka.BACKOFF_S[0] + ka.POLL_S
    s.step()
    assert w.launches
    w.crash(w.launches[-1][1])  # died before its first heartbeat
    n = len(w.launches)
    t0 = w.clock.t
    while len(w.launches) == n and w.clock.t - t0 < 300:
        w.clock.t += ka.POLL_S
        assert s.step() != "user-stop"
    assert len(w.launches) == n + 1


def test_hung_core_is_terminated_and_relaunched(tmp_path):
    w = World(tmp_path)
    w.alive.add(42)
    w.beat(42)
    s = w.sup()
    assert s.step() == "ok"
    w.health_ok = False
    w.clock.t += ka.STALE_S + 1
    s.step()
    assert w.terminated == [42]
    t0 = w.clock.t
    while not w.launches and w.clock.t - t0 < 120:
        w.clock.t += ka.POLL_S
        s.step()
    assert w.launches


def test_stale_heartbeat_but_healthy_is_left_alone(tmp_path):
    w = World(tmp_path)
    w.alive.add(42)
    w.beat(42)
    s = w.sup()
    w.health_ok = True
    w.clock.t += ka.STALE_S + 1
    assert s.step() == "ok"
    assert w.terminated == []


def test_core_answering_without_heartbeat_is_not_duplicated(tmp_path):
    # a core from before CORE-DETACH writes no core.alive but holds the port:
    # launching a second one would only fail to bind and spin to a give-up
    w = World(tmp_path)
    w.health_ok = True
    s = w.sup()
    for _ in range(50):
        assert s.step() == "ok"
        w.clock.t += ka.POLL_S
    assert w.launches == []
    w.health_ok = False  # it died: no heartbeat, nothing answering -> start one
    t0 = w.clock.t
    while not w.launches and w.clock.t - t0 < 120:
        s.step()
        w.clock.t += ka.POLL_S
    assert w.launches


def test_pid_alive_uses_no_signal(tmp_path):
    assert ka.pid_alive(os.getpid())
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    assert not ka.pid_alive(p.pid)
    assert not ka.pid_alive(0)
    # os.kill(pid, 0) TERMINATES the process on Windows; never use it
    src = Path(ka.__file__).read_text(encoding="ascii")
    assert "os.kill(" not in src


def test_single_instance_lock(tmp_path):
    a = ka.acquire_lock(tmp_path)
    assert a is not None
    try:
        assert ka.acquire_lock(tmp_path) is None
    finally:
        ka.release_lock(a)
    b = ka.acquire_lock(tmp_path)
    assert b is not None
    ka.release_lock(b)


def test_core_honours_stop_request(tmp_path):
    f = tmp_path / ka.STOP_FILE
    assert not entry.stop_requested(f)
    f.write_text("stop\n", encoding="ascii")
    assert entry.stop_requested(f)
    entry.clear_stop_request(f)
    assert not f.exists()
    text = Path(entry.__file__).read_text(encoding="ascii")
    assert "stop_requested(" in text and "clear_stop_request(" in text


def test_runtime_dir_override(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.RUNTIME_ENV, str(tmp_path / "rt"))
    assert paths.runtime_dir() == (tmp_path / "rt").resolve()
    assert paths.token_file() == (tmp_path / "rt").resolve() / "token"
    monkeypatch.delenv(paths.RUNTIME_ENV)
    assert paths.runtime_dir() == ROOT / "ops" / "runtime"


def test_run_starts_supervisor_and_clears_stop_request():
    text = RUN.read_text(encoding="ascii")
    assert "server.al.keepalive" in text
    assert "stop.request" in text
    for line in text.splitlines():
        if "server.al.keepalive" in line:
            assert "Start-Process" not in line, line


def test_stop_script_writes_stop_request():
    text = STOP.read_text(encoding="ascii")
    assert "stop.request" in text
    assert "core.alive" in text


@pytest.mark.skipif(PS51 is None, reason="Windows PowerShell 5.1 only")
def test_stop_script_parses_in_powershell_51():
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-Command",
                        "$e=$null; [System.Management.Automation.Language.Parser]::ParseFile("
                        f"'{STOP}', [ref]$null, [ref]$e) | Out-Null; $e.Count"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "0", r.stdout


def _read_hb(path):
    try:
        return json.loads(path.read_text(encoding="ascii"))
    except (OSError, ValueError):
        return None


def _wait(pred, timeout):
    end = time.time() + timeout
    while time.time() < end:
        v = pred()
        if v:
            return v
        time.sleep(0.2)
    return None


@pytest.mark.slow
@pytest.mark.server
def test_end_to_end_real_core_restart_and_user_stop(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    env = dict(os.environ)
    env[paths.RUNTIME_ENV] = str(runtime)
    env[paths.SIDECAR_ENV] = str(tmp_path / "AL")
    env["AL_HEARTBEAT_S"] = "0.5"
    cmd = [sys.executable, "-m", "server.al.keepalive", "--port", str(TEST_PORT),
           "--poll", "0.5", "--backoff", "0.5,1,2", "--core-args", "--no-tail"]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    sup = subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=flags)
    hb = runtime / "core.alive"
    first = None
    try:
        first = _wait(lambda: (_read_hb(hb) or {}).get("pid"), 30)
        assert first, "core never wrote a heartbeat"
        assert _read_hb(hb)["port"] == TEST_PORT
        # kill the core hard: the supervisor must bring a new one back
        subprocess.run(["taskkill", "/PID", str(first), "/F"] if os.name == "nt"
                       else ["kill", "-9", str(first)], capture_output=True)
        second = _wait(lambda: ((_read_hb(hb) or {}).get("pid") not in (None, first)
                                and _read_hb(hb)["pid"]), 30)
        assert second, "core was not restarted"
        assert ka.pid_alive(second)
        # a user stop: the core exits cleanly and is NOT restarted
        (runtime / ka.STOP_FILE).write_text("stop\n", encoding="ascii")
        assert sup.wait(timeout=30) == 0
        assert not hb.exists()
        assert _wait(lambda: not ka.pid_alive(second), 10)
        log = (tmp_path / "AL" / "Logs" / "keepalive.log").read_text(encoding="ascii")
        assert "crash" in log and "user stop" in log
    finally:
        if sup.poll() is None:
            sup.kill()
        data = _read_hb(hb) or {}
        for pid in {first, data.get("pid")}:
            if pid and pid != 13388 and ka.pid_alive(pid):
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
