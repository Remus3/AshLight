"""CORE-AUTOSTART (decision 0011): opt-in logon autostart, OFF by default.

Every test runs scripts/autostart.ps1 in -DryRun / -Status mode only, with
the runtime dir pointed at tmp, and with tripwire functions shadowing the
cmdlets that would change the machine (Register-/Unregister-ScheduledTask,
registry writes): a call writes a marker file and fails the test. Nothing
is ever registered on this machine.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AUTOSTART = ROOT / "scripts" / "autostart.ps1"
LAUNCHER = ROOT / "scripts" / "autostart_launch.vbs"
RUN = ROOT / "scripts" / "run.ps1"
PS51 = shutil.which("powershell.exe") if sys.platform == "win32" else None

needs_ps = pytest.mark.skipif(PS51 is None, reason="Windows PowerShell 5.1 only")

TRIPWIRES = ("Register-ScheduledTask", "Unregister-ScheduledTask", "Set-ScheduledTask",
             "New-ItemProperty", "Set-ItemProperty", "Remove-ItemProperty")


def _ps(command, tmp_path, timeout=90):
    env = dict(os.environ)
    env["AL_RUNTIME_DIR"] = str(tmp_path / "runtime")
    env["AL_SIDECAR_ROOT"] = str(tmp_path / "AL")
    return subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                           "Bypass", "-Command", command],
                          capture_output=True, text=True, timeout=timeout, env=env, cwd=ROOT)


def _guarded(call, marker):
    wires = "".join(
        f"function {name} {{ Add-Content -LiteralPath '{marker}' -Value '{name}'; "
        f"throw 'tripwire {name}' }}; " for name in TRIPWIRES)
    return wires + call + "; exit $LASTEXITCODE"


def _json_line(stdout):
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError(f"no JSON in output: {stdout!r}")


@needs_ps
@pytest.mark.slow
def test_enable_dryrun_prints_definition_and_registers_nothing(tmp_path):
    marker = tmp_path / "tripwire.txt"
    r = _ps(_guarded(f"& '{AUTOSTART}' -Enable -DryRun", marker), tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert not marker.exists(), marker.read_text()
    d = _json_line(r.stdout)
    assert d["dry_run"] is True and d["registered"] is False
    assert d["task_name"] == "AshLight Autostart" and d["task_path"] == "\\"
    # current user only, no admin rights, at logon with a short delay
    user = os.environ.get("USERNAME", "")
    assert d["user"].endswith(user) and d["trigger_user"] == d["user"]
    assert d["logon_type"] == "Interactive" and d["run_level"] == "Limited"
    assert d["trigger"] == "AtLogOn" and d["delay"] == "PT30S"
    # hidden: wscript runs the vbs launcher, which starts run.ps1 with style 0
    assert d["window"] == "hidden"
    assert Path(d["execute"]).name.lower() == "wscript.exe"
    assert d["arguments"].startswith("//B //NoLogo ")
    # action path resolved at run time from the script's own location
    assert Path(d["launcher"]).resolve() == LAUNCHER.resolve()
    assert str(LAUNCHER.resolve()).lower() in d["arguments"].lower()
    assert Path(d["working_directory"]).resolve() == ROOT.resolve()
    assert d["run_ps1_args"] == ["-NoBrowser", "-Autostart"]
    # opt-in not recorded by a dry run
    assert not (tmp_path / "runtime" / "autostart.json").exists()
    assert Path(d["optin_file"]).resolve() == (tmp_path / "runtime" / "autostart.json").resolve()


@needs_ps
@pytest.mark.slow
def test_disable_dryrun_and_status_change_nothing(tmp_path):
    marker = tmp_path / "tripwire.txt"
    r = _ps(_guarded(f"& '{AUTOSTART}' -Disable -DryRun", marker), tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    d = _json_line(r.stdout)
    assert d["dry_run"] is True and d["registered"] is False
    r = _ps(_guarded(f"& '{AUTOSTART}' -Status", marker), tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    s = _json_line(r.stdout)
    assert s["optin"] is False  # OFF by default
    assert not marker.exists()
    assert not (tmp_path / "runtime" / "autostart.json").exists()


@needs_ps
def test_usage_requires_exactly_one_action(tmp_path):
    r = _ps(f"& '{AUTOSTART}' -DryRun; exit $LASTEXITCODE", tmp_path)
    assert r.returncode == 2, r.stdout + r.stderr


@needs_ps
@pytest.mark.slow
def test_run_autostart_without_optin_is_a_noop(tmp_path):
    # Opt-in off: run.ps1 -Autostart returns before it launches anything.
    r = _ps(f"& '{RUN}' -Autostart; exit $LASTEXITCODE", tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    log = (tmp_path / "AL" / "Logs" / "run.log").read_text(encoding="ascii")
    assert "logon autostart, opt-in off (no-op)" in log
    assert "core launched" not in log
    assert not (tmp_path / "runtime" / "core.alive").exists()


def test_launcher_is_hidden_and_relative():
    text = LAUNCHER.read_text(encoding="ascii")
    assert "WScript.ScriptFullName" in text
    assert "run.ps1" in text and "-NoBrowser -Autostart" in text
    assert "-WindowStyle Hidden" in text
    assert "sh.Run cmd, 0, False" in text


def test_optin_lives_in_gitignored_runtime():
    text = AUTOSTART.read_text(encoding="ascii")
    assert "server.al.paths" in text and "autostart.json" in text
    ignore = (ROOT / ".gitignore").read_text(encoding="ascii").splitlines()
    assert "ops/runtime/" in ignore


@needs_ps
@pytest.mark.parametrize("script", [AUTOSTART, RUN])
def test_scripts_parse_in_powershell_51(script, tmp_path):
    r = _ps("$e=$null; [System.Management.Automation.Language.Parser]::ParseFile("
            f"'{script}', [ref]$null, [ref]$e) | Out-Null; $e.Count", tmp_path)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "0", r.stdout
