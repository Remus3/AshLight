"""TC-WORN-STORE (decision 0052): the worn-gear store and baseline.

Synthetic item texts only (tests/tc_eval_fixtures.py and the ones below);
no clipboard, no network, no game process, every file under tmp_path.
"""

import json

from server.al import jsonfile, paths
from server.al.theorycraft import evaluate as ev
from server.al.theorycraft import item as item_parser
from server.al.theorycraft import model
from server.al.theorycraft import worngear as wg
from tc_eval_fixtures import (ADVANCED_RING, CURRENCY, EVAL_BUILD_XML, JEWEL, MAGIC_BOOTS,
                              RARE_GLOVES, UNIQUE_STAFF)


def _ring(name, life, extra=""):
    return ("Item Class: Rings\nRarity: Rare\n%s\nExample Ring\n--------\n"
            "Item Level: 70\n--------\n+7%% to Cold Resistance (implicit)\n--------\n"
            "+%d to maximum Life\n%s" % (name, life, extra))


def _wand(name, life):
    return ("Item Class: Wands\nRarity: Rare\n%s\nExample Wand\n--------\n"
            "Item Level: 70\n--------\n+%d to maximum Life\n" % (name, life))


SHIELD = ("Item Class: Shields\nRarity: Rare\nWall Guard\nExample Shield\n--------\n"
          "+30 to maximum Life\n")
RING_A = _ring("Alpha Loop", 40)
RING_B = _ring("Beta Loop", 60)
RING_C = _ring("Gamma Loop", 80)
NAMES = ("Grim Clutch", "Storm Loop", "Example Unique", "Alpha Loop", "Beta Loop",
         "Gamma Loop", "Swift Example Boots of Warmth")


def _store(tmp_path):
    return wg.WornGear(tmp_path / wg.FILE_NAME)


# -- bounds

def test_bounds_16_slots_12_characters_oldest_character_dropped(tmp_path):
    assert wg.MAX_SLOTS == 16 and wg.MAX_SLOTS >= len(model.SLOTS)
    assert wg.MAX_CHARACTERS == 12
    s = _store(tmp_path)
    for i in range(14):
        assert s.wear("Char%02d" % i, RARE_GLOVES) == "Gloves"
    names = s.characters()
    assert len(names) == 12
    assert names[0] == "Char02" and names[-1] == "Char13"
    # filing again moves a character to the newest end
    s.wear("Char02", RING_A)
    s.wear("NewOne", RING_A)
    assert "Char02" in s.characters() and "Char03" not in s.characters()
    doc = json.loads((tmp_path / wg.FILE_NAME).read_text(encoding="ascii"))
    assert len(doc["characters"]) == 12


def test_hand_made_file_is_cut_to_the_bounds(tmp_path):
    entry = {"class": "Rings", "rarity": "RARE", "base": "Example Ring",
             "mods": [{"text": "+%d to maximum Life" % i, "section": "explicit"}
                      for i in range(60)] + [{"text": "x" * 999, "section": "bogus"}], "n": 1}
    slots = {s: dict(entry) for s in model.SLOTS}
    slots.update({"Bogus %d" % i: dict(entry) for i in range(10)})
    chars = {"C%02d" % i: {"n": 1, "slots": {"Belt": entry}} for i in range(19)}
    chars["C19"] = {"n": 1, "slots": slots}
    jsonfile.write_json(tmp_path / wg.FILE_NAME, {"schema": 1, "characters": chars})
    s = _store(tmp_path)
    assert s.characters() == ["C%02d" % i for i in range(8, 20)]
    worn = s.worn("C19")
    assert set(worn) == set(model.SLOTS) and len(worn) <= wg.MAX_SLOTS
    assert len(worn["Belt"]["mods"]) == wg.MAX_MODS


def test_long_strings_are_cut(tmp_path):
    s = _store(tmp_path)
    long_mod = "+5 to maximum Life " + "y" * 500
    s.wear("x" * 300, "Item Class: Belts\nRarity: Rare\nN\n" + "B" * 300
           + "\n--------\n" + long_mod + "\n")
    (name,) = s.characters()
    assert len(name) == wg.MAX_NAME
    belt = s.worn(name)["Belt"]
    assert len(belt["base"]) == wg.MAX_FIELD
    assert len(belt["mods"][0]["text"]) == wg.MAX_TEXT


# -- what the file holds

def test_file_holds_no_item_name_and_no_raw_text(tmp_path):
    s = _store(tmp_path)
    s.wear("Hero", RARE_GLOVES)
    s.wear("Hero", ADVANCED_RING)
    s.wear("Hero", UNIQUE_STAFF)
    s.wear("Hero", MAGIC_BOOTS)
    raw = (tmp_path / wg.FILE_NAME).read_text(encoding="ascii")
    bak = jsonfile.bak_path(tmp_path / wg.FILE_NAME).read_text(encoding="ascii")
    for text in (raw, bak):
        for name in NAMES:
            assert name not in text
        for marker in ("Item Level", "Requirements", "Note:", "~price", "Corrupted",
                       "--------", "Sockets", "flavour", "(6-10)", "Tier"):
            assert marker not in text
    doc = json.loads(raw)
    hero = doc["characters"]["Hero"]["slots"]
    assert set(hero["Gloves"]) == {"class", "rarity", "base", "mods", "n"}
    assert hero["Gloves"]["base"] == "Example Gloves"
    assert hero["Weapon 1"]["base"] == "Example Quarterstaff"
    assert hero["Boots"]["base"] == "Example Boots"  # magic: the parser's base only


def test_unresolved_magic_name_line_is_not_stored(tmp_path):
    parsed = item_parser.parse(MAGIC_BOOTS)
    parsed.name, parsed.base = None, "Swift Example Boots of Warmth"
    entry = wg.entry_of(parsed)
    assert entry["base"] is None and entry["class"] == "Boots"


def test_non_gear_is_not_filed(tmp_path):
    s = _store(tmp_path)
    for text in (CURRENCY, JEWEL, "not an item", "", None, 42):
        assert s.wear("Hero", text) is None
    assert s.characters() == []
    assert not (tmp_path / wg.FILE_NAME).exists()


# -- synthesized text

def test_synthesized_item_text_parses_to_the_same_stats():
    for text in (RARE_GLOVES, ADVANCED_RING, MAGIC_BOOTS, UNIQUE_STAFF, RING_A, SHIELD,
                 _ring("Flag Loop", 10, "Cannot be Example Frozen\nEnds with a stop.\n")):
        before = item_parser.parse(text)
        after = item_parser.parse(wg.item_text(wg.entry_of(text)))
        assert ev.stats_of(after) == ev.stats_of(before), text
        assert ([(m.section, m.text, m.values) for m in after.mods]
                == [(m.section, m.text, m.values) for m in before.mods]), text
        assert after.item_class == before.item_class and after.rarity == before.rarity
        if before.rarity != item_parser.MAGIC:
            assert after.base == before.base
        assert ev.slots_for_class(after.item_class) == ev.slots_for_class(before.item_class)


def test_as_item_is_a_model_item_without_name(tmp_path):
    s = _store(tmp_path)
    s.wear("Hero", RARE_GLOVES)
    it = s.item("Hero", "gloves")
    assert isinstance(it, model.Item)
    assert it.name is None and it.base == "Example Gloves" and it.rarity == "RARE"
    assert "Grim Clutch" not in it.text
    assert s.item("Hero", "Boots") is None and s.item("Nobody", "Gloves") is None
    assert s.item("Hero", "Not A Slot") is None


# -- slot choice

def test_ring_slots_fill_empty_then_oldest(tmp_path):
    s = _store(tmp_path)
    assert s.wear("Hero", RING_A) == "Ring 1"
    assert s.wear("Hero", RING_B) == "Ring 2"
    assert s.wear("Hero", RING_C) == "Ring 1"  # Ring 1 was filed longest ago
    assert s.wear("Hero", RING_A) == "Ring 2"
    assert s.worn("Hero")["Ring 1"]["mods"][1]["text"] == "+80 to maximum Life"


def test_ring_reuses_the_slot_last_compared_when_mod_lines_match(tmp_path):
    s = _store(tmp_path)
    s.wear("Hero", RING_A)
    s.wear("Hero", RING_B)
    s.note_compared("Hero", "Ring 2", RING_C)
    assert s.wear("Hero", RING_C) == "Ring 2"
    # a compared slot of other mod lines is ignored
    s.note_compared("Hero", "Ring 1", RING_B)
    assert s.wear("Hero", RING_A) == "Ring 1"  # oldest (Ring 1 holds A, n=1)


def test_same_item_again_keeps_its_slot(tmp_path):
    s = _store(tmp_path)
    s.wear("Hero", RING_A)
    s.wear("Hero", RING_B)
    assert s.wear("Hero", RING_B) == "Ring 2"
    assert s.wear("Hero", RING_A) == "Ring 1"


def test_explicit_slot_wins_and_wrong_slot_refused(tmp_path):
    s = _store(tmp_path)
    assert s.wear("Hero", RING_A, slot="ring 2") == "Ring 2"
    assert s.wear("Hero", RING_A, slot="Helmet") is None
    assert s.wear("Hero", RARE_GLOVES, slot="Boots") is None
    assert "Helmet" not in s.worn("Hero")


def test_one_hand_weapon_slots(tmp_path):
    s = _store(tmp_path)
    assert s.wear("Hero", _wand("W One", 10)) == "Weapon 1"
    assert s.wear("Hero", _wand("W Two", 20)) == "Weapon 1"  # no dual wield known
    assert s.wear("Hero", _wand("W Two", 20), slot="Weapon 2") == "Weapon 2"
    # now dual wielding: the older hand is replaced, the last compared reused
    assert s.wear("Hero", _wand("W Three", 30)) == "Weapon 1"
    s.note_compared("Hero", "Weapon 2", _wand("W Four", 40))
    assert s.wear("Hero", _wand("W Four", 40)) == "Weapon 2"
    # a shield in the off hand: a wand only goes to Weapon 1
    s.wear("Shield", SHIELD)
    assert s.worn("Shield") == {"Weapon 2": s.worn("Shield")["Weapon 2"]}
    assert s.wear("Shield", _wand("W Five", 50)) == "Weapon 1"
    assert s.wear("Shield", _wand("W Six", 60)) == "Weapon 1"
    assert wg.WornGear(tmp_path / wg.FILE_NAME).worn("Shield")["Weapon 2"]["class"] == "Shields"


def test_one_hand_weapon_follows_a_dual_wield_build(tmp_path):
    xml = EVAL_BUILD_XML.replace(
        "\t\t<ItemSet id=\"1\">",
        "\t\t<Item id=\"9\">\nItem Class: Wands\nRarity: RARE\nOff Wand\nExample Wand\n"
        "+5 to maximum Life\n</Item>\n\t\t<ItemSet id=\"1\">").replace(
        "<Slot name=\"Gloves\" itemId=\"1\"/>",
        "<Slot name=\"Gloves\" itemId=\"1\"/>\n\t\t\t<Slot name=\"Weapon 2\" itemId=\"9\"/>")
    build = model.parse(xml)
    s = _store(tmp_path)
    assert s.candidate_slots("Hero", "Wands", build) == ("Weapon 1", "Weapon 2")
    assert s.candidate_slots("Hero", "Wands", None) == ("Weapon 1",)
    assert s.wear("Hero", _wand("A", 1), build=build) == "Weapon 1"
    assert s.wear("Hero", _wand("B", 2), build=build) == "Weapon 2"


def test_characters_are_kept_apart(tmp_path):
    s = _store(tmp_path)
    s.wear("Hero", RING_A)
    s.wear("Other", RING_B)
    s.wear(None, RARE_GLOVES)
    assert set(s.worn("Hero")) == {"Ring 1"} and set(s.worn("Other")) == {"Ring 1"}
    assert set(s.worn(None)) == {"Gloves"} and s.worn("") == s.worn(None)
    assert s.worn("Hero")["Ring 1"]["mods"] != s.worn("Other")["Ring 1"]["mods"]


# -- persistence

def test_restart_reads_the_set_back(tmp_path):
    s = _store(tmp_path)
    s.wear("Hero", RING_A)
    s.wear("Hero", RING_B)
    s.wear("Hero", RARE_GLOVES)
    s.wear("Two", UNIQUE_STAFF)
    again = _store(tmp_path)
    assert again.characters() == s.characters()
    assert again.worn("Hero") == s.worn("Hero") and again.worn("Two") == s.worn("Two")
    # the slot ages survive too: the next ring replaces the older one
    assert again.wear("Hero", RING_C) == "Ring 1"


def test_clear_empties_the_set_and_drops_the_bak(tmp_path):
    path = tmp_path / wg.FILE_NAME
    s = _store(tmp_path)
    s.wear("Hero", RING_A)
    assert jsonfile.bak_path(path).exists()
    s.note_compared("Hero", "Ring 2", RING_B)
    s.clear()
    assert s.characters() == [] and s.worn("Hero") == {}
    assert not jsonfile.bak_path(path).exists()
    assert json.loads(path.read_text(encoding="ascii"))["characters"] == {}
    assert _store(tmp_path).characters() == []
    assert s.wear("Hero", RING_B) == "Ring 1"  # the compared slot was forgotten


def test_remove_one_slot(tmp_path):
    s = _store(tmp_path)
    s.wear("Hero", RING_A)
    s.wear("Hero", RARE_GLOVES)
    assert s.remove("Hero", "Ring 1") is True
    assert s.remove("Hero", "Ring 1") is False
    assert set(_store(tmp_path).worn("Hero")) == {"Gloves"}
    assert s.remove("Hero", "Gloves") is True and s.characters() == []


def test_damaged_file_reads_empty_and_is_not_overwritten_until_next_wear(tmp_path):
    path = tmp_path / wg.FILE_NAME
    for junk in (b"{not json", b"", b"[1, 2]", b"\xff\xfe\x00",
                 b'{"characters": {"Hero": {"slots": {"Ring 1": "x"}}}}'):
        path.write_bytes(junk)
        s = _store(tmp_path)
        assert s.characters() == []
        assert s.item("Hero", "Ring 1") is None
        s.note_compared("Hero", "Ring 1", RING_A)
        assert path.read_bytes() == junk
        assert s.wear("Hero", RING_A) == "Ring 1"
        assert json.loads(path.read_text(encoding="ascii"))["characters"]["Hero"]
        jsonfile.bak_path(path).unlink()


def test_damaged_file_restores_from_its_bak(tmp_path):
    path = tmp_path / wg.FILE_NAME
    _store(tmp_path).wear("Hero", RING_A)
    path.write_bytes(b"{torn")
    assert set(_store(tmp_path).worn("Hero")) == {"Ring 1"}


def test_oversized_file_reads_empty(tmp_path):
    path = tmp_path / wg.FILE_NAME
    path.write_bytes(b" " * (wg.MAX_BYTES + 1))
    assert _store(tmp_path).characters() == []


# -- baseline

def test_baseline_worn_first_plan_second(tmp_path):
    build = model.parse(EVAL_BUILD_XML)
    s = _store(tmp_path)
    s.wear("Hero", RING_C, slot="Ring 2")
    b = wg.Baseline(s, "Hero", build)
    assert b.source("Ring 2") == wg.SOURCE_WORN
    assert b.equipped("Ring 2").base == "Example Ring" and b.equipped("Ring 2").name is None
    assert "+80 to maximum Life" in b.equipped("Ring 2").text
    assert b.source("Ring 1") == wg.SOURCE_PLAN
    assert b.equipped("Ring 1") is build.equipped("Ring 1")
    assert b.source("Boots") is None and b.equipped("Boots") is None
    assert b.has_any(("Ring 1",)) and not b.has_any(("Boots", "Helmet"))
    assert b.plan("Ring 2") is build.equipped("Ring 2")


def test_baseline_without_build_or_store(tmp_path):
    s = _store(tmp_path)
    s.wear("Hero", RING_A)
    b = wg.Baseline(s, "Hero", None)
    assert b.source("Ring 1") == wg.SOURCE_WORN and b.equipped("Ring 2") is None
    assert wg.Baseline(s, "Other").has_any(model.SLOTS) is False
    assert wg.Baseline(None, "Hero", None).equipped("Ring 1") is None


def test_baseline_scores_through_the_stat_weights(tmp_path):
    """A worn item read through the baseline scores like the item itself."""
    s = _store(tmp_path)
    s.wear("Hero", ADVANCED_RING)
    worn = wg.Baseline(s, "Hero").equipped("Ring 1")
    assert (ev.stats_of(item_parser.parse(worn.text))
            == ev.stats_of(item_parser.parse(ADVANCED_RING)))


# -- path

def test_path_stays_under_the_runtime_dir(tmp_path, monkeypatch):
    monkeypatch.delenv(paths.RUNTIME_ENV, raising=False)
    p = wg.default_path()
    assert p.name == wg.FILE_NAME
    assert p.parent == paths.runtime_dir()
    p.resolve().relative_to(paths.runtime_dir().resolve())
    monkeypatch.setenv(paths.RUNTIME_ENV, str(tmp_path / "rt"))
    assert wg.default_path() == (tmp_path / "rt").resolve() / wg.FILE_NAME
    assert wg.default_path(tmp_path / "core") == tmp_path / "core" / wg.FILE_NAME


def test_store_never_touches_files_outside_its_path(tmp_path):
    sub = tmp_path / "rt"
    s = wg.WornGear(sub / wg.FILE_NAME)
    s.wear("Hero", RING_A)
    s.clear()
    s.wear("Hero", RING_B)
    left = sorted(p.name for p in tmp_path.rglob("*") if p.is_file())
    assert left == [wg.FILE_NAME, wg.FILE_NAME + ".bak"]
    assert all(p.parent == sub for p in tmp_path.rglob("*") if p.is_file())
