"""PINFETCH: hash-pinned download, verify and safe-extract helpers.

REL-PINFETCH (DEP-06, F-047; research 0052 cut-or-merge): one stdlib module
for pinned downloads, so the calc setup (tools/tc_pin.py), the runtime fetch
and the installer share one host allow-list check, redirect cap, size cap,
hash check, quarantine and archive path guard.

Every caller passes its own host allow-list and User-Agent purpose; nothing
here holds a default host. The running core never imports this module (a
static test in tests/test_pinfetch.py keeps every module under server/al/
outside server/al/install/ from importing it): it serves setup and install
steps only.

Floor: https only, exact host match on every redirect hop (webfetch.check_url),
a truthful AshLight User-Agent, no cookie, no stored session. Nothing from
an archive is imported or executed here.
"""

import hashlib
import json
import os
import shutil
import stat
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from server.al import webfetch

MAX_REDIRECTS = 3
TIMEOUT_S = 60.0
CHUNK = 1024 * 1024


class HashMismatch(Exception):
    """A downloaded or cached archive does not match its pin: refused."""


class UnsafeArchive(Exception):
    """An archive member would land outside its pinned top dir: refused."""


def file_matches(path, sha256, size):
    """True when the file exists with exactly this size and SHA-256."""
    try:
        path = Path(path)
        if path.stat().st_size != size:
            return False
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(CHUNK), b""):
                h.update(block)
        return h.hexdigest() == sha256
    except OSError:
        return False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_stream(url, max_bytes, hosts, purpose, max_redirects=MAX_REDIRECTS,
                timeout=TIMEOUT_S, opener=None):
    """Yield the body of url in chunks. Redirects are followed by hand, each
    hop checked against hosts (https, no userinfo, port 443, exact host);
    more than max_redirects hops raise webfetch.FetchError. The body is cut
    off past max_bytes (HashMismatch). The User-Agent names AshLight and
    `purpose`; no cookie is ever sent. `opener` is for tests only."""
    if not hosts:
        raise webfetch.UrlNotAllowed("no host allow-list given")
    headers = {"User-Agent": webfetch.user_agent(purpose), "Accept": "*/*"}
    opener = opener or urllib.request.build_opener(_NoRedirect())
    for _ in range(max_redirects + 1):
        webfetch.check_url(url, hosts)
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            resp = opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code in webfetch.REDIRECT_CODES:
                loc = e.headers.get("Location") or ""
                e.close()
                url = urllib.parse.urljoin(url, loc)
                continue
            raise
        with resp:
            got = 0
            while True:
                block = resp.read(CHUNK)
                if not block:
                    return
                got += len(block)
                if got > max_bytes:
                    raise HashMismatch(f"download larger than the pinned {max_bytes} bytes")
                yield block
    raise webfetch.FetchError("too many redirects")


def quarantine(path):
    """Move a bad archive aside as <name>.rejected (replaceable data; kept
    for inspection). Returns the new path."""
    path = Path(path)
    bad = path.with_name(path.name + ".rejected")
    try:
        os.replace(path, bad)
    except OSError:
        pass
    return bad


_quarantine = quarantine


def check_members(zf, top_dir):
    """Raise UnsafeArchive unless every member sits under top_dir/ and is a
    plain file or directory with a relative, forward-slash path."""
    prefix = top_dir + "/"
    for info in zf.infolist():
        n = info.filename
        parts = n.split("/")
        mode = (info.external_attr >> 16) & 0o170000
        if (not n.startswith(prefix) and n != prefix) or "\\" in n or ":" in n \
                or n.startswith("/") or ".." in parts or "\0" in n:
            raise UnsafeArchive(f"unsafe member path: {n!r}")
        if mode == stat.S_IFLNK:
            raise UnsafeArchive(f"symlink member refused: {n!r}")


def extract_safe(archive, top_dir, parent):
    """Extract archive into parent/<top_dir> through a temp dir, after
    check_members; a stale tree there is replaced. Returns the target path.
    Raises UnsafeArchive (nothing extracted) or zipfile.BadZipFile."""
    parent = Path(parent)
    target = parent / top_dir
    parent.mkdir(parents=True, exist_ok=True)
    tmp = parent / f".{top_dir}.tmp"
    if tmp.exists():
        shutil.rmtree(tmp)  # our own half-made extract, replaceable from the archive
    with zipfile.ZipFile(archive) as zf:
        check_members(zf, top_dir)
        zf.extractall(tmp)
    if target.exists():
        shutil.rmtree(target)  # stale tree without a matching marker, replaceable
    os.replace(tmp / top_dir, target)
    shutil.rmtree(tmp, ignore_errors=True)
    return target


# --- installed-copy runtimes (REL-RUNTIME-PINS, decision 0063) -------------
#
# The embeddable CPython and the unmodified Electron zip are fetched from
# their publishers inside the installer's own process, at the exact url,
# size and SHA-256 of their pin, and unpacked into <home>/runtime/<name>-<ver>.
# The CPython pin lives in config/runtime_pins.json; the Electron pin is read
# from config/electron_pin.json (one source). Never bundled, never vendored,
# never fetched by the running core.

RUNTIME_HOSTS = ("www.python.org", "github.com",
                 "release-assets.githubusercontent.com",
                 "objects.githubusercontent.com")
RUNTIME_NAMES = ("python", "electron")
RUNTIME_PINS_FILE = "runtime_pins.json"
ELECTRON_PIN_FILE = "electron_pin.json"
RUNTIME_MARKER = "ashlight-runtime.json"
MAX_RUNTIME_BYTES = 512 * 1024 * 1024
PYTHON_ARCH = {"x64": "amd64"}
_PIN_KEYS = ("url", "sha256", "size", "licence")


class PinError(ValueError):
    """A runtime pin is missing, malformed or points off the host list."""


def _is_hex64(value):
    return isinstance(value, str) and len(value) == 64 and \
        all(c in "0123456789abcdef" for c in value)


def check_runtime_pin(name, pin):
    """Raise PinError (or webfetch.UrlNotAllowed for the url) unless pin is
    a complete runtime pin: url (https, a RUNTIME_HOSTS host), sha256 (64
    lower-case hex), size (a positive int under the cap), licence and
    version (non-empty text). Nothing is fetched. Returns pin."""
    if name not in RUNTIME_NAMES:
        raise PinError(f"unknown runtime {name!r}")
    if not isinstance(pin, dict):
        raise PinError(f"{name}: pin is not an object")
    for key in _PIN_KEYS + ("version",):
        if key not in pin:
            raise PinError(f"{name}: pin has no {key}")
    if not isinstance(pin["url"], str):
        raise PinError(f"{name}: url is not text")
    webfetch.check_url(pin["url"], RUNTIME_HOSTS)
    if not _is_hex64(pin["sha256"]):
        raise PinError(f"{name}: sha256 is not 64 lower-case hex")
    size = pin["size"]
    if isinstance(size, bool) or not isinstance(size, int) \
            or not 0 < size <= MAX_RUNTIME_BYTES:
        raise PinError(f"{name}: size is not a positive byte count under the cap")
    for key in ("licence", "version"):
        if not isinstance(pin[key], str) or not pin[key].strip():
            raise PinError(f"{name}: {key} is empty")
    return pin


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        raise PinError(f"pin file unreadable: {Path(path).name}") from e


def load_runtime_pin(name, arch="x64", config_dir=None):
    """The checked pin {version, file, url, sha256, size, licence} of one
    runtime for one Windows architecture. CPython comes from
    runtime_pins.json; Electron from electron_pin.json (its licence from
    runtime_pins.json). config_dir defaults to <repo>/config."""
    if config_dir is None:
        config_dir = Path(__file__).resolve().parents[2] / "config"
    config_dir = Path(config_dir)
    doc = _read_json(config_dir / RUNTIME_PINS_FILE)
    entry = (doc.get("runtimes") or {}).get(name) if isinstance(doc, dict) else None
    if not isinstance(entry, dict):
        raise PinError(f"{name}: no entry in {RUNTIME_PINS_FILE}")
    if name == "python":
        if PYTHON_ARCH.get(arch) != entry.get("arch"):
            raise PinError(f"python: no pin for architecture {arch!r}")
        pin = {k: entry.get(k) for k in ("version", "file") + _PIN_KEYS}
    else:
        if entry.get("pin_file") != "config/" + ELECTRON_PIN_FILE:
            raise PinError("electron: pin_file must name config/" + ELECTRON_PIN_FILE)
        edoc = _read_json(config_dir / ELECTRON_PIN_FILE)
        spec = (edoc.get("arch") or {}).get(arch) if isinstance(edoc, dict) else None
        if not isinstance(spec, dict):
            raise PinError(f"electron: no pin for architecture {arch!r}")
        pin = {"version": edoc.get("version"), "file": spec.get("zip_name"),
               "url": spec.get("zip_url"), "sha256": spec.get("zip_sha256"),
               "size": spec.get("zip_size"), "licence": entry.get("licence")}
    url, fname = pin.get("url"), pin.get("file")
    if not isinstance(url, str) or not isinstance(fname, str) \
            or not url.endswith("/" + fname):
        raise PinError(f"{name}: url does not end with the pinned file name")
    return check_runtime_pin(name, pin)


def runtime_fetch(name, opener=None):
    """The default fetch for ensure_runtime: http_stream over RUNTIME_HOSTS
    with an AshLight User-Agent naming the runtime; no cookie. `opener` is
    for tests only."""
    purpose = f"install: {name} runtime download"

    def fetch(url, max_bytes):
        return http_stream(url, max_bytes, RUNTIME_HOSTS, purpose, opener=opener)
    return fetch


def check_flat_members(zf):
    """Raise UnsafeArchive unless every member is a plain file or directory
    with a relative, forward-slash path that stays inside the target (the
    runtime zips carry no top dir)."""
    for info in zf.infolist():
        n = info.filename
        parts = n.split("/")
        mode = (info.external_attr >> 16) & 0o170000
        if not n or "\\" in n or ":" in n or n.startswith("/") or ".." in parts \
                or "\0" in n:
            raise UnsafeArchive(f"unsafe member path: {n!r}")
        if mode == stat.S_IFLNK:
            raise UnsafeArchive(f"symlink member refused: {n!r}")


def _marker(name, pin):
    return {"name": name, "version": pin["version"], "url": pin["url"],
            "sha256": pin["sha256"], "size": pin["size"]}


def runtime_ready(name, pin, dest):
    """True when dest holds AshLight's marker for exactly this pin."""
    try:
        with open(Path(dest) / RUNTIME_MARKER, encoding="utf-8") as f:
            return json.load(f) == _marker(name, pin)
    except (OSError, ValueError):
        return False


def _remove_own(path):
    """Remove a half-made temp file or tree of ours (replaceable data)."""
    path = Path(path)
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def ensure_runtime(name, pin, dest, fetch=None):
    """Fetch, check and unpack one runtime into dest; return dest.

    A dest that already holds the marker of this exact pin is a no-op. The
    pin is checked before any request; the download goes to a temp file
    beside dest and is hashed while it streams; a wrong size or SHA-256
    deletes it and raises HashMismatch with nothing in dest. An unsafe zip
    member raises UnsafeArchive, nothing extracted. A dest without
    AshLight's marker is never removed (PinError). `fetch(url, max_bytes)`
    yields the body in chunks; it defaults to runtime_fetch(name)."""
    check_runtime_pin(name, pin)
    dest = Path(dest)
    if runtime_ready(name, pin, dest):
        return dest
    if dest.exists() and not (dest / RUNTIME_MARKER).is_file():
        raise PinError(f"{name}: target folder holds files AshLight did not make")
    parent = dest.parent
    parent.mkdir(parents=True, exist_ok=True)
    part = parent / f".{dest.name}.download"
    tmp = parent / f".{dest.name}.tmp"
    _remove_own(part)
    _remove_own(tmp)
    fetch = fetch or runtime_fetch(name)
    h = hashlib.sha256()
    got = 0
    try:
        with open(part, "wb") as f:
            for block in fetch(pin["url"], pin["size"]):
                got += len(block)
                if got > pin["size"]:
                    raise HashMismatch(f"{name}: download larger than the pinned size")
                h.update(block)
                f.write(block)
        if got != pin["size"] or h.hexdigest() != pin["sha256"]:
            raise HashMismatch(f"{name}: download does not match its pin")
        with zipfile.ZipFile(part) as zf:
            check_flat_members(zf)
            zf.extractall(tmp)
        with open(tmp / RUNTIME_MARKER, "w", encoding="ascii", newline="\n") as f:
            json.dump(_marker(name, pin), f, indent=1, sort_keys=True)
            f.write("\n")
        if dest.exists():
            shutil.rmtree(dest)  # an older runtime of ours (marker checked above)
        os.replace(tmp, dest)
    finally:
        _remove_own(part)
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
    return dest
