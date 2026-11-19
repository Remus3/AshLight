"""DEP-07: scripts/al_shell.ps1, the one shell integration helper.

It writes, reads back and removes the "AshLight" Start Menu and Desktop
shortcuts and the per-user uninstall entry; setup.ps1 dot-sources it.

Every effect here is injected through a scratch effect root (env
AL_SHELL_ROOT or -EffectRoot): the shortcuts land in a pytest tmp folder and
the uninstall entry in a scratch registry key (HKCU\\Software\\
AshLightShellScratch\\<id>) that the fixture deletes. The player's real
Start Menu, Desktop and Uninstall\\AshLight key are only read (a before /
after snapshot) and never written. Checked:
- the effect root redirects every place, as a parameter or from the env;
- every write is read back; a re-run is a no-op ('current');
- a shortcut or an uninstall entry that points elsewhere is left alone;
- a shortcut path outside the effect root is refused;
- Test-AlOurs is a full-path, case-insensitive "under the root" check.
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
SHELL = ROOT / "scripts" / "al_shell.ps1"
SETUP = ROOT / "scripts" / "setup.ps1"
PS51 = shutil.which("powershell.exe") if sys.platform == "win32" else None
SCRATCH_BASE = r"Software\AshLightShellScratch"
REAL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\AshLight"

needs_ps = pytest.mark.skipif(PS51 is None, reason="Windows PowerShell 5.1 only")


def _q(path):
    return "'" + str(path).replace("'", "''") + "'"


def _ps(script, effect_root=None, timeout=90):
    env = dict(os.environ)
    env.pop("AL_SHELL_ROOT", None)
    if effect_root is not None:
        env["AL_SHELL_ROOT"] = str(effect_root)
    full = ("$ErrorActionPreference = 'Stop'; Set-StrictMode -Version 2; "
            f". {_q(SHELL)}; " + script)
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                        "-Command", full], capture_output=True, text=True,
                       timeout=timeout, env=env, cwd=str(ROOT))
    return r


def _ok(script, effect_root=None):
    r = _ps(script, effect_root)
    assert r.returncode == 0, r.stdout + r.stderr
    return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]


def _scratch_id(root):
    full = os.path.abspath(str(root)).rstrip("\\")
    return hashlib.sha256(full.lower().encode("utf-8")).digest()[:8].hex()


def _delete_tree(winreg, parent, sub):
    try:
        key = winreg.OpenKey(parent, sub, 0, winreg.KEY_ALL_ACCESS)
    except OSError:
        return
    with key:
        while True:
            try:
                child = winreg.EnumKey(key, 0)
            except OSError:
                break
            _delete_tree(winreg, key, child)
    winreg.DeleteKey(parent, sub)


def _cleanup_scratch(root):
    import winreg
    _delete_tree(winreg, winreg.HKEY_CURRENT_USER, SCRATCH_BASE + "\\" + _scratch_id(root))
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, SCRATCH_BASE) as base:
            winreg.QueryInfoKey(base)
            empty = winreg.QueryInfoKey(base)[0] == 0
    except OSError:
        return
    if empty:
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, SCRATCH_BASE)
        except OSError:
            pass


@pytest.fixture
def eroot(tmp_path):
    root = tmp_path / "effect"
    root.mkdir()
    yield root
    _cleanup_scratch(root)


def _real_snapshot():
    """A read-only look at the player's real shortcuts and uninstall key."""
    lines = _ok("$p = Get-AlShellPlaces; "
                "foreach ($l in @(Get-AlShortcutPaths)) { "
                "  if (Test-Path -LiteralPath $l) { $i = Get-Item -LiteralPath $l; "
                "    'LINK ' + $l + ' ' + $i.Length + ' ' + $i.LastWriteTimeUtc.Ticks } "
                "  else { 'LINK ' + $l + ' absent' } }; "
                "'KEY ' + $p.UninstallKey + ' ' + $p.Scratch")
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REAL_KEY) as key:
            values = {}
            i = 0
            while True:
                try:
                    name, data, _ = winreg.EnumValue(key, i)
                except OSError:
                    break
                values[name] = data
                i += 1
            lines.append("VALUES " + json.dumps(values, sort_keys=True))
    except OSError:
        lines.append("VALUES absent")
    return lines


@pytest.fixture(scope="module", autouse=True)
def real_places_untouched():
    if PS51 is None:
        yield
        return
    before = _real_snapshot()
    yield
    assert _real_snapshot() == before


def _target(tmp_path, owner="owner"):
    folder = tmp_path / owner / "app"
    folder.mkdir(parents=True, exist_ok=True)
    exe = folder / "electron.exe"
    exe.write_bytes(b"")
    icon = folder / "icon.ico"
    icon.write_bytes(b"")
    return tmp_path / owner, folder, exe, icon


@needs_ps
def test_effect_root_redirects_every_place(eroot, tmp_path):
    show = ("$p = Get-AlShellPlaces{arg}; 'S=' + $p.Scratch; 'P=' + $p.Programs; "
            "'D=' + $p.Desktop; 'K=' + $p.UninstallKey")
    sid = _scratch_id(eroot)
    want = [f"S=True", f"P={eroot}\\Programs", f"D={eroot}\\Desktop",
            f"K=HKCU:\\{SCRATCH_BASE}\\{sid}\\Uninstall\\AshLight"]
    assert _ok(show.format(arg=""), effect_root=eroot) == want  # from the env
    assert _ok(show.format(arg=" -EffectRoot " + _q(eroot))) == want  # as a parameter
    real = _ok(show.format(arg=""))
    assert real[0] == "S=False"
    assert real[3] == "K=HKCU:\\" + REAL_KEY
    assert not real[1].startswith("P=" + str(tmp_path)) and real[1] != "P="
    # a relative effect root is refused
    r = _ps("Get-AlShellPlaces -EffectRoot 'relative\\dir'")
    assert r.returncode != 0 and "absolute" in (r.stdout + r.stderr)


@needs_ps
def test_shortcuts_written_read_back_and_rerun_is_noop(eroot, tmp_path):
    owner, app, exe, icon = _target(tmp_path)
    call = (f"Install-AlShortcuts -Target {_q(exe)} -Arguments '\"{app}\" --client' "
            f"-WorkDir {_q(app)} -Icon {_q(icon)} -OwnerRoot {_q(owner)} | "
            "ForEach-Object { $_.Status + '|' + $_.Link }")
    read = ("$sh = New-Object -ComObject WScript.Shell; "
            "foreach ($l in @(Get-AlShortcutPaths)) { $s = $sh.CreateShortcut($l); "
            "'T=' + $s.TargetPath; 'A=' + $s.Arguments; 'W=' + $s.WorkingDirectory; "
            "'I=' + $s.IconLocation }")
    lines = _ok(f"{call}; {call}; {read}", effect_root=eroot)
    progs, desk = eroot / "Programs" / "AshLight.lnk", eroot / "Desktop" / "AshLight.lnk"
    assert lines[:4] == [f"written|{progs}", f"written|{desk}",
                         f"current|{progs}", f"current|{desk}"], lines
    assert lines[4:8] == [f"T={exe}", f'A="{app}" --client', f"W={app}", f"I={icon},0"]
    assert lines[8:12] == lines[4:8]
    assert progs.is_file() and desk.is_file()
    # a changed argument is rewritten (and read back) on the next run
    again = _ok(call.replace("--client", "--client --x"), effect_root=eroot)
    assert again == [f"written|{progs}", f"written|{desk}"]


@needs_ps
def test_shortcut_pointing_elsewhere_is_left_alone(eroot, tmp_path):
    owner, app, exe, icon = _target(tmp_path)
    other, oapp, oexe, oicon = _target(tmp_path, "installed")
    desk = eroot / "Desktop" / "AshLight.lnk"
    progs = eroot / "Programs" / "AshLight.lnk"
    script = (
        f"Set-AlShortcut -LinkPath {_q(desk)} -Target {_q(oexe)} -Arguments 'x' "
        f"-WorkDir {_q(oapp)} -Icon {_q(oicon)} -OwnerRoot {_q(other)}; "
        f"Install-AlShortcuts -Target {_q(exe)} -Arguments 'y' -WorkDir {_q(app)} "
        f"-Icon {_q(icon)} -OwnerRoot {_q(owner)} | ForEach-Object {{ $_.Status }}; "
        f"'T=' + (New-Object -ComObject WScript.Shell).CreateShortcut({_q(desk)}).TargetPath; "
        f"Remove-AlShortcut -LinkPath {_q(desk)} -OwnerRoot {_q(owner)}; "
        f"Remove-AlShortcut -LinkPath {_q(progs)} -OwnerRoot {_q(owner)}; "
        f"Remove-AlShortcut -LinkPath {_q(progs)} -OwnerRoot {_q(owner)}")
    lines = _ok(script, effect_root=eroot)
    assert lines == ["written", "written", "elsewhere", f"T={oexe}",
                     "elsewhere", "removed", "absent"], lines
    assert desk.is_file() and not progs.exists()


@needs_ps
def test_shortcut_outside_the_effect_root_is_refused(eroot, tmp_path):
    owner, app, exe, icon = _target(tmp_path)
    outside = tmp_path / "outside" / "AshLight.lnk"
    r = _ps(f"Set-AlShortcut -LinkPath {_q(outside)} -Target {_q(exe)} -Arguments '' "
            f"-WorkDir {_q(app)} -Icon {_q(icon)} -OwnerRoot {_q(owner)}", effect_root=eroot)
    assert r.returncode != 0 and "outside the effect root" in (r.stdout + r.stderr)
    assert not outside.exists() and not outside.parent.exists()
    # a target outside the owner root is refused too
    r = _ps(f"Set-AlShortcut -LinkPath {_q(eroot / 'Desktop' / 'AshLight.lnk')} "
            f"-Target {_q(exe)} -Arguments '' -WorkDir {_q(app)} -Icon {_q(icon)} "
            f"-OwnerRoot {_q(tmp_path / 'elsewhere')}", effect_root=eroot)
    assert r.returncode != 0 and "not under the owner root" in (r.stdout + r.stderr)


@needs_ps
def test_uninstall_entry_round_trip(eroot, tmp_path):
    home = tmp_path / "home"
    icon = home / "app" / "icon.ico"
    show = ("$k = (Get-AlShellPlaces).UninstallKey; $v = Get-ItemProperty -LiteralPath $k; "
            "foreach ($n in @('DisplayName','DisplayVersion','Publisher','InstallLocation',"
            "'UninstallString','QuietUninstallString','DisplayIcon','NoModify','NoRepair')) "
            "{ $n + '=' + $v.$n }")
    script = (
        f"Set-AlUninstallEntry -InstallLocation {_q(home)} -Version '1.2.3' -Icon {_q(icon)}; "
        f"Set-AlUninstallEntry -InstallLocation {_q(home)} -Version '1.2.3' -Icon {_q(icon)}; "
        f"{show}; "
        f"Set-AlUninstallEntry -InstallLocation {_q(home)} -Version '1.2.4' -Icon {_q(icon)}; "
        f"Set-AlUninstallEntry -InstallLocation {_q(home)} -Version '1.2.4'; "
        "$k = (Get-AlShellPlaces).UninstallKey; "
        "'ICON=' + [bool]((Get-ItemProperty -LiteralPath $k).PSObject.Properties['DisplayIcon']); "
        f"Remove-AlUninstallEntry -InstallLocation {_q(home)}; "
        "'GONE=' + (-not (Test-Path -LiteralPath $k)); "
        f"Remove-AlUninstallEntry -InstallLocation {_q(home)}")
    lines = _ok(script, effect_root=eroot)
    ps = os.path.join(os.environ["SystemRoot"],
                      r"System32\WindowsPowerShell\v1.0\powershell.exe")
    cmd = f'"{ps}" -NoProfile -ExecutionPolicy Bypass -File "{home}\\uninstall.ps1"'
    assert lines[:2] == ["written", "current"], lines
    assert lines[2:11] == [
        "DisplayName=AshLight", "DisplayVersion=1.2.3", "Publisher=The AshLight authors",
        f"InstallLocation={home}", f"UninstallString={cmd}",
        f"QuietUninstallString={cmd} -Quiet", f"DisplayIcon={icon}", "NoModify=1",
        "NoRepair=1"], lines
    assert lines[11:] == ["written", "written", "ICON=False", "removed", "GONE=True",
                          "absent"], lines


@needs_ps
def test_uninstall_entry_pointing_elsewhere_is_left_alone(eroot, tmp_path):
    mine, theirs = tmp_path / "mine", tmp_path / "mine2"  # a prefix, not a parent
    script = (
        f"Set-AlUninstallEntry -InstallLocation {_q(theirs)} -Version '9.9.9'; "
        f"Set-AlUninstallEntry -InstallLocation {_q(mine)} -Version '1.0.0'; "
        "$k = (Get-AlShellPlaces).UninstallKey; "
        "'LOC=' + (Get-ItemProperty -LiteralPath $k).InstallLocation; "
        "'VER=' + (Get-ItemProperty -LiteralPath $k).DisplayVersion; "
        f"Remove-AlUninstallEntry -InstallLocation {_q(mine)}; "
        "'KEPT=' + (Test-Path -LiteralPath $k); "
        f"Remove-AlUninstallEntry -InstallLocation {_q(theirs)}")
    lines = _ok(script, effect_root=eroot)
    assert lines == ["written", "elsewhere", f"LOC={theirs}", "VER=9.9.9", "elsewhere",
                     "KEPT=True", "removed"], lines


@needs_ps
def test_test_al_ours_is_a_full_path_under_check(tmp_path):
    home = str(tmp_path / "AshLight")
    cases = [
        (home, home, True),
        (home + "\\app\\x.exe", home, True),
        (home.lower() + "\\APP", home.upper() + "\\\\", True),
        (home + "2\\x.exe", home, False),
        (home + "\\..\\Other\\x.exe", home, False),
        (str(tmp_path), home, False),
        ("", home, False),
        (home, "", False),
    ]
    script = "; ".join(f"Test-AlOurs -Path {_q(p)} -Root {_q(r)}" for p, r, _ in cases)
    assert _ok(script) == [str(want) for _, _, want in cases]


def test_helper_only_defines_functions_and_stays_per_user():
    text = SHELL.read_text(encoding="ascii")
    for name in ("Set-AlShortcut", "Install-AlShortcuts", "Remove-AlShortcut",
                 "Set-AlUninstallEntry", "Remove-AlUninstallEntry", "Test-AlOurs"):
        assert re.search(r"^function %s\b" % re.escape(name), text, re.MULTILINE), name
    # dot-sourced: top level holds only functions and $script: constants
    body = re.sub(r"<#.*?#>", "", text, flags=re.DOTALL)
    depth = 0
    code_lines = []
    for line in body.splitlines():
        code = line.split("#", 1)[0].rstrip()
        if depth == 0 and code:
            assert code.startswith(("function ", "$script:")), line
        depth += code.count("{") - code.count("}")
        code_lines.append(code)
    assert depth == 0
    code_text = "\n".join(code_lines)
    assert "GetFolderPath('Programs')" in code_text and "GetFolderPath('Desktop')" in code_text
    for banned in ("CommonPrograms", "CommonDesktop", "HKLM", "LocalMachine",
                   "ScheduledTask", "Set-StrictMode", "$ErrorActionPreference"):
        assert banned not in code_text, banned
    assert "AL_SHELL_ROOT" in text and "Software\\AshLightShellScratch" in text
    setup = SETUP.read_text(encoding="ascii")
    assert ". (Join-Path $PSScriptRoot 'al_shell.ps1')" in setup
    assert "function Set-AlShortcut" not in setup and "function Install-AlShortcuts" not in setup
    assert "Install-AlShortcuts -Target $electronExe" in setup and "-OwnerRoot $Repo" in setup
