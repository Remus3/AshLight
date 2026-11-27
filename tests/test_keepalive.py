"""CORE-KEEPALIVE: a core that dies unexpectedly is back within 2 minutes with
no operator input; a clean, user-requested stop is never restarted; a crash
loop backs off and gives up (logged) at a cap.

Unit tests drive server.al.keepalive.Keepalive with fakes. The end-to-end
test runs the real supervisor and the real core against a tmp runtime dir
(AL_RUNTIME_DIR) and a tmp sidecar (AL_SIDECAR_ROOT) on a leased test port
(tests/tc_live_util.lease_port, TEST-PORT-LEASE), so the live install is never
touched.
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
from server.al import hello, paths, ports
from tc_live_util import leased_port  # noqa: F401 (a fixture)

# TEST-MARKS (research 0049 R3): the three supervisor files share one
# xdist worker (they start real cores and supervisors).
pytestmark = pytest.mark.xdist_group("supervisor")
ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "scripts" / "run.ps1"
STOP = ROOT / "scripts" / "stop.ps1"
PS51 = shutil.which("powershell.exe") if sys.platform == "win32" else None
TEST_PORT = ports.PORT_BLOCK[1]  # a number in fake heartbeats only; real binds lease


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
        kw.setdefault("wall", self.clock)  # one fake clock unless a test splits them
        return ka.Keepalive(runtime=self.runtime, port=TEST_PORT, launch=self.launch,
                            pid_alive=lambda p: p in self.alive,
                            health=lambda: self.health_ok, terminate=self.terminate,
                            now=self.clock, log=self.lines.append, **kw)

    def poll_until(self, s, pred, limit_s=600.0, wall=None, beat=None):
        """Step every POLL_S (a split wall clock moves too; the `beat` pid
        writes a heartbeat every HEARTBEAT_S) until pred(); its time or None."""
        end = self.clock.t + limit_s
        last_beat = self.clock.t
        while self.clock.t < end:
            self.clock.t += ka.POLL_S
            if wall is not None:
                wall.t += ka.POLL_S
            if beat is not None and self.clock.t - last_beat >= entry.HEARTBEAT_S:
                self.beat(beat, at=wall.t if wall is not None else None)
                last_beat = self.clock.t
            s.step()
            if pred():
                return self.clock.t
        return None


def test_defaults_meet_the_two_minute_budget():
    # worst case: one poll to notice + the first backoff step
    assert ka.POLL_S + ka.BACKOFF_S[0] <= 30
    # a hung core (alive, stale heartbeat) is noticed and relaunched in time:
    # stale age, one poll to see it, the second health check RECHECK_S
    # later (RUN-SUPERVISOR-CLOCK), then the first backoff step: 102 s
    assert ka.STALE_S + ka.POLL_S + ka.RECHECK_S + ka.BACKOFF_S[0] <= 120
    assert ka.RECHECK_S >= ka.POLL_S  # the second check is a later poll
    assert ka.LOOP_STALE_S < ka.STALE_S
    assert ka.POLL_GAP_S > 2 * ka.POLL_S  # a normal poll is never a gap
    assert ka.GAP_GRACE_S > entry.HEARTBEAT_S  # a woken core can beat again
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
    hung = w.clock.t
    killed = w.poll_until(s, lambda: bool(w.terminated), limit_s=300)
    assert w.terminated == [42]
    # two failed checks RECHECK_S apart (RUN-SUPERVISOR-CLOCK)
    assert killed - hung <= ka.STALE_S + 2 * ka.POLL_S + ka.RECHECK_S
    assert sum("checking again" in x for x in w.lines) == 1
    launched = w.poll_until(s, lambda: bool(w.launches), limit_s=120)
    assert launched is not None and launched - hung <= 120


def test_stale_heartbeat_but_healthy_is_left_alone(tmp_path):
    w = World(tmp_path)
    w.alive.add(42)
    w.beat(42)
    s = w.sup()
    w.health_ok = True
    w.clock.t += ka.STALE_S + 1
    assert s.step() == "ok"
    assert w.terminated == []


def test_clock_step_back_3600_s_still_restarts_on_time(tmp_path):
    # C19 (F-136): the wall clock steps forward an hour, then back an hour,
    # while the core beats. Every interval runs on the monotonic clock, so
    # neither step kills a beating core, and a hang after the step back is
    # still relaunched inside the 2 minute budget (the old wall-clock age
    # read -3600 s there and waited an hour).
    w = World(tmp_path)
    wall = Clock(50000.0)
    w.alive.add(42)
    w.beat(42, at=wall.t)
    s = w.sup(wall=wall)
    assert s.step() == "ok"
    killed = lambda: bool(w.terminated)  # noqa: E731
    assert w.poll_until(s, killed, limit_s=120, wall=wall, beat=42) is None
    wall.t += 3600.0  # forward step; nothing answers /api/health either
    assert w.poll_until(s, killed, limit_s=120, wall=wall, beat=42) is None
    wall.t -= 3600.0  # back step
    assert w.poll_until(s, killed, limit_s=120, wall=wall, beat=42) is None
    w.beat(42, at=wall.t)
    hung = w.clock.t  # the last beat; the core hangs from here
    launched = w.poll_until(s, lambda: bool(w.launches), limit_s=300, wall=wall)
    assert w.terminated == [42], w.lines
    assert launched is not None and launched - hung <= 120, w.lines
    assert not any("poll gap" in x for x in w.lines)


def test_poll_gap_then_one_failed_check_does_not_kill(tmp_path):
    # C20 (F-136): the machine slept 10 minutes; the core slept too, so its
    # heartbeat is old and the first checks after waking fail. A poll gap
    # opens GAP_GRACE_S with no kill, and one failed check never kills.
    w = World(tmp_path)
    w.alive.add(42)
    w.beat(42)
    s = w.sup()
    assert s.step() == "ok"
    w.clock.t += 600.0  # asleep: no step, no beat
    woke = w.clock.t
    assert s.step() == "ok"
    assert s.grace_until == woke + ka.GAP_GRACE_S
    assert any("poll gap of 600 s" in x for x in w.lines)
    w.clock.t += ka.POLL_S
    assert s.step() == "ok"  # a failed check inside the grace: no kill
    w.beat(42)  # the woken core beats again
    assert w.poll_until(s, lambda: bool(w.terminated), limit_s=300, beat=42) is None
    assert w.terminated == [] and w.launches == []


def test_one_failed_check_only_checks_again(tmp_path):
    # without a gap, the first failed check on a stale heartbeat only
    # re-checks; a passing check in between starts the count over
    (tmp_path / "w").mkdir()
    w = World(tmp_path / "w")
    w.alive.add(7)
    w.beat(7)
    s = w.sup()
    assert s.step() == "ok"
    t = w.poll_until(s, lambda: s._failed_at is not None, limit_s=300)
    assert t is not None and w.terminated == []
    w.health_ok = True
    w.clock.t += ka.RECHECK_S
    assert s.step() == "ok" and s._failed_at is None and w.terminated == []
    w.health_ok = False
    w.clock.t += ka.POLL_S
    assert s.step() == "checking" and w.terminated == []
    w.clock.t += ka.RECHECK_S
    s.step()
    assert w.terminated == [7]


def test_stale_heartbeat_health_ok_loop_age_300_relaunches(tmp_path):
    # C21 (F-136): the HTTP thread answers but the core loop has not run
    # for 5 minutes (loop_age_s 300 > LOOP_STALE_S): a failed check; two of
    # them on a stale heartbeat terminate and relaunch the core
    (tmp_path / "a").mkdir()
    w = World(tmp_path / "a")
    w.alive.add(42)
    w.beat(42)
    w.health_ok = {"ok": True, "loop_age_s": 300.0}
    kill = w.terminate
    # the killed core stops answering
    w.terminate = lambda pid: (setattr(w, "health_ok", False), kill(pid))[1]
    s = w.sup()
    assert s.step() == "ok"
    hung = w.clock.t
    launched = w.poll_until(s, lambda: bool(w.launches), limit_s=300)
    assert w.terminated == [42], w.lines
    assert launched is not None and launched - hung <= 120
    assert any("two failed checks" in x for x in w.lines)
    # a fresh loop with a stale heartbeat is left alone (a slow disk)
    (tmp_path / "b").mkdir()
    w2 = World(tmp_path / "b")
    w2.alive.add(7)
    w2.beat(7)
    s2 = w2.sup()
    w2.health_ok = {"ok": True, "loop_age_s": 0.4}
    assert w2.poll_until(s2, lambda: bool(w2.terminated), limit_s=300) is None
    assert ka.check_passed({"ok": True, "loop_age_s": None})  # an older core
    assert not ka.check_passed({"ok": True, "loop_age_s": ka.LOOP_STALE_S + 0.1})
    assert not ka.check_passed({"ok": False, "loop_age_s": 0.1})
    assert ka.answered({"ok": True, "loop_age_s": 300.0})  # still a core


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
def test_end_to_end_real_core_restart_and_user_stop(tmp_path, leased_port):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    env = dict(os.environ)
    env[paths.RUNTIME_ENV] = str(runtime)
    env[paths.SIDECAR_ENV] = str(tmp_path / "AL")
    env["AL_HEARTBEAT_S"] = "0.2"
    cmd = [sys.executable, "-m", "server.al.keepalive", "--port", str(leased_port),
           "--poll", "0.1", "--backoff", "0.1,0.2,0.4", "--core-args", "--no-tail"]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    sup = subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=flags)
    hb = runtime / "core.alive"
    first = None
    try:
        first = _wait(lambda: (_read_hb(hb) or {}).get("pid"), 30)
        assert first, "core never wrote a heartbeat"
        assert _read_hb(hb)["port"] == leased_port
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
            if pid and ka.pid_alive(pid):
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)


def _counting_proxy():
    """A listener on an ephemeral loopback port that counts connections."""
    import socket
    import threading
    hits = []
    sock = socket.socket()
    sock.bind((ports.LOOPBACK, 0))
    sock.listen(8)

    def accept():
        while True:
            try:
                conn, _ = sock.accept()
            except OSError:
                return
            hits.append(1)
            conn.close()
    threading.Thread(target=accept, daemon=True).start()
    return sock, hits


def _test_core(token, health_body=b"{}"):
    """A stand-in core on an ephemeral port that answers /api/health (with
    health_body) and, SEC-HELLO-CORE, the /api/hello proof (the supervisor
    checks it first)."""
    import http.server
    import threading

    from server.al import hello

    class Health(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"{}"
            if self.path == hello.PATH:
                nonce = self.headers.get(hello.NONCE_HEADER)
                ok = hello.check_client(token, nonce, self.headers.get(hello.PROOF_HEADER))
                if ok:
                    port = self.server.server_address[1]
                    body = json.dumps(hello.answer(token, nonce, port)).encode("ascii")
            else:
                ok = self.path == "/api/health" and self.headers.get("X-AL-Token") == token
                body = health_body if ok else body
            self.send_response(200 if ok else 403)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass
    srv = http.server.HTTPServer((ports.LOOPBACK, 0), Health)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_health_check_ignores_proxy_settings(monkeypatch, tmp_path):
    proxy, hits = _counting_proxy()
    srv = _test_core("tok")
    try:
        url = f"http://{ports.LOOPBACK}:{proxy.getsockname()[1]}"
        for name in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY",
                     "all_proxy", "ALL_PROXY"):
            monkeypatch.setenv(name, url)
        for name in ("no_proxy", "NO_PROXY"):
            monkeypatch.delenv(name, raising=False)
        (tmp_path / "token").write_text("tok\n", encoding="ascii")
        hello.forget()
        assert ka.health_check(tmp_path, srv.server_address[1], timeout=5)
        assert hits == []
    finally:
        srv.shutdown()
        srv.server_close()
        proxy.close()


@pytest.mark.parametrize("body, age", [(b'{"ok": true, "loop_age_s": 300.5}', 300.5),
                                       (b'{"ok": true, "loop_age_s": null}', None),
                                       (b'{"ok": true}', None),
                                       (b'not json', None)])
def test_health_check_detail_reads_loop_age(tmp_path, body, age):
    # RUN-SUPERVISOR-CLOCK: the supervisor's check reads loop_age_s from
    # /api/health; the plain bool form is unchanged for other callers
    srv = _test_core("tok", health_body=body)
    try:
        (tmp_path / "token").write_text("tok\n", encoding="ascii")
        hello.forget()
        port = srv.server_address[1]
        got = ka.health_check(tmp_path, port, timeout=5, detail=True)
        assert got == {"ok": True, "loop_age_s": age}
        assert ka.health_check(tmp_path, port, timeout=5) is True
        # the supervisor's default check stays a bool and keeps the loop age
        sup = ka.Keepalive(runtime=tmp_path, port=port, launch=lambda: 1,
                           pid_alive=lambda p: False)
        assert sup._health() is True and sup._loop_age == age
        (tmp_path / "token").unlink()
        got = ka.health_check(tmp_path, port, timeout=5, detail=True)
        assert got == {"ok": False, "loop_age_s": None}
    finally:
        srv.shutdown()
        srv.server_close()


# -- RUN-CALC-PRIORITY (F-107): the preflight child runs below normal ---------

_OWN_CLASS = ("import ctypes, sys\n"
              "k = ctypes.WinDLL('kernel32')\n"
              "k.GetCurrentProcess.restype = ctypes.c_void_p\n"
              "k.GetPriorityClass.argtypes = (ctypes.c_void_p,)\n"
              "print(k.GetPriorityClass(k.GetCurrentProcess()))\n")


def test_preflight_child_has_below_normal_priority(tmp_path, monkeypatch):
    """run_preflight starts its child with the below-normal class: a real
    child started with the same flags reads its own class back. The core
    launcher (_Launcher) stays at normal."""
    seen = {}

    class R:
        returncode = 0
        stdout = b""
        stderr = b""

    def run(cmd, **kw):
        seen.update(kw)
        if os.name == "nt":
            got = subprocess.run([sys.executable, "-I", "-c", _OWN_CLASS],
                                 stdin=subprocess.DEVNULL, capture_output=True,
                                 timeout=60, creationflags=kw["creationflags"])
            seen["class"] = int(got.stdout.strip())
        return R()
    assert ka.run_preflight(tmp_path, run=run) == (True, None)
    if os.name == "nt":
        assert seen["creationflags"] & ka.prio.BELOW_NORMAL
        assert seen["class"] == ka.prio.BELOW_NORMAL
    else:
        assert seen["creationflags"] == 0

    launched = {}

    class Child:
        pid = 99

        def poll(self):
            return None

    def popen(cmd, **kw):
        launched.update(kw)
        return Child()
    monkeypatch.setattr(ka.subprocess, "Popen", popen)
    assert ka._Launcher(["core"])() == 99
    assert not launched["creationflags"] & ka.prio.BELOW_NORMAL  # core stays normal


def test_supervisor_does_not_import_urllib_at_start(tmp_path):
    # RUN-PERF-IDLE-BACKOFF (F-178, budget B9): the supervisor imports the
    # HTTP client only inside the health probe, so its start and a poll that
    # needs no probe load neither urllib nor http.client
    code = (
        "import sys, pathlib\n"
        # the interpreter's own loads stay out (3.11 pathlib loads urllib.parse)
        "base = set(sys.modules)\n"
        "from server.al import keepalive as ka\n"
        "ka.build_parser().parse_args([])\n"
        "sup = ka.Keepalive(sys.argv[1], int(sys.argv[2]), launch=lambda: 1,\n"
        "                   pid_alive=lambda p: False, health=lambda: False)\n"
        "sup.step()\n"
        "bad = sorted(m for m in set(sys.modules) - base\n"
        "             if m.split('.')[0] in ('urllib', 'http') or m.endswith('.hello'))\n"
        "print(','.join(bad))\n")
    env = dict(os.environ, AL_RUNTIME_DIR=str(tmp_path))
    out = subprocess.run([sys.executable, "-c", code, str(tmp_path), str(TEST_PORT)],
                         cwd=ROOT,
                         env=env, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == ""
    # the probe itself still builds its no-proxy opener on first use
    assert ka._opener() is ka._opener()
