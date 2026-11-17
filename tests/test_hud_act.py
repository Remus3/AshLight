"""HUD-ACT: per-act splits from area generation events, the zone level
table from the cached world areas export, and the snapshot `acts` part.
Exact-output tests; no network (the table is a tmp_path file)."""

import json

from server.al import acts, parser
from server.al.state import SessionState


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def gen(area_id, at, level=1):
    return {"type": "area_generated", "area_id": area_id, "area_level": level,
            "seed": "1", "recv_ts": at}


def test_act_of_and_label():
    assert acts.act_of("G1_1") == {"key": "G1", "label": "Act 1", "n": 1}
    assert acts.act_of("G1_town") == {"key": "G1", "label": "Act 1", "n": 1}
    assert acts.act_of("G3_12") == {"key": "G3", "label": "Act 3", "n": 3}
    assert acts.act_of("C_G2_4") == {"key": "C2", "label": "Cruel Act 2", "n": 2}
    assert acts.act_of("P1_2") == {"key": "P1", "label": "Interlude 1", "n": 1}
    for other in ("HideoutFelled", "MapCrypt", "G0_1", "G1", "", None, 5, "g1_1"):
        assert acts.act_of(other) is None
    assert acts.label_of("G2") == "Act 2"
    assert acts.label_of("C1") == "Cruel Act 1"
    assert acts.label_of("P3") == "Interlude 3"
    assert acts.label_of("X1") is None
    assert acts.label_of("G") is None
    assert acts.label_of(None) is None
    assert acts.is_endgame("MapCrypt") and not acts.is_endgame("G1_1")


def test_splits_full_run_exact():
    sp = acts.ActSplits()
    assert sp.fold("G1_1", 100.0) is True
    assert sp.fold("G1_town", 400.0) is False       # same act
    assert sp.fold("HideoutFelled", 500.0) is False  # hideout keeps the split
    assert sp.fold("G2_1", 1300.0) is True
    assert sp.fold("G1_town", 1400.0) is False      # back to an old act
    assert sp.fold("G2_2", 1500.0) is False
    assert sp.fold("G3_1", 2500.0) is True
    assert sp.current() == "G3"
    assert sp.rows(3100.0) == [
        {"key": "G1", "label": "Act 1", "started_at": 100.0, "ended_at": 1300.0,
         "time_s": 1200.0, "cumulative_s": 1200.0, "current": False, "partial": False},
        {"key": "G2", "label": "Act 2", "started_at": 1300.0, "ended_at": 2500.0,
         "time_s": 1200.0, "cumulative_s": 2400.0, "current": False, "partial": False},
        {"key": "G3", "label": "Act 3", "started_at": 2500.0, "ended_at": None,
         "time_s": 600.0, "cumulative_s": 3000.0, "current": True, "partial": False},
    ]
    # an endgame map closes the open split; nothing reopens after it
    assert sp.fold("MapCrypt", 3200.0) is True
    assert sp.finished is True and sp.current() is None
    assert sp.fold("MapCrypt", 3300.0) is False
    assert sp.fold("G4_1", 3400.0) is False
    rows = sp.rows(9999.0)
    assert rows[-1]["ended_at"] == 3200.0 and rows[-1]["time_s"] == 700.0
    assert rows[-1]["cumulative_s"] == 3100.0 and rows[-1]["current"] is False


def test_mid_campaign_start_is_partial_and_unknown_ids_ignored():
    sp = acts.ActSplits()
    assert sp.fold("HideoutFelled", 10.0) is False
    assert sp.fold("MapCrypt", 11.0) is False  # no open split: nothing to close
    assert sp.fold("G2_3", 20.0) is True
    rows = sp.rows(80.0)
    assert [(r["label"], r["partial"], r["time_s"]) for r in rows] == [("Act 2", True, 60.0)]


def test_new_character_starts_new_run():
    sp = acts.ActSplits()
    sp.fold("G1_1", 0.0)
    sp.fold("G2_1", 100.0, player_level=20)
    # a level-30 character walking back into G1_1 keeps the run
    assert sp.fold("G1_1", 150.0, player_level=30) is False
    assert [r["key"] for r in sp.rows(200.0)] == ["G1", "G2"]
    # a fresh character (level 1, or level not known yet) starts over
    assert sp.fold("G1_1", 300.0, player_level=1) is True
    assert sp.rows(360.0) == [
        {"key": "G1", "label": "Act 1", "started_at": 300.0, "ended_at": None,
         "time_s": 60.0, "cumulative_s": 60.0, "current": True, "partial": False}]
    # re-entering G1_1 during Act 1 keeps the same split
    assert sp.fold("G1_1", 400.0, player_level=None) is False
    assert sp.rows(400.0)[0]["started_at"] == 300.0


def test_split_cap():
    sp = acts.ActSplits()
    sp.fold("G1_1", 0.0)
    for n in range(2, acts.MAX_SPLITS + 3):
        sp.fold(f"G{n}_1", float(n))
    rows = sp.rows(100.0)
    assert len(rows) == acts.MAX_SPLITS
    assert rows[0]["partial"] is True  # the run's real start was dropped


AREAS = {
    "NULL": {"id": "NULL", "name": "NULL", "act": 1, "area_level": 0},
    "G1_1": {"id": "G1_1", "name": "The Riverbank", "act": 1, "area_level": 1,
             "is_town": False},
    "G1_town": {"id": "G1_town", "name": "Clearfell Encampment", "act": 1,
                "area_level": 15, "is_town": True},
    "G1_2": {"id": "G1_2", "name": "Clearfell", "act": 1, "area_level": 2},
    "G1_2_boss": {"id": "G1_2_boss", "name": "Clearfell", "act": 1, "area_level": 3},
    "G1_bad": {"id": "G1_bad", "name": "", "act": 1, "area_level": 4},
    "G1_bool": {"id": "G1_bool", "name": "Bool Zone", "act": 1, "area_level": True},
    "G1_str": "not an object",
    "G2_1": {"id": "G2_1", "name": "Vastiri Outskirts", "act": 2, "area_level": 16},
    "HideoutFelled": {"id": "HideoutFelled", "name": "Felled Hideout", "area_level": 1},
    "MapCrypt": {"id": "MapCrypt", "name": "Crypt", "area_level": 65},
}


def write_areas(tmp_path, doc=AREAS):
    p = tmp_path / acts.FILE_NAME
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def test_load_table_exact(tmp_path):
    table = acts.load_table(write_areas(tmp_path))
    assert table == {
        "G1": [
            {"id": "G1_1", "name": "The Riverbank", "level": 1, "town": False},
            {"id": "G1_2", "name": "Clearfell", "level": 2, "town": False},
            {"id": "G1_town", "name": "Clearfell Encampment", "level": 15, "town": True},
        ],
        "G2": [{"id": "G2_1", "name": "Vastiri Outskirts", "level": 16, "town": False}],
    }


def test_load_table_bad_files(tmp_path):
    assert acts.load_table(tmp_path / "missing.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    assert acts.load_table(bad) == {}
    lst = tmp_path / "list.json"
    lst.write_text("[1, 2]", encoding="utf-8")
    assert acts.load_table(lst) == {}


def test_table_cache_reloads_on_change(tmp_path):
    cache = acts.TableCache(tmp_path / acts.FILE_NAME)
    assert cache.get() == {}
    p = write_areas(tmp_path)
    assert list(cache.get()) == ["G1", "G2"]
    p.write_text(json.dumps({"G3_1": {"name": "Jungle", "area_level": 33}}),
                 encoding="utf-8")
    assert cache.get() == {"G3": [{"id": "G3_1", "name": "Jungle", "level": 33,
                                   "town": False}]}
    p.unlink()
    assert cache.get() == {}


def test_snapshot_acts_exact(tmp_path):
    clock = Clock(1000.0)
    st = SessionState(clock=clock)
    snap = st.snapshot()["acts"]
    assert snap == {
        "splits": [], "current": None, "finished": False, "zones": [],
        "zones_act": None, "levels": False, "source": None,
        "empty_text": ("No act times yet. They start by themselves when you enter "
                       "a campaign zone."),
        "no_levels_text": ("Zone levels aren't downloaded yet. Turn on web data, "
                           "then run AshLight's build step (scripts/build.ps1)."),
        "no_zones_text": "Zone levels show here while you are in a campaign act.",
        "act_levels_text": "",
        "partial_text": "partial: counted from the first zone AshLight saw",
    }
    st.set_zone_table(acts.load_table(write_areas(tmp_path)))
    v = st.version
    st.set_zone_table(acts.load_table(write_areas(tmp_path)))
    assert st.version == v  # same table: no push
    assert st.apply(gen("G1_1", 1000.0)) is True
    st.apply({"type": "scene_changed", "scene": "The Riverbank", "recv_ts": 1000.0})
    clock.t = 1090.0
    a = st.snapshot()["acts"]
    assert a["splits"] == [
        {"key": "G1", "label": "Act 1", "started_at": 1000.0, "ended_at": None,
         "time_s": 90.0, "cumulative_s": 90.0, "current": True, "partial": False}]
    assert a["current"] == "G1" and a["zones_act"] == "Act 1" and a["levels"] is True
    assert a["source"] == ("Zone levels: RePoE fork export, downloaded when AshLight "
                           "was built. Game data (c) Grinding Gear Games.")
    assert a["zones"] == [
        {"name": "The Riverbank", "level": 1, "town": False, "here": True},
        {"name": "Clearfell", "level": 2, "town": False, "here": False},
        {"name": "Clearfell Encampment", "level": 15, "town": True, "here": False},
    ]
    # into Act 2: the table follows the act, Act 1's split closes
    st.apply(gen("G2_1", 1600.0, level=16))
    clock.t = 1700.0
    a = st.snapshot()["acts"]
    assert [(r["label"], r["time_s"], r["cumulative_s"], r["current"])
            for r in a["splits"]] == [("Act 1", 600.0, 600.0, False),
                                      ("Act 2", 100.0, 700.0, True)]
    assert a["zones_act"] == "Act 2"
    assert a["zones"] == [{"name": "Vastiri Outskirts", "level": 16, "town": False,
                           "here": True}]
    # a hideout keeps showing the open act's zones
    st.apply(gen("HideoutFelled", 1750.0))
    a = st.snapshot()["acts"]
    assert a["current"] == "G2" and a["zones_act"] == "Act 2"
    assert a["zones"][0]["here"] is False
    # endgame (design review HA-2): the splits stay as the run record, the
    # zone table empties so the card no longer implies a campaign act
    st.apply(gen("MapCrypt", 1800.0, level=65))
    clock.t = 1900.0
    a = st.snapshot()["acts"]
    assert a["finished"] is True and a["current"] is None
    assert a["zones"] == [] and a["zones_act"] is None
    assert [(r["label"], r["time_s"], r["current"]) for r in a["splits"]] == [
        ("Act 1", 600.0, False), ("Act 2", 200.0, False)]
    st.apply(gen("HideoutFelled", 1950.0))
    a = st.snapshot()["acts"]
    assert a["zones"] == [] and a["current"] is None


def test_live_fixture_lines_drive_splits():
    # Real line shapes (research 0002 section 7) through the real parser.
    st = SessionState(clock=Clock(0.0))
    lines = [
        '2026/11/16 21:01:01 59200 2a3b4c5d [DEBUG Client 5150] Generating level 1 '
        'area "G1_1" with seed 1111111',
        '2026/11/16 21:06:00 358100 3b4c5d6e [DEBUG Client 5150] Generating level 15 '
        'area "G1_town" with seed 2222222',
    ]
    for i, line in enumerate(lines):
        ev = parser.parse_line(line)
        ev["recv_ts"] = 10.0 * (i + 1)
        st.apply(ev)
    st._clock = Clock(70.0)
    rows = st.snapshot()["acts"]["splits"]
    assert [(r["label"], r["started_at"], r["time_s"]) for r in rows] == [("Act 1", 10.0, 60.0)]
