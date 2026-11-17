"""AREA-AUDIT pass 4 regression tests (docs/audit/2026-11-17-audit.md,
"Pass 4"). Synthetic fixtures, a fake calc, a fake socket guard; no game,
no network."""

from server.al.theorycraft import evaluate as tc_evaluate
from server.al.theorycraft import lootfilter, model
from test_math_compare import ONE_HAND, _weapons_xml

# Real PoE2 shield / buckler bases whose names carry none of the words
# shield, buckler, focus, quiver (repoe-fork base_items snapshot fetched
# 2026-11-17: 47 Shield bases and 1 Buckler base; the Targe family and
# three named bases, each also in a Runeforged / Runemastered form).
WORDLESS_OFF_HANDS = ("Hardwood Targe", "Runeforged Golden Targe", "Glacial Fortress",
                      "Runemastered Glacial Fortress", "Golden Flame",
                      "Venerable Defender", "Runemastered Venerable Defender")


def test_p4_1_wordless_shield_bases_are_never_a_second_weapon():
    # Decision 0032: a shield build must never get a "replace your shield"
    # weapon comparison. A Targe (or Glacial Fortress, Golden Flame,
    # Venerable Defender) has no off-hand word in its name.
    for base in WORDLESS_OFF_HANDS:
        b = model.parse(_weapons_xml(base))
        assert tc_evaluate.slots_for_build(ONE_HAND, b) == ("Weapon 1",), base
        r = tc_evaluate.evaluate(ONE_HAND, b)
        assert [c["slot"] for c in r["comparisons"]] == ["Weapon 1"], base


def test_p4_1_a_magic_targe_name_line_is_still_an_off_hand():
    b = model.parse(_weapons_xml("Sturdy Hardwood Targe of the Fox"))
    assert tc_evaluate.slots_for_build(ONE_HAND, b) == ("Weapon 1",)


def test_p4_1_dual_wield_still_detected():
    b = model.parse(_weapons_xml("Example Dagger", "Adds 1 to 2 Lightning Damage to Attacks"))
    assert tc_evaluate.slots_for_build(ONE_HAND, b) == ("Weapon 1", "Weapon 2")


def test_p4_2_stackables_are_checked_against_the_cached_base_list():
    # The cached base_items list holds stackables too (StackableCurrency,
    # Omen, SoulCore ...). A name the game data does not list would make
    # the player's whole filter fail to load, so it is left out.
    prices = {"uniques": [],
              "stackables": [{"name": "Divine Orb", "value": 1.0},
                             {"name": "Made Up Shard", "value": 2.0},
                             {"name": "Omen of Light", "value": 0.2}]}
    names = {"divine orb": "Divine Orb", "omen of light": "Omen of Light"}
    t = lootfilter.tiers(prices, names)
    assert t["stack_top"] == ["Divine Orb"]
    assert t["stack_pick"] == ["Omen of Light"]
    text = lootfilter.generate(None, names, prices)
    assert "Made Up Shard" not in text
    # with no cached list nothing can be checked: kept as before
    assert "Made Up Shard" in lootfilter.tiers(prices)["stack_top"]
