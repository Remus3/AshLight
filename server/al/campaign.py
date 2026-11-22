"""UTIL-CAMPAIGN-CHECKS: short campaign hints (research 0031 section 4.4,
adjudicator ruling H; decision 0039).

Inputs are only what ruling H allows: the player level and area id from the
opted-in Client.txt tail, the loaded Path of Building build text (its gear
and PlayerStat resistances) and the build-time repoe-fork base_items
snapshot in the sidecar cache (decision 0009; none of its data is in a
tracked file - the flask base names and drop levels are read from the
cache at start). No screen or memory read, nothing sent to the game.

Hints, at most one per kind, in this order:
- boss: on entering a boss zone, the build's resistance to that boss's
  main element. The element comes from the caller: the zone's `boss` entry
  in the guide file (zoneguide.view's `boss`, DATA-GUIDE-BOSS), an
  AshLight-authored restated fact (guide source credited in
  docs/research/0031 only, no guide text here; decision 0039);
- flask: a higher life / mana flask base can drop at the player's level
  than the one the build has equipped (base drop levels from the snapshot);
- boots: the build's boots have no movement speed at or past a level
  setting ("boots_speed_level", default 16).
Unknown level, no build, a non-campaign area or missing data: no hint.
"""

import re
from pathlib import Path

from . import hotreload, jsonfile, num

CONFIG_KEY = "boots_speed_level"
DEFAULT_BOOTS_LEVEL = 16
MIN_BOOTS_LEVEL, MAX_BOOTS_LEVEL = 1, 100
RES_CAP = 75
WORD_MAX = 15  # the overlay HUD status word (design 0001 7.2)
MAX_BYTES = 64 * 1024 * 1024
FILE_NAME = "base_items.json"
FLASK_CLASSES = {"LifeFlask": "life", "ManaFlask": "mana"}
FLASK_SLOTS = ("Flask 1", "Flask 2")
RES_STAT = {"fire": "FireResist", "cold": "ColdResist",
            "lightning": "LightningResist", "chaos": "ChaosResist"}
_CAMPAIGN_RE = re.compile(r"^(?:C_)?G\d+_")


def boots_level_setting(value):
    if isinstance(value, bool) or not isinstance(value, int):
        return DEFAULT_BOOTS_LEVEL
    return value if MIN_BOOTS_LEVEL <= value <= MAX_BOOTS_LEVEL else DEFAULT_BOOTS_LEVEL


def _is_level(v):
    return isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 100


_num = num.finite


def load_flasks(path):
    """{"life": [(drop_level, name), ...], "mana": [...]} sorted by level,
    from a cached base_items.json; missing, oversized or malformed -> {}."""
    return flasks_from_doc(jsonfile.read_json(path, max_bytes=MAX_BYTES, kind=dict))


def flasks_from_doc(doc):
    """load_flasks' table from an already parsed base_items document
    (RUN-PERF-PARSE-ONCE: FlaskCache and basetypes.NamesCache share one
    parse); a document that is not an object gives {}."""
    if not isinstance(doc, dict):
        return {}
    out = {}
    for entry in doc.values():
        if not isinstance(entry, dict) or entry.get("release_state") == "unreleased":
            continue
        kind = FLASK_CLASSES.get(entry.get("item_class"))
        name, level = entry.get("name"), entry.get("drop_level")
        if kind and isinstance(name, str) and name.strip() and _is_level(level):
            out.setdefault(kind, []).append((level, " ".join(name.split())))
    return {k: sorted(set(v)) for k, v in out.items()}


def default_path(environ=None):
    from .theorycraft import datacredit
    return datacredit.cache_dir(environ) / FILE_NAME


class FlaskCache(hotreload.Watched):
    """Loads the flask table once and again only when the file changes;
    a malformed rewrite keeps the last good table (HOT-RELOAD, 0042). One
    parse of the file feeds this table and basetypes.NamesCache's list
    (RUN-PERF-PARSE-ONCE)."""

    def __init__(self, path):
        super().__init__(path, load_flasks, name="Flask table", default=dict,
                         check=hotreload.check_json(MAX_BYTES),
                         from_doc=flasks_from_doc, share=True)


# AREA-AUDIT P7-7: only a positive "N% increased Movement Speed" counts;
# "reduced" (or a zero / negative value) is not speed.
_SPEED = re.compile(r"(?<![\w.+-])\+?(\d+(?:\.\d+)?)% increased movement speed\b")


def _has_speed(text):
    return any(float(m.group(1)) > 0 for m in _SPEED.finditer(text.lower()))


def build_facts(build):
    """What the hints need from a loaded PoB build, or None without one:
    {"flasks": [base, ...], "boots": None | {"speed": bool}, "res": {el: n}}."""
    if build is None:
        return None
    equipped = getattr(build, "equipped", None)

    def item(slot):
        try:
            return equipped(slot) if callable(equipped) else None
        except Exception:  # noqa: BLE001 - a bad build reads as no item
            return None

    flasks = []
    for slot in FLASK_SLOTS:
        it = item(slot)
        base = getattr(it, "base", None)
        if isinstance(base, str) and base.strip():
            flasks.append(" ".join(base.split()))
    boots = item("Boots")
    boots_fact = None
    if boots is not None and isinstance(getattr(boots, "text", None), str):
        boots_fact = {"speed": _has_speed(boots.text)}
    stats = getattr(build, "stats", None)
    stats = stats if isinstance(stats, dict) else {}
    res = {el: _num(stats.get(key)) for el, key in RES_STAT.items()}
    return {"flasks": flasks, "boots": boots_fact, "res": res}


def _a(name, start=False):
    """"a Big Life Flask", "an Ultimate Life Flask" ("A" / "An" at the
    start of a sentence)."""
    art = "an" if name[:1].lower() in ("a", "e", "i", "o", "u") else "a"
    return (art.capitalize() if start else art) + " " + name


def _flask_hints(level, facts, table):
    out = []
    for base in facts.get("flasks") or ():
        for kind, tiers in (table or {}).items():
            names = [n for _lv, n in tiers]
            if base not in names:
                continue
            have = next(lv for lv, n in tiers if n == base)
            best = [(lv, n) for lv, n in tiers if lv <= level]
            if best and best[-1][0] > have and not any(h["id"] == "flask-" + kind
                                                      for h in out):
                out.append({"id": "flask-" + kind, "word": "Better flask",
                            "text": f"{_a(best[-1][1], True)} can drop at your "
                                    f"level; your build has {_a(base)}."})
    return out


def view(level, area_id, facts, flasks=None, boots_level=DEFAULT_BOOTS_LEVEL, boss=None):
    """The snapshot `campaign` part: {"hints": [{"id", "text", "word"}],
    "word"} or None when there is nothing to say. `boss` is the zone boss's
    element the guide passes in (zoneguide.view's `boss`); an element
    RES_STAT does not know reads as no boss."""
    if not _is_level(level) or not isinstance(facts, dict):
        return None
    if not isinstance(area_id, str) or not _CAMPAIGN_RE.match(area_id):
        return None
    hints = []
    element = boss if isinstance(boss, str) and boss in RES_STAT else None
    if element:
        res = _num((facts.get("res") or {}).get(element))
        if res is None:
            hints.append({"id": "boss", "word": f"Boss: {element}",
                          "text": f"This zone's boss deals mostly {element} damage. "
                                  f"Your build's {element} resistance is unknown."})
        else:
            r = round(res)
            low = " (the cap is 75%)" if r < RES_CAP else " (at the cap)"
            word = f"{element.capitalize()} res {r}%"
            hints.append({"id": "boss",
                          "word": word if len(word) <= WORD_MAX else f"Boss: {element}",
                          "text": f"This zone's boss deals mostly {element} damage. "
                                  f"Your build has {r}% {element} resistance{low}."})
    hints.extend(_flask_hints(level, facts, flasks))
    boots = facts.get("boots")
    if (isinstance(boots, dict) and not boots.get("speed")
            and level >= boots_level_setting(boots_level)):
        hints.append({"id": "boots", "word": "Boots: no speed",
                      "text": "Your build's boots have no movement speed. Boots with it "
                              "help in the campaign."})
    if not hints:
        return None
    return {"hints": hints, "word": hints[0]["word"]}
