"""REL-RUNTIME-PINS: the runtime pin file and the hash-checked runtime fetch.

The pin schema (url, sha256, size, licence), the Electron pin read from its
one source and equal to app/package.json, ensure_runtime refusing a wrong
hash with nothing left in the target, the host allow-list, the AshLight
User-Agent with no cookie, and THIRD-PARTY.md naming both runtimes as
fetched at install. No network: every opener is a fake (decision 0063)."""

import email.message
import hashlib
import io
import json
import shutil
import sys
import urllib.error
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.al import pinfetch, webfetch  # noqa: E402

CONFIG = ROOT / "config"
URL = "https://www.python.org/ftp/python/9.9.9/python-9.9.9-embed-amd64.zip"


class _Resp:
    def __init__(self, body, chunk=7):
        self._buf = io.BytesIO(body)
        self._chunk = chunk

    def read(self, n):
        return self._buf.read(min(n, self._chunk))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Opener:
    """Answers each open() with the next scripted step: bytes, or a
    (code, location) redirect raised as HTTPError."""

    def __init__(self, steps):
        self.steps = list(steps)
        self.requests = []

    def open(self, req, timeout=None):
        self.requests.append(req)
        step = self.steps.pop(0)
        if isinstance(step, bytes):
            return _Resp(step)
        code, loc = step
        hdrs = email.message.Message()
        hdrs["Location"] = loc
        raise urllib.error.HTTPError(req.full_url, code, "redirect", hdrs, io.BytesIO(b""))


def _zip(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _pin(body, url=URL, **over):
    pin = {"version": "9.9.9", "file": url.rsplit("/", 1)[1], "url": url,
           "sha256": hashlib.sha256(body).hexdigest(), "size": len(body),
           "licence": "PSF-2.0"}
    pin.update(over)
    return pin


# --- the pin files ----------------------------------------------------------

def test_runtime_pins_file_schema():
    doc = json.loads((CONFIG / "runtime_pins.json").read_text(encoding="ascii"))
    assert doc["schema"] == 1
    assert set(doc["runtimes"]) == set(pinfetch.RUNTIME_NAMES)
    py = doc["runtimes"]["python"]
    for key in ("url", "sha256", "size", "licence"):
        assert key in py, key
    assert py["url"].startswith("https://www.python.org/ftp/python/" + py["version"] + "/")
    assert py["url"].endswith("/" + py["file"])
    assert py["file"] == f"python-{py['version']}-embed-amd64.zip"
    assert len(py["sha256"]) == 64 and py["sha256"] == py["sha256"].lower()
    assert isinstance(py["size"], int) and py["size"] > 0
    assert py["licence"] == "PSF-2.0"
    el = doc["runtimes"]["electron"]
    assert el == {"pin_file": "config/electron_pin.json", "licence": "MIT"}


def test_python_version_is_exact_never_a_range():
    py = pinfetch.load_runtime_pin("python")
    parts = py["version"].split(".")
    assert len(parts) == 3 and all(p.isdigit() for p in parts)
    assert py["version"].startswith("3.14.")


@pytest.mark.parametrize("name", pinfetch.RUNTIME_NAMES)
def test_loaded_pins_are_complete(name):
    pin = pinfetch.load_runtime_pin(name)
    for key in ("url", "sha256", "size", "licence", "version", "file"):
        assert pin[key], key
    assert pinfetch.check_runtime_pin(name, pin) is pin


def test_electron_pin_is_read_from_its_one_source_and_equals_package_json():
    edoc = json.loads((CONFIG / "electron_pin.json").read_text(encoding="utf-8"))
    pkg = json.loads((ROOT / "app" / "package.json").read_text(encoding="utf-8"))
    deps = dict(pkg.get("dependencies") or {}, **(pkg.get("devDependencies") or {}))
    pin = pinfetch.load_runtime_pin("electron")
    assert pin["version"] == deps["electron"] == edoc["version"]
    x64 = edoc["arch"]["x64"]
    assert (pin["url"], pin["sha256"], pin["size"]) == \
        (x64["zip_url"], x64["zip_sha256"], x64["zip_size"])
    assert pin["licence"] == "MIT"
    # no second copy of the Electron hash in runtime_pins.json
    assert x64["zip_sha256"] not in (CONFIG / "runtime_pins.json").read_text(encoding="ascii")


def test_python_has_no_arm64_pin():
    with pytest.raises(pinfetch.PinError):
        pinfetch.load_runtime_pin("python", arch="arm64")


def _write_cfg(tmp_path, python_entry):
    shutil.copy(CONFIG / "electron_pin.json", tmp_path / "electron_pin.json")
    doc = {"schema": 1, "runtimes": {"python": python_entry,
                                     "electron": {"pin_file": "config/electron_pin.json",
                                                  "licence": "MIT"}}}
    (tmp_path / "runtime_pins.json").write_text(json.dumps(doc), encoding="ascii")


@pytest.mark.parametrize("drop", ["url", "sha256", "size", "licence"])
def test_a_pin_missing_a_field_refuses(tmp_path, drop):
    entry = dict(_pin(b"x"), arch="amd64")
    del entry[drop]
    _write_cfg(tmp_path, entry)
    with pytest.raises(pinfetch.PinError):
        pinfetch.load_runtime_pin("python", config_dir=tmp_path)


@pytest.mark.parametrize("over", [
    {"sha256": "A" * 64}, {"sha256": "ab"}, {"size": 0}, {"size": True},
    {"size": "12"}, {"licence": " "}, {"version": ""},
    {"size": pinfetch.MAX_RUNTIME_BYTES + 1},
])
def test_malformed_pin_values_refuse(over):
    with pytest.raises(pinfetch.PinError):
        pinfetch.check_runtime_pin("python", _pin(b"x", **over))


def test_unknown_runtime_name_refuses():
    with pytest.raises(pinfetch.PinError):
        pinfetch.check_runtime_pin("node", _pin(b"x"))


# --- ensure_runtime -----------------------------------------------------------

def _fetch_of(body):
    op = _Opener([body])
    return op, pinfetch.runtime_fetch("python", opener=op)


def test_ensure_runtime_unpacks_and_marks(tmp_path):
    body = _zip({"python.exe": b"MZ", "Lib/x.py": b"pass\n"})
    pin = _pin(body)
    dest = tmp_path / "runtime" / "python-9.9.9"
    op, fetch = _fetch_of(body)
    assert pinfetch.ensure_runtime("python", pin, dest, fetch) == dest
    assert (dest / "python.exe").read_bytes() == b"MZ"
    assert (dest / "Lib" / "x.py").is_file()
    assert pinfetch.runtime_ready("python", pin, dest)
    assert sorted(p.name for p in dest.parent.iterdir()) == ["python-9.9.9"]
    # a second call with the same pin is a no-op: no request
    op2, fetch2 = _fetch_of(b"never")
    pinfetch.ensure_runtime("python", pin, dest, fetch2)
    assert op2.requests == []


def test_wrong_pin_hash_raises_and_leaves_nothing_in_dest(tmp_path):
    body = _zip({"python.exe": b"MZ"})
    pin = _pin(body, sha256="0" * 64)
    dest = tmp_path / "runtime" / "python-9.9.9"
    _, fetch = _fetch_of(body)
    with pytest.raises(pinfetch.HashMismatch):
        pinfetch.ensure_runtime("python", pin, dest, fetch)
    assert not dest.exists()
    assert list(dest.parent.iterdir()) == []


def test_wrong_size_raises_and_leaves_nothing(tmp_path):
    body = _zip({"python.exe": b"MZ"})
    dest = tmp_path / "python-9.9.9"
    for size in (len(body) - 1, len(body) + 1):
        _, fetch = _fetch_of(body)
        with pytest.raises(pinfetch.HashMismatch):
            pinfetch.ensure_runtime("python", _pin(body, size=size), dest, fetch)
        assert list(tmp_path.iterdir()) == []


def test_unsafe_member_is_refused_and_nothing_extracted(tmp_path):
    body = _zip({"../evil.exe": b"MZ"})
    dest = tmp_path / "rt" / "python-9.9.9"
    _, fetch = _fetch_of(body)
    with pytest.raises(pinfetch.UnsafeArchive):
        pinfetch.ensure_runtime("python", _pin(body), dest, fetch)
    assert list(dest.parent.iterdir()) == []
    assert not (tmp_path / "evil.exe").exists()


def test_a_folder_not_made_by_ashlight_is_never_replaced(tmp_path):
    body = _zip({"python.exe": b"MZ"})
    dest = tmp_path / "python-9.9.9"
    dest.mkdir()
    (dest / "mine.txt").write_text("keep", encoding="ascii")
    op, fetch = _fetch_of(body)
    with pytest.raises(pinfetch.PinError):
        pinfetch.ensure_runtime("python", _pin(body), dest, fetch)
    assert (dest / "mine.txt").read_text(encoding="ascii") == "keep"
    assert op.requests == []


def test_an_older_runtime_of_ours_is_replaced(tmp_path):
    old = _zip({"old.exe": b"1"})
    new = _zip({"new.exe": b"2"})
    dest = tmp_path / "python-9.9.9"
    pinfetch.ensure_runtime("python", _pin(old), dest, _fetch_of(old)[1])
    pinfetch.ensure_runtime("python", _pin(new), dest, _fetch_of(new)[1])
    assert (dest / "new.exe").is_file() and not (dest / "old.exe").exists()


# --- hosts, User-Agent, cookie ------------------------------------------------

def test_runtime_hosts_are_exactly_the_publishers():
    assert pinfetch.RUNTIME_HOSTS == (
        "www.python.org", "github.com", "release-assets.githubusercontent.com",
        "objects.githubusercontent.com")


@pytest.mark.parametrize("url", [
    "https://example.com/python-9.9.9-embed-amd64.zip",
    "https://python.org/python-9.9.9-embed-amd64.zip",
    "https://www.python.org.evil.example/python-9.9.9-embed-amd64.zip",
    "http://www.python.org/python-9.9.9-embed-amd64.zip",
    "https://codeload.github.com/python-9.9.9-embed-amd64.zip",
])
def test_a_host_off_the_list_is_refused_before_any_request(tmp_path, url):
    body = _zip({"python.exe": b"MZ"})
    op, fetch = _fetch_of(body)
    with pytest.raises(webfetch.UrlNotAllowed):
        pinfetch.ensure_runtime("python", _pin(body, url=url), tmp_path / "rt", fetch)
    assert op.requests == []
    assert list(tmp_path.iterdir()) == []


def test_a_redirect_off_the_list_is_refused(tmp_path):
    body = _zip({"python.exe": b"MZ"})
    op = _Opener([(302, "https://example.com/x.zip"), body])
    with pytest.raises(webfetch.UrlNotAllowed):
        pinfetch.ensure_runtime("python", _pin(body), tmp_path / "rt",
                                pinfetch.runtime_fetch("python", opener=op))
    assert len(op.requests) == 1
    assert list(tmp_path.iterdir()) == []


def test_a_github_release_redirect_to_the_asset_host_is_followed(tmp_path):
    body = _zip({"electron.exe": b"MZ"})
    url = "https://github.com/electron/electron/releases/download/v9.9.9/e.zip"
    op = _Opener([(302, "https://release-assets.githubusercontent.com/a/e.zip"), body])
    dest = tmp_path / "electron-9.9.9"
    pinfetch.ensure_runtime("electron", _pin(body, url=url, licence="MIT"), dest,
                            pinfetch.runtime_fetch("electron", opener=op))
    assert (dest / "electron.exe").is_file()
    assert [r.full_url for r in op.requests][1].startswith(
        "https://release-assets.githubusercontent.com/")


@pytest.mark.parametrize("name", pinfetch.RUNTIME_NAMES)
def test_every_request_carries_the_ashlight_user_agent_and_no_cookie(tmp_path, name):
    body = _zip({"a.exe": b"MZ"})
    url = ("https://github.com/electron/electron/releases/download/v9.9.9/e.zip"
           if name == "electron" else URL)
    op = _Opener([(302, "https://objects.githubusercontent.com/e.zip"), body]
                 if name == "electron" else [(301, URL), body])
    pinfetch.ensure_runtime(name, _pin(body, url=url), tmp_path / name,
                            pinfetch.runtime_fetch(name, opener=op))
    assert len(op.requests) == 2
    want = webfetch.user_agent(f"install: {name} runtime download")
    for req in op.requests:
        assert req.get_header("User-agent") == want
        assert want.startswith(webfetch.NAME + "/")
        assert not any(k.lower() == "cookie" for k, _ in req.header_items())
        assert not req.unredirected_hdrs


def test_default_fetch_is_the_runtime_fetch(monkeypatch, tmp_path):
    body = _zip({"python.exe": b"MZ"})
    seen = []

    def fake_stream(url, max_bytes, hosts, purpose, opener=None, **kw):
        seen.append((url, max_bytes, hosts, purpose))
        yield body
    monkeypatch.setattr(pinfetch, "http_stream", fake_stream)
    pinfetch.ensure_runtime("python", _pin(body), tmp_path / "rt")
    assert seen == [(URL, len(body), pinfetch.RUNTIME_HOSTS,
                     "install: python runtime download")]


# --- THIRD-PARTY.md -----------------------------------------------------------

def test_third_party_names_both_runtimes_as_fetched_at_install():
    text = (ROOT / "THIRD-PARTY.md").read_text(encoding="ascii")
    for heading, licence in (("## CPython", "PSF-2.0"), ("## Electron", "MIT")):
        start = text.index(heading)
        nxt = text.find("\n## ", start + 1)
        section = text[start:nxt if nxt != -1 else len(text)]
        assert "Fetched at install, not bundled." in section, heading
        assert licence in section, heading
    assert "fetched at install, not bundled" in text
