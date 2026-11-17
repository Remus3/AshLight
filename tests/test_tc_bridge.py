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

from server.al import exepin  # noqa: E402
from server.al.theorycraft import bridge  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "tc_bridge"
FAKE = FIX / "fake_bridge.py"
LUA = ROOT / "server" / "al" / "theorycraft" / "bridge.lua"


def _fake(tmp_path, **kw):
    marker = tmp_path / "starts.txt"
    env = dict(os.environ)
    env["ALB_FAKE_MARKER"] = str(marker)
    kw.setdefault("timeout", 10.0)
    b = bridge.Bridge([sys.executable, "-I", str(FAKE)], cwd=str(tmp_path),
                      env=env, **kw)
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
    # no shell-out, no network, no file writes from the bridge
    for bad in ("os.execute", "io.popen", "socket", "lcurl", 'io.open(', "os.remove"):
        assert bad not in text, bad
    assert "HeadlessWrapper.lua" in text  # drives the unmodified checkout
    assert not re.search(r"pob-?mcp|pob2-?mcp", text, re.I)


# --- live: real luajit.exe + pinned PoB (skip when absent) -------------------

LIVE = pytest.mark.skipif(not bridge.available(),
                          reason="optional calc component absent (setup.ps1 -TcCalc)")
EXPECTED = [p for p in (FIX / "gui_expected.json",
                        ROOT / "ops" / "runtime" / "tc_bridge" / "gui_expected.json")
            if p.is_file()]


@pytest.fixture(scope="module")
def live_bridge():
    b = bridge.Bridge.from_component(start_timeout=180.0, timeout=120.0)
    yield b
    b.close()


@LIVE
@pytest.mark.slow
def test_live_minimal_build_returns_numeric_outputs(live_bridge):
    xml = (FIX / "minimal_build.xml").read_text(encoding="ascii")
    assert live_bridge.load_build(xml)["loaded"] is True
    out = live_bridge.outputs()
    assert out and all(isinstance(v, (int, float, bool)) for v in out.values())
    assert out.get("Life", 0) > 0


@LIVE
@pytest.mark.slow
@pytest.mark.skipif(not EXPECTED, reason="no PoB GUI reference values recorded "
                    "(tests/fixtures/tc_bridge/README.md)")
def test_live_outputs_match_pob_gui_within_0_1_percent(live_bridge):
    ref = json.loads(EXPECTED[0].read_text(encoding="ascii"))
    xml = (EXPECTED[0].parent / ref["build_xml"]).read_text(encoding="utf-8")
    live_bridge.load_build(xml)
    for text in ref.get("items", []):
        live_bridge.set_item(text)
    got = live_bridge.outputs(sorted(ref["outputs"]))
    for key, want in ref["outputs"].items():
        assert key in got, key
        assert got[key] == pytest.approx(want, rel=1e-3), key
