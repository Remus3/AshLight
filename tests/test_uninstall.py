"""DEP-10 and REL-UNINSTALL-SHELL: scripts/uninstall.ps1, the uninstaller
of an installed copy.

Every run here is on a scratch home built by hand from the plan 05
marker field list (docs/plan/05-deployment.md, "Installed-mode layout"),
with TEMP / TMP pointed at a scratch folder, AL_SHELL_ROOT pointed at a
scratch effect root (so the two AshLight.lnk paths are scratch files) and
AL_UNINSTALL_FAKE naming a JSON file that stands in for the process table,
the Recycle Bin, the task scheduler ("tasks") and the registry ("keys").
The script refuses the fake without an effect root, and its real
scheduler and registry calls sit after the fake branch has returned
(checked statically), so no test lists, stops, recycles, unregisters or
deletes anything real. The shell tests also read the real per-user
uninstall key, the real "AshLight Autostart" task, this run's scratch
task folder and registry key and the real Start Menu / Desktop
AshLight.lnk before and after a run and assert nothing changed. Checked:
- a valid marker is required, else exit 2 with nothing touched;
- the script re-runs from a temp copy, which removes itself;
- stop.request first, then only processes proven ours are stopped (a pid
  file pid with a matching, non-zero creation time, or an image under
  <home>\\runtime\\);
- the home ends with only data\\ (the per-run files gone); -Purge leaves
  nothing (the injected Recycle Bin gets data\\);
- a held file gives exit 1 and the one line "uninstall incomplete: <n>
  items remain", plus a report in the temp folder;
- -DryRun changes nothing;
- the output is byte-identical with and without ashlight.filter or a
  .build file elsewhere on the machine;
- steps 3 to 5: the logon task "AshLight Autostart", the two
  AshLight.lnk shortcuts and the per-user Uninstall\\AshLight key are
  removed only when they point into the home, else left and named; the dev
  loop task is never named;
- static: no game-folder path, every listing / probe / delete sits in a
  home-guarded helper, the only names outside the home are the fixed shell
  names, no dot-sourcing, PowerShell 5.1 parse.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

try:
    import winreg
except ImportError:  # not Windows: the shell tests skip with PS51
    winreg = None

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "uninstall.ps1"
PS51 = shutil.which("powershell.exe") if sys.platform == "win32" else None

needs_ps = pytest.mark.skipif(PS51 is None, reason="Windows PowerShell 5.1 only")

# plan 05 "Installed-mode layout", marker fields
MARKER = {
    "schema": 1, "name": "AshLight", "version": "0.1.1", "previous": "0.1.0",
    "channel": "stable", "installed_at": "2026-11-19T10:00:00Z",
    "updated_at": "2026-11-19T10:00:00Z", "python": "python-3.14.10",
    "electron": "electron-45.3.3", "pending_confirm": False, "start_attempts": 0,
}
DELETE_NAMES = ["app", "runtime", "cache", "logs", "temp", "build", "staged",
                "install.json", "install.json.bak"]
RUN_FILES = ["token", "token.reuse", "core.alive", "keepalive.json", "keepalive.lock",
             "overlay.pid", "stop.request", "restart.request", "hotreload.json"]
PLAYER_FILES = ["local.json", "consent.json", "run_history.json", "price_watch.json",
                "zone_visits.json", "hotkeys.json"]
LAST_KEPT = "AshLight is removed. Kept: {data} (your settings, history and builds)."
LAST_NONE = "AshLight is removed. Nothing was kept."
COPIED = ("AshLight hands out ashlight.filter and its .build files as downloads; "
          "if you copied them into the game's filter or planner folder, they are "
          "still there.")
INCOMPLETE = re.compile(r"^uninstall incomplete: (\d+) items remain$")
TASK = "AshLight Autostart"
LINK = "AshLight.lnk"
REAL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\AshLight"
SCRATCH_KEY_BASE = r"Software\AshLightShellScratch"


# --- scratch world ---------------------------------------------------------

def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii", newline="\n")


def make_home(base, marker=MARKER):
    home = base / "Programs" / "AshLight"
    if marker is not None:
        _write(home / "install.json", json.dumps(marker) + "\n")
        _write(home / "install.json.bak", json.dumps(marker) + "\n")
    shutil.copyfile(SCRIPT, home / "uninstall.ps1") if home.is_dir() else None
    if not home.is_dir():
        home.mkdir(parents=True)
        shutil.copyfile(SCRIPT, home / "uninstall.ps1")
    _write(home / "app" / "0.1.1" / "server" / "al" / "core.py", "x = 1\n")
    _write(home / "app" / "0.1.0" / "BUILD", "0.1.0\n")
    _write(home / "runtime" / "python-3.14.10" / "python.exe", "not a real exe\n")
    _write(home / "runtime" / "electron-45.3.3" / "electron.exe", "not a real exe\n")
    _write(home / "cache" / "downloads" / "a.zip", "zip\n")
    _write(home / "logs" / "core.log", "log\n")
    _write(home / "temp" / "t.txt", "t\n")
    _write(home / "build" / "b.txt", "b\n")
    _write(home / "staged" / "0.1.2.json", "{}\n")
    data = home / "data"
    for name in PLAYER_FILES:
        _write(data / name, '{"keep": true}\n')
    _write(data / "theorycraft" / "weights.json", "{}\n")
    _write(data / "token", "secret\n")
    _write(data / "token.reuse", "1\n")
    _write(data / "core.alive", json.dumps({"pid": 102, "port": 8960, "updated": 1.0,
                                            "created": 777}) + "\n")
    _write(data / "keepalive.json", json.dumps({"pid": 103, "created": 888}) + "\n")
    _write(data / "keepalive.lock", "")
    _write(data / "overlay.pid", json.dumps({"pid": 106, "created": 0}) + "\n")
    _write(data / "hotreload.json", "{}\n")
    return home


def make_fake(base, home):
    other = base / "elsewhere"
    procs = [
        # ours by image: under <home>\runtime\, never exits by itself
        {"pid": 101, "name": "python.exe",
         "path": str(home / "runtime" / "python-3.14.10" / "python.exe"),
         "created": 5, "graceful": False},
        # ours by pid file: core.alive pid 102 with the recorded creation time
        {"pid": 102, "name": "python.exe", "path": str(other / "py" / "python.exe"),
         "created": 777, "graceful": False},
        # keepalive.json names 103, but the pid was reused (other creation time)
        {"pid": 103, "name": "python.exe", "path": str(other / "py" / "python.exe"),
         "created": 999, "graceful": False},
        # an unrelated Electron app and the game: never ours
        {"pid": 104, "name": "electron.exe", "path": str(other / "chat" / "electron.exe"),
         "created": 1, "graceful": False},
        {"pid": 105, "name": "PathOfExile.exe", "path": str(other / "game" / "PathOfExile.exe"),
         "created": 2, "graceful": False},
        # overlay.pid records 106 with no creation time: not proof enough
        {"pid": 106, "name": "electron.exe", "path": str(other / "e" / "electron.exe"),
         "created": 0, "graceful": False},
        # ours by image, exits by itself once stop.request is there
        {"pid": 107, "name": "electron.exe",
         "path": str(home / "runtime" / "electron-45.3.3" / "electron.exe"),
         "created": 6, "graceful": True},
    ]
    bin_dir = base / "recycle"
    bin_dir.mkdir(exist_ok=True)
    fake = base / "fake.json"
    fake.write_text(json.dumps({"processes": procs, "stopped": [], "recycle": str(bin_dir)},
                               indent=1) + "\n", encoding="ascii")
    return fake


@pytest.fixture
def world(tmp_path):
    temp = tmp_path / "usertemp"
    temp.mkdir()
    home = make_home(tmp_path)
    fake = make_fake(tmp_path, home)
    return {"base": tmp_path, "home": home, "temp": temp, "fake": fake}


def run(world, *args, script=None, stdin=None, wait=1, shell_root=True):
    env = dict(os.environ)
    for name in ("AL_HOME", "AL_RUNTIME_DIR", "AL_SIDECAR_ROOT", "AL_SHELL_ROOT"):
        env.pop(name, None)
    env["TEMP"] = str(world["temp"])
    env["TMP"] = str(world["temp"])
    env["AL_UNINSTALL_FAKE"] = str(world["fake"])
    if shell_root:
        env["AL_SHELL_ROOT"] = str(world["base"] / "shell")
    target = script or (world["home"] / "uninstall.ps1")
    cmd = [PS51, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
           "-File", str(target), "-WaitSec", str(wait)] + list(args)
    feed = {"input": stdin} if stdin is not None else {"stdin": subprocess.DEVNULL}
    r = subprocess.run(cmd, capture_output=True, timeout=180, env=env,
                       cwd=str(world["base"]), **feed)
    out = r.stdout.decode("ascii")
    lines = [ln for ln in out.splitlines() if ln.strip()]
    return r.returncode, lines, r.stdout, r.stderr.decode("utf-8", "replace")


def snapshot(*roots):
    """Every path under roots with its kind, size, mtime and content hash."""
    out = []
    for root in roots:
        if not Path(root).exists():
            out.append((str(root), "absent"))
            continue
        for dirpath, dirs, files in os.walk(root):
            dirs.sort()
            for d in dirs:
                out.append((os.path.join(dirpath, d), "dir"))
            for f in sorted(files):
                p = os.path.join(dirpath, f)
                st = os.stat(p)
                with open(p, "rb") as fh:
                    digest = hashlib.sha256(fh.read()).hexdigest()
                out.append((p, st.st_size, st.st_mtime_ns, digest))
    return out


def _fake(world):
    return json.loads(world["fake"].read_text(encoding="utf-8-sig"))


def _left_in(path):
    return sorted(p.name for p in path.iterdir()) if path.exists() else None


# --- step 1: validation ----------------------------------------------------

BAD_MARKERS = {
    "missing": None,
    "wrong name": dict(MARKER, name="Ashlight"),
    "unknown schema": dict(MARKER, schema=2),
    "schema true": dict(MARKER, schema=True),
    "schema text": dict(MARKER, schema="1"),
}


@needs_ps
@pytest.mark.parametrize("label", sorted(BAD_MARKERS))
def test_an_invalid_marker_exits_2_with_nothing_touched(tmp_path, label):
    temp = tmp_path / "usertemp"
    temp.mkdir()
    marker = BAD_MARKERS[label]
    home = make_home(tmp_path, marker=marker)
    if marker is None:
        (home / "install.json.bak").unlink(missing_ok=True)
    w = {"base": tmp_path, "home": home, "temp": temp, "fake": make_fake(tmp_path, home)}
    before = snapshot(home, temp, w["fake"].parent / "recycle")
    fake_before = w["fake"].read_bytes()
    rc, lines, _, err = run(w)
    assert rc == 2, (lines, err)
    assert lines and lines[-1].startswith("uninstall refused: "), lines
    assert snapshot(home, temp, w["fake"].parent / "recycle") == before
    assert w["fake"].read_bytes() == fake_before


@needs_ps
def test_a_marker_that_is_not_json_exits_2(world):
    (world["home"] / "install.json").write_text("{not json", encoding="ascii")
    before = snapshot(world["home"], world["temp"])
    rc, lines, _, err = run(world)
    assert rc == 2, (lines, err)
    assert snapshot(world["home"], world["temp"]) == before


@needs_ps
@pytest.mark.parametrize("bad", ["SteamLibrary/steamapps/common/AshLight",
                                 "Games/Path of Exile 2/AshLight",
                                 "Lib/SteamApps/common/AshLight"])
def test_a_home_failing_the_path_shape_guard_exits_2(tmp_path, bad):
    temp = tmp_path / "usertemp"
    temp.mkdir()
    home = tmp_path / bad
    home.mkdir(parents=True)
    _write(home / "install.json", json.dumps(MARKER) + "\n")
    _write(home / "app" / "0.1.1" / "x.py", "x\n")
    shutil.copyfile(SCRIPT, home / "uninstall.ps1")
    w = {"base": tmp_path, "home": home, "temp": temp, "fake": make_fake(tmp_path, home)}
    before = snapshot(home, temp)
    rc, lines, _, err = run(w)
    assert rc == 2, (lines, err)
    assert "may not lie in" in lines[-1]
    assert snapshot(home, temp) == before


# --- the default run: data kept ----------------------------------------------

@needs_ps
def test_default_run_keeps_only_data_and_stops_only_our_processes(world):
    home, temp = world["home"], world["temp"]
    rc, lines, _, err = run(world)
    assert rc == 0, (lines, err)
    # step 6 / 7: only data\ stays, with the player's files and no run file
    assert _left_in(home) == ["data"]
    assert _left_in(home / "data") == sorted(PLAYER_FILES + ["theorycraft"])
    assert (home / "data" / "theorycraft" / "weights.json").is_file()
    # step 8: what stays, then the fixed sentence
    assert lines[-2:] == [LAST_KEPT.format(data=str(home / "data")), COPIED]
    # step 2: proven ours only (101 by image, 102 by pid file); 107 exited
    # by itself after stop.request; 103 (reused pid), 104 (other Electron),
    # 105 (the game) and 106 (no recorded creation time) are untouched
    doc = _fake(world)
    assert sorted(doc["stopped"]) == [101, 102]
    assert sorted(p["pid"] for p in doc["processes"]) == [103, 104, 105, 106, 107]
    assert "uninstall: stopping AshLight process 101" in lines
    # step 1: the work ran from a temp copy, which removed itself
    ran_from = Path(doc["ran_from"])
    assert ran_from.parent == temp and ran_from.name.startswith("AshLight-uninstall-")
    assert list(temp.iterdir()) == []
    # the injected Recycle Bin was not used without -Purge
    assert list((world["base"] / "recycle").iterdir()) == []


@needs_ps
def test_a_second_run_is_refused_once_the_marker_is_gone(world):
    rc, _, _, err = run(world)
    assert rc == 0, err
    shutil.copyfile(SCRIPT, world["home"] / "uninstall.ps1")
    before = snapshot(world["home"])
    rc, lines, _, _ = run(world)
    assert rc == 2 and lines[-1].startswith("uninstall refused: no install.json")
    assert snapshot(world["home"]) == before


@needs_ps
def test_quiet_prints_only_the_last_lines(world):
    rc, lines, _, err = run(world, "-Quiet")
    assert rc == 0, err
    assert lines == [LAST_KEPT.format(data=str(world["home"] / "data")), COPIED]


# --- -Purge -----------------------------------------------------------------

@needs_ps
def test_purge_leaves_nothing_and_data_goes_to_the_recycle_bin(world):
    home = world["home"]
    rc, lines, _, err = run(world, "-Purge", "-Yes")
    assert rc == 0, (lines, err)
    assert not home.exists()
    assert home.parent.is_dir()  # only the home itself goes
    assert lines[-2:] == [LAST_NONE, COPIED]
    binned = list((world["base"] / "recycle").iterdir())
    assert len(binned) == 1 and binned[0].name.startswith("data-")
    assert sorted(p.name for p in binned[0].iterdir()) == sorted(PLAYER_FILES + ["theorycraft"])
    assert sorted(_fake(world)["stopped"]) == [101, 102]
    assert list(world["temp"].iterdir()) == []


@needs_ps
def test_purge_without_yes_and_no_one_to_type_is_refused(world):
    before = snapshot(world["home"], world["temp"])
    rc, lines, _, err = run(world, "-Purge", stdin=b"PURGE\n")
    assert rc == 2, (lines, err)
    assert lines[-1] == "uninstall refused: -Purge needs -Yes when no one can type PURGE"
    assert snapshot(world["home"], world["temp"]) == before
    assert _fake(world)["stopped"] == []


# --- step 9: a held file ----------------------------------------------------

@needs_ps
def test_a_held_file_gives_exit_1_and_the_one_line(world):
    home, temp = world["home"], world["temp"]
    held = home / "app" / "0.1.1" / "server" / "al" / "core.py"
    with open(held, "rb"):  # CPython opens without FILE_SHARE_DELETE
        rc, lines, _, err = run(world)
        left = []
        for dirpath, dirs, files in os.walk(home):
            for name in dirs + files:
                p = Path(dirpath) / name
                if p == home / "data" or home / "data" in p.parents:
                    continue
                left.append(p)
    assert rc == 1, (lines, err)
    m = INCOMPLETE.match(lines[-1])
    assert m, lines
    assert int(m.group(1)) == len(left) and held in left
    assert COPIED not in lines  # never a success sentence while a file remains
    report = temp / "AshLight-uninstall-report.txt"
    text = report.read_text(encoding="utf-8")
    assert str(held) in text
    assert [p.name for p in temp.iterdir()] == [report.name]  # the copy is gone


# --- -DryRun ----------------------------------------------------------------

@needs_ps
@pytest.mark.parametrize("extra", [[], ["-Purge"], ["-Purge", "-Yes"]])
def test_dry_run_changes_nothing(world, extra):
    roots = (world["home"], world["temp"], world["base"] / "recycle")
    before = snapshot(*roots)
    fake_before = world["fake"].read_bytes()
    rc, lines, _, err = run(world, "-DryRun", *extra)
    assert rc == 0, (lines, err)
    assert snapshot(*roots) == before
    assert world["fake"].read_bytes() == fake_before
    assert "uninstall: would stop AshLight process 101" in lines
    assert "uninstall: would delete " + str(world["home"] / "app") in lines
    assert not any("would delete " + str(world["home"] / "data") == ln[len("uninstall: "):]
                   for ln in lines)


# --- step 8: the same lines whatever lies elsewhere ---------------------------

@needs_ps
def test_output_is_byte_identical_with_or_without_copied_files(tmp_path):
    temp = tmp_path / "usertemp"
    temp.mkdir()
    outputs = []
    for planted in (False, True):
        home = tmp_path / "Programs" / "AshLight"
        if home.exists():
            shutil.rmtree(home)
        home = make_home(tmp_path)
        w = {"base": tmp_path, "home": home, "temp": temp, "fake": make_fake(tmp_path, home)}
        if planted:
            docs = tmp_path / "Documents" / "My Games" / "Path of Exile 2"
            _write(docs / "ashlight.filter", "Show\n")
            _write(docs / "BuildPlanner" / "mine.build", "<build/>\n")
            _write(tmp_path / "Downloads" / "ashlight.filter", "Show\n")
        rc, _, raw, err = run(w)
        assert rc == 0, err
        outputs.append(raw)
    assert outputs[0] == outputs[1]
    assert outputs[0].rstrip().endswith(COPIED.encode("ascii"))


# --- static ----------------------------------------------------------------

def _text():
    return SCRIPT.read_text(encoding="ascii")


def test_script_is_ascii_lf_and_self_contained():
    raw = SCRIPT.read_bytes()
    assert raw.isascii() and b"\r" not in raw
    text = _text()
    # no dot-sourcing and no module import: the copy in temp must stand alone
    assert not re.search(r"(?m)^\s*\.\s+\S", text)
    assert not re.search(r"(?i)\bImport-Module\b|\bUsing\s+module\b", text)
    # no Python: the uninstaller needs none
    assert not re.search(r"(?i)\bpython\s+-m\b|server\.al|boot\.py", text)


# Every single-quoted literal of the script that names a place outside the
# home (a path separator, a link, a key or a task): exactly these.
OUTSIDE_LITERALS = {
    "'AshLight.lnk'", "'AshLight Autostart'",
    "'Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\AshLight'",
    "'Software\\AshLightShellScratch'", "'\\AshLightShellScratch\\'",
    "'\\Uninstall\\AshLight'", "'\\'", "'HKCU\\'",
    "'System32\\WindowsPowerShell\\v1.0\\powershell.exe'",
    "'[\\\\/]+'",  # the path-shape guard's split pattern, not a place
}


def test_reads_outside_the_home_are_only_the_fixed_shell_names():
    # DEP-10's static test, narrowed by REL-UNINSTALL-SHELL: no game-folder
    # path and no listing outside the home; the only places outside the
    # home are the two AshLight.lnk paths, the per-user Uninstall\AshLight
    # key and the task 'AshLight Autostart' (each with its effect-root
    # scratch twin).
    text = _text()
    for pat in (r"(?i)my games", r"(?i)\bsteam\b", r"(?i)steamapps[\\/]", r"(?i)valve",
                r"(?i)libraryfolders", r"(?i)client\.txt", r"(?i)grinding gear",
                r"(?i)path of exile 2[\\/]", r"(?i)[\\/]path of exile 2",
                r"(?i)\bfilter\b[^.;]*\bfolder\b.*[\\/]", r"(?i)hklm", r"(?i)registry::",
                r"(?i)Get-ItemProperty", r"(?i)PathOfExile", r"(?i)LocalMachine",
                r"(?i)\bHKLM\b", r"(?i)Common(Programs|Desktop|StartMenu)",
                r"(?i)\bschtasks\b", r"(?i)\breg(\.exe)?\s+(delete|query|add)\b"):
        assert not re.search(pat, text), pat
    # the two path-shape guard words appear once, as bare words
    assert text.count("'steamapps'") == 1 and text.count("'path of exile 2'") == 1
    # checkout mode is not here; the dev folders are never named at all
    for word in ("Worktree", "ClaudeHistory", "LaneLoop", "AshLightOps"):
        assert word not in text
    # the outside names, each defined once
    for line in ("$script:LinkName = 'AshLight.lnk'",
                 "$script:TaskName = 'AshLight Autostart'",
                 "$script:RealKey = 'Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\AshLight'"):
        assert text.count(line) == 1, line
    # no other place-like literal anywhere
    found = set(re.findall(r"'[^'\n]*'", text))
    placey = {lit for lit in found
              if "\\" in lit or "/" in lit or ".lnk" in lit.lower()
              or "autostart" in lit.lower() or "uninstall\\" in lit.lower()}
    assert placey == OUTSIDE_LITERALS, placey ^ OUTSIDE_LITERALS
    # the shell folders: only this user's Programs and Desktop
    assert sorted(set(re.findall(r"GetFolderPath\('([^']+)'\)", text))) == ["Desktop", "Programs"]
    # the registry: HKCU only, and only the one key of the places
    assert re.findall(r"\[Microsoft\.Win32\.Registry\]::(\w+)\.(\w+)\(([^,)]*)", text) == [
        ("CurrentUser", "OpenSubKey", "$script:Shell.Key"),
        ("CurrentUser", "DeleteSubKeyTree", "$script:Shell.Key")]
    # the task scheduler: only the one task name, in the one task folder
    for call in re.findall(r"(?m)^.*-ScheduledTask\b.*$", text):
        assert "-TaskName $script:TaskName -TaskPath $script:Shell.TaskPath" in call, call
    # the link paths are built from the fixed name only
    assert re.findall(r"\$script:LinkPaths \+= .*", text) == [
        "$script:LinkPaths += (Get-AlFullPath (Join-Path $folder $script:LinkName)) }"]


def test_delete_names_are_the_fixed_list():
    text = _text()
    m = re.search(r"\$script:DeleteNames = @\(([^)]*)\)", text)
    assert m and re.findall(r"'([^']+)'", m.group(1)) == DELETE_NAMES
    m = re.search(r"\$script:RunFiles = @\(([^)]*)\)", text)
    assert m and re.findall(r"'([^']+)'", m.group(1)) == RUN_FILES
    # no wildcard delete or listing anywhere
    assert not re.search(r"(?i)-(Filter|Include|Exclude)\b", text)
    assert "*" not in "".join(re.findall(r"'[^']*'", text))


# Where each file system cmdlet may sit (the enclosing function; <script>
# is the top level). Every listed helper refuses a path outside the home.
ALLOWED = {
    "test-path": {"Test-AlHomePath", "Get-AlHomeChildren", "Remove-AlHomeItem",
                  "Test-AlShellLink"},
    "get-childitem": {"Get-AlHomeChildren", "Remove-AlHomeItem"},
    "remove-item": {"Remove-AlHomeItem", "Remove-AlOwnCopy", "Remove-AlShellLink"},
    "move-item": {"Send-AlDataToRecycleBin"},
    "copy-item": {"<script>"},
    "set-content": {"Invoke-AlStop"},
    "get-content": {"Test-AlMarker", "Read-AlFake", "Get-AlPidRecords"},
    "get-process": {"Get-AlProcessTable"},
    "stop-process": {"Stop-AlOurProcess"},
    "wait-process": {"Stop-AlOurProcess"},
    "get-scheduledtask": {"Get-AlTaskRecord"},
    "unregister-scheduledtask": {"Remove-AlTask"},
}
GUARDED = ("Test-AlHomePath", "Get-AlHomeChildren", "Remove-AlHomeItem",
           "Send-AlDataToRecycleBin")
# the shortcut helpers accept only the two fixed AshLight.lnk paths
LINK_GUARDED = ("Test-AlShellLink", "Get-AlLinkTarget", "Remove-AlShellLink")
NEVER = ("get-item", "gi", "gci", "ls", "dir", "resolve-path", "get-psdrive",
         "get-itemproperty", "get-wmiobject", "get-ciminstance", "test-connection",
         "invoke-webrequest", "invoke-restmethod", "start-process", "new-item")

_AST_DUMP = r"""
$errs = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($args[0], [ref]$null, [ref]$errs)
foreach ($e in @($errs)) { 'ERROR ' + $e.Message }
$cmds = $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] }, $true)
foreach ($c in $cmds) {
    $name = $c.GetCommandName()
    if (-not $name) { continue }
    $fn = '<script>'
    $p = $c.Parent
    while ($p) {
        if ($p -is [System.Management.Automation.Language.FunctionDefinitionAst]) { $fn = $p.Name; break }
        $p = $p.Parent
    }
    'CMD ' + $name.ToLowerInvariant() + ' ' + $fn
}
$fns = $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true)
foreach ($f in $fns) { 'FN ' + $f.Name + ' ' + [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($f.Body.Extent.Text)) }
"""


@pytest.fixture(scope="module")
def ast_dump(tmp_path_factory):
    if PS51 is None:
        pytest.skip("Windows PowerShell 5.1 only")
    helper = tmp_path_factory.mktemp("ast") / "dump.ps1"
    helper.write_text(_AST_DUMP, encoding="ascii")
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                        "-File", str(helper), str(SCRIPT)], capture_output=True, text=True,
                       timeout=120)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()


def test_parses_with_powershell_5_1(ast_dump):
    assert not [ln for ln in ast_dump if ln.startswith("ERROR ")]


def test_every_probe_listing_and_delete_sits_in_a_home_guarded_helper(ast_dump):
    import base64
    cmds = [ln.split(" ", 2)[1:] for ln in ast_dump if ln.startswith("CMD ")]
    bodies = {}
    for ln in ast_dump:
        if ln.startswith("FN "):
            _, name, b64 = ln.split(" ", 2)
            bodies[name] = base64.b64decode(b64).decode("utf-8")
    assert cmds
    for name, fn in cmds:
        assert name not in NEVER, (name, fn)
        if name in ALLOWED:
            assert fn in ALLOWED[name], (name, fn)
    for fn in GUARDED:
        assert "Assert-AlInHome" in bodies[fn], fn
    for fn in LINK_GUARDED:
        body = bodies[fn]
        assert body.index("Assert-AlShellLink") < min(
            body.index(w) for w in ("Test-Path", "CreateShortcut", "Remove-Item") if w in body), fn
    # the real process table, process stop, Recycle Bin, task scheduler and
    # registry are only reached after the fake branch has returned
    for fn, real in (("Get-AlProcessTable", "Get-Process"), ("Stop-AlOurProcess", "Stop-Process"),
                     ("Send-AlDataToRecycleBin", "DeleteDirectory"),
                     ("Get-AlTaskRecord", "Get-ScheduledTask"),
                     ("Remove-AlTask", "Unregister-ScheduledTask"),
                     ("Get-AlKeyLocation", "OpenSubKey"), ("Remove-AlKey", "DeleteSubKeyTree")):
        body = bodies[fn]
        fake_at = body.index("if ($script:Fake)")
        ret_at = body.index("return", fake_at)
        assert fake_at < ret_at < body.index(real), fn
    # the one COM object is the shortcut reader, behind the link guard
    assert _text().count("-ComObject") == 1 and "-ComObject WScript.Shell" in bodies["Get-AlLinkTarget"]
    # no .NET file probe or listing either
    text = _text()
    assert not re.search(r"(?i)::(Exists|GetFiles|GetDirectories|Enumerate\w*)\s*\(", text)
    assert not re.search(r"(?i)\bDirectoryInfo\b|\bFileInfo\b", text)


# --- steps 3 to 5: logon task, shortcuts, uninstall key -----------------------

def _q(text):
    return "'" + str(text).replace("'", "''") + "'"


def _scratch(world):
    """The scratch places the effect root gives (as al_shell.ps1)."""
    root = world["base"] / "shell"
    sid = hashlib.sha256(str(root).lower().encode("utf-8")).digest()[:8].hex()
    return {
        "root": root,
        "id": sid,
        "task_path": "\\AshLightShellScratch\\" + sid + "\\",
        "key": SCRATCH_KEY_BASE + "\\" + sid + "\\Uninstall\\AshLight",
        "links": [root / "Programs" / LINK, root / "Desktop" / LINK],
    }


def make_links(world, targets):
    """Real .lnk files, only under the scratch effect root of this test."""
    sc = _scratch(world)
    lines = ["$s = New-Object -ComObject WScript.Shell"]
    for link, target in zip(sc["links"], targets):
        assert world["base"] in link.parents
        link.parent.mkdir(parents=True, exist_ok=True)
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        Path(target).touch()
        lines.append(f"$l = $s.CreateShortcut({_q(link)}); $l.TargetPath = {_q(target)}; $l.Save()")
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-Command", "; ".join(lines)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    for link in sc["links"]:
        assert link.is_file()


def set_shell_fake(world, tasks=(), keys=None):
    doc = _fake(world)
    doc["tasks"] = list(tasks)
    doc["keys"] = dict(keys or {})
    world["fake"].write_text(json.dumps(doc, indent=1) + "\n", encoding="ascii")


_REAL_STATE = r"""
$t = @(Get-ScheduledTask -TaskName 'AshLight Autostart' -ErrorAction SilentlyContinue)
$t += @(Get-ScheduledTask -TaskPath $args[0] -ErrorAction SilentlyContinue)
$rows = @($t | Where-Object { $_ } | ForEach-Object {
    $_.TaskPath + $_.TaskName + '|' + (@($_.Actions | ForEach-Object {
        [string]$_.Execute + ' ' + [string]$_.Arguments + ' ' + [string]$_.WorkingDirectory }) -join ';') })
foreach ($f in @([Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop'))) {
    $p = Join-Path $f 'AshLight.lnk'
    $i = Get-Item -LiteralPath $p -ErrorAction SilentlyContinue
    if ($i) { $rows += ('LINK ' + $p + '|' + $i.Length + '|' + $i.LastWriteTimeUtc.Ticks) }
    else { $rows += ('LINK ' + $p + '|absent') }
}
$rows | ForEach-Object { 'ROW ' + $_ }
"""


def _reg_state(sub):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub)
    except OSError:
        return None
    with key:
        nsub, nval, stamp = winreg.QueryInfoKey(key)
        return (nsub, stamp, sorted(winreg.EnumValue(key, i)[:2] for i in range(nval)))


def real_state(world, tmp_dir):
    """Read only: the real 'AshLight Autostart' task, this run's scratch task
    folder, the real Start Menu / Desktop AshLight.lnk, the real per-user
    uninstall key and this run's scratch keys."""
    sc = _scratch(world)
    helper = tmp_dir / "real_state.ps1"
    helper.write_text(_REAL_STATE, encoding="ascii")
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                        "-File", str(helper), sc["task_path"]],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    rows = sorted(ln[4:] for ln in r.stdout.splitlines() if ln.startswith("ROW "))
    assert len([x for x in rows if x.startswith("LINK ")]) == 2, rows
    return {"tasks_and_links": rows, "real_key": _reg_state(REAL_KEY),
            "scratch_key": _reg_state(sc["key"]),
            "scratch_id": _reg_state(SCRATCH_KEY_BASE + "\\" + sc["id"])}


needs_shell = pytest.mark.skipif(PS51 is None or winreg is None, reason="Windows only")


@pytest.fixture
def shell_world(world):
    world["sc"] = _scratch(world)
    world["state_dir"] = world["base"] / "state"
    world["state_dir"].mkdir()
    before = real_state(world, world["state_dir"])
    yield world
    # read back: nothing real changed, whatever the test did
    assert real_state(world, world["state_dir"]) == before


@needs_shell
def test_task_link_and_key_pointing_into_the_home_are_removed(shell_world):
    w = shell_world
    home, sc = w["home"], w["sc"]
    make_links(w, [home / "runtime" / "electron-45.3.3" / "electron.exe",
                   home / "app" / "0.1.1" / "AshLight.exe"])
    set_shell_fake(w, tasks=[{"path": sc["task_path"], "name": TASK,
                              "execute": str(home / "runtime" / "python-3.14.10" / "pythonw.exe"),
                              "working_directory": str(home / "app" / "0.1.1")}],
                   keys={sc["key"]: {"InstallLocation": str(home)}})
    where_task = sc["task_path"] + TASK
    where_key = "HKCU\\" + sc["key"]
    # the plan printer: everything named, nothing changed
    fake_before = w["fake"].read_bytes()
    rc, lines, _, err = run(w, "-DryRun")
    assert rc == 0, (lines, err)
    assert "uninstall: would remove the logon task " + where_task in lines
    for link in sc["links"]:
        assert "uninstall: would remove " + str(link) in lines
        assert link.is_file()
    assert "uninstall: would remove the uninstall entry " + where_key in lines
    assert w["fake"].read_bytes() == fake_before
    # the run: all three removed and read back
    rc, lines, _, err = run(w)
    assert rc == 0, (lines, err)
    assert "uninstall: removing the logon task " + where_task in lines
    assert "uninstall: removing the uninstall entry " + where_key in lines
    for link in sc["links"]:
        assert "uninstall: removing " + str(link) in lines
        assert not link.exists()
        assert link.parent.is_dir()  # only the link goes
    doc = _fake(w)
    assert doc["tasks"] == [] and doc["removed_tasks"] == [where_task]
    assert doc["keys"] == {} and doc["removed_keys"] == [sc["key"]]
    # the read-back asks for the same one name again, nothing else
    assert doc["task_queries"] == [where_task, where_task]
    assert doc["key_queries"] == [sc["key"], sc["key"]]
    assert _left_in(home) == ["data"]
    assert lines[-2:] == [LAST_KEPT.format(data=str(home / "data")), COPIED]


@needs_shell
@pytest.mark.parametrize("task_form", ["workdir elsewhere", "program elsewhere"])
def test_task_link_and_key_pointing_elsewhere_are_left(shell_world, task_form):
    w = shell_world
    home, sc = w["home"], w["sc"]
    other = w["base"] / "elsewhere"
    # a sibling whose name starts like the home is not the home
    make_links(w, [other / "AshLight" / "electron.exe",
                   home.parent / (home.name + "Old") / "electron.exe"])
    if task_form == "workdir elsewhere":
        task = {"execute": str(home / "runtime" / "python-3.14.10" / "pythonw.exe"),
                "working_directory": str(other / "checkout")}
    else:
        task = {"execute": '"' + str(other / "py" / "pythonw.exe") + '"', "working_directory": ""}
    tasks = [dict(task, path=sc["task_path"], name=TASK),
             # the real task folder and key are never looked at under an
             # effect root, even when they point into the home
             {"path": "\\", "name": TASK, "execute": str(home / "x.exe"),
              "working_directory": str(home)}]
    keys = {sc["key"]: {"InstallLocation": str(home) + "Old"},
            REAL_KEY: {"InstallLocation": str(home)}}
    set_shell_fake(w, tasks=tasks, keys=keys)
    links_before = snapshot(*(ln.parent for ln in sc["links"]))
    rc, lines, _, err = run(w)
    assert rc == 0, (lines, err)
    assert ("uninstall: leaving the logon task " + sc["task_path"] + TASK
            + ": it points elsewhere") in lines
    assert ("uninstall: leaving the uninstall entry HKCU\\" + sc["key"]
            + ": it points elsewhere") in lines
    for link in sc["links"]:
        assert "uninstall: leaving " + str(link) + ": it points elsewhere" in lines
    assert not any(ln.startswith("uninstall: removing") for ln in lines)
    assert snapshot(*(ln.parent for ln in sc["links"])) == links_before
    doc = _fake(w)
    assert doc["tasks"] == tasks and doc["keys"] == keys
    assert "removed_tasks" not in doc and "removed_keys" not in doc
    assert doc["task_queries"] == [sc["task_path"] + TASK]
    assert doc["key_queries"] == [sc["key"]]
    # the home's own files went as usual; the left items are not ours
    assert _left_in(home) == ["data"]
    assert lines[-1] == COPIED


@needs_shell
def test_shell_effects_are_redirected_in_tests(shell_world):
    w = shell_world
    home = w["home"]
    make_links(w, [home / "runtime" / "electron-45.3.3" / "electron.exe"] * 2)
    set_shell_fake(w, tasks=[{"path": "\\", "name": TASK, "execute": str(home / "x.exe"),
                              "working_directory": str(home)}],
                   keys={REAL_KEY: {"InstallLocation": str(home)}})
    roots = (home, w["temp"], w["sc"]["root"], w["base"] / "recycle")
    before = snapshot(*roots)
    fake_before = w["fake"].read_bytes()
    # the doubles must be in force before any code runs: the fake without
    # an effect root is refused at validation, with nothing touched
    for args in ((), ("-DryRun",)):
        rc, lines, _, err = run(w, *args, shell_root=False)
        assert rc == 2, (lines, err)
        assert lines[-1] == ("uninstall refused: AL_UNINSTALL_FAKE needs AL_SHELL_ROOT "
                             "(no real shell entry is read in a test)")
        assert snapshot(*roots) == before
        assert w["fake"].read_bytes() == fake_before
    # a relative effect root is refused too
    env = dict(os.environ, TEMP=str(w["temp"]), TMP=str(w["temp"]),
               AL_UNINSTALL_FAKE=str(w["fake"]), AL_SHELL_ROOT="relative\\root")
    for name in ("AL_HOME", "AL_RUNTIME_DIR", "AL_SIDECAR_ROOT"):
        env.pop(name, None)
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                        "-File", str(home / "uninstall.ps1"), "-WaitSec", "1"],
                       capture_output=True, timeout=180, env=env, cwd=str(w["base"]),
                       stdin=subprocess.DEVNULL)
    assert r.returncode == 2, r.stdout
    assert b"uninstall refused: AL_SHELL_ROOT is not an absolute path" in r.stdout
    assert snapshot(*roots) == before
    assert w["fake"].read_bytes() == fake_before
    # with the effect root, the real-place entries of the fake are never
    # asked for: only the scratch task folder and scratch key
    rc, lines, _, err = run(w)
    assert rc == 0, (lines, err)
    doc = _fake(w)
    assert doc["task_queries"] == [w["sc"]["task_path"] + TASK]
    assert doc["key_queries"] == [w["sc"]["key"]]
    assert len(doc["tasks"]) == 1 and REAL_KEY in doc["keys"]
    # the real scheduler and registry calls sit after the fake branch
    # (test_every_probe_listing_and_delete_sits_in_a_home_guarded_helper);
    # shell_world reads the real task, keys and links back after the test.


@needs_ps
def test_dev_loop_task_is_never_named(world):
    text = _text()
    for word in ("LaneLoop", "AshLightOps", "laneloop"):
        assert word not in text
    # the one task name, in the one call shape
    assert set(re.findall(r"-TaskName (\S+)", text)) == {"$script:TaskName"}
    assert text.count("'AshLight Autostart'") == 1
    # live: a dev loop task in the fake, even one pointing into the home,
    # is never asked for and stays
    sc = _scratch(world)
    home = world["home"]
    tasks = [{"path": "\\AshLightOps\\", "name": "LaneLoop", "execute": str(home / "x.exe"),
              "working_directory": str(home)},
             {"path": sc["task_path"], "name": "LaneLoop", "execute": str(home / "x.exe"),
              "working_directory": str(home)}]
    set_shell_fake(world, tasks=tasks)
    rc, lines, _, err = run(world)
    assert rc == 0, (lines, err)
    doc = _fake(world)
    assert doc["tasks"] == tasks
    assert doc["task_queries"] == [sc["task_path"] + TASK]
    assert not any("LaneLoop" in ln for ln in lines)
