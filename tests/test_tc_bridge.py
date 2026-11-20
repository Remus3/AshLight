"""TC-BRIDGE: the stdio JSON bridge client (server/al/theorycraft/bridge.py)
and our own Lua bridge script (bridge.lua).

Protocol, lazy start, timeout kill, crash restart with state replay and the
"component absent" path run against a Python fake of the Lua side
(tests/fixtures/tc_bridge/fake_bridge.py), so they need no LuaJIT. The live
tests drive the real pinned PoB checkout via luajit.exe and SKIP cleanly when
that optional component is absent (decision 0018, decision 0022).
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import tc_pin  # noqa: E402

from server.al import exepin, paths  # noqa: E402
from server.al.theorycraft import bridge  # noqa: E402
from tc_live_util import LIVE_CALC  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "tc_bridge"
FAKE = FIX / "fake_bridge.py"
LUA = ROOT / "server" / "al" / "theorycraft" / "bridge.lua"


def _fake(tmp_path, **kw):
    marker = tmp_path / "starts.txt"
    env = dict(os.environ)
    env["ALB_FAKE_MARKER"] = str(marker)
    kw.setdefault("timeout", 10.0)
    b = bridge.Bridge([sys.executable, "-I", str(FAKE)], cwd=str(tmp_path),
                      env=env, env_allow=("ALB_FAKE_MARKER",), **kw)
    return b, marker


def _starts(marker):
    try:
        return marker.read_text(encoding="ascii").count("start")
    except OSError:
        return 0


# --- protocol -------------------------------------------------------------

def test_lazy_start_then_round_trip(tmp_path):
    b, marker = _fake(tmp_path)
    try:
        assert not b.running()
        assert _starts(marker) == 0  # nothing spawned before first need
        assert b.load_build("<PathOfBuilding2/>") == {"loaded": True}
        assert b.running()
        assert b.set_item("Rarity: Rare\nGale Bite\nShort Bow") == {"slot": "Weapon 1"}
        out = b.outputs()
        assert out["Life"] == 1010 and out["TotalDPS"] == 123.5
        assert b.outputs(["Life"]) == {"Life": 1010}
        assert _starts(marker) == 1
    finally:
        b.close()
    assert not b.running()


def test_error_reply_raises_bridge_error(tmp_path):
    b, _ = _fake(tmp_path)
    try:
        with pytest.raises(bridge.BridgeError, match="no build loaded"):
            b.outputs()
        assert b.running()  # a reported error does not kill the bridge
        assert b.request("ping") == {"pong": True}
    finally:
        b.close()


def test_noise_lines_on_stdout_are_ignored(tmp_path):
    # the fake prints a non-frame line before its ready frame
    b, _ = _fake(tmp_path)
    try:
        assert b.request("ping") == {"pong": True}
    finally:
        b.close()


def test_rejects_bad_arguments(tmp_path):
    b, marker = _fake(tmp_path)
    with pytest.raises(ValueError):
        b.load_build("")
    with pytest.raises(ValueError):
        b.set_item("   ")
    with pytest.raises(ValueError):
        b.outputs("Life")  # keys must be a list of names
    assert _starts(marker) == 0


# --- timeout kill and crash restart ----------------------------------------

def test_timeout_kills_the_process_and_next_call_restarts(tmp_path):
    b, marker = _fake(tmp_path, timeout=0.5)
    try:
        b.request("ping")
        proc = b._proc
        t0 = time.monotonic()
        with pytest.raises(bridge.BridgeTimeout):
            b.request("sleep")
        assert time.monotonic() - t0 < 5
        assert proc.poll() is not None  # killed, not left hanging
        assert not b.running()
        assert b.request("ping") == {"pong": True}
        assert _starts(marker) == 2
    finally:
        b.close()


def test_crash_restarts_and_replays_build_and_items(tmp_path):
    b, marker = _fake(tmp_path)
    try:
        b.load_build("<PathOfBuilding2/>")
        b.set_item("item one")
        b.set_item("item two")
        b._proc.kill()  # the bridge dies between calls
        b._proc.wait(5)
        out = b.outputs(["Life"])
        assert out == {"Life": 1020}  # build and both items replayed
        assert _starts(marker) == 2
    finally:
        b.close()


def test_new_build_drops_old_items_from_replay(tmp_path):
    b, _ = _fake(tmp_path)
    try:
        b.load_build("<PathOfBuilding2/>")
        b.set_item("old item")
        b.load_build("<PathOfBuilding2/>")
        b._proc.kill()
        b._proc.wait(5)
        assert b.outputs(["Life"]) == {"Life": 1000}
    finally:
        b.close()


def test_crash_during_request_gives_up_after_one_restart(tmp_path):
    b, marker = _fake(tmp_path)
    try:
        with pytest.raises(bridge.BridgeError, match="exited"):
            b.request("die")
        assert _starts(marker) == 2  # one restart, then it stops trying
        assert b.request("ping") == {"pong": True}
    finally:
        b.close()


def test_missing_executable_is_bridge_unavailable(tmp_path):
    b = bridge.Bridge([str(tmp_path / "no-such-luajit.exe")], cwd=str(tmp_path))
    with pytest.raises(bridge.BridgeUnavailable):
        b.request("ping")


# --- confinement (TC-CALC-CONFINE-PROC, decision 0022 amendment) -----------

# A fake child: the bridge protocol plus "env" (its environment names) and
# "spawn" (tries to start a second process that would write a marker file).
CHILD = r"""
import json, os, subprocess, sys
def send(o):
    sys.stdout.write("ALB1 " + json.dumps(o) + "\n")
    sys.stdout.flush()
send({"id": 0, "ok": True, "result": {"ready": True}})
for line in sys.stdin:
    req = json.loads(line)
    rid, cmd = req["id"], req["cmd"]
    if cmd == "env":
        send({"id": rid, "ok": True, "result": {"names": sorted(os.environ)}})
    elif cmd == "spawn":
        mark = os.path.join(os.getcwd(), "grandchild.txt")
        code = "open(%r, 'w').write('ran')" % mark
        try:
            rc = subprocess.run([sys.executable, "-I", "-c", code], timeout=20).returncode
            err = None
        except Exception as exc:
            rc, err = None, str(exc)
        send({"id": rid, "ok": True, "result": {"rc": rc, "error": err}})
    elif cmd == "quit":
        send({"id": rid, "ok": True, "result": {}})
        break
"""
WINDOWS = pytest.mark.skipif(os.name != "nt", reason="job objects are Windows only")


def _child(tmp_path, env=None, **kw):
    script = tmp_path / "child.py"
    script.write_text(CHILD, encoding="ascii")
    return bridge.Bridge([sys.executable, "-I", str(script)], cwd=str(tmp_path),
                         env=env, timeout=30.0, **kw)


def test_child_environment_holds_only_allowed_names(tmp_path):
    env = dict(os.environ)
    env.update({"LUA_INIT": "os.exit(1)", "AL_PROBE_SECRET": "x",
                "TEMP": str(tmp_path), "TMP": str(tmp_path)})
    b = _child(tmp_path, env=env)
    try:
        names = {n.upper() for n in b.request("env")["names"] if not n.startswith("=")}
    finally:
        b.close()
    assert names <= set(bridge.ENV_ALLOW)
    assert {"TEMP", "TMP"} <= names
    assert "LUA_INIT" not in names and "AL_PROBE_SECRET" not in names
    assert "PATH" not in names
    # the component's own environment is built from the same allow-list
    assert set(bridge.child_env(env)) <= set(env)
    assert {n.upper() for n in bridge.child_env(env)} <= set(bridge.ENV_ALLOW)
    assert "X_EXTRA" in bridge.child_env({"X_EXTRA": "1"}, extra=("x_extra",))


@WINDOWS
def test_child_cannot_start_a_second_process(tmp_path):
    b = _child(tmp_path)
    try:
        b.request("env")  # starts the child inside its job
        limits = b._job.limits()
        assert limits["active_processes"] == 1
        assert limits["process_memory"] == bridge.JOB_MEMORY_LIMIT > 384 << 20
        assert limits["flags"] & 0x2000  # kill on job close
        got = b.request("spawn")
        assert got["rc"] != 0 or got["error"]  # refused or killed at birth
        assert not (tmp_path / "grandchild.txt").exists()
        assert b.request("env")["names"]  # the child itself lives on
    finally:
        b.close()


def test_confinement_failure_refuses_the_start(tmp_path, monkeypatch):
    class BadJob:
        closed = False

        def adopt(self, pid):
            raise OSError("assign refused")

        def close(self):
            BadJob.closed = True

    monkeypatch.setattr(bridge, "open_job", BadJob)
    b = _child(tmp_path)
    with pytest.raises(bridge.BridgeUnavailable, match="confine"):
        b.request("env")
    assert BadJob.closed and not b.running() and b._job is None


@WINDOWS
def test_job_closes_with_the_bridge(tmp_path):
    b = _child(tmp_path)
    try:
        b.request("env")
        job, proc = b._job, b._proc
        assert job is not None and not job.closed
        job.close()  # what the kernel does when the core dies
        assert proc.wait(10) is not None  # kill on job close
    finally:
        b.close()
    b.request("env")  # a fresh start gets a fresh job
    job, proc = b._job, b._proc
    assert job is not None and not job.closed
    b.close()
    assert job.closed and b._job is None
    assert proc.poll() is not None and not b.running()


# --- component discovery (core runs without it) -----------------------------

def test_component_paths_match_tc_pin_layout(tmp_path):
    env = {"AL_SIDECAR_ROOT": str(tmp_path)}
    lay = tc_pin.layout(tc_pin.load_pins(), environ=env)
    comp = bridge.component_paths(environ=env)
    assert comp["luajit"] == lay["luajit_exe"]
    assert comp["pob_src"] == lay["pob2_checkout"] / "src"
    assert comp["script"] == LUA
    assert comp["log"].parent == tmp_path / "Logs"


def test_absent_component_is_reported_and_never_spawns(tmp_path):
    env = {"AL_SIDECAR_ROOT": str(tmp_path)}
    assert bridge.available(environ=env) is False
    assert "luajit" in bridge.status(environ=env)["missing"]
    with pytest.raises(bridge.BridgeUnavailable):
        bridge.Bridge.from_component(environ=env)


def test_present_component_builds_luajit_command(tmp_path):
    env = {"AL_SIDECAR_ROOT": str(tmp_path)}
    comp = bridge.component_paths(environ=env)
    comp["luajit"].parent.mkdir(parents=True)
    comp["luajit"].write_bytes(b"")
    exepin.record(comp["luajit"])  # AUDIT-EXE-PATH: setup records the hash
    comp["pob_src"].mkdir(parents=True)
    (comp["pob_src"] / "HeadlessWrapper.lua").write_text("", encoding="ascii")
    assert bridge.available(environ=env) is True
    b = bridge.Bridge.from_component(environ=env)
    assert b.argv == [str(comp["luajit"]), str(LUA)]
    assert b.cwd == str(comp["pob_src"])
    assert b.env["TEMP"] == str(tmp_path / "Temp")
    assert not b.running()  # starts only on first need


def test_shared_bridge_is_lazy_and_reused(tmp_path, monkeypatch):
    env = {"AL_SIDECAR_ROOT": str(tmp_path)}
    monkeypatch.setattr(bridge, "_SHARED", None)
    with pytest.raises(bridge.BridgeUnavailable):
        bridge.shared(environ=env)
    comp = bridge.component_paths(environ=env)
    comp["luajit"].parent.mkdir(parents=True)
    comp["luajit"].write_bytes(b"")
    exepin.record(comp["luajit"])  # AUDIT-EXE-PATH: setup records the hash
    comp["pob_src"].mkdir(parents=True)
    (comp["pob_src"] / "HeadlessWrapper.lua").write_text("", encoding="ascii")
    first = bridge.shared(environ=env)
    assert bridge.shared(environ=env) is first
    assert not first.running()
    bridge.shutdown_shared()


def test_core_does_not_import_the_bridge():
    for path in (ROOT / "server" / "al").glob("*.py"):
        text = path.read_text(encoding="ascii")
        assert "theorycraft.bridge" not in text and "import bridge" not in text, path


# --- the Lua script (static checks; runs only under the live tests) ---------

def test_lua_script_is_our_own_and_stays_inside_the_floor():
    text = LUA.read_text(encoding="ascii")
    assert "ALB1 " in text  # frame prefix shared with the client
    assert bridge.FRAME_PREFIX == "ALB1 "
    for cmd in ("ping", "load_build", "set_item", "outputs", "quit"):
        assert f'"{cmd}"' in text, cmd
    # no shell-out, no network, no file writes from the bridge; the names
    # appear only where the lockdown takes them away and the test-only probe
    # tries them (TC-CALC-CONFINE-LUA)
    lock, probe, rest = _lua_parts(text)
    for bad in ("os.execute", "io.popen", "socket", "lcurl", 'io.open(', "os.remove"):
        assert bad not in rest, bad
    assert "HeadlessWrapper.lua" in text  # drives the unmodified checkout
    assert not re.search(r"pob-?mcp|pob2-?mcp", text, re.I)
    assert lock and probe


LOCK_START = "-- " + "-" * 60 + " lockdown --"
LOCK_END = "-- " + "-" * 60 + " commands --"


def _lua_parts(text):
    """(lockdown block, probe handler, the rest) of bridge.lua."""
    a, b = text.index(LOCK_START), text.index(LOCK_END)
    p = text.index("-- TC-CALC-CONFINE-LUA: test-only")
    q = text.index("-- " + "-" * 64 + " loop --")
    assert a < b < p < text.index('handlers["probe_confinement"]') < q
    return text[a:b], text[p:q], text[:a] + text[b:p] + text[q:]


def test_lockdown_runs_after_pob_loads_and_drops_each_entry_point():
    """TC-CALC-CONFINE-LUA: one lockdown block after the HeadlessWrapper
    load and the start-up checks, before any command; it removes the shell,
    process, native library and FFI entry points, refuses file deletes and
    renames, keeps io.open read-only and hides the originals from debug."""
    text = LUA.read_text(encoding="ascii")
    lock, _, _ = _lua_parts(text)
    load = text.index('pcall(dofile, "HeadlessWrapper.lua")')
    prompt = text.index("PoB start-up message")
    assert load < prompt < text.index(LOCK_START) < text.index("handlers = {}")
    for line in ("os.execute = nil", "io.popen = nil", "os.tmpname = nil",
                 "package.loadlib = nil", 'package.cpath = ""',
                 'package.loaded["ffi"] = nil', 'package.preload["ffi"] = nil',
                 'rawset(_G, "ffi", nil)', "os.remove = function() return nil",
                 "os.rename = function() return nil", "io.open = function(name, mode)",
                 "io.output = function(file)"):
        assert line in lock, line
    assert re.search(r'mode == nil or mode == "r" or mode == "rb" then return real_open',
                     lock)
    for name in ("getlocal", "setlocal", "getupvalue", "setupvalue", "upvalueid",
                 "upvaluejoin", "getregistry"):
        assert f'"{name}"' in lock, name
    # pob_main() keeps its own copy of getupvalue from before the lockdown
    assert text.index("local getupvalue = ") < text.index("local function pob_main()")


# --- live: real luajit.exe + pinned PoB (skip when absent) -------------------

LIVE = pytest.mark.skipif(not bridge.available(),
                          reason="optional calc component absent (setup.ps1 -TcCalc)")
# TC-LIVE: the reference may also live beside the component in the AL
# sidecar Cache (a public build whose owner was not asked stays untracked).
EXPECTED = [p for p in (FIX / "gui_expected.json",
                        ROOT / "ops" / "runtime" / "tc_bridge" / "gui_expected.json",
                        paths.all_runtime_paths()["tc_bridge_ref"])
            if p.is_file()]


@pytest.fixture(scope="module")
def live_bridge():
    """Its own process: the reload / leak test must not inherit another
    test's loaded builds (TEST-FULLSTACK-CALC-WARM keeps it apart)."""
    b = bridge.Bridge.from_component(start_timeout=180.0, timeout=120.0)
    yield b
    b.close()


@LIVE_CALC
@LIVE
@pytest.mark.slow
def test_live_minimal_build_returns_numeric_outputs(warm_bridge):
    live_bridge = warm_bridge  # TEST-FULLSTACK-CALC-WARM
    xml = (FIX / "minimal_build.xml").read_text(encoding="ascii")
    assert live_bridge.load_build(xml)["loaded"] is True
    out = live_bridge.outputs()
    assert out and all(isinstance(v, (int, float, bool)) for v in out.values())
    assert out.get("Life", 0) > 0


@LIVE_CALC
@LIVE
@pytest.mark.slow
def test_live_confined_calls_fail(warm_bridge):
    """TC-CALC-CONFINE-LUA: inside the running bridge (PoB loaded) a shell
    call, a write-mode open, a delete, a rename, an io.output redirect, FFI
    and the native loader all fail; reading PoB's own files still works."""
    temp = Path(warm_bridge.env["TEMP"])
    probe_file = temp / "alb-confine-probe.txt"
    before = probe_file.exists()
    got = warm_bridge.request("probe_confinement")
    assert got["execute"]["ok"] is False and "nil value" in got["execute"]["error"]
    assert got["popen"] == "nil" and got["tmpname"] == "nil"
    assert got["loadlib"] == "nil" and got["cpath"] == "" and got["ffi"] is False
    for op in ("remove", "rename"):
        assert got[op]["ok"] is False and "refused" in got[op]["error"], op
    assert got["output"]["ok"] is False and "refused" in got["output"]["error"]
    assert set(got["writes"]) == {"w", "wb", "a", "a+", "r+", "w+b"}
    for mode, res in got["writes"].items():
        assert res["ok"] is False and "refused" in res["error"], mode
    assert got["read"]["ok"] is True
    assert got["getupvalue"] == "nil" and got["getlocal"] == "nil"
    assert probe_file.exists() == before  # nothing created
    assert warm_bridge.request("ping") == {"pong": True}  # the bridge lives on


@LIVE_CALC
@LIVE
@pytest.mark.slow
def test_live_reload_does_not_leak_state(live_bridge):
    """TC-DRIFT / research 0017: PoB dev touched the headless global cache
    cleanup; loading build A, then B, then A again must give A's outputs."""
    a = (FIX / "minimal_build.xml").read_text(encoding="ascii")
    # TC-LIVE: PoB-PoE2 v0.23.1 derives the level from spent points unless
    # characterLevelAutoMode is off, so level="90" alone changes nothing.
    b = a.replace('level="1"', 'level="90" characterLevelAutoMode="false"', 1)
    assert a != b
    live_bridge.load_build(a)
    first = live_bridge.outputs()
    live_bridge.load_build(b)
    other = live_bridge.outputs()
    assert other.get("Life") != first.get("Life")  # B really differs
    live_bridge.load_build(a)
    assert live_bridge.outputs() == first


@LIVE_CALC
@LIVE
@pytest.mark.slow
@pytest.mark.skipif(not EXPECTED, reason="no PoB GUI reference values recorded "
                    "(tests/fixtures/tc_bridge/README.md)")
def test_live_outputs_match_pob_gui_within_0_1_percent(warm_bridge):
    live_bridge = warm_bridge  # TEST-FULLSTACK-CALC-WARM
    ref = json.loads(EXPECTED[0].read_text(encoding="ascii"))
    xml = (EXPECTED[0].parent / ref["build_xml"]).read_text(encoding="utf-8")
    live_bridge.load_build(xml)
    for text in ref.get("items", []):
        live_bridge.set_item(text)
    got = live_bridge.outputs(sorted(ref["outputs"]))
    for key, want in ref["outputs"].items():
        assert key in got, key
        assert got[key] == pytest.approx(want, rel=1e-3), key
