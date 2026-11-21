"""BUILD-LIVE (decision 0045): is the loaded build the one being played,
and which items checked earlier are upgrades now.

- `alert(build_info, character, log_class, log_level)`: a stale-build
  finding from the player's own Client.txt facts (class from the level-up
  line, level) against the loaded build, or None. The words come from
  state.build_alert_text (NLM: one place for text).
- `Candidates`: every item the player checked (one per item-hotkey press,
  decision 0003), kept in memory only, at most MAX_ITEMS per character and
  MAX_CHARACTERS characters. Nothing is written to disk or sent anywhere.
- `notice(result, entry, level, build)`: the upgrade notice of one
  re-scored candidate (slot it replaces, delta, class fit), or None when it
  is not an upgrade.
"""

import collections
import hashlib

from . import charjson
from . import treedata
from . import item as item_parser

LEVEL_GAP = 5  # the log level this far past the build's level -> stale
MAX_ITEMS = 10
MAX_CHARACTERS = 12
NO_CHARACTER = ""  # the list for presses made before the log names anyone


def _asc_class(name):
    """Base class of an ascendancy: the cached tree export first
    (TC-ASC-FROM-TREE), then the built-in table; None for a non-ascendancy."""
    return treedata.class_of(name) or charjson.ASCENDANCY_CLASS.get(name)


def _base_class(name):
    if not name:
        return None
    return _asc_class(name) or name


def class_fits(log_class, build_class, build_asc):
    """True / False, or None when either side is unknown. The log names the
    ascendancy once the player has one, else the base class."""
    if not log_class or not build_class:
        return None
    if log_class in (build_class, build_asc):
        return True
    if build_asc and _asc_class(log_class):
        return False  # ascended into another ascendancy than the build's
    return _base_class(log_class) == _base_class(build_class)


def alert(build_info, character, log_class, log_level):
    """{"kind": "missing" | "class" | "level", ...} or None.

    missing: the log names a character and no build is saved for it.
    class: the log's class or ascendancy does not fit the build's.
    level: the character is LEVEL_GAP or more levels past the build (a
    build planned for a higher level is normal and never alerts)."""
    info = build_info if isinstance(build_info, dict) else {}
    if not info.get("loaded"):
        if character:
            return {"kind": "missing", "character": character}
        return None
    owner = info.get("character")
    if character and owner and owner != character:
        return None  # the swap to this character's build is under way
    build_class = info.get("class_name")
    build_asc = info.get("ascendancy")
    if class_fits(log_class, build_class, build_asc) is False:
        return {"kind": "class", "character": character, "log_class": log_class,
                "build_class": build_asc or build_class}
    lvl = info.get("level")
    if (isinstance(log_level, int) and isinstance(lvl, int)
            and not isinstance(lvl, bool) and log_level - lvl >= LEVEL_GAP):
        return {"kind": "level", "character": character, "build_level": lvl,
                "level": log_level}
    return None


def _key(text):
    return hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()


class Candidates:
    """Items checked per character, newest last, memory only."""

    def __init__(self):
        self._by = collections.OrderedDict()

    def add(self, character, text, slot, verdict, at):
        """Remember one press. The same item text again moves to the end
        with its new verdict."""
        name = character or NO_CHARACTER
        rows = self._by.pop(name, None)
        if rows is None:
            rows = collections.OrderedDict()
        self._by[name] = rows
        key = _key(text)
        rows.pop(key, None)
        rows[key] = {"text": text, "slot": slot, "verdict": verdict, "at": at,
                     "was": verdict}
        while len(rows) > MAX_ITEMS:
            rows.popitem(last=False)
        while len(self._by) > MAX_CHARACTERS:
            self._by.popitem(last=False)

    def rows(self, character):
        """The character's rows (oldest first); the presses made before
        any character was known count for the first one named."""
        name = character or NO_CHARACTER
        rows = self._by.get(name)
        if character and NO_CHARACTER in self._by:
            early = self._by.pop(NO_CHARACTER)
            rows = self._by.setdefault(name, collections.OrderedDict())
            for k, v in early.items():
                rows.setdefault(k, v)
            while len(rows) > MAX_ITEMS:
                rows.popitem(last=False)
        return list(rows.values()) if rows else []

    def count(self, character):
        return len(self._by.get(character or NO_CHARACTER) or ())


def _pct(part, key):
    d = part.get(key) if isinstance(part, dict) else None
    return d.get("pct") if isinstance(d, dict) else None


def fit(text, level, build):
    """{"ok": bool, "kind": "level" | "build", "need": n, "level": n,
    "build_class": name}: whether the character can wear the item now."""
    req = None
    try:
        req = item_parser.parse(text).requirements.get("level")
    except Exception:  # noqa: BLE001 - a fit check never breaks a notice
        req = None
    who = None
    if build is not None:
        who = getattr(build, "ascendancy", None) or getattr(build, "class_name", None)
    if isinstance(req, int) and isinstance(level, int) and req > level:
        return {"ok": False, "kind": "level", "need": req, "level": level,
                "build_class": who}
    return {"ok": True, "kind": "build", "need": req, "level": level, "build_class": who}


def notice(result, entry, level, build):
    """The upgrade notice of a re-scored candidate, or None."""
    r = result if isinstance(result, dict) else {}
    if not r.get("ok") or r.get("verdict") != "upgrade":
        return None
    comps = [c for c in (r.get("comparisons") or []) if isinstance(c, dict)]
    best = next((c for c in comps if c.get("slot") == r.get("slot")),
                comps[0] if comps else {})
    eq = best.get("equipped") if isinstance(best.get("equipped"), dict) else {}
    item = r.get("item") if isinstance(r.get("item"), dict) else {}
    calc = r.get("calc") if isinstance(r.get("calc"), dict) else {}
    return {"name": item.get("name"), "base": item.get("base"),
            "slot": r.get("slot"), "empty": bool(best.get("empty")),
            "replaces": (eq.get("name") or eq.get("base")) if eq else None,
            "score_delta": r.get("score_delta"),
            "source": calc.get("source", "weights"),
            "dps_pct": _pct(best, "dps"), "ehp_pct": _pct(best, "ehp"),
            "new": entry.get("was") != "upgrade",
            "at": entry.get("at"),
            "fit": fit(entry.get("text"), level, build)}
