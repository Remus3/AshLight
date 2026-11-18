"""ZONE-GUIDE (decision 0043): a live per-zone guide and quest tracker.

PoE2 zone layouts are random per instance, so "pathing" here is per-zone
guidance, shown by itself on every zone change (zero clicks):
- the zone's objective, the optional content worth doing (permanent
  rewards such as spirit, resistances and passive points), a layout
  tendency and the next zone on the main path, all AshLight's own words
  in the tracked file `server/al/data/zone_guide.json` (decision 0009: no
  wiki or poe2db prose; a fact we are not sure of is left out, never
  guessed);
- waypoint and the nearest waypoint from the build-time world_areas
  snapshot's `has_waypoint` / `connections` fields (decision 0020; read
  only, never fetched here, and the guide works without it);
- a clear-or-push lean from the player's level against the zone level
  (the log's area level, else the snapshot's);
- a quest tracker per character (decision 0038 keying): the zones the
  character entered, from the `[SCENE]` lines already tailed. A main-path
  step counts as done once the character entered the zone after it; an
  optional reward counts as "skipped" when its zone was never entered and
  the character has moved on to a later act. Pickups are not in the log,
  so AshLight never claims a reward was taken, only that its zone was or
  was not visited.

The guide file is re-read when its mtime or size changes (hot reload via
hotreload.register, decision 0042: one stat per core tick, a malformed
edit keeps the last good guide and shows a Checks note). Visited zones are a bounded local file under the
runtime dir, under the run-history switch (decision 0036).
"""

import collections
import json
import os
from pathlib import Path

from . import acts as acts_mod
from . import hotreload, jsonfile

PATH = Path(__file__).resolve().parent / "data" / "zone_guide.json"
FILE_NAME = "zone_visits.json"
MAX_GUIDE_BYTES = 512 * 1024
MAX_GRAPH_BYTES = 64 * 1024 * 1024
MAX_CHARACTERS = 12
MAX_ACTS = 16
MAX_ZONES = 48
MAX_TEXT = 64
MAX_LINE = 120
WAYPOINT_HOPS = 6

KINDS = ("spirit", "resist", "passive", "life", "mana", "gem", "charm",
         "flask", "item", "skill", "other")
# Kinds the tracker counts as a lasting reward (a gem or an item is a
# one-off find, shown but not counted).
LASTING = ("spirit", "resist", "passive", "life", "mana", "charm", "flask",
           "skill", "other")
KIND_WORD = {"spirit": "spirit", "resist": "resistance", "passive": "passive points",
             "life": "life", "mana": "mana", "gem": "gem", "charm": "charm slot",
             "flask": "flask", "item": "item", "skill": "skill", "other": "bonus"}

# Dashboard and overlay copy (design 0001 section 9); printed as given.
SOURCE_TEXT = ("Own notes, not checked every patch. Layouts are random, so tips "
               "are tendencies.")
CLEAR_TEXT = ("You are {n} {lv} under this zone: clear it fully for "
              "experience.")
RUSH_TEXT = ("You are {n} {lv} over this zone, so it gives less experience. "
             "Move on once your goal is done.")
FIT_TEXT = "Your level fits this zone: clear what is on your way."
WAYPOINT_YES = "Waypoint in this zone."
WAYPOINT_NEAR = "No waypoint here. Nearest: {zone}."
MISSED_TEXT = "{act}: not entered yet: {names} ({n} of {m} bonus {zones})."
AHEAD_TEXT = "{act} bonus zones entered: {n} of {m}. AshLight can't see pickups."
ENDGAME_LABEL = "Endgame map"


def _zone_word(n):
    return "zone" if n == 1 else "zones"


def _lv(n):
    return "level" if n == 1 else "levels"


def _clean(text, limit=None):
    if not isinstance(text, str):
        return None
    text = " ".join(text.split())
    if not text:
        return None
    return text[:limit] if limit else text


# -- the guide file -----------------------------------------------------------

def load(path=PATH):
    """The guide document ({} when missing, oversized or malformed)."""
    return jsonfile.read_json(path, max_bytes=MAX_GUIDE_BYTES, encoding="ascii",
                              kind=dict, default={})


class FileCache:
    """Calls `loader(path)` once and again only when the file's mtime or
    size changes (hot reload); a missing file gives `empty`."""

    def __init__(self, path, loader, empty=None):
        self.path = Path(path)
        self._loader = loader
        self._empty = {} if empty is None else empty
        self._sig = None
        self._value = self._empty

    def get(self):
        try:
            st = os.stat(self.path)
            sig = (st.st_mtime_ns, st.st_size)
        except OSError:
            self._sig, self._value = None, self._empty
            return self._value
        if sig != self._sig:
            self._value = self._loader(self.path)
            self._sig = sig
        return self._value


def guide_cache(path=PATH):
    """HOT-RELOAD (decision 0042): the guide file joins the hot reload
    registry; a removed file reads as {}."""
    return hotreload.register(path, load, name="Zone guide", default=dict,
                              check=hotreload.check_json(MAX_GUIDE_BYTES))


# -- the snapshot graph -------------------------------------------------------

def load_graph(path):
    """{area id: {"name", "waypoint", "town", "links"}} for campaign areas
    from a cached world_areas.json (fields `name`, `has_waypoint`,
    `is_town`, `connections`, checked 2026-11-17). {} when missing,
    oversized or malformed; a malformed entry is skipped."""
    try:
        p = Path(path)
        if p.stat().st_size > MAX_GRAPH_BYTES:
            return {}
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    if not isinstance(doc, dict):
        return {}
    out = {}
    for area_id, a in doc.items():
        if acts_mod.act_of(area_id) is None or not isinstance(a, dict):
            continue
        name = _clean(a.get("name"))
        if name is None:
            continue
        links = a.get("connections")
        links = [c for c in links if isinstance(c, str)] if isinstance(links, list) else []
        out[area_id] = {"name": name, "waypoint": a.get("has_waypoint") is True,
                        "town": a.get("is_town") is True, "links": links[:16]}
    return out


def graph_cache(path):
    return FileCache(path, load_graph)


def _graph_node(graph, area_id, zone):
    node = graph.get(area_id) if isinstance(area_id, str) else None
    if node is not None:
        return area_id, node
    info = acts_mod.act_of(area_id)
    if info is None or not zone:
        return None, None
    for aid, n in graph.items():
        if n["name"] == zone and (acts_mod.act_of(aid) or {}).get("key") == info["key"]:
            return aid, n
    return None, None


def nearest_waypoint(graph, area_id):
    """The name of the nearest other area with a waypoint (or a town) by
    snapshot connections, within WAYPOINT_HOPS, else None."""
    seen = {area_id}
    frontier = collections.deque([(area_id, 0)])
    while frontier:
        aid, hops = frontier.popleft()
        if hops >= WAYPOINT_HOPS:
            continue
        for nxt in (graph.get(aid) or {}).get("links", ()):
            if nxt in seen or nxt not in graph:
                continue
            seen.add(nxt)
            node = graph[nxt]
            if node["waypoint"] or node["town"]:
                return node["name"]
            frontier.append((nxt, hops + 1))
    return None


# -- visited zones per character ---------------------------------------------

class Visits:
    """Zones one character entered, per act key. Bounded."""

    def __init__(self, acts=None):
        self.acts = collections.OrderedDict()
        for key, zones in (acts or {}).items():
            if isinstance(key, str) and isinstance(zones, list):
                for z in zones:
                    self.add(key, z)

    def add(self, act_key, zone):
        zone = _clean(zone, MAX_TEXT)
        if not isinstance(act_key, str) or zone is None:
            return False
        zones = self.acts.get(act_key)
        if zones is None:
            if len(self.acts) >= MAX_ACTS:
                return False
            zones = self.acts[act_key] = []
        if zone in zones or len(zones) >= MAX_ZONES:
            return False
        zones.append(zone)
        return True

    def has(self, act_key, zone):
        return zone in self.acts.get(act_key, ())

    def merge(self, other):
        changed = False
        for key, zones in other.acts.items():
            for z in zones:
                changed = self.add(key, z) or changed
        return changed

    def to_doc(self):
        return {k: list(v) for k, v in self.acts.items()}


class VisitBook:
    """Visits by character name ("" while the name is unknown). Not
    thread-safe: the SessionState lock guards it."""

    def __init__(self):
        self.by_name = collections.OrderedDict()
        self.version = 0

    def of(self, name):
        key = name or ""
        v = self.by_name.get(key)
        if v is None:
            v = self.by_name[key] = Visits()
        self.by_name.move_to_end(key)
        while len(self.by_name) > MAX_CHARACTERS:
            self.by_name.popitem(last=False)
        return v

    def visit(self, name, area_id, zone):
        """A real zone entered in a campaign area. True when new."""
        info = acts_mod.act_of(area_id)
        if info is None:
            return False
        if name and "" in self.by_name:
            # the name became known: the unnamed visits were this character's
            self.of(name).merge(self.by_name.pop(""))
        if self.of(name).add(info["key"], zone):
            self.version += 1
            return True
        return False

    def load_doc(self, doc):
        """Merge a saved file document in (live visits win nothing: union)."""
        chars = doc.get("characters") if isinstance(doc, dict) else None
        if not isinstance(chars, dict):
            return False
        changed = False
        for name, acts in list(chars.items())[-MAX_CHARACTERS:]:
            if isinstance(name, str) and name and isinstance(acts, dict):
                changed = self.of(name).merge(Visits(acts)) or changed
        if changed:
            self.version += 1
        return changed

    def to_doc(self):
        return {"schema": 1, "characters": {n: v.to_doc() for n, v in self.by_name.items()
                                            if n}}

    def clear(self):
        self.by_name.clear()
        self.version += 1


def read_visits(path):
    return jsonfile.read_json(path, max_bytes=1024 * 1024, kind=dict, default={})


def write_visits(path, doc):
    """Save a VisitBook.to_doc() document (atomic, ASCII, LF)."""
    jsonfile.write_json(path, doc)


# -- the view -----------------------------------------------------------------

def _act_table(doc, key):
    table = doc.get("acts") if isinstance(doc.get("acts"), dict) else {}
    entry = table.get(key)
    return entry if isinstance(entry, dict) else None


def _zones(entry):
    zones = entry.get("zones") if isinstance(entry, dict) else None
    return zones if isinstance(zones, dict) else {}


def _optional(z):
    out = []
    for o in (z.get("optional") if isinstance(z.get("optional"), list) else ()):
        if isinstance(o, dict) and _clean(o.get("text")):
            kind = o.get("kind") if o.get("kind") in KINDS else "other"
            out.append({"kind": kind, "text": _clean(o["text"])})
    return out


def act_rewards(doc, key):
    """[(zone, [lasting optional...]), ...] for an act, in file order."""
    out = []
    for name, z in _zones(_act_table(doc, key)).items():
        rows = [o for o in _optional(z) if o["kind"] in LASTING] if isinstance(z, dict) else []
        if rows:
            out.append((name, rows))
    return out


def _steps(doc, key, visits):
    """Main-path steps of an act, in file order: zones with an objective
    (not `"main": false`). A step is done once its `next` zone or any
    later step's zone was entered. A step whose `next` is a hub town
    (`"town": true`) counts once its own zone was entered; the act's last
    step counts once its next zone (in another act) was entered. An act
    with `"any_order": true` gets no later-step rule."""
    act = _act_table(doc, key) or {}
    zones = _zones(act)
    out = []
    for name, z in zones.items():
        if not isinstance(z, dict) or not _clean(z.get("objective")):
            continue
        nxt = _clean(z.get("next"))
        if z.get("main") is False or z.get("town") is True:
            continue
        if visits is None:
            done = False
        elif nxt and isinstance(zones.get(nxt), dict) and zones[nxt].get("town") is True:
            done = visits.has(key, name)
        elif nxt and nxt not in zones:
            done = any(nxt in v for v in visits.acts.values())
        else:
            done = bool(nxt) and visits.has(key, nxt)
        out.append({"zone": name, "text": _clean(z["objective"]), "done": done})
    if act.get("any_order") is True:
        return out
    # a later main-path zone entered means the earlier steps were passed
    # (also when the core started mid-campaign and missed the early ones)
    later = False
    for step in reversed(out):
        if later:
            step["done"] = True
        later = later or step["done"] or (visits is not None
                                          and visits.has(key, step["zone"]))
    return out


def advice(level, zone_level):
    """{"mode": "clear"|"push"|"fit", "text"} or None."""
    if not isinstance(level, int) or not isinstance(zone_level, int) or zone_level < 1:
        return None
    if level < zone_level - 2:
        n = zone_level - level
        return {"mode": "clear", "text": CLEAR_TEXT.format(n=n, lv=_lv(n))}
    over = level - zone_level
    if over > 3 + level // 16:
        return {"mode": "push", "text": RUSH_TEXT.format(n=over, lv=_lv(over))}
    return {"mode": "fit", "text": FIT_TEXT}


def _names(rows):
    names = [r for r in rows]
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def quest_view(doc, key, visits):
    """The tracker part: this act's steps and bonus counts, plus earlier
    acts' skipped bonus zones."""
    info_n = int(key[1:]) if key[1:].isdigit() else 0
    rewards = act_rewards(doc, key)
    seen = sum(1 for z, _ in rewards if visits is not None and visits.has(key, z))
    label = acts_mod.label_of(key)
    steps = _steps(doc, key, visits)
    missed = []
    table = doc.get("acts") if isinstance(doc.get("acts"), dict) else {}
    for other in table:
        if (not isinstance(other, str) or other[:1] != key[:1] or not other[1:].isdigit()
                or int(other[1:]) >= info_n):
            continue
        if visits is None or not visits.acts.get(other):
            continue  # the character never played that act here
        rows = act_rewards(doc, other)
        skipped = [z for z, _ in rows if not visits.has(other, z)]
        if skipped:
            missed.append({"act": acts_mod.label_of(other), "skipped": len(skipped),
                           "total": len(rows),
                           "text": MISSED_TEXT.format(
                               act=acts_mod.label_of(other), n=len(skipped), m=len(rows),
                               zones=_zone_word(len(rows)),
                               names=_names(skipped))})
    return {"act": label, "steps": steps,
            "steps_done": sum(1 for s in steps if s["done"]),
            "bonus_total": len(rewards), "bonus_visited": seen,
            "bonus_text": (AHEAD_TEXT.format(act=label, n=seen, m=len(rewards),
                                             zones=_zone_word(len(rewards)))
                           if rewards else None),
            "missed": missed}


def _line(zone, entry, adv):
    parts = []
    if entry.get("objective"):
        parts.append(entry["objective"])
    if entry.get("optional"):
        parts.append("Bonus: " + entry["optional"][0]["text"])
    if adv and adv["mode"] != "fit":
        parts.append("Clear it." if adv["mode"] == "clear" else "Push on.")
    text = " ".join(parts)
    if len(text) > MAX_LINE:
        text = text[:MAX_LINE - 3].rstrip() + "..."
    return text or None


def view(doc, graph, area_id, zone, in_hideout, level, area_level, visits,
         zone_level=None):
    """The `zone_guide` part of the snapshot, or None outside a campaign
    zone or map."""
    if in_hideout or not zone:
        return None
    doc = doc if isinstance(doc, dict) else {}
    graph = graph if isinstance(graph, dict) else {}
    zl = area_level if isinstance(area_level, int) and area_level > 0 else zone_level
    adv = advice(level, zl)
    if acts_mod.is_endgame(area_id):
        e = doc.get("endgame") if isinstance(doc.get("endgame"), dict) else {}
        entry = {"objective": _clean(e.get("objective")), "layout": _clean(e.get("layout")),
                 "optional": _optional(e), "next": None}
        if not entry["objective"]:
            return None
        return {"kind": "endgame", "zone": zone, "act": ENDGAME_LABEL,
                "objective": entry["objective"], "optional": entry["optional"],
                "layout": entry["layout"], "next": None, "waypoint": None,
                "advice": adv, "quest": None, "line": _line(zone, entry, adv),
                "source": SOURCE_TEXT}
    info = acts_mod.act_of(area_id)
    if info is None:
        return None
    act = _act_table(doc, info["key"])
    z = _zones(act).get(zone.strip())
    z = z if isinstance(z, dict) else {}
    entry = {"objective": _clean(z.get("objective")) or _clean((act or {}).get("default")),
             "layout": _clean(z.get("layout")), "optional": _optional(z),
             "next": _clean(z.get("next"))}
    aid, node = _graph_node(graph, area_id, zone.strip())
    waypoint = None
    if node is not None:
        if node["waypoint"] or node["town"]:
            waypoint = WAYPOINT_YES
        else:
            near = nearest_waypoint(graph, aid)
            waypoint = WAYPOINT_NEAR.format(zone=near) if near else None
    if not (entry["objective"] or entry["layout"] or entry["optional"] or waypoint):
        return None
    return {"kind": "campaign", "zone": zone.strip(), "act": info["label"],
            "objective": entry["objective"], "optional": entry["optional"],
            "layout": entry["layout"], "next": entry["next"], "waypoint": waypoint,
            "advice": adv, "quest": quest_view(doc, info["key"], visits),
            "line": _line(zone, entry, adv), "source": SOURCE_TEXT}


def replay(events, book, name):
    """Fold resumed run events (scene / area lines) into `book`."""
    area = None
    changed = False
    for e in events or ():
        t = e.get("type")
        if t == "area_generated":
            area = e.get("area_id")
        elif (t == "scene_changed" and not e.get("is_null") and not e.get("is_transient")
              and not e.get("is_hideout") and e.get("scene")):
            changed = book.visit(name, area, e.get("scene")) or changed
    return changed
