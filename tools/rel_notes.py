#!/usr/bin/env python3
"""Release notes and changelog generator (DEP-04, F-101, decision 0062).

Loaded by tools/release.py for the `notes` sub-command:

    release.py notes X.Y.Z [--write] [--from REV] [--to REF] [--date D]
                     [--root DIR]
        draft the notes of version X.Y.Z from the first-parent commit
        subjects in FROM..TO (FROM: the newest v* tag below X.Y.Z reachable
        from TO, else the whole history; TO: HEAD) joined to ROADMAP row
        titles. Without --write the draft goes to stdout; with --write it
        is written to docs/releases/X.Y.Z.md (the lead paragraph between
        the two lead markers of an existing file is kept) and CHANGELOG.md
        is regenerated.
    release.py notes --count [--from REV] [--to REF] [--root DIR]
        print one line `<n> <date>`: n row merges (first-parent `merge:
        <ROW-ID> ...` subjects) in FROM..TO (FROM: the newest v* tag
        reachable from TO, else the whole history) and the committer date
        (YYYY-MM-DD) of the oldest, `-` when n is 0. Read by the loop's
        refresh source (AUTO-16).
    release.py notes --changelog [--check] [--root DIR]
        regenerate CHANGELOG.md from docs/releases/*.md, newest first;
        --check writes nothing and exits 1 when the file differs.

Inputs (plan 05, Changelog generation):
- only commit subjects (`git log --first-parent --format=%H%x09%s`), never
  bodies or trailers, so no attribution line reaches a notes file (FLEET
  item 17). Two shapes name a row: `merge: <ROW-ID> ...` and
  `type(<ROW-ID>): ...`; the type comes from tools/commit_subject.py.
- row titles and kinds from ROADMAP.md at both ends of the range plus the
  ROADMAP.md diff of every commit in it (done rows are pruned at /done);
  the newest wins. Row ids have the loop's shape (tools/loop_base.py ROW_ID).

Rules: one line per row id, `- <title> (<ROW-ID>)`; a commit without a row
id makes a line only for feat, fix, perf and security. Groups: Security
(a security or deps commit, or an Electron pin row), Changed for a (data)
row, Added (feat), Fixed (fix), Changed (perf, refactor, data), Added for a
merged row with nothing else; the rest (docs, test, chore, ops, release,
plain merges, untyped subjects ...) is counted in "Also: N internal
changes.". Security keys on the commit type and the row kind, never on an
id prefix (DEP- ids are deployment rows). Every notes file ends with the
not-affiliated sentence. Output is ASCII and LF; two runs over one range
give the same bytes (the date defaults to the committer date of TO).

No network, no tag, no commit. Stdlib only.
"""
import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from commit_subject import parse as parse_subject  # noqa: E402
from loop_base import ROW_ID, ascii_text  # noqa: E402
from loop_roadmap import roadmap_rows  # noqa: E402


def _load_version():
    spec = importlib.util.spec_from_file_location(
        "rel_version", str(TOOLS / "rel_version.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rv = _load_version()

ROADMAP_REL = "ROADMAP.md"
NOTES_DIR_REL = rv.NOTES_DIR_REL
CHANGELOG_REL = "CHANGELOG.md"

DISCLAIMER = ("This product isn't affiliated with or endorsed by Grinding "
              "Gear Games in any way.")
LEAD_OPEN = "<!-- lead: hand-written, kept when the notes are regenerated -->"
LEAD_CLOSE = "<!-- /lead -->"
LEAD_STUB = (rv.STUB_MARK + ": replace this with 1 to 3 sentences in "
             "player words.")
CHANGELOG_HEAD = (
    "# Changelog\n\n"
    "Every AshLight version, newest first. Generated from docs/releases/"
    "<version>.md by `python tools/release.py notes --changelog`; edit those "
    "files, never this one.\n")

GROUPS = ("Added", "Changed", "Fixed", "Security")
LINE_TYPES = ("feat", "fix", "perf", "security")  # a line without a row id

_ID_HEAD = re.compile(r"^(" + ROW_ID + r")(?=[\s:]|$):?\s*(.*)$")
_ID_ONLY = re.compile(r"^" + ROW_ID + r"$")
_ELECTRON_PIN = re.compile(r"\belectron\b.*\bpin", re.I)
_NOTES_NAME = re.compile(r"^(\d+\.\d+\.\d+(?:-rc\.\d+)?)\.md$")
_SENTENCE_END = re.compile(r"\.(?:\s|$)")
# the loader's done mark, appended to a row's first line (tools/roadmap.py)
_DONE_MARK = re.compile(r"\s*-- done \d{4}-\d{2}-\d{2} \([^()]*\)")


class NotesError(ValueError):
    """A bad version, an unreadable range or a refused write."""


# ---------------------------------------------------------------- git


def _git(root, *args, ok_fail=False):
    proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          encoding="utf-8", errors="replace", check=False)
    if proc.returncode != 0:
        if ok_fail:
            return None
        raise NotesError("git %s failed: %s"
                         % (args[0], (proc.stderr or "").strip()[:200]))
    return proc.stdout


def _range_args(rev_range):
    start, end = rev_range
    return ["%s..%s" % (start, end)] if start else [end]


def previous_tag(version, to="HEAD", root=ROOT):
    """The newest v* tag reachable from `to` whose version sorts below
    `version`, else None (the first release reads the whole history)."""
    out = _git(root, "tag", "--list", "v*", "--merged", to, ok_fail=True) or ""
    key = rv.sort_key(version)
    best = None
    for tag in out.split():
        try:
            k = rv.sort_key(tag[1:])
        except rv.VersionError:
            continue
        if k < key and (best is None or k > best[0]):
            best = (k, tag)
    return best[1] if best else None


def last_tag(to="HEAD", root=ROOT):
    """The newest v* tag reachable from `to`, else None."""
    out = _git(root, "describe", "--tags", "--abbrev=0", "--match", "v*",
               to, ok_fail=True)
    return out.strip() or None if out else None


def count(rev_range, root=ROOT):
    """(n, date of the oldest) of the row merges in rev_range: first-parent
    commits whose subject is `merge: <ROW-ID> ...`. The date is the
    committer date YYYY-MM-DD, "" when n is 0."""
    out = _git(root, "log", "--first-parent", "--reverse",
               "--format=%cs%x09%s", *_range_args(rev_range), "--")
    n, oldest = 0, ""
    for line in out.splitlines():
        day, _, subject = line.partition("	")
        parsed = parse_subject(subject)
        if not parsed or parsed[0] != "merge":
            continue
        if row_id("merge", None, subject[len("merge:"):].strip()
                  if subject.startswith("merge:") else "") is None:
            continue
        n += 1
        oldest = oldest or day
    return n, oldest


# ---------------------------------------------------------------- inputs


def row_id(kind, scope, text, known=()):
    """The row id a parsed subject names, else None: the scope of a typed
    subject, or the first word of a `merge:` subject. A candidate must have
    the row id shape and carry a '-' or be a known row id."""
    if kind == "merge":
        m = _ID_HEAD.match(text or "")
        cand = m.group(1) if m else None
    else:
        cand = scope
    if not cand or not _ID_ONLY.match(cand):
        return None
    return cand if ("-" in cand or cand in known) else None


def collect(rev_range, root=ROOT):
    """[(hash, subject)] of the first-parent commits in rev_range
    ((start or None, end)), oldest first. Only the subject is read."""
    out = _git(root, "log", "--first-parent", "--reverse",
               "--format=%H%x09%s", *_range_args(rev_range), "--")
    commits = []
    for line in out.splitlines():
        sha, _, subject = line.partition("\t")
        if sha:
            commits.append((sha, subject))
    return commits


def _rows_of(text):
    return {r["id"]: (r["title"], r["lane"]) for r in roadmap_rows(text)}


def _diff_sides(diff):
    """[(old text, new text)] per hunk of a unified diff."""
    hunks, old, new, inside = [], [], [], False
    for line in diff.splitlines():
        if line.startswith("@@"):
            if inside:
                hunks.append(("\n".join(old), "\n".join(new)))
            old, new, inside = [], [], True
        elif line.startswith("diff --git") or line.startswith("\x00"):
            if inside:
                hunks.append(("\n".join(old), "\n".join(new)))
            old, new, inside = [], [], False
        elif inside:
            if line.startswith(" "):
                old.append(line[1:])
                new.append(line[1:])
            elif line.startswith("-"):
                old.append(line[1:])
            elif line.startswith("+"):
                new.append(line[1:])
    if inside:
        hunks.append(("\n".join(old), "\n".join(new)))
    return hunks


def titles(rev_range, root=ROOT):
    """{row id: (title, lane)} from ROADMAP.md at both ends of rev_range and
    the ROADMAP.md diff of every first-parent commit in it. ROADMAP.md at
    the end wins, then the newest diff, then ROADMAP.md at the start."""
    start, end = rev_range
    out = {}
    if start:
        out.update(_rows_of(_git(root, "show", "%s:%s" % (start, ROADMAP_REL),
                                 ok_fail=True) or ""))
    diff = _git(root, "log", "--first-parent", "--reverse",
                "--diff-merges=first-parent", "-p", "-U25", "--format=%x00%H",
                *_range_args(rev_range), "--", ROADMAP_REL)
    for old, new in _diff_sides(diff):
        out.update(_rows_of(old))
        out.update(_rows_of(new))
    out.update(_rows_of(_git(root, "show", "%s:%s" % (end, ROADMAP_REL),
                             ok_fail=True) or ""))
    return out


# ---------------------------------------------------------------- grouping


def _first_sentence(text, rid=None):
    text = _DONE_MARK.sub("", ascii_text(text)).strip()
    if rid and text.startswith(rid + ":"):
        text = text[len(rid) + 1:].strip()
    m = _SENTENCE_END.search(text)
    if m:
        text = text[:m.start()]
    text = text.strip().rstrip(".").strip()
    return text[:1].upper() + text[1:]


def _row_group(types, title, lane):
    if types & {"security", "deps"} or _ELECTRON_PIN.search(title or ""):
        return "Security"
    if lane == "data" and types & {"merge", "feat", "perf", "refactor", "data"}:
        return "Changed"
    if "feat" in types:
        return "Added"
    if "fix" in types:
        return "Fixed"
    if types & {"perf", "refactor", "data"}:
        return "Changed"
    if "merge" in types:
        return "Added"
    return None


def group(commits, rows):
    """({group: [line]}, internal count) for [(hash, subject)] and the row
    map {id: (title, lane)}. Lines keep the order of first appearance."""
    known = set(rows)
    order, row_types, row_count, row_text = [], {}, {}, {}
    plain, internal = [], 0
    for _sha, subject in commits:
        parsed = parse_subject(subject)
        if parsed is None:
            internal += 1
            continue
        kind, scope, text = parsed
        rid = row_id(kind, scope, text, known)
        if rid is None:
            if kind in LINE_TYPES:
                plain.append((kind, text))
            else:
                internal += 1
            continue
        if rid not in row_types:
            order.append(rid)
            row_types[rid], row_count[rid] = set(), 0
        row_types[rid].add(kind)
        row_count[rid] += 1
        if kind == "merge":
            rest = _ID_HEAD.match(text).group(2)
            row_text.setdefault(rid, rest)
        else:
            row_text.setdefault(rid, text)
    out = {g: [] for g in GROUPS}
    seen = set()
    for kind, text in plain:
        g = {"feat": "Added", "fix": "Fixed", "perf": "Changed",
             "security": "Security"}[kind]
        line = "- %s" % _first_sentence(text)
        if line not in seen:
            seen.add(line)
            out[g].append(line)
    for rid in order:
        title, lane = rows.get(rid, (None, None))
        g = _row_group(row_types[rid], title, lane)
        if g is None:
            internal += row_count[rid]
            continue
        words = _first_sentence(title, rid) if title else ""
        words = words or _first_sentence(row_text.get(rid, "")) or rid
        out[g].append("- %s (%s)" % (words, rid))
    return out, internal


# ---------------------------------------------------------------- render


def render(version, date, groups, internal, lead=None):
    """The notes text of one version (ASCII, LF, ends with the sentence)."""
    rv.parse(version)
    lead = (lead or "").strip() or LEAD_STUB
    parts = ["## [%s] - %s" % (version, date), LEAD_OPEN, lead, LEAD_CLOSE, ""]
    for g in GROUPS:
        if groups.get(g):
            parts.append("### " + g)
            parts.extend(groups[g])
            parts.append("")
    parts.append("Also: %d internal change%s." % (internal,
                                                   "" if internal == 1 else "s"))
    parts.extend(["", DISCLAIMER])
    return ascii_text("\n".join(parts) + "\n")


def lead_of(text):
    """The lead paragraph between the two markers, else None."""
    if not text:
        return None
    a = text.find(LEAD_OPEN)
    b = text.find(LEAD_CLOSE, a + len(LEAD_OPEN)) if a >= 0 else -1
    if a < 0 or b < 0:
        return None
    return text[a + len(LEAD_OPEN):b].strip() or None


def notes_path(version, root=ROOT):
    rv.parse(version)
    return Path(root) / NOTES_DIR_REL / ("%s.md" % version)


def draft(version, start=None, to="HEAD", date=None, root=ROOT, lead=None):
    """The draft notes text of `version` for start..to."""
    rv.parse(version)
    if start is None:
        start = previous_tag(version, to, root)
    rev_range = (start, to)
    if date is None:
        date = (_git(root, "log", "-1", "--format=%cs", to) or "").strip()
    commits = collect(rev_range, root)
    groups, internal = group(commits, titles(rev_range, root))
    return render(version, date, groups, internal, lead)


def write(version, start=None, to="HEAD", date=None, root=ROOT):
    """Write docs/releases/<version>.md (keeping its lead) and regenerate
    CHANGELOG.md. Returns the notes path."""
    path = notes_path(version, root)
    old = path.read_bytes().decode("utf-8") if path.is_file() else None
    text = draft(version, start, to, date, root, lead_of(old))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("ascii"))
    changelog(check=False, root=root)
    return path


def notes_files(root=ROOT):
    """[(version, path)] of docs/releases/*.md, newest first."""
    folder = Path(root) / NOTES_DIR_REL
    found = []
    if folder.is_dir():
        for p in folder.iterdir():
            m = _NOTES_NAME.match(p.name)
            if m and p.is_file():
                try:
                    found.append((rv.sort_key(m.group(1)), m.group(1), p))
                except rv.VersionError:
                    continue
    found.sort(key=lambda t: t[0], reverse=True)
    return [(v, p) for _k, v, p in found]


def changelog_text(root=ROOT):
    """CHANGELOG.md as it must be: the head, then every notes file, newest
    first, one blank line between them."""
    bodies = [p.read_bytes().decode("utf-8").rstrip("\n") + "\n"
              for _v, p in notes_files(root)]
    return CHANGELOG_HEAD + "".join("\n" + b for b in bodies)


def changelog(check=False, root=ROOT):
    """Regenerate CHANGELOG.md; with check, write nothing and return False
    when it differs. True when the file is (now) current."""
    want = changelog_text(root)
    path = Path(root) / CHANGELOG_REL
    have = path.read_bytes().decode("utf-8", "replace") if path.is_file() else None
    if check:
        return have == want
    if have != want:
        path.write_bytes(want.encode("utf-8"))
    return True


# ---------------------------------------------------------------- cli


def _parser():
    p = argparse.ArgumentParser(prog="release.py notes", add_help=True)
    p.add_argument("version", nargs="?")
    p.add_argument("--write", action="store_true")
    p.add_argument("--changelog", action="store_true")
    p.add_argument("--check", action="store_true")
    p.add_argument("--count", action="store_true")
    p.add_argument("--from", dest="start")
    p.add_argument("--to", default="HEAD")
    p.add_argument("--date")
    p.add_argument("--root", default=str(ROOT))
    return p


def main(command, argv):
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0) and 2
    root = Path(args.root)
    try:
        if args.count:
            start = args.start if args.start else last_tag(args.to, root)
            n, day = count((start, args.to), root)
            print("%d %s" % (n, day or "-"))
            return 0
        if args.changelog and not args.version:
            if args.check:
                if changelog(check=True, root=root):
                    print("notes: CHANGELOG.md ok")
                    return 0
                print("notes: CHANGELOG.md is stale; run release.py notes "
                      "--changelog", file=sys.stderr)
                return 1
            changelog(check=False, root=root)
            print("notes: wrote " + CHANGELOG_REL)
            return 0
        if not args.version or args.check:
            print("usage: release.py notes X.Y.Z [--write] [--from REV] "
                  "[--to REF] [--date D] | notes --changelog [--check]",
                  file=sys.stderr)
            return 2
        if args.write:
            path = write(args.version, args.start, args.to, args.date, root)
            print("notes: wrote %s and %s"
                  % (path.relative_to(root).as_posix(), CHANGELOG_REL))
            return 0
        sys.stdout.write(draft(args.version, args.start, args.to, args.date, root))
        return 0
    except (NotesError, rv.VersionError, OSError) as exc:
        print("notes: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main("notes", sys.argv[1:]))
