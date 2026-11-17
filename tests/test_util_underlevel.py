"""UTIL-UNDERLEVEL: the under-level warning from the area generation line
and the player's level-ups (research 0028 ruling B). Synthetic events."""

from server.al import underlevel
from server.al.state import SessionState


def gen(area_id, level, at=100.0):
    return {"type": "area_generated", "area_id": area_id, "area_level": level,
            "seed": "1", "recv_ts": at}


def lvl(n, name="Ash", at=50.0):
    return {"type": "level_up", "character": name, "class": "Witch",
            "level": n, "recv_ts": at}


def scene(name, at=101.0, hideout=False):
    return {"type": "scene_changed", "scene": name, "is_hideout": hideout,
            "recv_ts": at}


def test_view_gap_exact():
    v = underlevel.view(10, 14, "G2_3", "The Mud Burrow", False)
    assert v == {"gap": 4, "zone_level": 14, "level": 10,
                 "text": "4 levels under this zone (zone level 14).",
                 "word": "4 lv under", "source": "log"}
    assert len(v["word"]) <= underlevel.WORD_MAX


def test_word_is_never_cut():
    # design review R8: every possible gap fits the 15-char slot whole
    for gap in range(1, 100):
        v = underlevel.view(1, 1 + gap, "Map1", "z", False, threshold=1)
        assert v["word"] == f"{gap} lv under" and len(v["word"]) <= underlevel.WORD_MAX


def test_view_threshold_and_below():
    assert underlevel.view(10, 12, "G2_3", "z", False) is None          # gap 2 < 3
    assert underlevel.view(10, 13, "G2_3", "z", False)["gap"] == 3       # at threshold
    assert underlevel.view(10, 11, "G2_3", "z", False, threshold=1)["text"].startswith(
        "1 level under")
    assert underlevel.view(20, 14, "G2_3", "z", False) is None          # over-levelled


def test_unknown_player_level_no_warning():
    for level in (None, 0, True, "10"):
        assert underlevel.view(level, 30, "G2_3", "z", False) is None


def test_towns_and_hideouts_skipped():
    assert underlevel.view(1, 15, "G2_town", "Ardura Caravan", False) is None
    assert underlevel.view(1, 15, "HideoutFelled", "Felled Hideout", False) is None
    assert underlevel.view(1, 15, "Map1", "Somewhere", True) is None
    table = {"G1": [{"id": "G1_x", "name": "Clearfell Camp", "level": 15, "town": True}]}
    assert underlevel.view(1, 15, "G1_x", "Clearfell Camp", False, table) is None


def test_zone_table_fallback_and_absent():
    table = {"G2": [{"id": "G2_3", "name": "The Mud Burrow", "level": 16, "town": False}]}
    v = underlevel.view(10, None, "G2_3", "The Mud Burrow", False, table)
    assert v["zone_level"] == 16 and v["source"] == "zone table"
    by_name = underlevel.view(10, None, None, "The Mud Burrow", False, table)
    assert by_name["gap"] == 6
    # no log level, no table: nothing (graceful)
    assert underlevel.view(10, None, "G2_3", "The Mud Burrow", False, {}) is None
    assert underlevel.view(10, None, "G2_3", "The Mud Burrow", False, None) is None


def test_gap_setting():
    assert underlevel.gap_setting(5) == 5
    for bad in (None, 0, 21, True, "4", 3.5):
        assert underlevel.gap_setting(bad) == underlevel.DEFAULT_GAP


def test_state_snapshot_appears_and_clears():
    st = SessionState(clock=lambda: 200.0)
    st.apply(lvl(5))
    st.apply(gen("G1_4", 9))
    st.apply(scene("The Grelwood"))
    snap = st.snapshot()
    assert snap["underlevel"]["gap"] == 4
    # level-ups clear it by themselves
    st.apply(lvl(6, at=150.0))
    st.apply(lvl(7, at=160.0))
    assert st.snapshot()["underlevel"] is None
    # another player's level-up never counts
    st.apply(gen("G1_5", 12, at=170.0))
    st.apply(lvl(1, name="Other", at=171.0))
    assert st.snapshot()["underlevel"]["level"] == 7
    # a town entry clears it
    st.apply(gen("G1_town", 15, at=180.0))
    assert st.snapshot()["underlevel"] is None


def test_state_threshold_setting_bumps_version():
    st = SessionState(clock=lambda: 200.0)
    st.apply(lvl(10))
    st.apply(gen("G2_3", 12))
    assert st.snapshot()["underlevel"] is None
    v = st.version
    assert st.set_underlevel_gap(2) is True and st.version == v + 1
    assert st.set_underlevel_gap(2) is False
    assert st.snapshot()["underlevel"]["gap"] == 2
    st.set_underlevel_gap("junk")
    assert st.underlevel_gap == underlevel.DEFAULT_GAP


def test_unknown_level_in_state():
    st = SessionState(clock=lambda: 200.0)
    st.apply(gen("G3_1", 30))
    assert st.snapshot()["underlevel"] is None
