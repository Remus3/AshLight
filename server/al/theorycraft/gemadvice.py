"""Gem advice: the one gem lookup for the loaded build's gems against the
cached gems snapshot (TC-UNCUT-GEM, decision 0094; TC-GEM-UNLOCK).

Inputs only: the press's own item text (the one clipboard read of
decision 0003), the loaded build's gems (the pasted Path of Building
build, or the shown Kindler stage while no build is pasted) and the cached
repoe-fork gems snapshot (DATA-GEMS-SNAP, decision 0009), read through
hotreload with the last good copy kept. Nothing here reads the clipboard,
the screen or the game, and nothing is fetched or sent. No snapshot or no
build answers nothing; a field the snapshot lacks is never guessed.

- table(doc): {match key: {"name", "kind", "tier", "max_level", "need"}}
  from a parsed gems document. kind: an explicit gem_type of skill /
  support / spirit, else is_support, else a persistent / meta / spirit tag
  (spirit), else a SupportGem base item id (support), else skill. tier:
  the snapshot's gem_tier / tier, None when it names none. need: the
  level requirement (archetypes._gem_level). Unreleased and legacy
  entries are skipped.
- index(path): table() of the cached snapshot, re-read on change.
- pob_gems(build) / stage_gems(rows): the build's gems as
  [{"name", "level", "on", "skill_id"}] (on: enabled group and gem;
  level: PoB's gem level, None for a Kindler stage).
- parse_uncut(text): {"kind", "level"} of an uncut gem item text.
- cut_options(text, gems, tab): which build gems a level N cut can make
  and the build does not show as socketed at that level yet.
"""

import json
import re
from pathlib import Path

from .. import hotreload
from . import archetypes

KINDS = ("skill", "support", "spirit")
LEVEL_MAX = 40   # gem levels and tiers
CHAR_MAX = 100   # character levels
NAME_MAX = 80
SHOW_MAX = 24    # gem names kept in one answer
MAX_GEMS = 64    # build gems read (a build has far fewer)
TEXT_MAX = 8000

_CLASS_RE = re.compile(r"^item class:\s*uncut\s+(skill|support|spirit)\s+gems?\s*$", re.I)
_NAME_RE = re.compile(r"^uncut\s+(skill|support|spirit)\s+gem"
                      r"(?:\s*\(\s*level\s+(\d{1,2})\s*\))?\s*$", re.I)
_LEVEL_RE = re.compile(r"^level:\s*(\d{1,2})\b", re.I)
_SPIRIT_TAGS = ("persistent", "meta", "spirit")
_SKIP_STATES = ("unreleased", "legacy")


def _num(value, top=LEVEL_MAX):
    if isinstance(value, bool):
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if 1 <= n <= top else None


# --- the uncut gem text ----------------------------------------------------------

def parse_uncut(text):
    """{"kind", "level"} for an uncut gem item text, else None. The name
    line 'Uncut <Kind> Gem (Level N)' (the snapshot's own base names) or
    the 'Item Class: Uncut <Kind> Gems' header gives the kind; N comes from
    a 'Level: N' property, else the name's '(Level N)'. No level, no
    answer (the item level is not the cut level)."""
    if not isinstance(text, str) or len(text) > TEXT_MAX:
        return None
    kind = level = name_level = None
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")[:60]:
        line = raw.strip()
        m = _CLASS_RE.match(line)
        if m:
            kind = kind or m.group(1).lower()
            continue
        m = _NAME_RE.match(line)
        if m:
            kind = kind or m.group(1).lower()
            name_level = name_level or _num(m.group(2))
            continue
        m = _LEVEL_RE.match(line)
        if m and level is None:
            level = _num(m.group(1))
    level = level or name_level
    if kind is None or level is None:
        return None
    return {"kind": kind, "level": level}


# --- the snapshot table ----------------------------------------------------------

def norm(name):
    """The match key of a gem name: lower case, no 'Support:' prefix or
    ' Support' suffix, single spaces."""
    if not isinstance(name, str):
        return ""
    key = " ".join(name.lower().split())
    if key.startswith("support:"):
        key = key[len("support:"):].strip()
    if key.endswith(" support"):
        key = key[:-len(" support")].strip()
    return key


def _tags(entry):
    out = set()
    for field in ("tags", "gem_tags"):
        raw = entry.get(field)
        if isinstance(raw, dict):
            raw = list(raw)
        for tag in raw if isinstance(raw, list) else ():
            if isinstance(tag, str):
                out.add(tag.strip().lower())
    return out


def _kind(entry):
    explicit = entry.get("gem_type")
    if isinstance(explicit, str) and explicit.strip().lower() in KINDS:
        return explicit.strip().lower()
    if entry.get("is_support") is True:
        return "support"
    if _tags(entry) & set(_SPIRIT_TAGS):
        return "spirit"
    base = entry.get("base_item")
    bid = base.get("id") if isinstance(base, dict) else None
    if isinstance(bid, str) and "supportgem" in bid.lower():
        return "support"
    return "skill"


def _tier(entry):
    for holder in (entry, entry.get("base_item"), entry.get("static")):
        if not isinstance(holder, dict):
            continue
        for field in ("gem_tier", "tier"):
            value = _num(holder.get(field))
            if value is not None:
                return value
    return None


def _max_level(entry):
    per = entry.get("per_level")
    levels = [n for n in (_num(k) for k in (per if isinstance(per, dict) else ()))
              if n is not None]
    return max(levels) if levels else None


def _released(entry):
    base = entry.get("base_item")
    state = base.get("release_state") if isinstance(base, dict) else None
    return not (isinstance(state, str) and state.strip().lower() in _SKIP_STATES)


def table(doc):
    """{match key: {"name", "kind", "tier", "max_level", "need"}} from a
    parsed repoe-fork style gems document; unreadable or unreleased entries
    are skipped. A name seen twice keeps the lowest tier and need."""
    out = {}
    for entry in doc.values() if isinstance(doc, dict) else ():
        if not isinstance(entry, dict) or not _released(entry):
            continue
        name = archetypes._gem_name(entry)
        if not isinstance(name, str) or not name.strip() or len(name) > NAME_MAX:
            continue
        key = norm(name)
        row = {"name": name, "kind": _kind(entry), "tier": _tier(entry),
               "max_level": _max_level(entry), "need": archetypes._gem_level(entry)}
        old = out.get(key)
        if old is None:
            out[key] = row
            continue
        for field in ("tier", "need"):
            if row[field] is not None and (old[field] is None or row[field] < old[field]):
                old[field] = row[field]
    return out


def _load(path):
    p = Path(path)
    if p.stat().st_size > archetypes.GEMS_MAX_BYTES:
        raise ValueError("gems file too large")
    return table(json.loads(p.read_bytes())) or None


_watch = None


def index(path=None):
    """table() of the cached gems snapshot (re-read on change, the last
    good copy kept), or None when it is missing or unreadable."""
    global _watch
    target = Path(path) if path is not None else archetypes.gems_path()
    if _watch is None or _watch.path != target:
        _watch = hotreload.Watched(target, _load, name="skill gem list",
                                   default=None, registry=False)
    return _watch.get()


def lookup(tab, gem):
    """The table row of one build gem (by name, then PoB skill id), or None:
    a gem the snapshot does not name is never guessed."""
    if not tab or not isinstance(gem, dict):
        return None
    return tab.get(norm(gem.get("name"))) or tab.get(norm(gem.get("skill_id")))


# --- the build's gems ------------------------------------------------------------

def _clean(name):
    if not isinstance(name, str):
        return None
    name = " ".join(name.split())
    return name if 0 < len(name) <= NAME_MAX else None


def pob_gems(build):
    """[{"name", "level", "on", "skill_id"}] of a PoB build's active skill
    set, in build order; [] without a build."""
    out = []
    for group in getattr(build, "skills", None) or ():
        group_on = getattr(group, "enabled", True) is not False
        for gem in getattr(group, "gems", None) or ():
            name = _clean(getattr(gem, "name", None))
            if name is None:
                continue
            level = getattr(gem, "level", None)
            out.append({"name": name,
                        "level": level if _num(level) is not None else None,
                        "on": group_on and getattr(gem, "enabled", True) is not False,
                        "skill_id": getattr(gem, "skill_id", None)})
            if len(out) >= MAX_GEMS:
                return out
    return out


def stage_gems(rows):
    """The gems of Kindler skill rows (a plan stage's "skills", or the
    Progression model's skill rows): each skill and its linked supports,
    level None (a plan holds no socketed level)."""
    out = []
    for sk in rows if isinstance(rows, (list, tuple)) else ():
        if not isinstance(sk, dict):
            continue
        for g in [sk] + list(sk.get("supports") or ()):
            name = _clean(g.get("name")) if isinstance(g, dict) else None
            if name is not None:
                out.append({"name": name, "level": None, "on": True, "skill_id": None})
            if len(out) >= MAX_GEMS:
                return out
    return out


def plan_stage_gems(plan, stage):
    """stage_gems() of a Kindler plan's stage (the first when stage is None)."""
    stages = plan.get("stages") if isinstance(plan, dict) else None
    if not isinstance(stages, list) or not stages:
        return []
    i = stage if isinstance(stage, int) and 0 <= stage < len(stages) else 0
    st = stages[i]
    return stage_gems(st.get("skills") if isinstance(st, dict) else None)


# --- TC-UNCUT-GEM ------------------------------------------------------------------

def cut_options(text, gems, tab):
    """The answer for one press, or None (not an uncut gem, no build gems,
    no snapshot). Answer: {"kind", "level", "gems": [{"name", "level",
    "have"}], "unchecked": [names], "more", "unchecked_more"}.

    A build gem of the uncut's kind counts when the snapshot names it. Its
    tier (when the snapshot has one) must be at most N; a gem with no tier
    in the snapshot goes to "unchecked" (named, never claimed makeable).
    The level made is N clamped to the gem's highest snapshot level. have
    is the build's shown socketed level (0 when disabled or unknown); a gem
    already shown at that level is left out."""
    uncut = parse_uncut(text)
    if uncut is None or not gems or not tab:
        return None
    kind, n = uncut["kind"], uncut["level"]
    best, order = {}, []
    for gem in gems:
        row = lookup(tab, gem)
        if row is None or row["kind"] != kind:
            continue
        if row["tier"] is not None and row["tier"] > n:
            continue
        makes = min(n, row["max_level"]) if row["max_level"] else n
        have = (gem.get("level") or 0) if gem.get("on") else 0
        key = norm(row["name"])
        if key not in best:
            order.append(key)
            best[key] = {"name": row["name"], "level": makes, "have": have,
                         "checked": row["tier"] is not None}
        else:
            best[key]["have"] = max(best[key]["have"], have)
    found = [best[k] for k in order if best[k]["have"] < best[k]["level"]]
    sure = [{"name": r["name"], "level": r["level"], "have": r["have"]}
            for r in found if r["checked"]]
    unsure = [r["name"] for r in found if not r["checked"]]
    return {"kind": kind, "level": n, "gems": sure[:SHOW_MAX],
            "unchecked": unsure[:SHOW_MAX],
            "more": max(0, len(sure) - SHOW_MAX),
            "unchecked_more": max(0, len(unsure) - SHOW_MAX)}

