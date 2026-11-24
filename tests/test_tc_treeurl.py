"""TC-TREE-URL: the loaded build as a version 7 passive tree link.

The example link is GGG's own documented PoE2 example (API Reference,
"Passive Skill Tree URLs", research 0035 F10). The tree export here is a
synthetic stand-in written to tmp_path in the export's shape (class list in
index order, each class's ascendancy list, skillOverrides): no GGG data is
bundled (decision 0009). Its class order and the attribute override hash
mirror the cached export as read on the dev host on 2026-11-24 (Monk at
index 10, generic_attribute_dexterity = 14927), which is what the example
link names. The live sidecar file is never read (tests/conftest.py guard).
"""

import json

import pytest

from server.al.theorycraft import model, store, treedata, treeurl

EXAMPLE = ("https://pathofexile2.com/game/passive-skill-tree/"
           "AAAABwoAAAXO9AAArTcAAjpP1-wAAjpPNGMAAjpPvEYAAA==")
START = 44683       # the class start node of the example's class
ATTR = (44343, 55276, 13411)
DEX = 14927

CLASSES = [("Marauder", []), ("Witch", ["Infernalist", "Blood Mage", "Lich", "Abyssal Lich"]),
           ("Ranger", ["Deadeye", None, "Pathfinder"]), ("Duelist", []), ("Shadow", []),
           ("Templar", []), ("Warrior", ["Titan", "Warbringer", "Smith of Kitava"]),
           ("Sorceress", ["Stormweaver", "Chronomancer"]), ("Huntress", ["Amazon"]),
           ("Mercenary", ["Tactician"]),
           ("Monk", ["Martial Artist", "Invoker", "Acolyte of Chayula"]), ("Druid", ["Oracle"])]


def export_doc():
    classes = []
    for name, ascs in CLASSES:
        rows = [{"id": f"{name}{i + 1}", "name": a} for i, a in enumerate(ascs)]
        classes.append({"name": name, "ascendancies": rows})
    nodes = {"root": {"out": [str(START)]},
             str(START): {"skill": START, "name": "SIX", "classStartIndex": [4, 10]},
             "52980": {"skill": 52980, "name": "Evasion and Energy Shield"},
             "48198": {"skill": 48198, "name": "Step Like Mist"},
             "9994": {"skill": 9994, "name": "Invoker start", "ascendancyId": "Monk2",
                      "isAscendancyStart": True},
             "9995": {"skill": 9995, "name": "Invoker node", "ascendancyId": "Monk2"}}
    for a in ATTR:
        nodes[str(a)] = {"skill": a, "name": "Attribute"}
    overrides = {"26297": {"id": "generic_attribute_strength", "skill": 26297, "name": "Strength"},
                 str(DEX): {"id": "generic_attribute_dexterity", "skill": DEX, "name": "Dexterity"},
                 "57022": {"id": "generic_attribute_intelligence_", "skill": 57022,
                           "name": "Intelligence"},
                 "46793": {"id": "pathfinder_alternate_generic_attribute_damage",
                           "skill": 46793, "name": "Damage"}}
    return {"classes": classes, "nodes": nodes, "skillOverrides": overrides}


@pytest.fixture
def tree():
    return treedata.parse(export_doc())


def xml(cls="Monk", asc="None", nodes=None, extra=""):
    ids = nodes if nodes is not None else (START, 52980) + ATTR + (48198,)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<PathOfBuilding2>
<Build level="20" targetVersion="0_5" className="{cls}" ascendClassName="{asc}"/>
<Tree activeSpec="1">
<Spec title="Example" treeVersion="0_5" nodes="{','.join(str(n) for n in ids)}">
{extra}
<Overrides><AttributeOverride strNodes="" dexNodes="{','.join(str(a) for a in ATTR)}" intNodes=""/></Overrides>
</Spec>
</Tree>
</PathOfBuilding2>
"""


def test_documented_example_decodes():
    d = treeurl.decode(EXAMPLE)
    assert d["version"] == 7 and d["class_id"] == 10 and d["ascendancy"] == 0
    assert len(d["nodes"]) == 5
    assert [n["hash"] for n in d["nodes"]] == [52980, *ATTR, 48198]
    assert [n["override"] for n in d["nodes"]] == [None, DEX, DEX, DEX, None]
    assert all(n["weapon_set"] is None for n in d["nodes"])


def test_round_trip_is_byte_exact():
    assert treeurl.encode(treeurl.decode(EXAMPLE)) == EXAMPLE
    tail = EXAMPLE.rsplit("/", 1)[1]
    assert treeurl.encode(treeurl.decode(tail)) == EXAMPLE


def test_weapon_set_and_both_flags_round_trip():
    doc = {"class_id": 6, "ascendancy": 3,
           "nodes": [{"hash": 1, "weapon_set": 2, "override": None},
                     {"hash": 0xFFFF, "weapon_set": 1, "override": 0x1234},
                     {"hash": 7, "flags": 0x80, "weapon_set": None, "override": None}]}
    url = treeurl.encode(doc)
    back = treeurl.decode(url)
    assert [n["flags"] for n in back["nodes"]] == [1, 3, 0x80]
    assert back["nodes"][1]["override"] == 0x1234 and back["nodes"][0]["weapon_set"] == 2
    assert treeurl.encode(back) == url


@pytest.mark.parametrize("bad", [
    None, "", "!!!", "AAAABg==",                       # too short
    "AAAABgoAAAA=",                                     # version 6
    EXAMPLE[:-4],                                       # ends inside a node
    treeurl.encode({"class_id": 0, "ascendancy": 0, "nodes": []}) + "AA",  # bytes left
])
def test_bad_links_refused(bad):
    with pytest.raises(treeurl.TreeUrlError):
        treeurl.decode(bad)


def test_encode_refuses_out_of_range():
    for doc in ({"class_id": 256, "ascendancy": 0}, {"class_id": True, "ascendancy": 0},
                {"class_id": 0, "ascendancy": 0, "nodes": [{"hash": 65536}]},
                {"class_id": 0, "ascendancy": 0, "nodes": [{"hash": 1, "weapon_set": 300}]},
                {"class_id": 0, "ascendancy": 0, "nodes": [{"hash": 1, "override": -1}]}):
        with pytest.raises(treeurl.TreeUrlError):
            treeurl.encode(doc)


def test_class_and_ascendancy_bytes_from_the_export(tree):
    assert tree.classes[10] == "Monk"
    assert treeurl.class_bytes(tree, "Monk", None) == (10, 0)
    assert treeurl.class_bytes(tree, "Monk", "Invoker") == (10, 2)
    # a placeholder entry keeps its position
    assert treeurl.class_bytes(tree, "Ranger", "Pathfinder") == (2, 3)
    assert treeurl.class_bytes(tree, "Witch", "Abyssal Lich") == (1, 4)
    # never guessed: unknown class, unknown or foreign ascendancy
    assert treeurl.class_bytes(tree, "Nobody", None) is None
    assert treeurl.class_bytes(tree, "Monk", "Titan") is None
    assert treeurl.class_bytes(tree, None, None) is None
    assert treeurl.class_bytes(None, "Monk", None) is None


def test_export_attribute_hashes(tree):
    assert tree.attr_hashes == {"str": 26297, "dex": DEX, "int": 57022}
    doc = export_doc()
    doc["skillOverrides"]["1"] = {"id": "generic_attribute_dexterity2", "skill": 1,
                                  "name": "Dexterity"}
    assert "dex" not in treedata.parse(doc).attr_hashes  # two candidates: none


def test_build_gives_the_documented_example(tree):
    b = model.parse(xml())
    assert b.active_spec.attr_overrides == {a: "dex" for a in ATTR}
    assert treeurl.from_build(b, tree) == EXAMPLE


def test_build_with_ascendancy_and_weapon_sets(tree):
    extra = '<WeaponSet2 nodes="48198"/><WeaponSet1 nodes="52980"/>'
    b = model.parse(xml(asc="Invoker", extra=extra,
                        nodes=(START, 9994, 52980) + ATTR + (48198, 9995, 61000)))
    d = treeurl.decode(treeurl.from_build(b, tree))
    assert (d["class_id"], d["ascendancy"]) == (10, 2)
    # class and ascendancy starts and ids the export lacks are left out
    assert [n["hash"] for n in d["nodes"]] == [52980, *ATTR, 48198, 9995]
    by = {n["hash"]: n for n in d["nodes"]}
    assert by[52980]["weapon_set"] == 1 and by[48198]["weapon_set"] == 2
    assert by[9995]["weapon_set"] is None and by[44343]["override"] == DEX


def test_no_link_when_not_checkable(tree):
    assert treeurl.from_build(model.parse(xml(asc="Titan")), tree) is None
    assert treeurl.from_build(model.parse(xml(cls="Nobody")), tree) is None
    assert treeurl.from_build(model.parse(xml()), None) is None
    assert treeurl.from_build(None, tree) is None
    # ids that mostly miss the tree (another id space): no link
    assert treeurl.from_build(model.parse(xml(nodes=(1, 2, 3, 52980))), tree) is None


def test_existing_views_unchanged(tree):
    b = model.parse(xml())
    keys = set(b.active_spec.to_dict())
    assert "weapon_sets" not in keys and "attr_overrides" not in keys
    assert "asc_start" not in tree.node(9994).to_dict()


def test_store_snapshot_carries_the_link(tmp_path):
    tp = tmp_path / "gamedata" / treedata.FILE_NAME
    s = store.BuildStore(tmp_path / "last-code.txt", tree=treedata.TreeCache(tp))
    s.load_code(model.parse(xml()).to_code())
    assert s.snapshot()["tree_url"] is None  # no cached export: no link
    tp.parent.mkdir(parents=True)
    tp.write_text(json.dumps(export_doc()), encoding="ascii")
    assert s.snapshot()["tree_url"] == EXAMPLE
    assert store.BuildStore(tmp_path / "none.txt").snapshot()["tree_url"] is None


def test_module_makes_no_request():
    src = (treeurl.__file__ and open(treeurl.__file__, encoding="ascii").read())
    for word in ("urllib", "http.client", "socket", "webfetch", "open("):
        assert word not in src.split('"""', 2)[2], word
