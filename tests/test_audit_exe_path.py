"""AUDIT-EXE-PATH (audit finding S5, docs/audit/2026-11-17-audit.md).

Windows CreateProcess also searches the current directory for a bare name,
so every Windows tool runs by its System32 absolute path, a PATH tool by an
absolute PATH entry only, and luajit.exe (built locally, no published hash)
runs only when it matches the SHA-256 recorded when setup built it: checked
by tc_pin before a no-op, by bridge.status and before every bridge exec.
"""

import ast
import os
import re
import shutil
import subprocess
import sys
import time
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


# -- OVL-LAUNCH-ENV (F-110): the launcher and the client start
APP = ROOT / "app"
SPAWN_CALL = re.compile(
    r"\b(?:spawn|spawnSync|execFile|execFileSync|exec|execSync|fork|run)\(\s*"
    r"([\"'`])([^\"'`]*)\1")
# Known open item, not part of this package: setAutostart still names
# powershell.exe bare because app/test/autostart_switch.test.js pins that
# literal. The list may only shrink; a fixed line must be removed from it.
BARE_SPAWN_KNOWN = {
    ("app/client/launcher.js",
     'const child = run("powershell.exe", psArgs(path.join(repo, "scripts", '
     '"autostart.ps1"), [flag]), {'),
}


def _app_js():
    for path in sorted(APP.rglob("*.js")):
        rel = path.relative_to(ROOT).as_posix()
        if "/node_modules/" in rel or rel.startswith("app/test/"):
            continue
        yield rel, path.read_text(encoding="utf-8")


def test_no_bare_spawn_names_in_app():
    """A spawn whose program is a bare name (no folder) is also looked up in
    the child's working directory on Windows: a planted exe there would run."""
    bad, known = [], set()
    for rel, text in _app_js():
        for n, line in enumerate(text.splitlines(), 1):
            for m in SPAWN_CALL.finditer(line):
                name = m.group(2)
                if not name or "/" in name or "\\" in name:
                    continue
                if (rel, line.strip()) in BARE_SPAWN_KNOWN:
                    known.add((rel, line.strip()))
                    continue
                bad.append(f"{rel}:{n}: {name}")
    assert bad == []
    assert known == BARE_SPAWN_KNOWN, "a fixed line must leave BARE_SPAWN_KNOWN"


def test_launcher_runs_powershell_and_python_by_absolute_path():
    text = (APP / "client" / "launcher.js").read_text(encoding="utf-8")
    # TC-CALC-OPTIN-BUTTON (ruling W16-2): the calc setup spawn too
    for fn in ("function startCore", "function stopAll", "function setupCalc"):
        body = text[text.index(fn):]
        body = body[:body.index("\n}\n")]
        assert "run(psExe(env)," in body, fn
    body = text[text.index("function resolveSidecar"):]
    body = body[:body.index("\n}\n")]
    assert "whichAbs(name, env, fsMod)" in body and "run(py," in body
    assert '"WindowsPowerShell", "v1.0", "powershell.exe"' in text


def test_run_ps1_clears_node_switches_for_the_client():
    run = (ROOT / "scripts" / "run.ps1").read_text(encoding="ascii")
    assert "$clientUnset = @('ELECTRON_RUN_AS_NODE', 'NODE_OPTIONS')" in run
    lines = run.splitlines()
    i = next(k for k, ln in enumerate(lines) if "Start-AlDetached -FilePath $electron" in ln)
    call = lines[i] + lines[i + 1]
    assert "-Unset $clientUnset" in call
    # the core and supervisor starts keep their own environment
    for k, ln in enumerate(lines):
        if "Start-AlDetached -FilePath $exe" in ln:
            assert "-Unset" not in ln + lines[k + 1]
    detach = (ROOT / "scripts" / "al_detach.ps1").read_text(encoding="ascii")
    assert "[string[]]$Unset = @()" in detach
    assert "$vars.Remove($have)" in detach
    assert "OrdinalIgnoreCase" in detach


PS51 = shutil.which("powershell.exe") if sys.platform == "win32" else None


@pytest.mark.skipif(PS51 is None, reason="Windows PowerShell 5.1 only")
@pytest.mark.slow
def test_detached_child_does_not_get_unset_variables(tmp_path):
    out = tmp_path / "child.txt"
    child_py = tmp_path / "child.py"
    child_py.write_text(
        "import os, sys\n"
        "with open(sys.argv[1], 'w') as fh:\n"
        "    fh.write('|'.join(os.environ.get(k, '-') for k in\n"
        "             ('ELECTRON_RUN_AS_NODE', 'NODE_OPTIONS', 'AL_KEEP')))\n",
        encoding="ascii")
    detach = ROOT / "scripts" / "al_detach.ps1"
    script = (f". '{detach}'; "
              "$env:ELECTRON_RUN_AS_NODE = '1'; $env:Node_Options = '--inspect'; "
              f"$p = Start-AlDetached -FilePath '{sys.executable}' "
              f"-ArgumentList @('\"{child_py}\"', '\"{out}\"') "
              f"-WorkingDirectory '{tmp_path}' -Environment @{{AL_KEEP='k'}} "
              "-Unset @('ELECTRON_RUN_AS_NODE', 'NODE_OPTIONS'); \"$p\"")
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                        "-Command", script], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    deadline = time.time() + 15
    while not (out.exists() and out.read_text()) and time.time() < deadline:
        time.sleep(0.2)
    assert out.read_text() == "-|-|k"
