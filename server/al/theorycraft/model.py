"""Typed, read-only view of a Path of Building PoE2 build XML (TC-CODE).

The Build keeps the exact XML it was parsed from (`raw_xml`), so
`to_code()` is lossless; the typed fields are a view for the dashboard and
the item evaluator, never written back (decision 0004, adjudicator ruling
F5 2026-11-16). Element and attribute names follow the publicly observed
PoB2 export (research 0010 section 1); unknown elements are ignored, a
missing optional field reads as None / empty, never as an error.

Root element: `PathOfBuilding2` (PoB2) or `PathOfBuilding` (older layout).
Read: Build (level, className, ascendClassName, targetVersion,
mainSocketGroup, PlayerStat), Tree / Spec (activeSpec, nodes, URL,
Sockets), Skills (SkillSet or flat Skill, Gem), Items (Item text, ItemSet
or flat Slot), Notes.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from . import codec

ROOTS = ("PathOfBuilding2", "PathOfBuilding")
NO_ASCENDANCY = ("", "None")
# PoB gear slot names (TC-EVAL slot mapping). Flask / charm names follow the
# PoB numbering; jewels sit in tree sockets, not in a gear slot.
SLOTS = ("Weapon 1", "Weapon 2", "Helmet", "Body Armour", "Gloves", "Boots",
         "Amulet", "Ring 1", "Ring 2", "Belt", "Flask 1", "Flask 2",
         "Charm 1", "Charm 2", "Charm 3")


class BuildError(ValueError):
    """The XML is not a readable PoB build."""


def _int(value, default=None):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _num(value):
    """int, float, or the original text when not numeric."""
    text = (value or "").strip()
    for conv in (int, float):
        try:
            return conv(text)
        except ValueError:
            pass
    return text


def _bool(value, default=True):
    if value is None:
        return default
    return str(value).strip().lower() not in ("false", "0", "no", "")


@dataclass(frozen=True)
class Gem:
    name: str
    skill_id: str = None
    level: int = None
    quality: int = None
    enabled: bool = True

    def to_dict(self):
        return {"name": self.name, "skill_id": self.skill_id, "level": self.level,
                "quality": self.quality, "enabled": self.enabled}


@dataclass(frozen=True)
class SkillGroup:
    gems: tuple = ()
    enabled: bool = True
    slot: str = None
    label: str = None

    def to_dict(self):
        return {"enabled": self.enabled, "slot": self.slot, "label": self.label,
                "gems": [g.to_dict() for g in self.gems]}


@dataclass(frozen=True)
class TreeSpec:
    title: str = None
    tree_version: str = None
    nodes: tuple = ()
    url: str = None
    jewels: dict = field(default_factory=dict)  # node id -> item id

    def to_dict(self, tree=None):
        """`tree`: optional treedata.TreeData; when given, `named_nodes`
        resolves the node ids to names (DATA-TREE-SRC) and `tree_match`
        reports {known, total, ok}; when the ids mostly miss the tree
        (DATA-TREE-IDS guard) `named_nodes` is left out. Without a tree the
        dict is unchanged."""
        out = {"title": self.title, "tree_version": self.tree_version,
               "nodes": list(self.nodes), "node_count": len(self.nodes),
               "url": self.url, "jewels": {str(k): v for k, v in self.jewels.items()}}
        if tree is not None:
            match = tree.id_match(self.nodes)
            out["tree_match"] = match
            if match["ok"]:
                out["named_nodes"] = tree.resolve(self.nodes)
        return out


@dataclass(frozen=True)
class Item:
    id: int
    text: str
    rarity: str = None
    name: str = None
    base: str = None

    def to_dict(self):
        return {"id": self.id, "rarity": self.rarity, "name": self.name,
                "base": self.base, "text": self.text}


def _item(item_id, text):
    """Rarity / name / base from PoB's item text header lines."""
    lines = [ln.strip() for ln in (text or "").strip().splitlines() if ln.strip()]
    rarity = name = base = None
    if lines and lines[0].lower().startswith("rarity:"):
        rarity = lines[0].split(":", 1)[1].strip().upper() or None
        rest = lines[1:]
        # NORMAL and MAGIC items carry one header line (the base / full name);
        # RARE and UNIQUE carry a name line then the base line.
        if rarity in ("RARE", "UNIQUE") and len(rest) >= 2:
            name, base = rest[0], rest[1]
        elif rest:
            base = rest[0]
    return Item(id=item_id, text=(text or "").strip("\n"), rarity=rarity, name=name, base=base)


@dataclass(frozen=True)
class Build:
    raw_xml: str
    class_name: str = None
    ascendancy: str = None
    level: int = None
    target_version: str = None
    main_skill_index: int = None  # PoB mainSocketGroup, 1-based
    stats: dict = field(default_factory=dict)
    specs: tuple = ()
    active_spec_index: int = None  # 0-based into specs
    skills: tuple = ()
    items: dict = field(default_factory=dict)  # item id -> Item
    gear: dict = field(default_factory=dict)  # slot name -> Item
    notes: str = ""

    @property
    def active_spec(self):
        if self.active_spec_index is None:
            return None
        return self.specs[self.active_spec_index]

    def to_code(self):
        return codec.encode(self.raw_xml)

    def equipped(self, slot):
        """The Item in a gear slot (case-insensitive name), or None."""
        want = (slot or "").strip().lower()
        for name, item in self.gear.items():
            if name.lower() == want:
                return item
        return None

    def to_dict(self, tree_data=None):
        """JSON-ready view (no raw XML; the code is the export). `tree_data`
        (optional treedata.TreeData) adds node names to the tree view."""
        tree = self.active_spec
        return {"class_name": self.class_name, "ascendancy": self.ascendancy,
                "level": self.level, "target_version": self.target_version,
                "main_skill_index": self.main_skill_index,
                "stats": dict(self.stats),
                "tree": tree.to_dict(tree_data) if tree else None,
                "spec_titles": [s.title for s in self.specs],
                "gear": {slot: it.to_dict() for slot, it in self.gear.items()},
                "skills": [s.to_dict() for s in self.skills],
                "notes": self.notes}


def _root(xml):
    if not isinstance(xml, str):
        raise BuildError("build XML must be text")
    head = xml[:4096].upper()
    if "<!DOCTYPE" in head or "<!ENTITY" in xml.upper():
        raise BuildError("DTDs are not allowed in build XML")
    try:
        root = ET.fromstring(xml.encode(codec.ENCODING, codec.ERRORS))
    except ET.ParseError as e:
        raise BuildError(f"bad build XML: {e}") from e
    if root.tag not in ROOTS:
        raise BuildError(f"not a Path of Building build (root {root.tag!r})")
    return root


def _specs(root):
    tree = root.find("Tree")
    if tree is None:
        return (), None
    specs = []
    for sp in tree.findall("Spec"):
        nodes = tuple(n for n in (_int(x) for x in (sp.get("nodes") or "").split(","))
                      if n is not None)
        url_el = sp.find("URL")
        url = (url_el.text or "").strip() or None if url_el is not None else None
        jewels = {}
        for so in sp.iter("Socket"):
            node, item = _int(so.get("nodeId")), _int(so.get("itemId"))
            if node is not None and item:
                jewels[node] = item
        specs.append(TreeSpec(title=sp.get("title"), tree_version=sp.get("treeVersion"),
                              nodes=nodes, url=url, jewels=jewels))
    if not specs:
        return (), None
    active = _int(tree.get("activeSpec"), 1)
    idx = active - 1 if 1 <= active <= len(specs) else len(specs) - 1
    return tuple(specs), idx


def _active_set(parent, set_tag, attr):
    """The active SkillSet / ItemSet, or the parent itself (flat layout)."""
    sets = parent.findall(set_tag)
    if not sets:
        return parent
    want = parent.get(attr)
    for s in sets:
        if s.get("id") == want:
            return s
    return sets[0]


def _skills(root):
    skills = root.find("Skills")
    if skills is None:
        return ()
    holder = _active_set(skills, "SkillSet", "activeSkillSet")
    out = []
    for sk in holder.findall("Skill"):
        gems = tuple(Gem(name=g.get("nameSpec") or g.get("skillId") or "",
                         skill_id=g.get("skillId"), level=_int(g.get("level")),
                         quality=_int(g.get("quality")), enabled=_bool(g.get("enabled")))
                     for g in sk.findall("Gem"))
        out.append(SkillGroup(gems=gems, enabled=_bool(sk.get("enabled")),
                              slot=sk.get("slot") or None, label=sk.get("label") or None))
    return tuple(out)


def _items(root):
    items_el = root.find("Items")
    if items_el is None:
        return {}, {}
    items = {}
    for it in items_el.findall("Item"):
        item_id = _int(it.get("id"))
        if item_id is not None:
            items[item_id] = _item(item_id, "".join(it.itertext()))
    holder = _active_set(items_el, "ItemSet", "activeItemSet")
    gear = {}
    for slot in holder.findall("Slot"):
        item = items.get(_int(slot.get("itemId"), 0))
        if slot.get("name") and item is not None:
            gear[slot.get("name")] = item
    return items, gear


def parse(xml):
    """A Build from PoB build XML. Raises BuildError."""
    root = _root(xml)
    b = root.find("Build")
    if b is None:
        raise BuildError("no Build element")
    level = b.get("level")
    if level is not None and _int(level) is None:
        raise BuildError("Build level is not a number")
    stats = {}
    for ps in b.findall("PlayerStat"):
        if ps.get("stat"):
            stats[ps.get("stat")] = _num(ps.get("value"))
    asc = b.get("ascendClassName")
    specs, spec_idx = _specs(root)
    items, gear = _items(root)
    notes_el = root.find("Notes")
    return Build(raw_xml=xml, class_name=b.get("className") or None,
                 ascendancy=None if asc in NO_ASCENDANCY else asc,
                 level=_int(level), target_version=b.get("targetVersion"),
                 main_skill_index=_int(b.get("mainSocketGroup")), stats=stats,
                 specs=specs, active_spec_index=spec_idx, skills=_skills(root),
                 items=items, gear=gear,
                 notes=("".join(notes_el.itertext()).strip() if notes_el is not None else ""))


def from_code(code):
    """A Build from a share code. Raises codec.CodeError or BuildError."""
    return parse(codec.decode(code))
