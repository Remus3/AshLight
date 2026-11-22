"""AL loop work list: ROADMAP rows, optional briefs, dependencies and
hand-off items (plan 107 split of tools/al_loop.py, which re-exports every
name here). Rows are read through tools/roadmap.py (ROADMAP.md plus row
files, LOOP-ROWFILES-WORK); a row waits on the `DEPENDS: <ids>` in its own
text and its brief is docs/plan/briefs/<ID>.md (exact id). Stdlib only.

AL ROADMAP.md (repo root) rows are bullets, not table rows:
    - [ ] ID (lane) title. ACCEPT: ...
      continuation lines indented two spaces
`(priority)` jumps the queue; the merge flips `[ ]` to `[x]` and appends the
done note to the row's first line."""

import contextlib
import datetime as _dt
import hashlib
import re
from pathlib import Path

from loop_base import (
    BLOCKED_RX, DEPENDS_RX, DEP_ID_RX, MAX_ATTEMPTS, ROADMAP_REL, ROW_CONT_RX, ROW_RX,
    SKIP_TAGS, STOP, ascii_text,
)
from loop_prompts import resolve_prompt


# ---------------------------------------------------------------- work list

_PRIORITY_RX = re.compile(r"\(priority\)\s*", re.I)
_ACCEPT_RX = re.compile(r"\s*\bACCEPT:")


def roadmap_rows(text):
    """[{"id", "title", "status", "open", "lane", "text"}] from the ROADMAP
    bullets. status is "[ ] priority" / "[ ] open" / "[x] done"; text is the
    whole row (first line plus its continuation lines, without the `(priority)`
    tag), the lane brief; title is text up to its `ACCEPT:` clause. The first
    row of an id wins."""
    rows, cur, seen = [], None, set()
    for line in text.splitlines():
        m = ROW_RX.match(line)
        if m:
            cur = None
            mark, iid, lane, rest = m.group(1), m.group(2), m.group(3), m.group(4)
            if iid in seen:
                continue
            seen.add(iid)
            is_open = mark == " "
            prio = bool(_PRIORITY_RX.search(rest))
            title = _PRIORITY_RX.sub("", rest).strip()
            status = ("[ ] priority" if prio else "[ ] open") if is_open else "[x] done"
            cur = {"id": iid, "title": title or iid, "status": status, "open": is_open,
                   "lane": lane, "text": title}
            rows.append(cur)
        elif cur is not None and ROW_CONT_RX.match(line):
            cur["text"] = (cur["text"] + " " + line.strip()).strip()
        else:
            cur = None
    for r in rows:  # the title is the row's task: its text up to the ACCEPT clause
        r["title"] = _ACCEPT_RX.split(r["text"], 1)[0].strip() or r["id"]
    return rows


def flip_roadmap(text, plan_id, note):
    """The ROADMAP text with open row plan_id flipped to `- [x] ` and the note
    appended to its first line (`-- <note>`)."""
    out = []
    for line in text.split("\n"):
        m = ROW_RX.match(line)
        if m and m.group(2) == plan_id and m.group(1) == " ":
            line = "- [x] " + line[len("- [ ] "):].rstrip() + f" -- {note}"
        out.append(line)
    return "\n".join(out)


def plan_depends(text):
    """The row ids named by the first `Depends on:` line, in order ("none" or
    no such line -> []). Legacy parser only: the work list no longer reads
    `Depends on:` lines (LOOP-ROWFILES-WORK, F-029); `DEPENDS: <ids>` in the
    row text is the one machine-read form (tools/roadmap.py depends)."""
    m = DEPENDS_RX.search(text or "")
    out = []
    for dep in DEP_ID_RX.findall(m.group(1)) if m else ():
        if dep not in out:
            out.append(dep)
    return out


def plan_doc(root, plan_id):
    """Optional brief docs/plan/briefs/<ID>.md text, matched on the exact id
    (tools/roadmap.py brief_path; a prefix glob would hand TC-OAUTH-REG's
    brief to TC-OAUTH-REG-OPEN), or None when there is none. A brief is
    prose for the lane; it gates nothing."""
    import roadmap  # lazy: roadmap imports this module
    p = roadmap.brief_path(root, plan_id)
    if p is None:
        return None
    with contextlib.suppress(OSError):
        return p.read_text(encoding="utf-8", errors="replace")
    return None


def archived_rows(root):
    """The roadmap_rows of every docs/roadmap/archive/*.md file (done rows
    tools/roadmap_fold.py pruned out of ROADMAP.md), each marked done; the
    first row of an id wins. [] when there is no archive."""
    import roadmap  # lazy: roadmap imports this module
    rows, seen = [], set()
    for p in roadmap._row_files(root, roadmap.ARCHIVE_REL):
        try:
            text = p.read_bytes().decode("utf-8", errors="replace")
        except OSError:
            continue
        for r in roadmap_rows(text):
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            r.update(open=False, status="[x] done")
            rows.append(r)
    return rows


def base_kind(rec):
    """The item's own kind; a plan 058 resolve run keeps it in base_kind."""
    return rec.get("base_kind") or rec.get("kind")


# PUBREPO order (MAIN 2026-10-15, item 1b): commit subjects for outsiders.
# Lane commits: Conventional Commits, the item id in the scope; merge commits:
# `merge: <topic>`. No lane or worktree name ever reaches a subject; session
# detail (refute rounds, verifier, loop item) stays in the body.
SUBJECT_MAX = 100
_PLAN_DOC_TAIL_RX = re.compile(r"\s*\(plan doc [^)]*\)\s*$", re.I)
_FIX_HEAD_RX = re.compile(r"^(?:fix|bug)(?:es|ed)?\b[\s:-]*", re.I)
_SCOPE_BAD_RX = re.compile(r"[^a-z0-9-]+")
_LABEL_HEAD_RX = re.compile(r"^(?:plan|order|hand-off|deep-dive)\s+[^\s:]+:?\s*", re.I)


def _clip(text, limit):
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    cut = text[:limit - 3].rsplit(" ", 1)[0] or text[:limit - 3]
    return cut.rstrip(" :;,-") + "..."


def _subject_parts(rec):
    """(type, scope, description) of an item's commit."""
    kind = base_kind(rec)
    iid = _SCOPE_BAD_RX.sub("-", str(rec.get("id", "")).lower()).strip("-") or "item"
    if kind == "deep-dive":
        return "docs", "research", f"idle deep-dive {rec.get('date', '')}".strip()
    if kind == "handoff":
        title = rec.get("text") or rec.get("title") or rec.get("label", "")
    else:
        title = rec.get("title") or _LABEL_HEAD_RX.sub("", rec.get("label", ""), count=1)
    title = _PLAN_DOC_TAIL_RX.sub("", ascii_text(title)).strip()
    ctype = "feat" if kind == "plan" else "chore"
    if kind == "plan" and _FIX_HEAD_RX.match(title):
        ctype, title = "fix", _FIX_HEAD_RX.sub("", title, count=1)
    prefix = {"plan": "plan", "order": "order", "handoff": "handoff"}.get(kind, "item")
    return ctype, f"{prefix}-{iid}", title or "loop item"


def commit_subject(rec, wip=None):
    """Conventional Commits subject of an item's lane commit; `wip` (the
    reason) marks a kept-unmerged commit as chore + WIP."""
    ctype, scope, desc = _subject_parts(rec)
    if wip:
        ctype, desc = "chore", f"WIP ({wip}) {desc}"
    head = f"{ctype}({scope}): "
    return head + _clip(desc, SUBJECT_MAX - len(head))


# AUDIT-LOOP-COMMIT-MSG (audit C2): the lane's own result (root cause / what
# was done) goes into the commit body, so an ACCEPT that asks for it in the
# commit is met by the commit.
RESULT_MAX = 600
_RESULT_RX = re.compile(r"^\s*RESULT:\s*(.+?)\s*$", re.M)
_VERDICT_LINE_RX = re.compile(r"^\s*VERDICT:", re.I)


def result_line(text):
    """The lane's result line: its last `RESULT:` line, else the last
    paragraph of its reply (a trailing VERDICT line ignored); ASCII, one
    line, at most RESULT_MAX chars; "" when there is none."""
    if not text or not str(text).strip():
        return ""
    text = ascii_text(text)
    found = _RESULT_RX.findall(text)
    if found:
        out = found[-1]
    else:
        paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
        paras = [p for p in paras if not _VERDICT_LINE_RX.match(p)] or paras
        out = paras[-1] if paras else ""
    return _clip(out, RESULT_MAX)


def commit_body(rec):
    """Label paragraph (cut at 300) plus a `result:` paragraph when the lane
    left one; the caller appends the refute / verifier lines."""
    body = f"\n\n{ascii_text(rec.get('label', ''), 300)}\n\n"
    if rec.get("result"):
        body += f"result: {ascii_text(rec['result'], RESULT_MAX)}\n\n"
    return body


def merge_subject(rec):
    """`merge: <topic> (<scope>)` for an item's --no-ff merge into main."""
    _, scope, desc = _subject_parts(rec)
    tail = f" ({scope})"
    return "merge: " + _clip(desc, SUBJECT_MAX - len("merge: ") - len(tail)) + tail


# a resolve item copies its record minus these per-run fields
RUN_FIELDS = ("state", "pid", "rc", "error", "verdict", "verify_errors", "finished",
              "updated", "prompt", "worktree", "dispatched")


def resolve_item(rec):
    item = {k: v for k, v in rec.items() if k not in RUN_FIELDS}
    item.update(kind="resolve", base_kind=base_kind(rec))
    item["prompt"] = resolve_prompt(item)
    return item


def dependency_cycles(graph):
    """Each cycle of {id: [dep ids]} once, as [a, b, ..., a]."""
    cycles, state = [], {}

    def visit(node, stack):
        state[node] = 1
        stack.append(node)
        for dep in graph.get(node, ()):
            if state.get(dep) == 1:
                cycles.append(stack[stack.index(dep):] + [dep])
            elif dep in graph and not state.get(dep):
                visit(dep, stack)
        stack.pop()
        state[node] = 2

    for node in sorted(graph):
        if not state.get(node):
            visit(node, [])
    return cycles


def roadmap_flip_time(git, main, dep):
    """ISO commit time of the first-parent commit on main that closed row
    dep: the one that introduced its `[x]` line in ROADMAP.md (the --no-ff
    merge commit for a loop merge) or the one that added its done file
    docs/roadmap/done/<ID>.md (AUTO-03), whichever is earlier; None when
    neither is found. Fallback for dependencies merged before merge()
    recorded merged_at."""
    def first(args):
        r = git(["log", "-m", "--first-parent", "-1", "--format=%cI", *args], main)
        out = (r.stdout or "").strip() if r.returncode == 0 else ""
        return out.splitlines()[0] if out else None

    found = [t for t in (
        first([f"-G^- \\[x\\] {re.escape(dep)}( |$)", "--", ROADMAP_REL.as_posix()]),
        first(["--diff-filter=A", "--", f"docs/roadmap/done/{dep}.md"]),
    ) if t]
    if len(found) < 2:
        return found[0] if found else None
    try:
        return min(found, key=lambda t: _dt.datetime.fromisoformat(t).timestamp())
    except ValueError:
        return found[0]


def resolve_roadmap(base, ours, theirs):
    """Row-level three-way merge of ROADMAP.md (fix-0130), or None. Rows are
    keyed by row id (first line only; continuation lines are prose): a row
    only the lane changed or added takes the lane's line, a row both sides
    changed keeps main's (main is the ledger). Any prose (non-row) change on
    both sides is not guessed at: None."""
    def split(text):
        rows, prose = {}, []
        for line in text.split("\n"):
            m = ROW_RX.match(line)
            if m:
                rows[m.group(2)] = line
            else:
                prose.append(line)
        return rows, prose

    (b_rows, b_prose), (o_rows, o_prose), (t_rows, t_prose) = \
        split(base), split(ours), split(theirs)
    if t_prose != b_prose and t_prose != o_prose:
        return None
    lines = ours.split("\n")
    for iid, line in t_rows.items():
        if line == b_rows.get(iid):
            continue
        if iid not in o_rows:
            at = [i for i, x in enumerate(lines) if ROW_RX.match(x)]
            last = at[-1] if at else len(lines) - 1
            lines.insert(last + 1, line)
            o_rows[iid] = line
        elif o_rows[iid] == b_rows.get(iid):
            lines[lines.index(o_rows[iid])] = line
    for iid, line in b_rows.items():
        if iid not in t_rows and o_rows.get(iid) == line:
            lines.remove(line)
    return "\n".join(lines)


def _norm_words(text):
    return re.findall(r"[a-z0-9]+", text.lower())


LOOP_PREFIX_RX = re.compile(r"^LOOP:\s*")


def handoff_items(text):
    """LOOP: bullets under "Carried forward" as [{"id", "text", "skip"}]; the
    prefix is stripped from text. A bullet without the LOOP: prefix is not a
    work item at all (LOOP-HANDOFF-PREFIX). skip is None or the tag that keeps
    the loop off it (blocked / operator / other-tree / info); a blocked item
    also carries a reason, so the work list shows it and never dispatches it."""
    items, cur, inside = [], None, False
    for line in text.splitlines():
        if line.lower().startswith("carried forward"):
            inside = True
            continue
        if not inside:
            continue
        if line.startswith("- "):
            cur = [line[2:].strip()]
            items.append(cur)
        elif line.startswith("  ") and cur is not None and line.strip():
            cur.append(line.strip())
        elif line.strip() and not line.startswith(" "):
            break
    out = []
    for parts in items:
        m = LOOP_PREFIX_RX.match(parts[0])
        if not m:
            continue
        body = " ".join([parts[0][m.end():]] + parts[1:]).strip()
        hid = "H" + hashlib.sha1(" ".join(_norm_words(body)).encode()).hexdigest()[:6]
        if BLOCKED_RX.search(body):
            out.append({"id": hid, "text": body, "skip": "blocked",
                        "reason": "BLOCKED: operator act (see the hand-off)"})
            continue
        skip = next((tag for tag, rx in SKIP_TAGS if rx.search(body)), None)
        out.append({"id": hid, "text": body, "skip": skip})
    return out


def title_tokens(title):
    return {w for w in _norm_words(title) if len(w) > 2 and w not in STOP}


def is_duplicate(title, existing, threshold=0.6):
    """Normalized token overlap |A&B| / min(|A|, |B|) >= threshold."""
    a = title_tokens(title)
    for other in existing:
        b = title_tokens(other)
        if a and b and len(a & b) / min(len(a), len(b)) >= threshold:
            return other
    return None


def plan_titles(root):
    """{row id: title} of every row (open or done) in tree root, read through
    the loader (tools/roadmap.py load_rows: ROADMAP.md plus row files), plus
    the archived rows of docs/roadmap/archive/, so the dive duplicate check
    still sees done rows the fold pruned. A loaded row wins over an archived
    one of the same id."""
    import roadmap  # lazy: roadmap imports this module
    out = {}
    with contextlib.suppress(OSError):
        out.update((r["id"], r["title"]) for r in archived_rows(root))
    try:
        out.update((r["id"], r["title"]) for r in roadmap.load_rows(Path(root)))
    except OSError:
        pass
    return out


def dispatchable(rec, open_ids=()):
    """paused (the lane worker found HALT / backoff / runs cap before it ran)
    costs no attempt; refused / lost get MAX_ATTEMPTS dispatches; blocked
    (plan 019) waits until no id it needs is an open ROADMAP row, for at most
    MAX_ATTEMPTS blocked runs; merge-conflict (plan 058) with a kept commit
    gets MAX_ATTEMPTS resolve runs."""
    if rec is not None and rec.get("state") == "merge-conflict":
        return bool(rec.get("keep_ref")) and rec.get("resolve_runs", 0) < MAX_ATTEMPTS
    if rec is not None and rec.get("state") == "blocked":
        return (rec.get("blocked_runs", 0) < MAX_ATTEMPTS
                and not set(rec.get("needs") or ()) & set(open_ids))
    return rec is None or rec.get("state") == "paused" or (
        rec.get("state") in ("refused", "lost") and rec.get("attempts", 0) < MAX_ATTEMPTS)


# -- W44 (MAIN ORDER Nee58d0 item 3), AUTO-13: the idle deep-dive is weekly
DIVE_BACKOFF_DAYS = 7
_DIVE_RX = re.compile(r"^docs/research/\d+-deep-dive-(\d{8})\.md$")
_PLAN_RX = re.compile(r"^" + re.escape(ROADMAP_REL.as_posix()) + r"$")


def dive_backoff(history, today, days=DIVE_BACKOFF_DAYS):
    """history = [(YYYYMMDD, plans proposed)] oldest first. True = skip the
    idle dive today: the newest dive (idle or requested) is under `days` days
    old, whatever it proposed (AUTO-13: weekly, no zero-plan streak). A
    requested dive (tools/loop_steps/dive_request.py) has its own rule."""
    if not history:
        return False
    import datetime as _dt
    try:
        last = _dt.datetime.strptime(str(history[-1][0]), "%Y%m%d").date()
    except (ValueError, TypeError, IndexError):
        return False
    return (today - last).days < days


def dive_history(tree, git, limit=40):
    """Each deep-dive commit in `tree` (the one that added a
    docs/research/NNNN-deep-dive-<date>.md), with 1 when that same commit
    touched ROADMAP.md (it proposed rows) else 0; oldest first. `git` is the
    loop's runner, git(args, cwd) -> CompletedProcess. [] when git fails."""
    try:
        r = git(["log", f"-{int(limit)}", "--diff-filter=AM", "--name-only",
                 "--format=format:@", "--", "docs/research/", ROADMAP_REL.as_posix()], tree)
    except Exception:  # noqa: BLE001 - OSError, timeout: no history, no backoff
        return []
    if getattr(r, "returncode", 1) != 0 or not isinstance(getattr(r, "stdout", None), str):
        return []
    out = {}
    for group in r.stdout.split("@")[1:]:
        names = [n.strip() for n in group.splitlines() if n.strip()]
        dates = [m.group(1) for m in map(_DIVE_RX.match, names) if m]
        if dates:  # a later edit of the same dive file folds into its date
            n = 1 if any(_PLAN_RX.match(x) for x in names) else 0
            out[dates[0]] = max(out.get(dates[0], 0), n)
    return sorted(out.items())
