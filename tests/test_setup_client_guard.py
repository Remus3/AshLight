"""LOOP-ELECTRON-POLICY (F-130, decision 0070): the Electron upgrade policy
is written down, and scripts/setup.ps1 refuses the npm step while
AshLight's own client is live.

- setup.ps1 calls Test-AlClientLive after the up-to-date fast path and
  before the override clearing, `npm ci` and the pin's unpack; a live
  client ends setup with one line and exit 3, nothing changed.
- The test reads only AshLight's own process registry (overlay.pid through
  server.al.procs.overlay_main_pid) and this checkout's own electron.exe
  (opened with no sharing); never the game, never a system-wide process
  scan by name.
- Decision 0070 states the four policy rules (line, patch / minor wait and
  advisory fast path, major window, end of life).
The PowerShell runs are Windows PowerShell 5.1 with the guard function cut
out of the script by the parser: setup.ps1 itself never runs.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SETUP = ROOT / "scripts" / "setup.ps1"
DECISION = ROOT / "docs" / "decisions" / "0070-electron-upgrade-policy.md"
PS51 = shutil.which("powershell.exe") if sys.platform == "win32" else None


def _text(path):
    return path.read_bytes().decode("ascii")


def _ps_str(value):
    return "'" + str(value).replace("'", "''") + "'"


def _guard_body():
    text = _text(SETUP)
    m = re.search(r"^function Test-AlClientLive\b.*?^}\n", text, re.M | re.S)
    assert m, "Test-AlClientLive is missing from setup.ps1"
    return m.group(0)


def _run_guard(runtime, exe, python=None, repo=None):
    """Define Test-AlClientLive from setup.ps1 (parser cut, nothing else of
    the script runs) and print its answer between markers."""
    prog = (
        "$ErrorActionPreference = 'Stop'\n"
        "Set-StrictMode -Version 2\n"
        "$__ast = [System.Management.Automation.Language.Parser]::ParseFile("
        + _ps_str(SETUP) + ", [ref]$null, [ref]$null)\n"
        "$__fns = @($__ast.FindAll({ param($n) $n -is "
        "[System.Management.Automation.Language.FunctionDefinitionAst] -and "
        "$n.Name -eq 'Test-AlClientLive' }, $true))\n"
        "if ($__fns.Count -ne 1) { throw 'function missing' }\n"
        ". ([scriptblock]::Create($__fns[0].Extent.Text))\n"
        "$r = Test-AlClientLive " + _ps_str(python or sys.executable) + " "
        + _ps_str(repo or ROOT) + " " + _ps_str(runtime) + " " + _ps_str(exe) + "\n"
        "Write-Output ('<<' + $r + '>>')\n")
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                        "-Command", prog], capture_output=True, text=True, timeout=90)
    assert r.returncode == 0, r.stdout + r.stderr
    m = re.search(r"<<(.*?)>>", r.stdout)
    assert m, r.stdout + r.stderr
    return m.group(1)


# ------------------------------------------------------------ static order

def test_setup_checks_the_client_before_npm():
    text = _text(SETUP)
    call = text.index("$clientLive = Test-AlClientLive ")
    fast = text.index("if ($upToDate -and -not $Force)")
    clear = text.rindex("\nClear-AlElectronOverrides\n")
    npm = text.index("Invoke-AlLogged $npmLog 'npm.cmd'")
    unpack = text.index("Invoke-AlElectronPin 'setup'")
    assert fast < call < clear < npm < unpack
    # the refusal: one log line and exit 3, before anything is changed
    tail = text[call:clear]
    assert "Write-AlLog" in tail and "exit 3" in tail
    assert "Set-Content" not in tail and "Remove-Item" not in tail
    # npm runs nowhere before the guard
    assert "npm.cmd" not in text[:call]
    # the guard reads the registry record only: no process scan by name,
    # never the game
    body = _guard_body()
    assert "procs.overlay_main_pid" in body
    for banned in ("Get-Process", "Get-CimInstance", "Get-WmiObject", "Win32_Process",
                   "tasklist", "procs status", "overlay_pids", "list_processes",
                   "PathOfExile", "Path of Exile"):
        assert banned not in body, banned
    assert "[System.IO.FileShare]::None" in body


@pytest.mark.skipif(PS51 is None, reason="Windows PowerShell 5.1 only")
def test_setup_ps1_parses_under_powershell_5_1():
    prog = ("$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile("
            + _ps_str(SETUP) + ", [ref]$null, [ref]$e); "
            "if ($e.Count) { $e | ForEach-Object { Write-Output $_.Message }; exit 1 }")
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-Command", prog],
                       capture_output=True, text=True, timeout=90)
    assert r.returncode == 0, r.stdout + r.stderr
    data = SETUP.read_bytes()
    data.decode("ascii")
    assert b"\r" not in data


# ------------------------------------------------------------ the guard runs

@pytest.mark.skipif(PS51 is None, reason="Windows PowerShell 5.1 only")
def test_guard_idle_registry_and_free_exe_say_not_live(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    exe = tmp_path / "dist" / "electron.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"MZ fake")
    assert _run_guard(runtime, exe) == ""
    # a record naming a process that is not electron.exe (this python) is
    # not ours (decision 0010), so it does not count as a live client
    (runtime / "overlay.pid").write_text('{"pid": %d, "created": 0}\n' % os.getpid(),
                                         encoding="ascii")
    assert _run_guard(runtime, exe) == ""
    # no exe at all (a fresh install) is not live either
    assert _run_guard(runtime, tmp_path / "none" / "electron.exe") == ""


@pytest.mark.skipif(PS51 is None, reason="Windows PowerShell 5.1 only")
def test_guard_exe_in_use_says_live(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    exe = tmp_path / "dist" / "electron.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"MZ fake")
    with open(exe, "rb"):
        reason = _run_guard(runtime, exe)
    assert "client is running" in reason and "electron.exe is in use" in reason
    assert _run_guard(runtime, exe) == ""


@pytest.mark.skipif(PS51 is None, reason="Windows PowerShell 5.1 only")
def test_guard_registry_read_failure_fails_closed(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    exe = tmp_path / "electron.exe"
    exe.write_bytes(b"MZ fake")
    # a repo root without server.al: the registry cannot be read
    empty = tmp_path / "empty"
    empty.mkdir()
    reason = _run_guard(runtime, exe, repo=empty)
    assert reason == "the process registry could not be read"


# ------------------------------------------------------------ the policy

def test_policy_decision_states_the_four_rules():
    text = _text(DECISION)
    assert b"\r" not in DECISION.read_bytes()
    flat = " ".join(text.split())
    # (a) line
    assert "newest stable Electron major" in flat
    # (b) patch / minor: weekly, 3 days old, 24 h on an npm audit advisory
    assert re.search(r"Weekly, to the newest release .* at least 3 days old", flat)
    assert "within 24 h" in flat and "`npm audit`" in flat
    # (c) major: 14 to 42 days after .0.0, one at a time
    assert "between 14 and 42 days after its .0.0" in flat
    assert "one major at a time" in flat
    # (d) never past end of life, note and row from 30 days before
    assert "never runs past its line's end-of-life date" in flat
    assert "30 days before" in flat
    # gates by reference and the setup refusal
    assert "F-037" in flat and "F-044" in flat
    assert "setup.ps1 refuses the npm step while AshLight's own client runs" in flat
    assert "the app itself never checks versions" in flat
    for head in ("## Decision", "## Alternatives", "## Why", "## Reverses if"):
        assert head in text
