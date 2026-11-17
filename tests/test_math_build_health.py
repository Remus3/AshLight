"""MATH-BUILD-HEALTH and MATH-NEXT-LOOK (theorycraft/health.py).

Every number here is a PoB-exported PlayerStat (or a PoB-measured stat
weight from pobweights); the module only compares them to the 75 cap, to 0
and to PoB's own requirement stats, and orders them (decision 0004, ruling
A of research 0028). The PlayerStat sets below are real-shaped (the names
PoB's BuildDisplayStats writes) with invented values; the live leg reads the
public reference build from the sidecar cache when it is there.
"""

import pytest

from server.al.theorycraft import health, model, searchstr

GLOVES = "Rarity: RARE\nDoom Grip\nExample Gloves\nItem Level: 80\n+40 to maximum Life\n"
RING = ("Rarity: RARE\nLoop Band\nExample Ring\nItem Level: 80\n"
        "+20% to Fire Resistance\n+30 to maximum Life\n")
STAFF = "Rarity: UNIQUE\nExample Unique\nExample Quarterstaff\n"
FLASK = "Rarity: MAGIC\nExample Life Flask\n"


def _xml(stats, gear=None):
    gear = gear or {}
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<PathOfBuilding2>",
             '\t<Build level="80" className="Monk" ascendClassName="Invoker">']
    for k, v in stats.items():
        lines.append(f'\t\t<PlayerStat stat="{k}" value="{v}"/>')
    lines.append("\t</Build>")
    lines.append('\t<Items activeItemSet="1">')
    for i, (slot, text) in enumerate(gear.items(), start=1):
        lines.append(f'\t\t<Item id="{i}">\n{text}</Item>')
    lines.append('\t\t<ItemSet id="1">')
    for i, slot in enumerate(gear, start=1):
        lines.append(f'\t\t\t<Slot name="{slot}" itemId="{i}"/>')
    lines.append("\t\t</ItemSet>\n\t</Items>\n</PathOfBuilding2>\n")
    return "\n".join(lines)


CAPPED = {"Life": 2410, "EnergyShield": 0, "Armour": 1200, "Evasion": 300,
          "EffectiveBlockChance": 25, "Mana": 600, "Spirit": 100,
          "SpiritUnreserved": 30, "Str": 100, "ReqStr": 80, "Dex": 90,
          "ReqDex": 90, "Int": 50, "ReqInt": 20, "FireResist": 75,
          "ColdResist": 75, "LightningResist": 75, "ChaosResist": -12,
          "FireMaximumHitTaken": 9000, "ColdMaximumHitTaken": 8000,
          "LightningMaximumHitTaken": 8500, "PhysicalMaximumHitTaken": 3000}


def _build(stats, gear=None):
    return model.parse(_xml(stats, gear))


def _ids(doc):
    return [w["id"] for w in doc["warnings"]]


# ---- MATH-BUILD-HEALTH ---------------------------------------------------

def test_no_build_says_it_needs_one():
    doc = health.health(None)
    assert doc["loaded"] is False
    assert doc["warnings"] == [] and doc["values"] == []
    assert "Load a build" in doc["message"]


def test_capped_build_has_no_warnings_and_shows_values():
    doc = health.health(_build(CAPPED))
    assert doc["loaded"] and doc["has_stats"]
    assert doc["source"] == "PoB"
    assert [w for w in doc["warnings"] if w["severity"] != "low"] == []
    labels = {v["id"]: v["value"] for v in doc["values"]}
    assert labels["Life"] == 2410 and labels["Armour"] == 1200
    assert labels["ChaosResist"] == -12  # chaos is a number, never a fail
    assert labels["EffectiveBlockChance"] == 25
    assert "chaos" not in " ".join(_ids(doc))


def test_uncapped_resists_warn_biggest_gap_first():
    stats = dict(CAPPED, ColdResist=71, LightningResist=40, FireResist=76)
    doc = health.health(_build(stats))
    res = [w for w in doc["warnings"] if w["id"].startswith("res-")]
    assert [w["id"] for w in res] == ["res-lightning", "res-cold"]
    cold = res[1]
    assert cold["value"] == 71 and cold["limit"] == 75
    assert cold["severity"] == "medium"
    assert "71%" in cold["text"] and "75%" in cold["text"]


def test_unmet_attribute_uses_pobs_own_condition():
    # PoB warns when Req > have; equal is met
    stats = dict(CAPPED, Str=50, ReqStr=60, Dex=90, ReqDex=90)
    doc = health.health(_build(stats))
    assert "attr-str" in _ids(doc) and "attr-dex" not in _ids(doc)
    w = next(w for w in doc["warnings"] if w["id"] == "attr-str")
    assert w["severity"] == "high"
    assert "Strength" in w["text"] and "50" in w["text"] and "60" in w["text"]


def test_negative_spirit_warns_zero_does_not():
    doc = health.health(_build(dict(CAPPED, SpiritUnreserved=-15)))
    w = next(w for w in doc["warnings"] if w["id"] == "spirit")
    assert w["severity"] == "high" and "-15" in w["text"]
    assert "spirit" not in _ids(health.health(_build(dict(CAPPED, SpiritUnreserved=0))))


def test_high_warnings_sort_before_medium():
    stats = dict(CAPPED, ColdResist=10, SpiritUnreserved=-1)
    order = [w["severity"] for w in health.health(_build(stats))["warnings"]]
    rank = {"high": 0, "medium": 1, "low": 2}
    assert order == sorted(order, key=rank.get)


def test_weakest_element_is_pobs_smallest_max_hit():
    doc = health.health(_build(CAPPED))
    assert doc["weakest"] == {"element": "cold", "hit": 8000}
    w = next(w for w in doc["warnings"] if w["id"] == "weakest")
    assert w["severity"] == "low" and "cold" in w["text"] and "8,000 damage" in w["text"]


def test_missing_stats_show_nothing():
    doc = health.health(_build({"Life": 900, "ColdResist": 30}))
    assert _ids(doc) == ["res-cold"]  # no fire / lightning: missing, not 0
    assert [v["id"] for v in doc["values"]] == ["Life"]
    assert doc["weakest"] is None


def test_non_numeric_stat_is_missing():
    doc = health.health(_build({"FireResist": "n/a", "Life": "x"}))
    assert doc["warnings"] == [] and doc["values"] == []


def test_build_without_stats_says_so():
    doc = health.health(_build({}))
    assert doc["loaded"] and not doc["has_stats"]
    assert "Path of Building" in doc["message"]


def test_store_snapshot_carries_health_and_updates_on_load(tmp_path):
    from server.al.theorycraft import codec, store
    s = store.BuildStore(tmp_path / "last-code.txt")
    assert s.snapshot()["health"]["loaded"] is False
    s.load_code(codec.encode(_xml(dict(CAPPED, ColdResist=50))))
    assert "res-cold" in _ids(s.snapshot()["health"])
    s.load_code(codec.encode(_xml(CAPPED)))
    assert "res-cold" not in _ids(s.snapshot()["health"])


# ---- MATH-NEXT-LOOK ------------------------------------------------------

def _weights(table):
    return lambda build, slot: dict(table.get(slot, {}))


def test_next_look_gap_first_then_weight():
    b = _build(dict(CAPPED, ColdResist=60, LightningResist=70),
               {"Ring 1": RING, "Gloves": GLOVES})
    w = {"Ring 1": {"+# to maximum Life": 0.9, "#% increased Attack Speed": 2.5,
                    "+# to Accuracy Rating": 0.1, "#% increased Rarity of Items found": 0}}
    doc = health.next_look(b, _weights(w))
    ring = next(r for r in doc["slots"] if r["slot"] == "Ring 1")
    # gaps (biggest first), then the top PoB weight missing on the ring;
    # life is on the ring already, a zero weight is no reason
    assert ring["terms"] == ["cold res", "lightning res", "increased attack speed"]
    assert ring["line"] == ("cold resistance, then lightning resistance, "
                            "then increased attack speed")
    assert ring["text"] == '"cold res|lightning res|increased attack speed"'
    assert doc["pob_weights"] is True


def test_next_look_attribute_gap_after_resists():
    b = _build(dict(CAPPED, ColdResist=74, Str=10, ReqStr=60), {"Boots": GLOVES})
    boots = health.next_look(b)["slots"][0]
    assert boots["terms"][:2] == ["cold res", "strength"]


def test_next_look_covers_equipped_gear_slots_only():
    b = _build(dict(CAPPED, ColdResist=60),
               {"Gloves": GLOVES, "Weapon 1": STAFF, "Flask 1": FLASK})
    doc = health.next_look(b)
    slots = [r["slot"] for r in doc["slots"]]
    assert "Gloves" in slots and "Flask 1" not in slots
    # a weapon gets no resist gap; with no PoB weights it has no line
    assert "Weapon 1" not in slots
    assert doc["pob_weights"] is False


def test_next_look_weapon_gets_pob_weights():
    b = _build(CAPPED, {"Weapon 1": STAFF})
    w = {"Weapon 1": {"#% increased Physical Damage": 3.1, "Adds # to # Fire Damage": 1.2}}
    row = health.next_look(b, _weights(w))["slots"][0]
    assert row["slot"] == "Weapon 1"
    assert row["terms"] == ["increased physical damage", "fire damage"]


def test_next_look_slot_order_follows_gear_order():
    b = _build(dict(CAPPED, FireResist=10), {"Belt": GLOVES, "Helmet": GLOVES, "Ring 2": GLOVES})
    assert [r["slot"] for r in health.next_look(b)["slots"]] == ["Helmet", "Ring 2", "Belt"]


def test_next_look_term_cap_and_length_cap():
    b = _build(dict(CAPPED, FireResist=1, ColdResist=2, LightningResist=3), {"Amulet": GLOVES})
    long_keys = {f"+# to {'x' * 90} {i}": 10 - i for i in range(5)}
    row = health.next_look(b, _weights({"Amulet": long_keys}))["slots"][0]
    assert len(row["terms"]) <= health.MAX_TERMS
    assert len(row["text"]) <= searchstr.MAX_LEN


def test_next_look_no_build_and_no_stats():
    assert health.next_look(None) == {"slots": [], "pob_weights": False}
    assert health.next_look(_build({}, {"Gloves": GLOVES}))["slots"] == []


def test_next_look_weights_source_failure_is_ignored():
    def boom(build, slot):
        raise RuntimeError("cache broke")
    b = _build(dict(CAPPED, ColdResist=60), {"Gloves": GLOVES})
    assert health.next_look(b, boom)["slots"][0]["terms"] == ["cold res"]


def test_term_for_keys():
    assert health.term_for("+# to maximum Life") == "maximum life"
    assert health.term_for("+#% to all Elemental Resistances") == "all elemental res"
    assert health.term_for("Adds # to # Cold Damage") == "cold damage"
    assert health.term_for("#% increased Movement Speed") == "increased movement speed"
    assert health.term_for("") is None
    assert health.label_for("all elemental res") == "all elemental resistances"
    assert health.label_for("fire res") == "fire resistance"
    assert health.label_for("maximum life") == "maximum life"


def test_store_snapshot_next_look_uses_weights_source(tmp_path):
    from server.al.theorycraft import codec, store
    s = store.BuildStore(tmp_path / "last-code.txt")
    assert s.snapshot()["next_look"] == {"slots": [], "pob_weights": False}
    s.weights_for = _weights({"Gloves": {"#% increased Attack Speed": 2.0}})
    s.load_code(codec.encode(_xml(CAPPED, {"Gloves": GLOVES})))
    row = s.snapshot()["next_look"]["slots"][0]
    assert row["terms"] == ["increased attack speed"]


def test_core_wires_pob_weight_cache(tmp_path):
    from server.al.core import Core
    core = Core(runtime=tmp_path, tail=False)
    try:
        assert core.builds.weights_for == core.last_eval.pob_weights.fallback
    finally:
        core.close()


# ---- live leg: the public reference build (sidecar cache) ---------------

def _reference_xml():
    from tc_live_util import reference
    ref = reference()
    return None if ref is None else ref[1]


def test_live_reference_build_health():
    xml = _reference_xml()
    if xml is None:
        pytest.skip("reference build absent (sidecar Cache\\tc_bridge)")
    b = model.parse(xml)
    doc = health.health(b)
    ids = _ids(doc)
    # PoB's own export: cold 71, lightning 73 below the cap; fire 75 capped
    assert ids[:2] == ["res-cold", "res-lightning"]
    assert "res-fire" not in ids
    assert not any(i.startswith("attr-") for i in ids) and "spirit" not in ids
    assert doc["weakest"]["element"] == "cold"
    nl = health.next_look(b)
    assert nl["slots"] and all(r["terms"][0] == "cold res" for r in nl["slots"])
    assert all(len(r["text"]) <= searchstr.MAX_LEN for r in nl["slots"])
