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
  outputs present is a no-op with no network request;
- TC-PIN-POLICY (F-180, decision 0018 pin policy, decision 0027 amendment
  2026-11-21): once luajit.exe is built and verified ('ready', or a no-op
  run) the portable toolchain tree and archive are deleted directly (they
  are AshLight's own re-fetchable cache files under the sidecar, not player
  data); a later rebuild fetches them again;
- TC-CALC-VERIFY-PIN (F-139, decision 0018 amendment 2026-11-20): the pin
  carries a content digest per component (content_sha256: the tree_digest
  form over every file under the top dir) and, for PoB, a digest of its
  runnable Lua files (lua_sha256). A re-generated archive whose bytes differ
  from archive_sha256 is accepted only when its contents give the pinned
  content digest (read from the zip under the path guard, never run; at most
  CONTENT_SLACK x the pinned size); every extract is checked against the
  content digest before its marker is written; PoB's Lua files are re-hashed
  on every re-run (no-op included) and the LuaJIT source tree right before
  each build, and a mismatch re-extracts from the verified archive;
- TC-CALC-OPTIN (F-132): with --opt-in (setup.ps1 -TcCalc) and a verified
  install (status 'ready', or 'noop' for one already verified), turns the
  calc on: set_opt_in_flag() merges "tc_calc": true into config/local.json,
  keeping every other key (never seeding defaults). A refusal, a failure or
  a 'source-only' result leaves the file exactly as it was. One run of the
  switch is the whole opt-in; no second edit of the config.

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
import subprocess
import sys
import urllib.error
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.al import acl, exepin, jsonfile, paths, webfetch  # noqa: E402
# REL-PINFETCH: the shared hash-pinned fetch / verify / extract helpers; the
# names stay importable from this module (tests and tools/electron_pin.py).
from server.al.pinfetch import (  # noqa: E402,F401
    HashMismatch, UnsafeArchive, _NoRedirect, check_members, file_matches)
from server.al import pinfetch  # noqa: E402

COMPONENTS = ("pob2", "luajit")
ALLOWED_HOSTS = ("github.com", "codeload.github.com")
# Decision 0027: a GitHub release asset redirects to its asset host.
TOOLCHAIN = "toolchain"
TOOLCHAIN_HOSTS = ALLOWED_HOSTS + ("release-assets.githubusercontent.com",
                                   "objects.githubusercontent.com")
TOOLCHAIN_TOP = "mingw64"
MAX_REDIRECTS = pinfetch.MAX_REDIRECTS
TIMEOUT_S = pinfetch.TIMEOUT_S
CHUNK = pinfetch.CHUNK
UA_PURPOSE = "setup: theorycraft calc component download"
OPT_IN_KEY = "tc_calc"
MARKER = ".al-extracted.json"
STAMP_SCHEMA = 1
# TC-CALC-VERIFY-PIN: the content digests (decision 0018 amendment 2026-11-20)
CONTENT_KEY = "content_sha256"
LUA_KEY = "lua_sha256"
LUA_COMPONENT = "pob2"  # the component whose runnable Lua files are pinned
# a re-generated archive is read up to this many times its pinned size
CONTENT_SLACK = 2

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


class ConfigError(Exception):
    """config/local.json cannot be read as a JSON object: the opt-in flag
    is not written and the file is left as it was."""


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
    keys = (CONTENT_KEY, LUA_KEY) if name == LUA_COMPONENT else (CONTENT_KEY,)
    for key in keys:
        val = spec.get(key)
        if not isinstance(val, str) or not _HEX64.match(val):
            out.append(f"{key} must be 64 lower-case hex")
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

def http_stream(url, max_bytes, hosts=ALLOWED_HOSTS):
    """Yield the body of url in chunks (pinfetch.http_stream): each redirect
    hop checked against hosts (default ALLOWED_HOSTS), at most MAX_REDIRECTS,
    the body cut off past max_bytes, this step's User-Agent purpose."""
    return pinfetch.http_stream(url, max_bytes, hosts, UA_PURPOSE,
                                max_redirects=MAX_REDIRECTS, timeout=TIMEOUT_S)


def _quarantine(path):
    """Move a bad archive aside (pinfetch.quarantine)."""
    return pinfetch.quarantine(path)


def content_matches(name, spec, archive):
    """True when the archive's contents (archive_digests) give the pinned
    content digest. Only for a spec that carries one; an unreadable or
    unsafe archive is no match."""
    want = spec.get(CONTENT_KEY)
    if not want:
        return False
    try:
        got = archive_digests(archive, spec["top_dir"])[CONTENT_KEY]
    except (OSError, UnsafeArchive, zipfile.BadZipFile, ValueError) as e:
        log(f"{name}: archive contents unreadable ({type(e).__name__})")
        return False
    return got == want


def ensure_archive(name, spec, archive, fetch=None):
    """The verified archive path and whether it was downloaded now.
    A cached file that no longer matches is refused (quarantined); the next
    run downloads afresh. TC-CALC-VERIFY-PIN: for a spec with a content
    digest, an archive whose bytes differ from the pin (GitHub re-generated
    it) is accepted only when its contents give that digest; a spec without
    one (the toolchain, the Electron zip) stays byte-strict."""
    sha, size = spec["archive_sha256"], spec["archive_size"]
    has_content = bool(spec.get(CONTENT_KEY))
    if archive.exists():
        if file_matches(archive, sha, size):
            log(f"{name}: cached archive verified (sha256 ok)")
            return archive, False
        if has_content and archive.stat().st_size <= size * CONTENT_SLACK \
                and content_matches(name, spec, archive):
            log(f"{name}: cached archive bytes differ from the pin; contents match "
                "the pinned content digest (accepted)")
            return archive, False
        bad = _quarantine(archive)
        raise HashMismatch(f"{name}: cached archive does not match its pin; moved to "
                           f"{bad.name}; refusing")
    archive.parent.mkdir(parents=True, exist_ok=True)
    part = archive.with_name(archive.name + ".part")
    fetch = fetch or http_stream
    cap = size * CONTENT_SLACK if has_content else size
    log(f"{name}: downloading {spec['archive_url']} ({size} bytes)")
    h = hashlib.sha256()
    got = 0
    next_pct = 25
    with open(part, "wb") as out:
        for block in fetch(spec["archive_url"], cap):
            got += len(block)
            if got > cap:
                break
            h.update(block)
            out.write(block)
            while next_pct <= 100 and got * 100 >= next_pct * size:
                log(f"{name}: {next_pct}%")
                next_pct += 25
    if got == size and h.hexdigest() == sha:
        os.replace(part, archive)
        log(f"{name}: archive verified (sha256 ok)")
        return archive, True
    if has_content and got <= cap and content_matches(name, spec, part):
        os.replace(part, archive)
        log(f"{name}: archive bytes differ from the pin (size {got}, sha256 "
            f"{h.hexdigest()}); contents match the pinned content digest (accepted)")
        return archive, True
    bad = _quarantine(part)
    raise HashMismatch(f"{name}: download does not match its pin (size {got} vs {size}, "
                       f"sha256 {h.hexdigest()} vs {sha}"
                       + (", contents differ from the content digest" if has_content else "")
                       + f"); moved to {bad.name}; refusing")


# --- extract ------------------------------------------------------------

def read_marker(target):
    try:
        return json.loads((target / MARKER).read_text(encoding="ascii"))
    except (OSError, ValueError):
        return None


def is_lua(rel):
    """A runnable Lua file of a PoB checkout (lua_sha256 covers these)."""
    return rel.lower().endswith(".lua")


def _digest(entries):
    """The outer SHA-256 over (relative path, size, sha256) entries, sorted
    by path: the one form of tree_digest and archive_digests."""
    outer = hashlib.sha256()
    for rel, size, sha in sorted(entries):
        outer.update(f"{rel}\0{size}\0{sha}\n".encode("utf-8"))
    return outer.hexdigest()


def _hash_stream(f):
    h, size = hashlib.sha256(), 0
    for block in iter(lambda: f.read(CHUNK), b""):
        h.update(block)
        size += len(block)
    return size, h.hexdigest()


def _tree_entries(target, select=None):
    target = Path(target)
    out = []
    for dirpath, dirnames, filenames in os.walk(target):
        dirnames.sort()
        for fn in filenames:
            p = Path(dirpath) / fn
            rel = p.relative_to(target).as_posix()
            if rel == MARKER or (select is not None and not select(rel)):
                continue
            with open(p, "rb") as f:
                size, sha = _hash_stream(f)
            out.append((rel, size, sha))
    return out


def tree_digest(target, select=None):
    """SHA-256 over every file under target (sorted relative path, size and
    content hash; the marker itself excluded); `select(rel)` narrows it to
    some files (is_lua). AREA-AUDIT P3-10: the toolchain tree is re-hashed
    against its marker before each build. TC-CALC-VERIFY-PIN: the same value
    over an extracted component is its pinned content_sha256."""
    return _digest(_tree_entries(target, select))


def archive_digests(archive, top_dir):
    """{content_sha256, lua_sha256} of a zip's contents under top_dir, in
    the tree_digest form, so they equal tree_digest of a faithful extract.
    Members are read as data only, after check_members (path guard); a
    duplicate member path is refused (UnsafeArchive)."""
    prefix = top_dir + "/"
    entries, seen = [], set()
    with zipfile.ZipFile(archive) as zf:
        check_members(zf, top_dir)
        for info in zf.infolist():
            if info.is_dir():
                continue
            rel = info.filename[len(prefix):]
            if not rel or rel == MARKER:
                continue
            if rel in seen:
                raise UnsafeArchive(f"duplicate member path: {info.filename!r}")
            seen.add(rel)
            with zf.open(info) as f:
                size, sha = _hash_stream(f)
            entries.append((rel, size, sha))
    return {CONTENT_KEY: _digest(entries),
            LUA_KEY: _digest(e for e in entries if is_lua(e[0]))}


def lua_ok(spec, checkout):
    """True when PoB's runnable Lua files under checkout give the pinned
    lua_sha256 (always True for a spec without one)."""
    want = spec.get(LUA_KEY)
    return not want or tree_digest(checkout, select=is_lua) == want


def ensure_extracted(name, spec, archive, parent, force=False):
    """Extract archive into parent/<top_dir> once; a marker carrying the
    archive sha makes a re-run a no-op (unless `force`). The marker also
    records the extracted tree's digest (tree_digest)."""
    top = spec["top_dir"]
    target = parent / top
    marker = read_marker(target)
    if not force and marker and marker.get("archive_sha256") == spec["archive_sha256"]:
        log(f"{name}: extracted tree present (no-op)")
        return target, False
    pinfetch.extract_safe(archive, top, parent)
    tree = tree_digest(target)
    want = spec.get(CONTENT_KEY)
    if want and tree != want:
        # our own extract of a refused archive: replaceable, never vouched for
        shutil.rmtree(target, ignore_errors=True)
        raise HashMismatch(f"{name}: extracted tree does not match the pinned content "
                           f"digest ({tree} vs {want}); refusing")
    (target / MARKER).write_text(json.dumps({
        "component": name, "commit": spec.get("commit") or spec.get("tag"),
        "archive_sha256": spec["archive_sha256"], "tree_sha256": tree},
        sort_keys=True) + "\n", encoding="ascii")
    log(f"{name}: extracted")
    return target, True


def ensure_source(name, spec, lay, keys, fetch=None):
    """TC-CALC-VERIFY-PIN: re-hash an extracted source tree against its
    pinned content digest (the marker must name the pinned archive too); a
    mismatch, an added or changed file, or a missing marker re-extracts it
    from the verified archive. keys = (archive, parent, tree) layout keys."""
    archive, parent, tree = keys
    marker = read_marker(lay[tree])
    want = spec.get(CONTENT_KEY)
    if marker and marker.get("archive_sha256") == spec["archive_sha256"] \
            and (not want or tree_digest(lay[tree]) == want):
        log(f"{name}: source tree re-hashed (content digest ok)")
        return lay[tree]
    log(f"{name}: source tree does not match its content digest; re-extracting")
    path, _ = ensure_archive(name, spec, lay[archive], fetch)
    target, _ = ensure_extracted(name, spec, path, lay[parent], force=True)
    return target


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
    0027). Returns its bin dir. Raises like the other components.
    AREA-AUDIT P3-10: called right before each build; the tree is re-hashed
    against the digest its marker recorded at extraction, and any change (or
    a marker without a digest) re-extracts it from the verified archive."""
    spec = doc[TOOLCHAIN]
    root = lay["toolchain_root"]
    marker = read_marker(root)
    if marker and marker.get("archive_sha256") == spec["archive_sha256"] \
            and marker.get("tree_sha256") == tree_digest(root):
        log(f"{TOOLCHAIN}: extracted tree present and re-hashed (no-op)")
    else:
        if marker:
            log(f"{TOOLCHAIN}: extracted tree does not match its marker; re-extracting")
        fetch = fetch or (lambda url, n: http_stream(url, n, TOOLCHAIN_HOSTS))
        path, _ = ensure_archive(TOOLCHAIN, spec, lay["toolchain_archive"], fetch)
        ensure_extracted(TOOLCHAIN, spec, path, lay["toolchain_cache"], force=True)
    return lay["toolchain_bin"]


def _rm_readonly(func, path, _exc):
    """shutil.rmtree onerror: clear a read-only bit once and retry."""
    os.chmod(path, 0o700)
    func(path)


def remove_toolchain(lay):
    """TC-PIN-POLICY: delete the portable toolchain tree and archive after a
    verified luajit.exe (decision 0027 amendment 2026-11-21). A direct
    delete, not the Recycle Bin: both are AshLight's own re-fetchable cache
    files under the sidecar Cache. Quarantined *.rejected files are kept as
    evidence. Returns True when anything was removed; a delete that fails is
    logged and never fails setup (the next verified run tries again)."""
    root, archive = lay["toolchain_root"], lay["toolchain_archive"]
    cache = lay["toolchain_cache"]
    removed = False
    for path in (root, archive, archive.with_name(archive.name + ".part")):
        if path.parent != cache or not (path.exists() or path.is_symlink()):
            continue
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path, onerror=_rm_readonly)
            else:
                path.unlink()
            removed = True
        except OSError as e:
            log(f"{TOOLCHAIN}: could not delete {path.name} ({type(e).__name__}); "
                "kept, the next verified run tries again")
    if removed:
        log(f"{TOOLCHAIN}: luajit.exe verified; deleted the portable toolchain tree "
            "and archive directly (AshLight's own re-fetchable cache files under the "
            "sidecar Cache); a later rebuild fetches them again")
    return removed


def ensure_luajit(lay, which=None, run=subprocess.run, environ=None, toolchain=None,
                  source_check=None):
    """'ready' when luajit.exe exists AND matches the SHA-256 recorded when
    this step built it (built now or before), 'source-only' when no compiler
    is available. An existing luajit.exe without a matching record is not
    trusted (AUDIT-EXE-PATH): it is rebuilt when a compiler exists.
    TC-CALC-VERIFY-PIN: `source_check()` runs right before the build (the
    LuaJIT source re-hashed against its content digest, ensure_source).
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
    if source_check is not None:
        source_check()
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
    # TC-CALC-VERIFY-PIN: PoB's runnable Lua files re-hashed on every re-run
    if not lua_ok(doc[LUA_COMPONENT], lay["pob2_checkout"]):
        log("pob2: Lua files do not match the pinned lua digest")
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


# TC-CALC-OPTIN: the statuses that mean a verified install ('noop' is a
# previous 'ready' run whose outputs and luajit.exe record still verify).
VERIFIED = ("ready", "noop")


def write_config(path, cfg):
    """The default config writer: atomic, ASCII + LF, one .bak (the core's
    _write_config shape, F-014), then the private ACL on both copies
    (decision 0051; a no-op off Windows or on a refused path)."""
    path = Path(path)
    jsonfile.write_json(path, cfg, indent=2, backup=True)
    for p in (path, jsonfile.bak_path(path)):
        if p.is_file():
            acl.make_private(p)


def set_opt_in_flag(path=None, write=None):
    """Turn the calc on: "tc_calc": true merged into the local config with
    every other key kept. A missing file gets that one key only (no
    defaults are seeded). Returns True when written, False when the flag
    was already a real true (no write). Raises ConfigError, file untouched,
    when the file exists but is not a JSON object. `write(path, cfg)` is
    the injected writer (default write_config). DEP-09's installer calls
    this same function: keep the name."""
    path = Path(path) if path else paths.local_config_file()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        cfg = {}
    except (OSError, UnicodeDecodeError) as e:
        raise ConfigError(f"{path.name} is unreadable ({type(e).__name__})") from e
    else:
        try:
            cfg = json.loads(raw)
        except ValueError as e:
            raise ConfigError(f"{path.name} is not valid JSON") from e
        if not isinstance(cfg, dict):
            raise ConfigError(f"{path.name} is not a JSON object")
    if cfg.get(OPT_IN_KEY) is True:
        return False
    cfg[OPT_IN_KEY] = True
    (write or write_config)(path, cfg)
    return True


def turn_on(status, config_path=None, write=None):
    """After an --opt-in run: write the flag only for a verified install.
    Returns the exit code (RC_OK, or RC_FAIL when the flag could not be
    written)."""
    if status not in VERIFIED:
        log(f"tc calc: not turned on ({status}: luajit.exe was not built); "
            "config/local.json left as it was")
        return RC_OK
    try:
        wrote = set_opt_in_flag(config_path, write)
    except (ConfigError, OSError) as e:
        log(f"failed: calc installed but not turned on: {e}; "
            "config/local.json left as it was")
        return RC_FAIL
    log("tc calc: turned on (\"tc_calc\": true in config/local.json)" if wrote
        else "tc calc: already on in config/local.json")
    return RC_OK


def run_setup(doc, environ=None, fetch=None, which=None, run=subprocess.run,
              toolchain_fetch=None):
    """Fetch, verify, extract and (when possible) build. Returns the status
    'noop', 'ready' or 'source-only'."""
    lay = layout(doc, environ)
    if is_noop(doc, lay):
        log("tc calc component up to date (no-op)")
        remove_toolchain(lay)  # a toolchain an earlier version kept
        return "noop"
    for name, archive, parent, tree in (
            ("pob2", "pob2_archive", "pob2_cache", "pob2_checkout"),
            ("luajit", "luajit_archive", "luajit_build", "luajit_source")):
        spec = doc[name]
        marker = read_marker(lay[tree])
        if marker and marker.get("archive_sha256") == spec["archive_sha256"]:
            if name != LUA_COMPONENT or lua_ok(spec, lay[tree]):
                log(f"{name}: extracted tree present (no-op)")
                continue
            log(f"{name}: Lua files do not match the pinned lua digest; re-extracting")
        path, _ = ensure_archive(name, spec, lay[archive], fetch)
        ensure_extracted(name, spec, path, lay[parent], force=True)
    toolchain = None
    if TOOLCHAIN in doc:
        def toolchain():
            return ensure_toolchain(doc, lay, toolchain_fetch)

    def source_check():
        ensure_source("luajit", doc["luajit"], lay,
                      ("luajit_archive", "luajit_build", "luajit_source"), fetch)
    status = ensure_luajit(lay, which=which, run=run, environ=environ,
                           toolchain=toolchain, source_check=source_check)
    write_stamp(doc, lay, status)
    if status == "ready" and exepin.verified(lay["luajit_exe"]):
        remove_toolchain(lay)
    log(f"tc calc component: {status} (PoB-PoE2 {doc['pob2']['tag']}, "
        f"LuaJIT {doc['luajit']['version']})")
    return status


def main(argv=None, config_writer=None):
    """`config_writer(path, cfg)` is the injected writer for the opt-in
    flag (default write_config); it runs only for --opt-in with a
    verified install."""
    ap = argparse.ArgumentParser(prog="tc_pin", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup", help="fetch and verify (only when opted in)")
    s.add_argument("--opt-in", action="store_true",
                   help="the setup.ps1 -TcCalc switch (else config/local.json tc_calc); "
                        "after a verified install it also turns the calc on")
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
        status = run_setup(doc)
    except (HashMismatch, UnsafeArchive, webfetch.UrlNotAllowed) as e:
        log(f"refused: {e}")
        return RC_REFUSED
    except (OSError, RuntimeError, zipfile.BadZipFile, webfetch.FetchError,
            urllib.error.URLError) as e:
        log(f"failed: {e}")
        return RC_FAIL
    if args.opt_in:
        return turn_on(status, write=config_writer)
    return RC_OK


if __name__ == "__main__":
    sys.exit(main())
