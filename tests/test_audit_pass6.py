"""AREA-AUDIT pass 6 regression tests.

P6-1 (medium): the PoB-PoE2 fallback (decision 0037 amendment) brings
"(Local)" trade ids next to the global ones ("#% increased Armour" vs
"#% increased Armour (Local)"). The upgrade link used the global id in
every slot, so a body armour / helmet / weapon search weighted a stat the
items in that slot never carry (their armour, evasion, energy shield,
attack speed, accuracy roll as the local stat). The slot now decides:
armour pieces take the local id of a defence stat, the main-hand weapon
the local id of the others, jewellery the global id, and a slot whose
locality is unknown (off hand, flasks, charms) gets no filter for a stat
that has a local twin (never a guess). Ids below are invented."""

from server.al import tradestats, upgrade

G_ES, L_ES = "explicit.stat_2000001", "explicit.stat_2000002"
G_AS, L_AS = "explicit.stat_2000003", "explicit.stat_2000004"
LIFE = "explicit.stat_2000005"

IDS = {
    tradestats.norm("# to maximum Energy Shield"): G_ES,
    tradestats.norm("# to maximum Energy Shield (Local)"): L_ES,
    tradestats.norm("#% increased Attack Speed"): G_AS,
    tradestats.norm("#% increased Attack Speed (Local)"): L_AS,
    tradestats.norm("# to maximum Life"): LIFE,
}
TOP = [{"key": "+# to maximum Energy Shield", "weight": 3},
       {"key": "#% increased Attack Speed", "weight": 2},
       {"key": "+# to maximum Life", "weight": 1}]


def _ids(slot):
    return [f["id"] for f in upgrade._filters(TOP, IDS, slot)]


def test_armour_slot_uses_local_defence_id_global_other():
    for slot in ("Helmet", "Body Armour", "Gloves", "Boots"):
        assert _ids(slot) == [L_ES, G_AS, LIFE], slot


def test_main_hand_uses_local_weapon_id_and_drops_defence():
    assert _ids("Weapon 1") == [L_AS, LIFE]


def test_jewellery_uses_global_ids():
    for slot in ("Amulet", "Ring 1", "Ring 2", "Belt"):
        assert _ids(slot) == [G_ES, G_AS, LIFE], slot


def test_unknown_locality_slot_drops_stats_with_a_local_twin():
    for slot in ("Weapon 2", "Flask 1", "Charm 1", None, "junk"):
        assert _ids(slot) == [LIFE], slot


def test_no_local_twin_keeps_the_only_id_everywhere():
    ids = {tradestats.norm("# to maximum Life"): LIFE}
    for slot in ("Weapon 1", "Weapon 2", "Body Armour", "Ring 1"):
        assert [f["id"] for f in upgrade._filters(TOP, ids, slot)] == [LIFE]


def test_link_passes_the_slot():
    """The upgrade link doc of a body armour check carries the local id."""
    result = {"ok": True, "slot": "Body Armour", "item": {"base": "Plate Vest"},
              "comparisons": [{"slot": "Body Armour", "equipped": {"base": "Plate Vest"},
                               "stats": [{"key": "+# to maximum Energy Shield",
                                          "weighted": True, "weight": 3}]}]}
    doc = upgrade.link(result, "Example League", IDS)
    assert [f["id"] for f in doc["filters"]] == [L_ES]


# P6-2 (low): an id with a trailing newline or non-ASCII digits is refused.
def test_id_with_newline_or_unicode_digits_refused():
    from server.al import trade
    assert tradestats.lookup({"x": "explicit.stat_1\n"}, "x") is None
    assert tradestats.build_index([{"trade_stats": [
        {"id": "explicit.stat_1\n", "text": "x", "type": "explicit"}]}]) == {}
    assert trade._weight_group([("explicit.stat_\u00b2", 1.0)]) is None
    assert trade._weight_group([("explicit.stat_12", 1.0)]) is not None


def test_real_pinned_pob_body_armour_es_is_local():
    """With the installed, hash-verified checkout: body armour ES uses the
    trade site's local id (the PoB file's "(Local)" row)."""
    import pytest
    path, pins = tradestats.pob_source()
    idx = tradestats.load_pob_index(path, pins) if path else {}
    if not idx:
        pytest.skip("pinned PoB checkout absent (setup.ps1 -TcCalc)")
    key = "+# to maximum Energy Shield"
    glob, local = tradestats.lookup(idx, key), tradestats.lookup(idx, key + " (Local)")
    assert glob and local and glob != local
    assert upgrade._slot_id(idx, key, "Body Armour") == local
    assert upgrade._slot_id(idx, key, "Amulet") == glob
