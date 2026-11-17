"""AREA-AUDIT batch 4: AUDIT-SETTLED-LIST (P2-D2) and AUDIT-BRIDGE-LOW
(P2-B3..B5), docs/audit/2026-11-17-audit.md Pass 2."""

import io
import queue
import re
import subprocess
from pathlib import Path

import pytest

from server.al.theorycraft import bridge

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "docs" / "decisions"


def _settled_entries():
    text = (ROOT / "CLAUDE.md").read_text(encoding="ascii")
    head = "## Settled - do not re-litigate"
    assert head in text
    body = text.split(head, 1)[1]
    nxt = re.search(r"^## ", body, re.M)
    body = body[:nxt.start()] if nxt else body
    return [e for e in re.split(r"^- ", body, flags=re.M)[1:]]


def _decisions():
    return sorted((m.group(1), p) for p in DECISIONS.glob("*.md")
                  if (m := re.match(r"(\d{4})-", p.name)))


def test_every_decision_is_in_settled():
    """P2-D2: each docs/decisions/NNNN-*.md has a Settled line with a
    'Reverses if' clause that names it."""
    entries = _settled_entries()
    missing = [n for n, _ in _decisions()
               if not any(f"decision {n}" in " ".join(e.split()) or
                          re.search(rf"\b{n}\b", e) for e in entries)]
    assert not missing, f"decisions missing from CLAUDE.md Settled: {missing}"
    for e in entries:
        assert "Reverses if" in " ".join(e.split()), e[:60]


def test_every_dated_amendment_is_in_settled():
    """A decision amended in place ('## Amendment <date>') has a Settled
    line naming both the decision and the amendment ("amend")."""
    entries = [" ".join(e.split()).lower() for e in _settled_entries()]
    for n, p in _decisions():
        if re.search(r"^## Amendment \d{4}-\d{2}-\d{2}", p.read_text(encoding="ascii"), re.M):
            assert any(n in e and "amend" in e for e in entries), n


def test_exepin_record_threat_model_is_stated():
    """P2-B3: the .sha256 beside luajit.exe guards against a stale or foreign
    exe, not a same-user tamper; decision 0022 says so."""
    text = " ".join((DECISIONS / "0022-tc-bridge.md").read_text(encoding="ascii").split())
    assert "P2-B3" in text
    assert "NOT tamper protection" in text


class _StuckProc:
    """Closed stdout but never exits (wait always times out)."""

    stdin = stdout = None

    def poll(self):
        return None

    def kill(self):
        pass

    def wait(self, timeout=None):
        raise subprocess.TimeoutExpired("luajit", timeout)


def test_eof_with_a_process_that_will_not_exit_is_a_bridge_error():
    """P2-B4: proc.wait(5) after EOF raised TimeoutExpired, which escaped as a
    non-BridgeError."""
    b = bridge.Bridge(["unused"])
    b._proc = _StuckProc()
    b._lines = queue.Queue()
    b._lines.put(bridge._EOF)
    with pytest.raises(bridge.BridgeError):
        b._read(1, 2.0)
    assert b._proc is None


class _Proc:
    def __init__(self, data):
        self.stdout = io.BufferedReader(io.BytesIO(data))


def test_reader_drops_overlong_lines_and_keeps_the_next_frame():
    """P2-B5: the reader read unbounded stdout lines from PoB."""
    big = b"x" * (bridge.MAX_LINE_BYTES * 3) + b"\n"
    huge_frame = b"ALB1 " + b"{\"id\":9,\"pad\":\"" + b"y" * bridge.MAX_LINE_BYTES + b"\"}\n"
    ok = b'ALB1 {"id":1,"ok":true}\n'
    lines = queue.Queue()
    bridge.Bridge._reader(_Proc(big + huge_frame + ok), lines)
    got = []
    while not lines.empty():
        got.append(lines.get_nowait())
    assert got[-1] is bridge._EOF
    assert got[:-1] == [{"id": 1, "ok": True}]


def test_reader_keeps_a_line_at_the_limit():
    body = b'ALB1 {"id":2,"ok":true}'
    pad = b" " * (bridge.MAX_LINE_BYTES - len(body))
    lines = queue.Queue()
    bridge.Bridge._reader(_Proc(body + pad + b"\n"), lines)
    assert lines.get_nowait() == {"id": 2, "ok": True}
