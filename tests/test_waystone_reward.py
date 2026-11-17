"""UTIL-WAYSTONE-REWARD (research 0031 4.3): reward totals on the waystone
press. Texts are hand-written in the PoE2 Ctrl+C shape; the reward property
names match the hidden "_from_map" reward stats of the repoe-fork mods
snapshot (checked 2026-11-17); names and values are invented."""

from server.al.state import SessionState, eval_card_text, waystone_text
from server.al.theorycraft import item as item_parser
from server.al.theorycraft import live, waystone
from tests.test_waystone import CALM, LIFE_BUILD, UNID, WAYSTONE

RICH = """Item Class: Waystones
Rarity: Rare
Gloom Spiral
Waystone (Tier 16)
--------
Waystone Tier: 16
Revives Available: 0
Item Quantity: +12% (augmented)
Item Rarity: +38% (augmented)
Waystone Drop Chance: +120% (augmented)
Monster Pack Size: +20% (augmented)
Magic Monsters: +30% (augmented)
Rare Monsters: +25% (augmented)
--------
Item Level: 80
--------
Monsters deal 22% of Damage as Extra Cold
Monsters have 30% increased Stun Threshold
--------
Corrupted
"""


def rew(text):
    return {r["id"]: r["pct"] for r in waystone.check(text, LIFE_BUILD)["rewards"]}


def test_several_reward_properties_are_summed_in_order():
    res = waystone.check(RICH, LIFE_BUILD)
    assert [r["id"] for r in res["rewards"]] == ["quantity", "rarity", "pack", "magic",
                                                 "rare", "waystones"]
    assert rew(RICH) == {"quantity": 12, "rarity": 38, "pack": 20, "magic": 30, "rare": 25,
                         "waystones": 120}
    assert res["corrupted"]


def test_reward_mod_lines_add_to_the_property_total():
    text = WAYSTONE.replace("Monsters take 22% reduced Extra Damage from Critical Hits",
                            "10% increased Rarity of Items found in this Area")
    assert rew(text) == {"rarity": 48, "pack": 12}


def test_no_rewards_and_unidentified():
    assert rew(CALM) == {}
    res = waystone.check(UNID, LIFE_BUILD)
    assert res["unidentified"] and res["rewards"] == []
    shown = UNID.replace("Waystone Tier: 9\n", "Waystone Tier: 9\nItem Rarity: +10%\n")
    assert rew(shown) == {"rarity": 10}


def test_bad_values_read_as_no_reward():
    p = item_parser.parse(CALM)
    p.properties.update({"Item Rarity": "lots", "Monster Pack Size": "+99999%",
                         "Rare Monsters": "+0%", "Magic Monsters": None})
    assert waystone.rewards(p, ["abc", "5% increased Pack size"]) == [
        {"id": "pack", "label": "pack size", "short": "pack", "pct": 5}]
    assert waystone.rewards(None, None) == []


def test_reward_text_exact():
    t = waystone_text(waystone.check(RICH, LIFE_BUILD))
    assert t["rewards"] == ("Rewards: +12% item quantity, +38% item rarity, +20% pack size, "
                            "+30% magic monsters, +25% rare monsters, +120% waystone drops.")
    assert t["reward_line"] == "+12% quantity, +38% rarity +4 more"
    t = waystone_text(waystone.check(WAYSTONE, LIFE_BUILD))
    assert t["rewards"] == "Rewards: +38% item rarity, +12% pack size."
    assert t["reward_line"] == "+38% rarity, +12% pack"
    t = waystone_text(waystone.check(CALM, LIFE_BUILD))
    assert t["rewards"] == "Rewards: none found in the item text."
    assert t["reward_line"] == ""
    t = waystone_text(waystone.check(UNID, LIFE_BUILD))
    assert t["rewards"] == "Rewards: identify it to see them."
    assert t["reward_line"] == ""
    t = waystone_text({"rewards": [{"label": "item rarity", "short": "rarity", "pct": -20}]})
    assert t["rewards"] == "Rewards: -20% item rarity."
    assert waystone_text({})["rewards"] == "Rewards: none found in the item text."
    for w in (RICH, WAYSTONE, CALM, UNID):
        assert len(waystone_text(waystone.check(w, None))["reward_line"]) <= 34


def test_overlay_card_shows_rewards_in_the_item_line():
    card = live.compact({"ok": False, "error": "no gear slot for this item class",
                         "item": {"name": "Doom Trail", "base": "Waystone (Tier 15)"}})
    card["waystone"] = waystone.check(WAYSTONE, LIFE_BUILD)
    t = eval_card_text(card)
    assert t["item"] == "Doom Trail" and t["rewards"].startswith("Rewards: +38%")
    st = SessionState(clock=lambda: 100.0)
    st.set_eval(card)
    c = st.snapshot()["card"]
    assert (c["head"], c["line2"], c["line3"]) == ("Risky for this build",
                                                   "+38% rarity, +12% pack",
                                                   "Extra fire dmg +2 more")
    card["waystone"] = waystone.check(CALM, LIFE_BUILD)
    st.set_eval(card)
    assert st.snapshot()["card"]["line2"] == "Doom Trail"
