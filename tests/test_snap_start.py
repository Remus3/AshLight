"""DATA-SNAP-AT-START (finding F-072, ruling Q-04): with web data on and the
game-data cache missing or older than 24 h the keepalive supervisor starts
the snapshot tool as its own hidden, below-normal process; the core never
fetches.

Every process start is a fake popen and every pid check a fake: no test
here starts a process or touches the network.
"""

import ast
import json
import os
import time
from pathlib import Path

import pytest

from server.al import keepalive as ka
from server.al import paths, snapstart
from server.al.theorycraft import datacredit

ROOT = Path(__file__).resolve().parents[1]
NOW = 2_000_000_000.0
DAY = 24 * 3600
TEST_PORT = 8969


def _utc(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def write_manifest(cache, *checked):
    cache.mkdir(parents=True, exist_ok=True)
    files = {f"src{i}": {"url": "https://example.invalid/x", "sha256": "0" * 64,
                         "checked_at": _utc(t)} for i, t in enumerate(checked)}
    (cache / datacredit.MANIFEST).write_text(json.dumps({"files": files}) + "\n",
                                             encoding="ascii")
    return cache / datacredit.MANIFEST


class FakeProc:
    def __init__(self, pid):
        self.pid = pid


class World:
    """A tmp runtime and sidecar, a fake popen and a fake process table."""

    def __init__(self, tmp_path, web_data=True):
        self.runtime = tmp_path / "runtime"
        self.runtime.mkdir(parents=True)
        self.env = {paths.SIDECAR_ENV: str(tmp_path / "AL")}
        self.cache = tmp_path / "AL" / "Cache" / "gamedata"
        self.manifest = self.cache / datacredit.MANIFEST
        self.config = {"web_data": web_data}
        self.calls = []
        self.alive = set()
        self.next_pid = 7000

    def popen(self, cmd, **kw):
        self.next_pid += 1
        self.alive.add(self.next_pid)
        self.calls.append((cmd, kw))
        return FakeProc(self.next_pid)

    def tick(self, now, **kw):
        return snapstart.tick(self.runtime, now, config=self.config,
                              manifest_path=self.manifest, environ=self.env,
                              popen=self.popen, pid_alive=lambda p: p in self.alive,
                              created=lambda p: 0, **kw)


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def supervisor(world, clock, lines):
    return ka.Keepalive(runtime=world.runtime, port=TEST_PORT, launch=lambda: 4242,
                        pid_alive=lambda p: False, health=lambda: True,
                        terminate=lambda p: True, now=clock, log=lines.append,
                        created=lambda p: 0, snapshot=world.tick)


def test_web_data_off_starts_nothing(tmp_path):
    w = World(tmp_path, web_data=False)
    assert not snapstart.due(w.config, w.manifest, NOW)
    assert w.tick(NOW) is None
    # strictly True, as the core reads it
    for value in ("true", 1, None):
        w.config = {"web_data": value}
        assert w.tick(NOW) is None
    w.config = {}
    assert w.tick(NOW) is None
    # AL_NO_SNAPSHOT wins even with web data on
    w.config = {"web_data": True}
    w.env[snapstart.OPT_OUT_ENV] = "1"
    assert w.tick(NOW) is None
    # the supervisor with web data off: steps run, nothing starts
    w = World(tmp_path / "b", web_data=False)
    clock, lines = Clock(NOW), []
    sup = supervisor(w, clock, lines)
    for _ in range(5):
        sup.step()
        clock.t += ka.POLL_S
    assert w.calls == []
    assert not (w.runtime / snapstart.PID_FILE).exists()
    # a supervisor given its runtime dir (tests, isolated instances) gets no starter
    assert ka.snapshot_starter(w.runtime, str(w.runtime), environ={}) is None
    assert ka.snapshot_starter(w.runtime, None,
                               environ={paths.RUNTIME_ENV: str(w.runtime)}) is None
    assert isinstance(ka.snapshot_starter(w.runtime, None, environ={}), snapstart.Starter)


def test_missing_cache_starts_the_tool_within_one_supervisor_poll(tmp_path):
    w = World(tmp_path)
    clock, lines = Clock(NOW), []
    sup = supervisor(w, clock, lines)
    sup.step()  # the first poll
    assert len(w.calls) == 1
    assert any("game data snapshot started" in ln for ln in lines)
    rec = json.loads((w.runtime / snapstart.PID_FILE).read_text(encoding="ascii"))
    assert rec["pid"] == w.next_pid and rec["started_at"] == NOW
    # the tool's output goes to the sidecar Logs dir, never the repo
    out = w.calls[0][1]["stdout"]
    assert w.calls[0][1]["stderr"] is out
    assert (tmp_path / "AL" / "Logs" / snapstart.LOG_NAME).is_file()
    # the cache is due when missing, empty or a day old; fresh is not due
    assert snapstart.due({"web_data": True}, tmp_path / "none.json", NOW)
    write_manifest(tmp_path / "c1")
    assert snapstart.due({"web_data": True}, tmp_path / "c1" / "manifest.json", NOW)
    old = write_manifest(tmp_path / "c2", NOW - 60, NOW - DAY - 1)
    assert snapstart.due({"web_data": True}, old, NOW)
    fresh = write_manifest(tmp_path / "c3", NOW - 60, NOW - DAY + 60)
    assert not snapstart.due({"web_data": True}, fresh, NOW)
    future = write_manifest(tmp_path / "c4", NOW + 3600)
    assert snapstart.due({"web_data": True}, future, NOW)


def test_web_data_ticked_while_running_starts_on_the_next_poll(tmp_path):
    w = World(tmp_path, web_data=False)
    clock, lines = Clock(NOW), []
    sup = supervisor(w, clock, lines)
    sup.step()
    assert w.calls == []
    w.config["web_data"] = True  # the player ticks "Use web data"
    clock.t += ka.POLL_S
    sup.step()
    assert len(w.calls) == 1
    # a faster dev poll does not read the files more often than a normal poll
    w2 = World(tmp_path / "x", web_data=False)
    seen = []
    sup2 = ka.Keepalive(runtime=w2.runtime, port=TEST_PORT, launch=lambda: 1,
                        pid_alive=lambda p: False, health=lambda: True,
                        now=clock, log=lambda ln: None, created=lambda p: 0,
                        snapshot=lambda now: seen.append(now))
    for _ in range(10):
        sup2.step()
        clock.t += 1.0
    assert len(seen) == 2


def test_no_second_start_inside_24_h_or_while_one_runs(tmp_path):
    w = World(tmp_path)
    assert w.tick(NOW) == w.next_pid
    first = w.next_pid
    # the tool runs: no second copy, even a day later
    assert w.tick(NOW + 10) is None
    assert w.tick(NOW + DAY + 10) is None
    assert snapstart.blocked(w.runtime, NOW + DAY + 10,
                             pid_alive=lambda p: p in w.alive) == "running"
    # it ended without refreshing the cache (offline): no retry inside 24 h
    w.alive.discard(first)
    assert w.tick(NOW + 3600) is None
    assert snapstart.blocked(w.runtime, NOW + 3600,
                             pid_alive=lambda p: p in w.alive) == "started recently"
    assert len(w.calls) == 1
    # a day later it is due again
    assert w.tick(NOW + DAY + 20) == first + 1
    # a reused pid (other creation time) is not our tool
    rec = snapstart.read_record(w.runtime)
    rec["created"] = 111
    assert not snapstart.running(rec, lambda p: True, created=lambda p: 222)
    assert snapstart.running(rec, lambda p: True, created=lambda p: 111)
    # a failed launch is recorded and not retried inside 24 h
    w2 = World(tmp_path / "f")

    def refuse(cmd, **kw):
        w2.calls.append(cmd)
        raise OSError("no")

    w2.popen = refuse
    with pytest.raises(OSError):
        w2.tick(NOW)
    assert w2.tick(NOW + 60) is None and len(w2.calls) == 1
    # the supervisor survives a failing starter and logs no path
    clock, lines = Clock(NOW + 2 * DAY), []
    sup = supervisor(w2, clock, lines)
    assert sup.step() == "ok"
    assert any("did not start (OSError)" in ln for ln in lines)
    # a pending user stop starts nothing
    w3 = World(tmp_path / "s")
    (w3.runtime / ka.STOP_FILE).write_text("stop\n", encoding="ascii")
    supervisor(w3, Clock(NOW), []).step()
    assert w3.calls == []


def test_command_is_hidden_and_below_normal_priority(tmp_path, monkeypatch):
    cmd = snapstart.command(environ={})
    assert cmd[-2:] == ["-m", "server.al.theorycraft.snapshot"]
    assert "--opt-in" not in cmd  # the tool checks web data itself
    assert cmd == paths.python_cmd(snapstart.MODULE, windowless=True, environ={})
    w = World(tmp_path)
    w.tick(NOW)
    kw = w.calls[0][1]
    assert kw["stdin"] is not None and kw["close_fds"] is True
    if os.name == "nt":
        flags = kw["creationflags"]
        assert flags & 0x08000000  # CREATE_NO_WINDOW
        assert flags & 0x00004000  # BELOW_NORMAL_PRIORITY_CLASS
        assert flags & 0x00000008  # DETACHED_PROCESS
        assert w.calls[0][0][0] == str(paths._running_python(True))  # pythonw
    monkeypatch.setattr(snapstart.os, "name", "posix")
    assert snapstart.creation_flags() == 0
    # the cadence matches the tool's own 24 h gate
    from server.al.theorycraft import snapshot
    assert snapstart.MAX_AGE_S == snapshot.MIN_AGE_S
    assert snapstart.OPT_OUT_ENV == snapshot.OPT_OUT_ENV


def _imports(path):
    tree = ast.parse(path.read_text(encoding="ascii"))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            out.add(mod)
            out.update(f"{mod}.{a.name}" if mod else a.name for a in node.names)
    return out


def test_snapstart_never_imports_snapshot():
    for rel in ("server/al/snapstart.py", "server/al/keepalive.py",
                "server/al/theorycraft/datacredit.py"):
        names = _imports(ROOT / rel)
        assert not any(n == "snapshot" or n.endswith(".snapshot") for n in names), rel
        assert not any("webfetch" in n or "urllib" in n for n in names
                       if rel.endswith("snapstart.py")), rel
    # the module is only named as the command's string
    text = (ROOT / "server/al/snapstart.py").read_text(encoding="ascii")
    assert 'MODULE = "server.al.theorycraft.snapshot"' in text
