"""REL-INSTALL-PAYLOAD (finding F-050, DEP-09): server/al/install/payload.py
verifies the app zip against SHA256SUMS.txt and MANIFEST.json, lays it out
as <home>/app/<ver>/ through <ver>.partial and one rename, places the two
hash-pinned runtimes and checks the active version for repair.

The app zips are built by tools/rel_build.py from a scratch git repo under
tmp_path; the runtime zips are small stand-ins with pins made to match.
No request leaves the process: every opener is a fake and an autouse
fixture makes any socket connect fail the test.
"""

import email.message
import hashlib
import importlib.util
import io
import json
import os
import socket
import subprocess
import sys
import urllib.error
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.al import NAME, VERSION, pinfetch, webfetch  # noqa: E402
from server.al.install import home as homemod  # noqa: E402
from server.al.install import payload  # noqa: E402

VER = "1.2.3"
WHEN = "2026-11-19T10:20:30Z"
STAMP = datetime(2026, 11, 19, 12, 0, 0, tzinfo=timezone.utc)
UA = "AshLight/%s (installer)" % VERSION


def _load_tool(name):
    spec = importlib.util.spec_from_file_location(
        "payload_test_" + name, str(ROOT / "tools" / (name + ".py")))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*_a, **_k):
        raise AssertionError("a test tried to open a network connection")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


# --- a real app zip from tools/rel_build.py ----------------------------------

_GIT = ["git", "-c", "core.hooksPath=", "-c", "user.name=t",
        "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false"]

FILES = {
    "server/al/core.py": "\"\"\"Stand-in core.\"\"\"\nVALUE = 1\n",
    "server/al/data/zone_notes.json": "{\"zones\": []}\n",
    "web/index.html": "<!doctype html><title>AshLight</title>\n",
    "app/main.js": "'use strict';\n",
    "config/tc_pins.json": "{}\n",
    "tools/tc_pin.py": "# pin tool\n",
    "README.md": "# AshLight\n",
    "LICENSE": "licence\n",
    "boot.py": "# boot\n",
    "tests/test_x.py": "# not shipped\n",
}


def _git(cwd, *args):
    env = dict(os.environ, GIT_AUTHOR_DATE=WHEN, GIT_COMMITTER_DATE=WHEN)
    proc = subprocess.run(_GIT + list(args), cwd=str(cwd), env=env,
                          capture_output=True, check=False)
    assert proc.returncode == 0, proc.stderr


@pytest.fixture(scope="module")
def release(tmp_path_factory):
    """{zip, sums, data}: AshLight-1.2.3-app.zip and its SHA256SUMS.txt."""
    base = tmp_path_factory.mktemp("rel")
    repo = base / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    files = dict(FILES)
    files["server/al/__init__.py"] = "\"\"\"AshLight.\"\"\"\n\nVERSION = \"%s\"\n" % VER
    for rel, text in files.items():
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(text.encode("ascii"))
    dst = repo / "config" / "ship_list.json"
    dst.write_bytes((ROOT / "config" / "ship_list.json").read_bytes())
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "chore: scratch")
    (base / "cache").mkdir()
    rb = _load_tool("rel_build")
    res = rb.build(root=repo, ref="HEAD", out=base / "out", cache_dir=base / "cache")
    zip_path = res["zip"]
    return {"zip": zip_path, "sums": base / "out" / rb.SUMS_NAME,
            "data": zip_path.read_bytes()}


def _sums_for(name, data):
    return ("%s  %s\n" % (hashlib.sha256(data).hexdigest(), name)).encode("ascii")


def _write_zip(path, data):
    path.write_bytes(data)
    return path, _sums_for(path.name, data)


def _rezip(data, change=None, add=None, drop=()):
    """A copy of an app zip with member bytes changed, members added (name
    -> bytes or ZipInfo, bytes) or dropped; MANIFEST.json kept as it is."""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(out, "w") as dst:
        for info in src.infolist():
            rel = info.filename.partition("/")[2]
            if rel in drop:
                continue
            body = src.read(info)
            if change and rel in change:
                body = change[rel](body)
            dst.writestr(info.filename, body)
        for name, body in (add or {}).items():
            if isinstance(body, tuple):
                dst.writestr(body[0], body[1])
            else:
                info = zipfile.ZipInfo("placeholder")
                info.filename = name  # kept as written (no separator rewrite)
                dst.writestr(info, body)
    return out.getvalue()


def _with_manifest(data, mutate):
    """Rebuild the zip with MANIFEST.json changed by mutate(obj)."""
    top = "%s-%s/" % (NAME, VER)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        obj = json.loads(zf.read(top + "MANIFEST.json"))
    mutate(obj)
    body = json.dumps(obj, indent=1, sort_keys=True).encode("ascii")
    return _rezip(data, change={"MANIFEST.json": lambda _b: body})


def _nothing_laid_out(home):
    app = home / "app"
    return not app.exists() or sorted(os.listdir(app)) == []


# --- the good path -------------------------------------------------------------

def test_good_zip_lands_through_partial_and_one_rename(tmp_path, release, monkeypatch):
    home = tmp_path / "home"
    renames = []
    real = os.replace

    def spy(src, dst):
        renames.append((Path(src).name, Path(dst).name))
        return real(src, dst)
    monkeypatch.setattr(payload.os, "replace", spy)
    target = payload.install_payload(release["zip"], release["sums"], home, VER)
    assert target == home / "app" / VER
    assert renames == [(VER + ".partial", VER)]
    assert sorted(os.listdir(home / "app")) == [VER]
    assert (target / "server" / "al" / "core.py").read_bytes() == \
        FILES["server/al/core.py"].encode("ascii")
    assert not (target / "tests").exists()
    assert json.loads((target / "BUILD").read_text())["version"] == VER
    assert payload.check_manifest(target) == []


def test_verify_zip_reports_name_hash_and_size(release):
    got = payload.verify_zip(release["zip"], release["sums"], size=len(release["data"]))
    assert got == {"name": release["zip"].name, "size": len(release["data"]),
                   "sha256": hashlib.sha256(release["data"]).hexdigest()}


def test_every_extracted_file_is_checked_against_the_manifest(tmp_path, release,
                                                              monkeypatch):
    home = tmp_path / "home"
    seen = []
    real = payload.check_manifest

    def spy(directory, ignore_bytecode=False):
        problems = real(directory, ignore_bytecode)
        seen.append((Path(directory).name, ignore_bytecode, problems,
                     sorted(p.relative_to(directory).as_posix()
                            for p in Path(directory).rglob("*") if p.is_file())))
        return problems
    monkeypatch.setattr(payload, "check_manifest", spy)
    payload.install_payload(release["zip"], release["sums"], home, VER)
    assert len(seen) == 1
    name, ignore, problems, files = seen[0]
    assert name == VER + ".partial" and ignore is False and problems == []
    with zipfile.ZipFile(release["zip"]) as zf:
        listed = json.loads(zf.read("%s-%s/MANIFEST.json" % (NAME, VER)))["files"]
    assert set(files) == set(listed) | {"MANIFEST.json"}


def test_a_second_install_of_the_same_version_is_a_no_op(tmp_path, release):
    home = tmp_path / "home"
    target = payload.install_payload(release["zip"], release["sums"], home, VER)
    # bytecode the private Python wrote does not make the folder differ
    pyc = target / "server" / "al" / "__pycache__" / "core.cpython-314.pyc"
    pyc.parent.mkdir()
    pyc.write_bytes(b"\0")
    before = (target / "README.md").stat().st_mtime_ns
    assert payload.install_payload(release["zip"], release["sums"], home, VER) == target
    assert (target / "README.md").stat().st_mtime_ns == before
    assert sorted(os.listdir(home / "app")) == [VER]


def test_a_differing_version_folder_is_never_modified(tmp_path, release):
    home = tmp_path / "home"
    target = payload.install_payload(release["zip"], release["sums"], home, VER)
    (target / "README.md").write_bytes(b"edited\n")
    with pytest.raises(payload.PayloadError, match="repair"):
        payload.install_payload(release["zip"], release["sums"], home, VER)
    assert (target / "README.md").read_bytes() == b"edited\n"
    assert sorted(os.listdir(home / "app")) == [VER]


def test_a_stale_partial_folder_is_replaced(tmp_path, release):
    home = tmp_path / "home"
    stale = home / "app" / (VER + ".partial")
    (stale / "junk").mkdir(parents=True)
    (stale / "junk" / "x.txt").write_bytes(b"half\n")
    target = payload.install_payload(release["zip"], release["sums"], home, VER)
    assert sorted(os.listdir(home / "app")) == [VER]
    assert not (target / "junk").exists()


# --- refusals: nothing installed, no partial ---------------------------------------

def test_tampered_zip_installs_nothing(tmp_path, release):
    home = tmp_path / "home"
    data = bytearray(release["data"])
    data[len(data) // 2] ^= 0xFF
    bad = tmp_path / release["zip"].name
    bad.write_bytes(bytes(data))
    with pytest.raises(pinfetch.HashMismatch):
        payload.install_payload(bad, release["sums"], home, VER)
    assert _nothing_laid_out(home)


def test_missing_sums_line_installs_nothing(tmp_path, release):
    home = tmp_path / "home"
    other = b"%s  AshLight-9.9.9-app.zip\n" % (b"0" * 64)
    with pytest.raises(payload.SumsError, match="no line"):
        payload.install_payload(release["zip"], other, home, VER)
    with pytest.raises(payload.SumsError):
        payload.verify_zip(release["zip"], b"")
    assert _nothing_laid_out(home)


@pytest.mark.parametrize("text", [
    b"not a sums line\n",
    b"%s  a.zip\n%s  a.zip\n" % (b"a" * 64, b"b" * 64),
    b"%s  a.zip\n" % (b"A" * 64),
])
def test_malformed_sums_file_is_refused(text):
    with pytest.raises(payload.SumsError):
        payload.parse_sums(text)


def test_size_mismatch_installs_nothing(tmp_path, release):
    home = tmp_path / "home"
    with pytest.raises(pinfetch.HashMismatch, match="bytes"):
        payload.install_payload(release["zip"], release["sums"], home, VER,
                                size=len(release["data"]) + 1)
    assert _nothing_laid_out(home)


def test_manifest_size_mismatch_installs_nothing(tmp_path, release):
    home = tmp_path / "home"
    data = _with_manifest(release["data"],
                          lambda m: m["files"]["README.md"].update(size=999))
    path, sums = _write_zip(tmp_path / release["zip"].name, data)
    with pytest.raises(payload.ManifestError, match="size differs: README.md"):
        payload.install_payload(path, sums, home, VER)
    assert _nothing_laid_out(home)


def test_changed_member_bytes_install_nothing(tmp_path, release):
    home = tmp_path / "home"
    data = _rezip(release["data"], change={"README.md": lambda b: b.upper()})
    path, sums = _write_zip(tmp_path / release["zip"].name, data)
    with pytest.raises(payload.ManifestError, match="changed: README.md"):
        payload.install_payload(path, sums, home, VER)
    assert _nothing_laid_out(home)


@pytest.mark.parametrize("kind", ["unlisted", "missing", "no_manifest", "bad_build"])
def test_zip_that_differs_from_its_manifest_installs_nothing(tmp_path, release, kind):
    home = tmp_path / "home"
    top = "%s-%s/" % (NAME, VER)
    if kind == "unlisted":
        data = _rezip(release["data"], add={top + "extra.txt": b"x\n"})
        want = "unlisted: extra.txt"
    elif kind == "missing":
        data = _rezip(release["data"], drop=("README.md",))
        want = "missing: README.md"
    elif kind == "no_manifest":
        data = _rezip(release["data"], drop=("MANIFEST.json",))
        want = "MANIFEST.json: missing"
    else:
        build = json.dumps({"version": "9.9.9"}).encode("ascii")
        data = _with_manifest(
            _rezip(release["data"], change={"BUILD": lambda _b: build}),
            lambda m: m["files"]["BUILD"].update(
                sha256=hashlib.sha256(build).hexdigest(), size=len(build)))
        want = "BUILD: version"
    path, sums = _write_zip(tmp_path / release["zip"].name, data)
    with pytest.raises(payload.ManifestError, match=want):
        payload.install_payload(path, sums, home, VER)
    assert _nothing_laid_out(home)


def _symlink_info(name):
    info = zipfile.ZipInfo(name)
    info.external_attr = (0o120777 << 16)
    return info


@pytest.mark.parametrize("member", [
    "AshLight-1.2.3/../evil.txt",
    "AshLight-1.2.3/a\\b.txt",
    "AshLight-1.2.3/C:x.txt",
    "/AshLight-1.2.3/abs.txt",
    "AshLight-9.9.9/other.txt",
    "AshLight-1.2.3/sub/",
    "AshLight-1.2.3/CON.txt",
    "AshLight-1.2.3/readme.md",  # README.md again, by case only
    "evil.txt",
    "symlink",
])
def test_unsafe_member_installs_nothing(tmp_path, release, member):
    home = tmp_path / "home"
    if member == "symlink":
        add = {"s": (_symlink_info("AshLight-1.2.3/link"), b"../../outside")}
    else:
        add = {member: b"x\n"}
    data = _rezip(release["data"], add=add)
    path, sums = _write_zip(tmp_path / release["zip"].name, data)
    # zipfile reads a backslash name as '/' on Windows: then the member is
    # unlisted in MANIFEST.json, refused all the same
    refusal = pinfetch.UnsafeArchive
    if "\\" in member:
        refusal = (pinfetch.UnsafeArchive, payload.ManifestError)
    with pytest.raises(refusal):
        payload.install_payload(path, sums, home, VER)
    assert _nothing_laid_out(home)
    assert not (tmp_path / "evil.txt").exists()
    assert not (home / "evil.txt").exists()


def test_wrong_or_bad_version_installs_nothing(tmp_path, release):
    home = tmp_path / "home"
    with pytest.raises(pinfetch.UnsafeArchive):
        payload.install_payload(release["zip"], release["sums"], home, "1.2.4")
    for bad in ("../1.2.3", "1.2", "v1.2.3"):
        with pytest.raises(payload.PayloadError, match="not a version"):
            payload.install_payload(release["zip"], release["sums"], home, bad)
    assert _nothing_laid_out(home)


def test_failure_while_laying_out_leaves_no_partial(tmp_path, release, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setattr(payload, "check_manifest", lambda *a, **k: ["changed: x"])
    with pytest.raises(payload.ManifestError, match="changed: x"):
        payload.install_payload(release["zip"], release["sums"], home, VER)
    assert _nothing_laid_out(home)


def test_a_home_in_a_game_folder_is_refused(tmp_path, release):
    from server.al import paths
    home = tmp_path / "steamapps" / "AshLight"
    with pytest.raises(paths.HomeRefused):
        payload.install_payload(release["zip"], release["sums"], home, VER)
    assert not home.exists()


# --- the repair check ------------------------------------------------------------------

def _active_install(tmp_path, release):
    home = tmp_path / "home"
    payload.install_payload(release["zip"], release["sums"], home, VER)
    for name in pinfetch.RUNTIME_NAMES:
        folder = home / "runtime" / ("%s-1" % name)
        folder.mkdir(parents=True)
        (folder / pinfetch.RUNTIME_MARKER).write_text("{}\n", encoding="ascii")
    homemod.write_marker(home, homemod.new_marker(VER, "python-1", "electron-1",
                                                  now=STAMP))
    return home, home / "app" / VER


def test_verify_active_ok_and_ignores_bytecode(tmp_path, release):
    home, target = _active_install(tmp_path, release)
    pyc = target / "server" / "al" / "__pycache__" / "core.cpython-314.pyc"
    pyc.parent.mkdir()
    pyc.write_bytes(b"\0")
    assert payload.verify_active(home) == {"ok": True, "version": VER, "problems": []}


def test_verify_active_reports_a_changed_missing_or_unlisted_file(tmp_path, release):
    home, target = _active_install(tmp_path, release)
    (target / "README.md").write_bytes(b"edited\n")
    (target / "web" / "index.html").unlink()
    (target / "server" / "al" / "extra.py").write_bytes(b"x = 1\n")
    rep = payload.verify_active(home)
    assert rep["ok"] is False and rep["version"] == VER
    assert rep["problems"] == ["changed: README.md", "missing: web/index.html",
                               "unlisted: server/al/extra.py"]


def test_verify_active_reports_a_missing_folder_runtime_or_marker(tmp_path, release):
    home, target = _active_install(tmp_path, release)
    (home / "runtime" / "electron-1" / pinfetch.RUNTIME_MARKER).unlink()
    assert payload.verify_active(home)["problems"] == ["runtime missing: electron"]
    os.replace(target, home / "temp-moved")
    assert "missing: version folder" in payload.verify_active(home)["problems"]
    (home / "install.json").unlink()
    (home / "install.json.bak").unlink(missing_ok=True)
    assert payload.verify_active(home) == {
        "ok": False, "version": None, "problems": ["no valid install marker"]}


# --- runtimes --------------------------------------------------------------------------

def _runtime_zip(files):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as zf:
        for name, body in files.items():
            zf.writestr(name, body)
    return out.getvalue()


PY_ZIP = _runtime_zip({"python.exe": b"stand-in python\n", "python314._pth": b".\n"})
EL_ZIP = _runtime_zip({"electron.exe": b"stand-in electron\n", "LICENSE": b"MIT\n"})
PY_BAD = bytes([PY_ZIP[0] ^ 1]) + PY_ZIP[1:]  # one bit off the pin
PY_URL = "https://www.python.org/ftp/python/3.14.10/python-3.14.10-embed-amd64.zip"
EL_URL = ("https://github.com/electron/electron/releases/download/v45.3.3/"
          "electron-v45.3.3-win32-x64.zip")


def _pin(url, data, version, licence):
    return {"version": version, "file": url.rsplit("/", 1)[-1], "url": url,
            "sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
            "licence": licence}


def _release_doc():
    return {"name": NAME, "version": VER, "runtimes": {
        "python": _pin(PY_URL, PY_ZIP, "3.14.10", "PSF-2.0"),
        "electron": _pin(EL_URL, EL_ZIP, "45.3.3", "MIT")}}


class _Resp:
    def __init__(self, body):
        self._buf = io.BytesIO(body)

    def read(self, n):
        return self._buf.read(min(n, 7))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Opener:
    """Serves url -> bytes, or url -> (code, location) as a redirect."""

    def __init__(self, routes):
        self.routes = routes
        self.requests = []

    def open(self, req, timeout=None):
        self.requests.append(req)
        step = self.routes[req.full_url]
        if isinstance(step, bytes):
            return _Resp(step)
        hdrs = email.message.Message()
        hdrs["Location"] = step[1]
        raise urllib.error.HTTPError(req.full_url, step[0], "redirect", hdrs,
                                     io.BytesIO(b""))


def _refuse_fetch(*_a, **_k):
    raise AssertionError("no fetch expected")


def test_installer_user_agent_and_host_list():
    assert payload.user_agent() == UA
    assert payload.user_agent("1.2.3") == "AshLight/1.2.3 (installer)"
    assert set(payload.INSTALL_HOSTS) == {
        "github.com", "release-assets.githubusercontent.com",
        "objects.githubusercontent.com", "www.python.org"}


def test_pins_from_release_checks_each_pin():
    doc = _release_doc()
    pins = payload.pins_from_release(doc, version=VER)
    assert set(pins) == {"python", "electron"}
    with pytest.raises(pinfetch.PinError, match="not for version"):
        payload.pins_from_release(doc, version="1.2.4")
    broken = _release_doc()
    del broken["runtimes"]["electron"]
    with pytest.raises(pinfetch.PinError):
        payload.pins_from_release(broken)
    broken = _release_doc()
    broken["runtimes"]["python"]["file"] = "other.zip"
    with pytest.raises(pinfetch.PinError, match="file differs"):
        payload.pins_from_release(broken)
    broken = _release_doc()
    broken["runtimes"]["python"]["url"] = "https://example.com/" + \
        broken["runtimes"]["python"]["file"]
    with pytest.raises(webfetch.UrlNotAllowed):
        payload.pins_from_release(broken)


def test_the_tracked_runtime_pins_pass_the_release_check():
    pins = {name: pinfetch.load_runtime_pin(name) for name in pinfetch.RUNTIME_NAMES}
    assert payload.pins_from_release({"runtimes": pins}) == pins
    assert payload.runtime_folder("python", pins["python"]) == "python-3.14.10"


def test_runtime_from_the_runtime_dir_needs_no_request(tmp_path):
    home = tmp_path / "home"
    src = tmp_path / "downloads"
    src.mkdir()
    (src / PY_URL.rsplit("/", 1)[-1]).write_bytes(PY_ZIP)
    (src / EL_URL.rsplit("/", 1)[-1]).write_bytes(EL_ZIP)
    pins = payload.pins_from_release(_release_doc())
    opener = _Opener({})
    got = payload.place_runtimes(pins, home, source_dir=src, opener=opener)
    assert got == {"python": "python-3.14.10", "electron": "electron-45.3.3"}
    assert opener.requests == []
    py = home / "runtime" / "python-3.14.10"
    assert (py / "python.exe").read_bytes() == b"stand-in python\n"
    assert pinfetch.runtime_ready("python", pins["python"], py)
    # placed again: a no-op, the source is not even read
    (src / PY_URL.rsplit("/", 1)[-1]).unlink()
    assert payload.place_runtime("python", pins["python"], home, source_dir=src) \
        == "python-3.14.10"


def test_runtime_dir_with_a_wrong_hash_refuses(tmp_path):
    home = tmp_path / "home"
    src = tmp_path / "downloads"
    src.mkdir()
    (src / PY_URL.rsplit("/", 1)[-1]).write_bytes(PY_BAD)
    pin = payload.pins_from_release(_release_doc())["python"]
    opener = _Opener({})
    with pytest.raises(pinfetch.HashMismatch):
        payload.place_runtime("python", pin, home, source_dir=src, opener=opener)
    assert opener.requests == []
    assert not (home / "runtime" / "python-3.14.10").exists()
    with pytest.raises(payload.PayloadError, match="not in the runtime folder"):
        payload.place_runtime("electron", payload.pins_from_release(
            _release_doc())["electron"], home, source_dir=src)


def test_runtime_fetch_sends_the_installer_agent_to_listed_hosts_only(tmp_path):
    home = tmp_path / "home"
    asset = "https://release-assets.githubusercontent.com/x/electron.zip"
    opener = _Opener({PY_URL: PY_ZIP, EL_URL: (302, asset), asset: EL_ZIP})
    pins = payload.pins_from_release(_release_doc())
    got = payload.place_runtimes(pins, home, opener=opener)
    assert got == {"python": "python-3.14.10", "electron": "electron-45.3.3"}
    assert [r.full_url for r in opener.requests] == [PY_URL, EL_URL, asset]
    for req in opener.requests:
        host = req.full_url.split("/")[2]
        assert host in payload.INSTALL_HOSTS
        assert req.get_header("User-agent") == UA
        assert req.get_header("Cookie") is None
        assert sorted(req.header_items()) == [("Accept", "*/*"), ("User-agent", UA)]
    assert (home / "runtime" / "electron-45.3.3" / "electron.exe").is_file()


def test_runtime_fetch_with_a_wrong_hash_places_nothing(tmp_path):
    home = tmp_path / "home"
    opener = _Opener({PY_URL: PY_BAD})
    pin = payload.pins_from_release(_release_doc())["python"]
    with pytest.raises(pinfetch.HashMismatch):
        payload.place_runtime("python", pin, home, opener=opener)
    assert sorted(os.listdir(home / "runtime")) == []


def test_no_request_goes_to_a_host_off_the_list(tmp_path):
    home = tmp_path / "home"
    pin = payload.pins_from_release(_release_doc())["electron"]
    opener = _Opener({EL_URL: (302, "https://evil.example/electron.zip")})
    with pytest.raises(webfetch.UrlNotAllowed):
        payload.place_runtime("electron", pin, home, opener=opener)
    assert [r.full_url for r in opener.requests] == [EL_URL]
    off = dict(pin, url="https://example.com/" + pin["file"])
    opener = _Opener({})
    with pytest.raises(webfetch.UrlNotAllowed):
        payload.place_runtime("electron", off, home, opener=opener)
    assert opener.requests == []
    with pytest.raises(webfetch.UrlNotAllowed):
        list(payload.installer_stream("http://github.com/x.zip", 10, opener=opener))
    assert opener.requests == []
    assert not (home / "runtime" / "electron-45.3.3").exists()


def test_a_body_past_the_pinned_size_is_cut_off():
    opener = _Opener({PY_URL: b"x" * 20})
    with pytest.raises(pinfetch.HashMismatch):
        b"".join(payload.installer_stream(PY_URL, 10, opener=opener))


def test_read_release_reads_a_capped_json_object(tmp_path):
    path = tmp_path / "release.json"
    path.write_text(json.dumps(_release_doc()), encoding="ascii")
    assert payload.read_release(path)["version"] == VER
    path.write_text("[]", encoding="ascii")
    with pytest.raises(payload.PayloadError):
        payload.read_release(path)
    path.write_bytes(b"{" + b" " * payload.MAX_RELEASE_BYTES)
    with pytest.raises(payload.PayloadError):
        payload.read_release(path)
