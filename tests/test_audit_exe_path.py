"""AUDIT-EXE-PATH (audit finding S5, docs/audit/2026-11-17-audit.md).

Windows CreateProcess also searches the current directory for a bare name,
so every Windows tool runs by its System32 absolute path, a PATH tool by an
absolute PATH entry only, and luajit.exe (built locally, no published hash)
runs only when it matches the SHA-256 recorded when setup built it: checked
by tc_pin before a no-op, by bridge.status and before every bridge exec.
"""

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import tc_pin  # noqa: E402

from server.al import exepin, gfx  # noqa: E402
from server.al.theorycraft import bridge  # noqa: E402


# -- absolute Windows tools
def test_system_tool_is_absolute_under_system32():
    p = exepin.system_tool("cmd.exe")
    assert p.is_absolute() and p.name == "cmd.exe"
    assert p.parent.name.lower() == "system32"
    ps = exepin.system_tool("WindowsPowerShell", "v1.0", "powershell.exe")
    assert ps.is_absolute() and ps.parts[-4].lower() == "system32"


@pytest.mark.skipif(os.name != "nt", reason="Windows only")
def test_system_tool_exists_on_windows():
    assert exepin.system_tool("cmd.exe").is_file()
    assert exepin.system_tool("WindowsPowerShell", "v1.0", "powershell.exe").is_file()


def test_gfx_runs_powershell_by_absolute_path(monkeypatch):
    seen = {}

    def fake_run(argv, **kw):
        seen["argv"] = argv
        raise subprocess.TimeoutExpired(argv, 1)
    monkeypatch.setattr(gfx.os, "name", "nt")
    monkeypatch.setattr(gfx.subprocess, "run", fake_run)
    assert gfx.run_query() is None
    exe = Path(seen["argv"][0])
    assert exe.is_absolute() and exe.name.lower() == "powershell.exe"


def test_build_plan_uses_absolute_commands(tmp_path):
    plan = tc_pin.build_plan(lambda n: "cl.exe" if n == "cl" else None)
    assert Path(plan[0]).is_absolute() and Path(plan[0]).name == "cmd.exe"
    tools = tmp_path / "mingw" / "bin"
    tools.mkdir(parents=True)
    for name in ("mingw32-make.exe", "gcc.exe"):
        (tools / name).write_bytes(b"")
    env = {"PATH": os.pathsep.join([".", "relative\\bin", str(tools)]), "PATHEXT": ".EXE"}
    plan = tc_pin.build_plan(environ=env)
    assert Path(plan[0]).is_absolute() and Path(plan[0]).parent == tools


def test_which_abs_ignores_cwd_and_relative_path_entries(tmp_path, monkeypatch):
    (tmp_path / "evil.exe").write_bytes(b"")
    monkeypatch.chdir(tmp_path)
    env = {"PATH": os.pathsep.join([".", "", "sub"]), "PATHEXT": ".EXE"}
    assert exepin.which_abs("evil", env) is None
    env = {"PATH": str(tmp_path), "PATHEXT": ".EXE"}
    assert exepin.which_abs("evil", env) == tmp_path / "evil.exe"


def test_no_bare_windows_tool_in_argv_literals():
    """No subprocess argv in server/ or tools/ starts with a bare .exe name."""
    bad = []
    for base in ("server", "tools"):
        for path in (ROOT / base).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="ascii"))
            for node in ast.walk(tree):
                if isinstance(node, ast.List) and node.elts:
                    first = node.elts[0]
                    if (isinstance(first, ast.Constant) and isinstance(first.value, str)
                            and first.value.lower() in ("powershell.exe", "cmd.exe",
                                                        "mingw32-make", "pwsh.exe")):
                        bad.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert bad == []


# -- luajit.exe hash pin
def test_record_and_verify(tmp_path):
    exe = tmp_path / "luajit.exe"
    assert exepin.verified(exe) is False
    exe.write_bytes(b"built")
    assert exepin.verified(exe) is False  # nothing recorded: untrusted
    exepin.record(exe)
    assert exepin.verified(exe) is True
    exe.write_bytes(b"swapped")
    assert exepin.verified(exe) is False


def _lay(tmp_path):
    return tc_pin.layout(tc_pin.load_pins(), environ={"AL_SIDECAR_ROOT": str(tmp_path)})


def test_ensure_luajit_does_not_trust_an_unrecorded_exe(tmp_path):
    lay = _lay(tmp_path)
    (lay["luajit_source"] / "src").mkdir(parents=True)
    lay["luajit_exe"].write_bytes(b"planted")
    runs = []

    def run(cmd, cwd=None, env=None, capture_output=None, timeout=None):
        runs.append(cmd)
        lay["luajit_exe"].write_bytes(b"rebuilt")

        class R:
            returncode = 0
        return R()
    status = tc_pin.ensure_luajit(lay, which=lambda n: "cl.exe" if n == "cl" else None,
                                  run=run, environ={})
    assert status == "ready" and len(runs) == 1
    assert lay["luajit_exe"].read_bytes() == b"rebuilt"
    assert exepin.verified(lay["luajit_exe"])
    # now recorded: a second call is a no-op
    assert tc_pin.ensure_luajit(lay, which=lambda n: None, run=run, environ={}) == "ready"
    assert len(runs) == 1


def test_ensure_luajit_without_compiler_reports_untrusted_exe(tmp_path):
    lay = _lay(tmp_path)
    (lay["luajit_source"] / "src").mkdir(parents=True)
    lay["luajit_exe"].write_bytes(b"planted")
    assert tc_pin.ensure_luajit(lay, which=lambda n: None, run=None,
                                environ={}) == "source-only"


def _component(tmp_path, record=True):
    env = {"AL_SIDECAR_ROOT": str(tmp_path)}
    comp = bridge.component_paths(environ=env)
    comp["luajit"].parent.mkdir(parents=True)
    comp["luajit"].write_bytes(b"lj")
    if record:
        exepin.record(comp["luajit"])
    comp["pob_src"].mkdir(parents=True)
    (comp["pob_src"] / "HeadlessWrapper.lua").write_text("", encoding="ascii")
    return env, comp


def test_bridge_status_requires_a_recorded_hash(tmp_path):
    env, comp = _component(tmp_path, record=False)
    st = bridge.status(environ=env)
    assert st["available"] is False and "luajit" in st["missing"]


def test_bridge_checks_hash_before_every_exec(tmp_path, monkeypatch):
    env, comp = _component(tmp_path)
    b = bridge.Bridge.from_component(environ=env)
    assert b.exe_check == comp["luajit"]
    comp["luajit"].write_bytes(b"swapped after start-up")
    spawned = []
    monkeypatch.setattr(bridge.subprocess, "Popen",
                        lambda *a, **k: spawned.append(a) or pytest.fail("spawned"))
    with pytest.raises(bridge.BridgeUnavailable, match="hash"):
        b._start()
    assert spawned == []
