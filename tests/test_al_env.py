"""REL-RUNTIME-SCRIPTS (F-047, DEP-06): one PowerShell helper for Python and
paths.

scripts/al_env.ps1 is the only place a script finds Python, Electron and the
paths: the private runtime and <payload>/boot.py in an installed copy, PATH
Python and `-m` in a checkout (the twin of server/al/paths.py python_cmd).
The static half reads the scripts; the PowerShell half dot-sources a copy of
al_env.ps1 inside a scratch installed layout whose python.exe is an empty
file (nothing runs it) and the real one in checkout mode. Nothing here
starts the app, the core, the overlay or the loop.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
AL_ENV = SCRIPTS / "al_env.ps1"
DOT_SOURCE = ". (Join-Path $PSScriptRoot 'al_env.ps1')"
# The five scripts that lost their own Python lookup.
USERS = ("run.ps1", "stop.ps1", "setup.ps1", "build.ps1", "autostart.ps1")
# Scripts that run in an installed copy too: no `-m` call site of their own.
INSTALLED_USERS = ("run.ps1", "stop.ps1", "autostart.ps1")
# Scripts outside the package's files that keep a standalone lookup:
# calc_setup.ps1 is the client's one fixed, argument-free spawn (decision
# 0041 amendment 2026-11-20) and resolves the installed runtime itself.
STANDALONE = {"calc_setup.ps1"}
PS51 = shutil.which("powershell.exe") if sys.platform == "win32" else None
needs_ps = pytest.mark.skipif(PS51 is None, reason="Windows PowerShell 5.1 only")

_DEF = re.compile(r"^function\s+Get-AlPython\b", re.IGNORECASE | re.MULTILINE)


def _text(name):
    return (SCRIPTS / name).read_bytes().decode("ascii")


def _code(name):
    """The script's code: no comment-based help block, no # comment line."""
    text = _text(name)
    if text.startswith("<#"):
        text = text.split("\n#>\n", 1)[1]
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def _q(value):
    return "'" + str(value).replace("'", "''") + "'"


def _ps(script, env=None, cwd=None):
    return subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                           "Bypass", "-Command", script],
                          capture_output=True, text=True, timeout=120, env=env,
                          cwd=cwd, stdin=subprocess.DEVNULL)


def _env(**extra):
    env = {k: v for k, v in os.environ.items() if k.upper() != "AL_HOME"}
    env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
    env.update(extra)
    return env


# --- static ---------------------------------------------------------------

def test_exactly_one_get_alpython_and_it_is_in_al_env():
    defs = {p.name: len(_DEF.findall(p.read_bytes().decode("ascii")))
            for p in sorted(SCRIPTS.glob("*.ps1"))}
    owners = {name for name, n in defs.items() if n}
    assert defs["al_env.ps1"] == 1
    assert owners - STANDALONE == {"al_env.ps1"}, sorted(owners)
    for name in ("Get-AlPythonCmd", "Get-AlPaths", "Get-AlElectron", "Invoke-AlPython"):
        assert re.search(r"^function\s+%s\b" % re.escape(name), _text("al_env.ps1"),
                         re.MULTILINE), name


@pytest.mark.parametrize("name", USERS)
def test_every_script_dot_sources_al_env_and_has_no_lookup_of_its_own(name):
    code = _code(name)
    assert DOT_SOURCE in code
    assert not _DEF.search(code)
    assert "@('python', 'py')" not in code
    assert "Get-Command pythonw" not in code
    # the paths come from the helper, never a call of their own
    assert "server.al.paths" not in code
    assert "$paths = Get-AlPaths" in code


@pytest.mark.parametrize("name", INSTALLED_USERS)
def test_installed_scripts_have_no_python_m_call_sites(name):
    # only the help block and comments may quote the old form, plus the
    # checkout default of run.ps1's Get-AlPlan (tests/test_durable_lf.py
    # loads that function alone); the script itself passes Get-AlPythonCmd
    code = _code(name)
    if name == "run.ps1":
        default = "param([string[]]$PlanCmd = @($py, '-m', 'server.al.procs', 'plan'))"
        assert code.count(default) == 1
        code = code.replace(default, "")
        assert ("$plan = Get-AlPlan -PlanCmd (Get-AlPythonCmd -Module 'server.al.procs' "
                "-ArgList @('plan'))") in code
    assert "-m server.al" not in code
    assert "'-m'" not in code
    assert "& $py -m" not in code


@pytest.mark.parametrize("name", ("setup.ps1", "build.ps1"))
def test_checkout_scripts_refuse_an_installed_home_before_any_python(name):
    text = _text(name)
    guard = text.index("if (Get-AlInstallHome) {")
    assert text.index(DOT_SOURCE) < guard < text.index("$py = Get-AlPython")
    assert "throw" in text[guard:guard + 200]


def test_build_package_calls_the_release_build():
    text = _text("build.ps1")
    assert "[switch]$Package" in text
    block = text.split("if ($Package) {", 1)[1].split("\n}\n", 1)[0]
    assert "(Join-Path $Repo 'tools\\release.py'), 'build')" in block
    assert "exit $relRc" in block
    # release.py exits 2 while rel_build is not built; the step passes it on
    assert "$relRc -eq 2" in block
    # the package step comes before the tests and the stamp
    assert text.index("if ($Package) {") < text.index("# TC-SNAP")
    release = (ROOT / "tools" / "release.py").read_text(encoding="ascii")
    assert '"build": "build"' in release


def test_run_passes_the_app_folder_to_electron_never_resources_app():
    text = _text("run.ps1")
    code = _code("run.ps1").lower()
    assert "resources\\app" not in code and "resources/app" not in code
    assert "$appDir = Join-Path $AlEnvRoot 'app'" in text
    assert "$clientArgs = @(Format-AlArgs @($appDir, '--client'))" in text
    assert "$electron = [string](Get-AlElectron)" in text
    starts = [ln for ln in text.splitlines() if "Start-AlDetached -FilePath $electron" in ln]
    assert len(starts) == 1 and "$clientArgs" in starts[0]
    # the client's folder in an installed copy is the payload's app\ too
    assert "node_modules\\electron" not in text.split("$electron = [string]", 1)[1]


def test_al_env_is_ascii_lf_and_mirrors_the_path_resolver():
    raw = AL_ENV.read_bytes()
    raw.decode("ascii")
    assert b"\r" not in raw
    text = raw.decode("ascii")
    # the same mode rule and refusal words as server/al/paths.py
    for word in ("AL_HOME", "install.json", "'app'", "'steamapps'", "'path of exile 2'",
                 "boot.py", "'runtime'", "pythonw.exe", "electron.exe"):
        assert word in text, word
    # no registry, no game folder listing, no process start of its own
    for bad in ("HKLM:", "HKCU:", "Get-ItemProperty", "Start-Process", "Get-ChildItem"):
        assert bad not in text, bad


# --- PowerShell 5.1 -------------------------------------------------------

@needs_ps
@pytest.mark.parametrize("name", ("al_env.ps1",) + USERS)
def test_scripts_parse_in_powershell_51(name):
    r = _ps("$e=$null; [System.Management.Automation.Language.Parser]::ParseFile("
            f"{_q(SCRIPTS / name)}, [ref]$null, [ref]$e) | Out-Null; $e.Count")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "0", (name, r.stdout)


def _installed(tmp_path, marker, files=("python.exe",)):
    home = tmp_path / "AL Home"
    payload = home / "app" / "0.2.0"
    (payload / "scripts").mkdir(parents=True)
    shutil.copyfile(AL_ENV, payload / "scripts" / "al_env.ps1")
    (payload / "boot.py").write_text("# stand-in boot\n", encoding="ascii")
    (home / "install.json").write_text(json.dumps(marker), encoding="ascii")
    rt = home / "runtime" / "py"
    rt.mkdir(parents=True)
    for name in files:
        (rt / name).write_bytes(b"")
    return home, payload


def _call(al_env, body, env=None, cwd=None):
    return _ps(f". {_q(al_env)}\n" + body, env=env or _env(), cwd=cwd)


@needs_ps
def test_installed_layout_gives_the_private_runtime_and_boot_py(tmp_path):
    home, payload = _installed(tmp_path, {"python": "py", "electron": "el"})
    r = _call(payload / "scripts" / "al_env.ps1",
              "'CMD=' + ((Get-AlPythonCmd -Module 'server.al.paths') -join '|')\n"
              "'ARGS=' + ((Get-AlPythonCmd -Module 'server.al' -ArgList @('--port', '8961')) -join '|')\n"
              "'ELECTRON=' + (Get-AlElectron)\n"
              "'ROOT=' + $AlEnvRoot\n"
              "'HOME=' + (Get-AlInstallHome)\n")
    assert r.returncode == 0, r.stdout + r.stderr
    out = dict(ln.split("=", 1) for ln in r.stdout.splitlines() if "=" in ln)
    py = str(home / "runtime" / "py" / "python.exe")
    boot = str(payload / "boot.py")
    assert out["CMD"] == f"{py}|{boot}|server.al.paths"
    assert " ".join(out["CMD"].split("|")) == f"{py} {boot} server.al.paths"
    assert out["ARGS"] == f"{py}|{boot}|server.al|--port|8961"
    assert out["ELECTRON"] == str(home / "runtime" / "el" / "electron.exe")
    assert out["ROOT"] == str(payload)
    assert out["HOME"] == str(home)


@needs_ps
def test_installed_windowless_prefers_pythonw_when_it_is_there(tmp_path):
    home, payload = _installed(tmp_path / "a", {"python": "py"}, ("python.exe", "pythonw.exe"))
    body = "'W=' + (Get-AlPython -Windowless)\n'C=' + (Get-AlPython)\n"
    r = _call(payload / "scripts" / "al_env.ps1", body)
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"W={home / 'runtime' / 'py' / 'pythonw.exe'}" in r.stdout
    assert f"C={home / 'runtime' / 'py' / 'python.exe'}" in r.stdout
    # without pythonw.exe the console runtime stands in
    home, payload = _installed(tmp_path / "b", {"python": "py"})
    r = _call(payload / "scripts" / "al_env.ps1", body)
    assert f"W={home / 'runtime' / 'py' / 'python.exe'}" in r.stdout


@needs_ps
@pytest.mark.parametrize("marker,files,word", [
    ({"python": "..\\x"}, ("python.exe",), "no usable Python runtime"),
    ({"python": ""}, ("python.exe",), "no usable Python runtime"),
    ({"python": 7}, ("python.exe",), "no usable Python runtime"),
    ({}, ("python.exe",), "no usable Python runtime"),
    ({"python": "py"}, (), "private Python runtime is missing"),
])
def test_installed_layout_refuses_a_bad_marker_or_a_missing_runtime(tmp_path, marker, files, word):
    _, payload = _installed(tmp_path, marker, files)
    r = _call(payload / "scripts" / "al_env.ps1",
              "try { Get-AlPython | Out-Null; 'NO-THROW' } catch { 'THREW=' + $_.Exception.Message }\n"
              "'ELECTRON=' + [string](Get-AlElectron)\n")
    assert r.returncode == 0, r.stderr
    assert "NO-THROW" not in r.stdout and word in r.stdout, r.stdout
    # no "electron" key: no Electron path at all, never a guess
    assert "ELECTRON=" in [ln.rstrip() for ln in r.stdout.splitlines()]


@needs_ps
def test_a_home_in_a_steam_library_is_refused_by_path_text(tmp_path):
    bad = tmp_path / "steamapps" / "AshLight"
    r = _call(AL_ENV, "try { Get-AlInstallHome | Out-Null; 'NO-THROW' } "
                      "catch { 'THREW=' + $_.Exception.Message }\n",
              env=_env(AL_HOME=str(bad)))
    assert r.returncode == 0, r.stderr
    assert "THREW=" in r.stdout and "steamapps" in r.stdout
    assert not bad.exists()  # path text only: nothing made, nothing listed


@needs_ps
def test_checkout_form_is_python_dash_m_from_path():
    r = _call(AL_ENV, "'CMD=' + ((Get-AlPythonCmd -Module 'server.al.paths') -join '|')\n"
                      "'HOME=' + [string](Get-AlInstallHome)\n"
                      "'ELECTRON=' + (Get-AlElectron)\n")
    assert r.returncode == 0, r.stdout + r.stderr
    out = dict(ln.split("=", 1) for ln in r.stdout.splitlines() if "=" in ln)
    exe, rest = out["CMD"].split("|", 1)
    assert rest == "-m|server.al.paths"
    assert Path(exe).name.lower() in ("python.exe", "py.exe")
    assert out["HOME"] == ""
    assert out["ELECTRON"] == str(ROOT / "app" / "node_modules" / "electron" / "dist"
                                  / "electron.exe")


@needs_ps
def test_invoke_alpython_flattens_arrays_and_sets_the_exit_code(tmp_path):
    r = _call(AL_ENV, "$a = @('json.tool', '--help')\n"
                      "$x = @(Invoke-AlPython $a); 'RC1=' + $LASTEXITCODE + ' ' + [bool]($x -match 'usage')\n"
                      "$y = @(Invoke-AlPython json.tool '--help'); 'RC2=' + $LASTEXITCODE + ' ' + [bool]($y -match 'usage')\n"
                      "$null = Invoke-AlPython json.tool '--no-such-flag' 2>$null; 'RC3=' + $LASTEXITCODE\n"
                      "'LOC=' + (Get-Location).Path\n", cwd=tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "RC1=0 True" in r.stdout and "RC2=0 True" in r.stdout
    assert "RC3=2" in r.stdout
    assert f"LOC={tmp_path}" in r.stdout  # the caller's folder is restored


@needs_ps
def test_format_alargs_quotes_only_what_needs_it():
    r = _call(AL_ENV, "(Format-AlArgs @('a b', '', 'c', 'd\"e')) -join '|'\n")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == '"a b"|""|c|"d\\"e"'
