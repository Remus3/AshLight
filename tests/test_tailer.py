"""Tailer: start at end, append, partial line, truncation, replacement, missing,
UTF-8 replacement, libraryfolders discovery. All under tmp_path."""

import os

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
    p = tmp_path / "Client.txt"
    p.write_bytes(b"x" * 100 + b"\n")
    t, sink = _tail(p)
    t.poll_once()
    with open(p, "r+b") as fh:
        fh.truncate(0)
        fh.write(b"fresh\n")
    t.poll_once()
    assert any(s.get("reason") == "truncated" for s in sink.status)
    assert sink.lines == ["fresh"]
    t.stop()


def test_replacement_reopens(tmp_path):
    p = tmp_path / "Client.txt"
    p.write_bytes(b"one\n")
    t, sink = _tail(p)
    t.poll_once()
    new = tmp_path / "Client.new"
    new.write_bytes(b"line from the new file which is long enough\n")
    os.replace(new, p)
    t.poll_once()
    reasons = [s.get("reason") for s in sink.status if s["type"] == "tailer_reset"]
    assert reasons and reasons[0] in ("replaced", "truncated")
    assert sink.lines == ["line from the new file which is long enough"]
    t.stop()


def test_missing_then_back(tmp_path):
    p = tmp_path / "Client.txt"
    t, sink = _tail(p)
    t.poll_once()
    t.poll_once()
    missing = [s for s in sink.status if s.get("reason") == "missing"]
    assert len(missing) == 1  # reported once, not every poll
    p.write_bytes(b"born\n")
    t.poll_once()
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
