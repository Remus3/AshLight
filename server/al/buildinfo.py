"""RUN-BUILD-STAMP-CORE (F-027): one build id for every surface.

The build string is VERSION plus SemVer build metadata:

    0.1.0+0123456789ab        a checkout at that commit
    0.1.0+0123456789ab.dev    ... while hot reload is on (decision 0042)
    0.1.0                     no commit known (no .git, no BUILD file)

The commit is the first 12 hex characters of HEAD, read from the .git
files only: HEAD, a loose ref, then packed-refs; a linked worktree's
".git" file and its commondir are followed. No subprocess, no git binary,
no network. Outside a checkout (an installed copy, decision 0059) the
BUILD file at the payload root carries it: a small JSON object
{"version", "commit", "created"} written by the release step (F-048);
a BUILD file whose version is not VERSION is stale and ignored.

The commit is read once per root and cached ("computed at start"); a code
reload is a new core process, so it reads the new commit. /api/health,
/api/version and the Checks report header show the same string. The build
id never goes into the User-Agent (decisions 0013, 0015; 0051-X9): webfetch
keeps NAME/VERSION.
"""

import json
import re
import threading
from pathlib import Path

from . import VERSION, hotreload, paths

BUILD_FILE = "BUILD"
COMMIT_LEN = 12
DEV_MARK = "dev"
SMALL_MAX = 4096                  # HEAD, a loose ref, a .git file, BUILD
PACKED_MAX = 16 * 1024 * 1024     # packed-refs
REF_HOPS = 5                      # symbolic ref chain bound

_HEX = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")   # SHA-1 or SHA-256
_SHORT = re.compile(r"^[0-9a-f]{%d,64}$" % COMMIT_LEN)
_REF = re.compile(r"^refs/[A-Za-z0-9._/-]+$")

_LOCK = threading.Lock()
_COMMITS = {}      # str(root) -> 12-hex commit or None
_HOT = [None]      # the core's hot reload flag, as last reported by http


def _small(path, cap=SMALL_MAX):
    """The stripped text of a small file, or None (missing, too big,
    unreadable, not ASCII)."""
    try:
        p = Path(path)
        if not p.is_file() or p.stat().st_size > cap:
            return None
        return p.read_bytes().decode("ascii").strip()
    except (OSError, UnicodeDecodeError):
        return None


def _git_dirs(root):
    """(gitdir, commondir) for a checkout root, or None. A ".git" file
    (a linked worktree) names its gitdir; that dir's "commondir" file
    names the shared one."""
    dot = Path(root) / ".git"
    try:
        if dot.is_dir():
            return dot, dot
        if not dot.is_file():
            return None
    except OSError:
        return None
    text = _small(dot)
    if not text or not text.startswith("gitdir:"):
        return None
    gitdir = Path(text[len("gitdir:"):].strip())
    if not gitdir.is_absolute():
        gitdir = Path(root) / gitdir
    common = gitdir
    rel = _small(gitdir / "commondir")
    if rel:
        c = Path(rel)
        common = c if c.is_absolute() else gitdir / c
    return gitdir, common


def _packed(common, ref):
    """The hash packed-refs records for `ref`, or None."""
    p = Path(common) / "packed-refs"
    try:
        if not p.is_file() or p.stat().st_size > PACKED_MAX:
            return None
        with p.open("rb") as fh:
            for raw in fh:
                line = raw.decode("ascii", "replace").strip()
                if not line or line[0] in "#^":
                    continue
                sha, _, name = line.partition(" ")
                if name == ref and _HEX.match(sha):
                    return sha
    except OSError:
        return None
    return None


def _resolve(gitdir, common, ref):
    """The hash a ref names: a loose ref in the gitdir, then in the common
    dir, then packed-refs. Only plain refs/... names are looked up, so a
    crafted HEAD cannot point the read outside the git dir."""
    for _ in range(REF_HOPS):
        if not _REF.match(ref) or ".." in ref.split("/"):
            return None
        text = None
        for base in (gitdir, common):
            text = _small(Path(base) / ref)
            if text:
                break
        if not text:
            return _packed(common, ref)
        if text.startswith("ref:"):
            ref = text[len("ref:"):].strip()
            continue
        return text if _HEX.match(text) else None
    return None


def git_commit(root):
    """The 12-hex HEAD commit of a checkout root, or None. Files only."""
    dirs = _git_dirs(root)
    if dirs is None:
        return None
    gitdir, common = dirs
    head = _small(Path(gitdir) / "HEAD")
    if not head:
        return None
    if head.startswith("ref:"):
        sha = _resolve(gitdir, common, head[len("ref:"):].strip())
    else:
        sha = head if _HEX.match(head) else None
    return sha[:COMMIT_LEN] if sha else None


def build_file_commit(root, version=VERSION):
    """The 12-hex commit of the BUILD file at the payload root, or None
    when it is missing, malformed or written for another version."""
    text = _small(Path(root) / BUILD_FILE)
    if not text:
        return None
    try:
        doc = json.loads(text)
    except ValueError:
        return None
    if not isinstance(doc, dict) or doc.get("version") != version:
        return None
    sha = doc.get("commit")
    if not isinstance(sha, str) or not _SHORT.match(sha):
        return None
    return sha[:COMMIT_LEN]


def commit(root=None):
    """The build's commit: the .git files in a checkout, else the BUILD
    file; cached per root for the life of the process."""
    root = paths.repo_root() if root is None else Path(root)
    key = str(root)
    with _LOCK:
        if key in _COMMITS:
            return _COMMITS[key]
    value = git_commit(root) or build_file_commit(root)
    with _LOCK:
        _COMMITS[key] = value
    return value


def compose(version, sha, hot):
    """'<version>[+<sha>][.dev]' (SemVer build metadata)."""
    meta = [p for p in (sha, DEV_MARK if hot else None) if p]
    return f"{version}+{'.'.join(meta)}" if meta else str(version)


def _hot_now(hot):
    if hot is not None:
        _HOT[0] = bool(hot)
        return bool(hot)
    if _HOT[0] is not None:
        return _HOT[0]
    try:
        return bool(hotreload.dev_enabled())
    except Exception:  # noqa: BLE001 - an unreadable flag reads off
        return False


def build_id(hot=None, version=VERSION, root=None):
    """The build string. `hot` is the core's hot reload flag (http passes
    core.hot and it is remembered); None uses the last flag seen, else
    hotreload.dev_enabled() from the env and the checkout."""
    return compose(version, commit(root), _hot_now(hot))


def reset():
    """Forget cached commits and the remembered flag (tests)."""
    with _LOCK:
        _COMMITS.clear()
    _HOT[0] = None
