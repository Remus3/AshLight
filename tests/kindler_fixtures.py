"""Synthetic inputs for the KINDLER-DATA tests (decision 0081).

Hand-written by AshLight: a tiny passive tree in the shape of GGG's public
tree export (nodes keyed by skill id with `out` / `in` edges,
`classStartIndex`, `ascendancyId`, `isAscendancyStart`), a tiny gems
snapshot and a tiny base_items snapshot in the repoe-fork style, and
archetype template documents. Every
name, id and number is invented; nothing is copied from a game file or
another tool.
"""

import copy


def _node(skill, name, out=(), into=(), **extra):
    doc = {"skill": skill, "name": name, "stats": [],
           "out": [str(o) for o in out], "in": [str(i) for i in into]}
    doc.update(extra)
    return doc


def tree_doc():
    """Warrior start 100 -> 101 -> 102 -> 103 -> 104, 101 -> 105 -> 106;
    110 is in the tree but not linked to anything; Witch start 200 -> 201;
    the Titan ascendancy start 300 hangs off 100, 300 -> 301 -> 302."""
    nodes = {
        "root": {"out": ["100", "200"], "in": []},
        "100": _node(100, "WARRIOR", out=(101, 300), into=(), classStartIndex=[0]),
        "101": _node(101, "Strength", out=(102, 105), into=(100,)),
        "102": _node(102, "Life", out=(103,), into=(101,)),
        "103": _node(103, "Armour", out=(104,), into=(102,)),
        "104": _node(104, "Heavy Blows", out=(), into=(103,), isNotable=True),
        "105": _node(105, "Melee Damage", out=(106,), into=(101,)),
        "106": _node(106, "Stun", out=(), into=(105,)),
        "110": _node(110, "Island", out=(), into=()),
        "200": _node(200, "WITCH", out=(201,), into=(), classStartIndex=[1]),
        "201": _node(201, "Intelligence", out=(), into=(200,)),
        "300": _node(300, "Titan", out=(301,), into=(100,),
                     ascendancyId="Warrior1", isAscendancyStart=True),
        "301": _node(301, "Stone Skin", out=(302,), into=(300,),
                     ascendancyId="Warrior1"),
        "302": _node(302, "Giant Blood", out=(), into=(301,),
                     ascendancyId="Warrior1", isNotable=True),
    }
    return {"classes": [
        {"name": "Warrior", "ascendancies": [{"id": "Warrior1", "name": "Titan"}]},
        {"name": "Witch", "ascendancies": [{"id": "Witch1", "name": "Pyromancer"}]},
    ], "nodes": nodes}


def gems_doc():
    """repoe-fork style: keyed by item id, display name and level inside."""
    return {
        "Metadata/Items/Gems/SkillGemHammerSwing": {
            "display_name": "Hammer Swing", "is_support": False,
            "requirements": {"level": 1}},
        "Metadata/Items/Gems/SkillGemGroundCrack": {
            "base_item": {"display_name": "Ground Crack"},
            "per_level": {"1": {"requirements": {"level": 4}},
                          "2": {"requirements": {"level": 7}}}},
        "Metadata/Items/Gems/SupportGemBrute": {
            "display_name": "Brute Force", "is_support": True,
            "requirements": {"level": 3}},
        "Metadata/Items/Gems/SupportGemEcho": {
            "display_name": "Echo Strike", "is_support": True},
        "Metadata/Items/Gems/SkillGemWarCry": {
            "display_name": "War Cry", "requirements": {"level": 10}},
    }


def bases_doc():
    """repoe-fork base_items style: keyed by item id, name, item class,
    release state and the base's own requirements (KINDLER-WEAPON-BASE)."""
    def base(name, cls, level, state="released"):
        return {"name": name, "item_class": cls, "release_state": state,
                "requirements": {"level": level, "strength": 0,
                                 "dexterity": 0, "intelligence": 0}}
    return {
        "Metadata/Items/Weapons/TwoHandMaceA": base("Oak Mallet", "Two Hand Mace", 1),
        "Metadata/Items/Weapons/TwoHandMaceB": base("Iron Maul", "Two Hand Mace", 30),
        "Metadata/Items/Weapons/BowA": base("Twig Bow", "Bow", 1),
        "Metadata/Items/Weapons/WandA": base("Ash Wand", "Wand", 1),
        "Metadata/Items/Weapons/MaceUnreleased": base("Glass Mallet", "Two Hand Mace", 1,
                                                      state="unreleased"),
        "Metadata/Items/Amulets/AmuletA": base("Bead Amulet", "Amulet", 1),
    }


CHECKED = "2026-11-23"


def stage(**over):
    doc = {
        "id": "early",
        "label": "Early acts",
        "trigger": {"kind": "level", "min": 1, "max": 6},
        "level": 6,
        "skills": [{"name": "Hammer Swing", "sockets": 2,
                    "supports": ["Brute Force"]}],
        "gems": [{"name": "Ground Crack", "action": "pick", "level": 4}],
        "passives": [101, 102, 103],
        "focus": {"Weapon 1": ["physical damage", "attack speed"],
                  "Boots": ["movement speed", "life"]},
        "src": "authored for the tests",
        "checked": CHECKED,
    }
    doc.update(over)
    return doc


def template(**over):
    doc = {
        "id": "warrior_hammer",
        "label": "Hammer warrior",
        "class": "Warrior",
        "ascendancy": "Titan",
        "toggles": ["melee"],
        "defence": "life",
        "weapon": "Oak Mallet",
        "stages": [
            stage(),
            stage(id="mid", label="Later acts",
                  trigger={"kind": "act", "act": 2}, level=12,
                  skills=[{"name": "Ground Crack", "sockets": 3,
                           "supports": ["Brute Force", "Echo Strike"]}],
                  gems=[{"name": "Ground Crack", "action": "swap",
                         "for": "Hammer Swing"},
                        {"name": "War Cry", "action": "pick"}],
                  passives=[104, 105, 106],
                  ascendancy={"trial": 1, "nodes": [301, 302]}),
            stage(id="maps", label="Maps", trigger={"kind": "area_level",
                                                    "min": 65, "max": 80},
                  level=20, gems=[{"name": "War Cry", "action": "drop"}],
                  passives=[], focus={"Body Armour": ["life"]}),
        ],
        "src": "authored for the tests",
        "checked": CHECKED,
    }
    doc.update(over)
    return doc


def table_doc(*templates):
    return {"schema": 1,
            "templates": [copy.deepcopy(t) for t in (templates or (template(),))]}
