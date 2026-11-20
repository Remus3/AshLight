"""DEP-10: scripts/uninstall.ps1, the uninstaller of an installed copy.

Every run here is on a scratch home built by hand from the plan 05
marker field list (docs/plan/05-deployment.md, "Installed-mode layout"),
with TEMP / TMP pointed at a scratch folder and AL_UNINSTALL_FAKE naming a
JSON file that stands in for the process table and the Recycle Bin. So no
test lists, stops or recycles anything real, and no real install, Start
Menu, Desktop, registry key or scheduled task is read or written (steps 3
to 5 are not part of this package). Checked:
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
- static: no game-folder path, every listing / probe / delete sits in a
  home-guarded helper, no dot-sourcing, PowerShell 5.1 parse.
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


def run(world, *args, script=None, stdin=None, wait=1):
    env = dict(os.environ)
    for name in ("AL_HOME", "AL_RUNTIME_DIR", "AL_SIDECAR_ROOT"):
        env.pop(name, None)
    env["TEMP"] = str(world["temp"])
    env["TMP"] = str(world["temp"])
    env["AL_UNINSTALL_FAKE"] = str(world["fake"])
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


def test_script_names_no_game_folder_and_no_registry():
    text = _text()
    for pat in (r"(?i)my games", r"(?i)\bsteam\b", r"(?i)steamapps[\\/]", r"(?i)valve",
                r"(?i)libraryfolders", r"(?i)client\.txt", r"(?i)grinding gear",
                r"(?i)path of exile 2[\\/]", r"(?i)[\\/]path of exile 2",
                r"(?i)\bfilter\b[^.;]*\bfolder\b.*[\\/]", r"(?i)hklm", r"(?i)registry::",
                r"(?i)Get-ItemProperty", r"(?i)PathOfExile"):
        assert not re.search(pat, text), pat
    # the two path-shape guard words appear once, as bare words
    assert text.count("'steamapps'") == 1 and text.count("'path of exile 2'") == 1
    # checkout mode is not here; the dev folders are never named at all
    for word in ("Worktree", "Scratch", "ClaudeHistory", "LaneLoop"):
        assert word not in text


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
    "test-path": {"Test-AlHomePath", "Get-AlHomeChildren", "Remove-AlHomeItem"},
    "get-childitem": {"Get-AlHomeChildren", "Remove-AlHomeItem"},
    "remove-item": {"Remove-AlHomeItem", "Remove-AlOwnCopy"},
    "move-item": {"Send-AlDataToRecycleBin"},
    "copy-item": {"<script>"},
    "set-content": {"Invoke-AlStop"},
    "get-content": {"Test-AlMarker", "Read-AlFake", "Get-AlPidRecords"},
    "get-process": {"Get-AlProcessTable"},
    "stop-process": {"Stop-AlOurProcess"},
    "wait-process": {"Stop-AlOurProcess"},
}
GUARDED = ("Test-AlHomePath", "Get-AlHomeChildren", "Remove-AlHomeItem",
           "Send-AlDataToRecycleBin")
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
    # the real process table, process stop and Recycle Bin are only reached
    # after the fake branch has returned
    for fn, real in (("Get-AlProcessTable", "Get-Process"), ("Stop-AlOurProcess", "Stop-Process"),
                     ("Send-AlDataToRecycleBin", "DeleteDirectory")):
        body = bodies[fn]
        fake_at = body.index("if ($script:Fake)")
        ret_at = body.index("return", fake_at)
        assert fake_at < ret_at < body.index(real), fn
    # no .NET file probe or listing either
    text = _text()
    assert not re.search(r"(?i)::(Exists|GetFiles|GetDirectories|Enumerate\w*)\s*\(", text)
    assert not re.search(r"(?i)\bDirectoryInfo\b|\bFileInfo\b", text)
