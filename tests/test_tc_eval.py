"""TC-EVAL core: item text parser, slot mapping, stat weights, verdicts.

Synthetic fixtures only (tests/tc_eval_fixtures.py); no clipboard, no
network, no game process.
"""

import json

import pytest

from server.al import paths
from server.al.theorycraft import evaluate as ev
from server.al.theorycraft import item as item_parser
from server.al.theorycraft import model
from server.al.theorycraft import weights as wm
from tc_eval_fixtures import (ADVANCED_RING, CURRENCY, EVAL_BUILD_XML, GERMAN, JEWEL,
                              MAGIC_BOOTS, RARE_GLOVES, UNIQUE_STAFF)
from tc_fixtures import FULL_XML


@pytest.fixture
def build():
    return model.parse(EVAL_BUILD_XML)


# -- parser

def test_parse_rare_gloves():
    it = item_parser.parse(RARE_GLOVES)
    assert it.is_item and it.item_class == "Gloves" and it.rarity == "RARE"
    assert (it.name, it.base) == ("Grim Clutch", "Example Gloves")
    assert it.item_level == 81 and it.quality == 12
    assert it.requirements == {"level": 45, "str": 30}
    assert it.sockets == "S S" and it.rune_sockets == 2
    assert it.properties["Armour"] == "88 (augmented)"
    assert it.flags == {"corrupted": True}
    assert it.note == "~price 5 exalted"
    texts = [(m.section, m.text, m.values) for m in it.mods]
    assert texts == [
        ("rune", "+15% to Fire Resistance", (15,)),
        ("explicit", "+70 to maximum Life", (70,)),
        ("explicit", "+30% to Cold Resistance", (30,)),
        ("explicit", "-10% to Lightning Resistance", (-10,)),
        ("explicit", "12% reduced Attack Speed", (12,)),
        ("explicit", "Cannot be Example Frozen", ()),
    ]


def test_parse_advanced_crlf_ring():
    it = item_parser.parse(ADVANCED_RING)
    assert it.advanced and it.item_class == "Rings"
    assert it.requirements == {"level": 40, "dex": 20}
    imp, life, light, adds = it.mods
    assert imp.section == "implicit" and imp.text == "+8% to Cold Resistance"
    assert (life.kind, life.name, life.tier, life.values) == ("prefix", "Hale", 3, (55,))
    assert (light.kind, light.name, light.tier) == ("suffix", "of Sparks", 2)
    assert adds.values == (2, 40)
    assert all("(" not in m.text for m in it.mods)  # ranges and reminder text gone


def test_parse_magic_unique_and_flavour():
    boots = item_parser.parse(MAGIC_BOOTS)
    assert boots.name is None and boots.base == "Swift Example Boots of Warmth"
    staff = item_parser.parse(UNIQUE_STAFF)
    assert (staff.name, staff.base) == ("Example Unique", "Example Quarterstaff")
    assert [m.text for m in staff.mods] == ["+1 to Level of all Melee Skills",
                                            "80% increased Physical Damage"]
    assert staff.mods[0].section == "implicit"


def test_parse_pob_item_text(build):
    ring = item_parser.parse(build.equipped("Ring 2").text)
    assert ring.rarity == "RARE" and ring.base == "Example Ring"
    assert [m.section for m in ring.mods] == ["implicit", "explicit", "explicit", "explicit"]
    assert ring.mods[1].text == "+80 to maximum Life"  # {crafted} prefix stripped
    weak = item_parser.parse(build.equipped("ring 1").text)
    assert weak.requirements == {"level": 30}
    assert weak.mods[0].section == "implicit" and weak.mods[0].text == "+7% to Cold Resistance"


@pytest.mark.parametrize("text", ["", None, 5, "hello\nworld", GERMAN, "Rarity:",
                                  "x" * (item_parser.MAX_TEXT + 1),
                                  "Item Class: Rings\n--------\n--------\n{ broken"])
def test_parse_never_fatal(text):
    it = item_parser.parse(text)
    assert isinstance(it.to_dict(), dict)


def test_non_english_is_not_an_item():
    it = item_parser.parse(GERMAN)
    assert not it.is_item and it.warnings


# -- slot mapping

@pytest.mark.parametrize("cls,slots", [
    ("Gloves", ("Gloves",)), ("Body Armours", ("Body Armour",)), ("Helmets", ("Helmet",)),
    ("Boots", ("Boots",)), ("Amulets", ("Amulet",)), ("Rings", ("Ring 1", "Ring 2")),
    ("Belts", ("Belt",)), ("Quarterstaves", ("Weapon 1",)), ("Bows", ("Weapon 1",)),
    ("Wands", ("Weapon 1",)), ("One Hand Maces", ("Weapon 1",)),
    ("Shields", ("Weapon 2",)), ("Foci", ("Weapon 2",)), ("Quivers", ("Weapon 2",)),
    ("Life Flasks", ("Flask 1",)), ("Charms", ("Charm 1", "Charm 2", "Charm 3")),
    ("Jewels", ()), ("Stackable Currency", ()), ("", ()), (None, ()),
])
def test_slots_for_class(cls, slots):
    assert ev.slots_for_class(cls) == slots
    assert all(s in model.SLOTS for s in slots)


def test_equipped_lookup():
    b = model.parse(FULL_XML)
    assert b.equipped("Gloves").name == "Doom Grip"
    assert b.equipped("weapon 1").base == "Example Quarterstaff"
    assert b.equipped("Ring 1") is None and b.equipped(None) is None


# -- stat keys and scoring

@pytest.mark.parametrize("text,key,value", [
    ("+70 to maximum Life", "+# to maximum Life", 70),
    ("-10% to Lightning Resistance", "+#% to Lightning Resistance", -10),
    ("12% reduced Attack Speed", "#% increased Attack Speed", -12),
    ("40% increased Physical Damage", "#% increased Physical Damage", 40),
    ("Adds 2 to 40 Lightning Damage to Attacks", "Adds # to # Lightning Damage to Attacks", 21),
    ("1.5% of Damage taken Recouped as Life", "#% of Damage taken Recouped as Life", 1.5),
    ("Cannot be Frozen", "Cannot be Frozen", None),
])
def test_stat_key(text, key, value):
    assert wm.stat_key(text) == (key, value)


def test_score_rare_gloves():
    it = item_parser.parse(RARE_GLOVES)
    stats = ev.stats_of(it)
    # 15 fire (rune) + 70 life + 30 cold - 10 lightning - 12 * 2 attack speed
    assert ev.score(stats, wm.lookup(wm.DEFAULT_WEIGHTS)) == 81
    custom = wm.lookup({"+# TO MAXIMUM LIFE": 2})  # keys are case-insensitive
    assert ev.score(stats, custom) == 140


# -- verdicts

def test_gloves_upgrade_with_per_stat_delta(build):
    r = ev.evaluate(RARE_GLOVES, build, wm.defaults())
    assert r["ok"] and r["slot"] == "Gloves" and r["verdict"] == ev.UPGRADE
    comp = r["comparisons"][0]
    assert comp["equipped"]["name"] == "Old Grip" and comp["equipped_score"] == 60
    assert r["score"] == 81 and r["score_delta"] == 21
    rows = {row["key"]: row for row in comp["stats"]}
    assert rows["+# to maximum Life"]["delta"] == 30
    assert rows["+#% to Cold Resistance"] == {
        "key": "+#% to Cold Resistance", "weight": 1, "new": 30, "old": 20, "delta": 10,
        "score_delta": 10, "weighted": True}
    assert rows["#% increased Attack Speed"]["score_delta"] == -24
    assert "Cannot be Example Frozen" in r["unweighted"]


def test_ring_compares_both_rings(build):
    r = ev.evaluate(ADVANCED_RING, build, wm.defaults())
    assert [c["slot"] for c in r["comparisons"]] == ["Ring 1", "Ring 2"]
    by = {c["slot"]: c for c in r["comparisons"]}
    assert by["Ring 1"]["verdict"] == ev.UPGRADE and by["Ring 1"]["score_delta"] == 67
    assert by["Ring 2"]["verdict"] == ev.DOWNGRADE and by["Ring 2"]["score_delta"] == -75
    assert r["slot"] == "Ring 1" and r["verdict"] == ev.UPGRADE


def test_sidegrade_band_and_downgrade(build):
    side = {"weights": {"+# to maximum Life": 1, "+#% to Cold Resistance": 1},
            "sidegrade": {"abs": 0, "pct": 50}}
    r = ev.evaluate(RARE_GLOVES, build, side)
    # new 100 vs old 60: delta 40 is over the band (50% of 60 = 30)
    assert r["verdict"] == ev.UPGRADE
    side["sidegrade"]["pct"] = 70  # band 42 > 40
    assert ev.evaluate(RARE_GLOVES, build, side)["verdict"] == ev.SIDEGRADE
    down = {"weights": {"+#% to Fire Resistance": 1}}  # gloves have 15 fire, ring 2 has 40
    r = ev.evaluate(RARE_GLOVES, build, down, slot="Ring 2")
    assert r["slot"] == "Ring 2" and r["verdict"] == ev.DOWNGRADE


def test_empty_slot_and_edge_cases(build):
    r = ev.evaluate(MAGIC_BOOTS, build, None)
    assert r["verdict"] == ev.UPGRADE and r["comparisons"][0]["empty"]
    assert r["score"] == 70
    assert ev.evaluate(MAGIC_BOOTS, None, None)["error"] == "no build loaded"
    assert ev.evaluate(JEWEL, build, None)["error"] == "no gear slot for this item class"
    assert ev.evaluate(CURRENCY, build, None)["ok"] is False
    assert ev.evaluate(GERMAN, build, None)["error"] == "not an item"
    staff = ev.evaluate(UNIQUE_STAFF, build, None)
    assert staff["slot"] == "Weapon 1" and staff["score"] == 15 + 80


# -- weights document and persistence

def test_validate_rejects_bad_docs():
    for bad in (None, [], {}, {"weights": []}, {"weights": {"": 1}},
                {"weights": {"a": "x"}}, {"weights": {"a": True}},
                {"weights": {"a": float("inf")}}, {"weights": {"a": 1, "A": 2}},
                {"weights": {"a": 1}, "sidegrade": {"abs": -1}},
                {"weights": {chr(0xE9): 1}}):
        with pytest.raises(wm.WeightsError):
            wm.validate(bad)
    ok = wm.validate({"weights": {"  +# to  maximum Life ": 2}})
    assert ok["weights"] == {"+# to maximum Life": 2}
    assert ok["sidegrade"] == wm.DEFAULT_SIDEGRADE


def test_store_writes_defaults_then_persists(tmp_path):
    path = wm.default_path(tmp_path / "rt")
    store = wm.WeightsStore(path)
    assert path.is_file() and store.get() == wm.defaults()
    raw = path.read_bytes()
    assert b"\r" not in raw and raw.isascii()
    store.put({"weights": {"+# to maximum Life": 3}, "sidegrade": {"abs": 1, "pct": 0}})
    again = wm.WeightsStore(path)
    assert again.get()["weights"] == {"+# to maximum Life": 3}
    assert again.load_error is None


def test_store_bad_file_uses_defaults_and_keeps_file(tmp_path):
    path = tmp_path / "weights.json"
    path.write_text("{not json", encoding="ascii")
    store = wm.WeightsStore(path)
    assert store.load_error and store.get() == wm.defaults()
    assert path.read_text(encoding="ascii") == "{not json"
    path.write_text(json.dumps({"weights": {"a": "x"}}), encoding="ascii")
    assert wm.WeightsStore(path).load_error


def test_weights_path_is_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.RUNTIME_ENV, str(tmp_path))
    assert paths.weights_file() == tmp_path.resolve() / "theorycraft" / "weights.json"
    assert paths.all_runtime_paths()["weights"] == paths.weights_file()
