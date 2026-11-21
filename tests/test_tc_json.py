"""TC-JSON: character JSON paste import into the TC-CODE build model.

Synthetic fixtures only (tests/tc_fixtures.py); no network; the API tests
use an ephemeral port and a tmp runtime.
"""

import json
import xml.etree.ElementTree as ET

import pytest

from server.al.theorycraft import charjson, codec, model, paste
from server.al.theorycraft.store import BuildStore
from tc_fixtures import (CHAR_JSON, CURRENT_SHAPE_JSON, FULL_XML, JSON_TWIN_XML,
                         OLD_SHAPE_JSON, SHAPES_WEAPON_TEXT)
from test_tc_code_api import env, req  # noqa: F401  (pytest fixture reuse)


def _text(doc=CHAR_JSON):
    return json.dumps(doc, indent=1)


def test_json_maps_to_same_model_as_its_pob_code():
    from_json = charjson.from_json(_text())
    from_code = model.from_code(codec.encode(JSON_TWIN_XML))
    assert from_json.to_dict() == from_code.to_dict()
    d = from_json.to_dict()
    assert d["class_name"] == "Monk" and d["ascendancy"] == "Invoker" and d["level"] == 87
    assert d["tree"]["nodes"] == [10, 20, 30, 40, 50, 60]
    assert d["gear"]["Gloves"]["name"] == "Doom Grip"
    assert "+10% to Fire Resistance" in d["gear"]["Gloves"]["text"]
    assert d["skills"][0]["gems"][0] == {"name": "Example Strike", "skill_id": None,
                                         "level": 19, "quality": 20, "enabled": True}
    # the generated XML is a real build: lossless code round trip
    assert codec.decode(from_json.to_code()) == from_json.raw_xml


def test_bare_character_object_and_minimal():
    bare = charjson.from_json(_text(CHAR_JSON["character"]))
    assert bare.to_dict() == charjson.from_json(_text()).to_dict()
    b = charjson.from_json('{"class": "Warrior", "level": "12"}')
    assert b.class_name == "Warrior" and b.ascendancy is None and b.level == 12
    assert b.gear == {} and b.skills == ()
    unknown_cls = charjson.from_json('{"class": "Newclassname", "level": 3}')
    assert unknown_cls.class_name == "Newclassname" and unknown_cls.ascendancy is None


def test_wrong_types_are_ignored_not_fatal():
    doc = {"class": 5, "level": True, "passives": [1, 2], "equipment": {"x": 1},
           "skills": "nope", "jewels": [None, 3]}
    b = charjson.from_json(json.dumps(doc))
    assert b.class_name is None and b.level is None and b.gear == {}


@pytest.mark.parametrize("text", ["{", "{not json}", '{"a": 1}', '{"character": "x"}',
                                  "{" * 5000, '{"a": ' + "[" * 100000 + "]" * 100000 + "}"])
def test_bad_json_raises_build_error(text):
    with pytest.raises(model.BuildError):
        paste.parse(text)


def test_detect_formats():
    assert paste.detect(_text()) == "json"
    assert paste.detect("  \n{\"class\": 1}") == "json"
    assert paste.detect(codec.encode(FULL_XML)) == "code"
    assert paste.detect("https://pobb.in/AbCd") == "url"
    assert paste.detect("hello!") == "unknown"
    assert paste.parse(codec.encode(FULL_XML)).class_name == "Monk"
    with pytest.raises(codec.ShareUrlError):
        paste.parse("https://pobb.in/AbCd")


def test_store_persists_json_as_code(tmp_path):
    path = tmp_path / "build" / "last-code.txt"
    store = BuildStore(path)
    store.load_code(_text())
    saved = path.read_text(encoding="ascii").strip()
    assert paste.detect(saved) == "code"
    again = BuildStore(path)
    assert again.build.to_dict() == store.build.to_dict()


@pytest.mark.server
def test_api_auto_detects_json_paste(env):  # noqa: F811
    srv = env()
    status, doc = req(srv, "POST", "/api/build-code", {"code": _text()})
    assert status == 200, doc
    assert doc["build"]["ascendancy"] == "Invoker"
    assert doc["build"]["gear"]["Weapon 1"]["rarity"] == "UNIQUE"
    # the character object may also be posted as-is
    status, doc = req(srv, "POST", "/api/build-code", CHAR_JSON)
    assert status == 200 and doc["build"]["level"] == 87
    # a bad JSON paste is a 400 and keeps the good build
    assert req(srv, "POST", "/api/build-code", {"code": "{broken"})[0] == 400
    assert req(srv, "POST", "/api/build-code", {"code": '{"a": 1}'})[0] == 400
    status, doc = req(srv, "GET", "/api/build")
    assert doc["build"]["class_name"] == "Monk"
    # token check untouched
    assert req(srv, "POST", "/api/build-code", {"code": _text()}, token=None)[0] == 401


# TC-CHARJSON-SHAPES (research 0035 F7 / F9): the item shapes GGG documents
# today, the old shape still read.

def test_itemmod_objects_give_mod_lines():
    cur = charjson.from_json(_text(CURRENT_SHAPE_JSON))
    assert cur.gear["Weapon 1"].text == SHAPES_WEAPON_TEXT
    assert "10% increased Attack Speed" in cur.gear["Weapon 1 Swap"].text
    # the old string shape (with the removed lists) gives the same build
    old = charjson.from_json(_text(OLD_SHAPE_JSON))
    assert old.gear["Weapon 1"].text == SHAPES_WEAPON_TEXT
    assert cur.to_dict() == old.to_dict()
    assert set(charjson.LEGACY_MOD_FIELDS) <= set(charjson.MOD_FIELDS)
    # an ItemMod without a usable description adds no line and is not fatal
    item = {"rarity": "Magic", "typeLine": "Example Ring",
            "implicitMods": [{"description": "+5 to Intelligence"}, {}, None,
                             {"description": ["x"]}],
            "explicitMods": "not-a-list"}
    assert charjson.item_text(item).splitlines() == [
        "Rarity: MAGIC", "Example Ring", "+5 to Intelligence"]


def test_bonded_mods_are_read():
    for doc in (CURRENT_SHAPE_JSON, OLD_SHAPE_JSON):
        lines = charjson.from_json(_text(doc)).gear["Weapon 1"].text.splitlines()
        assert "+6 to Dexterity" in lines
        # rune and bonded lines come before the implicit
        assert (lines.index("+8% to Lightning Resistance") < lines.index("+6 to Dexterity")
                < lines.index("+12% to Critical Hit Chance"))
    only = {"rarity": "Normal", "typeLine": "Example Boots",
            "bondedMods": [{"description": "+3% to Example Bond"}, "+1 to Example Bond"]}
    assert charjson.mod_lines(only) == ["+3% to Example Bond", "+1 to Example Bond"]


def test_internal_and_display_class_names_give_same_build():
    display = charjson.from_json(_text(CURRENT_SHAPE_JSON))
    internal_doc = json.loads(_text(CURRENT_SHAPE_JSON))
    internal_doc["character"]["class"] = "Monk3"
    calls = []

    def names():
        calls.append(1)
        return {"Monk3": "Acolyte of Chayula", "Monk1": "Invoker"}

    mapped = charjson.from_json(_text(internal_doc), class_names=names)
    assert mapped.to_dict() == display.to_dict()
    assert mapped.class_name == "Monk" and mapped.ascendancy == "Acolyte of Chayula"
    # a display name never asks the map
    calls.clear()
    charjson.from_json(_text(CURRENT_SHAPE_JSON), class_names=names)
    assert calls == []
    # no map, a failing map or a wrong-typed map: the id passes through
    for cn in (None, lambda: 1 / 0, lambda: ["Monk3"], "not-callable"):
        b = charjson.from_json(_text(internal_doc), class_names=cn)
        assert b.class_name == "Monk3" and b.ascendancy is None
    # an internal id that maps to a base class gives that class
    base = charjson.from_json('{"class": "MonkBase", "level": 2}',
                              class_names=lambda: {"MonkBase": "Monk"})
    assert base.class_name == "Monk" and base.ascendancy is None


def test_flask_positions_above_one_are_charms():
    gear = charjson.from_json(_text(CURRENT_SHAPE_JSON)).gear
    assert gear["Flask 1"].base == "Example Life Flask"
    assert gear["Flask 2"].base == "Example Mana Flask"
    assert gear["Charm 1"].base == "Example Thawing Charm"
    assert gear["Charm 2"].base == "Example Staunching Charm"
    assert "Flask 3" not in gear and "Flask 4" not in gear
    # a Charm inventory id keeps its own x numbering
    doc = {"class": "Monk", "equipment": [
        {"rarity": "Normal", "typeLine": "Example Charm", "inventoryId": "Charm", "x": 1}]}
    assert "Charm 2" in charjson.from_json(json.dumps(doc)).gear


def test_weapon_set_membership_kept():
    b = charjson.from_json(_text(CURRENT_SHAPE_JSON))
    assert b.active_spec.nodes == (101, 102, 103, 201, 202, 301)
    spec = ET.fromstring(b.raw_xml).find("Tree/Spec")
    sets = {el.tag: el.get("nodes") for el in spec}
    assert sets == {"WeaponSet1": "201,202", "WeaponSet2": "301"}  # empty set3 left out
    assert b.gear["Weapon 1"].name == "Storm Branch"
    assert b.gear["Weapon 1 Swap"].base == "Example Spear of Haste"
    # the old fixture keeps a node that is in hashes and set2 in both
    old = ET.fromstring(charjson.to_xml(CHAR_JSON)).find("Tree/Spec")
    assert {el.tag: el.get("nodes") for el in old} == {"WeaponSet1": "50",
                                                         "WeaponSet2": "60,20"}
    # the generated XML is still a lossless share code
    assert codec.decode(b.to_code()) == b.raw_xml
