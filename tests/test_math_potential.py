"""MATH-POTENTIAL: roll ranges kept per value and the item's roll potential."""

import json
import random

from server.al.theorycraft import evaluate as tc_evaluate
from server.al.theorycraft import item as item_mod
from server.al.theorycraft import live
from server.al.theorycraft import potential as pot

ADV_RING = """Item Class: Rings
Rarity: Rare
Doom Loop
Iron Ring
--------
Item Level: 80
--------
{ Implicit Modifier }
+8(6-10)% to Cold Resistance (implicit)
--------
{ Prefix Modifier "Hale" (Tier: 3) }
+90(80-99) to maximum Life
{ Suffix Modifier "of the Kiln" (Tier: 2) }
-15(-20--10)% to Fire Resistance
{ Suffix Modifier "of Haste" (Tier: 1) }
15(10-20)% reduced Charges per use
{ Prefix Modifier "Heavy" }
Adds 5(4-6) to 12(10-14) Physical Damage
{ Suffix Modifier "of Skill" }
+10 to Dexterity
"""


def _mods():
    return {m.text: m for m in item_mod.parse(ADV_RING, names={}).mods}


def test_ranges_aligned_with_values():
    m = _mods()
    assert m["+90 to maximum Life"].ranges == ((80, 99),)
    assert m["-15% to Fire Resistance"].ranges == ((-20, -10),)
    assert m["Adds 5 to 12 Physical Damage"].ranges == ((4, 6), (10, 14))
    assert m["+10 to Dexterity"].ranges == (None,)
    assert m["+8% to Cold Resistance"].ranges == ((6, 10),)
    d = m["+90 to maximum Life"].to_dict()
    assert d["ranges"] == [[80, 99]] and json.dumps(d)


def test_pob_bare_range_and_plain_text():
    text = ("Item Class: Rings\nRarity: Unique\nX\nIron Ring\n--------\n"
            "{range:0.25}+(40-60) to Strength\n+5 to Intelligence\n")
    m = {x.text: x for x in item_mod.parse(text, names={}).mods}
    assert m["+45 to Strength"].values == (45,)
    assert m["+45 to Strength"].ranges == ((40, 60),)
    assert m["+5 to Intelligence"].ranges == (None,)
    assert item_mod.roll_ranges("no numbers") == ()
    assert item_mod.roll_ranges("+1.5(1-2.5)% x") == ((1, 2.5),)


def test_roll_pct():
    assert pot.roll_pct(90, (80, 100)) == 50
    assert pot.roll_pct(-15, (-20, -10)) == 50
    assert pot.roll_pct(5, (5, 5)) == 100
    assert pot.roll_pct(200, (80, 100)) == 100  # clamped
    assert pot.roll_pct(1, None) is None
    assert pot.roll_pct(float("nan"), (1, 2)) is None
    assert pot.roll_pct(1, (float("inf"), 2)) is None


def test_mod_potential_signs_and_reduced():
    m = _mods()
    life = pot.mod_potential(m["+90 to maximum Life"])
    assert (life["key"], life["value"], life["low"], life["high"]) == \
        ("+# to maximum Life", 90, 80, 99)
    fire = pot.mod_potential(m["-15% to Fire Resistance"])
    assert (fire["value"], fire["low"], fire["high"]) == (-15, -20, -10)
    red = pot.mod_potential(m["15% reduced Charges per use"])
    # "reduced" reads negative: the low end is -10, the high end -20
    assert (red["key"], red["value"], red["low"], red["high"]) == \
        ("#% increased Charges per use", -15, -10, -20)
    adds = pot.mod_potential(m["Adds 5 to 12 Physical Damage"])
    assert (adds["value"], adds["low"], adds["high"]) == (8.5, 7, 10)
    assert pot.mod_potential(m["+10 to Dexterity"]) is None


def test_item_potential_weighted():
    parsed = item_mod.parse(ADV_RING, names={})
    w = {"+# to maximum Life": 1.0, "+#% to Fire Resistance": 2.0,
         "#% increased Charges per use": 1.0, "+# to Dexterity": 0.5,
         "+#% to Cold Resistance": 1.0}
    p = pot.item_potential(parsed, w)
    # life 90 (80..99), fire -30 (-40..-20), charges -15 (-20..-10 best),
    # dex 5 fixed, cold 8 (6..10); adds unweighted (0)
    assert p["score"] == 90 - 30 - 15 + 5 + 8
    assert p["worst"] == 80 - 40 - 20 + 5 + 6
    assert p["best"] == 99 - 20 - 10 + 5 + 10
    assert p["pct"] == round((58 - 31) / (84 - 31) * 100, 4)
    assert {r["key"] for r in p["mods"]} >= {"+# to maximum Life"}
    assert all(r["weighted"] is (r["weight"] != 0) for r in p["mods"])
    # a negative weight flips which end is best
    p2 = pot.item_potential(parsed, {"+# to maximum Life": -1.0})
    assert p2["best"] == -80 and p2["worst"] == -99


def test_no_ranges_no_potential():
    plain = "Item Class: Rings\nRarity: Rare\nA\nIron Ring\n--------\n+20 to maximum Life\n"
    assert pot.item_potential(item_mod.parse(plain, names={})) is None
    assert pot.item_potential(None) is None


def test_evaluate_and_compact_carry_potential():
    r = tc_evaluate.evaluate(ADV_RING, None, None)
    assert r["potential"]["score"] == r["potential"]["score"]
    assert 0 <= r["potential"]["pct"] <= 100
    c = live.compact(r)
    assert set(c["potential"]) == {"score", "worst", "best", "pct"}
    json.dumps(c, allow_nan=False)
    assert tc_evaluate.evaluate("junk", None, None)["potential"] is None
    assert live.compact({})["potential"] is None


def test_property_random_ranged_lines():
    rng = random.Random(77)
    for _ in range(1500):
        a, b = sorted(rng.randint(-50, 200) for _ in range(2))
        v = rng.randint(a, b)
        sign = "+" if v >= 0 else ""
        word = rng.choice(["to maximum Life", "% increased Armour", "% reduced Mana Cost"])
        line = f"{sign}{v}({a}-{b}){word}" if "%" in word else f"{sign}{v}({a}-{b}) {word}"
        text = f"Item Class: Rings\nRarity: Rare\nA\nIron Ring\n--------\n{line}\n"
        parsed = item_mod.parse(text, names={})
        assert len(parsed.mods) == 1
        m = parsed.mods[0]
        assert len(m.ranges) == len(m.values)
        p = pot.item_potential(parsed, {"+# to maximum Life": 1, "#% increased Armour": 1,
                                        "#% increased Mana Cost": -1})
        if p is not None:
            assert p["worst"] <= p["score"] <= p["best"]
            assert 0 <= p["pct"] <= 100
            json.dumps(p, allow_nan=False)
