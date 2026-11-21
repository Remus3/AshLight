"""Character JSON paste import (ROADMAP TC-JSON, decision 0004 item 4).

Input: a character object in the shape of GGG's documented API reference
types Character / Item (https://www.pathofexile.com/developer/docs/reference,
research 0010 section 2), either bare or wrapped as {"character": {...}} the
way `GET /character/<realm>/<name>` answers. AshLight never calls that
endpoint (no OAuth client yet); the user pastes JSON they already have.

The JSON is turned into Path of Building build XML and read by `model.parse`,
so a JSON paste and a PoB code land in the SAME typed model, persist the same
way (as a share code) and export the same "copy code for PoB". Fields read:

- class (a PoE2 ascendancy name maps to its base class; an internal id such
  as an ascendancy id of the tree export maps through the optional
  `class_names` callable first), level
- passives.hashes plus PoE2 passives.specialisations set1..set3 -> tree nodes;
  each set's nodes are also kept as a PoB `WeaponSet<n>` element of the Spec
  (weapon-set membership, the form PoB writes itself)
- equipment[] (inventoryId -> PoB slot; Flask positions above 1 are charms)
  and jewels[] -> items; item text from rarity / frameType, name, typeLine,
  ilvl and the mod lists (research 0035 F7 / F9, TC-CHARJSON-SHAPES): a mod
  is a string or an ItemMod object (its `description`; flags are not
  needed for the line), PoE2 runeMods and bondedMods included, and the
  fields GGG removed in API entry 3.29.0 still read for old pastes
- PoE2 skills[] (gem items, supports in socketedItems) -> skill groups

Every other field is ignored, never fatal. A field of the wrong type reads as
missing. Jewel socket placement needs tree data (TC-SNAP) and is not mapped.
"""

import json
import xml.etree.ElementTree as ET

from . import model
from . import treedata

MAX_JSON_CHARS = 2 * 1024 * 1024

# PoE2 base classes (game facts, names only). UTIL-1.0-READY: Duelist and
# Shadow join at PoE2 1.0 (2026-12-11, research 0018); their ascendancy
# names are not published yet, so an unknown class name passes through as
# the class name unchanged, never an error.
BASE_CLASSES = ("Warrior", "Ranger", "Huntress", "Mercenary", "Sorceress", "Witch",
                "Monk", "Druid", "Duelist", "Shadow")

# PoE2 ascendancy -> base class (game facts, names only).
ASCENDANCY_CLASS = {
    "Titan": "Warrior", "Warbringer": "Warrior", "Smith of Kitava": "Warrior",
    "Deadeye": "Ranger", "Pathfinder": "Ranger",
    "Amazon": "Huntress", "Ritualist": "Huntress",
    "Witchhunter": "Mercenary", "Gemling Legionnaire": "Mercenary",
    "Tactician": "Mercenary",
    "Stormweaver": "Sorceress", "Chronomancer": "Sorceress",
    "Disciple of Varashta": "Sorceress",
    "Infernalist": "Witch", "Blood Mage": "Witch", "Lich": "Witch",
    "Invoker": "Monk", "Acolyte of Chayula": "Monk",
    "Oracle": "Druid", "Shaman": "Druid",
}

# GGG inventoryId -> PoB slot name. Flasks / charms are indexed by x: a
# Flask at x 0 / 1 is Flask 1 / 2, a Flask at x above 1 is a charm (x 2 is
# Charm 1), the way Path of Building's own importer reads the API answer.
SLOTS = {
    "Weapon": "Weapon 1", "Offhand": "Weapon 2",
    "Weapon2": "Weapon 1 Swap", "Offhand2": "Weapon 2 Swap",
    "Helm": "Helmet", "BodyArmour": "Body Armour", "Gloves": "Gloves",
    "Boots": "Boots", "Belt": "Belt", "Amulet": "Amulet",
    "Ring": "Ring 1", "Ring2": "Ring 2", "Ring3": "Ring 3",
}
INDEXED_SLOTS = {"Flask": "Flask", "Charm": "Charm"}

FLASK_POSITIONS = 2  # x 0 and 1 are flasks; higher x on a Flask is a charm

FRAME_RARITY = {0: "NORMAL", 1: "MAGIC", 2: "RARE", 3: "UNIQUE"}
# Mod lists in item-text order. Each entry may be a string (the old shape)
# or an ItemMod object (API entry 3.29.0: `description` plus flags).
# fracturedMods, craftedMods, desecratedMods and mutatedMods were removed
# from the API in entry 3.29.0 (their mods now sit in explicitMods with a
# flag); they stay here so an old paste keeps its mods.
LEGACY_MOD_FIELDS = ("fracturedMods", "craftedMods", "desecratedMods", "mutatedMods")
MOD_FIELDS = ("enchantMods", "runeMods", "bondedMods", "implicitMods", "fracturedMods",
              "explicitMods", "craftedMods", "desecratedMods", "mutatedMods")
SPEC_SETS = ("set1", "set2", "set3")


class CharJsonError(model.BuildError):
    """The text is JSON but not a readable character."""


def looks_like_json(text):
    return isinstance(text, str) and text.lstrip()[:1] == "{"


def _dict(v):
    return v if isinstance(v, dict) else {}


def _list(v):
    return v if isinstance(v, list) else []


def _str(v):
    return v.strip() if isinstance(v, str) and v.strip() else None


def _int(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        digits = "".join(ch for ch in v if ch.isdigit())
        return int(digits) if digits and len(digits) < 12 else None
    return None


def _prop(item, name):
    """First value of a named property (e.g. Level "19", Quality "+20%")."""
    for p in _list(item.get("properties")):
        p = _dict(p)
        if p.get("name") == name:
            for pair in _list(p.get("values")):
                if isinstance(pair, list) and pair:
                    return _int(pair[0])
    return None


def _rarity(item):
    r = _str(item.get("rarity"))
    if r:
        return r.upper()
    fr = item.get("frameType")
    return FRAME_RARITY.get(fr) if isinstance(fr, int) and not isinstance(fr, bool) else None


def _clean_line(line):
    return " ".join(line.split())


def _mod_text(mod):
    """The text of one mod entry: a string, or an ItemMod object's
    `description`; anything else (or blank) is None."""
    if isinstance(mod, dict):
        mod = mod.get("description")
    return mod if isinstance(mod, str) and mod.strip() else None


def mod_lines(item):
    """Every mod line of one GGG Item, in MOD_FIELDS order."""
    out = []
    for fld in MOD_FIELDS:
        for mod in _list(item.get(fld)):
            text = _mod_text(mod)
            if text:
                out.extend(_clean_line(m) for m in text.splitlines() if m.strip())
    return out


def item_text(item):
    """PoB-style item text for one GGG Item."""
    rarity = _rarity(item) or "NORMAL"
    name = _str(item.get("name"))
    base = _str(item.get("typeLine")) or _str(item.get("baseType")) or "Unknown Item"
    lines = [f"Rarity: {rarity}"]
    if rarity in ("RARE", "UNIQUE"):
        lines.append(_clean_line(name or base))
    lines.append(_clean_line(base))
    ilvl = _int(item.get("ilvl"))
    if ilvl is not None:
        lines.append(f"Item Level: {ilvl}")
    lines.extend(mod_lines(item))
    return "\n".join(lines)


def _character(doc):
    if not isinstance(doc, dict):
        raise CharJsonError("character JSON must be an object")
    inner = doc.get("character")
    if isinstance(inner, dict):
        doc = inner
    if not any(k in doc for k in ("class", "level", "passives", "equipment", "skills")):
        raise CharJsonError("JSON is not a character (no class, level, passives, "
                            "equipment or skills)")
    return doc


def _weapon_sets(passives):
    """[(set number, [node ids])] for the non-empty specialisation sets."""
    spec = _dict(passives.get("specialisations"))
    out = []
    for i, key in enumerate(SPEC_SETS, start=1):
        seen, ids = set(), []
        for h in _list(spec.get(key)):
            n = _int(h) if not isinstance(h, str) else None
            if n is not None and n not in seen:
                seen.add(n)
                ids.append(n)
        if ids:
            out.append((i, ids))
    return out


def _nodes(passives):
    seen, out = set(), []
    lists = [_list(passives.get("hashes"))]
    spec = _dict(passives.get("specialisations"))
    lists.extend(_list(spec.get(k)) for k in SPEC_SETS)
    for lst in lists:
        for h in lst:
            n = _int(h) if not isinstance(h, str) else None
            if n is not None and n not in seen:
                seen.add(n)
                out.append(n)
    return out


def _slot(item):
    inv = _str(item.get("inventoryId"))
    if inv in SLOTS:
        return SLOTS[inv]
    if inv in INDEXED_SLOTS:
        x = _int(item.get("x")) or 0
        if inv == "Flask" and x >= FLASK_POSITIONS:
            return f"Charm {x - FLASK_POSITIONS + 1}"
        return f"{INDEXED_SLOTS[inv]} {x + 1}"
    return None


def _class_map(class_names):
    """The internal id -> display name mapping from the optional callable,
    or {} when there is none or it fails (never fatal, no read of its own)."""
    if not callable(class_names):
        return {}
    try:
        got = class_names()
    except Exception:  # a missing or broken cache reads as no map
        return {}
    return got if isinstance(got, dict) else {}


def _classes(cls, class_names=None):
    """(base class, ascendancy or "None") for the `class` field. A display
    name is used as is; an internal id (e.g. an ascendancy id of the tree
    export) maps through `class_names` first; an unknown name passes
    through as the class name."""
    if (cls and cls not in ASCENDANCY_CLASS and cls not in BASE_CLASSES
            and not treedata.class_of(cls)):
        mapped = _str(_class_map(class_names).get(cls))
        if mapped:
            cls = mapped
    # TC-ASC-FROM-TREE: the cached tree export first, the table as fallback
    base = treedata.class_of(cls) or ASCENDANCY_CLASS.get(cls)
    if base:
        return base, cls
    return cls, "None"


def _gem(parent, gem):
    name = _str(gem.get("typeLine")) or _str(gem.get("baseType")) or _str(gem.get("name"))
    if not name:
        return
    attrs = {"nameSpec": name, "enabled": "true"}
    for key, prop in (("level", "Level"), ("quality", "Quality")):
        v = _prop(gem, prop)
        if v is not None:
            attrs[key] = str(v)
    ET.SubElement(parent, "Gem", attrs)


def to_xml(doc, class_names=None):
    """PoB build XML (str) for a parsed character JSON object.

    `class_names`: optional callable returning a dict of internal class /
    ascendancy id -> display name (the cached tree export's names); called
    only for a `class` value that is not already a known name."""
    ch = _character(doc)
    base_cls, asc = _classes(_str(ch.get("class")), class_names)
    root = ET.Element("PathOfBuilding2")
    battrs = {}
    level = _int(ch.get("level"))
    if level is not None:
        battrs["level"] = str(level)
    if base_cls:
        battrs["className"] = base_cls
    battrs["ascendClassName"] = asc
    ET.SubElement(root, "Build", battrs)

    passives = _dict(ch.get("passives"))
    nodes = _nodes(passives)
    tree = ET.SubElement(root, "Tree", {"activeSpec": "1"})
    spec = ET.SubElement(tree, "Spec", {"title": "Imported",
                                        "nodes": ",".join(map(str, nodes))})
    for num, ids in _weapon_sets(passives):
        ET.SubElement(spec, f"WeaponSet{num}", {"nodes": ",".join(map(str, ids))})

    skills_el = ET.SubElement(root, "Skills")
    for sk in _list(ch.get("skills")):
        sk = _dict(sk)
        if not sk:
            continue
        group = ET.SubElement(skills_el, "Skill", {"enabled": "true"})
        _gem(group, sk)
        for sup in _list(sk.get("socketedItems")):
            if isinstance(sup, dict):
                _gem(group, sup)

    items_el = ET.SubElement(root, "Items")
    slots = []
    next_id = 1
    for src, slotted in ((_list(ch.get("equipment")), True), (_list(ch.get("jewels")), False)):
        for it in src:
            if not isinstance(it, dict):
                continue
            el = ET.SubElement(items_el, "Item", {"id": str(next_id)})
            el.text = "\n" + item_text(it) + "\n"
            slot = _slot(it) if slotted else None
            if slot and slot not in dict(slots):
                slots.append((slot, next_id))
            next_id += 1
    for slot, item_id in slots:
        ET.SubElement(items_el, "Slot", {"name": slot, "itemId": str(item_id)})

    ET.indent(root, "\t")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        root, encoding="unicode") + "\n"


def loads(text):
    """The character object from pasted JSON text. Raises CharJsonError."""
    if not isinstance(text, str):
        raise CharJsonError("character JSON must be text")
    if len(text) > MAX_JSON_CHARS:
        raise CharJsonError("character JSON too long")
    try:
        return json.loads(text)
    except (ValueError, RecursionError) as e:
        raise CharJsonError("not valid JSON") from e


def from_json(text, class_names=None):
    """A model.Build from pasted character JSON. Raises CharJsonError.
    `class_names`: see to_xml."""
    return model.parse(to_xml(loads(text), class_names))
