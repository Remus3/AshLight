"""The core must outlive whatever started it (zero-interaction goal).

scripts/run.ps1 starts the core through scripts/al_detach.ps1, which creates
the process with WMI Win32_Process.Create: the parent is the WMI provider
host, so the core is outside the caller's process tree and job object and
survives the caller (a tool shell, a sub-agent, a console) being torn down.
"""

import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "scripts" / "run.ps1"
DETACH = ROOT / "scripts" / "al_detach.ps1"
PS51 = shutil.which("powershell.exe") if sys.platform == "win32" else None

needs_ps = pytest.mark.skipif(PS51 is None, reason="Windows PowerShell 5.1 only")


def _ps(script, timeout=60):
    return subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                           "Bypass", "-Command", script],
                          capture_output=True, text=True, timeout=timeout)


def test_run_uses_detached_launcher_for_core():
    text = RUN.read_text(encoding="ascii")
    assert "al_detach.ps1" in text
    assert "Start-AlDetached" in text
    # the core is never started with Start-Process (child of the caller's tree)
    for line in text.splitlines():
        if "server.al" in line:
            assert "Start-Process" not in line, line


def test_detach_helper_uses_wmi_create_with_full_environment():
    text = DETACH.read_text(encoding="ascii")
    assert "Win32_Process" in text and "Create" in text
    assert "Win32_ProcessStartup" in text
    # EnvironmentVariables replaces the whole block, so the helper must carry
    # the caller's environment (PATH, SystemRoot) plus the overrides
    assert "EnvironmentVariables" in text
    assert "GetEnvironmentVariables" in text


@needs_ps
@pytest.mark.parametrize("script", [RUN, DETACH])
def test_scripts_parse_in_powershell_51(script):
    r = _ps("$e=$null; [System.Management.Automation.Language.Parser]::ParseFile("
            f"'{script}', [ref]$null, [ref]$e) | Out-Null; $e.Count")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "0", r.stdout


@needs_ps
@pytest.mark.slow
def test_detached_child_is_outside_caller_tree_and_gets_env(tmp_path):
    out = tmp_path / "child.txt"
    py = sys.executable
    child_py = tmp_path / "child.py"
    child_py.write_text(
        "import os, sys, time\n"
        "with open(sys.argv[1], 'w') as fh:\n"
        "    fh.write(os.environ.get('AL_DETACH_PROBE', '-') + '|'\n"
        "            + ('1' if os.environ.get('SystemRoot') else '0'))\n"
        "time.sleep(30)\n", encoding="ascii")
    script = (f". '{DETACH}'; "
              f"$p = Start-AlDetached -FilePath '{py}' "
              f"-ArgumentList @('\"{child_py}\"', '\"{out}\"') "
              f"-WorkingDirectory '{tmp_path}' -Environment @{{AL_DETACH_PROBE='ok'}}; "
              "\"$p|$PID\"")
    r = _ps(script)
    assert r.returncode == 0, r.stderr
    child, caller = (int(x) for x in r.stdout.strip().splitlines()[-1].split("|"))
    try:
        deadline = time.time() + 15
        while not (out.exists() and out.read_text()) and time.time() < deadline:
            time.sleep(0.2)
        assert out.read_text() == "ok|1"
        q = _ps(f"(Get-CimInstance Win32_Process -Filter 'ProcessId={child}').ParentProcessId")
        parent = int(q.stdout.strip())
        assert parent != caller
        # the caller powershell has exited; the child is still alive
        alive = _ps(f"[bool](Get-Process -Id {child} -ErrorAction SilentlyContinue)")
        assert alive.stdout.strip() == "True"
    finally:
        subprocess.run(["taskkill", "/PID", str(child), "/F"], capture_output=True)
