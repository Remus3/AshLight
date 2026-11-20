"""HOT-RELOAD (decision 0042): data files re-read on change with the last
good copy kept on a bad edit, web/ edits pushed to the dashboard as an SSE
"reload", and server/ .py edits restarting the core through the supervisor
after a preflight, never looping on broken code."""

import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

import srcpaths
from ci_timing import ci_scale
from server.al import __main__ as entry
from server.al import acts, diag, hotreload, paths, ports
from server.al import keepalive as ka
from server.al import zonenotes
from server.al.core import Core
from server.al.http import serve

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "h" * 48
TEST_PORT = ports.PORT_BLOCK[1] - 1  # never the live core's port


def _bump(p, text):
    """Write text and move the mtime past the last one (the OS clock can
    give two quick writes the same mtime)."""
    try:
        prev = os.stat(p).st_mtime_ns
    except OSError:
        prev = 0
    p.write_text(text, encoding="utf-8")
    st = os.stat(p)
    os.utime(p, ns=(st.st_atime_ns, max(st.st_mtime_ns, prev) + 2_000_000_000))


# ---- Watched / Registry --------------------------------------------------

def test_watched_reloads_and_keeps_last_good(tmp_path):
    reg = hotreload.Registry()
    f = tmp_path / "d.json"
    seen = []
    w = hotreload.Watched(f, hotreload.load_json, name="Test data", default=dict,
                          check=hotreload.check_json(), registry=reg,
                          on_change=seen.append)
    assert w.get() == {} and w.error is None          # missing -> default
    _bump(f, '{"a": 1}')
    assert w.get() == {"a": 1}
    _bump(f, '{"a": 2}')
    assert w.get() == {"a": 2} and seen == [{"a": 2}]
    _bump(f, '{"a": ')                                  # a bad edit
    assert w.get() == {"a": 2}                          # last good copy
    assert w.error == ("Test data did not load (not valid JSON at line 1). "
                       "The last good copy stays in use.")
    assert reg.notes() == [w.error]
    _bump(f, "[1]")                                     # wrong kind
    assert w.get() == {"a": 2} and w.error
    _bump(f, '{"a": 3}')
    assert w.get() == {"a": 3} and w.error is None and reg.notes() == []
    f.unlink()
    assert w.get() == {}


def test_register_joins_the_module_registry_weakly(tmp_path):
    f = tmp_path / "x.json"
    f.write_text('{"k": 1}', encoding="utf-8")
    w = hotreload.register(f, hotreload.load_json, name="X")
    assert w in hotreload.REGISTRY.watches()
    _bump(f, "{bad")
    hotreload.REGISTRY.poll()
    assert w.error in hotreload.REGISTRY.notes()
    del w
    import gc
    gc.collect()
    assert all(x.name != "X" for x in hotreload.REGISTRY.watches())


def test_error_note_carries_no_path(tmp_path):
    w = hotreload.Watched(tmp_path / "d.json", lambda p: (_ for _ in ()).throw(
        OSError(2, "nope", str(tmp_path / "d.json"))), registry=False)
    (tmp_path / "d.json").write_text("{}", encoding="utf-8")
    w.get()
    assert str(tmp_path) not in w.error and "could not be read" in w.error


def _flaky_loader(fails):
    """A JSON loader whose first `fails` calls raise PermissionError (an
    editor or AV scanner holding the file)."""
    calls = []

    def load(path):
        calls.append(path)
        if len(calls) <= fails:
            raise PermissionError(13, "locked", str(path))
        return hotreload.load_json(path)
    return load, calls


def test_permission_error_once_then_same_mtime_loads_new_value(tmp_path):
    f = tmp_path / "d.json"
    _bump(f, '{"a": 1}')
    load, calls = _flaky_loader(0)
    w = hotreload.Watched(f, load, name="Test data", default=dict, registry=False)
    assert w.get() == {"a": 1}
    # every read of the next edit is locked: all tries fail, last good stays
    load2, calls2 = _flaky_loader(hotreload.RETRY_TRIES)
    w.loader = load2
    slept = []
    w._sleep = slept.append
    _bump(f, '{"a": 2}')
    assert w.get() == {"a": 1}
    assert len(calls2) == hotreload.RETRY_TRIES
    assert len(slept) == hotreload.RETRY_TRIES - 1
    assert all(0 < s <= 0.1 for s in slept)
    assert w.error == ("Test data did not load (could not be read). "
                       "The last good copy stays in use.")
    assert str(tmp_path) not in w.error
    # the lock is gone, the mtime has not moved: the next poll loads it
    assert w.get() == {"a": 2} and w.error is None and w.loads == 2
    # a single locked read is absorbed by the retry inside one get()
    w.loader, calls3 = _flaky_loader(1)
    _bump(f, '{"a": 3}')
    assert w.get() == {"a": 3} and len(calls3) == 2 and w.error is None


def test_json_syntax_error_keeps_last_good_without_retry_storm(tmp_path):
    f = tmp_path / "d.json"
    calls = []

    def load(path):
        calls.append(path)
        return hotreload.load_json(path)
    w = hotreload.Watched(f, load, name="Test data", default=dict, registry=False)
    slept = []
    w._sleep = slept.append
    _bump(f, '{"a": 1}')
    assert w.get() == {"a": 1}
    _bump(f, '{"a": ')
    for _ in range(5):
        assert w.get() == {"a": 1}
    assert len(calls) == 2 and slept == []          # one read of the bad edit
    assert "not valid JSON at line 1" in w.error
    _bump(f, '{"a": 4}')
    assert w.get() == {"a": 4} and w.error is None


def _deny_stat(monkeypatch, target):
    real = os.stat

    def fake(path, *a, **k):
        if Path(path) == target:
            raise PermissionError(13, "denied", str(path))
        return real(path, *a, **k)
    monkeypatch.setattr(hotreload.os, "stat", fake)
    return real


def test_stat_error_keeps_last_good_and_adds_a_note(tmp_path, monkeypatch):
    reg = hotreload.Registry()
    f = tmp_path / "d.json"
    _bump(f, '{"a": 1}')
    w = hotreload.Watched(f, hotreload.load_json, name="Test data",
                          default=dict, registry=reg)
    assert w.get() == {"a": 1}
    real = _deny_stat(monkeypatch, f)
    assert w.get() == {"a": 1}                        # not reset to the default
    assert w.error == ("Test data could not be checked for changes. "
                       "The last good copy stays in use.")
    assert reg.notes() == [w.error] and str(tmp_path) not in w.error
    monkeypatch.setattr(hotreload.os, "stat", real)
    assert w.get() == {"a": 1} and w.error is None and w.loads == 1
    # a content note from before the stat error comes back after it
    _bump(f, "{bad")
    w.get()
    content_note = w.error
    _deny_stat(monkeypatch, f)
    w.get()
    assert "could not be checked" in w.error
    monkeypatch.setattr(hotreload.os, "stat", real)
    assert w.get() == {"a": 1} and w.error == content_note
    # a really removed file still reads as the default
    f.unlink()
    assert w.get() == {} and w.error is None


def test_note_text_is_stable_across_polls(tmp_path, monkeypatch, caplog):
    reg = hotreload.Registry()
    f = tmp_path / "d.json"
    _bump(f, '{"a": 1}')
    w = hotreload.Watched(f, hotreload.load_json, name="Test data",
                          default=dict, registry=reg)
    w._sleep = lambda s: None
    reg.poll()
    caplog.set_level("WARNING", logger="al.hotreload")
    # a file that stays locked: same note, logged once
    w.loader, _ = _flaky_loader(10 ** 6)
    _bump(f, '{"a": 2}')
    seen = set()
    for _ in range(4):
        reg.poll()
        seen.add(tuple(reg.notes()))
    assert len(seen) == 1 and len(next(iter(seen))) == 1
    assert len([r for r in caplog.records if "did not load" in r.getMessage()]) == 1
    # a stat error that stays: same note, logged once
    real = _deny_stat(monkeypatch, f)
    stat_notes = set()
    for _ in range(4):
        reg.poll()
        stat_notes.add(tuple(reg.notes()))
    assert len(stat_notes) == 1
    assert len([r for r in caplog.records
                if "could not be checked" in r.getMessage()]) == 1
    monkeypatch.setattr(hotreload.os, "stat", real)
    w.loader = hotreload.load_json
    reg.poll()
    assert reg.notes() == [] and w.get() == {"a": 2}


def test_existing_caches_keep_last_good(tmp_path):
    f = tmp_path / acts.FILE_NAME
    cache = acts.TableCache(f)
    _bump(f, json.dumps({"G1_1": {"name": "Riverbank", "area_level": 1}}))
    good = cache.get()
    assert good["G1"][0]["name"] == "Riverbank"
    _bump(f, "{half written")
    assert cache.get() is good and "Zone level table" in cache.error


def test_zone_notes_are_watched():
    assert zonenotes._watch in hotreload.REGISTRY.watches()
    assert zonenotes.load() is zonenotes._watch.get()
    assert zonenotes.load()  # the tracked file loads


# ---- TreeWatch / dev_enabled ----------------------------------------------

class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_tree_watch_is_rate_limited_and_filtered(tmp_path):
    (tmp_path / "sub").mkdir()
    a = tmp_path / "sub" / "a.js"
    a.write_text("1", encoding="ascii")
    clock = Clock()
    tw = hotreload.TreeWatch([tmp_path], suffixes=(".js",), every_s=1.0, clock=clock)
    assert tw.poll() is False                       # first look: baseline
    _bump(a, "22")
    clock.t = 0.5
    assert tw.poll() is False                       # inside the rate limit
    clock.t = 1.0
    assert tw.poll() is True
    clock.t = 2.0
    assert tw.poll() is False                       # one True per change
    _bump(tmp_path / "notes.txt", "x")              # filtered out
    clock.t = 3.0
    assert tw.poll() is False
    (tmp_path / "__pycache__").mkdir()
    _bump(tmp_path / "__pycache__" / "x.js", "x")   # skipped dir
    clock.t = 4.0
    assert tw.poll() is False
    _bump(tmp_path / "new.js", "x")
    clock.t = 5.0
    assert tw.poll() is True


def test_tree_watch_is_bounded(tmp_path):
    for i in range(30):
        (tmp_path / f"f{i}.js").write_text("x", encoding="ascii")
    tw = hotreload.TreeWatch([tmp_path], max_files=10)
    assert len(tw.signature()) == 10


def test_dev_enabled_order(tmp_path):
    assert hotreload.dev_enabled({}, {}, root=tmp_path) is False
    (tmp_path / ".git").write_text("gitdir: x\n", encoding="ascii")
    assert hotreload.dev_enabled({}, {}, root=tmp_path) is True
    assert hotreload.dev_enabled({"hot_reload": False}, {}, root=tmp_path) is False
    assert hotreload.dev_enabled({"hot_reload": True}, {"AL_HOT_RELOAD": "0"},
                                 root=tmp_path) is False
    assert hotreload.dev_enabled({"hot_reload": "yes"}, {}, root=tmp_path) is True
    assert hotreload.dev_enabled({}, {"AL_HOT_RELOAD": "1"}, root=ROOT / "nope") is True


# ---- core: notes, zone table, web reload ---------------------------------

def _core(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    cfg = tmp_path / "local.json"
    cfg.write_text("{}", encoding="ascii", newline="\n")
    return Core(runtime=tmp_path, tail=False, config_path=cfg)


def test_test_core_watches_no_web_root(tmp_path):
    core = _core(tmp_path)
    try:
        assert core.hot is False and core.web_watch is None
        assert core.tick_reload() is False
    finally:
        core.close()


def test_bad_zone_table_edit_keeps_table_and_shows_a_check(tmp_path):
    core = _core(tmp_path)
    try:
        p = core._zones_path
        p.parent.mkdir(parents=True, exist_ok=True)
        _bump(p, json.dumps({"G1_1": {"name": "Riverbank", "area_level": 1}}))
        core.tick_sources()                           # read after start now
        assert core.state.zone_table["G1"][0]["level"] == 1
        _bump(p, "{oops")
        core.tick_sources()
        core.tick_reload()
        assert core.state.zone_table["G1"][0]["level"] == 1
        rows = {r["id"]: r for r in core.state.snapshot()["diag"]["checks"]}
        assert rows["reload"]["status"] == diag.FAIL
        assert "Zone level table" in rows["reload"]["detail"]
        assert rows["reload"]["fix"] == diag.FIX_RELOAD
        _bump(p, json.dumps({"G1_1": {"name": "Riverbank", "area_level": 2}}))
        core.tick_sources()
        core.tick_reload()
        assert core.state.zone_table["G1"][0]["level"] == 2
        assert "reload" not in {r["id"] for r in core.state.snapshot()["diag"]["checks"]}
    finally:
        core.close()


def test_supervisor_code_note_reaches_the_checks_card(tmp_path):
    core = _core(tmp_path)
    try:
        hotreload.write_status(tmp_path, "A code change did not load (x.py:3: bad).")
        core.tick_reload()
        rows = {r["id"]: r for r in core.state.snapshot()["diag"]["checks"]}
        assert "x.py:3" in rows["reload"]["detail"]
        hotreload.write_status(tmp_path, None)
        _bump(tmp_path / hotreload.STATUS_FILE, json.dumps({"code_error": None}))
        core.tick_reload()
        assert "reload" not in {r["id"] for r in core.state.snapshot()["diag"]["checks"]}
    finally:
        core.close()


def test_check_reload_row_only_with_notes():
    assert diag.check_reload({}) is None
    row = diag.check_reload({"reload_notes": ["one", "two"]})
    assert row["detail"] == "one (+1 more)"


@pytest.mark.server
def test_web_change_sends_sse_reload(tmp_path):
    web = tmp_path / "web"
    web.mkdir()
    (web / "app.js").write_text("1", encoding="ascii")
    core = _core(tmp_path / "rt")
    core.web_watch = hotreload.TreeWatch([web], every_s=0.0)
    server = serve(core, TOKEN, port=0, web_root=ROOT / "web")
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True)
    t.start()
    sock = socket.create_connection(("127.0.0.1", server.port), timeout=ci_scale(5))
    try:
        core.tick_reload()                            # baseline
        sock.sendall((f"GET /events?token={TOKEN} HTTP/1.1\r\nHost: 127.0.0.1:"
                      f"{server.port}\r\n\r\n").encode())
        buf = b""
        end = time.monotonic() + ci_scale(10)  # decision 0080: 3x under AL_CI=1
        while b"event: state" not in buf and time.monotonic() < end:
            buf += sock.recv(65536)
        _bump(web / "app.js", "22")
        assert core.tick_reload() is True and core.reload_web == 1
        while b"event: reload" not in buf and time.monotonic() < end:
            buf += sock.recv(65536)
        assert b'event: reload\ndata: {"target":"web","seq":1}' in buf
    finally:
        sock.close()
        server.stop()
        core.close()


def test_dashboard_reloads_on_the_event():
    js = srcpaths.read("app.js")
    assert 'es.addEventListener("reload"' in js and "location.reload()" in js


# ---- token hand-off --------------------------------------------------------

def test_token_reuse_mark(tmp_path):
    tok = tmp_path / "token"
    tok.write_text("ab" * 24 + "\n", encoding="ascii")
    assert hotreload.take_token_reuse(tmp_path, tok) is None      # no mark
    hotreload.mark_token_reuse(tmp_path, now=1000.0)
    assert hotreload.take_token_reuse(tmp_path, tok, now=1010.0) == "ab" * 24
    assert not (tmp_path / hotreload.TOKEN_REUSE_FILE).exists()  # consumed
    hotreload.mark_token_reuse(tmp_path, now=1000.0)
    assert hotreload.take_token_reuse(tmp_path, tok, now=1000.0 + 600) is None
    tok.write_text("not-a-token", encoding="ascii")
    hotreload.mark_token_reuse(tmp_path, now=1000.0)
    assert hotreload.take_token_reuse(tmp_path, tok, now=1001.0) is None


# ---- preflight -------------------------------------------------------------

def test_check_code_finds_a_syntax_error(tmp_path):
    (tmp_path / "server" / "al").mkdir(parents=True)
    (tmp_path / "server" / "al" / "ok.py").write_text("x = 1\n", encoding="ascii")
    assert entry.check_code(tmp_path, out=None) == 0
    (tmp_path / "server" / "al" / "bad.py").write_text("def f(:\n", encoding="ascii")
    import io
    out = io.StringIO()
    assert entry.check_code(tmp_path, out=out) == 1
    assert out.getvalue().startswith("server/al/bad.py:1: ")


def test_preflight_error_is_repo_relative(tmp_path):
    tb = (f'Traceback (most recent call last):\n  File "{tmp_path}\\server\\al\\core.py", '
          'line 12, in <module>\n    import nope\nModuleNotFoundError: No module named '
          "'nope'\n")
    msg = ka.preflight_error(tb, tmp_path)
    assert msg == "server/al/core.py:12: ModuleNotFoundError: No module named 'nope'"
    assert str(tmp_path) not in msg
    assert ka.preflight_error("", tmp_path) == "the code check failed"


def test_run_preflight_passes_on_this_checkout():
    assert ka.run_preflight(ROOT) == (True, None)


def test_run_preflight_reports_failure(tmp_path):
    class R:
        returncode = 1
        stdout = b"server/al/x.py:3: invalid syntax\n"
        stderr = b""
    ok, err = ka.run_preflight(tmp_path, run=lambda *a, **k: R())
    assert not ok and err == "server/al/x.py:3: invalid syntax"

    def boom(*a, **k):
        raise subprocess.TimeoutExpired("x", 1)
    assert ka.run_preflight(tmp_path, run=boom) == (False, "the code check timed out")


# ---- supervisor code reload --------------------------------------------------

class Code:
    def __init__(self):
        self.sig = 1

    def signature(self):
        return self.sig


class World:
    def __init__(self, tmp_path):
        self.runtime = tmp_path / "runtime"
        self.runtime.mkdir()
        self.t = 1000.0
        self.alive = set()
        self.launches = []
        self.terminated = []
        self.next_pid = 700
        self.lines = []
        self.code = Code()
        self.checks = []
        self.check_result = (True, None)

    def beat(self, pid):
        entry.write_heartbeat(self.runtime / "core.alive", pid, TEST_PORT, now=self.t)

    def launch(self):
        self.next_pid += 1
        self.alive.add(self.next_pid)
        self.launches.append(self.next_pid)
        return self.next_pid

    def preflight(self):
        self.checks.append(self.t)
        return self.check_result

    def sup(self):
        return ka.Keepalive(self.runtime, TEST_PORT, self.launch,
                            pid_alive=lambda p: p in self.alive,
                            health=lambda: False,
                            terminate=lambda p: self.terminated.append(p) or True,
                            now=lambda: self.t, log=self.lines.append,
                            created=lambda p: 0, code_watch=self.code,
                            preflight=self.preflight)

    def clean_exit(self, pid):
        self.alive.discard(pid)
        (self.runtime / "core.alive").unlink()

    def status(self):
        return json.loads((self.runtime / hotreload.STATUS_FILE).read_text())


def _running(w):
    s = w.sup()
    assert s.step() == "waiting"          # no core yet: crash path, backoff
    w.t += 3
    assert s.step() == "launched"
    w.beat(w.launches[-1])
    assert s.step() == "ok"
    return s


def test_code_change_restarts_core_once_settled(tmp_path):
    w = World(tmp_path)
    s = _running(w)
    first = w.launches[-1]
    restarts = len(s.restarts)
    w.code.sig = 2
    assert s.step() == "reload-pending"
    w.t += 0.5
    w.code.sig = 3                        # a burst of saves
    assert s.step() == "reload-pending"
    w.t += 1.0
    assert s.step() == "reload-pending"   # debounce restarts at the last save
    w.t += 1.0
    assert s.step() == "reloading"
    assert w.checks == [w.t]
    assert (w.runtime / hotreload.RESTART_FILE).exists()
    assert s.step() == "reloading"        # waits for the old core
    w.clean_exit(first)                   # the core honours restart.request
    w.t += 1
    assert s.step() == "launched"         # at once: no backoff
    assert len(s.restarts) == restarts    # not counted as a crash restart
    w.beat(w.launches[-1])
    assert s.step() == "ok" and not s.hot_launch
    assert w.status()["code_error"] is None


def test_core_that_ignores_restart_is_terminated(tmp_path):
    w = World(tmp_path)
    s = _running(w)
    first = w.launches[-1]
    w.code.sig = 2
    s.step()
    w.t += 2
    assert s.step() == "reloading"
    w.t += ka.RELOAD_EXIT_S + 1
    w.beat(first)
    assert s.step() == "reloading" and w.terminated == [first]
    w.alive.discard(first)
    assert s.step() == "launched"


def test_broken_code_keeps_the_old_core(tmp_path):
    w = World(tmp_path)
    s = _running(w)
    n = len(w.launches)
    w.check_result = (False, "server/al/core.py:3: invalid syntax")
    w.code.sig = 2
    s.step()
    w.t += 2
    assert s.step() == "reload-refused"
    assert not (w.runtime / hotreload.RESTART_FILE).exists()
    assert "core.py:3" in w.status()["code_error"]
    for _ in range(10):                   # no retry without a new edit
        w.t += 1
        w.beat(w.launches[-1])
        assert s.step() == "ok"
    assert len(w.checks) == 1 and len(w.launches) == n
    w.check_result = (True, None)         # the fix
    w.code.sig = 3
    s.step()
    w.t += 2
    assert s.step() == "reloading"
    assert w.status()["code_error"] is None


def test_new_code_that_dies_never_loops(tmp_path):
    w = World(tmp_path)
    s = _running(w)
    first = w.launches[-1]
    w.code.sig = 2
    s.step()
    w.t += 2
    s.step()
    w.clean_exit(first)
    assert s.step() == "launched"
    w.alive.discard(w.launches[-1])       # dies before its first heartbeat
    assert s.step() == "reload-blocked"
    n = len(w.launches)
    for _ in range(20):
        w.t += 30
        assert s.step() == "reload-blocked"
    assert len(w.launches) == n           # nothing starts until an edit
    assert w.status()["code_error"] == ka.RELOAD_DEAD_NOTE
    w.code.sig = 3                        # the fix
    assert s.step() == "reload-blocked"
    w.t += 2
    assert s.step() == "launched"
    w.beat(w.launches[-1])
    assert s.step() == "ok" and not s.blocked


def test_stop_request_wins_while_blocked(tmp_path):
    w = World(tmp_path)
    s = _running(w)
    first = w.launches[-1]
    w.code.sig = 2
    s.step()
    w.t += 2
    s.step()
    w.clean_exit(first)
    s.step()
    w.alive.discard(w.launches[-1])
    assert s.step() == "reload-blocked"
    (w.runtime / ka.STOP_FILE).write_text("stop\n", encoding="ascii")
    assert s.step() == "user-stop"


def test_without_code_watch_nothing_changes(tmp_path):
    w = World(tmp_path)
    s = ka.Keepalive(w.runtime, TEST_PORT, w.launch, pid_alive=lambda p: p in w.alive,
                     health=lambda: False, now=lambda: w.t, created=lambda p: 0)
    pid = w.launch()
    w.beat(pid)
    assert s.step() == "ok"
    w.clean_exit(pid)
    assert s.step() == "user-stop"


# ---- real core: restart.request is a clean exit that keeps the token ----------

@pytest.mark.slow
@pytest.mark.server
def test_real_core_exits_for_reload_and_keeps_token(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    env = dict(os.environ)
    env[paths.RUNTIME_ENV] = str(runtime)
    env[paths.SIDECAR_ENV] = str(tmp_path / "AL")
    env["AL_HEARTBEAT_S"] = "0.5"
    with socket.socket() as s:  # a free port: parallel suites share the block
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    cmd = [sys.executable, "-m", "server.al", "--quiet", "--no-tail",
           "--port", str(port)]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def start():
        return subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=flags)

    def wait_for(pred, s=30):
        end = time.monotonic() + s
        while time.monotonic() < end:
            if pred():
                return True
            time.sleep(0.1)
        return False

    hb = runtime / "core.alive"
    tok = runtime / "token"
    p = start()
    p2 = None
    try:
        assert wait_for(hb.exists), "core never wrote a heartbeat"
        token = tok.read_text(encoding="ascii").strip()
        (runtime / hotreload.RESTART_FILE).write_text("reload\n", encoding="ascii")
        assert p.wait(timeout=30) == 0
        assert not hb.exists()                       # a clean exit
        assert tok.read_text(encoding="ascii").strip() == token
        assert (runtime / hotreload.TOKEN_REUSE_FILE).exists()
        p2 = start()
        assert wait_for(hb.exists), "new core never wrote a heartbeat"
        assert tok.read_text(encoding="ascii").strip() == token
        assert not (runtime / hotreload.TOKEN_REUSE_FILE).exists()
        (runtime / ka.STOP_FILE).write_text("stop\n", encoding="ascii")
        assert p2.wait(timeout=30) == 0
        assert not tok.exists()                      # a user stop drops it
    finally:
        for proc in (p, p2):
            if proc is not None and proc.poll() is None:
                proc.kill()
