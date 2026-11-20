"""Verify and lay out the payload and the runtimes (REL-INSTALL-PAYLOAD,
finding F-050, DEP-09; docs/plan/05-deployment.md "How an update swaps
versions" step 1 and "Repair").

- verify_zip(zip, sums, size=None): the app zip's SHA-256 against its line
  in SHA256SUMS.txt (and its size against release.json, when given).
- extract(zip, home, version): one top folder AshLight-<version>/, every
  member a safe plain file listed in MANIFEST.json with its size; the
  files go to <home>/app/<version>.partial/, are checked again on disk
  against MANIFEST.json (check_manifest) and the folder is renamed to
  <home>/app/<version>/. Any failure removes the .partial folder and lays
  out nothing. A version folder is never modified after it is laid out:
  an identical one is a no-op, a differing one is refused (repair).
- install_payload(zip, sums, home, version, size=None): both, from ONE
  read of the zip into memory, so the bytes that were hashed are the
  bytes that are extracted.
- check_manifest(dir): the problems of a laid-out folder against its own
  MANIFEST.json (changed, missing, unlisted, link, unsafe path).
- verify_active(home): the 'repair' check of the active version of the
  marker, plus the presence of its two runtime folders.
- pins_from_release(doc), place_runtime(name, pin, home, source_dir=...):
  the two hash-pinned runtimes, from the -RuntimeDir folder of publisher
  zips (checked against the pin before use) or from the fetch, built on
  server/al/pinfetch.py ensure_runtime into <home>/runtime/<name>-<ver>/.

Every request goes to INSTALL_HOSTS only (https, port 443, exact host on
every redirect hop) and carries the User-Agent 'AshLight/<ver>
(installer)'; no cookie. This module runs only in the installer's own
process (plan 05 Design point 13), never in the running core. It never
reads or writes a game folder; standard library only.
"""

import hashlib
import io
import json
import os
import re
import shutil
import stat
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from .. import NAME, VERSION, pinfetch, webfetch
from . import home as homemod

INSTALL_HOSTS = pinfetch.RUNTIME_HOSTS
MANIFEST_NAME = "MANIFEST.json"
BUILD_NAME = "BUILD"
PARTIAL_SUFFIX = ".partial"
MAX_APP_ZIP_BYTES = 16 * 1024 * 1024     # the ship list budget is 2 MB
MAX_UNPACKED_BYTES = 64 * 1024 * 1024    # zip-bomb cap over every member
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_SUMS_BYTES = 64 * 1024
MAX_RELEASE_BYTES = 256 * 1024
MAX_PATH_CHARS = 200
CHUNK = 1024 * 1024

_SEGMENT = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._+-]*$")
_RESERVED = frozenset(["CON", "PRN", "AUX", "NUL"]
                      + ["COM%d" % i for i in range(1, 10)]
                      + ["LPT%d" % i for i in range(1, 10)])
_SUMS_LINE = re.compile(r"^([0-9a-f]{64}) [ *](\S(?:.*\S)?)$")
_PLAIN_VERSION = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.+-]*$")


class PayloadError(Exception):
    """The payload cannot be laid out; nothing was installed."""


class SumsError(PayloadError):
    """SHA256SUMS.txt is unreadable or has no single line for the zip."""


class ManifestError(PayloadError):
    """The zip or a folder does not match its MANIFEST.json."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems[:5]) or "manifest check failed")


# --- the installer User-Agent and its one fetch -----------------------------

def user_agent(version=None):
    """'AshLight/<ver> (installer)': the one User-Agent of every installer
    request, from the bootstrap and this package alike (plan 05 DEP-09)."""
    return f"{NAME}/{version or VERSION} (installer)"


def installer_stream(url, max_bytes, version=None, opener=None,
                     hosts=INSTALL_HOSTS, max_redirects=pinfetch.MAX_REDIRECTS,
                     timeout=pinfetch.TIMEOUT_S):
    """Yield the body of url in chunks. Every hop (redirects followed by
    hand, at most max_redirects) is checked against hosts before it is
    requested; the body is cut off past max_bytes (pinfetch.HashMismatch).
    Headers: the installer User-Agent and Accept, nothing else (no
    cookie). `opener` is for tests only."""
    if not hosts:
        raise webfetch.UrlNotAllowed("no host allow-list given")
    headers = {"User-Agent": user_agent(version), "Accept": "*/*"}
    opener = opener or urllib.request.build_opener(pinfetch._NoRedirect())
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
                    raise pinfetch.HashMismatch(
                        f"download larger than the pinned {max_bytes} bytes")
                yield block
    raise webfetch.FetchError("too many redirects")


def installer_fetch(version=None, opener=None):
    """A fetch(url, max_bytes) for pinfetch.ensure_runtime: installer_stream
    over INSTALL_HOSTS with the installer User-Agent."""
    def fetch(url, max_bytes):
        return installer_stream(url, max_bytes, version=version, opener=opener)
    return fetch


# --- small helpers -----------------------------------------------------------

def safe_path(path):
    """True for a relative '/'-path of plain segments that every OS extracts
    to the same place (no '..', drive, backslash, reserved or odd name);
    the rule of the release build (tools/rel_build.py)."""
    if not isinstance(path, str) or not path or len(path) > MAX_PATH_CHARS:
        return False
    for seg in path.split("/"):
        if not _SEGMENT.match(seg) or seg.endswith("."):
            return False
        if seg.split(".")[0].upper() in _RESERVED:
            return False
    return True


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _read_capped(path, cap, what):
    try:
        with open(path, "rb") as f:
            data = f.read(cap + 1)
    except OSError as e:
        raise PayloadError(f"{what} unreadable: {e.__class__.__name__}") from None
    if len(data) > cap:
        raise PayloadError(f"{what} larger than {cap} bytes")
    return data


def _is_link(path):
    """A symlink or a junction / other reparse point (lstat only)."""
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(st, "st_file_attributes", 0) & reparse)


def _remove_own(path):
    """Remove our own half-made .partial folder (replaceable data: it is
    re-made from the zip). A link or junction is unlinked, never followed."""
    path = Path(path)
    if not os.path.lexists(path):
        return
    if _is_link(path):
        try:
            os.rmdir(path)  # a junction / directory link: the link only
        except OSError:
            os.unlink(path)
    elif path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _check_version(version):
    if not homemod.is_version(version):
        raise PayloadError(f"not a version: {version!r}")
    return version


# --- SHA256SUMS.txt and the zip hash -----------------------------------------

def parse_sums(sums):
    """{name: sha256} from SHA256SUMS.txt (a path, or its bytes / text).
    One '<64 hex>  <name>' line per asset; a malformed line or a name
    listed twice raises SumsError."""
    if isinstance(sums, (bytes, bytearray)):
        data = bytes(sums)
    elif isinstance(sums, str) and "\n" in sums:
        data = sums.encode("ascii", "replace")
    else:
        try:
            data = _read_capped(sums, MAX_SUMS_BYTES, "SHA256SUMS.txt")
        except PayloadError as e:
            raise SumsError(str(e)) from None
    if len(data) > MAX_SUMS_BYTES:
        raise SumsError("SHA256SUMS.txt is too large")
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError:
        raise SumsError("SHA256SUMS.txt is not ASCII") from None
    out = {}
    for raw in text.splitlines():
        line = raw.strip("\r")
        if not line.strip():
            continue
        m = _SUMS_LINE.match(line)
        if m is None:
            raise SumsError("SHA256SUMS.txt has a malformed line")
        digest, name = m.group(1), m.group(2)
        if name in out:
            raise SumsError(f"SHA256SUMS.txt lists {name} twice")
        out[name] = digest
    return out


def _zip_bytes(zip_source):
    """(name, bytes) of an app zip given as a path, or ('', bytes)."""
    if isinstance(zip_source, (bytes, bytearray)):
        data = bytes(zip_source)
        if len(data) > MAX_APP_ZIP_BYTES:
            raise pinfetch.HashMismatch("app zip larger than the cap")
        return "", data
    path = Path(zip_source)
    try:
        if path.stat().st_size > MAX_APP_ZIP_BYTES:
            raise pinfetch.HashMismatch("app zip larger than the cap")
    except OSError as e:
        raise PayloadError(f"app zip unreadable: {e.__class__.__name__}") from None
    return path.name, _read_capped(path, MAX_APP_ZIP_BYTES, "app zip")


def check_zip_bytes(name, data, sums, size=None):
    """Raise unless data has the SHA-256 that SHA256SUMS lists for `name`
    (SumsError when no line names it; pinfetch.HashMismatch on a differing
    hash or, when given, a differing size). Returns the SHA-256."""
    listed = parse_sums(sums)
    if not name or name not in listed:
        raise SumsError(f"SHA256SUMS.txt has no line for {name or 'the zip'}")
    if size is not None and len(data) != size:
        raise pinfetch.HashMismatch(
            f"{name}: {len(data)} bytes, release.json lists {size}")
    digest = _sha256(data)
    if digest != listed[name]:
        raise pinfetch.HashMismatch(f"{name}: SHA-256 differs from SHA256SUMS.txt")
    return digest


def verify_zip(zip_path, sums, size=None):
    """Check the app zip at zip_path against its SHA256SUMS.txt line (and
    its size against release.json when given). Returns {name, sha256,
    size}; raises SumsError or pinfetch.HashMismatch."""
    name, data = _zip_bytes(zip_path)
    digest = check_zip_bytes(name, data, sums, size)
    return {"name": name, "sha256": digest, "size": len(data)}


# --- the zip members against MANIFEST.json -------------------------------------

def _manifest_files(obj):
    files = obj.get("files") if isinstance(obj, dict) else None
    return files if isinstance(files, dict) else None


def _plan_members(zf, version):
    """[(info, rel, sha256, size)] of every member to extract, after the
    member-shape checks and the zip-side MANIFEST.json check. Raises
    pinfetch.UnsafeArchive or ManifestError; nothing is written."""
    top = f"{NAME}-{version}"
    members, folded = {}, set()
    total = 0
    for info in zf.infolist():
        n = info.filename
        head, slash, rel = n.partition("/")
        mode = (info.external_attr >> 16) & 0o170000
        if head != top or not slash or not safe_path(rel) or n.endswith("/"):
            raise pinfetch.UnsafeArchive(f"unsafe member: {n!r}")
        if mode == stat.S_IFLNK or (mode and mode != stat.S_IFREG):
            raise pinfetch.UnsafeArchive(f"not a plain file member: {n!r}")
        if info.flag_bits & 0x1:
            raise pinfetch.UnsafeArchive(f"encrypted member: {n!r}")
        key = rel.lower()
        if rel in members or key in folded:
            raise pinfetch.UnsafeArchive(f"duplicate member: {n!r}")
        members[rel] = info
        folded.add(key)
        total += info.file_size
        if total > MAX_UNPACKED_BYTES:
            raise pinfetch.UnsafeArchive("the zip unpacks past the size cap")
    if MANIFEST_NAME not in members:
        raise ManifestError([f"{MANIFEST_NAME}: missing"])
    if members[MANIFEST_NAME].file_size > MAX_MANIFEST_BYTES:
        raise ManifestError([f"{MANIFEST_NAME}: too large"])
    try:
        obj = json.loads(zf.read(members[MANIFEST_NAME]).decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ManifestError([f"{MANIFEST_NAME}: unreadable"]) from None
    listed = _manifest_files(obj)
    if listed is None:
        raise ManifestError([f"{MANIFEST_NAME}: no files table"])
    problems = []
    if obj.get("version") != version:
        problems.append(f"{MANIFEST_NAME}: version is not {version}")
    plan = []
    for rel in sorted(listed):
        entry = listed[rel]
        if not safe_path(rel) or rel == MANIFEST_NAME:
            problems.append(f"unsafe path: {rel!r}")
            continue
        if rel not in members:
            problems.append(f"missing: {rel}")
            continue
        if not isinstance(entry, dict) or not isinstance(entry.get("sha256"), str) \
                or isinstance(entry.get("size"), bool) \
                or not isinstance(entry.get("size"), int):
            problems.append(f"bad entry: {rel}")
            continue
        if members[rel].file_size != entry["size"]:
            problems.append(f"size differs: {rel}")
            continue
        plan.append((members[rel], rel, entry["sha256"], entry["size"]))
    for rel in sorted(set(members) - set(listed) - {MANIFEST_NAME}):
        problems.append(f"unlisted: {rel}")
    if BUILD_NAME not in listed:
        problems.append(f"{BUILD_NAME}: missing")
    if problems:
        raise ManifestError(problems)
    plan.append((members[MANIFEST_NAME], MANIFEST_NAME, None, None))
    return plan


def _check_build(zf, plan, version):
    info = next(i for i, rel, _h, _s in plan if rel == BUILD_NAME)
    try:
        build = json.loads(zf.read(info).decode("ascii"))
    except (UnicodeDecodeError, ValueError):
        raise ManifestError([f"{BUILD_NAME}: unreadable"]) from None
    if not isinstance(build, dict) or build.get("version") != version:
        raise ManifestError([f"{BUILD_NAME}: version is not {version}"])


def _write_member(zf, info, dest, sha256, size):
    """Stream one member to dest (a new file), hashing it; a differing hash
    or a size past the manifest's raises ManifestError."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    got = 0
    with zf.open(info) as src, open(dest, "xb") as out:
        while True:
            block = src.read(CHUNK)
            if not block:
                break
            got += len(block)
            if size is not None and got > size:
                raise ManifestError([f"size differs: {info.filename}"])
            h.update(block)
            out.write(block)
    if sha256 is not None and (got != size or h.hexdigest() != sha256):
        raise ManifestError([f"changed: {info.filename.partition('/')[2]}"])


# --- the laid-out folder --------------------------------------------------------

def _walk(base):
    """(files, links): the '/'-relative file paths under base and the paths
    of every link or junction found (never followed)."""
    files, links = set(), []
    stack = [(Path(base), "")]
    while stack:
        folder, prefix = stack.pop()
        try:
            entries = sorted(os.scandir(folder), key=lambda e: e.name)
        except OSError:
            continue
        for entry in entries:
            rel = prefix + entry.name
            if _is_link(entry.path):
                links.append(rel)
            elif entry.is_dir(follow_symlinks=False):
                stack.append((Path(entry.path), rel + "/"))
            else:
                files.add(rel)
    return files, sorted(links)


def _is_bytecode(rel):
    parts = rel.split("/")
    return "__pycache__" in parts[:-1] and parts[-1].endswith(".pyc")


def _file_digest(path, cap):
    h = hashlib.sha256()
    got = 0
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            got += len(block)
            if got > cap:
                return None, got
            h.update(block)
    return h.hexdigest(), got


def check_manifest(directory, ignore_bytecode=False):
    """The problems of a laid-out version folder against its own
    MANIFEST.json, as short texts ([] when it matches): 'changed: <p>',
    'missing: <p>', 'unlisted: <p>', 'link: <p>', 'unsafe path: <p>'.
    ignore_bytecode skips __pycache__/*.pyc files the private Python
    writes beside the code it runs (the active-version check only)."""
    base = Path(directory)
    if _is_link(base) or not base.is_dir():
        return ["missing: version folder"]
    try:
        raw = _read_capped(base / MANIFEST_NAME, MAX_MANIFEST_BYTES, MANIFEST_NAME)
        obj = json.loads(raw.decode("utf-8"))
    except (PayloadError, UnicodeDecodeError, ValueError):
        return [f"{MANIFEST_NAME}: unreadable"]
    listed = _manifest_files(obj)
    if listed is None:
        return [f"{MANIFEST_NAME}: no files table"]
    present, links = _walk(base)
    problems = [f"link: {rel}" for rel in links]
    for rel in sorted(listed):
        entry = listed[rel]
        if not safe_path(rel) or rel == MANIFEST_NAME:
            problems.append(f"unsafe path: {rel!r}")
            continue
        if rel not in present:
            problems.append(f"missing: {rel}")
            continue
        size = entry.get("size") if isinstance(entry, dict) else None
        if isinstance(size, bool) or not isinstance(size, int):
            problems.append(f"changed: {rel}")
            continue
        try:
            digest, got = _file_digest(base / rel, size)
        except OSError:
            problems.append(f"changed: {rel}")
            continue
        if got != size or digest != entry.get("sha256"):
            problems.append(f"changed: {rel}")
    for rel in sorted(present - set(listed) - {MANIFEST_NAME}):
        if ignore_bytecode and _is_bytecode(rel):
            continue
        problems.append(f"unlisted: {rel}")
    return problems


# --- extract and install ----------------------------------------------------------

def extract(zip_source, home, version):
    """Lay out the app zip as <home>/app/<version>/ and return that path.

    The zip is checked first (one top folder AshLight-<version>/, plain
    safe members, every member listed in MANIFEST.json with its size, BUILD
    naming the version); then every file is written to
    <home>/app/<version>.partial/, checked on disk with check_manifest and
    the folder renamed. On any failure the .partial folder is removed and
    nothing is laid out. An existing identical version folder (bytecode the
    private Python wrote aside) is returned as it is; a differing one
    raises PayloadError and is left untouched
    (a version folder is never modified after it is laid out)."""
    _check_version(version)
    lay = homemod.layout(home)
    target = lay["app"] / version
    partial = lay["app"] / (version + PARTIAL_SUFFIX)
    _name, data = _zip_bytes(zip_source)
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise pinfetch.UnsafeArchive("not a zip") from None
    with zf:
        plan = _plan_members(zf, version)
        _check_build(zf, plan, version)
        if os.path.lexists(target):
            if _is_link(target) or check_manifest(target, ignore_bytecode=True):
                raise PayloadError(f"version folder {version} exists and differs; "
                                   "run repair")
            return target
        lay["app"].mkdir(parents=True, exist_ok=True)
        _remove_own(partial)
        try:
            partial.mkdir()
            for info, rel, sha256, size in plan:
                _write_member(zf, info, partial.joinpath(*rel.split("/")),
                              sha256, size)
            problems = check_manifest(partial)
            if problems:
                raise ManifestError(problems)
            os.replace(partial, target)
        except BaseException:
            _remove_own(partial)
            raise
    return target


def install_payload(zip_path, sums, home, version, size=None):
    """verify_zip then extract, from one read of the zip: the bytes that
    were hashed are the bytes laid out. Returns <home>/app/<version>."""
    _check_version(version)
    name, data = _zip_bytes(zip_path)
    check_zip_bytes(name, data, sums, size)
    return extract(data, home, version)


# --- repair check -------------------------------------------------------------------

def verify_active(home):
    """The 'repair' check of the active version: {ok, version, problems}.
    Problems: no valid marker, the version folder against its
    MANIFEST.json (changed / missing / unlisted / link; bytecode the
    private Python wrote is ignored) and a runtime folder of the marker
    without AshLight's runtime marker. Reads only; changes nothing."""
    lay = homemod.layout(home)
    doc = homemod.read_marker(lay["home"])
    if doc is None:
        return {"ok": False, "version": None, "problems": ["no valid install marker"]}
    version = doc["version"]
    problems = check_manifest(lay["app"] / version, ignore_bytecode=True)
    for key in pinfetch.RUNTIME_NAMES:
        folder = lay["runtime"] / doc[key]
        if _is_link(folder) or not (folder / pinfetch.RUNTIME_MARKER).is_file():
            problems.append(f"runtime missing: {key}")
    return {"ok": not problems, "version": version, "problems": problems}


# --- runtimes ---------------------------------------------------------------------------

def read_release(path):
    """release.json as a dict (size-capped); PayloadError when unreadable."""
    try:
        doc = json.loads(_read_capped(path, MAX_RELEASE_BYTES, "release.json")
                         .decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise PayloadError("release.json unreadable") from None
    if not isinstance(doc, dict):
        raise PayloadError("release.json is not an object")
    return doc


def _file_name(name, pin):
    """The publisher zip's file name: the last segment of the pinned url
    (and equal to pin['file'] when the pin names one)."""
    fname = urllib.parse.urlsplit(pin["url"]).path.rsplit("/", 1)[-1]
    if not safe_path(fname) or "/" in fname:
        raise pinfetch.PinError(f"{name}: url does not end in a plain file name")
    if pin.get("file") is not None and pin.get("file") != fname:
        raise pinfetch.PinError(f"{name}: file differs from the url's file name")
    return fname


def pins_from_release(doc, version=None):
    """{name: pin} for both runtimes from a release.json document
    ({"runtimes": {"python": {version, url, sha256, size, licence[, file]},
    "electron": {...}}}), each checked with pinfetch.check_runtime_pin.
    When version is given, the document's own version must equal it."""
    if not isinstance(doc, dict):
        raise pinfetch.PinError("release.json is not an object")
    if version is not None and doc.get("version") != version:
        raise pinfetch.PinError(f"release.json is not for version {version}")
    runtimes = doc.get("runtimes")
    if not isinstance(runtimes, dict):
        raise pinfetch.PinError("release.json has no runtimes table")
    pins = {}
    for name in pinfetch.RUNTIME_NAMES:
        pin = runtimes.get(name)
        pinfetch.check_runtime_pin(name, pin)
        _file_name(name, pin)
        pins[name] = dict(pin)
    return pins


def runtime_folder(name, pin):
    """'<name>-<ver>': the runtime folder name the marker records."""
    ver = pin.get("version")
    if not isinstance(ver, str) or not _PLAIN_VERSION.match(ver) or ".." in ver:
        raise pinfetch.PinError(f"{name}: version is not a plain name")
    return f"{name}-{ver}"


def _file_fetch(path):
    """A fetch(url, max_bytes) that yields a local file in chunks."""
    def fetch(_url, max_bytes):
        got = 0
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(CHUNK), b""):
                got += len(block)
                if got > max_bytes:
                    raise pinfetch.HashMismatch("file larger than the pinned size")
                yield block
    return fetch


def place_runtime(name, pin, home, source_dir=None, fetch=None, version=None,
                  opener=None):
    """Place one hash-pinned runtime in <home>/runtime/<name>-<ver>/ and
    return that folder name (for the marker).

    The pin is checked before anything is read or requested. With
    source_dir (install.ps1 -RuntimeDir) the publisher zip named by the
    pin's url must lie there with the pinned size and SHA-256, else
    pinfetch.HashMismatch (or PayloadError when absent) and no request is
    made; without it the zip is fetched over INSTALL_HOSTS with the
    installer User-Agent. pinfetch.ensure_runtime re-hashes the bytes,
    refuses an unsafe member and writes AshLight's runtime marker; a
    folder that already holds the marker of this pin is a no-op."""
    pinfetch.check_runtime_pin(name, pin)
    fname = _file_name(name, pin)
    folder = runtime_folder(name, pin)
    dest = homemod.layout(home)["runtime"] / folder
    if pinfetch.runtime_ready(name, pin, dest):
        return folder  # already placed for exactly this pin: nothing read
    if source_dir is not None:
        src = Path(source_dir) / fname
        if not src.is_file():
            raise PayloadError(f"{name}: {fname} is not in the runtime folder")
        if not pinfetch.file_matches(src, pin["sha256"], pin["size"]):
            raise pinfetch.HashMismatch(f"{name}: {fname} does not match its pin")
        fetch = _file_fetch(src)
    elif fetch is None:
        fetch = installer_fetch(version=version, opener=opener)
    pinfetch.ensure_runtime(name, pin, dest, fetch=fetch)
    return folder


def place_runtimes(pins, home, source_dir=None, version=None, opener=None):
    """place_runtime for both runtimes; {name: folder name}."""
    return {name: place_runtime(name, pins[name], home, source_dir=source_dir,
                                version=version, opener=opener)
            for name in pinfetch.RUNTIME_NAMES}
