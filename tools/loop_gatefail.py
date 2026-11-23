"""LOOP-FAILED-PARK (F-024): read a red gate's pytest tail and tell whether
every failing test lies outside the lane's diff. Then a fix round cannot help
(the break is foreign to the lane), so the loop parks the item for a session
at round 0 instead of spending three fix rounds on it.

Pure: no file, git or process access. Stdlib only. The tail is the detail
tools/al_loop.py _gates returns for a red command: `<cmd> rc=<n>` and the
last 1500 / 500 chars of its stdout / stderr. Stricter reading wins: any
doubt (no FAILED / ERROR line, a truncated summary, a failing file in the
diff) answers "not foreign", and the normal fix rounds run.

LOOP-TRUNC: a pytest gate's detail also carries an ids block built from the
whole stdout (ids_block), which no tail cut can drop; it is read first. A red
pytest gate whose block lists no id is gate-unknown (gate_unknown) and is
parked, never sent into a fix round."""

import re

# pytest's short test summary: `FAILED <nodeid>[ - <reason>]` and
# `ERROR <nodeid or file>[ - <reason>]` (a collection error names a file)
_LINE_RX = re.compile(r"^(FAILED|ERROR) (\S+?)(?: - .*)?\s*$", re.M)
# the final counts line, with or without the `===` frame of a non -q run
_FAILED_N_RX = re.compile(r"\b(\d+) failed\b")
_ERROR_N_RX = re.compile(r"\b(\d+) errors?\b")
_SUMMARY_RX = re.compile(r"^[= ]*(?:\d+ \w+(?:, )?)+.* in [0-9.]+s\b.*$", re.M)


def _norm(path):
    p = str(path).replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def failing(detail):
    """[(kind, nodeid, file)] of the FAILED / ERROR summary lines, in order,
    each node id once."""
    out, seen = [], set()
    for kind, node in _LINE_RX.findall(detail or ""):
        node = _norm(node)
        if node in seen:
            continue
        seen.add(node)
        out.append((kind, node, node.split("::", 1)[0]))
    return out


def _complete(detail, rows):
    """True when the tail holds pytest's final counts line and every failed /
    errored test it counts has its own summary line (a 1500-char tail can cut
    the first lines of a long summary)."""
    summary = _SUMMARY_RX.findall(detail or "")
    if not summary:
        return False
    last = summary[-1]
    m_f, m_e = _FAILED_N_RX.search(last), _ERROR_N_RX.search(last)
    want_f = int(m_f.group(1)) if m_f else 0
    want_e = int(m_e.group(1)) if m_e else 0
    have_f = sum(1 for k, _, _ in rows if k == "FAILED")
    have_e = sum(1 for k, _, _ in rows if k == "ERROR")
    return (want_f or want_e) > 0 and have_f >= want_f and have_e >= want_e


# LOOP-TRUNC: the ids block. tools/al_loop.py gate_tail builds it from a
# pytest gate's WHOLE stdout (every phase's short test summary) before the
# tail is cut, so 9 to 15 long FAILED lines, or a later phase's output, can
# no longer push the ids out of the detail. The block sits ahead of the tail
# (the detail still ENDS with the count line) and the gate cache keeps it.
IDS_HEAD = "AL-GATE-IDS"
IDS_ROW = "AL-ID"
IDS_MAX = 50
_HEAD_RX = re.compile(r"^AL-GATE-IDS complete=([01]) failed=(\d+) errors=(\d+) "
                      r"listed=(\d+)\s*$", re.M)
_ROW_RX = re.compile(r"^AL-ID (FAILED|ERROR) (\S+)\s*$", re.M)
_SECTION_RX = re.compile(r"^=+ short test summary info =+\s*$", re.M)
_INFRA_RX = re.compile(r"SUITE-GATE:|TimeoutExpired|OSError|SubprocessError|"
                       r"fail closed|Traceback \(most recent call last\)")


def ids_block(stdout, cap=IDS_MAX):
    """The ids block of a pytest gate's full stdout: one head line, then one
    `AL-ID <kind> <nodeid>` line per failing test of every summary section.
    complete=1 only when every phase's count line is matched by its own
    summary lines and at most `cap` ids are listed. A red with no summary
    gives `complete=0 ... listed=0`: the loop parks it as gate-unknown."""
    text = stdout or ""
    starts = [m.end() for m in _SECTION_RX.finditer(text)]
    rows, seen, want_f, want_e = [], set(), 0, 0
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        section = text[start:end]
        m = _SUMMARY_RX.search(section)
        if m:
            m_f, m_e = _FAILED_N_RX.search(m.group(0)), _ERROR_N_RX.search(m.group(0))
            want_f += int(m_f.group(1)) if m_f else 0
            want_e += int(m_e.group(1)) if m_e else 0
            section = section[:m.start()]
        for kind, node, _ in failing(section):
            if node not in seen:
                seen.add(node)
                rows.append((kind, node))
    have_f = sum(1 for k, _ in rows if k == "FAILED")
    have_e = sum(1 for k, _ in rows if k == "ERROR")
    complete = ((want_f or want_e) > 0 and have_f >= want_f and have_e >= want_e
                and len(rows) <= cap)
    head = (f"{IDS_HEAD} complete={int(complete)} failed={want_f} errors={want_e} "
            f"listed={min(len(rows), cap)}")
    return "\n".join([head] + [f"{IDS_ROW} {k} {n}" for k, n in rows[:cap]])


def _block(detail):
    """(rows, complete) of the ids block in detail, or None without one."""
    m = _HEAD_RX.search(detail or "")
    if not m:
        return None
    rows, seen = [], set()
    for kind, node in _ROW_RX.findall(detail[m.end():]):
        node = _norm(node)
        if node not in seen:
            seen.add(node)
            rows.append((kind, node, node.split("::", 1)[0]))
    complete = m.group(1) == "1" and len(rows) == int(m.group(4))
    return rows, complete


def keep_ids(detail, limit):
    """detail cut for the gate cache: its first line (the `<cmd> rc=<n>`
    line), the ids block whole, then the last `limit` chars of the rest."""
    from loop_merge import last_lines  # noqa: PLC0415 (loop_merge imports this module)
    text = detail or ""
    lines = text.splitlines()
    block = [ln for ln in lines if _HEAD_RX.match(ln) or _ROW_RX.match(ln)]
    if not block:
        return last_lines(text, limit)
    first = [lines[0]] if lines[0] not in block else []
    rest = [ln for ln in lines[len(first):] if ln not in block]
    tail = last_lines("\n".join(rest), limit)
    return "\n".join(first + block + ([tail] if tail else []))


def foreign_only(detail, changed):
    """The failing test ids when every failing test file is outside the lane's
    diff (`changed`: repo-relative paths, any slash), else []. [] also when the
    tail names no failing test or is incomplete, so the fix rounds run. An ids
    block (LOOP-TRUNC) is read first: it cannot be cut off."""
    got = _block(detail)
    if got is not None:
        rows, complete = got
        if not rows or not complete:
            return []
    else:
        rows = failing(detail)
        if not rows or not _complete(detail, rows):
            return []
    diff = {_norm(n) for n in changed or ()}
    if any(f in diff for _, _, f in rows):
        return []
    return [node for _, node, _ in rows]


def gate_unknown(detail):
    """LOOP-TRUNC: True for a red pytest gate whose ids block lists no failing
    test (no summary could be parsed). A fix round has nothing to aim at, so
    the loop parks the item as gate-unknown. False without an ids block (npm,
    the leak sweep, an old cached verdict) and for an infrastructure red."""
    got = _block(detail)
    if got is None or _INFRA_RX.search(detail or ""):
        return False
    return not got[0]
