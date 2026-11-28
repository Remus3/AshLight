"""DEP-09: scripts/install.ps1, the bootstrap of the one pasted line.

Run cases (Windows PowerShell 5.1, a local fake release folder, a runner
script in place of the real hand-over, no network): the script verifies
release.json, the app zip and the pinned CPython zip against their hashes
and hands over to '<python> boot.py server.al.install install' with the
-Zip / -RuntimeDir / -InstallDir / -NoStart choices; a tampered zip or a
missing hash line stops before any extract; AL_INSTALL_DIR is honoured in
piped use and a piped run never exits the caller's window.

Static cases: every web call passes the 'AshLight/<ver> (installer)'
User-Agent and basic parsing with no cookie or web session; only the four
allowed hosts appear; no elevation call; no game folder path outside the
path-shape guard; no registry read; no ExecutionPolicy change outside the
process.
"""
import base64
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install.ps1"
PS51 = shutil.which("powershell.exe") if sys.platform == "win32" else None
needs_ps = pytest.mark.skipif(PS51 is None, reason="Windows PowerShell 5.1 only")

VERSION = "1.2.3"
APP_ZIP = f"AshLight-{VERSION}-app.zip"
PY_FILE = "python-3.14.10-embed-amd64.zip"
PY_URL = f"https://www.python.org/ftp/python/3.14.10/{PY_FILE}"
HOSTS = {"github.com", "release-assets.githubusercontent.com",
         "objects.githubusercontent.com", "www.python.org"}
WEB_CMDS = {"invoke-webrequest", "iwr", "invoke-restmethod", "irm", "curl",
            "wget", "start-bitstransfer", "new-webserviceproxy"}


# --- the fake release ------------------------------------------------------

def _zip(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in sorted(entries.items()):
            zf.writestr(name, data)
    return buf.getvalue()


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def make_release(base, sums_skip=()):
    """A release folder (app zip, release.json, SHA256SUMS.txt) and a
    runtime folder holding a stand-in CPython zip. Returns the paths."""
    rel = base / "release"
    rt = base / "runtimes"
    rel.mkdir(parents=True)
    rt.mkdir(parents=True)
    top = f"AshLight-{VERSION}/"
    app = _zip({top + "boot.py": "# stand-in boot\n",
                top + "server/al/__init__.py": f'VERSION = "{VERSION}"\n',
                top + "MANIFEST.json": "{}\n"})
    py = _zip({"python.exe": "stand-in\n", "python314._pth": "python314.zip\n.\n"})
    (rel / APP_ZIP).write_bytes(app)
    (rt / PY_FILE).write_bytes(py)
    doc = {"name": "AshLight", "version": VERSION, "schema": 1,
           "bootstrap_protocol": 1, "channel": "stable",
           "runtimes": {
               "python": {"version": "3.14.10", "file": PY_FILE, "url": PY_URL,
                          "sha256": _sha(py), "size": len(py), "licence": "PSF-2.0"},
               "electron": {"version": "45.3.3", "file": "electron-v45.3.3-win32-x64.zip",
                            "url": "https://github.com/electron/electron/releases/download/"
                                   "v45.3.3/electron-v45.3.3-win32-x64.zip",
                            "sha256": "0" * 64, "size": 1, "licence": "MIT"}},
           "assets": [{"name": APP_ZIP, "sha256": _sha(app), "size": len(app)}]}
    release = (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode("ascii")
    (rel / "release.json").write_bytes(release)
    files = {APP_ZIP: app, "release.json": release}
    sums = "".join(f"{_sha(files[n])}  {n}\n" for n in sorted(files)
                   if n not in sums_skip)
    (rel / "SHA256SUMS.txt").write_bytes(sums.encode("ascii"))
    return {"rel": rel, "zip": rel / APP_ZIP, "rt": rt, "py": rt / PY_FILE}


def make_runner(base, code=0):
    """A runner script: records its arguments (and whether the python and
    boot.py it was handed exist) and exits with code."""
    record = base / "handover.json"
    runner = base / "runner.ps1"
    runner.write_text(
        "$rec = @{ argv = @($args); python = (Test-Path -LiteralPath $args[0]);\n"
        "          boot = (Test-Path -LiteralPath $args[1]) }\n"
        f"$rec | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath '{record}' -Encoding ASCII\n"
        f"exit {code}\n", encoding="ascii", newline="\n")
    return runner, record


def _env(extra=None):
    env = {k: v for k, v in os.environ.items() if k.upper() != "AL_INSTALL_DIR"}
    env.update(extra or {})
    return env


def run_file(*args, env=None):
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                        "Bypass", "-File", str(SCRIPT), *map(str, args)],
                       capture_output=True, text=True, timeout=120, env=_env(env))
    return r.returncode, r.stdout + r.stderr


def run_command(command, env=None):
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                        "Bypass", "-Command", command],
                       capture_output=True, text=True, timeout=120, env=_env(env))
    return r.returncode, r.stdout + r.stderr


def code_text():
    """The script without its comments (the <# #> block and the full-line
    '#' comments; the script has no trailing comments)."""
    text = re.sub(r"(?s)<#.*?#>", "", SCRIPT.read_text(encoding="ascii"))
    return "\n".join(ln for ln in text.split("\n") if not ln.lstrip().startswith("#"))


def stage_of(home):
    return home / "temp" / f"bootstrap-{VERSION}"


# --- parse -----------------------------------------------------------------

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
    $els = @($c.CommandElements | ForEach-Object { $_.Extent.Text }) -join "`n"
    'CMD ' + $name.ToLowerInvariant() + ' ' + $fn + ' ' + [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($els))
}
$fns = $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true)
foreach ($f in $fns) { 'FN ' + $f.Name + ' ' + [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($f.Body.Extent.Text)) }
"""


@pytest.fixture(scope="module")
def ast(tmp_path_factory):
    if PS51 is None:
        pytest.skip("Windows PowerShell 5.1 only")
    helper = tmp_path_factory.mktemp("ast") / "dump.ps1"
    helper.write_text(_AST_DUMP, encoding="ascii")
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                        "-File", str(helper), str(SCRIPT)], capture_output=True, text=True,
                       timeout=120)
    assert r.returncode == 0, r.stderr
    lines = r.stdout.splitlines()
    cmds, fns = [], {}
    for ln in lines:
        if ln.startswith("CMD "):
            _, name, fn, b64 = ln.split(" ", 3)
            cmds.append((name, fn, base64.b64decode(b64).decode("utf-8").split("\n")))
        elif ln.startswith("FN "):
            _, name, b64 = ln.split(" ", 2)
            fns[name] = base64.b64decode(b64).decode("utf-8")
    return {"errors": [ln for ln in lines if ln.startswith("ERROR ")],
            "cmds": cmds, "fns": fns}


def test_parses_with_powershell_5_1(ast):
    assert ast["errors"] == []
    assert ast["cmds"] and "Invoke-AlBootstrap" in ast["fns"]


def test_script_is_ascii_lf_and_self_contained():
    data = SCRIPT.read_bytes()
    assert all(b < 128 for b in data) and b"\r" not in data
    text = data.decode("ascii")
    # no dot-sourcing and no module import: it runs before any payload exists
    assert not re.search(r"(?m)^\s*\.\s+\S", text)
    assert "Import-Module" not in text and "al_env.ps1" not in text


# --- the hand-over from a local fake release ---------------------------------

@needs_ps
def test_verifies_and_hands_over_to_the_installer(tmp_path):
    rel = make_release(tmp_path)
    runner, record = make_runner(tmp_path)
    home = tmp_path / "Programs" / "AshLight"
    code, out = run_file("-Zip", rel["zip"], "-RuntimeDir", rel["rt"], "-InstallDir", home,
                         "-NoStart", "-Runner", runner)
    assert code == 0, out
    rec = json.loads(record.read_text(encoding="ascii"))
    stage = stage_of(home)
    assert rec["argv"] == [
        str(stage / "python" / "python.exe"),
        str(stage / "app" / f"AshLight-{VERSION}" / "boot.py"),
        "server.al.install", "install", "--zip", str(rel["zip"]), "--home", str(home),
        "--runtime-dir", str(rel["rt"]), "--no-start"]
    # the verified bytes were unpacked before the hand-over ...
    assert rec["python"] is True and rec["boot"] is True
    # ... and the bootstrap folder is gone after it
    assert not stage.exists()
    assert "verified " + APP_ZIP in out and "verified " + PY_FILE in out


@needs_ps
def test_a_finished_install_prints_the_sums_file_sha256(tmp_path):
    # REL-INSTALL-SUMS-PRINT (research 0066 F6): a second hash source a
    # careful player can compare with the release page
    rel = make_release(tmp_path)
    runner, _record = make_runner(tmp_path)
    home = tmp_path / "h"
    code, out = run_file("-Zip", rel["zip"], "-RuntimeDir", rel["rt"], "-InstallDir", home,
                         "-NoStart", "-Runner", runner)
    assert code == 0, out
    want = _sha((rel["rel"] / "SHA256SUMS.txt").read_bytes())
    line = ("AshLight installer: SHA-256 of SHA256SUMS.txt: " + want
            + " (the release page lists the same value)")
    assert line in out.splitlines()
    assert out.index(line) < out.index("AshLight installer: done")
    # a failed hand-over prints no hash: nothing was installed to compare
    (tmp_path / "x").mkdir()
    runner7, _ = make_runner(tmp_path / "x", code=7)
    code, out = run_file("-Zip", rel["zip"], "-RuntimeDir", rel["rt"], "-InstallDir",
                         tmp_path / "h2", "-NoStart", "-Runner", runner7)
    assert code == 7 and want not in out


@needs_ps
def test_without_no_start_the_flag_is_not_passed(tmp_path):
    rel = make_release(tmp_path)
    runner, record = make_runner(tmp_path)
    home = tmp_path / "h"
    code, out = run_file("-Zip", rel["zip"], "-RuntimeDir", rel["rt"], "-InstallDir", home,
                         "-Runner", runner)
    assert code == 0, out
    argv = json.loads(record.read_text(encoding="ascii"))["argv"]
    assert "--no-start" not in argv
    assert argv[2:4] == ["server.al.install", "install"]


@needs_ps
def test_the_installer_exit_code_is_passed_on(tmp_path):
    rel = make_release(tmp_path)
    runner, record = make_runner(tmp_path, code=7)
    home = tmp_path / "h"
    code, out = run_file("-Zip", rel["zip"], "-RuntimeDir", rel["rt"], "-InstallDir", home,
                         "-NoStart", "-Runner", runner)
    assert code == 7, out
    assert record.is_file()
    assert "last-install.json" in out


def _assert_stopped_before_extract(code, out, record, home, needle):
    assert code == 1, out
    assert needle in out, out
    assert not record.exists()                       # no hand-over
    stage = stage_of(home)
    assert not (stage / "python").exists() and not (stage / "app").exists()


@needs_ps
def test_a_tampered_zip_stops_before_any_extract(tmp_path):
    rel = make_release(tmp_path)
    data = bytearray(rel["zip"].read_bytes())
    data[-30] ^= 0xFF
    rel["zip"].write_bytes(bytes(data))
    runner, record = make_runner(tmp_path)
    home = tmp_path / "h"
    code, out = run_file("-Zip", rel["zip"], "-RuntimeDir", rel["rt"], "-InstallDir", home,
                         "-NoStart", "-Runner", runner)
    _assert_stopped_before_extract(code, out, record, home,
                                   APP_ZIP + " does not match its SHA256SUMS.txt line")


@needs_ps
def test_a_missing_zip_hash_line_stops_before_any_extract(tmp_path):
    rel = make_release(tmp_path, sums_skip=(APP_ZIP,))
    runner, record = make_runner(tmp_path)
    home = tmp_path / "h"
    code, out = run_file("-Zip", rel["zip"], "-RuntimeDir", rel["rt"], "-InstallDir", home,
                         "-NoStart", "-Runner", runner)
    _assert_stopped_before_extract(code, out, record, home,
                                   "SHA256SUMS.txt has no single line for " + APP_ZIP)


@needs_ps
def test_a_release_json_without_a_hash_line_stops(tmp_path):
    rel = make_release(tmp_path, sums_skip=("release.json",))
    runner, record = make_runner(tmp_path)
    home = tmp_path / "h"
    code, out = run_file("-Zip", rel["zip"], "-RuntimeDir", rel["rt"], "-InstallDir", home,
                         "-NoStart", "-Runner", runner)
    _assert_stopped_before_extract(code, out, record, home,
                                   "SHA256SUMS.txt has no single line for release.json")


@needs_ps
def test_a_cpython_zip_off_its_pin_stops_before_any_extract(tmp_path):
    rel = make_release(tmp_path)
    data = rel["py"].read_bytes()
    rel["py"].write_bytes(data[:-1] + bytes([data[-1] ^ 0xFF]))
    runner, record = make_runner(tmp_path)
    home = tmp_path / "h"
    code, out = run_file("-Zip", rel["zip"], "-RuntimeDir", rel["rt"], "-InstallDir", home,
                         "-NoStart", "-Runner", runner)
    _assert_stopped_before_extract(code, out, record, home,
                                   PY_FILE + " does not match its pinned SHA-256")


@needs_ps
def test_a_game_folder_home_is_refused_before_anything_is_written(tmp_path):
    rel = make_release(tmp_path)
    runner, record = make_runner(tmp_path)
    for home in (tmp_path / "steamapps" / "common" / "AshLight",
                 tmp_path / "Path of Exile 2" / "AshLight"):
        code, out = run_file("-Zip", rel["zip"], "-RuntimeDir", rel["rt"], "-InstallDir", home,
                             "-NoStart", "-Runner", runner)
        assert code == 2, out
        assert "refused: the install home may not lie in a" in out
        assert not home.exists() and not record.exists()


@needs_ps
def test_an_unstamped_script_needs_zip_and_fetches_nothing(tmp_path):
    home = tmp_path / "h"
    code, out = run_file("-InstallDir", home, "-NoStart")
    assert code == 2, out
    assert "not from a release" in out
    assert not home.exists()


# --- piped use ---------------------------------------------------------------

@needs_ps
def test_piped_use_honours_al_install_dir_and_never_exits_the_window(tmp_path):
    # the real pipe (Get-Content | iex, as irm | iex): the home guard reads
    # AL_INSTALL_DIR and refuses before any request; the caller keeps running
    bad = tmp_path / "steamapps" / "common" / "AshLight"
    cmd = (f"Get-Content -Raw -LiteralPath '{SCRIPT}' | Invoke-Expression; "
           "'AFTER ' + $LASTEXITCODE")
    code, out = run_command(cmd, env={"AL_INSTALL_DIR": str(bad)})
    assert code == 0, out
    assert "refused: the install home may not lie in a 'steamapps' folder" in out
    assert "AFTER 2" in out
    assert not bad.exists()


@needs_ps
def test_piped_use_hands_over_with_the_al_install_dir_home(tmp_path):
    rel = make_release(tmp_path)
    runner, record = make_runner(tmp_path)
    home = tmp_path / "Piped" / "AshLight"
    cmd = (f"$t = Get-Content -Raw -LiteralPath '{SCRIPT}'; "
           f"& ([scriptblock]::Create($t)) -Zip '{rel['zip']}' -RuntimeDir '{rel['rt']}' "
           f"-NoStart -Runner '{runner}'; 'AFTER ' + $LASTEXITCODE")
    code, out = run_command(cmd, env={"AL_INSTALL_DIR": str(home)})
    assert code == 0, out
    assert "AFTER 0" in out
    argv = json.loads(record.read_text(encoding="ascii"))["argv"]
    assert argv[argv.index("--home") + 1] == str(home)


@needs_ps
def test_install_dir_wins_over_al_install_dir(tmp_path):
    rel = make_release(tmp_path)
    runner, record = make_runner(tmp_path)
    home = tmp_path / "Given"
    code, out = run_file("-Zip", rel["zip"], "-RuntimeDir", rel["rt"], "-InstallDir", home,
                         "-NoStart", "-Runner", runner,
                         env={"AL_INSTALL_DIR": str(tmp_path / "steamapps" / "x")})
    assert code == 0, out
    argv = json.loads(record.read_text(encoding="ascii"))["argv"]
    assert argv[argv.index("--home") + 1] == str(home)


# --- static: requests, hosts, elevation, game folder, policy ----------------

def test_every_web_call_passes_the_installer_user_agent(ast):
    calls = [(n, fn, els) for n, fn, els in ast["cmds"] if n in WEB_CMDS]
    assert calls, "the bootstrap fetches the release files"
    for name, fn, els in calls:
        params = {e.lower() for e in els if e.startswith("-")}
        assert "-useragent" in params, (name, fn)
        assert "-usebasicparsing" in params, (name, fn)
        for banned in ("-sessionvariable", "-websession", "-headers",
                       "-credential", "-usedefaultcredentials", "-proxyusedefaultcredentials"):
            assert banned not in params, (name, banned)
        # the one web call site, which checks every hop against the hosts
        assert fn == "Get-AlDownload", fn
    # its User-Agent argument comes from Get-AlUserAgent at every call site
    ua_fn = ast["fns"]["Get-AlUserAgent"]
    assert "'AshLight/' + $Version + ' (installer)'" in ua_fn
    downloads = [els for n, _fn, els in ast["cmds"] if n == "get-aldownload"]
    assert downloads
    for els in downloads:
        assert els[3] == "$ua" or els[3].startswith("(Get-AlUserAgent "), els
    text = code_text()
    assert "$ua = Get-AlUserAgent $version" in text
    # no other request route and no cookie
    for word in ("WebClient", "HttpWebRequest", "HttpClient", "DownloadString",
                 "DownloadFile", "BitsTransfer", "Net.Sockets", "Cookie", "POESESSID",
                 "Invoke-Expression"):
        assert word.lower() not in text.lower(), word


def test_only_the_allowed_hosts_appear():
    text = SCRIPT.read_text(encoding="ascii")
    found = set(m.lower() for m in re.findall(r"https?://([^/\s'\"<>)]+)", text))
    assert found and found <= HOSTS, found - HOSTS
    assert "http://" not in text
    m = re.search(r"\$AlHosts = @\(([^)]*)\)", text)
    assert set(re.findall(r"'([^']+)'", m.group(1))) == HOSTS


def test_the_repository_default_is_the_public_address():
    repo = json.loads((ROOT / "config" / "public_repo.json").read_text(encoding="utf-8"))["repo"]
    assert f"$AlRepo = '{repo}'" in SCRIPT.read_text(encoding="ascii")


def test_no_elevation_call(ast):
    text = SCRIPT.read_text(encoding="ascii")
    assert not re.search(r"runas", text, re.I)
    assert not re.search(r"-Verb\b", text, re.I)
    names = {n for n, _fn, _els in ast["cmds"]}
    assert not names & {"start-process", "saps", "start", "invoke-command", "icm",
                        "new-pssession", "enter-pssession", "set-executionpolicy"}


def test_no_game_folder_path_outside_the_shape_guard(ast):
    text = code_text().lower()
    guard = ast["fns"]["Get-AlHomeRefusal"].lower()
    for word in ("steamapps", "path of exile"):
        assert text.count(word) == guard.count(word) >= 1, word
    for word in ("client.txt", "hklm", "hkcu", "registry", "get-itemproperty",
                 "microsoft.win32", "reg.exe", "get-process", "get-ciminstance",
                 "get-wmiobject", "libraryfolders"):
        assert word not in text, word


def test_no_execution_policy_change_outside_the_process(ast):
    for name, _fn, els in ast["cmds"]:
        if name == "set-executionpolicy":
            joined = " ".join(els).lower()
            assert "-scope process" in joined, els


def test_release_build_stamps_the_version_in():
    spec = importlib.util.spec_from_file_location("rel_assets_t", ROOT / "tools" / "rel_assets.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = mod.stamp_installer(SCRIPT.read_bytes(), VERSION).decode("ascii")
    assert mod.VERSION_TOKEN not in out
    assert f"$AlVersion = '{VERSION}'" in out
