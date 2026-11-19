#!/usr/bin/env python3
"""ROADMAP-PRUNE (AUTO-02, finding F-028): ROADMAP.md holds open rows only.

    roadmap_fold.py prune [--write] [--date YYYY-MM-DD] [--root R]
        moves every done bullet ('- [x] ' or '- [X] ', whatever its id
        grammar) with its continuation lines, byte for byte, out of
        ROADMAP.md into docs/roadmap/archive/<YYYY-MM>.md (the month of
        --date, default today); section headings, prose, pointer lines and
        open rows stay, and no line is deleted that was not archived
    roadmap_fold.py fold [--write] [--date YYYY-MM-DD] [--root R]
        applies the row files: each docs/roadmap/new/<ID>.md row is appended
        under its '## Lane: <lane>' heading, each docs/roadmap/done/<ID>.md
        line flips its row and is appended to the row's first line; the
        applied files are removed with git rm; then prune

Without --write both print what they would do and change nothing. A fold
that finds a bad row file, a new row whose id is already a different row, or
a done file whose row exists nowhere changes nothing and exits 1. Neither
commits. Row-file layout: tools/roadmap.py (AUTO-03). Stdlib only.
"""

import argparse
import datetime as _dt
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from loop_base import ROW_CONT_RX, ROW_RX  # noqa: E402
from loop_roadmap import flip_roadmap  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ROADMAP_REL = "ROADMAP.md"
NEW_REL = "docs/roadmap/new"
DONE_REL = "docs/roadmap/done"
ARCHIVE_REL = "docs/roadmap/archive"
DEFAULT_LANE = "build"
GIT_TIMEOUT_S = 60
DONE_BULLETS = ("- [x] ", "- [X] ")
BULLET_ID_RX = re.compile(r"^- \[[ xX]\] (\S+)")
HEADING_RX = re.compile(r"^#{1,6} ")
LANE_HEADING = "## Lane: {}"
FILE_ID_RX = re.compile(r"^[A-Z][A-Z0-9-]*$")
DONE_LINE_RX = re.compile(r"^ -- done (\d{4}-\d{2}-\d{2}) \(([^\n]+)\)$")
DATE_RX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class FoldError(ValueError):
    """A refused fold: the message names the file and the cause."""


# ---------------------------------------------------------------- text


def _read(path):
    return Path(path).read_bytes().decode("utf-8")


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _lines(text):
    """text as lines that keep their own '\\n' (''.join gives text back)."""
    return text.splitlines(keepends=True)


def _body(line):
    return line.rstrip("\r\n")


def _row_end(lines, i):
    """Index after the bullet at lines[i] and its continuation lines."""
    j = i + 1
    while j < len(lines) and ROW_CONT_RX.match(_body(lines[j])):
        j += 1
    return j


def bullet_id(line):
    m = BULLET_ID_RX.match(line)
    return m.group(1) if m else "?"


def split_done(text):
    """(kept text, [(heading, block)]) where each block is one done bullet
    with its continuation lines exactly as it stood, and heading is the text
    of the nearest heading above it ('' when none)."""
    lines = _lines(text)
    kept, moved, heading, i = [], [], "", 0
    while i < len(lines):
        line = lines[i]
        body = _body(line)
        if HEADING_RX.match(body):
            heading = body.lstrip("#").strip()
        if body.startswith(DONE_BULLETS) or body in ("- [x]", "- [X]"):
            j = _row_end(lines, i)
            moved.append((heading, "".join(lines[i:j])))
            i = j
            continue
        kept.append(line)
        i += 1
    return "".join(kept), moved


def archive_rel(date):
    return f"{ARCHIVE_REL}/{date[:7]}.md"


def archive_text(old, moved, date):
    """The archive file text with this run's blocks appended: one
    '## Pruned <date> from: <heading>' line per run of blocks from one
    section, then the blocks byte for byte."""
    out = old
    if not out:
        out = (f"# ROADMAP archive {date[:7]}\n\n"
               "Done rows moved out of ROADMAP.md by `tools/roadmap_fold.py prune`,\n"
               "byte for byte, in file order. History only: not linted, never\n"
               "dispatched.\n")
    if not out.endswith("\n"):
        out += "\n"
    last = None
    for heading, block in moved:
        if heading != last:
            out += f"\n## Pruned {date} from: {heading or '(top)'}\n\n"
            last = heading
        out += block if block.endswith("\n") else block + "\n"
    return out


def prune_plan(roadmap_text, archive_old, date):
    """(new ROADMAP text, new archive text or None, moved blocks)."""
    kept, moved = split_done(roadmap_text)
    if not moved:
        return roadmap_text, None, []
    return kept, archive_text(archive_old, moved, date), moved


# ---------------------------------------------------------------- fold


def _row_files(root, rel):
    d = Path(root) / rel
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir() if p.is_file() and p.suffix == ".md")


def _find_row(text, row_id):
    """(start, end) line indexes of the first row with this id, or None."""
    lines = _lines(text)
    for i, line in enumerate(lines):
        m = ROW_RX.match(_body(line))
        if m and m.group(2) == row_id:
            return i, _row_end(lines, i)
    return None


def _row_is_open(text, row_id):
    span = _find_row(text, row_id)
    if span is None:
        return None
    return _lines(text)[span[0]].startswith("- [ ] ")


def append_under_lane(text, lane, block):
    """text with block appended at the end of the '## Lane: <lane>' section
    (after its last non-blank line); a missing section is added at the end."""
    lines = _lines(text)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    head = LANE_HEADING.format(lane)
    start = next((i for i, ln in enumerate(lines) if _body(ln) == head), None)
    if not block.endswith("\n"):
        block += "\n"
    if start is None:
        sep = "" if not lines or _body(lines[-1]) == "" else "\n"
        return "".join(lines) + f"{sep}{head}\n\n{block}"
    end = start + 1
    while end < len(lines) and not HEADING_RX.match(_body(lines[end])):
        end += 1
    at = end
    while at > start + 1 and _body(lines[at - 1]) == "":
        at -= 1
    if at == start + 1:  # empty section: keep one blank line under the heading
        block = "\n" + block
    tail = lines[at:]
    if tail and _body(tail[0]) != "" and not block.endswith("\n\n"):
        block += "\n"
    return "".join(lines[:at]) + block + "".join(tail)


def fold_plan(root, roadmap_text):
    """(folded ROADMAP text, [(path, action)]) for the row files under root;
    raises FoldError on the first file it cannot apply."""
    root = Path(root)
    text, actions = roadmap_text, []
    archived = set()
    for p in _row_files(root, ARCHIVE_REL):
        for line in _read(p).splitlines():
            m = ROW_RX.match(line)
            if m:
                archived.add(m.group(2))
    for p in _row_files(root, NEW_REL):
        rel = f"{NEW_REL}/{p.name}"
        block = _read(p)
        lines = _lines(block)
        m = ROW_RX.match(_body(lines[0])) if lines else None
        if not m or m.group(2) != p.stem or not FILE_ID_RX.match(p.stem):
            raise FoldError(f"{rel}: not one row with id {p.stem}")
        if _row_end(lines, 0) != len(lines):
            raise FoldError(f"{rel}: lines after the row")
        span = _find_row(text, p.stem)
        if span is not None:
            have = "".join(_lines(text)[span[0]:span[1]])
            if have.rstrip("\n") != block.rstrip("\n"):
                raise FoldError(f"{rel}: id {p.stem} is already a different row")
            actions.append((rel, f"{p.stem} already in ROADMAP.md"))
            continue
        if p.stem in archived:
            raise FoldError(f"{rel}: id {p.stem} is already an archived row")
        lane = m.group(3) or DEFAULT_LANE
        text = append_under_lane(text, lane, block)
        actions.append((rel, f"add {p.stem} under {LANE_HEADING.format(lane)}"))
    for p in _row_files(root, DONE_REL):
        rel = f"{DONE_REL}/{p.name}"
        line = _read(p).rstrip("\n")
        if not FILE_ID_RX.match(p.stem) or not DONE_LINE_RX.match(line):
            raise FoldError(f"{rel}: not one ' -- done <YYYY-MM-DD> (<who>)' line")
        state = _row_is_open(text, p.stem)
        if state is True:
            text = flip_roadmap(text, p.stem, line[len(" -- "):])
            actions.append((rel, f"flip {p.stem}"))
        elif state is False or p.stem in archived:
            actions.append((rel, f"{p.stem} already done"))
        else:
            raise FoldError(f"{rel}: no row {p.stem} in ROADMAP.md or the archive")
    return text, actions


def _git(root, *args):
    try:
        r = subprocess.run(["git", *args], cwd=str(root), capture_output=True,
                           text=True, timeout=GIT_TIMEOUT_S)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _git_rm(root, rel):
    """git rm the path. A file git refuses (staged but never committed,
    untracked, or no git) is unlinked and its index entry, if any, dropped:
    its content is already in ROADMAP.md."""
    if _git(root, "rm", "-q", "--", rel):
        return
    p = Path(root) / rel
    if p.exists():
        p.unlink()
    _git(root, "rm", "-q", "--cached", "--ignore-unmatch", "--", rel)


# ---------------------------------------------------------------- commands


def prune(root=ROOT, date=None, write=False, out=print):
    """Run prune; returns the number of rows moved."""
    root = Path(root)
    date = date or _dt.date.today().isoformat()
    rm = root / ROADMAP_REL
    arel = archive_rel(date)
    ap = root / arel
    old = _read(ap) if ap.is_file() else ""
    text, arch, moved = prune_plan(_read(rm), old, date)
    for heading, block in moved:
        out(f"move {bullet_id(block)} ({len(_lines(block))} lines) from "
            f"'{heading or '(top)'}' to {arel}")
    if not moved:
        out("prune: no done rows in ROADMAP.md")
        return 0
    if write:
        _write(ap, arch)
        _write(rm, text)
        out(f"prune: moved {len(moved)} rows to {arel}")
    else:
        out(f"prune: would move {len(moved)} rows to {arel} (dry run; --write applies)")
    return len(moved)


def fold(root=ROOT, date=None, write=False, out=print):
    """Run fold then prune; returns the number of row files applied."""
    root = Path(root)
    rm = root / ROADMAP_REL
    text, actions = fold_plan(root, _read(rm))
    for rel, what in actions:
        out(f"{what} ({rel})")
    if not actions:
        out("fold: no row files")
    if write and actions:
        _write(rm, text)
        for rel, _ in actions:
            _git_rm(root, rel)
        out(f"fold: applied {len(actions)} row files")
        prune(root, date=date, write=True, out=out)
    elif actions:
        out(f"fold: would apply {len(actions)} row files (dry run; --write applies)")
        date = date or _dt.date.today().isoformat()
        arel = archive_rel(date)
        ap = root / arel
        _, _, moved = prune_plan(text, _read(ap) if ap.is_file() else "", date)
        out(f"prune: would move {len(moved)} rows to {arel} (dry run; --write applies)")
    else:
        prune(root, date=date, write=write, out=out)
    return len(actions)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="roadmap_fold.py",
                                 description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("prune", "fold"):
        p = sub.add_parser(name)
        p.add_argument("--write", action="store_true")
        p.add_argument("--date")
        p.add_argument("--root", default=str(ROOT))
    a = ap.parse_args(argv)
    if a.date and not DATE_RX.match(a.date):
        print(f"bad --date {a.date}; want YYYY-MM-DD", file=sys.stderr)
        return 2
    root = Path(a.root)
    if not (root / ROADMAP_REL).is_file():
        print(f"no {ROADMAP_REL} under {root}", file=sys.stderr)
        return 2
    try:
        if a.cmd == "prune":
            prune(root, date=a.date, write=a.write)
        else:
            fold(root, date=a.date, write=a.write)
    except FoldError as e:
        print(f"fold refused: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
