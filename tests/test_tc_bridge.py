"""TC-BRIDGE: the stdio JSON bridge client (server/al/theorycraft/bridge.py)
and our own Lua bridge script (bridge.lua).

Protocol, lazy start, timeout kill, crash restart with state replay and the
"component absent" path run against a Python fake of the Lua side
(tests/fixtures/tc_bridge/fake_bridge.py), so they need no LuaJIT. The live
tests drive the real pinned PoB checkout via luajit.exe and SKIP cleanly when
that optional component is absent (decision 0018, decision 0022).
"""

import os
import re
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import tc_pin  # noqa: E402

from server.al import exepin, logs, prio  # noqa: E402
from server.al.theorycraft import bridge, calcwire  # noqa: E402
import tc_live_util  # noqa: E402
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


# --- RUN-CALC-PRIORITY (F-107) and RUN-OBS-LOGS-PY (F-090) -------------------

def test_started_luajit_has_below_normal_priority(tmp_path, monkeypatch):
    """The calc child (luajit; here the fake child through the same start
    path) starts with the below-normal priority class, read back from the
    running process."""
    flags = []
    real = bridge.subprocess.Popen

    def spy(*a, **kw):
        flags.append(kw.get("creationflags", 0))
        return real(*a, **kw)
    monkeypatch.setattr(bridge.subprocess, "Popen", spy)
    b = _child(tmp_path)
    try:
        b.request("env")
        assert flags and flags[0] == prio.below_normal(flags[0])
        if os.name == "nt":
            assert flags[0] & prio.BELOW_NORMAL
            assert prio.priority_class(b._proc.pid) == prio.BELOW_NORMAL
    finally:
        b.close()


def test_each_calc_start_rotates_its_log_and_writes_a_banner(tmp_path):
    log = tmp_path / "logs" / "tc-bridge.log"
    log.parent.mkdir()
    old = b"missing node\n" * (1_200_000 // 13)
    log.write_bytes(old)
    b = _child(tmp_path, log_path=log)
    try:
        b.request("env")
        assert logs.backup_path(log).read_bytes() == old  # one old file kept
        first = log.read_text(encoding="ascii").splitlines()[0]
        assert re.match(r"^\d{4}-\d\d-\d\dT[\d:.]+Z INFO tc-bridge\[\d+\] AshLight \S+ "
                        r"calc bridge start \(pid \d+", first), first
        b.close()
        b.request("env")  # a second start: no rotation, a second banner
        lines = log.read_text(encoding="ascii").splitlines()
        assert sum(" calc bridge start (pid " in ln for ln in lines) == 2
        assert logs.backup_path(log).read_bytes() == old
    finally:
        b.close()


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


def _pin_fake_lua(monkeypatch, comp):
    """Pin the fake checkout's own Lua digest (the real pin names the real
    PoB tree, which a fake never matches)."""
    want = bridge.lua_digest(comp["pob_src"].parent)
    monkeypatch.setattr(bridge, "pinned_lua_digest", lambda: want)
    return want


def test_present_component_builds_luajit_command(tmp_path, monkeypatch):
    env = {"AL_SIDECAR_ROOT": str(tmp_path)}
    comp = bridge.component_paths(environ=env)
    comp["luajit"].parent.mkdir(parents=True)
    comp["luajit"].write_bytes(b"")
    exepin.record(comp["luajit"])  # AUDIT-EXE-PATH: setup records the hash
    comp["pob_src"].mkdir(parents=True)
    (comp["pob_src"] / "HeadlessWrapper.lua").write_text("", encoding="ascii")
    assert bridge.status(environ=env)["missing"] == [bridge.LUA_MISSING]
    _pin_fake_lua(monkeypatch, comp)
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


# --- TC-CALC-VERIFY-USE: PoB's Lua files against their pinned digest -------

def _lua_component(tmp_path):
    """A fake component whose checkout holds a few Lua files and one data
    file, luajit.exe recorded as setup does."""
    env = {"AL_SIDECAR_ROOT": str(tmp_path)}
    comp = bridge.component_paths(environ=env)
    comp["luajit"].parent.mkdir(parents=True)
    comp["luajit"].write_bytes(b"lj")
    exepin.record(comp["luajit"])
    top = comp["pob_src"].parent
    (top / "runtime" / "lua").mkdir(parents=True)
    comp["pob_src"].mkdir(parents=True)
    (comp["pob_src"] / "HeadlessWrapper.lua").write_text("-- wrapper\n", encoding="ascii")
    (comp["pob_src"] / "Launch.lua").write_text("-- launch\n", encoding="ascii")
    (top / "runtime" / "lua" / "xml.lua").write_text("-- xml\n", encoding="ascii")
    (comp["pob_src"] / "notes.txt").write_text("data\n", encoding="ascii")
    return env, comp


def test_edited_lua_file_makes_from_component_unavailable(tmp_path, monkeypatch):
    env, comp = _lua_component(tmp_path)
    top = comp["pob_src"].parent
    # the bridge's digest is tools/tc_pin.py's lua_sha256 form, byte for byte
    assert bridge.lua_digest(top) == tc_pin.tree_digest(top, select=tc_pin.is_lua)
    want = _pin_fake_lua(monkeypatch, comp)
    assert bridge.status(environ=env) == {"available": True, "missing": []}
    b = bridge.Bridge.from_component(environ=env)
    assert b.lua_check == (top, want)
    # a data file is not runnable Lua: no change
    (comp["pob_src"] / "notes.txt").write_text("other\n", encoding="ascii")
    assert bridge.available(environ=env) is True
    spawned = []
    monkeypatch.setattr(bridge.subprocess, "Popen",
                        lambda *a, **k: spawned.append(a) or pytest.fail("spawned"))
    for change in (lambda: (comp["pob_src"] / "Launch.lua").write_text(
                       "os.execute('x')\n", encoding="ascii"),
                   lambda: (top / "runtime" / "lua" / "extra.lua").write_text(
                       "-- added\n", encoding="ascii")):
        change()
        st = bridge.status(environ=env)
        assert st == {"available": False, "missing": [bridge.LUA_MISSING]}
        with pytest.raises(bridge.BridgeUnavailable) as err:
            b.request("ping")
        assert str(err.value) == bridge.LUA_CHANGED == "calc component changed, re-run setup"
        assert not b.running()
        (comp["pob_src"] / "Launch.lua").write_text("-- launch\n", encoding="ascii")
        extra = top / "runtime" / "lua" / "extra.lua"
        if extra.exists():
            extra.unlink()
    assert spawned == []
    assert bridge.available(environ=env) is True  # restored files verify again
    # a pin file without a well-formed digest verifies nothing (fail closed)
    monkeypatch.setattr(bridge, "pinned_lua_digest", lambda: None)
    assert bridge.status(environ=env)["missing"] == ["pins"]
    assert bridge.lua_verified(top, None) is False


def test_digest_check_is_cached_by_mtime_and_size(tmp_path, monkeypatch):
    _, comp = _lua_component(tmp_path)
    top = comp["pob_src"].parent
    want = bridge.lua_digest(top)
    hashed = []
    real = bridge._hash_file
    monkeypatch.setattr(bridge, "_hash_file", lambda p: hashed.append(p) or real(p))
    monkeypatch.setattr(bridge, "_LUA_CACHE", {})
    assert bridge.lua_verified(top, want) is True
    assert len(hashed) == 3  # every Lua file read once
    hashed.clear()
    assert bridge.lua_verified(top, want) is True
    assert hashed == []  # unchanged sizes and mtimes: stat only
    launch = comp["pob_src"] / "Launch.lua"
    st = launch.stat()
    os.utime(launch, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))
    assert bridge.lua_verified(top, want) is True  # same bytes, new mtime
    assert len(hashed) == 3
    hashed.clear()
    assert bridge.lua_verified(top, want) is True
    assert hashed == []
    launch.write_text("-- launch, longer\n", encoding="ascii")  # size changes
    assert bridge.lua_verified(top, want) is False
    assert len(hashed) == 3
    hashed.clear()
    assert bridge.lua_verified(top, want) is False  # a mismatch is never cached
    assert len(hashed) == 3
    hashed.clear()
    assert bridge.lua_verified(top, "0" * 64) is False  # another pin: no cache hit


def test_lua_loader_guard_refuses_native_modules():
    """TC-CALC-VERIFY-USE: the C loaders of require answer only for the
    allow-listed lua-utf8 and only until the lockdown; the guard is set up
    before PoB loads."""
    text = LUA.read_text(encoding="ascii")
    lock, _, _ = _lua_parts(text)
    guard = text.index("local NATIVE_ALLOW = ")
    assert guard < text.index('pcall(dofile, "HeadlessWrapper.lua")')
    assert 'local NATIVE_ALLOW = { ["lua-utf8"] = true }' in text
    assert "for i = 3, #loaders do" in text
    assert "if native_open and NATIVE_ALLOW[name] then return real(name) end" in text
    assert "native_open = false" in lock


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


# --- KINDLER-SUPPORT-FIT: PoB's support applicability ------------------------

def test_support_fit_command_reads_pobs_own_effect_list():
    """The command reads PoB's verdict, never an own rule: a support applies
    when calcs.createActiveSkill put it in the active skill's effectList;
    the linked supports come from its supportList. Read only."""
    text = LUA.read_text(encoding="ascii")
    _, _, rest = _lua_parts(text)
    start = text.index('handlers["support_fit"]')
    body = text[start:text.index("\nend\n", start)]
    assert "build.calcsTab.mainEnv" in body and "env.player.activeSkillList" in body
    assert "active.supportList" in body and "active.effectList" in body
    assert "for i = 2, #active.effectList do" in body  # index 1 is the active effect
    assert "applies = used[sup] == true" in body
    for bad in ("set_item", "load_build", "SetSelItemId", "AddItem", "buildFlag",
                "canGrantedEffectSupportActiveSkill(", "skillTypes"):
        assert bad not in body, bad
    assert 'handlers["support_fit"]' in rest  # outside the lockdown and the probe
    assert text.index(LOCK_END) < start


POB_SUPPORT_SHAPE = [
    ("Modules/CalcActiveSkill.lua", r"activeSkill\.effectList\s*=\s*\{\s*activeEffect\s*\}"),
    ("Modules/CalcActiveSkill.lua",
     r"if calcLib\.canGrantedEffectSupportActiveSkill\(supportEffect\.grantedEffect, "
     r"activeSkill\) then\s*\n\s*t_insert\(activeSkill\.effectList, supportEffect\)"),
    ("Modules/CalcActiveSkill.lua", r"supportList\s*=\s*supportList"),
    ("Modules/CalcSetup.lua", r"t_insert\(env\.player\.activeSkillList, activeSkill\)"),
    ("Classes/CalcsTab.lua", r"self\.mainEnv\s*=\s*self\.calcs\.buildOutput\("),
]


@pytest.mark.parametrize("rel,pattern", POB_SUPPORT_SHAPE,
                         ids=[r[1][:40] for r in POB_SUPPORT_SHAPE])
def test_pinned_pob_still_has_the_support_fit_shape(rel, pattern):
    """The PoB fields the support_fit command reads, in the pinned checkout
    (skips when the optional component is absent)."""
    try:
        src = bridge.component_paths()["pob_src"]
    except (OSError, ValueError, KeyError):
        pytest.skip("calc component pins unreadable")
    path = src / rel
    if not path.is_file():
        pytest.skip("pinned PoB checkout absent (setup.ps1 -TcCalc)")
    text = path.read_text(encoding="utf-8", errors="replace")
    assert re.search(pattern, text), (
        f"PoB drift: {rel} no longer matches {pattern!r}; bridge.lua support_fit "
        "relies on it (update it before moving the pin)")


class _FitBridge:
    def __init__(self, reply=None, fail=False):
        self.reply = reply
        self.fail = fail
        self.sent = []

    def request(self, cmd, **args):
        self.sent.append((cmd, args))
        if self.fail:
            raise bridge.BridgeError("unknown command: support_fit")
        return self.reply

    def load_build(self, xml):
        self.sent.append(("load_build", {}))
        return {"loaded": True}


def test_support_fit_reader_normalises_the_reply():
    reply = {"skills": [
        {"skill": "Spark", "supports": [{"name": "Pierce I", "applies": True},
                                         {"name": "Close Combat I", "applies": False},
                                         {"name": "Odd", "applies": "yes"}, "junk"]},
        {"skill": "Elemental Storm", "supports": {}},  # an empty Lua list
        {"skill": "Raise", "supports": [{"name": "Minion Mastery", "applies": False}]},
        {"skill": "Raise", "supports": [{"name": "Minion Mastery", "applies": True}]},
        {"skill": "", "supports": [{"name": "X", "applies": True}]},
        {"skill": "N" * (calcwire.FIT_NAME_MAX + 1), "supports": []},
        "junk"]}
    b = _FitBridge(reply)
    assert calcwire.support_fit(b) == {
        "Spark": {"Pierce I": True, "Close Combat I": False},
        "Raise": {"Minion Mastery": True}}  # either active skill of the gem
    assert b.sent == [("support_fit", {})]
    for bad in (None, {}, {"skills": {}}, {"skills": "x"}, []):
        assert calcwire.support_fit(_FitBridge(bad)) == {}
    many = {"skills": [{"skill": f"S{i}", "supports": [
        {"name": f"P{j}", "applies": True} for j in range(40)]} for i in range(100)]}
    got = calcwire.support_fit(_FitBridge(many))
    assert len(got) == calcwire.FIT_MAX_SKILLS
    assert all(len(v) == calcwire.FIT_MAX_SUPPORTS for v in got.values())
    with pytest.raises(bridge.BridgeError):
        calcwire.support_fit(_FitBridge(fail=True))


def test_calc_fit_loads_the_build_once_and_is_tracked():
    reply = {"skills": [{"skill": "Spark", "supports": [{"name": "Pierce I",
                                                         "applies": True}]}]}
    b = _FitBridge(reply)
    calc = calcwire.make_calc(lambda: b)
    build = type("B", (), {"raw_xml": "<PathOfBuilding2/>"})()
    assert calcwire.build_fit(calc, build) == {"Spark": {"Pierce I": True}}
    assert calcwire.build_fit(calc, build) == {"Spark": {"Pierce I": True}}
    assert [c for c, _ in b.sent] == ["load_build", "support_fit", "support_fit"]
    with pytest.raises(calcwire.OutputError):
        calc.fit(type("B", (), {"raw_xml": " "})())
    assert calcwire.build_fit(lambda build, swaps: {}, build) == {}  # no fit: no answer
    clock = [100.0]
    prov = calcwire.Provider(lambda: True, available=lambda: True, get_bridge=lambda: b,
                             clock=lambda: clock[0], stop=lambda: None)
    tracked = prov()
    clock[0] = 5000.0
    assert tracked.fit(build) == {"Spark": {"Pierce I": True}}
    assert prov.last_used == 5000.0 and prov.held()


# --- live: real luajit.exe + pinned PoB (skip when absent) -------------------

LIVE = pytest.mark.skipif(not bridge.available(),
                          reason="optional calc component absent (setup.ps1 -TcCalc)")
# TC-LIVE: the reference may also live beside the component in the AL
# sidecar Cache (a public build whose owner was not asked stays untracked).
# LOOP-DRIFT-REF: references are keyed by tag (tc_live_util.pick_reference).
EXPECTED = tc_live_util.gui_references()


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
    # KINDLER-SUPPORT-FIT: the command answers and the reader takes its
    # shape. Not compared with {}: after a load whose skill set is empty,
    # PoB's mainEnv still lists the previous build's skills (main_skill
    # shows the same); Kindler never asks fit for a build without links
    # (kindlerplan.stage_fits), and each build with skills replaces the list.
    got = live_bridge.request("support_fit")
    assert isinstance(got.get("skills"), (list, dict))
    fits = calcwire.support_fit(live_bridge)
    assert all(isinstance(v, bool) for sups in fits.values() for v in sups.values())


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
    # TC-CALC-VERIFY-USE (the package's test_live_native_require_fails, kept
    # in this test: tests/test_marks.py CALC_TESTS pins this file's live
    # calc tests): a native require fails, even one whose DLL sits in PoB's
    # runtime
    assert set(got["native"]) == {"socket", "lzip"}
    for name, res in got["native"].items():
        assert res["ok"] is False, name
        assert "refused by the AshLight calc bridge" in res["error"], name
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
    """LOOP-DRIFT-REF: the reference is chosen by the tag under test. The
    same tag compares the recorded numbers within 0.1 percent; another tag
    reports per-key deltas and passes only with a session's written
    acceptance recorded in that reference for the tag under test."""
    live_bridge = warm_bridge  # TEST-FULLSTACK-CALC-WARM
    tag = tc_live_util.tested_tag()
    mode, ref_path, ref = tc_live_util.pick_reference(tag, EXPECTED)
    xml = (ref_path.parent / ref["build_xml"]).read_text(encoding="utf-8")
    live_bridge.load_build(xml)
    for text in ref.get("items", []):
        live_bridge.set_item(text)
    got = live_bridge.outputs(sorted(ref["outputs"]))
    if mode == "same":
        for key, want in ref["outputs"].items():
            assert key in got, key
            assert got[key] == pytest.approx(want, rel=1e-3), key
        return
    lines = tc_live_util.delta_lines(tc_live_util.reference_deltas(ref["outputs"], got))
    print(f"GUI reference is for PoB {ref['pob']}, tested {tag}; per-key deltas:")
    for line in lines:
        print("  " + line)
    if tc_live_util.accepted_for(ref, tag) is None:
        pytest.fail(f"no GUI reference recorded for {tag} (newest is {ref['pob']}); "
                    "record one or a session's written acceptance "
                    f'("accepted": {{"{tag}": "<YYYY-MM-DD> <why>"}}); deltas: '
                    + "; ".join(lines))
