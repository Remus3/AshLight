"""MATH-COMPARE: the item check card names the equipped item a swap
replaces and Path of Building's DPS / EHP delta of that swap, including the
two-slot cases (rings; a one-hand weapon in either hand of a dual wielder),
where the better slot is the headline and the other slot keeps its own
PoB line (decision 0032). Synthetic fixtures and a fake calc only."""

from server.al.state import eval_card_text
from server.al.theorycraft import evaluate as tc_evaluate
from server.al.theorycraft import live, model
from tc_eval_fixtures import ADVANCED_RING, EVAL_BUILD_XML, RARE_GLOVES
from test_tc_delta import FakeCalc, _Builds, _State, _Weights

ONE_HAND = """Item Class: Wands
Rarity: Rare
Spark Twig
Example Wand
--------
Item Level: 70
--------
Adds 1 to 30 Lightning Damage to Attacks
10% increased Attack Speed
"""

BOW = """Item Class: Bows
Rarity: Rare
Long Reach
Example Bow
--------
Item Level: 70
--------
20% increased Attack Speed
"""


def _weapons_xml(off_hand_base, off_hand_mod="+10 to maximum Life"):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<PathOfBuilding2>
\t<Build level="80" className="Ranger" ascendClassName="None"/>
\t<Items activeItemSet="1">
\t\t<Item id="1">
Rarity: RARE
Main Twig
Example Wand
Item Level: 70
Implicits: 0
Adds 1 to 10 Lightning Damage to Attacks
</Item>
\t\t<Item id="2">
Rarity: RARE
Off Thing
{off_hand_base}
Item Level: 70
Implicits: 0
{off_hand_mod}
</Item>
\t\t<ItemSet id="1">
\t\t\t<Slot name="Weapon 1" itemId="1"/>
\t\t\t<Slot name="Weapon 2" itemId="2"/>
\t\t</ItemSet>
\t</Items>
</PathOfBuilding2>
"""


def _card(text, build, calc=None):
    st = _State()
    live.LastEval(_Builds(build), _Weights(), st,
                  calc=(lambda: calc) if calc is not None else None).run(text)
    return st.eval


# -- slots -------------------------------------------------------------------

def test_one_hand_weapon_compares_both_hands_of_a_dual_wielder():
    b = model.parse(_weapons_xml("Example Dagger", "Adds 1 to 2 Lightning Damage to Attacks"))
    assert tc_evaluate.slots_for_build(ONE_HAND, b) == ("Weapon 1", "Weapon 2")
    r = tc_evaluate.evaluate(ONE_HAND, b, calc=FakeCalc())
    assert [c["slot"] for c in r["comparisons"]] == ["Weapon 1", "Weapon 2"]
    # Weapon 2 holds the weaker weapon, so the swap there gains more DPS
    assert r["slot"] == "Weapon 2"
    best = max(r["comparisons"], key=lambda c: c["score_delta"])
    assert best["slot"] == r["slot"]


def test_one_hand_weapon_never_compares_a_shield_quiver_or_focus():
    for base in ("Example Tower Shield", "Wooden Buckler", "Twig Focus", "Fire Quiver"):
        b = model.parse(_weapons_xml(base))
        assert tc_evaluate.slots_for_build(ONE_HAND, b) == ("Weapon 1",), base
        r = tc_evaluate.evaluate(ONE_HAND, b)
        assert [c["slot"] for c in r["comparisons"]] == ["Weapon 1"]


def test_one_hand_weapon_with_an_empty_off_hand_and_two_hand_weapon():
    xml = _weapons_xml("Example Dagger").replace('\t\t\t<Slot name="Weapon 2" itemId="2"/>\n', "")
    b = model.parse(xml)
    assert tc_evaluate.slots_for_build(ONE_HAND, b) == ("Weapon 1",)
    dual = model.parse(_weapons_xml("Example Dagger"))
    # a two-hand weapon only ever goes in Weapon 1
    assert tc_evaluate.slots_for_build(BOW, dual) == ("Weapon 1",)
    assert tc_evaluate.slots_for_build(ONE_HAND, None) == ("Weapon 1",)


def test_explicit_slot_still_wins():
    b = model.parse(_weapons_xml("Example Dagger"))
    r = tc_evaluate.evaluate(ONE_HAND, b, slot="Weapon 1")
    assert [c["slot"] for c in r["comparisons"]] == ["Weapon 1"]


# -- card text ---------------------------------------------------------------

def test_card_names_the_replaced_item_and_the_swap_delta():
    t = eval_card_text(_card(RARE_GLOVES, model.parse(EVAL_BUILD_XML), FakeCalc()))
    assert t["calc"] == ("Path of Building: this item in Gloves replaces Old Grip. "
                         "DPS -36% (from 100 to 64). EHP +12.7% (from 4720 to 5320).")
    assert t["line"] == "DPS -36%, EHP +12.7%"
    assert t["comparisons"][0]["calc"] == "Path of Building: DPS -36%, EHP +12.7%."


def test_card_two_rings_headline_is_the_better_slot_and_other_slot_has_its_line():
    card = _card(ADVANCED_RING, model.parse(EVAL_BUILD_XML), FakeCalc())
    t = eval_card_text(card)
    assert card["slot"] == "Ring 1"
    assert t["calc"].startswith("Path of Building: this item in Ring 1 replaces "
                                "Weak Loop (the better of the 2 slots it fits). DPS ")
    other = next(c for c in t["comparisons"] if c["slot"] == "Ring 2")
    assert other["calc"].startswith("Path of Building: DPS ")
    assert "EHP " in other["calc"]


def test_card_empty_slot_wording():
    b = model.parse(EVAL_BUILD_XML.replace('\t\t\t<Slot name="Gloves" itemId="1"/>\n', ""))
    t = eval_card_text(_card(RARE_GLOVES, b, FakeCalc()))
    assert t["calc"].startswith("Path of Building: this item goes in the empty Gloves "
                                "slot. DPS ")
    nameless = dict(_card(RARE_GLOVES, b, FakeCalc()))
    nameless["comparisons"] = [dict(nameless["comparisons"][0], slot=None)]
    nameless["slot"] = None
    assert "goes in the empty slot. DPS " in eval_card_text(nameless)["calc"]


def test_card_without_calc_has_no_per_slot_pob_line():
    t = eval_card_text(_card(ADVANCED_RING, model.parse(EVAL_BUILD_XML)))
    assert all(c["calc"] == "" for c in t["comparisons"])
