"""TEST-LIVE-EXIT (decision 0029): a killed game writes no Client.txt line,
so a quiet log for summary.IDLE_S puts the state in an "idle, game may be
closed" mode by itself: the zone stays (marked stale), the zone and map
clocks freeze at the last line, the play stretch closes into the summary
card, and the next line clears it. Log staleness only: no process check.
Synthetic events, a fake clock; no game, no network."""

import inspect
import pathlib

from server.al import state as state_mod
from server.al import state_idle
from server.al import summary
from server.al.state import SessionState

IDLE = summary.IDLE_S


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def gen(area_id, at, seed="1", level=65):
    return {"type": "area_generated", "area_id": area_id, "area_level": level,
            "seed": seed, "recv_ts": at}


def scene(name, at, hideout=False):
    return {"type": "scene_changed", "scene": name, "is_null": False,
            "is_transient": False, "is_hideout": hideout, "recv_ts": at}


def whisper_in(at):
    return {"type": "whisper_in", "from": "Someone", "text": "hi", "recv_ts": at}


def consented(clk):
    st = SessionState(clock=clk)
    st.set_tailer(consented=True, reading=True, path="logs/Client.txt")
    return st


def in_map(st):
    st.apply(gen("MapCrypt", 1000.0))
    st.apply(scene("Crypt", 1010.0))


def test_quiet_log_turns_idle_after_idle_s_only():
    clk = Clock()
    st = consented(clk)
    in_map(st)
    assert st.check_log_idle(now=1010.0 + IDLE - 1) is False
    assert st.snapshot()["tailer"]["idle"] is False
    assert st.check_log_idle(now=1010.0 + IDLE) is True
    assert st.check_log_idle(now=1010.0 + IDLE + 5) is False  # once
    clk.t = 1010.0 + IDLE + 60
    snap = st.snapshot()
    assert snap["tailer"]["idle"] is True
    assert snap["tailer"]["last_line_at"] == 1010.0


def test_idle_keeps_the_zone_and_freezes_its_clocks_at_the_last_line():
    clk = Clock()
    st = consented(clk)
    in_map(st)
    st.apply(whisper_in(1100.0))  # any line keeps the log alive
    st.check_log_idle(now=1100.0 + IDLE)
    clk.t = 1100.0 + IDLE + 600
    snap = st.snapshot()
    assert snap["zone"] == "Crypt"
    assert snap["zone_entered_at"] == 1010.0
    assert snap["zone_s"] == 90.0  # frozen at the last line, not now
    cur = snap["maps"]["current"]
    assert cur["inside"] is False
    assert cur["time_s"] == 90.0


def test_idle_closes_the_play_stretch_into_the_summary_card():
    clk = Clock()
    st = consented(clk)
    in_map(st)
    st.check_log_idle(now=1010.0 + IDLE)
    card = st.snapshot()["session_summary"]
    assert card is not None
    assert card["reason"] == "idle"
    assert card["ended_at"] == 1010.0
    assert st.check_session_end(now=99999.0) is None  # already closed


def test_idle_closes_with_movers_when_given():
    clk = Clock()
    st = consented(clk)
    in_map(st)
    movers = {"up": [{"name": "Exalted Orb", "change": 12, "value": 1.0,
                      "unit": "Divine Orb", "type": "Currency"}], "down": []}
    st.check_log_idle(now=1010.0 + IDLE, movers=movers)
    assert st.snapshot()["session_summary"]["reason"] == "idle"


def test_next_line_clears_idle_and_the_zone_clock_runs_again():
    clk = Clock()
    st = consented(clk)
    in_map(st)
    st.check_log_idle(now=1010.0 + IDLE)
    t2 = 1010.0 + IDLE + 300
    st.apply(whisper_in(t2))
    clk.t = t2 + 10
    snap = st.snapshot()
    assert snap["tailer"]["idle"] is False
    assert snap["tailer"]["last_line_at"] == t2
    assert snap["zone_s"] == t2 + 10 - 1010.0


def test_new_game_run_after_idle_clears_it():
    clk = Clock()
    st = consented(clk)
    in_map(st)
    st.check_log_idle(now=1010.0 + IDLE)
    st.apply({"type": "log_opened", "recv_ts": 1010.0 + IDLE + 900})
    snap = st.snapshot()
    assert snap["tailer"]["idle"] is False
    assert snap["zone"] is None


def test_no_idle_without_consent_or_before_any_line():
    clk = Clock()
    st = SessionState(clock=clk)
    in_map(st)
    assert st.check_log_idle(now=99999.0) is False
    assert st.snapshot()["tailer"]["idle"] is False
    fresh = consented(Clock())
    assert fresh.check_log_idle(now=99999.0) is False
    assert fresh.snapshot()["tailer"]["idle"] is False


def test_idle_due_is_cheap_and_matches():
    clk = Clock()
    st = consented(clk)
    in_map(st)
    assert st.log_idle_due(now=1010.0 + IDLE - 1) is False
    assert st.log_idle_due(now=1010.0 + IDLE) is True
    st.check_log_idle(now=1010.0 + IDLE)
    assert st.log_idle_due(now=1010.0 + IDLE + 1) is False


def test_core_tick_turns_idle_and_saves_the_card(tmp_path):
    from server.al.core import Core
    core = Core(runtime=tmp_path, tail=False)
    try:
        core.state.set_tailer(consented=True, reading=True, path="x")
        core.state.apply(gen("MapCrypt", 1000.0))
        core.state.apply(scene("Crypt", 1010.0))
        assert core.tick_summary(now=1010.0 + IDLE - 1) is None
        card = core.tick_summary(now=1010.0 + IDLE)
        assert card is not None and card["reason"] == "idle"
        assert core.state.snapshot()["tailer"]["idle"] is True
        assert (tmp_path / "session_summaries.json").exists()
    finally:
        core.close()


def test_exit_detection_never_looks_at_processes():
    # Decision 0029: log staleness only; no process list, no handle.
    root = pathlib.Path(state_mod.__file__).parent
    # TEST-STATE-MIXIN-C: the idle check lives in state_idle.IdleMixin
    for name in ("state.py", "state_idle.py", "summary.py", "core.py"):
        src = (root / name).read_text(encoding="utf-8")
        for bad in ("tasklist", "CreateToolhelp32Snapshot", "EnumProcesses",
                    "OpenProcess", "PathOfExile"):
            assert bad not in src, (name, bad)
    assert issubclass(SessionState, state_idle.IdleMixin)
    assert "check_log_idle" in inspect.getsource(state_idle.IdleMixin)


def test_resume_seed_turns_a_closed_game_idle():
    # A game that closed before the core started: the resumed log's mtime
    # stands in for the last line.
    clk = Clock(5000.0)
    st = consented(clk)
    st.seed_last_line(1000.0)
    assert st.check_log_idle(now=1000.0 + IDLE) is True
    live = consented(Clock())
    live.apply(whisper_in(4000.0))
    live.seed_last_line(1000.0)  # a live line wins over the seed
    assert live.snapshot()["tailer"]["last_line_at"] == 4000.0


def test_core_resume_seeds_from_the_log_mtime(tmp_path):
    import os
    from server.al.core import Core
    log = tmp_path / "Client.txt"
    log.write_text("2026/11/16 20:00:00 ***** LOG FILE OPENING *****\n"
                   "2026/11/16 20:00:05 1 a [INFO Client 1] [SCENE] Set Source [Crypt]\n",
                   encoding="ascii", newline="\n")
    os.utime(log, (1000.0, 1000.0))
    core = Core(runtime=tmp_path, tail=False)
    try:
        core._resume(log, log.stat().st_size)
        assert core.state.snapshot()["tailer"]["last_line_at"] == 1000.0
    finally:
        core.close()
