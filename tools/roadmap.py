#!/usr/bin/env python3
"""Row files (AUTO-03, finding F-029): ROADMAP.md plus one file per filed or
finished row, composed by one loader.

    roadmap.py rows [--open] [--untagged] [--json] [--root R]
        one row id per line (ROADMAP.md first, then docs/roadmap/new/);
        --open: open rows only; --untagged: rows without the upper-case word
        BLOCKED; --json: the row dicts, with "waits" (the reasons an open
        row waits on its DEPENDS: ids, "waits on <id>" or
        "waits on <id> (no such row)")
    roadmap.py lint [--open-only] [--root R]
        exit 0 and "roadmap lint: ok <n> rows", else exit 1 and one line per
        problem; every '- [' bullet of ROADMAP.md and every row file is
        checked (--open-only: the '- [ ]' bullets of ROADMAP.md only, plus
        every row file); docs/roadmap/archive/ is history and is not linted
    roadmap.py new [FILE] [--root R]
        files one open row: its text from FILE, else stdin; writes
        docs/roadmap/new/<ID>.md and prints that repo-relative path
    roadmap.py done ID WHO [--date YYYY-MM-DD] [--root R]
        closes row ID: writes docs/roadmap/done/<ID>.md, one line
        ' -- done <date> (<WHO>)', and prints that repo-relative path

Layout contract (shared with AUTO-02, LOOP-ROWFILES-MERGE,
LOOP-ROWFILES-WORK and LOOP-WATCH-FILE):
- a row file path matches ^docs/roadmap/(new|done)/[A-Z][A-Z0-9-]*\\.md$;
- a new file holds exactly one open row in the ROADMAP grammar
  (tools/loop_base.py ROW_RX; ASCII, LF, at most 700 characters);
- a done file holds exactly one line ' -- done <YYYY-MM-DD> (<who>)'; the
  loader appends it to the row's first line, which marks the row done; a
  done file without a row fails lint;
- 'DEPENDS: <ids>' in a row's text names the rows it waits on (the ids up
  to the next full stop);
- a row's brief is docs/plan/briefs/<ID>.md, matched on the exact id.

new and done are the only writers of row files and only ever add a file:
an existing path, a bad id or a bad row is refused (exit 1, cause on
stderr). Neither commits; the caller runs `git add -N` and commits the one
path. Folding the files into ROADMAP.md is tools/roadmap_fold.py (AUTO-02).
Stdlib only.
"""

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from loop_base import BLOCKED_RX, DEP_ID_RX, ROW_CONT_RX, ROW_ID, ROW_RX  # noqa: E402
from loop_roadmap import flip_roadmap, roadmap_rows  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ROADMAP_REL = "ROADMAP.md"
NEW_REL = "docs/roadmap/new"
DONE_REL = "docs/roadmap/done"
ARCHIVE_REL = "docs/roadmap/archive"
BRIEFS_REL = "docs/plan/briefs"
ROW_MAX = 700
FILE_ID = r"[A-Z][A-Z0-9-]*"
PATH_RX = re.compile(r"^docs/roadmap/(new|done)/(" + FILE_ID + r")\.md$")
FILE_ID_RX = re.compile(r"^" + FILE_ID + r"$")
ROW_ID_RX = re.compile(r"^" + ROW_ID + r"$")
DONE_LINE_RX = re.compile(r"^ -- done (\d{4}-\d{2}-\d{2}) \(([^\n]+)\)$")
DEPENDS_TEXT_RX = re.compile(r"\bDEPENDS:([^.]*)")
BULLET = "- ["
OPEN_BULLET = "- [ ]"
LANE_HINT_RX = re.compile(r"^\(([a-z][a-z0-9-]*)\)")
PRIORITY_HINT = "priority"


class RowFileError(ValueError):
    """A refused row-file write: the message is the cause."""


# ---------------------------------------------------------------- reading


def _read(path):
    return Path(path).read_bytes().decode("utf-8", errors="replace")


def _row_files(root, rel):
    """Sorted .md paths of one row-file folder ([] when it does not exist)."""
    d = Path(root) / rel
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir() if p.is_file() and p.suffix == ".md")


def depends(text):
    """The row ids named after 'DEPENDS:' up to the next full stop, in order,
    each once ('DEPENDS: none.' -> [])."""
    out = []
    for m in DEPENDS_TEXT_RX.finditer(text or ""):
        for dep in DEP_ID_RX.findall(m.group(1)):
            if dep not in out:
                out.append(dep)
    return out


def done_marks(root):
    """{id: done line} of the well-formed done files."""
    out = {}
    for p in _row_files(root, DONE_REL):
        line = _read(p).rstrip("\n")
        if FILE_ID_RX.match(p.stem) and DONE_LINE_RX.match(line):
            out[p.stem] = line
    return out


def _apply_done(text, marks):
    """text with each open row named in marks flipped to [x] and its done
    line appended to the row's first line (the loop's flip form)."""
    for iid, line in marks.items():
        text = flip_roadmap(text, iid, line[len(" -- "):])
    return text


def load_rows(root=ROOT):
    """The row dicts of loop_roadmap.roadmap_rows for ROADMAP.md, then for
    each docs/roadmap/new/ file, with the done files applied; each row also
    carries 'depends' (its DEPENDS: ids) and 'source' ('roadmap' or 'new').
    The first row of an id wins."""
    root = Path(root)
    marks = done_marks(root)
    rows, seen = [], set()
    sources = []
    rm = root / ROADMAP_REL
    if rm.is_file():
        sources.append(("roadmap", _read(rm)))
    for p in _row_files(root, NEW_REL):
        sources.append(("new", _read(p)))
    for source, text in sources:
        for row in roadmap_rows(_apply_done(text, marks)):
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            row["depends"] = depends(row["text"])
            row["source"] = source
            rows.append(row)
    return rows


def waits(rows):
    """{id: [reason, ...]} for each open row with a dependency that is not
    done: 'waits on <id>' (an open row) or 'waits on <id> (no such row)'."""
    by_id = {r["id"]: r for r in rows}
    out = {}
    for r in rows:
        if not r["open"]:
            continue
        why = []
        for dep in r.get("depends", ()):
            if dep not in by_id:
                why.append(f"waits on {dep} (no such row)")
            elif by_id[dep]["open"]:
                why.append(f"waits on {dep}")
        if why:
            out[r["id"]] = why
    return out


def is_tagged(row):
    """True when the row text carries the upper-case word BLOCKED."""
    return bool(BLOCKED_RX.search(row.get("text", "")))


def brief_path(root, row_id):
    """docs/plan/briefs/<ID>.md for exactly this id, or None."""
    if not ROW_ID_RX.match(row_id or ""):
        return None
    p = Path(root) / BRIEFS_REL / f"{row_id}.md"
    return p if p.is_file() else None


def used_ids(root=ROOT):
    """Every id named by a '- [' row of ROADMAP.md, docs/roadmap/new/ and
    docs/roadmap/archive/, and by a docs/roadmap/new|done/ file name."""
    root = Path(root)
    out = set()
    texts = []
    rm = root / ROADMAP_REL
    if rm.is_file():
        texts.append(_read(rm))
    for rel in (NEW_REL, ARCHIVE_REL):
        texts.extend(_read(p) for p in _row_files(root, rel))
    for text in texts:
        for line in text.splitlines():
            m = ROW_RX.match(line)
            if m:
                out.add(m.group(2))
    for rel in (NEW_REL, DONE_REL):
        out.update(p.stem for p in _row_files(root, rel))
    return out


# ---------------------------------------------------------------- lint


def _bullet_problems(where, line):
    """Problems of one '- [' bullet line (empty when it is a clean row)."""
    m = ROW_RX.match(line)
    if not m:
        return [f"{where}: row-like bullet does not parse: {line[:80]}"]
    rest = m.group(4)
    if rest.lower().startswith("(" + PRIORITY_HINT + ")"):
        rest = rest[len(PRIORITY_HINT) + 2:].lstrip()
    h = LANE_HINT_RX.match(rest)
    if h and h.group(1) != PRIORITY_HINT:
        return [f"{where}: unknown lane hint ({h.group(1)}) in row {m.group(2)}"]
    return []


def new_file_problems(rel, text):
    """Problems of one docs/roadmap/new/ file's text."""
    probs = []
    try:
        text.encode("ascii")
    except UnicodeEncodeError:
        probs.append(f"{rel}: not ASCII")
    if "\r" in text:
        probs.append(f"{rel}: not LF")
    if len(text.rstrip("\n")) > ROW_MAX:
        probs.append(f"{rel}: row over {ROW_MAX} characters")
    lines = text.rstrip("\n").split("\n")
    heads = [ln for ln in lines if ln.startswith(BULLET)]
    if len(heads) != 1 or not lines[0].startswith(BULLET):
        probs.append(f"{rel}: holds {len(heads)} rows, not exactly one")
        return probs
    bad = _bullet_problems(rel, lines[0])
    if bad:
        return probs + bad
    m = ROW_RX.match(lines[0])
    if m.group(1) != " ":
        probs.append(f"{rel}: row {m.group(2)} is not open (close it with a done file)")
    if m.group(2) != Path(rel).stem:
        probs.append(f"{rel}: row id {m.group(2)} does not match the file name")
    for ln in lines[1:]:
        if not ROW_CONT_RX.match(ln):
            probs.append(f"{rel}: stray line outside the row: {ln[:80]}")
            break
    return probs


def done_file_problems(rel, text):
    """Problems of one docs/roadmap/done/ file's text (row existence aside)."""
    if "\r" in text:
        return [f"{rel}: not LF"]
    body = text[:-1] if text.endswith("\n") else text
    if "\n" in body or not DONE_LINE_RX.match(body):
        return [f"{rel}: not exactly one line ' -- done <YYYY-MM-DD> (<who>)'"]
    try:
        body.encode("ascii")
    except UnicodeEncodeError:
        return [f"{rel}: not ASCII"]
    return []


def lint(root=ROOT, open_only=False):
    """Problems of ROADMAP.md and the row files, one string each ([] = clean).

    Every '- [' bullet of ROADMAP.md must parse as a row (ROW_RX), carry no
    unknown lane hint and hold an id no other row holds; open_only lints the
    '- [ ]' bullets only (a repeat counts when one of its rows is open).
    Every new file must hold one open row named by its file name, every done
    file one done line whose row exists. docs/roadmap/archive/ is history and
    is not linted."""
    root = Path(root)
    probs = []
    seen = {}  # id -> [(where, open)]
    rm = root / ROADMAP_REL
    text = _read(rm) if rm.is_file() else ""
    for n, line in enumerate(text.splitlines(), 1):
        if not line.startswith(BULLET):
            continue
        if open_only and not line.startswith(OPEN_BULLET):
            continue
        where = f"{ROADMAP_REL}:{n}"
        bad = _bullet_problems(where, line)
        probs.extend(bad)
        m = ROW_RX.match(line)
        if m:
            seen.setdefault(m.group(2), []).append((where, m.group(1) == " "))
    if open_only:  # the done rows still count as holders of their ids
        for n, line in enumerate(text.splitlines(), 1):
            m = ROW_RX.match(line)
            if m and m.group(1) != " ":
                seen.setdefault(m.group(2), []).append((f"{ROADMAP_REL}:{n}", False))
    for sub, checker in ((NEW_REL, new_file_problems), (DONE_REL, done_file_problems)):
        d = root / sub
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            rel = f"{sub}/{p.name}"
            if not p.is_file() or not PATH_RX.match(rel):
                probs.append(f"{rel}: not a row file name (<ID>.md, ID upper-case)")
                continue
            body = _read(p)
            probs.extend(checker(rel, body))
            if sub == NEW_REL:
                m = ROW_RX.match(body.split("\n", 1)[0])
                if m:
                    seen.setdefault(m.group(2), []).append((rel, m.group(1) == " "))
    for iid, where in seen.items():
        if len(where) > 1 and (not open_only or any(o for _, o in where)):
            probs.append(f"repeated row id {iid}: " + ", ".join(w for w, _ in where))
    for p in _row_files(root, DONE_REL):
        if PATH_RX.match(f"{DONE_REL}/{p.name}") and p.stem not in seen:
            probs.append(f"{DONE_REL}/{p.name}: done file without a row {p.stem}")
    return probs


# ---------------------------------------------------------------- writers


def _add_file(root, rel, text):
    """Create root/rel with text (ASCII, LF); refuse an existing path."""
    path = Path(root) / rel
    if path.exists():
        raise RowFileError(f"{rel} exists (row files are add-only)")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "x", encoding="ascii", newline="\n") as fh:
            fh.write(text)
    except FileExistsError:
        raise RowFileError(f"{rel} exists (row files are add-only)") from None
    return rel


def write_new(root, row_text):
    """File one open row as docs/roadmap/new/<ID>.md; return that
    repo-relative path. Refuses a bad row (not exactly one open row in the
    ROADMAP grammar, not ASCII, over 700 characters, an id that is not a file
    id) and an id already used in ROADMAP.md, docs/roadmap/new|done/ or
    docs/roadmap/archive/. Never commits."""
    text = str(row_text).replace("\r\n", "\n").rstrip("\n") + "\n"
    m = ROW_RX.match(text.split("\n", 1)[0])
    if not m:
        raise RowFileError("not a row in the ROADMAP grammar")
    iid = m.group(2)
    if not FILE_ID_RX.match(iid):
        raise RowFileError(f"bad row id {iid} for a row file")
    rel = f"{NEW_REL}/{iid}.md"
    probs = new_file_problems(rel, text)
    if probs:
        raise RowFileError("; ".join(probs))
    if (Path(root) / rel).exists():
        raise RowFileError(f"{rel} exists (row files are add-only)")
    if iid in used_ids(root):
        raise RowFileError(f"row id {iid} is already used")
    return _add_file(root, rel, text)


def write_done(root, row_id, note, date=None):
    """Close row row_id: write docs/roadmap/done/<ID>.md, one line
    ' -- done <date> (<note>)' (date: today unless given); return that
    repo-relative path. Refuses a bad id, an empty, multi-line or non-ASCII
    note, a bad date, an id with no row, a row already done and an existing
    path. Never commits."""
    row_id = str(row_id or "")
    if not FILE_ID_RX.match(row_id) or not ROW_ID_RX.match(row_id):
        raise RowFileError(f"bad row id {row_id!r}")
    rel = f"{DONE_REL}/{row_id}.md"
    if (Path(root) / rel).exists():
        raise RowFileError(f"{rel} exists (row files are add-only)")
    note = str(note or "").strip()
    day = date or _dt.date.today().isoformat()
    line = f" -- done {day} ({note})"
    if not note or done_file_problems(rel, line + "\n"):
        raise RowFileError(f"bad done line {line!r}")
    try:
        _dt.date.fromisoformat(day)
    except ValueError:
        raise RowFileError(f"bad date {day!r}") from None
    row = next((r for r in load_rows(root) if r["id"] == row_id), None)
    if row is None:
        raise RowFileError(f"no row {row_id} in ROADMAP.md or {NEW_REL}/")
    if not row["open"]:
        raise RowFileError(f"row {row_id} is already done")
    return _add_file(root, rel, line + "\n")


# ---------------------------------------------------------------- CLI


def main(argv=None):
    ap = argparse.ArgumentParser(prog="roadmap.py", description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(ROOT))
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("rows")
    p.add_argument("--open", action="store_true")
    p.add_argument("--untagged", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--root", default=argparse.SUPPRESS)
    p = sub.add_parser("lint")
    p.add_argument("--open-only", action="store_true")
    p.add_argument("--root", default=argparse.SUPPRESS)
    p = sub.add_parser("new")
    p.add_argument("file", nargs="?")
    p.add_argument("--root", default=argparse.SUPPRESS)
    p = sub.add_parser("done")
    p.add_argument("id")
    p.add_argument("who")
    p.add_argument("--date")
    p.add_argument("--root", default=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    root = Path(a.root)
    if a.cmd == "rows":
        rows = load_rows(root)
        if a.open:
            rows = [r for r in rows if r["open"]]
        if a.untagged:
            rows = [r for r in rows if not is_tagged(r)]
        if a.json:
            w = waits(load_rows(root))
            for r in rows:
                r["waits"] = w.get(r["id"], [])
            print(json.dumps(rows, indent=1))
        else:
            for r in rows:
                print(r["id"])
        return 0
    if a.cmd == "lint":
        probs = lint(root, open_only=a.open_only)
        for pr in probs:
            print(pr)
        if probs:
            return 1
        print(f"roadmap lint: ok {len(load_rows(root))} rows")
        return 0
    try:
        if a.cmd == "new":
            if a.file:
                text = Path(a.file).read_bytes().decode("ascii")
            else:
                text = sys.stdin.read()
            print(write_new(root, text))
        else:
            print(write_done(root, a.id, a.who, date=a.date))
    except (RowFileError, UnicodeDecodeError, OSError) as e:
        print(f"roadmap {a.cmd}: refused: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
