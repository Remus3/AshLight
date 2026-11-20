"""Logon autostart entry point (decision 0011, REL-AUTOSTART-ENTRY).

The opt-in logon task "AshLight Autostart" runs

    pythonw.exe -m server.al.autostart_entry

with the checkout root as its working directory (scripts/autostart.ps1
registers it through scripts/al_shell.ps1). pythonw has no console, so
nothing flashes at logon. This module checks the recorded opt-in
(<runtime>/autostart.json, written by autostart.ps1) and, only when it is
on, starts scripts/run.ps1 -Autostart with CREATE_NO_WINDOW and does not
wait. run.ps1 -Autostart checks the opt-in again, so a task left behind
after -Disable never starts anything; it then starts the desktop client
tray-only (--client --tray: tray and overlay, no companion window, the
overlay gated by the log) when the client is installed, else the core
alone, and never opens the browser (REL-AUTOSTART-TRAY, decision 0011
amendment 2026-11-18).

Windows PowerShell is started by its System32 path built from %SystemRoot%
at run time (SEC-ACL-SETUP, decision 0051), never by a bare name a PATH
entry or the current folder could shadow; nothing here names a machine
path. Never touches the game process (decision 0003 floor).

CLI:
    python -m server.al.autostart_entry               start (logon task)
    python -m server.al.autostart_entry --dry-run     print the plan as JSON, start nothing
    python -m server.al.autostart_entry --task-action print the task action as JSON
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from server.al import paths

MODULE = "server.al.autostart_entry"
OPTIN_NAME = "autostart.json"
RUN_ARGS = ("-Autostart",)
PS_REL = ("System32", "WindowsPowerShell", "v1.0", "powershell.exe")
LOG_NAME = "run.log"


def optin_file():
    """The recorded opt-in, <runtime>/autostart.json (gitignored)."""
    return paths.runtime_dir() / OPTIN_NAME


def read_optin(path=None):
    """True only when the opt-in file holds {"enabled": true}; a missing or
    unreadable file is off (fail closed)."""
    p = optin_file() if path is None else Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and data.get("enabled") is True


def powershell_exe(environ=None):
    """Windows PowerShell 5.1 by its System32 path from %SystemRoot%; None
    when the variable is unset (no guessed drive letter)."""
    env = os.environ if environ is None else environ
    root = ""
    for key in ("SystemRoot", "SYSTEMROOT"):
        root = (env.get(key) or "").strip().strip('"')
        if root:
            break
    if not root or not os.path.isabs(root):
        return None
    return Path(root).joinpath(*PS_REL)


def run_script(root=None):
    """scripts/run.ps1 under the checkout root."""
    base = paths.repo_root() if root is None else Path(root)
    return base / "scripts" / "run.ps1"


def launch_command(root=None, environ=None):
    """The hidden run.ps1 start: [powershell, flags, -File, run.ps1,
    -Autostart]; None when %SystemRoot% is unset. run.ps1 -Autostart picks
    the tray-only client or the core alone."""
    ps = powershell_exe(environ)
    if ps is None:
        return None
    return [str(ps), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-WindowStyle", "Hidden", "-File", str(run_script(root))] + list(RUN_ARGS)


def task_action(environ=None):
    """The scheduled task action: execute (pythonw), arguments, working
    directory and the launcher module file. Built by paths.python_cmd, the
    one Python spawn builder (DEP-06)."""
    cmd = paths.python_cmd(MODULE, windowless=True, environ=environ)
    root = paths.repo_root()
    return {
        "execute": cmd[0],
        "arguments": subprocess.list2cmdline(cmd[1:]),
        "working_directory": str(root),
        "launcher": str(Path(__file__).resolve()),
    }


def _log(message, environ=None):
    """One line in the sidecar Logs/run.log (best effort; pythonw has no
    console to report to)."""
    try:
        folder = paths.sidecar_dir("Logs", environ)
        folder.mkdir(parents=True, exist_ok=True)
        line = time.strftime("%Y-%m-%dT%H:%M:%S") + " autostart entry: " + message + "\n"
        with open(folder / LOG_NAME, "a", encoding="ascii", errors="replace") as fh:
            fh.write(line)
    except (OSError, ValueError):
        pass


def plan(root=None, environ=None):
    """What a start would do, without doing it."""
    optin = read_optin()
    cmd = launch_command(root, environ)
    script = run_script(root)
    return {
        "optin": optin,
        "optin_file": str(optin_file()),
        "command": cmd,
        "cwd": str(paths.repo_root() if root is None else Path(root)),
        "run_script_present": script.is_file(),
        "would_start": bool(optin and cmd and script.is_file()),
    }


def start(root=None, environ=None, popen=None):
    """Start run.ps1 hidden when the opt-in is on; never waits. Returns the
    exit code: 0 started or opt-in off, 1 a start that could not happen."""
    p = plan(root, environ)
    if not p["optin"]:
        _log("opt-in off (no-op)", environ)
        return 0
    if p["command"] is None:
        _log("SystemRoot is not set; nothing started", environ)
        return 1
    if not p["run_script_present"]:
        _log("scripts/run.ps1 is missing; nothing started", environ)
        return 1
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    spawn = subprocess.Popen if popen is None else popen
    try:
        proc = spawn(p["command"], cwd=p["cwd"], stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     close_fds=True, creationflags=flags)
    except OSError as exc:
        _log("start failed: " + type(exc).__name__, environ)
        return 1
    _log("run.ps1 started (pid %s)" % getattr(proc, "pid", "?"), environ)
    return 0


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--task-action"]:
        sys.stdout.write(json.dumps(task_action(), sort_keys=True) + "\n")
        return 0
    if args == ["--dry-run"]:
        out = plan()
        out["dry_run"] = True
        sys.stdout.write(json.dumps(out, sort_keys=True) + "\n")
        return 0
    if args:
        if sys.stderr is not None:
            sys.stderr.write("usage: python -m %s [--dry-run | --task-action]\n" % MODULE)
        return 2
    return start()


if __name__ == "__main__":
    sys.exit(main())
