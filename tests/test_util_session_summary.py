"""UTIL-SESSION-SUMMARY: an end-of-session summary card, built by itself
when the game goes idle for IDLE_S or a new game run starts in Client.txt
(the previous game closed), persisted only under the runtime dir.
Synthetic events, a fake clock, tmp runtime; no network, no game."""

import json

from server.al import parser, summary
from server.al.state import SessionState


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


def death(at, who="Ash"):
    return {"type": "death", "character": who, "suicide": False, "recv_ts": at}


def up(level, at, who="Ash"):
    return {"type": "level_up", "character": who, "class": "Witch",
            "level": level, "recv_ts": at}


MOVERS = {"up": [{"name": "Greater Essence of Ruin", "change": 61, "value": 0.35,
                  "unit": "Divine Orb", "type": "Essences"},
                 {"name": "Small Orb", "change": 2}],
          "down": [{"name": "Hollow Crown", "change": -25.5, "value": 1234.5,
                    "unit": "Divine Orb", "type": "UniqueArmours"}]}


def play(st):
    for ev in (up(68, 1000.0), gen("MapCrypt", 1100.0), scene("Crypt", 1110.0),
               death(1500.0), up(69, 2000.0), gen("MapSavannah", 2500.0, seed="2"),
               scene("Savannah", 2510.0), scene("Felled Hideout", 3500.0, True),
               up(70, 4600.0)):
        st.apply(ev)


def test_idle_closes_the_session_with_exact_card():
    clk = Clock(1000.0)
    st = SessionState(clock=clk)
    play(st)
    clk.t = 4600.0 + summary.IDLE_S - 1
    assert st.check_session_end(movers=MOVERS) is None
    clk.t = 4600.0 + summary.IDLE_S
    card = st.check_session_end(movers=MOVERS)
    assert card is not None
    assert card["reason"] == "idle"
    assert card["ended_at"] == 4600.0
    assert card["played_s"] == 3600.0
    assert card["levels"] == 2
    assert card["level_to"] == 70
    assert card["maps"] == 2
    assert card["deaths"] == 1
    assert card["lines"] == [
        "Played 1:00:00 and reached level 70.",
        "Levels: 68 to 70, at 2.0 an hour.",
        "Maps: 2.",
        "Deaths: 1.",
        "Price movers: Greater Essence of Ruin up 61%, Hollow Crown down 25.5%, "
        "Small Orb up 2%.",
    ]
    assert card["reason_text"] == "after 20 minutes with no game activity"
    snap = st.snapshot()
    assert snap["session_summary"]["id"] == card["id"]
    # nothing new happened: no second card
    clk.t += 5000.0
    assert st.check_session_end(movers=MOVERS) is None


def test_idle_gaps_do_not_count_as_played_and_a_new_stretch_starts_fresh():
    clk = Clock(1000.0)
    st = SessionState(clock=clk)
    play(st)
    clk.t = 9000.0
    first = st.check_session_end()
    assert first["lines"][-1] == "Deaths: 1."  # no movers line without movers
    st.apply(gen("MapCrypt", 20000.0, seed="9"))
    st.apply(scene("Crypt", 20010.0))
    st.apply(scene("Hideout", 20310.0, hideout=True))
    clk.t = 20310.0 + summary.IDLE_S
    second = st.check_session_end()
    assert second["id"] == first["id"] + 1
    assert second["played_s"] == 310.0
    assert second["maps"] == 1
    assert second["deaths"] == 0
    assert second["levels"] == 0
    assert second["lines"] == ["Played 5:10 at level 70.", "Maps: 1.", "Deaths: 0."]


def test_new_game_run_closes_the_previous_session():
    line = "2026/11/17 21:00:00 ***** LOG FILE OPENING *****"
    ev = parser.parse_line(line)
    assert ev["type"] == "game_started"
    assert ev["ts_local"] == "2026-11-17T21:00:00"
    clk = Clock(1000.0)
    st = SessionState(clock=clk)
    play(st)
    st.apply(dict(ev, recv_ts=4700.0))
    card = st.snapshot()["session_summary"]
    assert card["reason"] == "game_closed"
    assert card["reason_text"] == "when the game closed"
    assert card["ended_at"] == 4600.0
    clk.t = 99999.0
    assert st.check_session_end() is None  # already closed


def test_no_activity_no_card():
    clk = Clock(1000.0)
    st = SessionState(clock=clk)
    clk.t = 99999.0
    assert st.check_session_end() is None
    assert st.snapshot()["session_summary"] is None
    st.apply({"type": "game_started", "recv_ts": 100000.0})
    assert st.snapshot()["session_summary"] is None


def test_card_is_json_safe_and_movers_junk_is_ignored():
    card = summary.build(start={"level": None, "level_ups": 0, "deaths": 0, "maps": 0},
                         end={"level": None, "level_ups": 0, "deaths": 0, "maps": 0},
                         played_s=30.0, ended_at=50.0, reason="idle",
                         movers={"up": "x", "down": [None, {"name": 5}, {"change": "y"}]})
    json.dumps(card)
    assert card["lines"] == ["Played 0:30.", "Maps: 0.", "Deaths: 0."]


def test_persist_and_load_keeps_the_last_cards(tmp_path):
    f = tmp_path / "session_summaries.json"
    for i in range(summary.MAX_SAVED + 3):
        summary.save(f, {"id": i, "lines": ["x"], "ended_at": float(i)})
    saved = json.loads(f.read_text(encoding="utf-8"))
    assert len(saved["summaries"]) == summary.MAX_SAVED
    assert summary.load_last(f)["id"] == summary.MAX_SAVED + 2
    assert summary.load_last(tmp_path / "missing.json") is None
    (tmp_path / "bad.json").write_text("{nope", encoding="utf-8")
    assert summary.load_last(tmp_path / "bad.json") is None


def test_core_tick_saves_under_its_runtime_and_reloads(tmp_path):
    from server.al.core import Core
    core = Core(runtime=tmp_path, tail=False)
    try:
        assert core.tick_summary(now=1.0) is None
        for ev in (gen("MapCrypt", 1000.0), scene("Crypt", 1010.0), death(1300.0)):
            core.state.apply(ev)
        assert core.tick_summary(now=1300.0 + summary.IDLE_S - 1) is None
        card = core.tick_summary(now=1300.0 + summary.IDLE_S)
        assert card["lines"] == ["Played 5:00.", "Maps: 1.", "Deaths: 1."]
        assert core.tick_summary(now=99999.0) is None  # saved once
        saved = json.loads((tmp_path / "session_summaries.json").read_text("utf-8"))
        assert [c["id"] for c in saved["summaries"]] == [card["id"]]
    finally:
        core.close()
    again = Core(runtime=tmp_path, tail=False)
    try:
        assert again.state.snapshot()["session_summary"]["lines"] == card["lines"]
        assert again.tick_summary(now=99999.0) is None  # not saved twice
    finally:
        again.close()


def test_summary_file_lives_under_the_runtime_dir():
    from server.al import paths
    assert summary.summary_file().parent == paths.runtime_dir()
