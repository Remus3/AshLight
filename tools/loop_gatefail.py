"""LOOP-FAILED-PARK (F-024): read a red gate's pytest tail and tell whether
every failing test lies outside the lane's diff. Then a fix round cannot help
(the break is foreign to the lane), so the loop parks the item for a session
at round 0 instead of spending three fix rounds on it.

Pure: no file, git or process access. Stdlib only. The tail is the detail
tools/al_loop.py _gates returns for a red command: `<cmd> rc=<n>` and the
last 1500 / 500 chars of its stdout / stderr. Stricter reading wins: any
doubt (no FAILED / ERROR line, a truncated summary, a failing file in the
diff) answers "not foreign", and the normal fix rounds run."""

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


def foreign_only(detail, changed):
    """The failing test ids when every failing test file is outside the lane's
    diff (`changed`: repo-relative paths, any slash), else []. [] also when the
    tail names no failing test or is incomplete, so the fix rounds run."""
    rows = failing(detail)
    if not rows or not _complete(detail, rows):
        return []
    diff = {_norm(n) for n in changed or ()}
    if any(f in diff for _, _, f in rows):
        return []
    return [node for _, node, _ in rows]
