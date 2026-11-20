"""LOOP-WATCH-FILE (F-030, AUTO-05, ruling Q-12): the two row primitives and
the unattended add-only commit path.

file_pending(root, now, git, budget, halted, dry) -> tick lines

The tick step (LOOP-WATCH-WIRE) calls it after the work list. It turns the
queued findings of ops/runtime/watch/pending.json (tools/upstream_watch.py)
into committed row files, one commit per file:

- a finding whose template act is "row" becomes docs/roadmap/new/<ID>.md
  (tools/roadmap.py write_new), its text rendered only from the tracked
  template (tools/watch_rows.py render);
- a finding whose template act is "gate" becomes docs/roadmap/done/<ID>.md
  (tools/roadmap.py write_done), one line
  ' -- done <YYYY-MM-DD> (watch: <source> <key>)'.
Findings of the other acts (note, dive) are not this module's and stay
pending untouched.

Filing runs only when all hold: HALT absent (the halted flag and the file);
not a dry run; no flag ops/runtime/watch/COMMIT_FAULT; fewer than 3 files of
that kind committed this local day (counted from git log of docs/roadmap/new
and docs/roadmap/done by the watch commit subject and the commit date);
the usage gate under 60 percent of the runs cap (a row marked priority and
every done file skip this one test); the id unused in ROADMAP.md,
docs/roadmap/new/, docs/roadmap/done/ and docs/roadmap/archive/ (a done file:
no done file yet and the row open). A done finding that flips a gate row
(id GATE-... or a 'BLOCKED: gate' row) is written before any other done file.

Per file: render, parse (exactly one row, the expected id and lane, ASCII,
LF, at most 700 characters), write the path (it must match
^docs/roadmap/(new|done)/[A-Z][A-Z0-9-]*\\.md$ and not exist at HEAD),
`git add -N -- <path>`, then
`git commit -m "chore(roadmap): file <ID> (watch <source>)" -- <path>`
through the `git` callable the tick passes (al_loop's _git runs a commit
under the kit git lock); the identity is the local git config's, no trailer
(FLEET item 17). Read back: HEAD is one new commit on the old HEAD,
`git show --name-only --format=%H HEAD` names exactly that path and
`git status --short -- <path>` is empty; anything else writes COMMIT_FAULT
(the Q-12 tripwire; only a session removes it) and stops all filing. Nothing
here ever reverts, resets or amends a commit. A failed commit removes the
untracked file (and its intent-to-add entry) and keeps the finding pending.
A filed or dropped finding leaves pending.json; a waiting one stays.

`git(args, cwd)` returns a CompletedProcess-like object (returncode,
stdout, stderr). `budget` has readable(), used() and cap (al_loop's
governor budget); None or unreadable fails closed. `now` is epoch seconds.
This module never imports al_loop. Python stdlib only.
"""

import datetime as _dt
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
for _p in (str(ROOT), str(TOOLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import loop_base  # noqa: E402
import roadmap  # noqa: E402
import upstream_watch  # noqa: E402
import watch_rows  # noqa: E402

FAULT_REL = upstream_watch.WATCH_REL / "COMMIT_FAULT"
HALT_REL = loop_base.HALT_REL
DAY_CAP = 3
SOFT_GATE = 0.60
KINDS = {"row": roadmap.NEW_REL, "gate": roadmap.DONE_REL}
SUBJECT = "chore(roadmap): file {id} (watch {source})"
SUBJECT_RX = re.compile(r"^chore\(roadmap\): file [A-Z][A-Z0-9-]* \(watch [a-z][a-z0-9_-]*\)$")
SOURCE_RX = re.compile(r"^[a-z][a-z0-9_-]{0,47}$")
# The key goes into the done line; a short word only, never an upstream sentence.
KEY_RX = re.compile(r"^[A-Za-z0-9._:/@+-]{1,80}$")
LOG_MAX = 200
LINE_MAX = 200


def _line(text):
    return "watch file: " + loop_base.ascii_text(" ".join(str(text).split()), LINE_MAX)


def _ok(r):
    return r is not None and getattr(r, "returncode", 1) == 0


def _out(r):
    return (getattr(r, "stdout", "") or "") if r is not None else ""


def _git(git, root, args):
    try:
        return git(list(args), Path(root))
    except Exception as exc:  # noqa: BLE001 - a git failure is a result, never a crash
        return _Failed(f"{type(exc).__name__}: {exc}")


class _Failed:
    def __init__(self, err):
        self.returncode, self.stdout, self.stderr = 1, "", err


def _local_day(epoch):
    return _dt.datetime.fromtimestamp(epoch).date()


def fault_text(root):
    """The COMMIT_FAULT flag's text, or None when no flag exists."""
    p = Path(root) / FAULT_REL
    if not p.exists():
        return None
    try:
        return p.read_text(encoding="ascii", errors="replace").strip() or "set"
    except OSError:
        return "set"


def _set_fault(root, now, why):
    loop_base.atomic_write(
        Path(root) / FAULT_REL,
        f"{loop_base.iso(now)} {loop_base.ascii_text(why, 300)}\n"
        "Filing stopped (Q-12 tripwire). A session checks HEAD and removes this file.\n")


def committed_today(root, git, now):
    """{"row": n, "gate": n}: watch commits this local day per folder, or
    None when git log fails (fail closed)."""
    day = _local_day(now)
    out = {}
    for act, rel in KINDS.items():
        r = _git(git, root, ["log", f"--max-count={LOG_MAX}", "--format=%ct%x09%s",
                             "--", rel])
        if not _ok(r):
            return None
        n = 0
        for ln in _out(r).splitlines():
            stamp, _, subject = ln.partition("\t")
            if not stamp.strip().isdigit() or not SUBJECT_RX.match(subject.strip()):
                continue
            if _local_day(int(stamp)) == day:
                n += 1
        out[act] = n
    return out


def soft_gate_open(budget):
    """True when usage is under 60 percent of the cap (fail closed)."""
    try:
        if budget is None or not budget.readable():
            return False
        cap = float(budget.cap)
        return cap > 0 and float(budget.used()) < SOFT_GATE * cap
    except Exception:  # noqa: BLE001 - an unreadable budget holds the gated rows
        return False


def _ident(f):
    return tuple(str(f.get(k)) for k in ("source", "key", "kind"))


def _gate_row_ids(root):
    """Ids of the rows that are gates (id GATE-... or a BLOCKED: gate tag)."""
    out = set()
    for row in roadmap.load_rows(root):
        if row["id"].startswith("GATE-") or re.search(r"\bBLOCKED:\s*gate\b",
                                                       row.get("text", "")):
            out.add(row["id"])
    return out


def _gate_id(kdef, tokens, today):
    """(row id, None) for a gate finding, or (None, reason)."""
    declared = kdef.get("tokens") or {}
    tokens = tokens or {}
    if not isinstance(tokens, dict) or set(tokens) != set(declared):
        return None, f"tokens {sorted(tokens) if isinstance(tokens, dict) else tokens} " \
                     f"are not {sorted(declared)}"
    for name, value in tokens.items():
        bad = watch_rows._bad_value(name, value, declared[name])
        if bad:
            return None, bad
    values = dict(tokens)
    values.update({"YYYY-MM-DD": today, "YYYYMMDD": today.replace("-", "")})
    row_id = watch_rows._fill(kdef["id"], values)
    if not roadmap.ROW_ID_RX.match(row_id) or not roadmap.FILE_ID_RX.match(row_id):
        return None, f"id {row_id} is not a row id"
    return row_id, None


def _at_head(root, git, rel):
    """True when rel exists in HEAD; None when git cannot tell."""
    r = _git(git, root, ["ls-tree", "--name-only", "HEAD", "--", rel])
    if not _ok(r):
        return None
    return any(ln.strip() == rel for ln in _out(r).splitlines())


def _head(root, git):
    r = _git(git, root, ["rev-parse", "--verify", "-q", "HEAD"])
    return _out(r).strip() if _ok(r) else None


def _unstage_and_remove(root, git, rel):
    _git(git, root, ["rm", "--cached", "--quiet", "--ignore-unmatch", "--", rel])
    try:
        (Path(root) / rel).unlink()
    except OSError:
        pass


def _read_back(root, git, rel, before):
    """None when HEAD is exactly one new commit on `before` naming only rel
    and rel is clean, else why."""
    after = _head(root, git)
    if not after or after == before:
        return "HEAD did not move"
    r = _git(git, root, ["rev-parse", "--verify", "-q", "HEAD^"])
    if not _ok(r) or _out(r).strip() != before:
        return "HEAD is not one commit on the old HEAD"
    r = _git(git, root, ["show", "--name-only", "--format=%H", "HEAD"])
    if not _ok(r):
        return "git show failed"
    lines = [ln.strip() for ln in _out(r).splitlines() if ln.strip()]
    if not lines or lines[0] != after:
        return "git show did not name HEAD"
    paths = lines[1:]
    if paths != [rel]:
        return f"commit names {len(paths)} path(s): " + ", ".join(paths[:5])
    r = _git(git, root, ["status", "--short", "--", rel])
    if not _ok(r) or _out(r).strip():
        return "the filed path is not clean after the commit"
    return None


def _commit(root, git, rel, row_id, source):
    """('ok' | 'failed' | 'fault', why)."""
    if not roadmap.PATH_RX.match(rel):
        return "failed", f"path {rel} is not a row file path"
    before = _head(root, git)
    if not before:
        return "failed", "no HEAD"
    r = _git(git, root, ["add", "-N", "--", rel])
    if not _ok(r):
        _unstage_and_remove(root, git, rel)
        return "failed", "git add -N failed"
    subject = SUBJECT.format(id=row_id, source=source)
    r = _git(git, root, ["commit", "-m", subject, "--", rel])
    if not _ok(r):
        if _head(root, git) != before:
            return "fault", "a failed commit moved HEAD"
        _unstage_and_remove(root, git, rel)
        err = (getattr(r, "stderr", "") or _out(r) or "").strip().splitlines()
        return "failed", "commit failed" + (f": {err[-1]}" if err else "")
    why = _read_back(root, git, rel, before)
    if why:
        return "fault", why
    return "ok", None


def _plan(table, findings, gates_open, today):
    """Order the findings: gate flips first, then every other one in queue
    order. Returns [(finding, kdef or None)]."""
    flips, rest = [], []
    for f in findings:
        kdef = table.get(f.get("kind"))
        if kdef is not None and kdef.get("act") == "gate":
            rid, _why = _gate_id(kdef, f.get("tokens"), today)
            if rid and (rid.startswith("GATE-") or rid in gates_open):
                flips.append((f, kdef))
                continue
        rest.append((f, kdef))
    return flips + rest


def file_pending(root, now, git, budget, halted=False, dry=False):
    """File the pending findings (module docstring); return tick lines."""
    root = Path(root)
    queue = upstream_watch.pending(root)
    if not queue:
        return []
    if halted or (root / HALT_REL).exists():
        return [_line(f"HALT: {len(queue)} finding(s) pending, nothing filed")]
    if dry:
        return [_line(f"dry run: {len(queue)} finding(s) pending, nothing filed")]
    fault = fault_text(root)
    if fault is not None:
        return [_line(f"COMMIT_FAULT set, filing stopped ({len(queue)} pending): "
                      f"{fault.splitlines()[0]}")]
    try:
        table = watch_rows.load(root)
    except watch_rows.WatchRowsError as exc:
        return [_line(f"templates refused, nothing filed: {exc}")]
    counts = committed_today(root, git, now)
    if counts is None:
        return [_line("git log failed, nothing filed")]
    today = _local_day(now).isoformat()
    soft_open = soft_gate_open(budget)
    lines, gone = [], set()
    waited = {"row": 0, "gate": 0, "soft": 0}
    try:
        gates_open = _gate_row_ids(root)
    except Exception:  # noqa: BLE001 - ordering only; never a tick failure
        gates_open = set()
    for f, kdef in _plan(table, queue, gates_open, today):
        if kdef is None:
            lines.append(_line(f"{f.get('source')} {f.get('kind')}: dropped (unknown kind)"))
            gone.add(_ident(f))
            continue
        act = kdef.get("act")
        if act not in KINDS:
            continue  # note / dive findings belong to other steps
        source = f.get("source") or ""
        tag = f"{source} {f.get('kind')}"
        if not isinstance(source, str) or not SOURCE_RX.match(source):
            lines.append(_line(f"{tag}: dropped (bad source name)"))
            gone.add(_ident(f))
            continue
        if counts[act] >= DAY_CAP:
            waited[act] += 1
            continue
        if act == "row":
            if not kdef.get("priority") and not soft_open:
                waited["soft"] += 1
                continue
            row_id, text = watch_rows.render(table, f.get("kind"), f.get("tokens"), today)
            if row_id is None:
                lines.append(_line(f"{tag}: dropped ({text})"))
                gone.add(_ident(f))
                continue
            rel = f"{roadmap.NEW_REL}/{row_id}.md"
        else:
            row_id, why = _gate_id(kdef, f.get("tokens"), today)
            key = f.get("key")
            if row_id is None or not isinstance(key, str) or not KEY_RX.match(key):
                lines.append(_line(f"{tag}: dropped ({why or 'key is not a short word'})"))
                gone.add(_ident(f))
                continue
            rel = f"{roadmap.DONE_REL}/{row_id}.md"
        if not roadmap.PATH_RX.match(rel):
            lines.append(_line(f"{tag}: dropped (path {rel} is not a row file path)"))
            gone.add(_ident(f))
            continue
        at_head = _at_head(root, git, rel)
        if at_head is None:
            lines.append(_line(f"{tag}: git ls-tree failed, finding kept"))
            continue
        if at_head:
            lines.append(_line(f"{tag}: dropped ({rel} exists at HEAD)"))
            gone.add(_ident(f))
            continue
        try:
            if act == "row":
                roadmap.write_new(root, text)  # refuses an id already used
            else:
                roadmap.write_done(root, row_id, f"watch: {source} {key}", date=today)
        except roadmap.RowFileError as exc:
            lines.append(_line(f"{tag}: dropped ({exc})"))
            gone.add(_ident(f))
            continue
        state, why = _commit(root, git, rel, row_id, source)
        if state == "ok":
            counts[act] += 1
            gone.add(_ident(f))
            lines.append(_line(f"filed {rel} ({tag})"))
            continue
        if state == "failed":
            lines.append(_line(f"{tag}: {why}; file removed, finding kept"))
            continue
        _set_fault(root, now, f"{rel}: {why}")
        gone.add(_ident(f))  # it is in a commit now; never filed twice
        lines.append(_line(f"COMMIT_FAULT: {rel}: {why}; filing stopped"))
        break
    if waited["row"]:
        lines.append(_line(f"{waited['row']} new row(s) wait: {DAY_CAP} filed today"))
    if waited["gate"]:
        lines.append(_line(f"{waited['gate']} done file(s) wait: {DAY_CAP} filed today"))
    if waited["soft"]:
        lines.append(_line(f"{waited['soft']} row(s) wait: usage at or over "
                           f"{int(SOFT_GATE * 100)} percent of the cap"))
    if gone:
        left = [f for f in upstream_watch.pending(root) if _ident(f) not in gone]
        upstream_watch.set_pending(root, left)
    return lines
