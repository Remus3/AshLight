"""RUN-QUIET-FEED (findings F-093, F-109; acceptance B4): the feed is
silent while nothing happens.

The Checks view in the snapshot holds no minute stamp and no report text
(the report is built on the click by GET /api/report), and its age rows
carry an absolute time ("at") next to a detail with the AGO mark instead
of an "N min ago" text, so an idle minute changes no state version.
web/checks.js writes the ages in, stepped at 5 minutes
(app/test/checks.test.js). Checks facts come from one light state
accessor (SessionState.checks_facts), never a whole snapshot.

No socket, process or network call: the core runs with tail=False, the
price refresh is stubbed, runtime state lives in tmp_path and the wall
clock is a test clock.
"""

import json
import time

import pytest

from server.al import diag
from server.al.core import Core
from server.al.state import SessionState

T0 = 1_795_200_000.0


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def idle_core(tmp_path, monkeypatch):
    """A core with web data on, a contact, consent given, the last log line
    5 minutes old and a price book checked 10 minutes ago; the wall clock
    is `clock` (time.time), moved by the test."""
    clock = Clock(T0)
    monkeypatch.setattr(time, "time", clock)
    cfg = tmp_path / "local.json"
    cfg.write_text(json.dumps({"web_data": True, "contact": "quiet-feed-test-contact"}),
                   encoding="ascii")
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False, config_path=cfg)
    core.rates.refresh_async = lambda *a, **k: False  # no request, ever
    core.state.set_tailer(consented=True, reading=False, idle=False,
                          last_line_at=T0 - 300)
    core.state.set_sources(book_checked_at=T0 - 600)
    try:
        yield core, clock
    finally:
        core.close()


def _idle_minutes(core, clock, minutes, step_s=30.0):
    """Run the core loop as __main__ does over `minutes` of wall time,
    with the Checks tick due on every pass; the versions seen."""
    seen = []
    for _ in range(int(minutes * 60 / step_s)):
        clock.t += step_s
        core._next_diag = 0.0  # the 5 s throttle is monotonic: due now
        core.tick_all()
        seen.append(core.state.version)
    return seen


def test_five_idle_minutes_change_no_state_version(idle_core):
    core, clock = idle_core
    core.tick_all()
    core._next_diag = 0.0
    core.tick_diag()
    before = core.state.version
    diag_before = core.state.snapshot()["diag"]
    seen = _idle_minutes(core, clock, 5)
    assert set(seen) == {before}, seen
    assert core.state.snapshot()["diag"] == diag_before


def test_three_idle_minutes_with_web_data_on_and_old_last_line(idle_core):
    core, clock = idle_core
    core.tick_diag(force=True)
    rows = {r["id"]: r for r in core.state.snapshot()["diag"]["checks"]}
    assert rows["web_data"]["status"] == "pass"
    assert rows["last_line"]["status"] == "pass"
    assert rows["last_line"]["at"] == T0 - 300
    assert rows["last_line"]["detail"] == diag.AGO + "."
    assert rows["prices"]["at"] == T0 - 600
    assert rows["prices"]["detail"] == "Updated " + diag.AGO + "."
    before = core.state.version
    for _ in range(18):  # 3 minutes, a Checks pass every 10 s
        clock.t += 10.0
        assert core.tick_diag(force=True) is False
    assert core.state.version == before
    # a real change still publishes: a new log line moves the age row
    core.state.set_tailer(last_line_at=clock.t)
    assert core.tick_diag(force=True) is True


def test_snapshot_holds_no_report_text(idle_core):
    core, clock = idle_core
    core.tick_diag(force=True)
    d = core.state.snapshot()["diag"]
    assert set(d) == {"checks", "failed", "summary"}
    blob = json.dumps(d)
    assert "self-check" not in blob and "UTC" not in blob
    assert " min ago" not in blob and "just now" not in blob
    # the report, built on the click, still writes the ages in at its now
    from server.al.plug import report
    text = report.build(core, now=clock.t)
    assert "[ok] Last log line: 5 min ago." in text
    assert "[ok] Price book: Updated 10 min ago." in text
    assert diag.AGO not in text


def test_render_detail():
    row = {"detail": diag.AGO + ". The game may be closed.", "at": 100.0}
    assert diag.render_detail(row, 100.0 + 3600) == "60 min ago. The game may be closed."
    assert diag.render_detail({"detail": "Fetched " + diag.AGO + ".", "at": 0.0},
                              3 * 86400) == "Fetched 3 days ago."
    # no "at": the detail as it is
    assert diag.render_detail({"detail": "Present."}, 5.0) == "Present."
    # an exit record's own words never carry the age mark
    rec = {"at": 50.0, "reason": "crash", "detail": "KeyError: " + diag.AGO}
    r = diag.check_last_exit({"started_at": 60.0, "last_exit": rec}, 70.0)[0]
    assert r["detail"].count(diag.AGO) == 1 and r["at"] == 50.0


def test_checks_facts_reads_no_snapshot(tmp_path, monkeypatch):
    core = Core(runtime=tmp_path, tail=False, character="Quietwisp")
    try:
        def boom(*a, **k):
            raise AssertionError("diag_facts built a snapshot")
        monkeypatch.setattr(core.state, "snapshot", boom)
        f = core.diag_facts()
        assert f["character_seen"] is True and f["_character"] == "Quietwisp"
        assert f["snapshot"] is False and f["lang"] == core.state.lang.verdict()
        core.tick_diag(force=True)
    finally:
        monkeypatch.undo()
        core.close()


def test_checks_facts_shape():
    s = SessionState()
    s.set_sources(book_checked_at=12.0)
    f = s.checks_facts()
    assert set(f) == {"tailer", "character", "lang", "book_checked_at",
                      "rates_checked_at", "levels"}
    assert f["book_checked_at"] == 12.0 and f["levels"] is False
    f["tailer"]["x"] = 1  # a copy: the state is untouched
    assert "x" not in s.tailer
