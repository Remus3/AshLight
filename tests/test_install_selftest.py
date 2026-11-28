"""REL-INSTALL-SELFTEST (F-050, DEP-09; docs/plan/05-deployment.md, update
step 2): the self-test of a laid-out version before any marker write.

`boot.py server.al --check`, then a demo core (decision 0049) on the first
free port of ports.SELFTEST_PORTS with a scratch runtime under <home>/temp
and web data off; /api/health must answer version == <new> within 15 s. A
failure moves the folder to <home>/temp/failed-<new>, writes one report
and leaves the marker alone. The children run hidden at below-normal
priority; the gate waits while an injected game_idle status is false and
never queries a process list.

The real runs copy this checkout's server/ and boot.py into a tmp home as
<home>/app/<new>/ with VERSION set to <new>. The demo core binds a port of
the self-test block (8970-8975, never 8960) by its own first-free probe;
the test binds no port itself.
"""

import ast
import io
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from server.al import demo, http, paths, ports
from server.al.install import home as homemod
from server.al.install import selftest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "server" / "al" / "install" / "selftest.py"
FIXTURE = ROOT.joinpath(*selftest.FIXTURE_REL)
NEW = "0.9.1"
OLD = "0.9.0"


@pytest.fixture
def clean_env(monkeypatch):
    for key in (paths.HOME_ENV, paths.SIDECAR_ENV, paths.RUNTIME_ENV, "AL_PORT"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(paths, "_MARKER_SEEN", {})
    return monkeypatch


def lay_out(home, folder=NEW, version=None):
    """<home>/app/<folder> as a payload copy whose VERSION is version."""
    root = Path(home) / "app" / folder
    shutil.copytree(ROOT / "server", root / "server",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copyfile(ROOT / "boot.py", root / "boot.py")
    init = root / "server" / "al" / "__init__.py"
    text = init.read_text(encoding="utf-8")
    init.write_text(re.sub(r'VERSION = "[^"]*"', f'VERSION = "{version or folder}"', text),
                    encoding="utf-8", newline="\n")
    return root


def with_marker(home):
    """An active install of OLD; returns the marker's bytes."""
    (Path(home) / "app" / OLD).mkdir(parents=True)
    homemod.write_marker(home, homemod.new_marker(OLD, "python-3.12.7", "electron-45.3.3"))
    return (Path(home) / paths.MARKER_NAME).read_bytes()


class Recorder:
    """A spawn that records every call and starts the real child."""

    def __init__(self):
        self.calls = []

    def __call__(self, cmd, **kw):
        self.calls.append((list(cmd), dict(kw)))
        return subprocess.Popen(cmd, **kw)


class FakeProc:
    def __init__(self, code):
        self.code = code
        self.returncode = None
        self.stdout = None
        self.pid = 0

    def poll(self):
        self.returncode = self.code
        return self.code

    def wait(self, timeout=None):
        self.returncode = self.code
        return self.code

    def terminate(self):
        pass

    def kill(self):
        pass


class FakeSpawn:
    """--check exits check_code; the demo exits demo_code."""

    def __init__(self, check_code=0, demo_code=1, on_call=None):
        self.check_code, self.demo_code = check_code, demo_code
        self.calls = []
        self.on_call = on_call

    def __call__(self, cmd, **kw):
        self.calls.append((list(cmd), dict(kw)))
        if self.on_call:
            self.on_call(cmd, kw)
        return FakeProc(self.check_code if "--check" in cmd else self.demo_code)


class LiveDemo:
    """A demo core that printed its token line and keeps running."""

    def __init__(self, token="tok123"):
        self.stdout = io.BytesIO(f"http://127.0.0.1:8970/#token={token}\n".encode("ascii"))
        self.returncode = None
        self.pid = 0

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        self.returncode = 0

    def kill(self):
        self.returncode = 0


class HermeticSpawn(Recorder):
    """--check exits 0; the demo core stays up and answers health (faked)."""

    def __call__(self, cmd, **kw):
        self.calls.append((list(cmd), dict(kw)))
        return FakeProc(0) if "--check" in cmd else LiveDemo()


def leftovers(home):
    temp = Path(home) / "temp"
    return sorted(os.listdir(temp)) if temp.is_dir() else []


# -- real runs (a real demo core)

def test_new_version_passes_and_runs_hidden_below_normal(tmp_path, clean_env):
    home = tmp_path / "home"
    root = lay_out(home)
    marker = with_marker(home)
    spawn = HermeticSpawn()
    clean_env.setattr(selftest, "_health",
                      lambda port, token, timeout=2.0: {"name": selftest.NAME, "version": NEW})
    res = selftest.run(home, NEW, clicked=True, spawn=spawn, probe=lambda p: True)
    assert res.status == selftest.PASSED, res
    assert res.ok and res.stage == "health"
    assert ports.SELFTEST_PORTS[0] <= res.port <= ports.SELFTEST_PORTS[1]
    assert res.port != ports.AL_PORT
    # --check first, then the demo core, both from the NEW payload root
    (check_cmd, check_kw), (demo_cmd, demo_kw) = spawn.calls
    for cmd in (check_cmd, demo_cmd):
        assert Path(cmd[1]) == root / paths.BOOT_NAME and cmd[2] == "server.al"
    assert check_cmd[3:] == ["--check"]
    assert demo_cmd[3] == "--demo" and "--port" in demo_cmd
    assert int(demo_cmd[demo_cmd.index("--port") + 1]) == res.port
    for kw in (check_kw, demo_kw):
        if os.name == "nt":
            assert kw["creationflags"] & subprocess.CREATE_NO_WINDOW
            assert kw["creationflags"] & subprocess.BELOW_NORMAL_PRIORITY_CLASS
        env = kw["env"]
        assert env[paths.HOME_ENV] == str(home)
        assert paths.RUNTIME_ENV not in env and paths.SIDECAR_ENV not in env
        # cwd under <home>/temp, never the version folder (so it can move)
        assert Path(kw["cwd"]).parent == home / "temp"
    # the fixture folder lies under <home>/temp; the log is the shipped one
    assert Path(demo_cmd[4]).parent.parent == home / "temp"
    # the marker is untouched; the version stays; scratch is cleaned up
    assert (home / paths.MARKER_NAME).read_bytes() == marker
    assert root.is_dir()
    assert leftovers(home) == []
    assert not (home / "logs" / "reports").exists()


def test_port_taken_respawns_the_demo_core_on_the_next_port(tmp_path, clean_env):
    home = tmp_path / "home"
    lay_out(home)
    with_marker(home)
    taken = set()
    demos = []

    class Spawn(HermeticSpawn):
        def __call__(self, cmd, **kw):
            if "--demo" in cmd:
                port = int(cmd[cmd.index("--port") + 1])
                demos.append(port)
                if len(demos) == 1:
                    taken.add(port)  # another run grabbed it: bind fails, exit 2
                    self.calls.append((list(cmd), dict(kw)))
                    return FakeProc(2)
            return super().__call__(cmd, **kw)

    spawn = Spawn()
    clean_env.setattr(selftest, "_health",
                      lambda port, token, timeout=2.0: {"name": selftest.NAME, "version": NEW})
    res = selftest.run(home, NEW, clicked=True, spawn=spawn, probe=lambda p: p not in taken)
    assert res.status == selftest.PASSED, res
    assert len(spawn.calls) == 3  # --check, demo (port taken), demo again
    assert len(demos) == 2 and demos[0] != demos[1] and res.port == demos[1]
    assert leftovers(home) == []


def test_wrong_version_answer_fails_moves_and_reports(tmp_path, clean_env):
    home = tmp_path / "home"
    lay_out(home, NEW, version="0.9.2")
    marker = with_marker(home)
    res = selftest.run(home, NEW, clicked=True)
    assert res.status == selftest.FAILED
    assert res.stage == "health" and "0.9.2" in res.reason
    assert res.moved
    assert not (home / "app" / NEW).exists()
    assert (home / "temp" / f"failed-{NEW}" / "boot.py").is_file()
    assert (home / paths.MARKER_NAME).read_bytes() == marker
    reports = sorted((home / "logs" / "reports").iterdir())
    assert reports == [home / "logs" / "reports" / f"selftest-{NEW}.json"]
    text = reports[0].read_text(encoding="ascii")
    doc = json.loads(text)
    assert doc["version"] == NEW and doc["status"] == "failed" and doc["stage"] == "health"
    # the report names no path
    assert "\\" not in text and "/" not in text and str(tmp_path.name) not in text
    # the demo scratch was kept for a look; it lies under <home>/temp
    assert any(n.startswith("demo-") for n in leftovers(home))


def test_broken_code_fails_at_check_without_a_demo_core(tmp_path, clean_env):
    home = tmp_path / "home"
    root = lay_out(home)
    (root / "server" / "al" / "zz_broken.py").write_text("def broken(:\n", encoding="ascii")
    spawn = Recorder()
    res = selftest.run(home, NEW, clicked=True, spawn=spawn)
    assert res.status == selftest.FAILED and res.stage == "check"
    assert res.exit_code == 1
    assert len(spawn.calls) == 1 and "--check" in spawn.calls[0][0]
    assert res.moved and (home / "temp" / f"failed-{NEW}").is_dir()
    assert not (home / paths.MARKER_NAME).exists()
    assert (home / "logs" / "reports" / f"selftest-{NEW}.json").is_file()


# -- injected children

def test_exit_97_fails_and_fixture_is_the_shipped_synthetic_log(tmp_path, clean_env):
    home = tmp_path / "home"
    lay_out(home)
    marker = with_marker(home)
    seen = {}

    def look(cmd, kw):
        if "--demo" in cmd:
            folder = Path(cmd[cmd.index("--demo") + 1])
            seen["log"] = (folder / "Client.txt").read_bytes()
            seen["marker"] = (folder / demo.MARKER).is_file()
            seen["folder"] = folder

    spawn = FakeSpawn(check_code=0, demo_code=selftest.EXIT_LOG_OUTSIDE, on_call=look)
    res = selftest.run(home, NEW, clicked=True, spawn=spawn, probe=lambda p: True)
    assert res.status == selftest.FAILED and res.exit_code == 97
    assert "outside its fixture" in res.reason
    assert seen["log"] == FIXTURE.read_bytes() and seen["marker"]
    assert seen["folder"].parent.parent == home / "temp"
    assert (home / paths.MARKER_NAME).read_bytes() == marker
    doc = json.loads((home / "logs" / "reports" / f"selftest-{NEW}.json").read_text("ascii"))
    assert doc["exit_code"] == 97


def test_gate_waits_while_game_idle_is_false(tmp_path, clean_env):
    home = tmp_path / "home"
    lay_out(home)
    answers = iter([False, None, False, True])
    asked = []
    slept = []

    def idle():
        value = next(answers)
        asked.append(value)
        return value

    def on_call(cmd, kw):
        # nothing starts before game_idle answered True
        assert asked[-1] is True

    spawn = FakeSpawn(check_code=1, on_call=on_call)
    res = selftest.run(home, NEW, idle=idle, spawn=spawn, sleep=slept.append, poll_s=7)
    assert asked == [False, None, False, True]
    assert res.waited == 3 and slept == [7, 7, 7]
    assert spawn.calls and res.stage == "check"


def test_gate_defers_without_starting_anything(tmp_path, clean_env):
    home = tmp_path / "home"
    root = lay_out(home)
    spawn = FakeSpawn()
    t = [0.0]

    def clock():
        return t[0]

    def sleep(s):
        t[0] += s

    res = selftest.run(home, NEW, idle=lambda: False, spawn=spawn, sleep=sleep,
                       clock=clock, poll_s=60, max_wait_s=300)
    assert res.status == selftest.DEFERRED and res.stage == "gate"
    assert res.waited == 6
    # no idle signal and no click: deferred at once
    res2 = selftest.run(home, NEW, spawn=spawn)
    assert res2.status == selftest.DEFERRED and res2.waited == 0
    # an error from the status read counts as not idle
    res3 = selftest.run(home, NEW, idle=lambda: 1 / 0, spawn=spawn, max_wait_s=0)
    assert res3.status == selftest.DEFERRED
    assert spawn.calls == []
    assert root.is_dir() and not (home / "logs").exists() and leftovers(home) == []


def test_idle_from_status_only_true_counts():
    assert selftest.idle_from_status({"game_idle": True})
    for doc in ({"game_idle": False}, {"game_idle": None}, {}, None, {"game_idle": 1}):
        assert not selftest.idle_from_status(doc)


def test_missing_layout_fails_without_spawning(tmp_path, clean_env):
    home = tmp_path / "home"
    spawn = FakeSpawn()
    res = selftest.run(home, NEW, clicked=True, spawn=spawn)
    assert res.status == selftest.FAILED and res.stage == "layout" and not res.moved
    assert spawn.calls == []
    bad = selftest.run(home, "../x", clicked=True, spawn=spawn)
    assert bad.status == selftest.FAILED and bad.stage == "layout"


def test_port_taken_meanwhile_moves_to_the_next(tmp_path, clean_env):
    home = tmp_path / "home"
    lay_out(home)
    taken = set()

    def probe(port):
        return port not in taken

    def on_call(cmd, kw):
        if "--demo" in cmd:
            taken.add(int(cmd[cmd.index("--port") + 1]))  # lost the race

    spawn = FakeSpawn(check_code=0, demo_code=2, on_call=on_call)
    res = selftest.run(home, NEW, clicked=True, spawn=spawn, probe=probe)
    demo_ports = [int(c[c.index("--port") + 1]) for c, _ in spawn.calls if "--demo" in c]
    assert demo_ports == list(ports.block_range(ports.SELFTEST_PORTS))
    assert res.status == selftest.FAILED and res.stage == "start"


def test_free_ports_stay_in_the_block_and_never_8960():
    got = selftest.free_ports(probe=lambda p: True)
    assert got == list(ports.block_range(ports.SELFTEST_PORTS))
    assert ports.AL_PORT not in got
    assert selftest.free_ports((8960, 8961), probe=lambda p: True) == [8961]


# -- static and data checks

def test_no_process_list_query_and_no_marker_write():
    text = SRC.read_text(encoding="ascii").lower()
    for word in ("tasklist", "psutil", "get-process", "wmic", "enumprocesses",
                 "createtoolhelp32snapshot", "process32", "win32_process",
                 "findwindow", "enumwindows", "procs"):
        assert word not in text, word
    tree = ast.parse(SRC.read_text(encoding="ascii"))
    called = {n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not called & {"write_marker", "switch_marker", "read_marker"}
    assert "shell=True" not in SRC.read_text(encoding="ascii")


def test_constants_match_the_core():
    assert selftest.TOKEN_HEADER == http.TOKEN_HEADER
    assert selftest.DEMO_MARKER == demo.MARKER
    assert selftest.DEMO_LOG == demo.LOG_NAME
    assert selftest.DEMO_SCRATCH_PREFIX == demo.SCRATCH_PREFIX
    assert selftest.EXIT_LOG_OUTSIDE == demo.EXIT_LOG_OUTSIDE
    assert selftest.HEALTH_TIMEOUT_S == 15.0
    from server.al import __main__ as core_main
    assert selftest.STOP_FILE == core_main.STOP_FILE


def test_client_stage_skips_without_electron_and_fails_on_a_missing_exe(tmp_path, clean_env):
    """REL-SELFTEST-CLIENT: no electron named skips the client stage; a named
    electron.exe that is missing fails it (stage client) and starts nothing."""
    clean_env.setattr(selftest, "_health",
                      lambda port, token, timeout=2.0: {"name": selftest.NAME, "version": NEW})
    home = tmp_path / "home"
    lay_out(home)
    with_marker(home)
    res = selftest.run(home, NEW, clicked=True, spawn=HermeticSpawn(), probe=lambda p: True)
    assert res.ok and res.detail["client"] == "skipped"
    spawn = HermeticSpawn()
    bad = selftest.run(home, NEW, clicked=True, spawn=spawn, probe=lambda p: True,
                       electron=home / "runtime" / "electron-0" / "electron.exe")
    assert bad.status == selftest.FAILED and bad.stage == "client"
    assert "electron.exe" in bad.reason and bad.moved
    assert not [c for c, _ in spawn.calls if selftest.CLIENT_ARG in c]


def test_client_env_drops_node_switches_and_names_a_scratch_profile(tmp_path):
    env = selftest.client_env({"ELECTRON_RUN_AS_NODE": "1", "node_options": "x", "KEEP": "1"},
                              tmp_path)
    assert env == {"KEEP": "1",
                   selftest.CLIENT_PROFILE_ENV: str(tmp_path / selftest.CLIENT_PROFILE_DIR)}


def test_client_exit_codes_match_the_app():
    text = (ROOT / "app" / "selftest.js").read_text(encoding="ascii")
    m = re.search(r"const EXIT = \{([^}]*)\}", text)
    codes = {k.strip(): int(v) for k, v in (p.split(":") for p in m.group(1).split(","))}
    assert codes["ok"] == 0 and codes["part"] == selftest.CLIENT_EXIT_PART
    assert selftest.CLIENT_EXIT_WORDS == {
        codes["part"]: "a part failed to load", codes["egress"]: "egress lock off",
        codes["window"]: "a window opened", codes["crash"]: "client crashed",
        codes["timeout"]: "client timed out"}
    assert f'const ARG = "{selftest.CLIENT_ARG}"' in text
    assert selftest.CLIENT_PROFILE_ENV in (ROOT / "app" / "main.js").read_text(encoding="ascii")


def test_child_env_drops_caller_overrides(tmp_path):
    env = selftest.child_env(tmp_path, {"AL_RUNTIME_DIR": "x", "AL_SIDECAR_ROOT": "y",
                                        "AL_PORT": "8960", "PYTHONPATH": "z", "KEEP": "1"})
    assert env == {"KEEP": "1", paths.HOME_ENV: str(tmp_path), "AL_HOT_RELOAD": "0"}


def test_fixture_is_synthetic_ascii_lf_and_a_valid_demo_log(tmp_path):
    data = FIXTURE.read_bytes()
    data.decode("ascii")
    assert b"\r" not in data and data.endswith(b"\n")
    lines = data.decode("ascii").splitlines()
    assert lines[0].endswith("***** LOG FILE OPENING *****")
    prefix = re.compile(r"^\d{4}/\d\d/\d\d \d\d:\d\d:\d\d \d+ [0-9a-f]{8} \[(INFO|DEBUG) Client \d+\] ")
    assert all(prefix.match(line) for line in lines[1:])
    # TEST-NET addresses only (RFC 5737), invented character
    assert all("192.0.2." in line for line in lines if "Connecting to instance" in line)
    folder = selftest.prepare_fixture(ROOT, tmp_path / "run")
    real, log = demo.check_fixture(folder)
    assert log.read_bytes() == data
