"""UTIL-RUN-HISTORY: per-run act splits and deaths by zone across runs
(research 0028 ruling C, decision 0036). Synthetic events; tmp files only."""

import json

from server.al import jsonfile, runhistory
from server.al.core import Core
from server.al.state import SessionState


class Clock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


def gen(area_id, at, area_level=1):
    return {"type": "area_generated", "area_id": area_id, "area_level": area_level,
            "seed": "1", "recv_ts": at}


def scene(name, at):
    return {"type": "scene_changed", "scene": name, "recv_ts": at}


def death(at, name="Ash"):
    return {"type": "death", "character": name, "recv_ts": at}


def lvl(n, at, name="Ash"):
    return {"type": "level_up", "character": name, "class": "Witch", "level": n,
            "recv_ts": at}


def play_run(st, t0, act1_s, act2_s, deaths_in=("The Grelwood",)):
    """One run: Act 1 for act1_s, Act 2 for act2_s, then Act 3 opens."""
    st.apply(gen("G1_1", t0))
    st.apply(lvl(1, t0 + 1))
    for i, zone in enumerate(deaths_in):
        st.apply(scene(zone, t0 + 10 + i))
        st.apply(death(t0 + 11 + i))
    st.apply(gen("G2_1", t0 + act1_s))
    st.apply(gen("G3_1", t0 + act1_s + act2_s))


def test_run_record_from_state():
    clock = Clock(10000.0)
    st = SessionState(clock=clock)
    assert st.run_record() is None
    play_run(st, 1000.0, 1200.0, 900.0, deaths_in=("The Grelwood", "The Grelwood"))
    clock.t = 4000.0
    rec = st.run_record()
    assert rec["started_at"] == 1000.0 and rec["character"] == "Ash"
    assert rec["class"] == "Witch" and rec["closed"] == 2 and rec["finished"] is False
    assert rec["splits"] == [{"key": "G1", "label": "Act 1", "time_s": 1200.0},
                             {"key": "G2", "label": "Act 2", "time_s": 900.0}]
    assert rec["deaths"] == {"The Grelwood": 2}


def test_a_new_run_resets_the_death_counter():
    st = SessionState(clock=Clock(99999.0))
    play_run(st, 1000.0, 600.0, 600.0)
    # a new character: G1_1 at level <= 2 starts a new run
    st.apply(gen("G1_1", 5000.0))
    rec = st.run_record()
    assert rec["started_at"] == 5000.0 and rec["deaths"] == {} and rec["closed"] == 0


def test_partial_first_split_is_no_best():
    st = SessionState(clock=Clock(9000.0))
    st.apply(gen("G2_3", 1000.0))  # core started mid-campaign
    st.apply(gen("G3_1", 2000.0))
    rec = st.run_record()
    assert rec["closed"] == 1 and rec["splits"] == []


def test_history_bests_and_delta(tmp_path):
    h = runhistory.RunHistory(tmp_path / runhistory.FILE_NAME)
    base = {"character": "Ash", "class": "Witch", "finished": False}
    assert h.record(dict(base, started_at=1000.0, deaths={"Grelwood": 2},
                         splits=[{"key": "G1", "label": "Act 1", "time_s": 1500.0},
                                 {"key": "G2", "label": "Act 2", "time_s": 900.0}]))
    assert h.record(dict(base, started_at=50000.0, deaths={"Ogham": 1, "Grelwood": 1},
                         splits=[{"key": "G1", "label": "Act 1", "time_s": 1200.0}]))
    cur = dict(base, started_at=90000.0, deaths={"Ogham": 3},
               splits=[{"key": "G1", "label": "Act 1", "time_s": 1300.0}])
    v = h.view(cur)
    assert v["on"] is True and v["runs"] == 3
    assert v["best"] == [
        {"key": "G1", "label": "Act 1", "best_s": 1200.0, "best_text": "20:00",
         "delta_s": 100.0},
        {"key": "G2", "label": "Act 2", "best_s": 900.0, "best_text": "15:00",
         "delta_s": None}]
    assert v["deaths_by_zone"] == [{"zone": "Ogham", "deaths": 4},
                                   {"zone": "Grelwood", "deaths": 3}]
    assert v["text"] == runhistory.ON_TEXT and v["empty_text"] == ""
    # the current run's own saved record is not its own best
    h.record(cur)
    assert h.view(cur)["best"][0]["best_s"] == 1200.0


def test_resume_matches_the_saved_run_no_duplicate(tmp_path):
    h = runhistory.RunHistory(tmp_path / runhistory.FILE_NAME)
    run = {"character": "Ash", "started_at": 1000.4, "deaths": {},
           "splits": [{"key": "G1", "label": "Act 1", "time_s": 1200.0}]}
    assert h.record(run) is True
    assert h.record(run) is False  # unchanged: no write
    moved = dict(run, started_at=1001.0,
                 splits=run["splits"] + [{"key": "G2", "label": "Act 2", "time_s": 60.0}])
    assert h.record(moved) is True
    assert len(h.runs) == 1 and len(h.runs[0]["splits"]) == 2
    # another character with the same start is another run
    assert h.record(dict(run, character="Other")) is True and len(h.runs) == 2


def test_file_is_bounded_and_survives_reload(tmp_path):
    p = tmp_path / runhistory.FILE_NAME
    h = runhistory.RunHistory(p)
    for i in range(runhistory.MAX_RUNS + 5):
        h.record({"character": "Ash", "started_at": 1000.0 * (i + 1) * 10, "deaths": {},
                  "splits": [{"key": "G1", "label": "Act 1", "time_s": 100.0 + i}]})
    assert len(h.runs) == runhistory.MAX_RUNS
    again = runhistory.RunHistory(p)
    assert again.runs == h.runs
    assert again.runs[0]["splits"][0]["time_s"] == 105.0  # oldest dropped
    doc = json.loads(p.read_text(encoding="ascii"))
    # UTIL-MULTICHAR: schema 2, runs kept per character (decision 0038)
    assert doc["schema"] == 2
    assert len(doc["characters"]["Ash"]["runs"]) == runhistory.MAX_RUNS
    # long strings and many zones are cut
    run = runhistory.clean_run({"started_at": 1.0, "character": "x" * 500,
                                "deaths": {f"z{i}": 1 for i in range(100)},
                                "splits": []})
    assert len(run["character"]) == runhistory.MAX_TEXT
    assert len(run["deaths"]) == runhistory.MAX_ZONES
    # RUN-DURABLE-STORE-FILES (F-014): an oversized or broken file is
    # restored from its .bak and the main file is healed
    good = p.read_bytes()
    p.write_text("x" * (runhistory.MAX_BYTES + 1), encoding="ascii")
    assert runhistory.load(p) == h.runs and p.read_bytes() == good
    p.write_text("{bad", encoding="ascii")
    assert runhistory.load(p) == h.runs and p.read_bytes() == good
    # without a .bak an oversized or broken file reads as empty
    jsonfile.bak_path(p).unlink()
    p.write_text("x" * (runhistory.MAX_BYTES + 1), encoding="ascii")
    assert runhistory.load(p) == []
    p.write_text("{bad", encoding="ascii")
    assert runhistory.load(p) == []
    assert not jsonfile.bak_path(p).exists()


def test_clear_and_off(tmp_path):
    h = runhistory.RunHistory(tmp_path / runhistory.FILE_NAME)
    h.record({"character": "Ash", "started_at": 1.0, "deaths": {"Z": 1}, "splits": []})
    h.clear()
    assert h.runs == [] and runhistory.load(h.path) == []
    v = h.view(None)
    assert v["empty_text"] == runhistory.EMPTY_TEXT
    assert v["deaths_empty_text"] == runhistory.DEATHS_EMPTY_TEXT
    off = h.view(None, enabled=False)
    assert off["on"] is False and off["text"] == runhistory.OFF_TEXT and off["best"] == []
    assert runhistory.enabled_setting(None) and not runhistory.enabled_setting(False)


def test_core_saves_on_split_close_and_honours_off(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False)
    try:
        path = tmp_path / "rt" / runhistory.FILE_NAME
        core.state.apply(gen("G1_1", 1000.0))
        assert core.tick_history() is False and not path.exists()  # no split closed
        assert core.state.snapshot()["run_history"]["on"] is True
        core.state.apply(gen("G2_1", 2200.0))
        assert core.tick_history() is True
        assert runhistory.load(path)[0]["splits"][0]["time_s"] == 1200.0
        assert core.tick_history() is False  # nothing new
        # off: no write, view says off
        core.set_history(enabled=False)
        core.state.apply(gen("G3_1", 3000.0))
        assert core.tick_history() is False
        assert len(runhistory.load(path)[0]["splits"]) == 1
        assert core.state.snapshot()["run_history"]["on"] is False
        # clear empties the file
        core.set_history(enabled=True, clear=True)
        assert core.history.runs == [] and runhistory.load(path) == []
        assert core.tick_history() is False  # the cleared run is not re-saved
        core.state.apply(gen("G4_1", 4000.0))
        assert core.tick_history() is True  # until its next act closes
        assert core.state.snapshot()["run_history"]["runs"] == 1
    finally:
        core.close()


def test_file_is_byte_identical_when_no_clear_arrives(tmp_path):
    """RUN-HISTORY-UNDO (F-191): the page waits out its 10 s undo window
    before it sends the clear, so a core that gets no clear request (an
    Undo, a page close or a core exit inside the window) keeps the saved
    file byte for byte."""
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    path = tmp_path / "rt" / runhistory.FILE_NAME
    core = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False)
    try:
        core.state.apply(gen("G1_1", 1000.0))
        core.state.apply(gen("G2_1", 2200.0))
        assert core.tick_history() is True
        before = path.read_bytes()
        assert runhistory.load(path)
        for _ in range(20):  # the window's core ticks, no request
            assert core.tick_history() is False
        assert path.read_bytes() == before
    finally:
        core.close()
    assert path.read_bytes() == before  # a core exit leaves it too
    again = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False)
    try:
        assert again.history.runs and path.read_bytes() == before
    finally:
        again.close()
