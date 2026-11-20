"""OVL-ELECTRON-PIN: pin equals app/package.json, exe verify, zip hash refused
before unpack, AshLight User-Agent on the fetch, unknown arch warns. No
network: the fetch test uses a loopback mock server, the rest fakes.

OVL-ELECTRON-SETUP (decision 0068): scripts/setup.ps1 never names
electron's install.js, clears the install override variables before npm
and fetches the binary only through tools/electron_pin.py; with
electron_use_remote_checksums=1 (and the mirror / dist-path overrides) in
the environment the pin still decides; setup verifies electron.exe after
the install and on the up-to-date fast path; run.ps1 runs verify-exe before
the client start. The PowerShell checks run the scripts' own functions
(cut out by the 5.1 parser) against a fake tools/electron_pin.py: no npm,
no download, no Electron."""

import hashlib
import http.server
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import electron_pin  # noqa: E402

from server.al import paths, webfetch  # noqa: E402

VER = "45.3.3"
EXE = b"MZ fake electron exe " * 64


def _zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _spec(blob, exe=EXE, arch="x64"):
    name = f"electron-v{VER}-win32-{arch}.zip"
    return {
        "zip_name": name,
        "zip_url": f"https://github.com/electron/electron/releases/download/v{VER}/{name}",
        "zip_sha256": hashlib.sha256(blob).hexdigest(), "zip_size": len(blob),
        "exe_sha256": hashlib.sha256(exe).hexdigest(), "exe_size": len(exe),
    }


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv(paths.SIDECAR_ENV, str(tmp_path / "sidecar"))
    blob = _zip({"electron.exe": EXE, "resources/default_app.asar": b"x",
                 "locales/en-US.pak": b"y"})
    app = tmp_path / "app"
    pkg = app / "node_modules" / "electron"
    pkg.mkdir(parents=True)
    (pkg / "package.json").write_text('{"name": "electron"}', encoding="ascii")
    pin = {"schema": 1, "version": VER, "eol": "2027-04-27", "verified": "2026-11-19",
           "arch": {"x64": _spec(blob)}}
    pin_path = tmp_path / "electron_pin.json"
    pin_path.write_text(json.dumps(pin), encoding="ascii")
    return {"tmp": tmp_path, "blob": blob, "app": app, "pkg": pkg, "pin": pin,
            "pin_path": pin_path}


def _fake_fetch(blob, calls):
    def fetch(url, max_bytes):
        calls.append(url)
        yield blob[: len(blob) // 2]
        yield blob[len(blob) // 2:]
    return fetch


# --- the tracked pin ----------------------------------------------------

def test_pin_version_equals_package_json():
    doc = electron_pin.load_pin()
    pkg = json.loads((ROOT / "app" / "package.json").read_text(encoding="utf-8"))
    deps = {}
    deps.update(pkg.get("devDependencies") or {})
    deps.update(pkg.get("dependencies") or {})
    assert doc["version"] == deps["electron"]
    assert set(doc["arch"]) == {"x64", "arm64"}
    for spec in doc["arch"].values():
        assert spec["zip_url"].startswith("https://github.com/electron/electron/releases/")


def test_version_drift_from_package_json_is_refused(world):
    other = world["tmp"] / "package.json"
    other.write_text(json.dumps({"dependencies": {"electron": "46.0.0"}}), encoding="utf-8")
    with pytest.raises(electron_pin.PinError, match="differs from app/package.json"):
        electron_pin.load_pin(world["pin_path"], package_json=other)


def test_malformed_pin_is_refused(world):
    bad = dict(world["pin"])
    bad["arch"] = {"x64": dict(world["pin"]["arch"]["x64"], exe_sha256="nope")}
    world["pin_path"].write_text(json.dumps(bad), encoding="ascii")
    rc, _ = electron_pin.run("check", pin_path=world["pin_path"], package_json=False)
    assert rc == electron_pin.RC_REFUSED


# --- verify-exe ---------------------------------------------------------

def test_one_byte_change_in_a_copy_of_the_exe_fails_verify(world):
    spec = world["pin"]["arch"]["x64"]
    exe = world["tmp"] / "copy" / "electron.exe"
    exe.parent.mkdir()
    exe.write_bytes(EXE)
    assert electron_pin.verify_exe(spec, exe) is True
    assert electron_pin.verify_exe(spec, exe) is False  # unchanged: no full hash
    bad = bytearray(EXE)
    bad[100] ^= 1
    old = exe.stat().st_mtime_ns
    exe.write_bytes(bytes(bad))
    os.utime(exe, ns=(old + 2_000_000_000, old + 2_000_000_000))
    with pytest.raises(electron_pin.ExeMismatch):
        electron_pin.verify_exe(spec, exe)
    rc, _ = electron_pin.run("verify-exe", arch="x64", exe=exe,
                             pin_path=world["pin_path"], package_json=False)
    assert rc == electron_pin.RC_REFUSED


def test_verify_record_lives_in_the_sidecar_build_dir(world):
    assert electron_pin.check_file() == paths.sidecar_dir("Build") / "electron-exe-check.json"
    assert electron_pin.cache_dir() == paths.sidecar_dir("Cache") / "electron"


# --- fetch and unpack ---------------------------------------------------

def test_setup_fetches_unpacks_and_writes_path_txt(world):
    calls = []
    rc, client = electron_pin.run("setup", arch="x64", app_dir=world["app"],
                                  pin_path=world["pin_path"], package_json=False,
                                  fetch=_fake_fetch(world["blob"], calls))
    assert (rc, client) == (electron_pin.RC_OK, True)
    assert len(calls) == 1
    assert (world["pkg"] / "dist" / "electron.exe").read_bytes() == EXE
    assert (world["pkg"] / "path.txt").read_bytes() == b"electron.exe"
    rc, _ = electron_pin.run("setup", arch="x64", app_dir=world["app"],
                             pin_path=world["pin_path"], package_json=False,
                             fetch=_fake_fetch(world["blob"], calls))
    assert rc == electron_pin.RC_OK and len(calls) == 1  # cached zip, no refetch


def test_wrong_zip_hash_is_refused_before_unpack(world, monkeypatch):
    unpacked = []
    monkeypatch.setattr(electron_pin, "unpack", lambda *a, **k: unpacked.append(a))
    evil = _zip({"electron.exe": b"X" * len(EXE)})
    calls = []
    rc, _ = electron_pin.run("setup", arch="x64", app_dir=world["app"],
                             pin_path=world["pin_path"], package_json=False,
                             fetch=_fake_fetch(evil + b"\0" * (len(world["blob"]) - len(evil)),
                                               calls))
    assert rc == electron_pin.RC_REFUSED
    assert unpacked == []
    assert not (world["pkg"] / "dist").exists()
    assert not (world["pkg"] / "path.txt").exists()
    rejected = list(electron_pin.cache_dir().glob("*.rejected"))
    assert len(rejected) == 1


def test_exe_not_matching_pin_after_unpack_is_refused(world):
    other = _zip({"electron.exe": b"Y" * len(EXE)})
    pin = dict(world["pin"])
    pin["arch"] = {"x64": dict(_spec(other), exe_sha256=world["pin"]["arch"]["x64"]["exe_sha256"])}
    world["pin_path"].write_text(json.dumps(pin), encoding="ascii")
    rc, _ = electron_pin.run("setup", arch="x64", app_dir=world["app"],
                             pin_path=world["pin_path"], package_json=False,
                             fetch=_fake_fetch(other, []))
    assert rc == electron_pin.RC_REFUSED
    assert not (world["pkg"] / "dist").exists()
    assert not (world["pkg"] / ".dist.tmp").exists()


@pytest.mark.parametrize("member", ["../evil.dll", "/abs.dll", "Z" + ":" + "/x.dll", "a/../../b.dll"])
def test_unsafe_zip_member_is_refused(member):
    with zipfile.ZipFile(io.BytesIO(_zip({member: b"z"}))) as zf:
        with pytest.raises(electron_pin.UnsafeArchive):
            electron_pin.check_members(zf)


def test_symlink_zip_member_is_refused():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        info = zipfile.ZipInfo("link.dll")
        info.external_attr = (0o120777 << 16)
        zf.writestr(info, "electron.exe")
    with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as zf:
        with pytest.raises(electron_pin.UnsafeArchive):
            electron_pin.check_members(zf)


def test_fetch_sends_the_ashlight_user_agent():
    seen = []
    body = b"electron zip bytes" * 100

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            seen.append(dict(self.headers))
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = http.server.HTTPServer(("127.0.0.1", port), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        got = b"".join(electron_pin.http_stream(
            f"http://127.0.0.1:{port}/electron.zip", len(body),
            check=lambda url, hosts: None))
    finally:
        srv.shutdown()
        srv.server_close()
    assert got == body
    ua = seen[0].get("User-Agent", "")
    assert ua == webfetch.user_agent(electron_pin.UA_PURPOSE)
    assert ua.startswith("AshLight/")
    assert "Cookie" not in seen[0]


def test_default_check_refuses_plain_http_and_foreign_hosts():
    with pytest.raises(webfetch.UrlNotAllowed):
        next(electron_pin.http_stream("http://github.com/x.zip", 10))
    with pytest.raises(webfetch.UrlNotAllowed):
        next(electron_pin.http_stream("https://example.com/x.zip", 10))


# --- architecture -------------------------------------------------------

def test_unknown_arch_warns_and_reports_no_client(world, capsys, monkeypatch):
    monkeypatch.setattr(electron_pin.platform, "machine", lambda: "ia64")
    assert electron_pin.machine_arch() is None
    calls = []
    rc, client = electron_pin.run("setup", app_dir=world["app"], pin_path=world["pin_path"],
                                  package_json=False, fetch=_fake_fetch(world["blob"], calls))
    assert (rc, client) == (electron_pin.RC_OK, False)
    assert calls == []
    assert "no client" in capsys.readouterr().out
    # arm64 is a known arch, but this test pin carries only x64.
    rc, client = electron_pin.run("setup", arch="arm64", app_dir=world["app"],
                                  pin_path=world["pin_path"], package_json=False)
    assert (rc, client) == (electron_pin.RC_OK, False)


def test_machine_arch_names():
    assert electron_pin.machine_arch("AMD64") == "x64"
    assert electron_pin.machine_arch("ARM64") == "arm64"
    assert electron_pin.machine_arch("x86") is None


# --- OVL-ELECTRON-SETUP: setup.ps1 and run.ps1 --------------------------

SETUP_PS1 = ROOT / "scripts" / "setup.ps1"
RUN_PS1 = ROOT / "scripts" / "run.ps1"
PS51 = shutil.which("powershell.exe") if sys.platform == "win32" else None

# Every override the package notes and research 0046 R4 name.
OVERRIDES = (
    "electron_use_remote_checksums", "ELECTRON_USE_REMOTE_CHECKSUMS",
    "npm_config_electron_use_remote_checksums",
    "ELECTRON_MIRROR", "npm_config_electron_mirror", "ELECTRON_NIGHTLY_MIRROR",
    "ELECTRON_CUSTOM_DIR", "ELECTRON_CUSTOM_FILENAME", "ELECTRON_CUSTOM_VERSION",
    "ELECTRON_OVERRIDE_DIST_PATH", "ELECTRON_INSTALL_PLATFORM", "ELECTRON_INSTALL_ARCH",
    "electron_config_cache", "force_no_cache",
)


def _text(path):
    return path.read_bytes().decode("ascii")


def _ps_str(value):
    return "'" + str(value).replace("'", "''") + "'"


def _ps_funcs(script, names, body, env=None):
    """Run `body` in Windows PowerShell 5.1 after defining the named
    functions of `script` (cut out by the 5.1 parser; nothing else of the
    script runs). Returns the stdout lines."""
    quoted = ", ".join(_ps_str(n) for n in names)
    prog = (
        "$ErrorActionPreference = 'Stop'\n"
        "Set-StrictMode -Version 2\n"
        "$__names = @(" + quoted + ")\n"
        "$__ast = [System.Management.Automation.Language.Parser]::ParseFile("
        + _ps_str(script) + ", [ref]$null, [ref]$null)\n"
        "$__fns = $__ast.FindAll({ param($n) $n -is "
        "[System.Management.Automation.Language.FunctionDefinitionAst] -and "
        "$__names -contains $n.Name }, $true)\n"
        "if (@($__fns).Count -ne $__names.Count) { throw 'function missing' }\n"
        "foreach ($__f in $__fns) { . ([scriptblock]::Create($__f.Extent.Text)) }\n"
        + body)
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                        "-Command", prog], capture_output=True, text=True, timeout=90,
                       env=env if env is not None else dict(os.environ))
    assert r.returncode == 0, r.stdout + r.stderr
    return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]


def _fake_repo(tmp_path):
    """A repo root whose tools/electron_pin.py only prints FAKE_OUT, records
    its argv and exits FAKE_RC (no pin, no download, no exe)."""
    repo = tmp_path / "repo"
    (repo / "tools").mkdir(parents=True)
    (repo / "tools" / "electron_pin.py").write_text(
        "import os, sys\n"
        "with open(os.environ['FAKE_ARGV'], 'a') as fh:\n"
        "    fh.write(' '.join(sys.argv[1:]) + '\\n')\n"
        "for line in os.environ.get('FAKE_OUT', '').split('|'):\n"
        "    print(line)\n"
        "sys.exit(int(os.environ['FAKE_RC']))\n", encoding="ascii")
    return repo


def test_setup_never_names_electron_install_js():
    text = _text(SETUP_PS1)
    assert "install.js" not in text.lower()
    assert not re.search(r"node_modules\\electron\\install", text, re.I)
    # the one Electron fetch route is AshLight's own tool, after npm ci
    i = text.index("'npm.cmd'")
    j = text.index("Assert-AlElectronPin (Invoke-AlElectronPin 'setup')")
    assert i < j
    assert "'tools\\electron_pin.py'" in text


def test_setup_clears_the_override_variables_before_npm():
    text = _text(SETUP_PS1)
    start = text.index("function Clear-AlElectronOverrides {")
    body = text[start:text.index("\n}\n", start)]
    for name in OVERRIDES:
        assert "'" + name + "'" in body, name
    call = text.index("\nClear-AlElectronOverrides\n")
    assert call < text.index("'npm.cmd'")
    assert call < text.index("Invoke-AlElectronPin 'setup'")
    # the old cache steer for electron's installer is gone, not re-set
    assert "$env:electron_config_cache" not in text


def test_setup_verifies_the_exe_after_install_and_on_the_fast_path():
    text = _text(SETUP_PS1)
    fast = text.index("if ($upToDate -and -not $Force) {")
    block = text[fast:text.index("\n}\n", fast)]
    assert block.index("Invoke-AlElectronPin 'verify-exe'") < block.index("up to date (no-op)")
    assert "exit 0" in block[block.index("if ($verifyRc -eq 0) {"):]
    tail = text[text.index("Invoke-AlElectronPin 'setup'"):]
    assert "Assert-AlElectronPin (Invoke-AlElectronPin 'verify-exe')" in tail
    assert tail.index("verify-exe") < tail.index("Set-Content -Path $stamp")
    assert "run setup again" in text  # a failed check names the fix


def test_run_verifies_the_exe_before_the_client_start():
    text = _text(RUN_PS1)
    assert "function Test-AlElectronExe {" in text
    assert "'verify-exe'" in text and "'tools\\electron_pin.py'" in text
    gate = text.index("} elseif (-not (Test-AlElectronExe)) {")
    start = text.index("Start-AlDetached -FilePath $electron")
    assert gate < start
    refused = text[gate:text.index("} else {", gate)]
    assert "Start-AlDetached" not in refused
    assert "setup.ps1 again" in refused


def test_override_environment_cannot_steer_the_pinned_fetch(world, monkeypatch):
    """electron_use_remote_checksums=1, a mirror and a dist override in the
    environment: the fetch still goes to the pinned URL, the wrong zip is
    still refused, the right one still lands in the app's own dist."""
    elsewhere = world["tmp"] / "elsewhere"
    monkeypatch.setenv("electron_use_remote_checksums", "1")
    monkeypatch.setenv("npm_config_electron_use_remote_checksums", "1")
    monkeypatch.setenv("ELECTRON_MIRROR", "https://example.com/mirror/")
    monkeypatch.setenv("ELECTRON_OVERRIDE_DIST_PATH", str(elsewhere))
    monkeypatch.setenv("ELECTRON_INSTALL_ARCH", "arm64")
    monkeypatch.setenv("force_no_cache", "true")
    evil = _zip({"electron.exe": b"X" * len(EXE)})
    calls = []
    rc, _ = electron_pin.run("setup", arch="x64", app_dir=world["app"],
                             pin_path=world["pin_path"], package_json=False,
                             fetch=_fake_fetch(evil + b"\0" * (len(world["blob"]) - len(evil)),
                                               calls))
    assert rc == electron_pin.RC_REFUSED
    assert not (world["pkg"] / "dist").exists()
    assert calls == [world["pin"]["arch"]["x64"]["zip_url"]]
    calls = []
    rc, client = electron_pin.run("setup", arch="x64", app_dir=world["app"],
                                  pin_path=world["pin_path"], package_json=False,
                                  fetch=_fake_fetch(world["blob"], calls))
    assert (rc, client) == (electron_pin.RC_OK, True)
    assert calls == [world["pin"]["arch"]["x64"]["zip_url"]]
    assert (world["pkg"] / "dist" / "electron.exe").read_bytes() == EXE
    assert not elsewhere.exists()


def test_the_pin_tools_read_no_override_variable():
    src = (_text(ROOT / "tools" / "electron_pin.py") + _text(ROOT / "tools" / "tc_pin.py")).lower()
    for name in OVERRIDES:
        assert name.lower() not in src, name
    assert "mirror" not in src


@pytest.mark.skipif(PS51 is None, reason="Windows PowerShell 5.1 only")
def test_clear_overrides_removes_every_variable():
    env = dict(os.environ)
    for name in OVERRIDES:
        env[name] = "1"
    env["AL_KEEP_ME"] = "kept"
    names = ", ".join(_ps_str(n) for n in OVERRIDES)
    out = _ps_funcs(SETUP_PS1, ["Clear-AlElectronOverrides"],
                    "Clear-AlElectronOverrides\n"
                    "foreach ($n in @(" + names + ")) {\n"
                    "  if ($null -ne [Environment]::GetEnvironmentVariable($n)) { 'LEFT=' + $n }\n"
                    "}\n"
                    "'KEEP=' + $env:AL_KEEP_ME\n", env=env)
    assert [ln for ln in out if ln.startswith("LEFT=")] == []
    assert "KEEP=kept" in out


def _setup_pin_call(tmp_path, rc, out, cmd):
    repo = _fake_repo(tmp_path)
    argv = tmp_path / "argv.txt"
    env = dict(os.environ, FAKE_RC=str(rc), FAKE_OUT=out, FAKE_ARGV=str(argv))
    lines = _ps_funcs(SETUP_PS1, ["Invoke-AlElectronPin", "Write-AlLog"],
                      "$Repo = " + _ps_str(repo) + "\n"
                      "$py = " + _ps_str(sys.executable) + "\n"
                      "$app = " + _ps_str(repo / "app") + "\n"
                      "$log = " + _ps_str(tmp_path / "setup.log") + "\n"
                      "'RC=' + (Invoke-AlElectronPin " + _ps_str(cmd) + ")\n", env=env)
    rcs = [ln for ln in lines if ln.startswith("RC=")]
    return rcs[-1], argv.read_text(encoding="ascii").split()


@pytest.mark.skipif(PS51 is None, reason="Windows PowerShell 5.1 only")
def test_setup_pin_helper_maps_the_tool_result(tmp_path):
    rc, argv = _setup_pin_call(tmp_path / "a", 0, "electron.exe ok (hashed)", "verify-exe")
    assert rc == "RC=0"
    assert argv[:2] == ["verify-exe", "--app-dir"]
    rc, _ = _setup_pin_call(tmp_path / "b", 2, "refused: electron.exe sha256 differs",
                            "verify-exe")
    assert rc == "RC=2"
    # rc 0 with no pin for this machine is no trusted exe
    rc, _ = _setup_pin_call(tmp_path / "c", 0, "warning: no Electron pin; no client",
                            "verify-exe")
    assert rc == "RC=2"
    # the install step itself may end with no client (nothing unpacked)
    rc, argv = _setup_pin_call(tmp_path / "d", 0, "warning: no Electron pin; no client", "setup")
    assert rc == "RC=0" and argv[0] == "setup"
    rc, _ = _setup_pin_call(tmp_path / "e", 1, "failed: network", "setup")
    assert rc == "RC=1"


def _run_exe_check(tmp_path, rc, out):
    repo = _fake_repo(tmp_path)
    argv = tmp_path / "argv.txt"
    exe = repo / "app" / "node_modules" / "electron" / "dist" / "electron.exe"
    env = dict(os.environ, FAKE_RC=str(rc), FAKE_OUT=out, FAKE_ARGV=str(argv))
    lines = _ps_funcs(RUN_PS1, ["Test-AlElectronExe", "Write-AlLog"],
                      "$Repo = " + _ps_str(repo) + "\n"
                      "$py = " + _ps_str(sys.executable) + "\n"
                      "$electron = " + _ps_str(exe) + "\n"
                      "$log = " + _ps_str(tmp_path / "run.log") + "\n"
                      "'OK=' + (Test-AlElectronExe)\n", env=env)
    oks = [ln for ln in lines if ln.startswith("OK=")]
    return oks[-1], argv.read_text(encoding="ascii").split(), str(exe)


@pytest.mark.skipif(PS51 is None, reason="Windows PowerShell 5.1 only")
def test_run_exe_check_refuses_a_changed_or_unpinned_exe(tmp_path):
    ok, argv, exe = _run_exe_check(tmp_path / "a", 0,
                                   "electron.exe ok (unchanged since last check)")
    assert ok == "OK=True"
    assert argv[:2] == ["verify-exe", "--exe"] and " ".join(argv[2:]) == exe
    ok, _, _ = _run_exe_check(tmp_path / "b", 2, "refused: electron.exe size 1 differs")
    assert ok == "OK=False"
    ok, _, _ = _run_exe_check(tmp_path / "c", 0, "warning: no Electron pin; no client")
    assert ok == "OK=False"
    ok, _, _ = _run_exe_check(tmp_path / "d", 1, "failed: boom")
    assert ok == "OK=False"
