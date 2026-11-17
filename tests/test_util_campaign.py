"""UTIL-CAMPAIGN-CHECKS (research 0031 4.4, ruling H, decision 0039).

A synthetic base_items snapshot in tmp_path (names in the shape of the
repoe-fork export, levels invented), a hand-made build and synthetic log
events; no real snapshot data is copied here."""

import json

from server.al import campaign, settingsio
from server.al.state import SessionState
from server.al.theorycraft import live
from server.al.theorycraft.model import Build, Item

SNAP = {
    "Metadata/Items/Flasks/L1": {"name": "Small Life Flask", "item_class": "LifeFlask",
                                 "drop_level": 1, "release_state": "released"},
    "Metadata/Items/Flasks/L2": {"name": "Big Life Flask", "item_class": "LifeFlask",
                                 "drop_level": 10, "release_state": "released"},
    "Metadata/Items/Flasks/L3": {"name": "Huge Life Flask", "item_class": "LifeFlask",
                                 "drop_level": 20, "release_state": "released"},
    "Metadata/Items/Flasks/L9": {"name": "Secret Life Flask", "item_class": "LifeFlask",
                                 "drop_level": 2, "release_state": "unreleased"},
    "Metadata/Items/Flasks/M1": {"name": "Small Mana Flask", "item_class": "ManaFlask",
                                 "drop_level": 1, "release_state": "released"},
    "Metadata/Items/Flasks/M2": {"name": "Ultimate Mana Flask", "item_class": "ManaFlask",
                                 "drop_level": 60, "release_state": "released"},
    "Metadata/Items/Armours/B1": {"name": "Plain Boots", "item_class": "Boots",
                                  "drop_level": 1},
}


def table(tmp_path):
    p = tmp_path / "base_items.json"
    p.write_text(json.dumps(SNAP), encoding="utf-8")
    return campaign.load_flasks(p)


def make_build(life="Small Life Flask", mana="Small Mana Flask", boots_text="Plain Boots",
               cold=32):
    gear = {}
    if life:
        gear["Flask 1"] = Item(id=1, text=f"Rarity: NORMAL\n{life}", rarity="NORMAL", base=life)
    if mana:
        gear["Flask 2"] = Item(id=2, text=f"Rarity: NORMAL\n{mana}", rarity="NORMAL", base=mana)
    if boots_text is not None:
        gear["Boots"] = Item(id=3, text=f"Rarity: MAGIC\n{boots_text}", rarity="MAGIC",
                             base="Plain Boots")
    stats = {"FireResist": -10, "LightningResist": 75, "ChaosResist": 0}
    if cold is not None:
        stats["ColdResist"] = cold
    return Build(raw_xml="", stats=stats, gear=gear)


def test_load_flasks_reads_released_flasks_only(tmp_path):
    t = table(tmp_path)
    assert t == {"life": [(1, "Small Life Flask"), (10, "Big Life Flask"),
                          (20, "Huge Life Flask")],
                 "mana": [(1, "Small Mana Flask"), (60, "Ultimate Mana Flask")]}
    assert campaign.load_flasks(tmp_path / "missing.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("[1, 2", encoding="utf-8")
    assert campaign.load_flasks(bad) == {}


def test_build_facts():
    f = campaign.build_facts(make_build())
    assert f["flasks"] == ["Small Life Flask", "Small Mana Flask"]
    assert f["boots"] == {"speed": False}
    assert f["res"]["cold"] == 32 and f["res"]["fire"] == -10
    fast = campaign.build_facts(make_build(boots_text="Plain Boots\n15% increased Movement Speed"))
    assert fast["boots"] == {"speed": True}
    assert campaign.build_facts(make_build(boots_text=None))["boots"] is None
    assert campaign.build_facts(None) is None


def test_flask_upgrade_shown_and_not_shown(tmp_path):
    t = table(tmp_path)
    facts = campaign.build_facts(make_build())
    v = campaign.view(12, "G1_5", facts, t)
    assert v["hints"][0] == {"id": "flask-life", "word": "Better flask",
                             "text": "A Big Life Flask can drop at your level; your build "
                                     "has a Small Life Flask."}
    assert v["word"] == "Better flask"
    hi = campaign.view(60, "G1_5", campaign.build_facts(make_build(boots_text=None)), t)
    assert hi["hints"][1]["text"] == ("An Ultimate Mana Flask can drop at your level; your "
                                      "build has a Small Mana Flask.")
    # already the best base for the level, or below the next tier's level
    assert campaign.view(9, "G1_5", facts, t) is None
    best = campaign.build_facts(make_build(life="Huge Life Flask"))
    assert campaign.view(30, "G1_5", best, t) is None or all(
        h["id"] != "flask-life" for h in campaign.view(30, "G1_5", best, t)["hints"])
    # an unknown base (a unique) or no snapshot gives nothing
    odd = campaign.build_facts(make_build(life="Odd Flask"))
    assert campaign.view(12, "G1_5", odd, t) is None
    assert campaign.view(12, "G1_5", facts, {}) is None


def test_boots_hint_from_the_level_setting(tmp_path):
    facts = campaign.build_facts(make_build(life=None, mana=None))
    assert campaign.view(15, "G1_5", facts) is None
    v = campaign.view(16, "G1_5", facts)
    assert v["hints"] == [{"id": "boots", "word": "Boots: no speed",
                           "text": "Your build's boots have no movement speed. Boots with "
                                   "it help in the campaign."}]
    assert campaign.view(16, "G1_5", facts, boots_level=20) is None
    assert campaign.view(16, "G1_5", facts, boots_level="junk")["word"] == "Boots: no speed"
    fast = campaign.build_facts(make_build(life=None, mana=None,
                                           boots_text="10% increased Movement Speed"))
    assert campaign.view(40, "G1_5", fast) is None


def test_boss_zone_line(tmp_path):
    facts = campaign.build_facts(make_build(life=None, mana=None, boots_text=None))
    v = campaign.view(15, "G1_15", facts)
    assert v["hints"] == [{"id": "boss", "word": "Cold res 32%",
                           "text": "This zone's boss deals mostly cold damage. Your build "
                                   "has 32% cold resistance (the cap is 75%)."}]
    v = campaign.view(30, "G2_10_2", facts)
    assert v["word"] == "Fire res -10%"
    capped = campaign.build_facts(make_build(life=None, mana=None, boots_text=None, cold=80))
    assert campaign.view(15, "G1_15", capped)["hints"][0]["text"].endswith(
        "has 80% cold resistance (at the cap).")
    unknown = campaign.build_facts(make_build(life=None, mana=None, boots_text=None, cold=None))
    v = campaign.view(15, "G1_15", unknown)
    assert v["word"] == "Boss: cold"
    assert v["hints"][0]["text"].endswith("Your build's cold resistance is unknown.")
    assert campaign.view(15, "G1_14", facts) is None
    assert campaign.view(15, "G1_15", {"res": {"cold": -100}})["word"] == "Cold res -100%"


def test_long_element_word_falls_back(monkeypatch):
    monkeypatch.setitem(campaign.BOSS_ZONES, "G9_1", "lightning")
    v = campaign.view(50, "G9_1", {"res": {"lightning": -100}})
    assert v["word"] == "Boss: lightning" and len(v["word"]) <= campaign.WORD_MAX


def test_unknown_level_no_build_and_endgame_give_nothing(tmp_path):
    t = table(tmp_path)
    facts = campaign.build_facts(make_build())
    assert campaign.view(None, "G1_15", facts, t) is None
    assert campaign.view(True, "G1_15", facts, t) is None
    assert campaign.view(20, "G1_15", None, t) is None
    assert campaign.view(70, "MapCrypt", facts, t) is None
    assert campaign.view(20, "HideoutCave", facts, t) is None
    assert campaign.view(20, None, facts, t) is None


def test_state_snapshot_and_live_wiring(tmp_path):
    st = SessionState(clock=lambda: 200.0)
    assert st.snapshot()["campaign"] is None
    assert st.set_campaign(flasks=table(tmp_path)) is True
    assert st.set_campaign(flasks=table(tmp_path)) is False

    class Builds:
        build = make_build()

        def add_listener(self, fn):
            self.fn = fn

    class Weights:
        def get(self):
            return None

    builds = Builds()
    live.attach(builds, Weights(), st)
    st.apply({"type": "level_up", "character": "Ash", "class": "Witch", "level": 15,
              "recv_ts": 50.0})
    st.apply({"type": "area_generated", "area_id": "G1_15", "area_level": 15, "seed": "1",
              "recv_ts": 100.0})
    v = st.snapshot()["campaign"]
    assert [h["id"] for h in v["hints"]] == ["boss", "flask-life"]
    builds.fn(None)  # build cleared: no hints
    assert st.snapshot()["campaign"] is None
    ver = st.version
    assert st.set_campaign(boots_level=30) is True and st.version == ver + 1
    assert st.boots_level == 30


def test_setting_is_importable():
    assert "boots_speed_level" in settingsio.ALLOWED
    assert settingsio.LABELS["boots_speed_level"] == "boots speed level"
