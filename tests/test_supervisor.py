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
                            now=self.now, wall=kw.pop("wall", self.now),
                            log=self.lines.append, **kw)

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
    for _ in range(400):  # every poll (a 90 s jump is a poll gap: no kill)
        w.t += ka.POLL_S
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


# ------------------------------------- RUN-SUPERVISOR-CLOCK: last restart

def _state(w):
    return json.loads((w.runtime / ka.STATE_FILE).read_text("ascii"))


def test_restart_is_recorded_with_its_reason(tmp_path):
    w = World(tmp_path)
    s = w.sup()
    w.run_until(s, lambda r: r == "launched")  # a first start: not a restart
    assert _state(w)["last_restart"] is None
    pid = w.launches[-1][1]
    w.beat(pid)
    w.t += 1
    assert s.step() == "ok"
    del w.procs[pid]  # crash, core.alive left behind
    w.run_until(s, lambda r: r == "launched")
    rec = _state(w)["last_restart"]
    assert rec == {"at": w.t, "reason": "crash"}
    # a hang: two failed checks, terminate, relaunch
    pid = w.launches[-1][1]
    w.beat(pid)
    w.t += 1
    assert s.step() == "ok"
    w.run_until(s, lambda r: r == "launched")
    assert pid in w.terminated
    assert _state(w)["last_restart"]["reason"] == "hung"
    # a new supervisor (run.ps1 again) keeps the record
    s2 = w.sup()
    assert s2.last_restart == _state(w)["last_restart"]
    s2._write_state("started")
    assert _state(w)["last_restart"]["reason"] == "hung"


def test_start_timeout_and_gave_up_records(tmp_path):
    w = World(tmp_path)
    s = w.sup(start_grace_s=30.0)
    w.run_until(s, lambda r: r == "launched")
    w.run_until(s, lambda r: len(w.launches) == 2)
    assert _state(w)["last_restart"]["reason"] == "start-timeout"
    # a launch that fails records nothing new
    (tmp_path / "b").mkdir()
    w2 = World(tmp_path / "b")
    w2.launch_error = OSError("python not found")
    s2 = w2.sup(cap=2, backoff=(1.0,))
    assert w2.run_until(s2, lambda r: r == "gave-up", limit_s=600) == "gave-up"
    assert _state(w2)["last_restart"] is None


def test_read_last_restart_rejects_bad_records(tmp_path):
    f = tmp_path / ka.STATE_FILE
    assert ka.read_last_restart(f) is None  # no file
    for bad in ('{"last_restart": {"at": 1, "reason": "reload"}}',
                '{"last_restart": {"at": true, "reason": "hung"}}',
                '{"last_restart": {"at": "1", "reason": "hung"}}',
                '{"last_restart": [1]}', '[1]', 'not json'):
        f.write_text(bad, encoding="ascii")
        assert ka.read_last_restart(f) is None, bad
    f.write_text('{"last_restart": {"at": 12, "reason": "hung"}}', encoding="ascii")
    assert ka.read_last_restart(f) == {"at": 12.0, "reason": "hung"}


def test_last_restart_row_shows_for_10_minutes(tmp_path):
    from server.al import diag, plug
    from server.al.plug import supervisor as sp

    class FakeCore:
        runtime = tmp_path

    core = FakeCore()
    assert sp.facts(core, 0.0) == {"supervisor_restart": None}  # no file
    at = 1_800_000_000.0
    (tmp_path / ka.STATE_FILE).write_text(json.dumps(
        {"pid": 1, "status": "starting", "last_restart": {"at": at, "reason": "hung"}}),
        encoding="ascii")
    f = sp.facts(core, at)
    assert f == {"supervisor_restart": {"at": at, "reason": "hung"}}
    clock = time.strftime("%H:%M", time.localtime(at))
    want = f"AshLight restarted its core at {clock} (it had stopped answering)."
    for age in (0.0, 1.0, 300.0, 599.0):
        row = sp.rows(f, at + age)
        assert row == {"id": "supervisor_restart", "label": "Keepalive",
                       "status": "note", "detail": want}, age
    for age in (600.0, 601.0, 3600.0, -3600.0):
        assert sp.rows(f, at + age) is None, age
    for reason, words in sp.REASON_WORDS.items():
        assert sp.rows({"supervisor_restart": {"at": at, "reason": reason}}, at)[
            "detail"].endswith(f"({words}).")
    assert set(sp.REASON_WORDS) == set(ka.RESTART_REASONS)
    assert sp.rows({"supervisor_restart": None}, at) is None
    assert sp.rows({}, at) is None
    # discovered through the plug seam and shown in Checks
    assert "supervisor" in [n for _, n, _ in plug.modules()]
    ids = [r["id"] for r in diag.checks({"supervisor_restart": f["supervisor_restart"]},
                                        at + 60.0)]
    assert "supervisor_restart" in ids
    ids = [r["id"] for r in diag.checks({"supervisor_restart": f["supervisor_restart"]},
                                        at + 601.0)]
    assert "supervisor_restart" not in ids


def test_health_reports_loop_age(tmp_path):
    # /api/health gains loop_age_s from core.loop_at (monotonic), null
    # before the first loop pass; the supervisor fails a check over 60 s
    import http.client
    import threading

    from server.al.core import Core
    from server.al.http import serve

    token = "k" * 48
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    server = serve(core, token, port=0, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True)
    t.start()

    def health():
        conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
        conn.request("GET", "/api/health", headers={
            "Host": f"127.0.0.1:{server.port}", "X-AL-Token": token})
        r = conn.getresponse()
        body = json.loads(r.read())
        conn.close()
        assert r.status == 200
        return body

    try:
        core.loop_at = None
        assert health()["loop_age_s"] is None
        core.loop_at = time.monotonic() - 300.0
        age = health()["loop_age_s"]
        assert 300.0 <= age < 330.0
        assert not ka.check_passed({"ok": True, "loop_age_s": age})
        core.loop_at = time.monotonic()
        assert ka.check_passed({"ok": True, "loop_age_s": health()["loop_age_s"]})
    finally:
        server.stop()
        core.close()


# --------------------- RUN-SECOND-LINE-PY (F-127): adopt and second line

def test_slow_core_start_gives_one_core_and_a_supervisor(tmp_path):
    # C16: run.ps1 used to start the supervisor only after the core answered
    # within 15 s; a slow start left a core and no supervisor. Now the
    # supervisor starts first and adopts the core's pid while it starts.
    w = World(tmp_path)
    core = w.spawn()  # launched by run.ps1, no heartbeat yet
    s = w.sup(adopt_pid=core)
    assert s.pid == core and s.launch_grace_s == ka.ADOPT_GRACE_S
    assert _state(w)["status"] == "starting" and _state(w)["core_pid"] == core
    for _ in range(8):  # 40 s without a heartbeat: still starting
        w.t += ka.POLL_S
        assert s.step() == "starting"
    w.beat(core)
    w.t += ka.POLL_S
    assert s.step() == "ok" and s.pid == core
    assert w.launches == [] and w.terminated == []
    # without the pid the same start would get a second core next to it
    (tmp_path / "b").mkdir()
    w2 = World(tmp_path / "b")
    w2.spawn()
    s2 = w2.sup()
    w2.run_until(s2, lambda r: r == "launched", limit_s=30)
    assert len(w2.launches) == 1


def test_adopted_core_that_never_beats_is_retried_once_after_the_grace(tmp_path):
    w = World(tmp_path)
    core = w.spawn()
    s = w.sup(adopt_pid=core)
    w.run_until(s, lambda r: bool(w.launches), limit_s=ka.ADOPT_GRACE_S * 3)
    assert w.terminated == [core] and len(w.launches) == 1
    assert w.launches[0][0] - 1000.0 > ka.ADOPT_GRACE_S
    assert _state(w)["last_restart"]["reason"] == "start-timeout"


def test_adopted_pid_reused_before_its_heartbeat_is_never_terminated(tmp_path):
    w = World(tmp_path)
    core = w.spawn(created=111)
    s = w.sup(adopt_pid=core)
    w.procs[core] = 222  # the core died and another process got its pid
    w.run_until(s, lambda r: bool(w.launches), limit_s=ka.ADOPT_GRACE_S * 3)
    assert w.terminated == [] and len(w.launches) == 1


def test_dead_pid_is_not_adopted(tmp_path):
    w = World(tmp_path)
    s = w.sup(adopt_pid=4242)
    assert s.pid is None and s.launched_at is None
    assert any("not running" in x for x in w.lines)
    assert ka.build_parser().parse_args(["--adopt-pid", "77"]).adopt_pid == 77
    assert ka.build_parser().parse_args([]).adopt_pid == 0


def test_run_script_starts_the_supervisor_before_the_health_wait():
    text = RUN.read_text(encoding="ascii")
    sup = text.index("Get-AlDetachArgs 'server.al.keepalive'")
    core = text.index("Get-AlDetachArgs 'server.al' @('--quiet'")
    wait = text.index("Wait-AlCore $waitSince")
    assert core < sup < wait
    assert "'--adopt-pid', [string]$corePid" in text
    assert text.count("Wait-AlCore") == 2  # the function and its one call


class _Child:
    def __init__(self, pid):
        self.pid = pid

    def poll(self):
        return None


def _line(tmp_path, live=False, fail=None):
    from server.al.plug import secondline as sl
    clock = {"t": 50.0}
    started = []

    def start(port):
        if fail:
            raise fail
        started.append(port)
        return _Child(9000 + len(started))

    line = sl.SecondLine(tmp_path, lambda: TEST_PORT, live=lambda: live,
                         start=start, now=lambda: clock["t"],
                         wall=lambda: 1_800_000_000.0 + clock["t"])
    return sl, line, clock, started


def _ticks(line, clock, n, step=5.0):
    out = []
    for _ in range(n):
        out.append(line.tick())
        clock["t"] += step
    return out


def test_killed_supervisor_is_restarted_by_the_core(tmp_path):
    # C17: the supervisor restarts the core, the core restarts the supervisor
    sl, line, clock, started = _line(tmp_path)
    assert _ticks(line, clock, 3) == ["missing", "missing", "started"]
    assert started == [TEST_PORT]
    clock["t"] -= 4.0
    assert line.tick() is None  # not due before the next Checks tick
    f = {"supervisor_started": line.started_at}
    row = sl.rows(f, line.started_at + 30.0)
    assert row == {"id": "supervisor_started", "label": "Keepalive", "status": "note",
                   "detail": "Keepalive was not running; AshLight started it again."}
    assert sl.rows(f, line.started_at + sl.SHOW_S) is None
    assert sl.rows({"supervisor_started": None}, 0.0) is None
    # a live supervisor resets the count
    _, line2, clock2, started2 = _line(tmp_path, live=True)
    assert _ticks(line2, clock2, 5) == ["live"] * 5 and started2 == []


def test_killed_supervisor_is_restarted_by_the_core_on_a_real_lock(tmp_path):
    # the liveness signal is the real one: the supervisor's lock in the runtime
    from server.al import procs
    from server.al.plug import secondline as sl
    clock = {"t": 0.0}
    started = []
    line = sl.SecondLine(tmp_path, lambda: TEST_PORT, start=started.append,
                         now=lambda: clock["t"])
    held = ka.acquire_lock(tmp_path)
    try:
        assert procs.supervisor_live(tmp_path)
        assert _ticks(line, clock, 4) == ["live"] * 4
    finally:
        ka.release_lock(held)  # the supervisor was killed
    assert _ticks(line, clock, 3) == ["missing", "missing", "started"]
    assert started == [TEST_PORT]


def test_no_supervisor_restart_under_stop_request(tmp_path):
    sl, line, clock, started = _line(tmp_path)
    (tmp_path / ka.STOP_FILE).write_text("stop", encoding="ascii")
    assert _ticks(line, clock, 10) == ["stop"] * 10
    assert started == [] and line.started_at is None
    (tmp_path / ka.STOP_FILE).unlink()  # the count starts over
    assert _ticks(line, clock, 3) == ["missing", "missing", "started"]


def test_supervisor_restart_at_most_once_per_5_min(tmp_path):
    sl, line, clock, started = _line(tmp_path)
    got = _ticks(line, clock, int(sl.EVERY_S / 5.0) + 3)
    assert got.count("started") == 2 and len(started) == 2
    first, second = [i for i, r in enumerate(got) if r == "started"]
    assert (second - first) * 5.0 >= sl.EVERY_S
    # a start that fails counts against the cap too
    _, bad, bclock, _ = _line(tmp_path, fail=OSError("no python"))
    out = _ticks(bad, bclock, 30)
    assert out.count("failed") == 1 and "started" not in out
    assert bad.started_at is None


def test_second_line_runs_only_in_the_real_core(tmp_path):
    from server.al.plug import secondline as sl

    class FakeCore:
        runtime = tmp_path
        port = TEST_PORT
        DIAG_TICK_S = 5.0

        def __init__(self, real):
            self._real = real
            self.ticks = []

        def add_tick(self, name, fn):
            self.ticks.append(name)

    for real, env, want in ((True, {}, True), (False, {}, False),
                            (True, {paths.RUNTIME_ENV: str(tmp_path)}, False)):
        assert sl.enabled(FakeCore(real), environ=env) is want
    test_core = FakeCore(False)
    sl.attach(test_core)
    assert test_core.ticks == []
    assert sl.facts(test_core, 0.0) == {"supervisor_started": None}


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
