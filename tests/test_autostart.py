"""CORE-AUTOSTART (decision 0011): opt-in logon autostart, OFF by default.

The scripts/autostart.ps1 tests run in -DryRun / -Status mode with the
runtime dir pointed at tmp and tripwire functions shadowing the cmdlets that
would change the machine (Register-/Unregister-ScheduledTask, registry
writes): a call writes a marker file and fails the test. The logon task
tests of scripts/al_shell.ps1 (REL-AUTOSTART-ENTRY) and the one -Enable /
-Disable round trip run with a scratch effect root (task folder
AshLightShellScratch\\<id>) AND in-memory doubles of Get-, Register- and
Unregister-ScheduledTask. Nothing is ever registered on this machine.
server/al/autostart_entry.py is checked with a Popen double: nothing is
started.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from server.al import autostart_entry

ROOT = Path(__file__).resolve().parents[1]
AUTOSTART = ROOT / "scripts" / "autostart.ps1"
LAUNCHER = ROOT / "server" / "al" / "autostart_entry.py"
SHELL = ROOT / "scripts" / "al_shell.ps1"
RUN = ROOT / "scripts" / "run.ps1"
SETUP = ROOT / "scripts" / "setup.ps1"
PS51 = shutil.which("powershell.exe") if sys.platform == "win32" else None

needs_ps = pytest.mark.skipif(PS51 is None, reason="Windows PowerShell 5.1 only")

TRIPWIRES = ("Register-ScheduledTask", "Unregister-ScheduledTask", "Set-ScheduledTask",
             "New-ItemProperty", "Set-ItemProperty", "Remove-ItemProperty")
TASK = "AshLight Autostart"


def _ps(command, tmp_path, timeout=90, shell_root=None):
    env = dict(os.environ)
    env["AL_RUNTIME_DIR"] = str(tmp_path / "runtime")
    env["AL_SIDECAR_ROOT"] = str(tmp_path / "AL")
    env.pop("AL_SHELL_ROOT", None)
    if shell_root is not None:
        env["AL_SHELL_ROOT"] = str(shell_root)
    return subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                           "Bypass", "-Command", command],
                          capture_output=True, text=True, timeout=timeout, env=env, cwd=ROOT)


def _guarded(call, marker):
    # ScheduledTasks commands are CDXML functions: import the module first so
    # an autoload on first use cannot replace a tripwire of the same name.
    wires = "Import-Module ScheduledTasks -ErrorAction Stop; " + "".join(
        f"function {name} {{ Add-Content -LiteralPath '{marker}' -Value '{name}'; "
        f"throw 'tripwire {name}' }}; " for name in TRIPWIRES)
    # every tripwire is checked to be the command that resolves before the
    # call runs (a throw here stops the whole -Command string)
    check = ("foreach ($n in @(" + ", ".join(f"'{n}'" for n in TRIPWIRES) + ")) { "
             "$c = Get-Command $n -ErrorAction Stop; "
             "if ($c.CommandType -ne 'Function' -or $c.ModuleName -or "
             "$c.ScriptBlock.ToString() -notmatch 'tripwire') "
             "{ throw ('double not in force: ' + $n) } }; ")
    return wires + check + call + "; exit $LASTEXITCODE"


def _json_line(stdout):
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError(f"no JSON in output: {stdout!r}")


def _q(text):
    return "'" + str(text).replace("'", "''") + "'"


@needs_ps
@pytest.mark.slow
def test_enable_dryrun_prints_definition_and_registers_nothing(tmp_path):
    marker = tmp_path / "tripwire.txt"
    r = _ps(_guarded(f"& '{AUTOSTART}' -Enable -DryRun", marker), tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert not marker.exists(), marker.read_text()
    d = _json_line(r.stdout)
    assert d["dry_run"] is True and d["registered"] is False
    assert d["task_name"] == TASK and d["task_path"] == "\\"
    # current user only, no admin rights, at logon with a short delay
    user = os.environ.get("USERNAME", "")
    assert d["user"].endswith(user) and d["trigger_user"] == d["user"]
    assert d["logon_type"] == "Interactive" and d["run_level"] == "Limited"
    assert d["trigger"] == "AtLogOn" and d["delay"] == "PT30S"
    # hidden: pythonw runs the entry point module from the checkout root;
    # no wscript, no VBScript (REL-AUTOSTART-ENTRY)
    assert d["window"] == "hidden"
    assert Path(d["execute"]).name.lower() == "pythonw.exe"
    assert Path(d["execute"]).is_absolute()
    assert d["arguments"] == "-m server.al.autostart_entry"
    action = (d["execute"] + " " + d["arguments"]).lower()
    assert "wscript" not in action and ".vbs" not in action
    # action paths resolved at run time from the script's own location
    assert Path(d["launcher"]).resolve() == LAUNCHER.resolve()
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


def test_launcher_is_hidden_and_relative(tmp_path, monkeypatch):
    text = LAUNCHER.read_text(encoding="ascii")
    # no machine path in the module: the checkout root comes from paths.py
    assert ":\\" not in text and ":/" not in text
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "run.ps1").write_text("# stub\n", encoding="ascii")
    win = tmp_path / "Win"
    cmd = autostart_entry.launch_command(root, {"SystemRoot": str(win)})
    # SEC-ACL-SETUP: PowerShell by its System32 path from %SystemRoot%,
    # never by a bare name a PATH entry or the current folder could shadow
    assert Path(cmd[0]) == win / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    assert cmd[cmd.index("-WindowStyle") + 1] == "Hidden"
    assert cmd[cmd.index("-File") + 1] == str(root / "scripts" / "run.ps1")
    assert cmd[-2:] == ["-NoBrowser", "-Autostart"]
    assert autostart_entry.launch_command(root, {}) is None  # no guessed drive

    calls = []

    class _Proc:
        pid = 4242

    def fake_popen(argv, **kw):
        calls.append((argv, kw))
        return _Proc()

    monkeypatch.setenv("AL_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("AL_SIDECAR_ROOT", str(tmp_path / "AL"))
    monkeypatch.setenv("SystemRoot", str(win))
    optin = tmp_path / "runtime" / "autostart.json"
    # opt-in missing, then off: nothing started
    assert autostart_entry.start(root, popen=fake_popen) == 0
    optin.parent.mkdir(parents=True)
    optin.write_text('{"enabled": false}\n', encoding="ascii")
    assert autostart_entry.start(root, popen=fake_popen) == 0
    assert calls == []
    # opt-in on: one hidden start that does not wait
    optin.write_text('{"enabled": true}\n', encoding="ascii")
    assert autostart_entry.start(root, popen=fake_popen) == 0
    assert len(calls) == 1
    argv, kw = calls[0]
    assert argv == autostart_entry.launch_command(root, {"SystemRoot": str(win)})
    assert kw["cwd"] == str(root)
    assert kw["stdin"] == kw["stdout"] == kw["stderr"] == subprocess.DEVNULL
    if os.name == "nt":
        assert kw["creationflags"] & subprocess.CREATE_NO_WINDOW
    log = (tmp_path / "AL" / "Logs" / "run.log").read_text(encoding="ascii")
    assert "autostart entry: opt-in off (no-op)" in log
    assert "autostart entry: run.ps1 started (pid 4242)" in log
    # a missing run.ps1 starts nothing and says so
    (root / "scripts" / "run.ps1").unlink()
    assert autostart_entry.start(root, popen=fake_popen) == 1
    assert len(calls) == 1
    # the task action comes from paths.python_cmd: pythonw -m <module>
    act = autostart_entry.task_action(environ={})
    assert act["arguments"] == "-m server.al.autostart_entry"
    assert Path(act["launcher"]).resolve() == LAUNCHER.resolve()
    assert Path(act["working_directory"]).resolve() == ROOT.resolve()


def test_entry_cli_dry_run_starts_nothing(tmp_path):
    env = dict(os.environ)
    env["AL_RUNTIME_DIR"] = str(tmp_path / "runtime")
    env["AL_SIDECAR_ROOT"] = str(tmp_path / "AL")
    r = subprocess.run([sys.executable, "-m", "server.al.autostart_entry", "--dry-run"],
                       capture_output=True, text=True, timeout=60, env=env, cwd=ROOT)
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    assert d["dry_run"] is True and d["optin"] is False and d["would_start"] is False
    r = subprocess.run([sys.executable, "-m", "server.al.autostart_entry", "--bogus"],
                       capture_output=True, text=True, timeout=60, env=env, cwd=ROOT)
    assert r.returncode == 2


# In-memory doubles of the ScheduledTasks commands: a task lives only in the
# $global:AlFakeTasks table; every Register / Unregister call is logged.
# ScheduledTasks is a CDXML module whose commands are FUNCTIONS: an
# autoload on first use would replace a global double of the same name, so
# the module is imported first, every command al_shell.ps1 uses is doubled,
# and the doubles are checked to be in force before anything runs.
_FAKE_NAMES = ("Get-ScheduledTask", "Register-ScheduledTask", "Unregister-ScheduledTask",
               "New-ScheduledTaskAction", "New-ScheduledTaskTrigger",
               "New-ScheduledTaskPrincipal", "New-ScheduledTaskSettingsSet")
_FAKES = (
    "Import-Module ScheduledTasks -ErrorAction Stop; "
    "$global:AlFakeTasks = @{}; $global:AlFakeCalls = @(); "
    "function global:New-ScheduledTaskAction { [CmdletBinding()] "
    "  param([string]$Execute, [string]$Argument, [string]$WorkingDirectory) "
    "  [pscustomobject]@{ AlFake = 1; Execute = $Execute; Arguments = $Argument; "
    "    WorkingDirectory = $WorkingDirectory } }; "
    "function global:New-ScheduledTaskTrigger { [CmdletBinding()] "
    "  param([switch]$AtLogOn, [string]$User) "
    "  [pscustomobject]@{ AlFake = 1; User = $User; Delay = '' } }; "
    "function global:New-ScheduledTaskPrincipal { [CmdletBinding()] "
    "  param([string]$UserId, [string]$LogonType, [string]$RunLevel) "
    "  [pscustomobject]@{ AlFake = 1; UserId = $UserId; RunLevel = $RunLevel } }; "
    "function global:New-ScheduledTaskSettingsSet { [CmdletBinding()] "
    "  param([switch]$AllowStartIfOnBatteries, [switch]$DontStopIfGoingOnBatteries, "
    "        $ExecutionTimeLimit, [string]$MultipleInstances) "
    "  [pscustomobject]@{ AlFake = 1 } }; "
    "function global:Get-ScheduledTask { [CmdletBinding()] "
    "  param([string]$TaskName, [string]$TaskPath) "
    "  $k = $TaskPath + $TaskName; "
    "  if ($global:AlFakeTasks.ContainsKey($k)) { return $global:AlFakeTasks[$k] }; "
    "  throw 'no such task' }; "
    "function global:Register-ScheduledTask { [CmdletBinding()] "
    "  param([string]$TaskName, [string]$TaskPath, $Action, $Trigger, $Principal, "
    "        $Settings, [string]$Description, [switch]$Force) "
    "  $global:AlFakeCalls += ('register ' + $TaskPath + $TaskName); "
    "  $global:AlFakeTasks[$TaskPath + $TaskName] = [pscustomobject]@{ TaskName = $TaskName; "
    "    TaskPath = $TaskPath; Description = $Description; State = 'Ready'; "
    "    Actions = @([pscustomobject]@{ Execute = $Action.Execute; "
    "      Arguments = $Action.Arguments; WorkingDirectory = $Action.WorkingDirectory }) } }; "
    "function global:Unregister-ScheduledTask { [CmdletBinding(SupportsShouldProcess = $true)] "
    "  param([string]$TaskName, [string]$TaskPath) "
    "  $global:AlFakeCalls += ('unregister ' + $TaskPath + $TaskName); "
    "  $global:AlFakeTasks.Remove($TaskPath + $TaskName) }; "
    "foreach ($n in @(" + ", ".join(f"'{n}'" for n in _FAKE_NAMES) + ")) { "
    "  $c = Get-Command $n -ErrorAction Stop; "
    "  if ($c.CommandType -ne 'Function' -or $c.ModuleName -or "
    "      $c.ScriptBlock.ToString() -notmatch 'AlFake') { throw ('double not in force: ' + $n) } }; "
)


def test_every_task_command_is_doubled():
    # The shell tests fake every ScheduledTasks command the scripts call:
    # a new command, a module-qualified call, a re-import of the module or a
    # COM / schtasks route would slip past the doubles, so each is refused.
    used = set()
    for script in (SHELL, AUTOSTART):
        text = script.read_text(encoding="ascii")
        used |= set(re.findall(r"\b[A-Za-z]+-ScheduledTask[A-Za-z]*\b", text))
        low = text.lower()
        assert "scheduledtasks\\" not in low, script.name
        assert "schedule.service" not in low and "schtasks" not in low, script.name
        assert not re.search(r"import-module\s+[^\n]*scheduledtasks", low), script.name
    assert used and used <= set(_FAKE_NAMES), sorted(used - set(_FAKE_NAMES))
    defined = re.findall(r"function global:([A-Za-z-]+)", _FAKES)
    assert sorted(defined) == sorted(_FAKE_NAMES)
    assert len(_FAKE_NAMES) == 7


def _real_scratch_folder():
    """Read only, in a fresh process with no doubles: the real Task
    Scheduler's \\AshLightShellScratch folder ('' when absent). Only the
    folder-not-found HRESULT (0x80070002) counts as absent; any other
    outcome is returned as 'unreadable: ...' so a failed read-back never
    passes as 'absent'."""
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-Command",
                        "$s = New-Object -ComObject Schedule.Service; $s.Connect(); "
                        "try { 'FOLDER=' + $s.GetFolder('\\AshLightShellScratch').Path } "
                        "catch { $e = $_.Exception; "
                        "while ($e.InnerException) { $e = $e.InnerException }; "
                        "if ($e.HResult -eq -2147024894) { 'ABSENT' } "
                        "else { 'ERROR=' + $e.HResult } }"],
                       capture_output=True, text=True, timeout=60)
    out = r.stdout.strip()
    if r.returncode == 0 and out == "ABSENT":
        return ""
    if r.returncode == 0 and out.startswith("FOLDER="):
        return out[len("FOLDER="):] or "\\"
    return "unreadable: rc=%s %s %s" % (r.returncode, out, r.stderr.strip()[:200])


def _require_no_real_scratch_folder():
    """Before a test that runs the logon task code: the real scheduler must
    read back with no scratch folder. If it cannot be read, skip: the test
    must never run when its after-check could not prove anything."""
    state = _real_scratch_folder()
    if state.startswith("unreadable"):
        pytest.skip("real Task Scheduler not readable for the read-back: " + state)
    assert state == "", state


def _skip_if_doubles_missing(text):
    # The doubles check (or the module import) failed before anything ran:
    # nothing was called, but the test cannot prove its point, so it skips.
    flat = "".join(text.split())
    if "doublenotinforce" in flat or "ScheduledTasks'wasnotloaded" in flat:
        pytest.skip("ScheduledTasks doubles not in force; nothing was run")


def _plant(execute, workdir):
    """PowerShell that plants a task of the test's name in the effect
    root's task folder ($p)."""
    return (f"$global:AlFakeTasks[$p + '{TASK}'] = [pscustomobject]@{{ TaskName = '{TASK}'; "
            f"TaskPath = $p; Description = 'old'; State = 'Ready'; "
            f"Actions = @([pscustomobject]@{{ Execute = {_q(execute)}; Arguments = '//B x'; "
            f"WorkingDirectory = {_q(workdir)} }}) }}; ")


def _shell(script, tmp_path, shell_root):
    full = ("$ErrorActionPreference = 'Stop'; Set-StrictMode -Version 2; "
            + _FAKES + f". {_q(SHELL)}; $p = (Get-AlShellPlaces).TaskPath; " + script)
    r = _ps(full, tmp_path, shell_root=shell_root)
    if r.returncode != 0:
        _skip_if_doubles_missing(r.stdout + r.stderr)
    assert r.returncode == 0, r.stdout + r.stderr
    return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]


@needs_ps
@pytest.mark.slow
def test_task_pointing_elsewhere_is_left_alone(tmp_path):
    scratch = tmp_path / "shell"
    owner = tmp_path / "repo"
    other = tmp_path / "other-copy"
    for d in (scratch, owner, other):
        d.mkdir()
    _require_no_real_scratch_folder()
    exe = tmp_path / "py" / "pythonw.exe"
    reg = (f"Register-AlLogonTask -TaskName '{TASK}' -Execute {_q(exe)} "
           f"-Arguments '-m server.al.autostart_entry' -WorkDir {_q(owner)} -UserId 'U' "
           f"-Description 'd' -OwnerRoot {_q(owner)}")
    unreg = f"Unregister-AlLogonTask -TaskName '{TASK}' -OwnerRoot {_q(owner)}"
    # the effect root moves the task folder off the real one
    out = _shell("'P=' + $p", tmp_path, scratch)
    assert out[0].startswith("P=\\AshLightShellScratch\\") and out[0].endswith("\\")
    # a task of another folder is left alone by register and by unregister
    out = _shell(_plant(exe, other)
                 + f"'R=' + ({reg}); 'U=' + ({unreg}); "
                 "'C=' + $global:AlFakeCalls.Count; "
                 f"'W=' + $global:AlFakeTasks[$p + '{TASK}'].Actions[0].WorkingDirectory",
                 tmp_path, scratch)
    assert out == ["R=elsewhere", "U=elsewhere", "C=0", f"W={other}"]
    # ours: an old wscript task of this folder is replaced and read back,
    # a re-run is 'current', then removed (read back) and absent
    out = _shell(_plant("wscript.exe", owner)
                 + f"'R1=' + ({reg}); 'R2=' + ({reg}); "
                 f"'E=' + $global:AlFakeTasks[$p + '{TASK}'].Actions[0].Execute; "
                 f"'U1=' + ({unreg}); 'U2=' + ({unreg}); "
                 "'C=' + ($global:AlFakeCalls -join ',')",
                 tmp_path, scratch)
    assert out[:5] == ["R1=written", "R2=current", f"E={exe}", "U1=removed", "U2=absent"]
    calls = out[5][2:].split(",")
    assert [c.split(" ")[0] for c in calls] == ["register", "unregister"]
    assert all(c.split(" ", 1)[1].startswith("\\AshLightShellScratch\\") for c in calls)
    # a working directory outside the owner root is refused before any write
    bad = reg.replace(f"-WorkDir {_q(owner)}", f"-WorkDir {_q(other)}")
    r = _ps("$ErrorActionPreference = 'Stop'; " + _FAKES + f". {_q(SHELL)}; " + bad,
            tmp_path, shell_root=scratch)
    assert r.returncode != 0
    assert "notundertheownerroot" in "".join((r.stdout + r.stderr).split())  # console wraps
    # the real Task Scheduler was never written
    assert _real_scratch_folder() == ""


@needs_ps
@pytest.mark.slow
def test_enable_and_disable_go_through_the_helper(tmp_path):
    # autostart.ps1 -Enable / -Disable for real, but with the scratch effect
    # root and the cmdlet doubles; the opt-in lands in the tmp runtime dir.
    scratch = tmp_path / "shell"
    scratch.mkdir()
    _require_no_real_scratch_folder()
    call = (f"& {_q(AUTOSTART)} -Enable; 'RC=' + $LASTEXITCODE; "
            f"& {_q(AUTOSTART)} -Enable; 'RC=' + $LASTEXITCODE; "
            f"& {_q(AUTOSTART)} -Status; "
            f"& {_q(AUTOSTART)} -Disable; 'RC=' + $LASTEXITCODE; "
            "'C=' + ($global:AlFakeCalls -join ',')")
    r = _ps(_FAKES + call, tmp_path, shell_root=scratch)
    if r.returncode != 0:
        _skip_if_doubles_missing(r.stdout + r.stderr)
    assert r.returncode == 0, r.stdout + r.stderr
    out = r.stdout
    assert "registered (at logon" in out and "already registered (no-op)" in out
    assert f"task '{TASK}' removed" in out
    assert out.count("RC=0") == 3
    status = _json_line(out)
    assert status["optin"] is True and status["task_registered"] is True
    assert status["task_ours"] is True
    calls = [ln for ln in out.splitlines() if ln.startswith("C=")][0][2:].split(",")
    assert [c.split(" ")[0] for c in calls] == ["register", "unregister"]
    assert all("\\AshLightShellScratch\\" in c for c in calls)
    rec = json.loads((tmp_path / "runtime" / "autostart.json").read_text(encoding="ascii"))
    assert rec["enabled"] is False
    # the real Task Scheduler was never written
    assert _real_scratch_folder() == ""


def test_no_vbscript_left():
    # REL-AUTOSTART-ENTRY: Windows is retiring VBScript. No .vbs under
    # scripts/ and no wscript in scripts/; the one allowed form is the
    # WScript.Shell COM ProgID al_shell.ps1 uses for .lnk files (the Windows
    # Script Host object model, not the VBScript engine).
    scripts = ROOT / "scripts"
    assert not list(scripts.rglob("*.vbs"))
    hits = []
    for f in sorted(scripts.rglob("*")):
        if not f.is_file():
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            if "wscript" in line.lower().replace("wscript.shell", ""):
                hits.append(f"{f.name}:{n}: {line.strip()}")
    assert not hits, hits


def test_optin_lives_in_gitignored_runtime():
    text = AUTOSTART.read_text(encoding="ascii")
    assert "server.al.paths" in text and "autostart.json" in text
    ignore = (ROOT / ".gitignore").read_text(encoding="ascii").splitlines()
    assert "ops/runtime/" in ignore


@needs_ps
@pytest.mark.parametrize("script", [AUTOSTART, RUN, SETUP, SHELL])
def test_scripts_parse_in_powershell_51(script, tmp_path):
    r = _ps("$e=$null; [System.Management.Automation.Language.Parser]::ParseFile("
            f"'{script}', [ref]$null, [ref]$e) | Out-Null; $e.Count", tmp_path)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "0", r.stdout
