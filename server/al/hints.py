"""NEWBIE-HINTS: one-time first-hours hints for a new character (research
0032 sections 1 and 5.3; adjudicator ruling L).

Every trigger is a Client.txt event the core already parses, so nothing
shows before the player allows reading Client.txt:
- "start": the character's first level-up from level 1 (level 2). Only a
  character AshLight first sees at level 2 is new; one first seen higher
  is a veteran and never gets a hint.
- "town": its first town or hideout area generation (the item check
  hotkey how-to, the moment a player sorts loot). OVL-KEYS-WEB: it names
  the item check key the desktop client bound (its runtime file
  hotkeys.json beside the hint store, read through hotkeys.read_runtime,
  the source of the snapshot's hotkeys view); with no bound key it names
  no key (town_text).
- "campaign_death": its first death in a campaign area.
- "first_map": its first endgame map generation.
Each hint shows once per character, on the dashboard and in the event
list, and goes away by itself after HINT_S; none starts past MAX_LEVEL.

The text is AshLight's own wording of plain facts; no wiki or guide text
is bundled (decision 0009). Death penalty numbers stay out until the 1.0
patch notes confirm them.

Store (ruling L): one bounded JSON file in the runtime dir (ops/runtime,
gitignored) holding, per character, only whether it is new and the hint
ids already shown, keyed by a hash of the character name; the plain name
is never written. It is not tied to the run-history switch (ids carry no
history). Without the file (unreadable or unwritable) hints are kept for
this session only. "Reset hints" (dashboard button) clears the shown ids.
"""

import collections
import hashlib
from pathlib import Path

from . import acts, hotkeys, jsonfile

FILE_NAME = "hints.json"
SCHEMA = 1
HINT_S = 600.0
MAX_LEVEL = 30
MAX_CHARS = 50
MAX_BYTES = 64 * 1024
KEY_LEN = 16
_SALT = "AshLight NEWBIE-HINTS v1:"

# id -> text, in the order a new character usually meets them.
HINTS = collections.OrderedDict([
    ("start", "New character: this page follows your game by itself. Your "
              "zone, level, deaths and act times update as you play. The "
              "badge at the top shows when AshLight reads Client.txt."),
    ("town", "To check an item, copy it in the game with Ctrl+C. Then press "
             "{key}. AshLight reads the clipboard once for each press."),
    ("campaign_death", "Deaths in the campaign cost no experience. The Death "
                       "recap card shows where each one happened."),
    ("first_map", "Your first map. Unlike the campaign, deaths in endgame "
                  "maps cost experience. The Maps card times each map and "
                  "sorts them by map level."),
])

RESET_TEXT = "New-character tips will show again."
# The town hint's words while no item check key is bound (no client, or
# the client could not register one): no key is named.
NO_KEY = "the item check key shown under Settings"


def town_text(key):
    """The town hint with the bound item check key, or NO_KEY's words."""
    key = hotkeys.safe_accelerator(key) if key else None
    return HINTS["town"].replace("{key}", key or NO_KEY)


def char_key(name):
    """The store key of a character: a salted SHA-256 prefix, never the
    plain name. None for no name."""
    if not isinstance(name, str) or not name:
        return None
    return hashlib.sha256((_SALT + name).encode("utf-8")).hexdigest()[:KEY_LEN]


def _clean(doc):
    out = collections.OrderedDict()
    chars = doc.get("chars") if isinstance(doc, dict) else None
    if not isinstance(chars, dict):
        return out
    for key, c in chars.items():
        if (not isinstance(key, str) or len(key) != KEY_LEN
                or not isinstance(c, dict)):
            continue
        seen = c.get("seen") if isinstance(c.get("seen"), list) else []
        out[key] = {"fresh": c.get("fresh") is True,
                    "seen": [h for h in HINTS if h in seen]}
    while len(out) > MAX_CHARS:
        out.popitem(last=False)
    return out


def is_town(area_id):
    if not isinstance(area_id, str):
        return False
    low = area_id.lower()
    return "_town" in low or low.startswith("hideout")


class Hints:
    """The hint store and the hint on show. Not thread-safe: the
    SessionState lock guards it."""

    def __init__(self, path=None):
        self.path = None
        self.chars = collections.OrderedDict()
        self.shown = None
        if path is not None:
            self.use_file(path)

    def use_file(self, path):
        """Keep the store in `path` (loaded now). A bad file reads as
        empty; the memory store of this session merges in."""
        self.path = Path(path)
        loaded = _clean(jsonfile.read_json(self.path, max_bytes=MAX_BYTES, kind=dict,
                                           backup=True))
        for key, c in self.chars.items():
            loaded[key] = c
        self.chars = loaded

    def _save(self):
        if self.path is None:
            return
        try:
            jsonfile.write_json(self.path, {"schema": SCHEMA,
                                            "chars": dict(self.chars)},
                                backup=True)  # F-014: one .bak
        except OSError:
            self.path = None  # per-session fallback (ruling L)

    def _entry(self, name, level):
        """The store entry of `name`, made on first sight: new only when
        first seen at level 2."""
        key = char_key(name)
        if key is None:
            return None
        c = self.chars.get(key)
        if c is None:
            if not isinstance(level, int) or isinstance(level, bool):
                return None
            c = {"fresh": level == 2, "seen": []}
            self.chars[key] = c
            while len(self.chars) > MAX_CHARS:
                self.chars.popitem(last=False)
            self._save()
        self.chars.move_to_end(key)
        return c

    def fire(self, name, hint_id, level, at):
        """Show `hint_id` for `name` when it is new, below MAX_LEVEL and
        has not seen it. Returns the hint dict, or None."""
        if hint_id not in HINTS:
            return None
        c = self._entry(name, level)
        if (c is None or not c["fresh"] or hint_id in c["seen"]
                or not isinstance(level, int) or level > MAX_LEVEL):
            return None
        c["seen"].append(hint_id)
        self._save()
        text = town_text(self.bound_key()) if hint_id == "town" else HINTS[hint_id]
        self.shown = {"id": hint_id, "text": text, "at": at,
                      "expires_at": at + HINT_S}
        return dict(self.shown)

    def bound_key(self):
        """The item check key the desktop client bound, from its runtime
        file beside the store (hotkeys.read_runtime: bounded, validated),
        or None (no store, no file, or not registered)."""
        if self.path is None:
            return None
        rt = hotkeys.read_runtime(self.path.parent)
        ev = rt.get("eval") if isinstance(rt, dict) else None
        if isinstance(ev, dict) and ev.get("registered") is True:
            return ev.get("key")
        return None

    def on_level(self, name, level, at):
        c = self._entry(name, level)
        if c is not None and level == 2:
            return self.fire(name, "start", level, at)
        return None

    def on_area(self, name, area_id, level, at):
        if acts.is_endgame(area_id):
            return self.fire(name, "first_map", level, at)
        if is_town(area_id):
            return self.fire(name, "town", level, at)
        return None

    def on_death(self, name, area_id, level, at):
        if acts.act_of(area_id) is not None:
            return self.fire(name, "campaign_death", level, at)
        return None

    def reset(self):
        """The dashboard's "reset hints": every character's shown ids are
        cleared (new / veteran stays), the hint on show goes."""
        for c in self.chars.values():
            c["seen"] = []
        self.shown = None
        self._save()

    def view(self, now):
        """The snapshot `hint` part: the hint on show, or None."""
        s = self.shown
        if s is None or now >= s["expires_at"]:
            return None
        return dict(s)
