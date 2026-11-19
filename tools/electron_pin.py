"""OVL-ELECTRON-PIN: fetch, verify and unpack the pinned Electron runtime.

F-044 / research 0046 R4. Python stdlib only. AshLight's own fetch code
replaces electron's install.js (whose requests do not name AshLight):

- reads the tracked pin file config/electron_pin.json and REFUSES when a
  value is missing or malformed (never guesses one); its version must equal
  the electron entry of app/package.json;
- picks the pin entry of this machine's architecture (x64, arm64); an
  unknown architecture warns and reports "no client" (exit 0: the core
  works without the desktop client);
- downloads the pinned zip from github.com over https (host-allowlisted per
  redirect hop, the AshLight User-Agent, no cookie) into the sidecar
  Cache\\electron\\, bounded to the pinned size; a size or SHA-256 mismatch
  moves the file aside as <name>.rejected and REFUSES (exit 2) BEFORE
  anything is unpacked;
- unpacks with a path guard (relative forward-slash members only, no drive,
  parent or symlink member) to app/node_modules/electron/dist plus the
  path.txt electron's index.js reads, then checks electron.exe against the
  pin (a mismatch removes the new dist and refuses);
- verify-exe: checks electron.exe against the pinned size and SHA-256; the
  full hash runs only when the size or mtime changed since the last good
  check, recorded in the sidecar Build\\electron-exe-check.json.

Setup-time fetch only, not gated by web_data (ruling Q-20: an install-time
fetch is separate from the web_data opt-in, as npm ci is). Not wired into
setup.ps1 / run.ps1 here (OVL-ELECTRON-SETUP does that). Nothing from the
zip is executed by this module.

Usage:
  python tools/electron_pin.py check            validate the pin file only
  python tools/electron_pin.py fetch            download + verify the zip
  python tools/electron_pin.py setup            fetch, unpack, verify the exe
  python tools/electron_pin.py verify-exe [--exe PATH]
Common options: --arch x64|arm64 (default: this machine), --app-dir DIR.
Exit codes: 0 ok / no client, 2 refused (pin, hash, unsafe zip, exe
mismatch), 1 other failure (network, missing package dir).
"""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from server.al import paths, webfetch  # noqa: E402
import tc_pin  # noqa: E402  (fetch and hash helpers, decision 0018)

PIN_FILE = ROOT / "config" / "electron_pin.json"
PACKAGE_JSON = ROOT / "app" / "package.json"
APP_DIR = ROOT / "app"
ARCHES = ("x64", "arm64")
# A GitHub release asset redirects to its asset host (as decision 0027).
ALLOWED_HOSTS = ("github.com", "release-assets.githubusercontent.com",
                 "objects.githubusercontent.com")
UA_PURPOSE = "setup: Electron runtime download"
EXE_NAME = "electron.exe"
CACHE_SUB = "electron"
CHECK_FILE = "electron-exe-check.json"
MAX_REDIRECTS = 3
TIMEOUT_S = 60.0
CHUNK = 1024 * 1024
MAX_ZIP = 512 * 1024 * 1024

RC_OK = tc_pin.RC_OK
RC_FAIL = tc_pin.RC_FAIL
RC_REFUSED = tc_pin.RC_REFUSED

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_VERSION = re.compile(r"^\d+\.\d+\.\d+$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ZIP = re.compile(r"^electron-v(\d+\.\d+\.\d+)-win32-(x64|arm64)\.zip$")
_URL_PREFIX = "https://github.com/electron/electron/releases/download/v"

PinError = tc_pin.PinError
HashMismatch = tc_pin.HashMismatch
UnsafeArchive = tc_pin.UnsafeArchive


class ExeMismatch(Exception):
    """electron.exe does not match its pin: refused."""


def log(msg):
    print(msg, flush=True)


# --- pins ---------------------------------------------------------------

def package_version(package_json=None):
    """The electron entry of app/package.json (dependencies or
    devDependencies), or None."""
    try:
        doc = json.loads(Path(package_json or PACKAGE_JSON).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for key in ("dependencies", "devDependencies"):
        deps = doc.get(key)
        if isinstance(deps, dict) and isinstance(deps.get("electron"), str):
            return deps["electron"]
    return None


def validate_pin(doc, package_json=None):
    """A list of problems (empty when the pin is complete and well formed)."""
    if not isinstance(doc, dict):
        return ["pin file is not a JSON object"]
    out = []
    if doc.get("schema") != 1:
        out.append("schema must be 1")
    ver = doc.get("version")
    if not isinstance(ver, str) or not _VERSION.match(ver):
        out.append("version must be X.Y.Z")
        ver = None
    elif package_json is not False:
        want = package_version(package_json)
        if want != ver:
            out.append(f"version {ver} differs from app/package.json electron {want}")
    for key in ("eol", "verified"):
        if not isinstance(doc.get(key), str) or not _DATE.match(doc[key]):
            out.append(f"{key} must be YYYY-MM-DD")
    arch = doc.get("arch")
    if not isinstance(arch, dict) or not arch:
        out.append("arch: missing")
        return out
    for name, spec in sorted(arch.items()):
        if name not in ARCHES:
            out.append(f"arch {name}: unknown (one of {', '.join(ARCHES)})")
            continue
        out.extend(f"arch {name}: {p}" for p in _validate_arch(name, spec, ver))
    return out


def _validate_arch(name, spec, ver):
    if not isinstance(spec, dict):
        return ["not an object"]
    out = []
    zname = spec.get("zip_name")
    m = _ZIP.match(zname) if isinstance(zname, str) else None
    if not m or m.group(2) != name or (ver and m.group(1) != ver):
        out.append("zip_name must be electron-v<version>-win32-<arch>.zip")
    elif spec.get("zip_url") != f"{_URL_PREFIX}{m.group(1)}/{zname}":
        out.append("zip_url must be the GitHub release asset of zip_name")
    for key in ("zip_sha256", "exe_sha256"):
        if not isinstance(spec.get(key), str) or not _HEX64.match(spec[key]):
            out.append(f"{key} must be 64 lower-case hex")
    for key, cap in (("zip_size", MAX_ZIP), ("exe_size", MAX_ZIP)):
        v = spec.get(key)
        if not isinstance(v, int) or isinstance(v, bool) or not 0 < v <= cap:
            out.append(f"{key} must be a positive byte count")
    return out


def load_pin(path=None, package_json=None):
    """The validated pin document. PinError lists every problem found.
    package_json=False skips the package.json cross-check (tests)."""
    path = Path(path) if path else PIN_FILE
    try:
        doc = json.loads(path.read_bytes().decode("ascii"))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise PinError(f"pin file unreadable: {path.name}: {e}") from e
    problems = validate_pin(doc, package_json)
    if problems:
        raise PinError("pin file incomplete or malformed; refusing rather than "
                       "guessing: " + "; ".join(problems))
    return doc


def machine_arch(machine=None):
    """x64, arm64, or None for an architecture the pin does not cover."""
    m = (platform.machine() if machine is None else machine or "").lower()
    if m in ("amd64", "x86_64", "x64"):
        return "x64"
    if m in ("arm64", "aarch64"):
        return "arm64"
    return None


def arch_spec(doc, arch):
    """The pin entry for arch, or None (warned) when there is none."""
    spec = doc["arch"].get(arch) if arch else None
    if spec is None:
        log(f"warning: no Electron pin for this architecture "
            f"({arch or platform.machine() or 'unknown'}); no client "
            f"(the core and the dashboard work without it)")
    return spec


# --- fetch --------------------------------------------------------------

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_stream(url, max_bytes, hosts=ALLOWED_HOSTS, check=webfetch.check_url):
    """Yield the body of url in chunks with the AshLight User-Agent and no
    cookie. Redirects are followed by hand, each hop passed through `check`
    (https, host in hosts, no userinfo, port 443); the body is cut off past
    max_bytes. `check` is a parameter only so a test can serve over plain
    http on loopback."""
    headers = {"User-Agent": webfetch.user_agent(UA_PURPOSE), "Accept": "*/*"}
    opener = urllib.request.build_opener(_NoRedirect())
    for _ in range(MAX_REDIRECTS + 1):
        check(url, hosts)
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            resp = opener.open(req, timeout=TIMEOUT_S)
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


def cache_dir(environ=None):
    return paths.sidecar_dir("Cache", environ) / CACHE_SUB


def check_file(environ=None):
    return paths.sidecar_dir("Build", environ) / CHECK_FILE


def ensure_zip(spec, environ=None, fetch=None):
    """The verified zip path (cached or downloaded now). A wrong size or
    SHA-256 is quarantined and refused before any unpack."""
    tc_spec = {"archive_sha256": spec["zip_sha256"], "archive_size": spec["zip_size"],
               "archive_url": spec["zip_url"]}
    archive = cache_dir(environ) / spec["zip_name"]
    path, _ = tc_pin.ensure_archive("electron", tc_spec, archive, fetch=fetch or http_stream)
    return path


# --- unpack -------------------------------------------------------------

def check_members(zf):
    """Raise UnsafeArchive unless every member is a plain file or directory
    with a relative, forward-slash path (the Electron zip has no top dir)."""
    for info in zf.infolist():
        n = info.filename
        parts = n.split("/")
        mode = (info.external_attr >> 16) & 0o170000
        if not n or "\\" in n or ":" in n or n.startswith("/") or ".." in parts \
                or "\0" in n:
            raise UnsafeArchive(f"unsafe member path: {n!r}")
        if mode == stat.S_IFLNK:
            raise UnsafeArchive(f"symlink member refused: {n!r}")


def electron_dir(app_dir=None):
    return Path(app_dir or APP_DIR) / "node_modules" / "electron"


def unpack(zip_path, spec, app_dir=None, environ=None):
    """Unpack into node_modules/electron/dist (a temp dir first, swapped in
    only after electron.exe matches the pin) and write path.txt. The npm
    package dir must exist (npm ci --ignore-scripts made it)."""
    pkg = electron_dir(app_dir)
    if not (pkg / "package.json").is_file():
        raise FileNotFoundError(f"the electron npm package is missing ({pkg.name}); "
                                f"run npm ci first")
    tmp = pkg / ".dist.tmp"
    if tmp.exists():
        shutil.rmtree(tmp)  # our own half-made unpack, replaceable from the zip
    with zipfile.ZipFile(zip_path) as zf:
        check_members(zf)
        zf.extractall(tmp)
    try:
        verify_exe(spec, tmp / EXE_NAME, environ=environ, record=False)
    except ExeMismatch:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    dist = pkg / "dist"
    if dist.exists():
        shutil.rmtree(dist)  # replaced by the verified unpack
    os.replace(tmp, dist)
    (pkg / "path.txt").write_bytes(EXE_NAME.encode("ascii"))
    log("electron: unpacked")
    return dist / EXE_NAME


# --- verify-exe ---------------------------------------------------------

def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def _read_check(path):
    try:
        doc = json.loads(path.read_text(encoding="ascii"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def verify_exe(spec, exe, environ=None, record=True):
    """Check exe against the pinned size and SHA-256. The full hash runs
    only when size or mtime differ from the last good check recorded for
    this path and pin; ExeMismatch when it does not match. Returns True
    when a full hash ran."""
    exe = Path(exe)
    try:
        st = exe.stat()
    except OSError as e:
        raise ExeMismatch(f"{EXE_NAME} missing: {e}") from e
    if st.st_size != spec["exe_size"]:
        raise ExeMismatch(f"{EXE_NAME} size {st.st_size} differs from the pinned "
                          f"{spec['exe_size']}; refusing")
    key = str(exe.resolve())
    cfile = check_file(environ)
    last = _read_check(cfile).get(key) if record else None
    if isinstance(last, dict) and last.get("sha256") == spec["exe_sha256"] \
            and last.get("size") == st.st_size and last.get("mtime_ns") == st.st_mtime_ns:
        return False
    got = _sha256(exe)
    if got != spec["exe_sha256"]:
        raise ExeMismatch(f"{EXE_NAME} sha256 {got} differs from the pinned "
                          f"{spec['exe_sha256']}; refusing")
    if record:
        doc = _read_check(cfile)
        doc[key] = {"sha256": got, "size": st.st_size, "mtime_ns": st.st_mtime_ns}
        cfile.parent.mkdir(parents=True, exist_ok=True)
        tmpf = cfile.with_name(cfile.name + ".tmp")
        tmpf.write_text(json.dumps(doc, sort_keys=True, indent=1) + "\n", encoding="ascii")
        os.replace(tmpf, cfile)
    return True


# --- commands -----------------------------------------------------------

def run(cmd, arch=None, app_dir=None, exe=None, pin_path=None, package_json=None,
        environ=None, fetch=None):
    """One command; returns (rc, client) where client is False only when
    this architecture has no pin."""
    try:
        doc = load_pin(pin_path, package_json)
    except PinError as e:
        log(f"refused: {e}")
        return RC_REFUSED, None
    if cmd == "check":
        log(f"pin ok: Electron {doc['version']} ({', '.join(sorted(doc['arch']))}), "
            f"line end of life {doc['eol']}")
        return RC_OK, None
    spec = arch_spec(doc, arch if arch is not None else machine_arch())
    if spec is None:
        return RC_OK, False
    try:
        if cmd == "verify-exe":
            target = Path(exe) if exe else electron_dir(app_dir) / "dist" / EXE_NAME
            full = verify_exe(spec, target, environ=environ)
            log(f"electron.exe ok ({'hashed' if full else 'unchanged since last check'})")
            return RC_OK, True
        zpath = ensure_zip(spec, environ=environ, fetch=fetch)
        if cmd == "fetch":
            return RC_OK, True
        target = unpack(zpath, spec, app_dir=app_dir, environ=environ)
        verify_exe(spec, target, environ=environ)
        log(f"electron {doc['version']}: ready")
        return RC_OK, True
    except (HashMismatch, UnsafeArchive, ExeMismatch, webfetch.UrlNotAllowed) as e:
        log(f"refused: {e}")
        return RC_REFUSED, True
    except (OSError, zipfile.BadZipFile, webfetch.FetchError, urllib.error.URLError) as e:
        log(f"failed: {e}")
        return RC_FAIL, True


def main(argv=None):
    ap = argparse.ArgumentParser(prog="electron_pin", description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("check", "fetch", "setup", "verify-exe"))
    ap.add_argument("--arch", choices=ARCHES, default=None)
    ap.add_argument("--app-dir", default=None)
    ap.add_argument("--exe", default=None, help="verify-exe: the exe to check")
    args = ap.parse_args(argv)
    rc, _ = run(args.cmd, arch=args.arch, app_dir=args.app_dir, exe=args.exe)
    return rc


if __name__ == "__main__":
    sys.exit(main())
