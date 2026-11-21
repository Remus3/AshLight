#!/usr/bin/env python3
"""Release build tool (DEP-08, F-048, decision 0064): the app zip.

Loaded by tools/release.py for the `build` sub-command:

    release.py build [--ref REF | --tag vX.Y.Z] [--out DIR] [--root DIR]

It writes, to <sidecar>/Build/release/<version>/ (or --out):

    AshLight-<version>-app.zip   one top folder AshLight-<version>/; the
                                 entries are the ship list
                                 (config/ship_list.json at the ref) over
                                 `git ls-tree` at the ref, bytes from git
                                 blobs, sorted, every time field = the ref's
                                 commit time, plus the generated BUILD and
                                 MANIFEST.json
    install.ps1, release.json, AshLight-<version>-notes.md,
    AshLight-<version>.sbom.json  from tools/rel_assets.py (REL-BUILD-ASSETS),
                                 with its leak sweep and poe.ninja release
                                 switch refusals of the staged tree
    SHA256SUMS.txt               one '<sha256>  <name>' line per asset,
                                 sorted

BUILD is one JSON line {"commit": <12 hex>, "created": <commit time, UTC>,
"version": <VERSION>}. MANIFEST.json holds sha256 and size per file (BUILD
included, itself not). No artifact carries the tag: a `--ref` build and a
`--tag` build of one commit give the same bytes (adjudicator LE-53).

Refusals, each before anything is written: a dirty tree; `--tag` naming a
tag that does not exist or differs from 'v' + VERSION at its commit; a
VERSION that is not SemVer; a ship list missing or malformed at the ref; a
shipped path that is unsafe, not a plain file blob, collides with a
generated name, matches a cache_deny pattern or carries the bytes of a file
in the sidecar Cache; a zip over the ship list's max_zip_bytes.

Reproducible: nothing reads the clock, the host name or a random source.
It never uploads, tags, commits or pushes; no network. Stdlib only.
"""
import argparse
import datetime
import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent

SHIP_LIST_REL = "config/ship_list.json"
INIT_REL = "server/al/__init__.py"
BUILD_NAME = "BUILD"
MANIFEST_NAME = "MANIFEST.json"
GENERATED = (BUILD_NAME, MANIFEST_NAME)
SUMS_NAME = "SHA256SUMS.txt"
CACHE_MIN_BYTES = 256  # shorter files match unrelated cache files by chance
FILE_MODES = ("100644", "100755")
_DEFAULT = object()

_SEGMENT = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._+-]*$")
_RESERVED = frozenset(["CON", "PRN", "AUX", "NUL"]
                      + ["COM%d" % i for i in range(1, 10)]
                      + ["LPT%d" % i for i in range(1, 10)])
_MAX_PATH = 200


class BuildError(Exception):
    """A refusal; nothing has been written."""


def _load_tool(name):
    spec = importlib.util.spec_from_file_location(name, str(TOOLS / (name + ".py")))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_version():
    return _load_tool("rel_version")


rv = _load_version()


# --- git -------------------------------------------------------------------

def _git(root, *args, data=None):
    proc = subprocess.run(["git", *args], cwd=str(root), input=data,
                          capture_output=True, check=False)
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        raise BuildError("git %s failed: %s" % (args[0], err[-1] if err else
                                                 "exit %d" % proc.returncode))
    return proc.stdout


def _rev(root, spec):
    proc = subprocess.run(["git", "rev-parse", "-q", "--verify", spec],
                          cwd=str(root), capture_output=True, check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("ascii", "replace").strip() or None


def _show(root, commit, rel):
    proc = subprocess.run(["git", "cat-file", "blob", "%s:%s" % (commit, rel)],
                          cwd=str(root), capture_output=True, check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout


def dirty(root=ROOT):
    """Porcelain lines of a dirty tree (tracked changes and untracked files)."""
    out = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=normal")
    return [p for p in out.decode("utf-8", "replace").split("\0") if p]


def tree(root, commit):
    """[(mode, type, sha, path)] of every entry at the commit, recursively."""
    out = _git(root, "ls-tree", "-r", "-z", "--full-tree", commit)
    rows = []
    for rec in out.split(b"\0"):
        if not rec:
            continue
        head, _tab, path = rec.partition(b"\t")
        mode, kind, sha = head.decode("ascii").split(" ")
        rows.append((mode, kind, sha, path.decode("utf-8", "replace")))
    return rows


def blobs(root, shas):
    """{sha: bytes} for the given blob ids, read in one `git cat-file`."""
    wanted = sorted(set(shas))
    if not wanted:
        return {}
    out = _git(root, "cat-file", "--batch",
               data=("".join(s + "\n" for s in wanted)).encode("ascii"))
    found, pos = {}, 0
    for sha in wanted:
        nl = out.index(b"\n", pos)
        head = out[pos:nl].decode("ascii").split(" ")
        if len(head) != 3 or head[0] != sha or head[1] != "blob":
            raise BuildError("git object %s is not a blob" % sha)
        size = int(head[2])
        found[sha] = out[nl + 1:nl + 1 + size]
        pos = nl + 1 + size + 1
    return found


# --- ship list -------------------------------------------------------------

def glob_regex(pattern):
    """A '/'-separated glob: '*' and '?' stay in one segment, '**' spans."""
    parts = pattern.split("/")
    out = []
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        if part == "**":
            out.append(".+" if last else "(?:[^/]+/)*")
            continue
        seg = "".join("[^/]*" if c == "*" else "[^/]" if c == "?" else
                      re.escape(c) for c in part)
        out.append(seg if last else seg + "/")
    return re.compile("".join(out))


def _matches(path, patterns):
    return any(glob_regex(p).fullmatch(path) for p in patterns)


def parse_ship_list(data):
    """The ship list as a dict; raises BuildError when it is malformed."""
    try:
        spec = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise BuildError("%s is not JSON" % SHIP_LIST_REL)
    if not isinstance(spec, dict) or spec.get("schema") != 1:
        raise BuildError("%s: schema 1 expected" % SHIP_LIST_REL)
    for key in ("include", "exclude", "cache_deny"):
        value = spec.get(key)
        if not isinstance(value, list) or not all(
                isinstance(p, str) and p for p in value):
            raise BuildError("%s: %s must be a list of patterns"
                             % (SHIP_LIST_REL, key))
    if not spec["include"]:
        raise BuildError("%s: include is empty" % SHIP_LIST_REL)
    if spec.get("compression") not in ("deflate", "stored"):
        raise BuildError("%s: compression must be deflate or stored"
                         % SHIP_LIST_REL)
    level = spec.get("compresslevel")
    if not isinstance(level, int) or isinstance(level, bool) or not 0 <= level <= 9:
        raise BuildError("%s: compresslevel must be 0 to 9" % SHIP_LIST_REL)
    limit = spec.get("max_zip_bytes")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        raise BuildError("%s: max_zip_bytes must be a positive integer"
                         % SHIP_LIST_REL)
    top = spec.get("top")
    if not isinstance(top, str) or "{version}" not in top:
        raise BuildError("%s: top must hold {version}" % SHIP_LIST_REL)
    return spec


def ship_list(root, commit):
    data = _show(root, commit, SHIP_LIST_REL)
    if data is None:
        raise BuildError("%s is missing at %s" % (SHIP_LIST_REL, commit[:12]))
    return parse_ship_list(data)


def safe_path(path):
    """True for a relative '/'-path of plain segments that every OS extracts
    to the same place (no '..', drive, backslash, reserved or odd name)."""
    if not isinstance(path, str) or not path or len(path) > _MAX_PATH:
        return False
    for seg in path.split("/"):
        if not _SEGMENT.match(seg) or seg.endswith("."):
            return False
        if seg.split(".")[0].upper() in _RESERVED:
            return False
    return True


def select(rows, spec):
    """[(mode, sha, path)] the ship list keeps, sorted by path; raises
    BuildError on an unsafe, non-file or cache-shaped shipped path."""
    kept = []
    for mode, kind, sha, path in rows:
        if not _matches(path, spec["include"]) or _matches(path, spec["exclude"]):
            continue
        if not safe_path(path):
            raise BuildError("unsafe path in the ship list: %r" % path)
        if kind != "blob" or mode not in FILE_MODES:
            raise BuildError("not a plain file: %s (mode %s)" % (path, mode))
        if path in GENERATED:
            raise BuildError("%s would collide with the generated file" % path)
        if _matches(path, spec["cache_deny"]):
            raise BuildError("sidecar cache file in the ship list: %s" % path)
        kept.append((mode, sha, path))
    if not kept:
        raise BuildError("the ship list selects no file")
    return sorted(kept, key=lambda r: r[2])


def ship(ref="HEAD", root=ROOT):
    """The shipped paths at the ref, sorted (the allow-list over the tree)."""
    commit = _rev(root, "%s^{commit}" % ref)
    if commit is None:
        raise BuildError("no commit for %r" % ref)
    return [p for _m, _s, p in select(tree(root, commit), ship_list(root, commit))]


# --- sidecar cache ---------------------------------------------------------

def default_cache_dir():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from server.al import paths  # noqa: E402
    return paths.sidecar_dir("Cache")


def cache_hits(files, cache_dir):
    """Shipped paths whose bytes equal a file under the sidecar Cache."""
    if cache_dir is None or not Path(cache_dir).is_dir():
        return []
    by_size = {}
    for path, data in files.items():
        if len(data) >= CACHE_MIN_BYTES:
            by_size.setdefault(len(data), []).append(path)
    digests = {}
    hits = set()
    for dirpath, dirnames, filenames in os.walk(str(cache_dir)):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            try:
                size = os.stat(full).st_size
            except OSError:
                continue
            if size not in by_size:
                continue
            try:
                with open(full, "rb") as fh:
                    digest = hashlib.sha256(fh.read()).hexdigest()
            except OSError:
                continue
            for path in by_size[size]:
                if path not in digests:
                    digests[path] = hashlib.sha256(files[path]).hexdigest()
                if digests[path] == digest:
                    hits.add(path)
    return sorted(hits)


# --- generated files and the zip -------------------------------------------

def created_text(commit_time):
    stamp = datetime.datetime.fromtimestamp(int(commit_time),
                                            tz=datetime.timezone.utc)
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_bytes(obj):
    return (json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=True)
            + "\n").encode("ascii")


def build_file(version, commit, commit_time):
    """BUILD: version, 12-hex commit and created (the commit time, UTC)."""
    return (json.dumps({"commit": commit[:12], "created": created_text(commit_time),
                        "version": version}, sort_keys=True)
            + "\n").encode("ascii")


def manifest(files, version, commit):
    """MANIFEST.json bytes: sha256 and size per file (itself not listed)."""
    listed = {}
    for path in sorted(files):
        if path == MANIFEST_NAME:
            continue
        data = files[path]
        listed[path] = {"sha256": hashlib.sha256(data).hexdigest(),
                        "size": len(data)}
    return _json_bytes({"commit": commit[:12], "files": listed, "schema": 1,
                        "version": version})


def _dos_time(commit_time):
    t = datetime.datetime.fromtimestamp(int(commit_time), tz=datetime.timezone.utc)
    if t.year < 1980:
        return (1980, 1, 1, 0, 0, 0)
    return (t.year, t.month, t.day, t.hour, t.minute, t.second)


def write_zip(files, top, commit_time, compression="deflate", level=9):
    """Zip bytes: one entry per file under `top`/, sorted, fixed metadata."""
    method = zipfile.ZIP_DEFLATED if compression == "deflate" else zipfile.ZIP_STORED
    when = _dos_time(commit_time)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path in sorted(files):
            info = zipfile.ZipInfo("%s/%s" % (top, path), date_time=when)
            info.compress_type = method
            info.create_system = 0
            info.external_attr = 0
            zf.writestr(info, files[path], compress_type=method,
                        compresslevel=level if method == zipfile.ZIP_DEFLATED
                        else None)
    return buf.getvalue()


# --- checks of a laid-out tree or a zip ------------------------------------

def _manifest_files(obj):
    files = obj.get("files") if isinstance(obj, dict) else None
    if not isinstance(files, dict):
        return None
    return files


def _compare(listed, present, read):
    """Problems between the manifest's files and the present names."""
    problems = []
    for path in sorted(listed):
        entry = listed[path]
        if not safe_path(path):
            problems.append("unsafe path: %r" % (path,))
            continue
        if path not in present:
            problems.append("missing: %s" % path)
            continue
        data = read(path)
        if (not isinstance(entry, dict) or entry.get("size") != len(data)
                or entry.get("sha256") != hashlib.sha256(data).hexdigest()):
            problems.append("changed: %s" % path)
    for path in sorted(present - set(listed) - {MANIFEST_NAME}):
        problems.append("unlisted: %s" % path)
    return problems


def verify_tree(directory, manifest_obj=None):
    """Problems of a laid-out version folder against its MANIFEST.json: a
    changed, missing or unlisted file and an unsafe listed path."""
    base = Path(directory)
    if manifest_obj is None:
        try:
            manifest_obj = json.loads((base / MANIFEST_NAME).read_bytes()
                                      .decode("utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            return ["%s: unreadable" % MANIFEST_NAME]
    listed = _manifest_files(manifest_obj)
    if listed is None:
        return ["%s: no files table" % MANIFEST_NAME]
    present = set()
    for dirpath, _dirs, names in os.walk(str(base)):
        for name in names:
            rel = os.path.relpath(os.path.join(dirpath, name), str(base))
            present.add(rel.replace(os.sep, "/"))
    return _compare(listed, present, lambda p: (base / p).read_bytes())


def verify_zip(zip_path):
    """Problems of an app zip: unsafe or duplicate member names, more than
    one top folder, and every member against the MANIFEST.json inside."""
    try:
        zf = zipfile.ZipFile(str(zip_path))
    except (OSError, zipfile.BadZipFile):
        return ["not a zip: %s" % Path(zip_path).name]
    with zf:
        names = zf.namelist()
        problems, members, tops = [], {}, set()
        for name in names:
            top, _slash, rel = name.partition("/")
            tops.add(top)
            if not safe_path(name) or not rel:
                problems.append("unsafe member: %r" % (name,))
                continue
            if rel in members:
                problems.append("duplicate member: %s" % name)
            members[rel] = name
        if len(tops) != 1:
            problems.append("expected one top folder, found %d" % len(tops))
        if problems:
            return problems
        if MANIFEST_NAME not in members:
            return ["%s: missing" % MANIFEST_NAME]
        try:
            obj = json.loads(zf.read(members[MANIFEST_NAME]).decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return ["%s: unreadable" % MANIFEST_NAME]
        listed = _manifest_files(obj)
        if listed is None:
            return ["%s: no files table" % MANIFEST_NAME]
        return _compare(listed, set(members), lambda p: zf.read(members[p]))


# --- build -----------------------------------------------------------------

def resolve(root, ref=None, tag=None):
    """(commit, version, commit_time) for the ref or the tag, with the tag
    checks of `--tag`; raises BuildError."""
    if ref is not None and tag is not None:
        raise BuildError("give --ref or --tag, not both")
    if tag is not None:
        if not tag.startswith("v"):
            raise BuildError("tag %r is not v<version>" % tag)
        try:
            rv.parse(tag[1:])
        except rv.VersionError:
            raise BuildError("tag %r is not v<version>" % tag)
        commit = _rev(root, "refs/tags/%s^{commit}" % tag)
        if commit is None:
            raise BuildError("no tag %s" % tag)
    else:
        commit = _rev(root, "%s^{commit}" % (ref or "HEAD"))
        if commit is None:
            raise BuildError("no commit for %r" % (ref or "HEAD"))
    init = _show(root, commit, INIT_REL)
    if init is None:
        raise BuildError("%s is missing at %s" % (INIT_REL, commit[:12]))
    found = rv._INIT_LINE.findall(init.decode("utf-8", "replace"))
    if len(found) != 1:
        raise BuildError("%s: expected one VERSION line" % INIT_REL)
    version = found[0]
    try:
        rv.parse(version)
    except rv.VersionError as exc:
        raise BuildError(str(exc))
    if tag is not None and not rv.tag_ok(tag, version):
        raise BuildError("tag %s differs from %s" % (tag, rv.tag_for(version)))
    when = _git(root, "show", "-s", "--format=%ct", commit).decode("ascii").strip()
    return commit, version, int(when)


def zip_name(version):
    return "AshLight-%s-app.zip" % version


def default_out(version):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from server.al import paths  # noqa: E402
    return paths.sidecar_dir("Build") / "release" / version


def _write_atomic(path, data):
    tmp = path.with_name(path.name + ".partial")
    tmp.write_bytes(data)
    os.replace(str(tmp), str(path))


def sums_text(out, names):
    """SHA256SUMS.txt bytes: one '<sha256>  <name>' line per asset, sorted."""
    lines = []
    for name in sorted(names):
        digest = hashlib.sha256((Path(out) / name).read_bytes()).hexdigest()
        lines.append("%s  %s\n" % (digest, name))
    return "".join(lines).encode("ascii")


def assemble(root, commit, spec, version, commit_time, cache_dir=_DEFAULT):
    """{zip path: bytes}: the shipped blobs at the commit plus BUILD and
    MANIFEST.json; raises BuildError on a ship-list or cache refusal."""
    rows = select(tree(root, commit), spec)
    data = blobs(root, [sha for _m, sha, _p in rows])
    files = {path: data[sha] for _m, sha, path in rows}
    if cache_dir is _DEFAULT:
        cache_dir = default_cache_dir()
    hits = cache_hits(files, cache_dir)
    if hits:
        raise BuildError("sidecar cache file in the ship list: %s" % hits[0])
    files[BUILD_NAME] = build_file(version, commit, commit_time)
    files[MANIFEST_NAME] = manifest(files, version, commit)
    return files


def prepare(root=ROOT, ref=None, tag=None, cache_dir=_DEFAULT, check_clean=True):
    """Every check and the zip bytes in memory; nothing is written.
    Returns {version, commit, created, zip_name, zip, files}."""
    root = Path(root)
    if check_clean:
        lines = dirty(root)
        if lines:
            raise BuildError("the tree is dirty (%d path(s), first: %s)"
                             % (len(lines), lines[0][3:]))
    commit, version, when = resolve(root, ref=ref, tag=tag)
    spec = ship_list(root, commit)
    files = assemble(root, commit, spec, version, when, cache_dir=cache_dir)
    blob = write_zip(files, spec["top"].replace("{version}", version), when,
                     spec["compression"], spec["compresslevel"])
    if len(blob) > spec["max_zip_bytes"]:
        raise BuildError("the zip is %d bytes, over the %d byte budget"
                         % (len(blob), spec["max_zip_bytes"]))
    return {"version": version, "commit": commit, "created": created_text(when),
            "zip_name": zip_name(version), "zip": blob, "files": files}


def build(root=ROOT, ref=None, tag=None, out=None, cache_dir=_DEFAULT,
          check_clean=True):
    """Check, then write the app zip and SHA256SUMS.txt to `out` (default
    <sidecar>/Build/release/<version>/). Returns a result dict."""
    ready = prepare(root, ref=ref, tag=tag, cache_dir=cache_dir,
                    check_clean=check_clean)
    # REL-BUILD-ASSETS: the other assets and the staged-tree refusals, all
    # in memory, so a refusal still writes nothing (tools/rel_assets.py).
    ra = _load_tool("rel_assets")
    try:
        staged = ra.stage(Path(root), ready)
    except ra.AssetError as exc:
        raise BuildError(str(exc))
    out = Path(out) if out is not None else default_out(ready["version"])
    out.mkdir(parents=True, exist_ok=True)
    _write_atomic(out / ready["zip_name"], ready["zip"])
    for name in staged["order"]:
        _write_atomic(out / name, staged["assets"][name])
    assets = sorted([ready["zip_name"]]
                    + [n for n in staged["order"] if n != SUMS_NAME])
    return {"version": ready["version"], "commit": ready["commit"],
            "created": ready["created"], "out": out, "assets": assets,
            "zip": out / ready["zip_name"],
            "sha256": hashlib.sha256(ready["zip"]).hexdigest(),
            "files": len(ready["files"]), "notes": staged["notes"]}


def _parser():
    p = argparse.ArgumentParser(
        prog="release.py build",
        description="Build the reproducible AshLight app zip from one git "
                    "ref (no upload, no tag, no network).")
    which = p.add_mutually_exclusive_group()
    which.add_argument("--ref", help="any commit-ish; default HEAD")
    which.add_argument("--tag", help="a release tag v<VERSION> that must exist")
    p.add_argument("--out", help="output folder (default "
                                 "<sidecar>/Build/release/<version>)")
    p.add_argument("--root", default=str(ROOT), help="the repository")
    return p


def main(command, argv):
    """Entry from tools/release.py; returns the exit code."""
    if command != "build":
        print("rel_build: unknown sub-command %r" % command, file=sys.stderr)
        return 2
    try:
        args = _parser().parse_args(list(argv))
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    try:
        res = build(root=args.root, ref=args.ref, tag=args.tag, out=args.out)
    except BuildError as exc:
        print("build: refused: %s" % exc, file=sys.stderr)
        return 1
    print("build: %s %s (%d files) -> %s" % (res["version"], res["commit"][:12],
                                             res["files"], res["out"]))
    print("build: sha256 %s  %s" % (res["sha256"], res["zip"].name))
    return 0


if __name__ == "__main__":
    sys.exit(main("build", sys.argv[1:]))
