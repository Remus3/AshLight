"""OVL-ELECTRON-PIN: pin equals app/package.json, exe verify, zip hash refused
before unpack, AshLight User-Agent on the fetch, unknown arch warns. No
network: the fetch test uses a loopback mock server, the rest fakes."""

import hashlib
import http.server
import io
import json
import os
import socket
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
