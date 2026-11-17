"""TC-PIN: fetch and verify the optional theorycraft calc component.

Decision 0004 item 3 / decision 0018. Python stdlib only. scripts/setup.ps1
calls `python tools/tc_pin.py setup [--opt-in]`; the step is OFF by default
and runs only when the user opts in (setup.ps1 -TcCalc, or "tc_calc": true in
the gitignored config/local.json).

What it does, all under the AL sidecar (server/al/paths.py):
- reads the tracked pin file config/tc_pins.json and REFUSES when a value is
  missing or malformed (never guesses one);
- downloads each pinned source archive (PoB-PoE2, LuaJIT) from github.com
  over https, host-allowlisted per redirect hop, with a truthful User-Agent,
  into its own Cache dir; verifies size and SHA-256; a mismatch moves the
  file aside as <name>.rejected and REFUSES (exit 2);
- extracts with a path guard (every member under the pinned top dir, no
  absolute / drive / parent / symlink member): PoB into Cache\\pob2\\, LuaJIT
  source into Build\\luajit\\;
- builds luajit.exe from the verified LuaJIT source with a compiler on PATH
  (MSVC cl via msvcbuild.bat, else MinGW); without one it falls back to the
  OPTIONAL pinned portable toolchain (decision 0027: a WinLibs MinGW-w64
  release .zip, SHA-256 + size pinned, fetched into Cache\\toolchain\\ only,
  on PATH only inside the build subprocess); without either it reports
  "source-only" and the core keeps working (the component is optional);
- writes Build\\tc-pins-stamp.json; a re-run with the same pins and the
  outputs present is a no-op with no network request.

Nothing from an archive is imported or executed by this module, except the
LuaJIT build script of the hash-verified source on the user's opt-in.
Exit codes: 0 ok / no-op / off, 2 refused (pin, hash, unsafe archive),
1 other failure (network, extract, build).
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.al import exepin, paths, webfetch  # noqa: E402

COMPONENTS = ("pob2", "luajit")
ALLOWED_HOSTS = ("github.com", "codeload.github.com")
# Decision 0027: a GitHub release asset redirects to its asset host.
TOOLCHAIN = "toolchain"
TOOLCHAIN_HOSTS = ALLOWED_HOSTS + ("release-assets.githubusercontent.com",
                                   "objects.githubusercontent.com")
TOOLCHAIN_TOP = "mingw64"
MAX_REDIRECTS = 3
TIMEOUT_S = 60.0
CHUNK = 1024 * 1024
UA_PURPOSE = "setup: theorycraft calc component download"
OPT_IN_KEY = "tc_calc"
MARKER = ".al-extracted.json"
STAMP_SCHEMA = 1

RC_OK = 0
RC_FAIL = 1
RC_REFUSED = 2

_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_TAG = re.compile(r"^v\d+\.\d+\.\d+$")
_LJVER = re.compile(r"^2\.1\.\d+$")
_RELTAG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]{0,127}$")
_ASSET = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]{0,200}\.zip$")


class PinError(Exception):
    """A pin is missing or malformed: setup refuses rather than guess."""


class HashMismatch(Exception):
    """A downloaded or cached archive does not match its pin: refused."""


class UnsafeArchive(Exception):
    """An archive member would land outside its pinned top dir: refused."""


def log(msg):
    print(msg, flush=True)


# --- pins ---------------------------------------------------------------

def pins_file():
    return paths.tc_pins_file()


def load_pins(path=None):
    """The validated pin document. PinError lists every problem found."""
    path = Path(path) if path else pins_file()
    try:
        raw = path.read_bytes()
        doc = json.loads(raw.decode("ascii"))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise PinError(f"pin file unreadable: {path.name}: {e}") from e
    problems = validate_pins(doc)
    if problems:
        raise PinError("pin file incomplete or malformed; refusing rather than "
                       "guessing: " + "; ".join(problems))
    return doc


def validate_pins(doc):
    """A list of problems (empty when every pin is complete and well formed)."""
    if not isinstance(doc, dict):
        return ["pin file is not a JSON object"]
    out = []
    if doc.get("schema") != 1:
        out.append("schema must be 1")
    for name in COMPONENTS:
        spec = doc.get(name)
        if not isinstance(spec, dict):
            out.append(f"{name}: missing")
            continue
        out.extend(f"{name}: {p}" for p in _validate_spec(name, spec))
    if TOOLCHAIN in doc:  # optional (decision 0027)
        spec = doc[TOOLCHAIN]
        if not isinstance(spec, dict):
            out.append(f"{TOOLCHAIN}: not an object")
        else:
            out.extend(f"{TOOLCHAIN}: {p}" for p in _validate_toolchain(spec))
    return out


def _validate_toolchain(spec):
    """The portable build toolchain pin: a GitHub release .zip asset."""
    out = []
    repo, tag, asset = spec.get("repo"), spec.get("tag"), spec.get("asset")
    if not isinstance(repo, str) or not _REPO.match(repo):
        out.append("repo missing or malformed")
    if not isinstance(tag, str) or not _RELTAG.match(tag):
        out.append("tag missing or malformed")
    if not isinstance(asset, str) or not _ASSET.match(asset):
        out.append("asset must be a plain .zip file name")
    sha = spec.get("archive_sha256")
    if not isinstance(sha, str) or not _HEX64.match(sha):
        out.append("archive_sha256 must be 64 lower-case hex")
    size = spec.get("archive_size")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        out.append("archive_size must be a positive integer")
    if not out:
        want = f"https://github.com/{repo}/releases/download/{tag}/{asset}"
        if spec.get("archive_url") != want:
            out.append("archive_url must be the github release download URL")
    if spec.get("top_dir") != TOOLCHAIN_TOP:
        out.append(f"top_dir must be {TOOLCHAIN_TOP}")
    return out


def _validate_spec(name, spec):
    out = []
    repo = spec.get("repo")
    commit = spec.get("commit")
    if not isinstance(repo, str) or not _REPO.match(repo):
        out.append("repo missing or malformed")
        repo = None
    if not isinstance(commit, str) or not _HEX40.match(commit):
        out.append("commit must be a 40-hex lower-case sha")
        commit = None
    sha = spec.get("archive_sha256")
    if not isinstance(sha, str) or not _HEX64.match(sha):
        out.append("archive_sha256 must be 64 lower-case hex")
    size = spec.get("archive_size")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        out.append("archive_size must be a positive integer")
    if name == "pob2":
        tag = spec.get("tag")
        if not isinstance(tag, str) or not _TAG.match(tag):
            out.append("tag must look like vX.Y.Z")
    if name == "luajit":
        ver = spec.get("version")
        if not isinstance(ver, str) or not _LJVER.match(ver):
            out.append("version must look like 2.1.<commit epoch>")
    url = spec.get("archive_url")
    if repo and commit:
        want = f"https://github.com/{repo}/archive/{commit}.zip"
        if url != want:
            out.append("archive_url must be the commit-addressed github archive URL")
        top = spec.get("top_dir")
        if top != f"{repo.split('/')[1]}-{commit}":
            out.append("top_dir must be <repo name>-<commit>")
    elif not isinstance(url, str) or not url:
        out.append("archive_url missing")
    return out


def pins_digest(doc):
    """SHA-256 of the canonical pin values (comments excluded)."""
    core = {k: doc[k] for k in ("schema",) + COMPONENTS}
    text = json.dumps(core, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("ascii")).hexdigest()


# --- layout -------------------------------------------------------------

def layout(doc, environ=None):
    """Every path this step touches, all inside the AL sidecar."""
    p = paths.all_runtime_paths(environ)
    pob = doc["pob2"]
    lj = doc["luajit"]
    lj_src = p["luajit_build"] / lj["top_dir"]
    return {
        "pob2_cache": p["pob2_cache"],
        "pob2_archive": p["pob2_cache"] / f"{pob['top_dir']}.zip",
        "pob2_checkout": p["pob2_cache"] / pob["top_dir"],
        "luajit_cache": p["luajit_cache"],
        "luajit_archive": p["luajit_cache"] / f"{lj['top_dir']}.zip",
        "luajit_build": p["luajit_build"],
        "luajit_source": lj_src,
        "luajit_exe": lj_src / "src" / "luajit.exe",
        "stamp": p["tc_stamp"],
        "temp": p["temp"],
        # decision 0027: the optional portable build toolchain
        "toolchain_cache": p["toolchain_cache"],
        "toolchain_archive": p["toolchain_cache"] / "toolchain.zip",
        "toolchain_root": p["toolchain_cache"] / TOOLCHAIN_TOP,
        "toolchain_bin": p["toolchain_cache"] / TOOLCHAIN_TOP / "bin",
    }


# --- download and verify ------------------------------------------------

def file_matches(path, sha256, size):
    """True when the file exists with exactly this size and SHA-256."""
    try:
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


def http_stream(url, max_bytes, hosts=ALLOWED_HOSTS):
    """Yield the body of url in chunks. Redirects are followed by hand, each
    hop checked against hosts (default ALLOWED_HOSTS) (https, no userinfo, port 443); the
    body is cut off past max_bytes. No cookie is ever sent."""
    headers = {"User-Agent": webfetch.user_agent(UA_PURPOSE), "Accept": "*/*"}
    opener = urllib.request.build_opener(_NoRedirect())
    for _ in range(MAX_REDIRECTS + 1):
        webfetch.check_url(url, hosts)
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


def _quarantine(path):
    """Move a bad archive aside (replaceable data; kept for inspection)."""
    bad = path.with_name(path.name + ".rejected")
    try:
        os.replace(path, bad)
    except OSError:
        pass
    return bad


def ensure_archive(name, spec, archive, fetch=None):
    """The verified archive path and whether it was downloaded now.
    A cached file that no longer matches is refused (quarantined); the next
    run downloads afresh."""
    sha, size = spec["archive_sha256"], spec["archive_size"]
    if archive.exists():
        if file_matches(archive, sha, size):
            log(f"{name}: cached archive verified (sha256 ok)")
            return archive, False
        bad = _quarantine(archive)
        raise HashMismatch(f"{name}: cached archive does not match its pin; moved to "
                           f"{bad.name}; refusing")
    archive.parent.mkdir(parents=True, exist_ok=True)
    part = archive.with_name(archive.name + ".part")
    fetch = fetch or http_stream
    log(f"{name}: downloading {spec['archive_url']} ({size} bytes)")
    h = hashlib.sha256()
    got = 0
    next_pct = 25
    with open(part, "wb") as out:
        for block in fetch(spec["archive_url"], size):
            got += len(block)
            if got > size:
                break
            h.update(block)
            out.write(block)
            while next_pct <= 100 and got * 100 >= next_pct * size:
                log(f"{name}: {next_pct}%")
                next_pct += 25
    if got != size or h.hexdigest() != sha:
        bad = _quarantine(part)
        raise HashMismatch(f"{name}: download does not match its pin (size {got} vs {size}, "
                           f"sha256 {h.hexdigest()} vs {sha}); moved to {bad.name}; refusing")
    os.replace(part, archive)
    log(f"{name}: archive verified (sha256 ok)")
    return archive, True


# --- extract ------------------------------------------------------------

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


def read_marker(target):
    try:
        return json.loads((target / MARKER).read_text(encoding="ascii"))
    except (OSError, ValueError):
        return None


def ensure_extracted(name, spec, archive, parent):
    """Extract archive into parent/<top_dir> once; a marker carrying the
    archive sha makes a re-run a no-op."""
    top = spec["top_dir"]
    target = parent / top
    marker = read_marker(target)
    if marker and marker.get("archive_sha256") == spec["archive_sha256"]:
        log(f"{name}: extracted tree present (no-op)")
        return target, False
    parent.mkdir(parents=True, exist_ok=True)
    tmp = parent / f".{top}.tmp"
    if tmp.exists():
        shutil.rmtree(tmp)  # our own half-made extract, replaceable from the archive
    with zipfile.ZipFile(archive) as zf:
        check_members(zf, top)
        zf.extractall(tmp)
    if target.exists():
        shutil.rmtree(target)  # stale tree without a matching marker, replaceable
    os.replace(tmp / top, target)
    shutil.rmtree(tmp, ignore_errors=True)
    (target / MARKER).write_text(json.dumps({
        "component": name, "commit": spec.get("commit") or spec.get("tag"),
        "archive_sha256": spec["archive_sha256"]}, sort_keys=True) + "\n", encoding="ascii")
    log(f"{name}: extracted")
    return target, True


# --- LuaJIT build -------------------------------------------------------

def build_plan(which=None, environ=None):
    """The build command for the verified LuaJIT source, or None when no
    supported compiler is on PATH. Runs in <source>/src. AUDIT-EXE-PATH:
    cmd.exe by its System32 path, PATH tools only from absolute PATH entries
    (never the current directory)."""
    find = which or (lambda name: exepin.which_abs(name, environ))
    # AUDIT pass 2 (P2-B2): a static build is one luajit.exe with the VM
    # inside, so the SHA-256 exepin records covers everything that runs (the
    # default dynamic build loads an unhashed lua51.dll beside it).
    if find("cl"):
        return [str(exepin.system_tool("cmd.exe")), "/d", "/c", "msvcbuild.bat",
                "static"]
    make = find("mingw32-make")
    if make and find("gcc"):
        return [str(make), "BUILDMODE=static"]
    return None


def toolchain_env(bin_dir, temp):
    """A minimal build env for the pinned toolchain: its bin first, then the
    Windows system dirs only. No MSYS / Git-for-Windows shell or TERM leaks
    in (LuaJIT's Makefile would then take the POSIX host path), and nothing
    outside this subprocess sees the PATH change (decision 0027)."""
    root = os.environ.get("SystemRoot") or os.environ.get("SYSTEMROOT") or "C" + ":\\Windows"
    env = {k: os.environ[k] for k in ("SystemDrive", "COMSPEC", "PATHEXT",
                                      "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
                                      "USERPROFILE", "LOCALAPPDATA")
           if k in os.environ}
    env["SystemRoot"] = root
    env["OS"] = "Windows_NT"
    env["PATH"] = os.pathsep.join([str(bin_dir), str(Path(root) / "System32"), root])
    env["TEMP"] = env["TMP"] = str(temp)
    return env


def toolchain_plan(bin_dir):
    """The MinGW build command from the pinned toolchain, or None."""
    make, gcc = Path(bin_dir) / "mingw32-make.exe", Path(bin_dir) / "gcc.exe"
    if make.is_file() and gcc.is_file():
        return [str(make), "BUILDMODE=static"]
    return None


def ensure_toolchain(doc, lay, fetch=None):
    """Fetch, verify and extract the pinned portable toolchain (decision
    0027). Returns its bin dir. Raises like the other components."""
    spec = doc[TOOLCHAIN]
    marker = read_marker(lay["toolchain_root"])
    if marker and marker.get("archive_sha256") == spec["archive_sha256"]:
        log(f"{TOOLCHAIN}: extracted tree present (no-op)")
    else:
        fetch = fetch or (lambda url, n: http_stream(url, n, TOOLCHAIN_HOSTS))
        path, _ = ensure_archive(TOOLCHAIN, spec, lay["toolchain_archive"], fetch)
        ensure_extracted(TOOLCHAIN, spec, path, lay["toolchain_cache"])
    return lay["toolchain_bin"]


def ensure_luajit(lay, which=None, run=subprocess.run, environ=None, toolchain=None):
    """'ready' when luajit.exe exists AND matches the SHA-256 recorded when
    this step built it (built now or before), 'source-only' when no compiler
    is available. An existing luajit.exe without a matching record is not
    trusted (AUDIT-EXE-PATH): it is rebuilt when a compiler exists.
    Raises RuntimeError on a failed build."""
    exe = lay["luajit_exe"]
    if exepin.verified(exe):
        log("luajit: luajit.exe present and verified (no-op)")
        return "ready"
    if exe.is_file():
        log("luajit: luajit.exe present but not recorded by this step; not trusted")
    plan = build_plan(which, environ)
    env = None
    if plan is None and toolchain is not None:
        log("luajit: no compiler on PATH; using the pinned portable toolchain")
        bin_dir = toolchain()
        plan = toolchain_plan(bin_dir)
        if plan is None:
            raise RuntimeError("pinned toolchain lacks mingw32-make.exe / gcc.exe")
        env = toolchain_env(bin_dir, lay["temp"])
    if plan is None:
        log("luajit: no compiler on PATH (MSVC cl or MinGW gcc); source verified, "
            "build skipped. Re-run setup from a Developer PowerShell to build it.")
        return "source-only"
    if env is None:
        env = dict(os.environ if environ is None else environ)
        env["TEMP"] = env["TMP"] = str(lay["temp"])
    log(f"luajit: building with {Path(plan[0]).name}")
    r = run(plan, cwd=str(lay["luajit_source"] / "src"), env=env,
            capture_output=True, timeout=1800)
    if r.returncode != 0 or not exe.is_file():
        raise RuntimeError(f"luajit build failed (rc {r.returncode})")
    exepin.record(exe)
    log("luajit: built (sha256 recorded)")
    return "ready"


# --- stamp and orchestration ------------------------------------------

def read_stamp(path):
    try:
        return json.loads(Path(path).read_text(encoding="ascii"))
    except (OSError, ValueError):
        return None


def is_noop(doc, lay):
    """True when a previous run finished with these exact pins and its
    outputs are still present: nothing to do, no network."""
    stamp = read_stamp(lay["stamp"])
    if not stamp or stamp.get("schema") != STAMP_SCHEMA:
        return False
    if stamp.get("pins_sha256") != pins_digest(doc) or stamp.get("status") != "ready":
        return False
    for key, name in (("pob2_checkout", "pob2"), ("luajit_source", "luajit")):
        m = read_marker(lay[key])
        if not m or m.get("archive_sha256") != doc[name]["archive_sha256"]:
            return False
    return exepin.verified(lay["luajit_exe"])


def write_stamp(doc, lay, status):
    lay["stamp"].parent.mkdir(parents=True, exist_ok=True)
    body = {
        "schema": STAMP_SCHEMA,
        "pins_sha256": pins_digest(doc),
        "status": status,
        "pob2": {"tag": doc["pob2"]["tag"], "commit": doc["pob2"]["commit"]},
        "luajit": {"version": doc["luajit"]["version"], "commit": doc["luajit"]["commit"]},
    }
    lay["stamp"].write_text(json.dumps(body, indent=1, sort_keys=True) + "\n", encoding="ascii")


def opted_in(switch, local_cfg):
    """The step runs only on an explicit opt-in: the setup switch, or
    "tc_calc": true (a real boolean) in config/local.json."""
    return bool(switch) or local_cfg.get(OPT_IN_KEY) is True


def run_setup(doc, environ=None, fetch=None, which=None, run=subprocess.run,
              toolchain_fetch=None):
    """Fetch, verify, extract and (when possible) build. Returns the status
    'noop', 'ready' or 'source-only'."""
    lay = layout(doc, environ)
    if is_noop(doc, lay):
        log("tc calc component up to date (no-op)")
        return "noop"
    for name, archive, parent, tree in (
            ("pob2", "pob2_archive", "pob2_cache", "pob2_checkout"),
            ("luajit", "luajit_archive", "luajit_build", "luajit_source")):
        spec = doc[name]
        marker = read_marker(lay[tree])
        if marker and marker.get("archive_sha256") == spec["archive_sha256"]:
            log(f"{name}: extracted tree present (no-op)")
            continue
        path, _ = ensure_archive(name, spec, lay[archive], fetch)
        ensure_extracted(name, spec, path, lay[parent])
    toolchain = None
    if TOOLCHAIN in doc:
        def toolchain():
            return ensure_toolchain(doc, lay, toolchain_fetch)
    status = ensure_luajit(lay, which=which, run=run, environ=environ,
                           toolchain=toolchain)
    write_stamp(doc, lay, status)
    log(f"tc calc component: {status} (PoB-PoE2 {doc['pob2']['tag']}, "
        f"LuaJIT {doc['luajit']['version']})")
    return status


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tc_pin", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup", help="fetch and verify (only when opted in)")
    s.add_argument("--opt-in", action="store_true",
                   help="the setup.ps1 -TcCalc switch (else config/local.json tc_calc)")
    sub.add_parser("check", help="validate the pin file only")
    args = ap.parse_args(argv)
    try:
        doc = load_pins()
    except PinError as e:
        log(f"refused: {e}")
        return RC_REFUSED
    if args.cmd == "check":
        log(f"pins ok: PoB-PoE2 {doc['pob2']['tag']} {doc['pob2']['commit'][:12]}, "
            f"LuaJIT {doc['luajit']['version']} {doc['luajit']['commit'][:12]}")
        return RC_OK
    if not opted_in(args.opt_in, paths.load_local_config()):
        log("tc calc component off (opt in with setup.ps1 -TcCalc or "
            "\"tc_calc\": true in config/local.json); nothing fetched")
        return RC_OK
    try:
        run_setup(doc)
    except (HashMismatch, UnsafeArchive, webfetch.UrlNotAllowed) as e:
        log(f"refused: {e}")
        return RC_REFUSED
    except (OSError, RuntimeError, zipfile.BadZipFile, webfetch.FetchError,
            urllib.error.URLError) as e:
        log(f"failed: {e}")
        return RC_FAIL
    return RC_OK


if __name__ == "__main__":
    sys.exit(main())
