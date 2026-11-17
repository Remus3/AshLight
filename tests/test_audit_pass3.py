"""AREA-AUDIT pass 3 regression tests (docs/audit/2026-11-17-audit.md,
"Pass 3"). Synthetic events and a fake clock; no game, no network."""

from server.al import summary
from server.al.state import SessionState

IDLE = summary.IDLE_S


def _consented(t=5000.0):
    st = SessionState(clock=lambda: t)
    st.set_tailer(consented=True, reading=True, path="logs/Client.txt")
    return st


def test_p3_1_tailer_status_is_not_a_log_line():
    # Decision 0029: last_line_at is the receipt time of the last PARSED
    # Client.txt line. The tailer's own status events are not log lines.
    st = _consented()
    st.apply({"type": "area_generated", "area_id": "MapCrypt", "area_level": 65,
              "seed": "1", "recv_ts": 1000.0, "source": "client_log"})
    st.apply({"type": "tailer_reset", "reason": "missing", "source": "tailer",
              "recv_ts": 1000.0 + IDLE / 2})
    assert st.snapshot()["tailer"]["last_line_at"] == 1000.0
    assert st.check_log_idle(now=1000.0 + IDLE) is True
    # a status event after the idle state does not clear it either
    st.apply({"type": "tailer_started", "path": "x", "source": "tailer",
              "recv_ts": 1000.0 + IDLE + 5})
    assert st.snapshot()["tailer"]["idle"] is True


def test_p3_1_core_resume_seed_survives_the_tailer_start(tmp_path):
    # The real tailer calls on_resume (the mtime seed) and THEN emits
    # tailer_started; the seed must survive it, so a game closed before the
    # core started turns idle IDLE_S after its last write, not after start.
    import os
    from server.al.core import Core
    log = tmp_path / "Client.txt"
    log.write_text("2026/11/16 20:00:05 1 a [INFO Client 1] [SCENE] Set Source [Crypt]\n",
                   encoding="ascii", newline="\n")
    os.utime(log, (1000.0, 1000.0))
    core = Core(runtime=tmp_path, tail=False)
    try:
        core.state.set_tailer(consented=True, reading=True, path=str(log))
        core._resume(log, log.stat().st_size)
        core._on_status({"type": "tailer_started", "path": str(log),
                         "offset": log.stat().st_size, "file_size": log.stat().st_size,
                         "resumed": False, "recv_ts": 2000.0})
        assert core.state.snapshot()["tailer"]["last_line_at"] == 1000.0
        core.tick_summary(now=1000.0 + IDLE)
        assert core.state.snapshot()["tailer"]["idle"] is True
    finally:
        core.close()


def test_p3_2_pricebook_parsers_survive_a_huge_json_int():
    # FUZZ-4 was fixed in ninja._num only; the price book kept its own copy.
    from server.al import pricebook
    huge = "1" + "0" * 400
    body = ('{"core": {}, "lines": [{"name": "A", "primaryValue": %s},'
            ' {"name": "B", "primaryValue": 2}]}' % huge)
    got = pricebook.parse_item_overview(body)
    assert [e["name"] for e in got["entries"]] == ["B"]
    assert pricebook._num(10 ** 400) is None


def test_p3_5_ninja_rollover_wording_matches_decision_0026():
    # Behaviour (tests/test_price_book.py rollover test): the next hourly
    # refresh re-reads the league; the docstring no longer claims "at once".
    from server.al import ninja
    doc = " ".join(ninja.__doc__.split())
    assert "at once" not in doc
    assert "the next hourly refresh re-reads it (within the hour, decision 0026" in doc
    assert ninja.MIN_INTERVAL_S <= 3600


def test_p3_7_pricebook_saves_each_request_time_as_it_goes(tmp_path):
    # A core killed mid-loop (up to 22 GETs x 10 s) must not re-request the
    # types it already asked for: attempt_at is on disk per request.
    from server.al import pricebook
    book = pricebook.PriceBook(tmp_path)
    asked = []

    class Killed(BaseException):
        pass

    def get(url, etag):
        asked.append(url)
        if len(asked) == 3:
            raise Killed()  # the process dies during the third GET
        return 200, {}, b'{"core": {}, "lines": []}'
    try:
        book.refresh(get, "https://poe.ninja", "Example League", 1000.0)
    except Killed:
        pass
    again = pricebook.PriceBook(tmp_path)  # the restarted core
    done = [n for n, t in again.doc["types"].items()
            if isinstance(t.get("attempt_at"), (int, float))]
    assert len(done) >= 2
    asked2 = []
    again.refresh(lambda url, etag: asked2.append(url) or (200, {}, b"{}"),
                  "https://poe.ninja", "Example League", 1000.0 + 60)
    assert not set(asked[:2]) & set(asked2)  # not re-requested early


def test_p3_4_map_clock_resumes_when_idle_clears_in_the_same_zone():
    # Idle freezes the map clock at the last line; a later non-scene line in
    # the same map proves the game is alive, so the clock runs again from it
    # (the idle gap itself is not counted).
    from test_live_exit import Clock, consented, in_map, scene, whisper_in
    clk = Clock()
    st = consented(clk)
    in_map(st)  # Crypt entered at 1010
    st.apply(whisper_in(1100.0))
    assert st.check_log_idle(now=1100.0 + IDLE) is True
    back = 1100.0 + IDLE + 600
    st.apply(whisper_in(back))
    clk.t = back + 30
    cur = st.snapshot()["maps"]["current"]
    assert cur["inside"] is True
    assert cur["time_s"] == 90.0 + 30.0
    # a game restart (log_opened) clearing idle keeps the clock stopped
    st.apply(whisper_in(back + 40))
    assert st.check_log_idle(now=back + 40 + IDLE) is True
    st.apply({"type": "log_opened", "recv_ts": back + 40 + IDLE + 5})
    assert st.snapshot()["maps"]["current"]["inside"] is False
    # idle that cleared on a zone change: the new zone decides, as before
    st2 = consented(Clock())
    in_map(st2)
    st2.check_log_idle(now=1010.0 + IDLE)
    st2.apply(scene("Hideout", 1010.0 + IDLE + 9, hideout=True))
    assert st2.snapshot()["maps"]["current"]["inside"] is False
