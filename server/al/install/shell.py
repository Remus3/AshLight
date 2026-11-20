"""Shell entries of an install, rewritten at every version switch
(REL-INSTALL-SHELL, finding F-050, DEP-09; docs/plan/05-deployment.md
"Installed-mode layout" and "How an update swaps versions" step 4).

rewrite(home, version) makes every per-user entry point at the active
version of the marker and reads each back:
- <home>/uninstall.ps1: copied from the active version's
  scripts/uninstall.ps1 (byte compare; a no-op when equal), read back;
- the two "AshLight" shortcuts (Start Menu, Desktop): the pinned
  Electron of the marker with the active version's app folder;
- the per-user uninstall entry (InstallLocation = the home);
- the opt-in logon task "AshLight Autostart" (decision 0011), only when
  it exists and its action points into this home: its action moves to
  the active version's boot.py; its user, delay and description stay.
An entry that points elsewhere (a checkout's, another install's) is left
alone and reported as 'elsewhere'. A missing task stays missing: the
opt-in is the player's own act.

This module holds no registry or COM code of its own. Every shell effect
goes through ONE injected runner, runner(request) -> results, whose
request carries the effect root (al_shell.ps1 -EffectRoot: a scratch
Start Menu, Desktop, uninstall key and task folder). The default,
PowerShellRunner, dot-sources scripts/al_shell.ps1 shipped in the active
version's payload and runs it under Windows PowerShell 5.1 by its
System32 path. Read-back: al_shell reads every write back and throws on
a mismatch; rewrite then runs the same request a second time and every
entry that is ours must answer 'current' (nothing left to change).

Per-user locations only; no admin rights. No game folder is read or
written. Standard library only.
"""

import base64
import json
import os
import stat
import subprocess

from .. import autostart_entry, jsonfile, paths
from . import home as homemod

TASK_NAME = "AshLight Autostart"
CLIENT_ARG = "--client"
OUT_PREFIX = "ALSHELL "
LINK_STATES = ("written", "current", "elsewhere")
ENTRY_STATES = ("written", "current", "elsewhere")
TASK_STATES = ("written", "current", "elsewhere", "absent")
TIMEOUT_S = 90
MAX_UNINSTALL_BYTES = 1024 * 1024


class ShellError(Exception):
    """A shell entry could not be rewritten or did not read back."""


# --- what the entries should be ---------------------------------------------

def plan(home, version=None, effect_root=None):
    """The runner request for the active version (no shell access). The
    marker must be valid; `version`, when given, must be its active one."""
    lay = homemod.layout(home)
    marker = homemod.read_marker(lay["home"])
    if marker is None:
        raise ShellError("no valid marker")
    active = marker["version"]
    if version is not None and version != active:
        raise ShellError(f"{version} is not the active version ({active})")
    payload = lay["app"] / active
    if not homemod._is_plain_dir(payload):
        raise ShellError(f"no version folder for {active}")
    al_shell = payload / "scripts" / "al_shell.ps1"
    if not al_shell.is_file():
        raise ShellError("the payload has no scripts/al_shell.ps1")
    if effect_root is not None and not os.path.isabs(str(effect_root)):
        raise ShellError("the effect root must be an absolute path")
    app_dir = payload / "app"
    icon = app_dir / "assets" / "icon.ico"
    runtime = lay["runtime"]
    electron = runtime / marker["electron"] / paths.ELECTRON_EXE
    pythonw = runtime / marker["python"] / "pythonw.exe"
    return {
        "al_shell": str(al_shell),
        "effect_root": str(effect_root) if effect_root is not None else "",
        "owner_root": str(lay["home"]),
        "version": active,
        "shortcut": {
            "target": str(electron),
            "arguments": '"' + str(app_dir) + '" ' + CLIENT_ARG,
            "workdir": str(app_dir),
            "icon": str(icon),
        },
        "uninstall": {
            "install_location": str(lay["home"]),
            "version": active,
            "icon": str(icon),
        },
        "task": {
            "name": TASK_NAME,
            "execute": str(pythonw),
            "arguments": subprocess.list2cmdline(
                [str(payload / paths.BOOT_NAME), autostart_entry.MODULE]),
            "workdir": str(payload),
        },
    }


# --- uninstall.ps1 at the home root ------------------------------------------

def _regular_or_absent(path):
    """True when path is absent or a regular file (never a link or folder)."""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return True
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        return False
    attrs = getattr(st, "st_file_attributes", 0)
    return not attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def copy_uninstall(home, version):
    """Copy <home>/app/<version>/scripts/uninstall.ps1 to <home>/uninstall.ps1
    and read it back. Returns "written" or "current" (already equal)."""
    lay = homemod.layout(home)
    src = lay["app"] / version / "scripts" / "uninstall.ps1"
    dst = lay["uninstall"]
    if not _regular_or_absent(src) or not src.is_file():
        raise ShellError("the payload has no scripts/uninstall.ps1")
    if not _regular_or_absent(dst):
        raise ShellError("uninstall.ps1 at the home root is not a plain file")
    data = src.read_bytes()
    if len(data) > MAX_UNINSTALL_BYTES:
        raise ShellError("the payload's uninstall.ps1 is too large")
    try:
        if dst.is_file() and dst.read_bytes() == data:
            return "current"
    except OSError:
        pass
    jsonfile.write_bytes(dst, data)
    try:
        back = dst.read_bytes()
    except OSError as exc:
        raise ShellError(f"uninstall.ps1 read-back failed: {exc.__class__.__name__}") from None
    if back != data:
        raise ShellError("uninstall.ps1 read-back differs from the payload")
    return "written"


# --- the default runner: scripts/al_shell.ps1 under PowerShell 5.1 ----------

_PS_QUOTES = "'\u2018\u2019\u201a\u201b"


def ps_quote(text):
    """A PowerShell single-quoted literal (every quote character doubled)."""
    text = str(text)
    for q in _PS_QUOTES:
        text = text.replace(q, q + q)
    return "'" + text + "'"


def build_script(request):
    """The PowerShell text of one rewrite: dot-source the payload's
    al_shell.ps1, call its functions with -EffectRoot on every call, print
    one ASCII line 'ALSHELL <json>'. Only al_shell functions touch the
    shell."""
    q = ps_quote
    link = request["shortcut"]
    entry = request["uninstall"]
    task = request["task"]
    lines = [
        "$ErrorActionPreference = 'Stop'",
        "Set-StrictMode -Version 2",
        ". " + q(request["al_shell"]),
        "$er = " + q(request["effect_root"]),
        "$owner = " + q(request["owner_root"]),
        "$out = [ordered]@{}",
        "$links = @(Install-AlShortcuts -Target " + q(link["target"])
        + " -Arguments " + q(link["arguments"]) + " -WorkDir " + q(link["workdir"])
        + " -Icon " + q(link["icon"]) + " -OwnerRoot $owner -EffectRoot $er)",
        "$out['shortcuts'] = @($links | ForEach-Object { [string]$_.Status })",
        "$out['uninstall_entry'] = [string](Set-AlUninstallEntry -InstallLocation "
        + q(entry["install_location"]) + " -Version " + q(entry["version"])
        + " -Icon " + q(entry["icon"]) + " -EffectRoot $er)",
        "$task = Get-AlLogonTask -TaskName " + q(task["name"]) + " -EffectRoot $er",
        "if ($null -eq $task) {",
        "    $out['logon_task'] = 'absent'",
        "} elseif (-not (Test-AlTaskOurs -Task $task -OwnerRoot $owner)) {",
        "    $out['logon_task'] = 'elsewhere'",
        "} else {",
        "    $user = ''",
        "    $pp = $task.PSObject.Properties['Principal']",
        "    if ($null -ne $pp -and $null -ne $pp.Value) {"
        " $user = Get-AlTaskField -Object $pp.Value -Name 'UserId' }",
        "    if (-not $user) { $user = [string]$env:USERNAME }",
        "    $delay = 'PT30S'",
        "    $tp = $task.PSObject.Properties['Triggers']",
        "    if ($null -ne $tp -and $null -ne $tp.Value) {",
        "        $trs = @($tp.Value)",
        "        if ($trs.Count -gt 0) {",
        "            $d = Get-AlTaskField -Object $trs[0] -Name 'Delay'",
        "            if ($d) { $delay = $d }",
        "        }",
        "    }",
        "    $desc = Get-AlTaskField -Object $task -Name 'Description'",
        "    $out['logon_task'] = [string](Register-AlLogonTask -TaskName " + q(task["name"])
        + " -Execute " + q(task["execute"]) + " -Arguments " + q(task["arguments"])
        + " -WorkDir " + q(task["workdir"]) + " -UserId $user -Delay $delay"
        + " -Description $desc -OwnerRoot $owner -EffectRoot $er)",
        "}",
        "$json = $out | ConvertTo-Json -Compress -Depth 4",
        "$json = [regex]::Replace($json, '[^\\x00-\\x7F]',"
        " { param($m) '\\u{0:x4}' -f [int][char]$m.Value })",
        "Write-Output (" + q(OUT_PREFIX) + " + $json)",
    ]
    return "\n".join(lines) + "\n"


def parse_output(stdout):
    """The results dict of the last 'ALSHELL <json>' line; ShellError when
    there is none or it is not a JSON object."""
    found = None
    for line in (stdout or "").splitlines():
        if line.startswith(OUT_PREFIX):
            found = line[len(OUT_PREFIX):]
    if found is None:
        raise ShellError("al_shell printed no result")
    try:
        doc = json.loads(found)
    except ValueError:
        raise ShellError("al_shell printed an unreadable result") from None
    if not isinstance(doc, dict):
        raise ShellError("al_shell printed an unreadable result")
    return doc


class PowerShellRunner:
    """runner(request) -> results, through Windows PowerShell 5.1 (its
    System32 path from %SystemRoot%, never a bare name). `run` is
    subprocess.run; tests replace it."""

    def __init__(self, exe=None, run=None, timeout=TIMEOUT_S, environ=None):
        self.exe = exe
        self.run = run or subprocess.run
        self.timeout = timeout
        self.environ = environ

    def command(self, script):
        exe = self.exe or autostart_entry.powershell_exe(self.environ)
        if exe is None:
            raise ShellError("SystemRoot is not set; Windows PowerShell not found")
        encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        return [str(exe), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-EncodedCommand", encoded]

    def __call__(self, request):
        argv = self.command(build_script(request))
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            res = self.run(argv, capture_output=True, text=True, timeout=self.timeout,
                           stdin=subprocess.DEVNULL, creationflags=flags)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ShellError(f"al_shell did not run: {exc.__class__.__name__}") from None
        if res.returncode != 0:
            tail = [ln.strip() for ln in (res.stderr or "").splitlines() if ln.strip()]
            raise ShellError("al_shell failed: " + (tail[0][:300] if tail else
                                                    f"exit {res.returncode}"))
        return parse_output(res.stdout)


# --- the rewrite ---------------------------------------------------------------

def _check(results):
    """The runner results, validated: {'shortcuts': [..], 'uninstall_entry',
    'logon_task'}."""
    if not isinstance(results, dict):
        raise ShellError("the runner returned no results")
    links = results.get("shortcuts")
    if isinstance(links, str):
        links = [links]
    if not isinstance(links, list) or not links or any(s not in LINK_STATES for s in links):
        raise ShellError(f"unexpected shortcut results: {links!r}")
    entry = results.get("uninstall_entry")
    if entry not in ENTRY_STATES:
        raise ShellError(f"unexpected uninstall entry result: {entry!r}")
    task = results.get("logon_task")
    if task not in TASK_STATES:
        raise ShellError(f"unexpected logon task result: {task!r}")
    return {"shortcuts": list(links), "uninstall_entry": entry, "logon_task": task}


def _read_back(first, second):
    """Problems of the second pass: an entry that is ours must now be
    'current', one left alone must still be 'elsewhere', a task that was
    absent must still be absent."""
    out = []
    if len(first["shortcuts"]) != len(second["shortcuts"]):
        out.append("shortcut count changed")
    for i, (a, b) in enumerate(zip(first["shortcuts"], second["shortcuts"])):
        want = "elsewhere" if a == "elsewhere" else "current"
        if b != want:
            out.append(f"shortcut {i + 1} reads back {b}")
    for key in ("uninstall_entry", "logon_task"):
        a, b = first[key], second[key]
        want = a if a in ("elsewhere", "absent") else "current"
        if b != want:
            out.append(f"{key} reads back {b}")
    return out


def rewrite(home, version=None, runner=None, effect_root=None):
    """Point uninstall.ps1, the shortcuts, the uninstall entry and the
    opt-in logon task (when it exists and is ours) at the active version,
    and read each back. Returns {'version', 'uninstall_script',
    'shortcuts', 'uninstall_entry', 'logon_task', 'read_back': True};
    raises ShellError on any failure."""
    request = plan(home, version, effect_root)
    runner = runner or PowerShellRunner()
    copied = copy_uninstall(home, request["version"])
    first = _check(runner(request))
    second = _check(runner(request))
    problems = _read_back(first, second)
    if problems:
        raise ShellError("read-back failed: " + "; ".join(problems))
    out = {"version": request["version"], "uninstall_script": copied}
    out.update(first)
    out["read_back"] = True
    return out
