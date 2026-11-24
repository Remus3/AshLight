"""KINDLER-DATA (decision 0081 points 2, 6 and 11 to 16): Kindler's
archetype template table and its checked loader.

The table is `server/al/data/archetypes.json`, AshLight-authored (the
file itself is KINDLER-TEMPLATES). It is plain JSON data read by this
module, never run as code: every object has a fixed key allow-list, so no
field can carry an expression. Schema 1:

    {"schema": 1, "templates": [<template>, ...]}

    template: {"id", "label", "class", "ascendancy" (name or null),
               "toggles": subset of TOGGLES, "defence" (DEFENCES or absent),
               "weapon" (optional: one authored weapon base name, KINDLER-
               WEAPON-BASE; an attack template, toggle melee or bow, needs
               one so Path of Building has a weapon to attack with),
               "stages": [<stage>, ...], "src", "checked" (YYYY-MM-DD)}
    stage:    {"id", "label", "trigger", "level" (the character level the
               stage plans for; its point budget), "bonus_points" (optional,
               authored passive points beyond levels, e.g. from quests),
               "skills": [{"name", "sockets", "supports": [names]}],
               "gems": [{"name", "action": pick|swap|drop, "level"
                         (optional authored), "for" (swap only: the gem
                         it replaces)}],
               "passives": [node ids, in allocation order; each stage
                            continues the earlier stages' list],
               "ascendancy": null or {"trial": 1..4, "nodes": [ids]}
                             ("after your Nth Ascendancy trial"),
               "focus": {slot: [stats, highest priority first]},
               "src", "checked"}
    trigger:  {"kind": "level", "min", "max"} | {"kind": "act", "act"} |
              {"kind": "zone", "zone": <world_areas id>} |
              {"kind": "area_level", "min", "max"}

Three layers:
- `validate` / `load` / `watch`: the structural check; the tracked file is
  hot reloaded (decision 0042), a bad edit keeps the last good table with
  a Checks note, a missing file reads as no table.
- `resolve`: run time. Node ids missing from the cached GGG tree export
  are dropped with a note, never guessed (decision 0034); each gem carries
  checked=True and the snapshot level when the cached repoe-fork gems
  snapshot names it, else checked=False and the authored level (point
  16). The weapon base reads checked=True with its item class only when
  the cached repoe-fork base_items snapshot names it as a released weapon
  base; otherwise checked=False with a note, and the engine composes no
  weapon (never guessed). Set lookups only: no route search at run time
  (point 14). KINDLER-GEM-VARIANT: given the gem variants of the pinned
  PoB checkout's Gems.lua (theorycraft.pobtext, read as text), a skill gem
  whose name PoB holds under several weapon variants gets "skill_id": the
  one variant whose weapon list is exactly the checked weapon's item
  class, else the one variant that lists it (skill_id()). With no checked
  weapon, no variant data or no single fit the key is absent and the
  composer writes the gem by name only, as before (never guessed).
- `check`: the validator, for tests and the template package only. It
  runs the breadth-first connectivity check from the class start (and the
  ascendancy start), the allocation-order check and the point budget at
  each stage's level, and refuses gem names the snapshot lacks (point 13).
  It also refuses an attack template without a weapon base, and with the
  base_items snapshot a weapon base the snapshot does not name, of an item
  class that does not fit the template's toggle, or needing a higher level
  than the first stage plans for.

This module reads the tracked table and the three sidecar caches only. It
never fetches, never reads the game, the clipboard or the screen, and
sends nothing anywhere.
"""

import json
import re
from collections import deque
from pathlib import Path

from .. import hotreload
from ..text import kindler as words
from . import datacredit, model, pobtext, treedata

PATH = Path(__file__).resolve().parent.parent / "data" / "archetypes.json"
GEMS_FILE = "gems.json"
BASES_FILE = "base_items.json"
BASES_MAX_BYTES = 64 * 1024 * 1024
MAX_BYTES = 1024 * 1024
GEMS_MAX_BYTES = 64 * 1024 * 1024
SCHEMA = 1
MAX_TEMPLATES = 64
MAX_STAGES = 16
MAX_SKILLS = 6
MAX_SOCKETS = 5          # support sockets a stage may author per skill
MAX_GEM_STEPS = 16
MAX_PASSIVES = 160       # per stage
MAX_ASC_NODES = 16
MAX_TRIALS = 4
MAX_FOCUS_STATS = 12
MAX_BONUS_POINTS = 40
MIN_LEVEL, MAX_LEVEL = 1, 100
MAX_ACT = 10
LABEL_MAX = 40
NAME_MAX = 60
STAT_MAX = 80
TEXT_MAX = 200
TOGGLES = ("melee", "spell", "minion", "bow", "crit")
DEFENCES = ("life", "es", "hybrid")
ACTIONS = ("pick", "swap", "drop")
# KINDLER-WEAPON-BASE: the toggles whose skills attack with a weapon, and
# the base_items item classes that fit each one (repoe-fork class names,
# server/al/text/kindler.py). Only attack weapon classes are indexed; a
# caster weapon (wand, staff, sceptre) is no attack template's base.
ATTACK_TOGGLES = ("melee", "bow")
MELEE_CLASSES = words.MELEE_CLASSES
RANGED_CLASSES = words.RANGED_CLASSES
WEAPON_CLASSES = MELEE_CLASSES + RANGED_CLASSES
TOGGLE_CLASSES = {"melee": MELEE_CLASSES, "bow": (words.BOW_CLASS,)}
TRIGGER_KINDS = ("level", "act", "zone", "area_level")

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ID = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_ZONE = re.compile(r"^[A-Za-z0-9_]{1,40}$")
_SLOTS = {s.lower(): s for s in model.SLOTS}

_TEMPLATE_KEYS = {"id", "label", "class", "ascendancy", "toggles", "defence",
                  "weapon", "stages", "src", "checked"}
_STAGE_KEYS = {"id", "label", "trigger", "level", "bonus_points", "skills",
               "gems", "passives", "ascendancy", "focus", "src", "checked"}
_SKILL_KEYS = {"name", "sockets", "supports"}
_GEM_KEYS = {"name", "action", "level", "for"}
_ASC_KEYS = {"trial", "nodes"}
_TRIGGER_KEYS = {"level": {"kind", "min", "max"}, "act": {"kind", "act"},
                 "zone": {"kind", "zone"}, "area_level": {"kind", "min", "max"}}


# --- structural check ---------------------------------------------------

def _int(v, lo, hi):
    return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi


def _text(v, limit=TEXT_MAX):
    return (isinstance(v, str) and v.strip() != "" and v.isascii()
            and v.isprintable() and len(v) <= limit)


def _keys(obj, allowed, where):
    if not isinstance(obj, dict):
        raise ValueError(f"{where} is not an object")
    extra = sorted(set(obj) - allowed)
    if extra:
        raise ValueError(f"{where} has an unknown field: {extra[0]}")


def _provenance(obj, where):
    if not _text(obj.get("src")):
        raise ValueError(f"{where} has no src")
    if not (isinstance(obj.get("checked"), str) and _DATE.match(obj["checked"])):
        raise ValueError(f"{where} has no checked date")


def _trigger(trig, where):
    w = f"{where} trigger"
    if not isinstance(trig, dict) or trig.get("kind") not in TRIGGER_KINDS:
        raise ValueError(f"{w} has no known kind")
    kind = trig["kind"]
    if set(trig) != _TRIGGER_KEYS[kind]:
        raise ValueError(f"{w} fields do not match its kind")
    if kind in ("level", "area_level"):
        lo, hi = trig["min"], trig["max"]
        if not (_int(lo, MIN_LEVEL, MAX_LEVEL) and _int(hi, MIN_LEVEL, MAX_LEVEL)
                and lo <= hi):
            raise ValueError(f"{w} has no valid level range")
    elif kind == "act":
        if not _int(trig["act"], 1, MAX_ACT):
            raise ValueError(f"{w} act is not 1 to {MAX_ACT}")
    elif not (isinstance(trig["zone"], str) and _ZONE.match(trig["zone"])):
        raise ValueError(f"{w} zone is not an area id")
    return dict(trig)


def _names(values, where, limit):
    if not (isinstance(values, list) and len(values) <= limit
            and all(_text(v, NAME_MAX) for v in values)):
        raise ValueError(f"{where} is not a list of gem names")
    if len({v.lower() for v in values}) != len(values):
        raise ValueError(f"{where} repeats a gem")
    return list(values)


def _skill(sk, where):
    _keys(sk, _SKILL_KEYS, where)
    if not _text(sk.get("name"), NAME_MAX):
        raise ValueError(f"{where} has no gem name")
    if not _int(sk.get("sockets"), 0, MAX_SOCKETS):
        raise ValueError(f"{where} sockets is not 0 to {MAX_SOCKETS}")
    supports = _names(sk.get("supports", []), f"{where} supports", MAX_SOCKETS)
    if len(supports) > sk["sockets"]:
        raise ValueError(f"{where} has more supports than sockets")
    return {"name": sk["name"], "sockets": sk["sockets"], "supports": supports}


def _gem_step(g, where):
    _keys(g, _GEM_KEYS, where)
    if not _text(g.get("name"), NAME_MAX):
        raise ValueError(f"{where} has no gem name")
    if g.get("action") not in ACTIONS:
        raise ValueError(f"{where} action is not one of {', '.join(ACTIONS)}")
    if "level" in g and not _int(g["level"], MIN_LEVEL, MAX_LEVEL):
        raise ValueError(f"{where} level is not {MIN_LEVEL} to {MAX_LEVEL}")
    if g["action"] == "swap":
        if not _text(g.get("for"), NAME_MAX):
            raise ValueError(f"{where} swap has no for gem")
    elif "for" in g:
        raise ValueError(f"{where} for belongs to a swap only")
    return {"name": g["name"], "action": g["action"], "level": g.get("level"),
            "for": g.get("for")}


def _ids(values, where, limit):
    if not (isinstance(values, list) and len(values) <= limit
            and all(_int(v, 0, 2 ** 31 - 1) for v in values)):
        raise ValueError(f"{where} is not a list of node ids")
    return list(values)


def _focus(focus, where):
    if not (isinstance(focus, dict) and len(focus) <= len(_SLOTS)):
        raise ValueError(f"{where} focus is not an object of slots")
    out = {}
    for slot, stats in focus.items():
        name = _SLOTS.get(slot.lower()) if isinstance(slot, str) else None
        if name is None:
            raise ValueError(f"{where} focus has an unknown slot")
        if name in out:
            raise ValueError(f"{where} focus repeats slot {name}")
        if not (isinstance(stats, list) and 0 < len(stats) <= MAX_FOCUS_STATS
                and all(_text(s, STAT_MAX) for s in stats)):
            raise ValueError(f"{where} focus {name} is not a list of stats")
        out[name] = [" ".join(s.split()).lower() for s in stats]
    return out


def _stage(st, where, seen):
    _keys(st, _STAGE_KEYS, where)
    if not (isinstance(st.get("id"), str) and _ID.match(st["id"])):
        raise ValueError(f"{where} has no valid id")
    if not _text(st.get("label"), LABEL_MAX):
        raise ValueError(f"{where} has no short label")
    _provenance(st, where)
    trig = _trigger(st.get("trigger"), where)
    if not _int(st.get("level"), MIN_LEVEL, MAX_LEVEL):
        raise ValueError(f"{where} level is not {MIN_LEVEL} to {MAX_LEVEL}")
    bonus = st.get("bonus_points", 0)
    if not _int(bonus, 0, MAX_BONUS_POINTS):
        raise ValueError(f"{where} bonus_points is not 0 to {MAX_BONUS_POINTS}")
    skills = st.get("skills", [])
    if not (isinstance(skills, list) and len(skills) <= MAX_SKILLS):
        raise ValueError(f"{where} skills is not a list")
    skills = [_skill(s, f"{where} skill {i}") for i, s in enumerate(skills, 1)]
    gems = st.get("gems", [])
    if not (isinstance(gems, list) and len(gems) <= MAX_GEM_STEPS):
        raise ValueError(f"{where} gems is not a list")
    gems = [_gem_step(g, f"{where} gem {i}") for i, g in enumerate(gems, 1)]
    passives = _ids(st.get("passives", []), f"{where} passives", MAX_PASSIVES)
    asc = st.get("ascendancy")
    if asc is not None:
        _keys(asc, _ASC_KEYS, f"{where} ascendancy")
        if not _int(asc.get("trial"), 1, MAX_TRIALS):
            raise ValueError(f"{where} ascendancy trial is not 1 to {MAX_TRIALS}")
        asc = {"trial": asc["trial"],
               "nodes": _ids(asc.get("nodes", []), f"{where} ascendancy nodes",
                             MAX_ASC_NODES)}
    for nid in passives + (asc["nodes"] if asc else []):
        if nid in seen:
            raise ValueError(f"{where} repeats passive {nid}")
        seen.add(nid)
    return {"id": st["id"], "label": st["label"], "trigger": trig,
            "level": st["level"], "bonus_points": bonus, "skills": skills,
            "gems": gems, "passives": passives, "ascendancy": asc,
            "focus": _focus(st.get("focus", {}), where),
            "src": st["src"], "checked": st["checked"]}


def _template(t, where):
    _keys(t, _TEMPLATE_KEYS, where)
    if not (isinstance(t.get("id"), str) and _ID.match(t["id"])):
        raise ValueError(f"{where} has no valid id")
    where = f"template {t['id']}"
    if not _text(t.get("label"), LABEL_MAX):
        raise ValueError(f"{where} has no short label")
    _provenance(t, where)
    if not _text(t.get("class"), NAME_MAX):
        raise ValueError(f"{where} has no class")
    asc = t.get("ascendancy")
    if asc is not None and not _text(asc, NAME_MAX):
        raise ValueError(f"{where} ascendancy is not a name")
    toggles = t.get("toggles")
    if not (isinstance(toggles, list) and toggles and all(x in TOGGLES for x in toggles)
            and len(set(toggles)) == len(toggles)):
        raise ValueError(f"{where} toggles is not a list from {', '.join(TOGGLES)}")
    if "defence" in t and t["defence"] not in DEFENCES:
        raise ValueError(f"{where} defence is not one of {', '.join(DEFENCES)}")
    weapon = t.get("weapon")
    if weapon is not None and not _text(weapon, NAME_MAX):
        raise ValueError(f"{where} weapon is not a base name")
    stages = t.get("stages")
    if not (isinstance(stages, list) and 0 < len(stages) <= MAX_STAGES):
        raise ValueError(f"{where} has no stages")
    seen, cleaned = set(), []
    for i, st in enumerate(stages, 1):
        cleaned.append(_stage(st, f"{where} stage {i}", seen))
    if len({s["id"] for s in cleaned}) != len(cleaned):
        raise ValueError(f"{where} repeats a stage id")
    trial = 0
    for s in cleaned:
        if s["ascendancy"] is not None:
            if s["ascendancy"]["trial"] < trial:
                raise ValueError(f"{where} stage {s['id']} ascendancy trial goes back")
            trial = s["ascendancy"]["trial"]
    if any(s["ascendancy"] for s in cleaned) and asc is None:
        raise ValueError(f"{where} has ascendancy nodes but no ascendancy")
    return {"id": t["id"], "label": t["label"], "class": t["class"],
            "ascendancy": asc, "toggles": list(toggles),
            "defence": t.get("defence"),
            "weapon": " ".join(weapon.split()) if weapon is not None else None,
            "stages": cleaned,
            "src": t["src"], "checked": t["checked"]}


def validate(doc):
    """The cleaned table, or ValueError naming the first problem."""
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise ValueError(f"schema is not {SCHEMA}")
    _keys(doc, {"schema", "templates"}, "the table")
    templates = doc.get("templates")
    if not (isinstance(templates, list) and 0 < len(templates) <= MAX_TEMPLATES):
        raise ValueError(f"templates is not a list of 1 to {MAX_TEMPLATES}")
    out = [_template(t, f"template {i}") for i, t in enumerate(templates, 1)]
    ids = [t["id"] for t in out]
    if len(set(ids)) != len(ids):
        raise ValueError("the table repeats template id "
                         + next(i for i in ids if ids.count(i) > 1))
    return {"schema": SCHEMA, "templates": out}


def load(path=PATH):
    """The validated table of `path`; raises on any problem (Watched then
    keeps the last good copy)."""
    p = Path(path)
    if p.stat().st_size > MAX_BYTES:
        raise ValueError(f"larger than {MAX_BYTES} bytes")
    return validate(json.loads(p.read_text(encoding="ascii")))


def watch(path=PATH, registry=None):
    """A hot-reloaded table for `path` (registry None: the core's)."""
    return hotreload.Watched(path, load, name=words.TABLE_NAME, default=dict,
                             registry=registry)


_watch = watch(PATH)


def table():
    """The current tracked table ({} when the file is missing)."""
    return _watch.get()


# --- caches: tree graph and gems index ------------------------------------

class TreeGraph:
    """Node ids, links and start nodes of one GGG tree export document."""

    def __init__(self, nodes, adj, class_starts, asc_starts, asc_class, asc_names):
        self.nodes = nodes                # set of node ids
        self.adj = adj                    # id -> set of linked ids
        self._class_starts = class_starts  # lower class name -> id
        self._asc_starts = asc_starts     # ascendancy name -> id
        self._asc_class = asc_class       # ascendancy name -> class name
        self._asc_of = asc_names          # node id -> ascendancy name

    def class_start(self, name):
        return self._class_starts.get(name.lower()) if isinstance(name, str) else None

    def asc_start(self, name):
        return self._asc_starts.get(name)

    def asc_class(self, name):
        return self._asc_class.get(name)

    def asc_of(self, node_id):
        return self._asc_of.get(node_id)


def _node_id(value):
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def tree_graph(doc):
    """TreeGraph from a decoded tree export; ValueError when it is not one.
    Links come from each node's `out` and `in` lists (both ways)."""
    tree = treedata.parse(doc)
    adj = {nid: set() for nid in tree.nodes}
    for key, raw in doc["nodes"].items():
        if not isinstance(raw, dict):
            continue
        nid = _node_id(raw.get("skill"))
        nid = _node_id(key) if nid is None else nid
        if nid not in adj:
            continue
        for field in ("out", "in"):
            links = raw.get(field)
            for other in links if isinstance(links, list) else ():
                oid = _node_id(other)
                if oid in adj and oid != nid:
                    adj[nid].add(oid)
                    adj[oid].add(nid)
    starts = {cls.lower(): nid for cls, nid in tree.class_starts().items()}
    asc_starts = {}
    for key, raw in doc["nodes"].items():
        if isinstance(raw, dict) and raw.get("isAscendancyStart") is True:
            nid = _node_id(raw.get("skill"))
            node = tree.nodes.get(nid if nid is not None else _node_id(key))
            if node is not None and node.ascendancy:
                asc_starts.setdefault(node.ascendancy, node.id)
    asc_of = {n.id: n.ascendancy for n in tree.nodes.values() if n.ascendancy}
    return TreeGraph(set(tree.nodes), adj, starts, asc_starts,
                     dict(tree.class_map), asc_of)


def _gem_level(entry):
    req = entry.get("requirements")
    if isinstance(req, dict) and _int(req.get("level"), MIN_LEVEL, MAX_LEVEL):
        return req["level"]
    per = entry.get("per_level")
    levels = []
    for row in per.values() if isinstance(per, dict) else ():
        req = row.get("requirements") if isinstance(row, dict) else None
        if isinstance(req, dict) and _int(req.get("level"), MIN_LEVEL, MAX_LEVEL):
            levels.append(req["level"])
    return min(levels) if levels else None


def _gem_name(entry):
    for holder in (entry, entry.get("base_item"), entry.get("active_skill")):
        if isinstance(holder, dict) and _text(holder.get("display_name"), NAME_MAX):
            return holder["display_name"]
    return None


def gem_index(doc):
    """{lower gem name: {"name", "level"}} from a repoe-fork style gems
    document (an object of entries with a display name, directly or under
    base_item / active_skill, and a level from requirements or the lowest
    per_level requirement). Unreadable entries are skipped."""
    out = {}
    for entry in doc.values() if isinstance(doc, dict) else ():
        if not isinstance(entry, dict):
            continue
        name = _gem_name(entry)
        if name is None:
            continue
        key = name.lower()
        level = _gem_level(entry)
        old = out.get(key)
        if old is None or (level is not None and (old["level"] is None
                                                  or level < old["level"])):
            out[key] = {"name": name, "level": level}
    return out


def load_gems(path):
    """gem_index of a cached gems snapshot, or None when it is missing,
    too large or unreadable (gems then read checked=False)."""
    p = Path(path)
    try:
        if p.stat().st_size > GEMS_MAX_BYTES:
            return None
        return gem_index(json.loads(p.read_bytes()))
    except (OSError, ValueError):
        return None


def gems_path(environ=None):
    return datacredit.cache_dir(environ) / GEMS_FILE


def base_index(doc):
    """{lower base name: {"name", "item_class", "level"}} of the released
    weapon bases (item class in WEAPON_CLASSES) of a parsed repoe-fork
    base_items document; level is the base's own required level (None when
    the entry names none; the lowest one when a name repeats). Unreadable
    entries are skipped."""
    out = {}
    for entry in doc.values() if isinstance(doc, dict) else ():
        if not isinstance(entry, dict) or entry.get("release_state") != "released":
            continue
        cls = entry.get("item_class")
        name = entry.get("name")
        if cls not in WEAPON_CLASSES or not _text(name, NAME_MAX):
            continue
        name = " ".join(name.split())
        req = entry.get("requirements")
        level = req.get("level") if isinstance(req, dict) else None
        level = level if _int(level, 0, MAX_LEVEL) else None
        old = out.get(name.lower())
        if old is None or (level is not None and (old["level"] is None
                                                  or level < old["level"])):
            out[name.lower()] = {"name": name, "item_class": cls, "level": level}
    return out


def load_bases(path):
    """base_index of a cached base_items snapshot, or None when it is
    missing, too large or unreadable (the weapon then reads checked=False)."""
    p = Path(path)
    try:
        if p.stat().st_size > BASES_MAX_BYTES:
            return None
        return base_index(json.loads(p.read_bytes()))
    except (OSError, ValueError):
        return None


def bases_path(environ=None):
    return datacredit.cache_dir(environ) / BASES_FILE


def default_bases(gems_file=None):
    """The base_items file beside a given gems file (both snapshots share
    one cache folder), else the cache's own."""
    return Path(gems_file).parent / BASES_FILE if gems_file else bases_path()


# --- run time: resolve ----------------------------------------------------

def _gem(name, gems, notes, where, authored=None):
    hit = gems.get(name.lower()) if gems is not None else None
    if hit is None:
        if gems is not None:
            notes.append(f"{where}: gem {name} is not in the gems snapshot")
        return {"name": name, "level": authored, "checked": False}
    level = hit["level"] if hit["level"] is not None else authored
    return {"name": hit["name"], "level": level, "checked": True}


def _known(ids, tree, notes, where):
    if tree is None:
        return list(ids)
    kept = []
    for nid in ids:
        if nid in tree.nodes:
            kept.append(nid)
        else:
            notes.append(f"{where}: passive {nid} is not in the tree export; dropped")
    return kept


def _weapon(name, bases, notes, where):
    """{"name", "item_class", "level", "checked"} of an authored weapon
    base, or None when the template names none. checked only when the
    base_items index names it; never guessed."""
    if name is None:
        return None
    hit = bases.get(name.lower()) if bases is not None else None
    if hit is None:
        if bases is not None:
            notes.append(words.weapon_unknown(where, name))
        return {"name": name, "item_class": None, "level": None, "checked": False}
    return {"name": hit["name"], "item_class": hit["item_class"],
            "level": hit["level"], "checked": True}


def skill_id(name, weapon, variants):
    """KINDLER-GEM-VARIANT: the PoB skill id of gem `name` for a resolved
    `weapon` ({"item_class", "checked", ...} or None) from `variants`
    (pobtext.parse_gem_variants form), or None. Only a name with two or
    more variants gets one, only with a checked weapon: the one variant
    whose weapon list is exactly the weapon's item class, else the one
    variant that lists it; None when none or several fit. Never guessed."""
    rows = (variants or {}).get(pobtext.key(name))
    if not rows or len(rows) < 2:
        return None
    if not (isinstance(weapon, dict) and weapon.get("checked") and weapon.get("item_class")):
        return None
    cls = weapon["item_class"]
    fits = [r for r in rows if r["weapons"] == [cls]] or \
        [r for r in rows if cls in r["weapons"]]
    return fits[0]["skill_id"] if len(fits) == 1 else None


def _skill_gem(name, gems, notes, where, weapon, variants):
    info = _gem(name, gems, notes, where)
    sid = skill_id(name, weapon, variants)
    return dict(info, skill_id=sid) if sid else info


def resolve(table, tree=None, gems=None, bases=None, variants=None):
    """The run-time view of a validated table: unknown node ids dropped
    with a note, each gem with checked and a level (snapshot first, else
    the authored one), the weapon base checked against `bases`, a skill
    gem's PoB skill id from `variants` (skill_id()). `tree` is a TreeGraph
    or None, `gems` a gem_index or None, `bases` a base_index or None,
    `variants` pobtext gem variants or None. Lookups only; the route search
    lives in check()."""
    notes, out = [], []
    for t in (table or {}).get("templates", ()):
        stages = []
        weapon = _weapon(t.get("weapon"), bases, [], t["id"])
        for st in t["stages"]:
            where = f"{t['id']} {st['id']}"
            skills = [{"gem": _skill_gem(s["name"], gems, notes, where, weapon, variants),
                       "sockets": s["sockets"],
                       "supports": [_gem(n, gems, notes, where) for n in s["supports"]]}
                      for s in st["skills"]]
            steps = []
            for g in st["gems"]:
                info = _gem(g["name"], gems, notes, where, authored=g["level"])
                steps.append({"name": info["name"], "action": g["action"],
                              "level": info["level"], "for": g["for"],
                              "checked": info["checked"]})
            asc = st["ascendancy"]
            if asc is not None:
                asc = {"trial": asc["trial"],
                       "nodes": _known(asc["nodes"], tree, notes, where)}
            stages.append(dict(st, skills=skills, gems=steps, ascendancy=asc,
                               passives=_known(st["passives"], tree, notes, where),
                               focus={k: list(v) for k, v in st["focus"].items()}))
        out.append(dict(t, toggles=list(t["toggles"]), stages=stages,
                        weapon=_weapon(t.get("weapon"), bases, notes, t["id"])))
    return {"schema": SCHEMA, "templates": out, "notes": notes,
            "tree": tree is not None, "gems": gems is not None,
            "bases": bases is not None}


class Sources:
    """The tracked table plus the three sidecar caches, each re-read on
    change: view() is the resolved table the engine reads."""

    def __init__(self, path=PATH, tree_path=None, gems_file=None, registry=False,
                 bases_file=None):
        self._table = watch(path, registry=registry) if path != PATH else _watch
        self._tree = hotreload.Watched(
            tree_path or treedata.default_path(), self._load_tree,
            name=words.TREE_NAME, default=None, registry=False)
        self._gems = hotreload.Watched(
            gems_file or gems_path(), self._load_gems_strict,
            name=words.GEMS_NAME, default=None, registry=False)
        self._bases = hotreload.Watched(
            bases_file or default_bases(gems_file), self._load_bases_strict,
            name=words.BASES_NAME, default=None, registry=False)

    @staticmethod
    def _load_tree(path):
        p = Path(path)
        if p.stat().st_size > treedata.MAX_BYTES:
            raise ValueError("tree file too large")
        return tree_graph(json.loads(p.read_bytes()))

    @staticmethod
    def _load_gems_strict(path):
        p = Path(path)
        if p.stat().st_size > GEMS_MAX_BYTES:
            raise ValueError("gems file too large")
        return gem_index(json.loads(p.read_bytes()))

    @staticmethod
    def _load_bases_strict(path):
        p = Path(path)
        if p.stat().st_size > BASES_MAX_BYTES:
            raise ValueError("base_items file too large")
        return base_index(json.loads(p.read_bytes()))

    def view(self):
        return resolve(self._table.get(), tree=self._tree.get(), gems=self._gems.get(),
                       bases=self._bases.get())


# --- validator only: breadth-first route and point budget -----------------

def point_budget(level, bonus=0):
    """Passive points at a character level: one per level after the first,
    plus the stage's authored bonus points."""
    return max(0, level - 1) + bonus


def _reach(start, allowed, adj):
    """Breadth-first: the ids of `allowed` reachable from `start` through
    allowed ids only."""
    seen, queue = {start}, deque([start])
    while queue:
        cur = queue.popleft()
        for nxt in sorted(adj.get(cur, ())):
            if nxt in allowed and nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def _route(start, order, new, tree, where, label, problems):
    """Connectivity (breadth-first) and allocation order of the cumulative
    prefix `order`; problems are named for this stage's nodes `new` only."""
    allowed = set(order) | {start}
    reached = _reach(start, allowed, tree.adj)
    taken = {start}
    for nid in order:
        if nid in new:
            if nid not in reached:
                problems.append(f"{where}: {label} {nid} is not connected to its start")
            elif not tree.adj.get(nid, set()) & taken:
                problems.append(f"{where}: {label} {nid} comes before a linked "
                                f"node in the order")
        taken.add(nid)


def _check_weapon(t, bases, problems):
    """An attack template names one weapon base; with the base_items index
    it must be a released weapon base of a class that fits each attack
    toggle, usable at the first stage's level."""
    tid, name = t["id"], t.get("weapon")
    attack = [x for x in t["toggles"] if x in ATTACK_TOGGLES]
    if name is None:
        if attack:
            problems.append(f"{tid}: attack template has no weapon base")
        return
    if bases is None:
        return
    hit = bases.get(name.lower())
    if hit is None:
        problems.append(f"{tid}: weapon {name} is not a weapon base in base_items")
        return
    for x in attack:
        if hit["item_class"] not in TOGGLE_CLASSES[x]:
            problems.append(f"{tid}: weapon {name} ({hit['item_class']}) does not "
                            f"fit toggle {x}")
    first = t["stages"][0]["level"]
    if hit["level"] is not None and hit["level"] > first:
        problems.append(f"{tid}: weapon {name} needs level {hit['level']}, past "
                        f"the first stage's level {first}")


def _check_template(t, tree, gems, area_ids, problems, notes, bases=None):
    tid = t["id"]
    _check_weapon(t, bases, problems)
    start = asc_start = None
    if tree is not None:
        start = tree.class_start(t["class"])
        if start is None:
            problems.append(f"{tid}: class {t['class']} has no class start in the tree export")
        if t["ascendancy"] is not None:
            asc_start = tree.asc_start(t["ascendancy"])
            owner = tree.asc_class(t["ascendancy"])
            if asc_start is None or (owner or "").lower() != t["class"].lower():
                problems.append(f"{tid}: ascendancy {t['ascendancy']} is not one of "
                                f"class {t['class']} in the tree export")
                asc_start = None
    main, asc = [], []
    for st in t["stages"]:
        where = f"{tid} {st['id']}"
        passives = _known(st["passives"], tree, notes, where)
        asc_nodes = _known((st["ascendancy"] or {}).get("nodes", []), tree,
                           notes, where)
        if tree is not None:
            for nid in passives:
                if tree.asc_of(nid):
                    problems.append(f"{where}: passive {nid} is an ascendancy node")
            for nid in asc_nodes:
                if tree.asc_of(nid) != t["ascendancy"]:
                    problems.append(f"{where}: ascendancy node {nid} is not a "
                                    f"{t['ascendancy']} node")
        main.extend(passives)
        asc.extend(asc_nodes)
        if len(main) > point_budget(st["level"], st["bonus_points"]):
            problems.append(f"{where}: {len(main)} passives pass the point budget "
                            f"of {point_budget(st['level'], st['bonus_points'])} "
                            f"at level {st['level']}")
        if start is not None:
            _route(start, [n for n in main if not tree.asc_of(n)], set(passives),
                   tree, where, "passive", problems)
        if asc_start is not None:
            _route(asc_start, asc, set(asc_nodes), tree, where, "ascendancy node",
                   problems)
        trig = st["trigger"]
        if area_ids is not None and trig["kind"] == "zone" and trig["zone"] not in area_ids:
            problems.append(f"{where}: zone {trig['zone']} is not in world_areas")
        if gems is not None:
            names = [s["name"] for s in st["skills"]]
            names += [n for s in st["skills"] for n in s["supports"]]
            names += [g["name"] for g in st["gems"]]
            names += [g["for"] for g in st["gems"] if g["for"]]
            for name in names:
                if name.lower() not in gems:
                    problems.append(f"{where}: gem {name} is not in the gems snapshot")


def check(table, tree=None, gems=None, area_ids=None, bases=None):
    """Validator report for a validated table: {"ok", "problems", "notes"}.
    Problems: a route prefix not connected from the class start (or the
    ascendancy start) by breadth-first search, out of allocation order, or
    past the point budget at its stage's level; a gem the cached snapshot
    lacks; a zone trigger not in `area_ids`; an attack template with no
    weapon base, or (with `bases`, a base_index) a weapon base the snapshot
    does not name, of a class that does not fit its toggle or needing a
    level past the first stage's. Notes: unknown node ids
    (dropped, never guessed) and checks skipped for a missing cache. Tests
    and the template package only; never called at run time."""
    problems, notes = [], []
    if tree is None:
        notes.append("no tree export cached: node ids and routes not checked")
    if gems is None:
        notes.append("no gems snapshot cached: gem names read checked=false")
    if bases is None:
        notes.append("no base_items snapshot cached: weapon bases not checked")
    for t in (table or {}).get("templates", ()):
        _check_template(t, tree, gems, area_ids, problems, notes, bases)
    return {"ok": not problems, "problems": problems, "notes": notes}
