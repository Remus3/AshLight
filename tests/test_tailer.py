"""Tailer: start at end, append, partial line, truncation, replacement, missing,
UTF-8 replacement, libraryfolders discovery. All under tmp_path.

RUN-TAIL-HEAL-READER (research 0050 R1): the chaos tests C1 and C3 to C6
- a listener error, a file renamed away and back, an old file that shows
up late, a trim in place and a locked file - never stop the reader and
never replay a backlog."""

import os
import time
from pathlib import Path

import pytest

from server.al import logfile


class Sink:
    def __init__(self):
        self.lines = []
        self.status = []

    def line(self, s):
        self.lines.append(s)

    def stat(self, ev):
        self.status.append(ev)


def _tail(path, **kw):
    sink = Sink()
    t = logfile.Tailer(path, sink.line, sink.stat, **kw)
    return t, sink


def _append(path, data):
    with open(path, "ab") as fh:
        fh.write(data)


def _log(n, start=0):
    """n realistic Client.txt lines (about 95 bytes each, so 1,000 of them
    are past the 64 KB new-file limit)."""
    return b"".join(
        b"2026/11/18 19:%02d:%02d 123456789 abcdef01 [INFO Client 4242] : "
        b"line %06d of the old session\n" % ((i // 60) % 60, i % 60, i)
        for i in range(start, start + n))


def _wait(cond, timeout=3.0):
    deadline = time.monotonic() + timeout
    while not cond() and time.monotonic() < deadline:
        time.sleep(0.01)
    return cond()


def _resets(sink):
    return [s.get("reason") for s in sink.status if s["type"] == "tailer_reset"]


def test_starts_at_end_never_replays(tmp_path):
    p = tmp_path / "Client.txt"
    p.write_bytes(b"old 1\nold 2\n")
    t, sink = _tail(p)
    assert t.poll_once() == 0
    assert sink.lines == []
    assert sink.status[0]["type"] == "tailer_started"
    assert sink.status[0]["offset"] == len(b"old 1\nold 2\n")
    _append(p, b"new 1\n")
    assert t.poll_once() == 1
    assert sink.lines == ["new 1"]
    t.stop()


def test_start_at_beginning_when_asked(tmp_path):
    p = tmp_path / "Client.txt"
    p.write_bytes(b"\xef\xbb\xbfa\r\nb\n")
    t, sink = _tail(p, start_at_end=False)
    t.poll_once()
    assert sink.lines == ["a", "b"]
    t.stop()


def test_partial_line_held_back(tmp_path):
    p = tmp_path / "Client.txt"
    p.write_bytes(b"")
    t, sink = _tail(p)
    t.poll_once()
    _append(p, b"half a li")
    assert t.poll_once() == 0
    _append(p, b"ne\nnext")
    assert t.poll_once() == 1
    assert sink.lines == ["half a line"]
    _append(p, b"\r\n")
    t.poll_once()
    assert sink.lines == ["half a line", "next"]
    t.stop()


def test_truncation_resets(tmp_path):
    """Cleared in place and rewritten with new text of at most 64 KB: read
    from its first line, no resume scan (RUN-TAIL-HEAL-READER). A log seen
    empty after the clear is read in full as it grows."""
    p = tmp_path / "Client.txt"
    p.write_bytes(b"x" * 100 + b"\n")
    asked = []
    t, sink = _tail(p, on_resume=lambda path, end: asked.append(end))
    t.poll_once()
    asked.clear()
    with open(p, "r+b") as fh:
        fh.truncate(0)
        fh.write(b"fresh\n")
    t.poll_once()
    assert _resets(sink) == ["truncated"]
    assert sink.status[-1]["read"] == "start"
    assert sink.lines == ["fresh"]
    assert asked == []
    with open(p, "r+b") as fh:
        fh.truncate(0)
    t.poll_once()
    assert _resets(sink) == ["truncated", "truncated"]
    big = _log(1000, start=5000)
    _append(p, big)
    t.poll_once()
    assert sink.lines == ["fresh"] + [x.decode() for x in big.splitlines()]
    assert asked == []
    t.stop()


def test_truncation_to_new_big_text_jumps_to_the_end(tmp_path):
    """Cut in place below the read offset and refilled with more than 64 KB
    of text the reader never saw: skipped to its end, resume scan asked."""
    p = tmp_path / "Client.txt"
    p.write_bytes(_log(2000))
    asked = []
    t, sink = _tail(p, on_resume=lambda path, end: asked.append(end))
    t.poll_once()
    asked.clear()
    big = _log(1000, start=9000)
    with open(p, "r+b") as fh:
        fh.truncate(0)
        fh.write(big)
    assert t.poll_once() == 0
    assert sink.lines == []
    assert _resets(sink) == ["truncated"]
    assert sink.status[-1]["read"] == "end"
    assert asked == [len(big)]
    t.stop()


def test_replacement_reopens(tmp_path):
    """Replaced by another file: one of at most 64 KB is read from its first
    line; one past 64 KB is skipped to its end and handed to the resume
    scan."""
    p = tmp_path / "Client.txt"
    p.write_bytes(b"one\n")
    asked = []
    t, sink = _tail(p, on_resume=lambda path, end: asked.append(end))
    t.poll_once()
    asked.clear()
    new = tmp_path / "Client.new"
    new.write_bytes(b"line from the new file which is long enough\n")
    os.replace(new, p)
    t.poll_once()
    assert _resets(sink) == ["replaced"]
    assert sink.lines == ["line from the new file which is long enough"]
    assert asked == []
    big = _log(1000)
    new.write_bytes(big)
    os.replace(new, p)
    assert t.poll_once() == 0
    assert _resets(sink) == ["replaced", "replaced"]
    assert asked == [len(big)]
    started = [s for s in sink.status if s["type"] == "tailer_started"]
    assert started[-1]["offset"] == len(big)
    assert sink.lines == ["line from the new file which is long enough"]
    t.stop()


def test_missing_then_back(tmp_path):
    """Missing, then a file shows up: at most 64 KB is read from its first
    line; a bigger one (C4 covers it) starts at its end."""
    p = tmp_path / "Client.txt"
    t, sink = _tail(p)
    t.poll_once()
    t.poll_once()
    missing = [s for s in sink.status if s.get("reason") == "missing"]
    assert len(missing) == 1  # reported once, not every poll
    p.write_bytes(b"born\n")
    t.poll_once()
    assert sink.lines == ["born"]
    new = tmp_path / "Client.new"
    new.write_bytes(_log(1000, start=7000))  # made first: another file id
    p.unlink()
    t.poll_once()
    assert _resets(sink) == ["missing", "missing"]
    os.replace(new, p)
    assert t.poll_once() == 0
    assert sink.lines == ["born"]
    t.stop()


def test_invalid_utf8_replaced(tmp_path):
    p = tmp_path / "Client.txt"
    p.write_bytes(b"")
    t, sink = _tail(p)
    t.poll_once()
    _append(p, b"bad \xff byte\n" + "ok \u00e9\n".encode("utf-8"))
    t.poll_once()
    assert sink.lines[0] == "bad \ufffd byte"
    assert sink.lines[1] == "ok \u00e9"
    t.stop()


def test_thread_picks_up_appends(tmp_path):
    p = tmp_path / "Client.txt"
    p.write_bytes(b"")
    t, sink = _tail(p, poll_s=0.02)
    t.start()
    import time
    deadline = time.monotonic() + 3
    while not sink.status and time.monotonic() < deadline:
        time.sleep(0.01)
    _append(p, b"live\n")
    while not sink.lines and time.monotonic() < deadline:
        time.sleep(0.01)
    t.stop()
    assert sink.lines == ["live"]
    assert not t.running


def test_libraryfolders_discovery(tmp_path):
    steam = tmp_path / "Steam"
    lib2 = tmp_path / "Lib2"
    (steam / "steamapps").mkdir(parents=True)
    vdf = ('"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"%s"\n\t}\n'
           '\t"1"\n\t{\n\t\t"path"\t\t"%s"\n\t}\n}\n') % (
        str(steam).replace("\\", "\\\\"), str(lib2).replace("\\", "\\\\"))
    (steam / "steamapps" / "libraryfolders.vdf").write_text(vdf, encoding="utf-8")
    log = lib2 / logfile.LOG_REL
    log.parent.mkdir(parents=True)
    log.write_bytes(b"")
    assert logfile.steam_libraries([steam]) == [steam, lib2]
    assert logfile.discover_client_log(None, steam_roots=[steam]) == log
    assert logfile.discover_client_log(str(log), steam_roots=[]) == log
    assert logfile.discover_client_log(None, steam_roots=[tmp_path / "none"]) is None
    # UX-FIRSTRUN: a Steam root spelled in another case (the registry keeps
    # it lower case) still gives the file's real spelling on the consent card.
    if os.name == "nt":
        lower = Path(str(steam).lower())
        found = logfile.discover_client_log(None, steam_roots=[lower])
        assert str(found) == str(log.resolve())


# ---------------------------------------------------------------- chaos (R1)

def test_listener_error_keeps_thread_alive(tmp_path):
    """C1: a listener raises on one line -> thread alive, next line
    delivered."""
    p = tmp_path / "Client.txt"
    p.write_bytes(b"")
    got = []

    def on_line(line):
        if line == "boom":
            raise ValueError("listener bug")
        got.append(line)

    t = logfile.Tailer(p, on_line, poll_s=0.02)
    t.start()
    try:
        assert _wait(lambda: t._ident is not None)
        _append(p, b"boom\nafter boom\n")
        assert _wait(lambda: got == ["after boom"])
        _append(p, b"later\n")
        assert _wait(lambda: got == ["after boom", "later"])
        assert t.running
        assert t.listener_errors == 1
    finally:
        t.stop()


def test_renamed_away_and_back_reemits_nothing(tmp_path):
    """C3: a 1,000-line file renamed away and back -> 0 lines re-emitted;
    the reader continues from its old offset."""
    p = tmp_path / "Client.txt"
    p.write_bytes(_log(1000))
    t, sink = _tail(p)
    t.poll_once()
    away = tmp_path / "Client.away"
    os.replace(p, away)
    t.poll_once()
    assert _resets(sink) == ["missing"]
    os.replace(away, p)
    assert t.poll_once() == 0
    assert sink.lines == []
    assert _resets(sink) == ["missing", "continued"]
    _append(p, b"fresh after the move\n")
    assert t.poll_once() == 1
    assert sink.lines == ["fresh after the move"]
    t.stop()


def test_late_old_file_emits_nothing_and_asks_resume(tmp_path):
    """C4: the path is missing, then an old 1,000-line file appears (a late
    drive, a logon start) -> 0 lines, the reader starts at its end and asks
    for the resume scan (decision 0008: scan only)."""
    p = tmp_path / "Client.txt"
    asked = []
    t, sink = _tail(p, on_resume=lambda path, end: asked.append((Path(path), end)))
    t.poll_once()
    old = tmp_path / "Client.old"
    old.write_bytes(_log(1000))
    os.replace(old, p)
    size = p.stat().st_size
    assert size > logfile.NEW_FILE_MAX
    assert t.poll_once() == 0
    assert sink.lines == []
    assert asked == [(p, size)]
    started = [s for s in sink.status if s["type"] == "tailer_started"]
    assert started and started[-1]["offset"] == size
    _append(p, b"live line\n")
    t.poll_once()
    assert sink.lines == ["live line"]
    t.stop()


def test_trim_in_place_replays_nothing(tmp_path):
    """C5: the file is trimmed in place to its newest half -> no line is
    replayed, whether the kept half is under the 64 KB new-file limit (the
    reader finds where it was) or over it (it jumps to the end and asks for
    the resume scan); later lines still arrive."""
    for n in (1000, 4000):
        p = tmp_path / ("Client%d.txt" % n)
        p.write_bytes(_log(n))
        asked = []
        t, sink = _tail(p, on_resume=lambda path, end: asked.append(end))
        t.poll_once()
        asked.clear()
        with open(p, "r+b") as fh:
            data = fh.read()
            half = data[data.index(b"\n", len(data) // 2) + 1:]
            fh.seek(0)
            fh.write(half)
            fh.truncate()
        assert t.poll_once() == 0
        assert sink.lines == []
        assert _resets(sink) == ["truncated"]
        if len(half) > logfile.NEW_FILE_MAX:
            assert asked == [len(half)]
        else:
            assert asked == []
        _append(p, b"after the trim\n")
        assert t.poll_once() == 1
        assert sink.lines == ["after the trim"]
        t.stop()


def _lock_exclusive(path):
    """Open path with share mode 0 (no one else may open it)."""
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                wintypes.HANDLE]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    h = k32.CreateFileW(str(path), 0x80000000, 0, None, 3, 0x80, None)
    assert h and h != wintypes.HANDLE(-1).value
    return lambda: k32.CloseHandle(h)


@pytest.mark.skipif(os.name != "nt", reason="share modes are Windows only")
def test_locked_file_reports_unreadable_then_clears(tmp_path):
    """C6: the file is held with share mode 0 -> "unreadable" after 20
    failed polls (5 s at the default poll), once; cleared on the first good
    poll, and the waiting line is then delivered."""
    assert logfile.UNREADABLE_POLLS * logfile.DEFAULT_POLL_S <= 5.0
    p = tmp_path / "Client.txt"
    p.write_bytes(b"old\n")
    t, sink = _tail(p)
    t.poll_once()
    _append(p, b"waiting line\n")
    unlock = _lock_exclusive(p)
    try:
        for _ in range(logfile.UNREADABLE_POLLS - 1):
            assert t.poll_once() == 0
        assert not [s for s in sink.status if s["type"] == "tailer_unreadable"]
        t.poll_once()
        t.poll_once()
        bad = [s for s in sink.status if s["type"] == "tailer_unreadable"]
        assert len(bad) == 1
        assert t.failed_polls == logfile.UNREADABLE_POLLS + 1
    finally:
        unlock()
    assert t.poll_once() == 1
    assert sink.lines == ["waiting line"]
    assert sink.status[-1]["type"] == "tailer_readable"
    t.poll_once()
    assert [s["type"] for s in sink.status].count("tailer_readable") == 1
    t.stop()


def test_new_small_log_is_read_from_its_first_line(tmp_path):
    """The risk R1 names: a log recreated by a game restart (a new file of
    at most 64 KB) is still read from its first line."""
    p = tmp_path / "Client.txt"
    p.write_bytes(_log(1000))
    t, sink = _tail(p)
    t.poll_once()
    new = tmp_path / "Client.new"
    new.write_bytes(b"first line of the new game\nsecond line\n")
    os.replace(new, p)
    t.poll_once()
    assert sink.lines == ["first line of the new game", "second line"]
    t.stop()
