"""UTIL-1.0-READY: PoE2 1.0 (2026-12-11, research 0018) must break nothing.
Acts 5 and 6 area ids, Duelist / Shadow and unknown class names, unknown
area ids and system lines, and the league rollover for the trade link and
the price card label (the poe.ninja league re-read is in
tests/test_price_book.py).

Every line here is synthetic and 1.0-SHAPED (invented names and ids in the
known formats); no real 1.0 log exists yet."""

import json

import pytest

from server.al import acts, parser, runs
from server.al.core import Core
from server.al.state import SessionState
from server.al.theorycraft import charjson

_N = [0]


def L(body, tag="INFO"):
    _N[0] += 1
    return f"2026/12/11 19:00:00 {_N[0]} 1a2b3c4d [{tag} Client 4242] {body}"


def G(area_id, level=70):
    return L(f'Generating level {level} area "{area_id}" with seed 9', tag="DEBUG")


def test_acts_five_and_six_read_by_the_same_rule():
    assert acts.act_of("G5_1") == {"key": "G5", "label": "Act 5", "n": 5}
    assert acts.act_of("G6_town") == {"key": "G6", "label": "Act 6", "n": 6}
    assert acts.label_of("G6") == "Act 6"
    s = acts.ActSplits()
    for i, aid in enumerate(("G4_1", "G5_1", "G5_town", "G6_1", "MapNew")):
        s.fold(aid, 100.0 * i, 60)
    assert [r["key"] for r in s.rows(1000.0)] == ["G4", "G5", "G6"]
    assert s.finished is True


@pytest.mark.parametrize("aid", ["G5", "Act5_1", "X_Strange", "", None, 7,
                                 "G0_1", "g5_1", "HideoutConqueror", "G100_1"])
def test_unknown_area_ids_change_nothing(aid):
    assert acts.act_of(aid) is None
    s = acts.ActSplits()
    s.fold("G5_1", 0.0, 60)
    assert s.fold(aid, 10.0, 60) is False
    m = runs.MapRuns()
    assert m.on_generated(aid, 10.0, 70) is False


@pytest.mark.parametrize("cls", ["Duelist", "Shadow", "Blade Dancer of the Vaal"])
def test_new_and_unknown_class_names_parse_and_count(cls):
    ev = parser.parse_line(L(f": Quill ({cls}) is now level 2"))
    assert ev["type"] == "level_up" and ev["class"] == cls and ev["level"] == 2
    st = SessionState(clock=lambda: 10.0)
    st.apply(dict(ev, recv_ts=10.0))
    s = st.snapshot()
    assert s["class"] == cls and s["level"] == 2 and s["character"] == "Quill"


def test_base_classes_include_duelist_and_shadow():
    assert {"Duelist", "Shadow"} <= set(charjson.BASE_CLASSES)


@pytest.mark.parametrize("cls", ["Duelist", "Shadow", "Unknown Ascendancy"])
def test_pob_export_passes_new_classes_through(cls):
    xml = charjson.to_xml({"class": cls, "level": 12})
    assert f'className="{cls}"' in xml and 'ascendClassName="None"' in xml


def test_a_10_shaped_session_folds_without_errors():
    lines = [G("G5_1", 45), L("[SCENE] Set Source [Sunken Conqueror Hold]"),
             L(": Quill (Shadow) is now level 46"),
             L(": The Conqueror of Wraeclast stirs."),  # unknown system line
             L("Some new 1.0 debug line nobody has seen", tag="DEBUG"),
             G("G6_town", 55), L("[SCENE] Set Source [Unknown Camp]"),
             L(": Quill has been slain."),
             G("MapConquerorKeep", 75), L("[SCENE] Set Source [Conqueror Keep]")]
    st = SessionState(clock=lambda: 500.0)
    t = 100.0
    for line in lines:
        ev = parser.parse_line(line)
        if ev is not None:
            t += 10
            st.apply(dict(ev, recv_ts=t))
    s = st.snapshot()
    assert [r["key"] for r in s["acts"]["splits"]] == ["G5", "G6"]
    assert s["acts"]["finished"] is True
    assert s["maps"]["current"]["name"] == "Conqueror Keep"
    assert s["death_recap"]["recent"][0]["text"].startswith("Died in Unknown Camp")
    assert s["class"] == "Shadow" and s["deaths"] == 1
    json.dumps(s)  # the snapshot stays plain JSON


# -- league rollover for the trade link and the price card label ------------

def _core(tmp_path, cfg):
    p = tmp_path / "local.json"
    p.write_text(json.dumps(cfg), encoding="ascii")
    return Core(runtime=tmp_path / "rt", tail=False, config_path=p,
                web_fetch=lambda *a: (500, {}, b""))


def test_trade_league_follows_the_cached_ninja_league_only_with_web_data(tmp_path):
    core = _core(tmp_path, {"web_data": True})
    try:
        core.rates.doc["league"] = "Conquerors of Wraeclast"
        assert core.trade_league() == "Conquerors of Wraeclast"
        core.set_web_data(False)
        assert core.trade_league() is None
    finally:
        core.close()


def test_a_configured_league_wins_and_labels_the_card(tmp_path):
    core = _core(tmp_path, {"web_data": True, "league": "Standard"})
    try:
        core.rates.doc["league"] = "Conquerors of Wraeclast"
        assert core.trade_league() == "Standard"
    finally:
        core.close()


UNIQUE_TEXT = "\n".join(["Item Class: Rings", "Rarity: Rare", "Doom Loop",
                         "Example Ring", "--------", "Item Level: 70"])


def test_press_card_uses_the_rollover_league(tmp_path):
    core = _core(tmp_path, {"web_data": True})
    try:
        core.rates.doc["league"] = "Conquerors of Wraeclast"
        core.eval_press(UNIQUE_TEXT)
        card = core.state.snapshot()["price"]
        assert card["league"] == "Conquerors of Wraeclast"
        assert "/trade2/search/poe2/Conquerors%20of%20Wraeclast?" in card["url"]
    finally:
        core.close()
