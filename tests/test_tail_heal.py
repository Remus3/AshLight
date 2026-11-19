"""RUN-TAIL-HEAL-CORE (research 0050 R1; F10, F11, F13): the core restarts
a dead log reader, the Reading row and the state's reading flag tell the
truth (dead thread, unreadable file), and a big backlog that shows up
after a break is skipped to its end and counted by the resume scan, never
replayed as live lines. The X1 experiments of research 0050 as
regression tests on synthetic fixture logs (tools/synth_client.py); no
live Client.txt is read and no port is bound."""

import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import synth_client  # noqa: E402
from ci_timing import ci_scale  # noqa: E402
from server.al import core as core_mod  # noqa: E402
from server.al import diag, logfile, resume  # noqa: E402
from server.al.core import Core  # noqa: E402
from server.al.state import SessionState, summarize  # noqa: E402

WAIT_S = ci_scale(8.0)  # decision 0080: 3x under AL_CI=1
BACKLOG = 24 * 1024 * 1024


def make_core(tmp_path, log):
    rt = tmp_path / "rt"
    rt.mkdir()
    (rt / "consent.json").write_text('{"consented": true}\n', encoding="ascii")
    return Core(runtime=rt, log_path=str(log), poll_s=0.02)


def wait_for(pred, what):
    end = time.monotonic() + WAIT_S
    while time.monotonic() < end:
        if pred():
            return
        time.sleep(0.02)
    pytest.fail(f"timed out waiting for {what}")


def append(path, data):
    with open(path, "ab") as fh:
        fh.write(data)


def reading_row(core):
    return {r["id"]: r for r in diag.checks(core.diag_facts(), time.time())}["reading"]


def texts(core):
    return [r["text"] for r in core.state.snapshot()["recent_events"]]


def death_line(name="Healer"):
    s = synth_client.Session(seed=31, character=name, klass="Monk")
    s.death()
    return s.text().encode()


def test_dead_reader_is_restarted_within_5_s_and_row_is_not_pass(tmp_path):
    """C2: the reader thread dies -> restarted within 5 s; the Reading row
    is not PASS between; the line written while it was dead is read once."""
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = make_core(tmp_path, log)
    try:
        assert core.start_tailing()
        wait_for(lambda: core.state.snapshot()["tailer"]["reading"], "reading")
        assert reading_row(core)["status"] == "pass"
        t = core.tailer
        t._stop.set()  # the thread ends as if a bug had killed it
        t._thread.join(2.0)
        assert not t.running and not core.reader_alive()
        append(log, death_line())
        row = reading_row(core)
        assert row["status"] != "pass" and row["fix"]
        t0 = time.monotonic()
        while not core.reader_alive():
            core.ensure_tailing()
            assert time.monotonic() - t0 < 5.0
            time.sleep(0.01)
        assert time.monotonic() - t0 < 5.0
        assert core.tailer is t and core.tailer_restarts == 1
        wait_for(lambda: core.state.snapshot()["deaths"] == 1, "the death line")
        assert texts(core).count("AshLight restarted its log reader") == 1
        assert reading_row(core)["status"] == "pass"
        time.sleep(0.1)
        assert core.state.snapshot()["deaths"] == 1  # nothing read twice
    finally:
        core.close()


def test_restart_backs_off_while_the_reader_keeps_dying(tmp_path):
    """A reader that dies again is restarted at most once per
    RESTART_MIN_S, not on every loop tick."""
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = make_core(tmp_path, log)
    try:
        assert core.start_tailing()
        t = core.tailer

        def kill():
            t._stop.set()
            t._thread.join(2.0)
            assert not t.running

        kill()
        assert core.ensure_tailing(now=1000.0) is True and t.running
        kill()
        assert core.ensure_tailing(now=1001.0) is False and not t.running
        assert reading_row(core)["status"] != "pass"
        assert core.ensure_tailing(now=1000.0 + core_mod.RESTART_MIN_S) is True
        assert t.running and core.tailer_restarts == 2
        # consent withdrawn: the reader is stopped and never restarted
        core.record_consent(False)
        assert core.tailer is None and not t.running
        assert core.ensure_tailing(now=5000.0) is False and core.tailer is None
    finally:
        core.close()


def test_listener_error_keeps_the_reader_alive(tmp_path):
    """X1 (F10): one listener exception left the thread dead, the row PASS
    and no later line read. Now the thread lives and the next line counts."""
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = make_core(tmp_path, log)
    boom = []

    def bad(ev):
        if ev.get("type") == "death" and not boom:
            boom.append(1)
            raise RuntimeError("a listener bug")

    core.bus.add_listener(bad)
    try:
        assert core.start_tailing()
        wait_for(lambda: core.state.snapshot()["tailer"]["reading"], "reading")
        append(log, death_line())
        wait_for(lambda: boom, "the failing listener")
        append(log, death_line())
        wait_for(lambda: core.state.snapshot()["deaths"] == 2, "the next line")
        assert core.reader_alive() and core.tailer.listener_errors == 1
        assert reading_row(core)["status"] == "pass"
    finally:
        core.close()


def test_unreadable_state_shows_and_clears(tmp_path, monkeypatch):
    """C6 at the core (F13): every open fails -> the state says unreadable,
    reading is off, the Reading row is a fix row with its own words; the
    first good read clears it and the waiting line is counted once."""
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = make_core(tmp_path, log)
    real = logfile._open_shared
    try:
        assert core.start_tailing()
        wait_for(lambda: core.state.snapshot()["tailer"]["reading"], "reading")

        def locked(path):
            raise PermissionError(13, "held by another program")

        monkeypatch.setattr(logfile, "_open_shared", locked)
        append(log, death_line())
        wait_for(lambda: core.state.snapshot()["tailer"]["unreadable"], "unreadable")
        tl = core.state.snapshot()["tailer"]
        assert tl["reading"] is False
        facts = core.diag_facts()
        assert facts["unreadable"] is True and facts["reading"] is False
        row = reading_row(core)
        assert row["status"] == "fail" and row["detail"] == diag.UNREADABLE_DETAIL
        assert row["fix"] == diag.FIX_UNREADABLE
        assert "Client.txt can't be read right now - trying again" in texts(core)
        assert core.state.snapshot()["deaths"] == 0
        monkeypatch.setattr(logfile, "_open_shared", real)
        wait_for(lambda: not core.state.snapshot()["tailer"]["unreadable"], "readable")
        wait_for(lambda: core.state.snapshot()["deaths"] == 1, "the waiting line")
        tl = core.state.snapshot()["tailer"]
        assert tl["reading"] is True
        assert texts(core).count("Client.txt can't be read right now - trying again") == 1
        assert texts(core).count("Client.txt can be read again") == 1
        assert reading_row(core)["status"] == "pass"
    finally:
        monkeypatch.setattr(logfile, "_open_shared", real)
        core.close()


def _backlog_bytes(size):
    """Old game runs (many deaths, trade requests and whispers) padded to
    `size`, then a game start and the current run: 2 deaths, level 3."""
    old = synth_client.Session(seed=21, character="Backlog", klass="Witch",
                               start=(2026, 11, 15, 10, 0, 0))
    old.marker()
    old.zone_change("G1_1", 1, "The Riverbank")
    for i in range(40):
        old.death()
        old.trade_whisper(f"Buyer{i}", "Grim Bane Ruby Ring", 5, "exalted")
        old.whisper("Friend", "hello")
    block = old.text().encode()
    cur = synth_client.Session(seed=22, character="Backlog", klass="Witch",
                               start=(2026, 11, 16, 21, 0, 0))
    cur.marker()
    cur.zone_change("G1_town", 15, "Clearfell Encampment")
    cur.level_up()
    cur.level_up()
    cur.death()
    cur.death()
    tail = cur.text().encode()
    reps = max(1, (size - len(tail)) // len(block) + 1)
    return block * reps + tail, old.deaths * reps, cur


@pytest.mark.parametrize("how", ["late", "replaced"])
def test_24mb_backlog_adds_no_deaths_or_trade_cards(tmp_path, monkeypatch, how):
    """X1 (F11): a 24 MB log that showed up late (or replaced the file)
    was replayed in full: 3,200 deaths and 5 open trade cards. Now the
    reader jumps to its end and the resume scan runs again: the counts are
    the current run's, no old line becomes a live event."""
    log = tmp_path / "Client.txt"
    scans = []
    real_scan = resume.scan

    def counting(path, **kw):
        scans.append(kw.get("end"))
        return real_scan(path, **kw)

    monkeypatch.setattr(resume, "scan", counting)
    if how == "replaced":
        first = synth_client.Session(seed=23, character="Backlog", klass="Witch")
        first.marker()
        first.level_up()
        log.write_bytes(first.text().encode())
    core = make_core(tmp_path, log)
    try:
        assert core.start_tailing()
        if how == "late":
            wait_for(lambda: core.tailer._missing, "the missing file")
            assert scans == []
        else:
            wait_for(lambda: core.state.snapshot()["level"] == 2, "the first resume")
            assert len(scans) == 1
        data, old_deaths, cur = _backlog_bytes(BACKLOG)
        assert len(data) >= BACKLOG and old_deaths > 3000
        tmp = tmp_path / "Client.new"
        tmp.write_bytes(data)
        os.replace(tmp, log)  # whole at once, as a drive coming back shows it
        wait_for(lambda: core.tailer._offset == len(data) and scans
                 and scans[-1] == len(data), "the jump to the end")
        wait_for(lambda: core.state.snapshot()["deaths"] == cur.deaths, "the resumed counts")
        snap = core.state.snapshot()
        assert len(scans) == (1 if how == "late" else 2)
        assert snap["deaths"] == 2 and snap["level"] == 3
        assert snap["trade_requests"] == []
        assert not any(r["whisper"] or r["type"] == "death" for r in snap["recent_events"])
        assert core.tailer.lines == 0
        assert snap["tailer"]["reading"] is True
        # a live line after the jump is read as usual
        append(log, death_line("Backlog"))
        wait_for(lambda: core.state.snapshot()["deaths"] == 3, "a live death")
    finally:
        core.close()


def test_resume_scan_failure_is_logged(tmp_path, monkeypatch, caplog):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path, tail=False)
    try:
        monkeypatch.setattr(resume, "scan", lambda *a, **kw: None)
        with caplog.at_level("WARNING", logger="al.core"):
            core._resume(log, 0)
        assert any("resume scan could not read" in r.getMessage() for r in caplog.records)
    finally:
        core.close()


# -- event text and the reading flag (design 0001 section 9)

@pytest.mark.parametrize("ev,want", [
    ({"type": "tailer_reset", "reason": "continued", "offset": 9},
     "Client.txt is back - reading on from where it stopped"),
    ({"type": "tailer_unreadable", "error": "PermissionError 13"},
     "Client.txt can't be read right now - trying again"),
    ({"type": "tailer_readable"}, "Client.txt can be read again"),
    ({"type": "tailer_restarted", "restarts": 1}, "AshLight restarted its log reader"),
    ({"type": "tailer_reset", "reason": "truncated", "read": "start"},
     "Client.txt was cleared - reading from the start"),
    ({"type": "tailer_reset", "reason": "truncated", "read": "kept"},
     "Client.txt got shorter - reading on from where it stopped"),
    ({"type": "tailer_reset", "reason": "truncated", "read": "end"},
     "Client.txt got shorter - reading new lines only"),
    ({"type": "tailer_reset", "reason": "replaced", "read": "start"},
     "Client.txt was replaced - reading the new file"),
    ({"type": "tailer_reset", "reason": "replaced", "read": "kept"},
     "Client.txt was replaced - reading on from where it stopped"),
    ({"type": "tailer_reset", "reason": "replaced", "read": "end"},
     "Client.txt was replaced - reading new lines only"),
])
def test_tailer_event_text(ev, want):
    assert summarize(ev) == want
    want.encode("ascii")


def test_reading_from_the_start_only_when_it_is_true():
    """Session-7 finding: the truncated sentence said "reading from the
    start" for every reset; the reader reads byte 0 only on read=start."""
    for reason in ("missing", "replaced", "truncated", "continued", "odd"):
        for read in ("kept", "end"):
            text = summarize({"type": "tailer_reset", "reason": reason, "read": read})
            assert "from the start" not in text, (reason, read, text)


def _st():
    st = SessionState()
    st.set_tailer(consented=True)
    return st


def ev(t, **kw):
    return dict(kw, type=t, source="tailer")


def test_reading_flag_follows_the_status_events():
    st = _st()
    st.apply(ev("tailer_started", path="x"))
    assert st.snapshot()["tailer"]["reading"] is True
    st.apply(ev("tailer_reset", reason="missing"))
    assert st.snapshot()["tailer"]["reading"] is False
    # the same file back: no tailer_started follows, reading is on again
    st.apply(ev("tailer_reset", reason="continued", offset=10))
    tl = st.snapshot()["tailer"]
    assert tl["reading"] is True and tl["last_reset"] == "continued"
    st.apply(ev("tailer_unreadable", error="PermissionError 13"))
    tl = st.snapshot()["tailer"]
    assert tl["reading"] is False and tl["unreadable"] is True
    st.apply(ev("tailer_readable"))
    tl = st.snapshot()["tailer"]
    assert tl["reading"] is True and tl["unreadable"] is False
    # unreadable, then missing: the clear on the next good poll keeps
    # reading off until the file is back
    st.apply(ev("tailer_unreadable"))
    st.apply(ev("tailer_reset", reason="missing"))
    st.apply(ev("tailer_readable"))
    assert st.snapshot()["tailer"]["reading"] is False
    st.apply(ev("tailer_started", path="x"))
    assert st.snapshot()["tailer"]["reading"] is True
    # a start while still unreadable leaves reading off until readable
    st.apply(ev("tailer_unreadable"))
    st.apply(ev("tailer_started", path="x"))
    assert st.snapshot()["tailer"]["reading"] is False
    st.apply(ev("tailer_readable"))
    st.apply(ev("tailer_restarted", restarts=1))
    assert st.snapshot()["tailer"]["reading"] is True
    rows = [r["type"] for r in st.snapshot()["recent_events"]]
    for t in ("tailer_unreadable", "tailer_readable", "tailer_restarted"):
        assert t in rows
    # status events are not log lines (AREA-AUDIT P3-1)
    assert st.snapshot()["tailer"]["last_line_at"] is None
