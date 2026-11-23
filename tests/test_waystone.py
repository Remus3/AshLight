"""UTIL-WAYSTONE (decision 0030): waystone parse, rule table and card text.

Waystone texts are hand-written in the PoE2 Ctrl+C shape (research 0003);
names and values are invented. Mod wording follows the real waystone mod
pool (repoe-fork mods snapshot, checked 2026-11-17 by AREA-UTIL b6); each
line is our own sanitized fixture, not copied data."""

import re

from server.al.state import SessionState, eval_card_text, waystone_text
from server.al.text.common import CARD_LINE
from server.al.theorycraft import live, waystone
from server.al.theorycraft.model import Build

WAYSTONE = """Item Class: Waystones
Rarity: Rare
Doom Trail
Waystone (Tier 15)
--------
Waystone Tier: 15
Revives Available: 0
Monster Pack Size: +12% (augmented)
Item Rarity: +38% (augmented)
--------
Item Level: 79
--------
Monsters deal 28(20-30)% of Damage as Extra Fire
Players have 40% less Recovery Rate of Life and Energy Shield
Monsters have 210% increased Critical Hit Chance
Area has patches of Chilled Ground
Monsters take 22% reduced Extra Damage from Critical Hits
--------
Can be used in a Map Device, allowing you to enter a Map. Waystones can only be used once.
"""

CALM = """Item Class: Waystones
Rarity: Magic
Waystone (Tier 3)
--------
Waystone Tier: 3
--------
Item Level: 66
--------
Monsters have 40% increased Stun Threshold
"""

UNID = """Item Class: Waystones
Rarity: Rare
Waystone (Tier 9)
--------
Waystone Tier: 9
--------
Item Level: 72
--------
Unidentified
"""

LIFE_BUILD = Build(raw_xml="", stats={"Life": 4000, "EnergyShield": 200, "FireResist": 60,
                                      "ColdResist": 75, "LightningResist": 75,
                                      "ChaosResist": -10})
ES_BUILD = Build(raw_xml="", stats={"Life": 1000, "EnergyShield": 5000, "FireResist": 75,
                                    "ColdResist": 40, "LightningResist": 75,
                                    "ChaosResist": 20})


def ids(res):
    return [r["id"] for r in res["risky"]]


def test_not_a_waystone_is_none():
    assert waystone.check("Item Class: Rings\nRarity: Rare\nA\nRuby Ring\n", None) is None
    assert waystone.check("", None) is None
    assert waystone.check(None, None) is None


def test_mod_lines_skip_properties_and_help_text():
    mods = waystone.mod_lines(WAYSTONE)
    assert mods == ["Monsters deal 28% of Damage as Extra Fire",
                    "Players have 40% less Recovery Rate of Life and Energy Shield",
                    "Monsters have 210% increased Critical Hit Chance",
                    "Area has patches of Chilled Ground",
                    "Monsters take 22% reduced Extra Damage from Critical Hits"]


def test_life_build_flags_fire_recovery_crit_not_cold_ground():
    res = waystone.check(WAYSTONE, LIFE_BUILD)
    assert res["tier"] == 15 and res["item_level"] == 79 and res["build_loaded"]
    assert ids(res) == ["extra_element", "less_recovery", "monster_crit"]
    assert res["risky"][0]["label"] == "extra fire damage (fire resistance 60%)"
    assert res["risky"][0]["short"] == "Extra fire dmg"


def test_es_build_flags_cold_ground_and_recovery_not_fire():
    res = waystone.check(WAYSTONE, ES_BUILD)
    assert ids(res) == ["less_recovery", "monster_crit", "ground"]
    assert res["risky"][2]["label"] == "cold ground (cold resistance 40%)"


def test_reduced_crit_damage_taken_is_not_monster_crit():
    # b5 matched "monsters ... critical hits" and flagged this player-side
    # mod; the snapshot check found it (AREA-UTIL b6).
    text = CALM.replace("Monsters have 40% increased Stun Threshold",
                        "Monsters take 22% reduced Extra Damage from Critical Hits")
    assert ids(waystone.check(text, Build(raw_xml="", stats={}))) == []


def test_no_build_flags_everything_that_depends_on_it():
    res = waystone.check(WAYSTONE, None)
    assert not res["build_loaded"]
    assert ids(res) == ["extra_element", "less_recovery", "monster_crit", "ground"]
    assert res["risky"][0]["label"] == "extra fire damage (fire resistance unknown)"


def test_rule_table_shape_and_samples():
    sample = {
        "extra_element": "Monsters deal 17% of Damage as Extra Lightning",
        "ground": "Area has patches of Shocked Ground",
        "max_res": "-7% maximum Player Resistances",
        "penetration": "Monster Damage Penetrates 10% Elemental Resistances",
        "less_recovery": "Players have 32% less Recovery Rate of Life and Energy Shield",
        "monster_crit": "Monsters have +18% Critical Damage Bonus",
        "speed": "Monsters have 12% increased Attack, Cast and Movement Speed",
        "poison": "Monsters have 22% chance to Poison on Hit",
        "bleed": "Monsters have 12% chance to inflict Bleeding on Hit",
        "ailments": "Monster have 90% increased Elemental Ailment Application",
        "flasks": "Players gain 27% reduced Flask Charges",
    }
    seen = set()
    for rule in waystone.RULES:
        assert set(rule) >= {"id", "short", "match", "when", "label", "avoid"}
        assert rule["id"] not in seen
        seen.add(rule["id"])
        assert len(rule["short"].format(el="lightning", El="Lightning")) <= 20
        assert re.search(rule["match"], sample[rule["id"]].lower()), rule["id"]
    assert seen == set(sample)
    blank = Build(raw_xml="", stats={})
    for rid, line in sample.items():
        text = CALM.replace("Monsters have 40% increased Stun Threshold", line)
        assert ids(waystone.check(text, blank)) == [rid], rid


def test_unidentified_and_corrupted():
    res = waystone.check(UNID, LIFE_BUILD)
    assert res["unidentified"] and res["risky"] == [] and res["tier"] == 9
    res = waystone.check(CALM + "--------\nCorrupted\n", LIFE_BUILD)
    assert res["corrupted"] and res["risky"] == []


def test_card_text_exact():
    t = waystone_text(waystone.check(WAYSTONE, LIFE_BUILD))
    assert t["head"] == "Risky for this build"
    assert t["line"] == "Extra fire dmg +2 more"
    assert t["sentence"] == ("Tier 15 waystone. Risky for this build: extra fire damage "
                             "(fire resistance 60%), less life and energy shield recovery, "
                             "monster critical hits.")
    t = waystone_text(waystone.check(CALM, LIFE_BUILD))
    assert (t["head"], t["line"]) == ("No risky mods found", "Tier 3 waystone")
    assert t["sentence"] == "Tier 3 waystone. None of its mods look risky for this build."
    t = waystone_text(waystone.check(CALM, None))
    assert t["line"] == "No build loaded"
    t = waystone_text(waystone.check(WAYSTONE, None))
    assert t["head"] == "Risky waystone"
    assert t["sentence"].startswith("Tier 15 waystone. Risky mods (no build loaded, so "
                                    "resistances are unknown): extra fire damage")
    t = waystone_text(waystone.check(UNID, None))
    assert t["head"] == "Waystone unidentified"
    for w in (WAYSTONE, CALM, UNID):
        for b in (None, LIFE_BUILD, ES_BUILD):
            t = waystone_text(waystone.check(w, b))
            assert len(t["head"]) <= CARD_LINE and len(t["line"]) <= CARD_LINE, t
            assert "None" not in t["sentence"].replace("None of", "")
    assert waystone_text({})["head"] == "No risky mods found"


def test_eval_card_carries_the_waystone_verdict():
    card = live.compact({"ok": False, "error": "no gear slot for this item class",
                         "item": {"name": "Doom Trail", "base": "Waystone (Tier 15)"}})
    card["waystone"] = waystone.check(WAYSTONE, LIFE_BUILD)
    t = eval_card_text(card)
    assert t["head"] == "Risky for this build" and t["item"] == "Doom Trail"
    st = SessionState(clock=lambda: 100.0)
    st.set_eval(card)
    snap = st.snapshot()
    assert snap["card"]["head"] == "Risky for this build"
    assert snap["card"]["line3"] == "Extra fire dmg +2 more"


class _Builds:
    def __init__(self, build):
        self.build = build


class _Weights:
    def get(self):
        return None


def test_last_eval_adds_waystone_on_the_same_press():
    st = SessionState(clock=lambda: 100.0)
    last = live.LastEval(_Builds(ES_BUILD), _Weights(), st)
    last.run(WAYSTONE)
    ev = st.snapshot()["eval"]
    assert [r["id"] for r in ev["waystone"]["risky"]] == ["less_recovery", "monster_crit",
                                                          "ground"]
    last.run("Item Class: Rings\nRarity: Rare\nA\nRuby Ring\n--------\n+10 to maximum Life\n")
    assert st.snapshot()["eval"]["waystone"] is None


def test_avoid_terms_follow_the_build():
    life = waystone.avoid_terms(LIFE_BUILD)
    assert "extra fire" in life and "extra cold" not in life and "to poison" in life
    assert "rate of life" in life and "critical damage bonus" in life
    es = waystone.avoid_terms(ES_BUILD)
    assert "extra cold" in es and "chilled ground" in es and "to poison" not in es
    assert "ignited ground" not in es and "burning ground" not in es
