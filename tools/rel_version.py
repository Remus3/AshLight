#!/usr/bin/env python3
"""Release version tool (DEP-03): one version, enforced, bumped in one go.

Loaded by tools/release.py for the `bump` sub-command:

    release.py bump X.Y.Z [--root DIR]      set X.Y.Z everywhere (edits files;
                                            never commits, tags or pushes)
    release.py bump --check [--tag vX.Y.Z] [--root DIR]
                                            exit 0 when every version-bearing
                                            place holds VERSION (and the tag, if
                                            given, is 'v' + VERSION), else exit 1
                                            with one line per problem; writes
                                            nothing

The one source is VERSION in server/al/__init__.py. Version-bearing places:

    server/al/__init__.py       VERSION = "X.Y.Z"
    app/package.json            top-level "version"
    app/package-lock.json       top-level "version" and packages[""].version
    stamped lines               every tracked line carrying the stamp marker
                                (MARKER below) as a comment, right after its
                                opener (<!--, #, // or ;); the line must hold
                                VERSION. A line that is only the marker
                                comment stamps the next line that is not
                                blank or a code fence instead (the README
                                install line, README-STAMP-HIDDEN). Any
                                other mention of the marker is prose, not
                                a stamp.

A bump also writes the notes stub docs/releases/X.Y.Z.md carrying STUB_MARK
(the folder is made on first bump). Versions are SemVer X.Y.Z with an
optional -rc.N pre-release; X.Y.Z-rc.N sorts below X.Y.Z. A bump refuses a
version that is not above the current one, an inconsistent tree, and an
existing notes file. Stdlib only; no network.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MARKER = "al-version-stamp"
STUB_MARK = "STUB: release notes not written yet"

INIT_REL = "server/al/__init__.py"
PKG_REL = "app/package.json"
LOCK_REL = "app/package-lock.json"
NOTES_DIR_REL = "docs/releases"

_VERSION_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-rc\.(0|[1-9]\d*))?$")
_INIT_LINE = re.compile(r'^VERSION = "([^"]*)"$', re.M)
_TOP_VERSION = re.compile(r'^  "version": "([^"]*)",?$', re.M)
_ROOT_PKG_VERSION = re.compile(r'^      "version": "([^"]*)",?$', re.M)
_STAMP_RE = re.compile(r"(?:<!--|#|//|;)[ \t]*" + re.escape(MARKER) + r"(?![\w-])")
# README-STAMP-HIDDEN: a line that is only the marker comment points at the
# next line that is not blank and not a code fence (``` or ~~~).
_POINTER_RE = re.compile(r"^[ \t]*(?:<!--[ \t]*" + re.escape(MARKER)
                         + r"(?![\w-])[^>]*-->|(?:#|//|;)[ \t]*"
                         + re.escape(MARKER) + r"(?![\w-])[^\n]*)[ \t]*$")
_FENCE_RE = re.compile(r"^[ \t]*(?:```|~~~)")


def stamp_targets(text):
    """[(1-based line number, line text)] of every stamped line in `text`.

    A line carrying the marker after a comment opener is stamped itself. A
    line that is only the marker comment (README-STAMP-HIDDEN) stamps the
    next line that is not blank and not a fence line instead, so a pasted
    command needs no trailing dev comment. Raises VersionError("line <n>:
    stamp marker points at no line") when nothing follows a marker line.
    """
    lines = text.split("\n")
    hits, seen = [], set()
    for i, line in enumerate(lines):
        if not _STAMP_RE.search(line):
            continue
        j = i
        if _POINTER_RE.match(line):
            j, fences = i + 1, 0
            while j < len(lines) and (not lines[j].strip()
                                      or _FENCE_RE.match(lines[j])):
                fences += 1 if lines[j].strip() else 0
                j += 1
            if j >= len(lines) or fences > 1:
                raise VersionError("line %d: stamp marker points at no line"
                                   % (i + 1))
        if j not in seen:
            seen.add(j)
            hits.append((j + 1, lines[j]))
    return hits


class VersionError(ValueError):
    """A malformed version string or an unreadable version-bearing file."""


def parse(text):
    """'0.2.0-rc.1' -> (0, 2, 0, 1); a release has rc None."""
    m = _VERSION_RE.match(text or "")
    if not m:
        raise VersionError("not a version (X.Y.Z or X.Y.Z-rc.N): %r" % (text,))
    rc = m.group(4)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)),
            None if rc is None else int(rc))


def sort_key(text):
    """Order key: a pre-release sorts below its release."""
    major, minor, patch, rc = parse(text)
    return (major, minor, patch, (1, 0) if rc is None else (0, rc))


def compare(a, b):
    """-1, 0 or 1 as a sorts below, equal to or above b."""
    ka, kb = sort_key(a), sort_key(b)
    return (ka > kb) - (ka < kb)


def tag_for(version):
    parse(version)
    return "v" + version


def tag_ok(tag, version):
    """A release tag must equal 'v' + VERSION."""
    return tag == tag_for(version)


def _read(root, rel):
    try:
        return (Path(root) / rel).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise VersionError("%s: unreadable (%s)" % (rel, exc.__class__.__name__))


def _write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def source_version(root=ROOT):
    """VERSION as written in server/al/__init__.py (read as text, never imported)."""
    found = _INIT_LINE.findall(_read(root, INIT_REL))
    if len(found) != 1:
        raise VersionError("%s: expected one VERSION line, found %d"
                           % (INIT_REL, len(found)))
    return found[0]


def _lock_root_span(text):
    """Index range of the packages[""] block's own fields in the lock text."""
    start = text.find('\n    "": {\n')
    if start < 0:
        return None
    end = text.find("\n    },", start)
    return (start, end if end >= 0 else len(text))


def app_versions(root=ROOT):
    """{label: version} for the app manifest and lockfile fields."""
    out = {}
    try:
        out[PKG_REL] = json.loads(_read(root, PKG_REL)).get("version")
    except ValueError:
        raise VersionError("%s: not JSON" % PKG_REL)
    try:
        lock = json.loads(_read(root, LOCK_REL))
    except ValueError:
        raise VersionError("%s: not JSON" % LOCK_REL)
    out[LOCK_REL + " version"] = lock.get("version")
    out[LOCK_REL + ' packages[""].version'] = (
        (lock.get("packages") or {}).get("") or {}).get("version")
    return out


def tracked_files(root=ROOT):
    proc = subprocess.run(["git", "ls-files", "-z"], cwd=str(root),
                          capture_output=True, check=False)
    if proc.returncode != 0:
        raise VersionError("git ls-files failed in the release root")
    return [p for p in proc.stdout.decode("utf-8", "replace").split("\0") if p]


def is_stamp_line(line):
    """True when the marker sits in a comment right after its opener."""
    return _STAMP_RE.search(line) is not None


def stamp_lines(root=ROOT):
    """[(rel path, 1-based line number, line text)] for every tracked stamp."""
    hits = []
    for rel in tracked_files(root):
        path = Path(root) / rel
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if MARKER.encode("ascii") not in data:
            continue
        text = data.decode("utf-8", "replace")
        try:
            targets = stamp_targets(text)
        except VersionError as exc:
            raise VersionError("%s:%s" % (rel, str(exc)[len("line "):]))
        hits.extend((rel, n, line) for n, line in targets)
    return hits


def _holds(line, version):
    return re.search(r"(?<![\w.-])" + re.escape(version) + r"(?![\w-]|\.\d)",
                     line) is not None


def check(root=ROOT, tag=None):
    """Problems (one line each); empty when every place holds VERSION."""
    problems = []
    try:
        version = source_version(root)
        parse(version)
    except VersionError as exc:
        return [str(exc)]
    try:
        for label, value in app_versions(root).items():
            if value != version:
                problems.append("%s is %r, VERSION is %r" % (label, value, version))
    except VersionError as exc:
        problems.append(str(exc))
    try:
        for rel, n, line in stamp_lines(root):
            if not _holds(line, version):
                problems.append("%s:%d stamped line does not hold %s"
                                % (rel, n, version))
    except VersionError as exc:
        problems.append(str(exc))
    if tag is not None and not tag_ok(tag, version):
        problems.append("tag %r is not %r" % (tag, tag_for(version)))
    return problems


def notes_rel(version):
    return "%s/%s.md" % (NOTES_DIR_REL, version)


def notes_stub(version):
    return ("# AshLight %s\n\n%s (release.py notes %s --write fills this "
            "file).\n" % (version, STUB_MARK, version))


def _swap_once(pattern, text, old, new, where):
    matches = list(pattern.finditer(text))
    if len(matches) != 1 or matches[0].group(1) != old:
        raise VersionError("%s: version field not found as expected" % where)
    m = matches[0]
    a, b = m.span(1)
    return text[:a] + new + text[b:]


def _swap_on_line(line, old, new):
    pat = re.compile(r"(?<![\w.-])" + re.escape(old) + r"(?![\w-]|\.\d)")
    return pat.sub(new, line)


def plan_bump(root, new):
    """{rel path: new text} for a bump to `new`; raises VersionError."""
    parse(new)
    problems = check(root)
    if problems:
        raise VersionError("tree is not consistent, fix first: " + problems[0])
    old = source_version(root)
    if compare(new, old) <= 0:
        raise VersionError("%s is not above the current %s" % (new, old))
    if (Path(root) / notes_rel(new)).exists():
        raise VersionError("%s exists already" % notes_rel(new))
    out = {}
    out[INIT_REL] = _swap_once(_INIT_LINE, _read(root, INIT_REL), old, new, INIT_REL)
    out[PKG_REL] = _swap_once(_TOP_VERSION, _read(root, PKG_REL), old, new, PKG_REL)
    lock = _read(root, LOCK_REL)
    span = _lock_root_span(lock)
    if span is None:
        raise VersionError('%s: packages[""] block not found' % LOCK_REL)
    head = _swap_once(_TOP_VERSION, lock[:span[0]], old, new, LOCK_REL)
    block = _swap_once(_ROOT_PKG_VERSION, lock[span[0]:span[1]], old, new,
                       LOCK_REL + ' packages[""]')
    out[LOCK_REL] = head + block + lock[span[1]:]
    for rel, text in ((PKG_REL, out[PKG_REL]), (LOCK_REL, out[LOCK_REL])):
        before, after = json.loads(_read(root, rel)), json.loads(text)
        before["version"] = new
        if rel == LOCK_REL:
            before["packages"][""]["version"] = new
        if before != after:
            raise VersionError("%s: edit changed more than the version" % rel)
    by_file = {}
    for rel, n, _line in stamp_lines(root):
        by_file.setdefault(rel, []).append(n)
    for rel, numbers in by_file.items():
        text = out.get(rel, None)
        if text is None:
            text = _read(root, rel)
        lines = text.split("\n")
        for n in numbers:
            lines[n - 1] = _swap_on_line(lines[n - 1], old, new)
        out[rel] = "\n".join(lines)
    out[notes_rel(new)] = notes_stub(new)
    return out


def bump(root, new):
    """Write the bump; returns the changed paths, sorted."""
    plan = plan_bump(root, new)
    for rel in sorted(plan):
        _write(root, rel, plan[rel])
    return sorted(plan)


def _usage():
    return ("usage: release.py bump X.Y.Z [--root DIR]\n"
            "       release.py bump --check [--tag vX.Y.Z] [--root DIR]")


def main(command, argv):
    """Entry from tools/release.py; returns the exit code."""
    if command != "bump":
        print("rel_version: unknown sub-command %r" % command, file=sys.stderr)
        return 2
    args = list(argv)
    root, tag, do_check, version = ROOT, None, False, None
    while args:
        a = args.pop(0)
        if a == "--check":
            do_check = True
        elif a in ("--root", "--tag") and args:
            value = args.pop(0)
            if a == "--root":
                root = Path(value)
            else:
                tag = value
        elif a in ("-h", "--help"):
            print(_usage())
            return 0
        elif not a.startswith("-") and version is None:
            version = a
        else:
            print(_usage(), file=sys.stderr)
            return 2
    if do_check == (version is not None) or (tag is not None and not do_check):
        print(_usage(), file=sys.stderr)
        return 2
    if do_check:
        problems = check(root, tag=tag)
        for p in problems:
            print("bump --check: " + p)
        if problems:
            return 1
        print("bump --check: ok %s" % source_version(root))
        return 0
    try:
        changed = bump(root, version)
    except VersionError as exc:
        print("bump: refused: %s" % exc, file=sys.stderr)
        return 1
    for rel in changed:
        print("bump: wrote %s" % rel)
    return 0


if __name__ == "__main__":
    sys.exit(main("bump", sys.argv[1:]))
