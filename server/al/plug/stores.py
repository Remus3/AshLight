"""RUN-DURABLE-STORES (finding F-014): the Checks rows of the core's saved
files, through the plug seam (decision 0056).

- One row while a store has changes its Saver could not write yet (run
  history, map ladder, price watch, zone visits, session summaries, and
  the Kindler tabs of plug/genbuilds.py, KINDLER-STORE, and the card
  layout of plug/uilayout.py, UI-CARD-COLLAPSE); the
  core keeps retrying with back-off (1, 5, 30, then every 60 s), so the
  row clears by itself once a save lands.
- One note once a damaged file was restored from its .bak (jsonfile
  read_json(..., backup=True)), kept for the life of the core. Only the
  store's name is shown, never a path.

The tick reads jsonfile.pop_restored() (the restores of this core's
files; others are dropped) and asks for a Checks refresh when either
list changes. Nothing is read from the game; no request is made.
"""

import logging
from pathlib import Path

from .. import jsonfile

ORDER = 100

log = logging.getLogger("al.stores")

# Saver name -> the words for it in the unsaved row
UNSAVED_WORDS = {
    "history": "run history",
    "ladder": "map ladder",
    "watch": "price watch list",
    "visits": "zone visits",
    "summary": "session summary",
    "genbuilds": "Kindler tabs",  # KINDLER-STORE (plug/genbuilds.py)
    "uilayout": "card layout",  # UI-CARD-COLLAPSE (plug/uilayout.py)
}

# file name -> (noun phrase, plural) for the restore note; the config file
# is matched by its path (core.config_path), any other by its name
RESTORED_WORDS = {
    "settings": ("settings", True),
    "consent.json": ("your log reading choice", False),
    "run_history.json": ("run history", False),
    "map_ladder.json": ("the map ladder", False),
    "price_watch.json": ("the price watch list", False),
    "session_summaries.json": ("session summaries", True),
    "zone_visits.json": ("zone visits", True),
    "hints.json": ("hint progress", False),
    "verdicts.json": ("in-game check results", True),
    "worn_gear.json": ("worn gear", False),
    "gen_builds.json": ("Kindler tabs", True),  # KINDLER-STORE
    "ui_layout.json": ("the card layout", False),  # UI-CARD-COLLAPSE
}
OTHER_FILE = ("a saved file", False)

UNSAVED_FIX = ("Free some space on the drive, or close any program that has "
               "AshLight's files open.")


def _join(words):
    if len(words) == 1:
        return words[0]
    return ", ".join(words[:-1]) + " and " + words[-1]


def unsaved_text(names):
    """The unsaved row's sentence for Saver names, in UNSAVED_WORDS order."""
    words = [UNSAVED_WORDS[n] for n in UNSAVED_WORDS if n in names]
    return f"AshLight couldn't save your {_join(words)} yet. It keeps trying on its own."


def restored_text(names):
    """The restore note's sentence for RESTORED_WORDS keys, oldest first."""
    found = [RESTORED_WORDS.get(n, OTHER_FILE) for n in names]
    words = []
    for noun, _ in found:
        if noun not in words:
            words.append(noun)
    plural = len(words) > 1 or any(p for _, p in found)
    text = _join(words)
    return (text[:1].upper() + text[1:] + (" were" if plural else " was")
            + " damaged and restored from the last good copy.")


def _name_of(core, path):
    """The RESTORED_WORDS key of a restored path of this core, or None
    when the path belongs to another core (a test process)."""
    path = Path(path)
    if path == Path(core.config_path):
        return "settings"
    if path.parent != Path(core.runtime):
        return None
    return path.name


def attach(core):
    core.add_tick("tick_stores", lambda: tick(core))


def tick(core):
    """Collect this core's .bak restores and, when the unsaved or the
    restored list changed, refresh the Checks card on the next pass.
    True when it asked for a refresh."""
    restored = getattr(core, "stores_restored", None)
    if restored is None:
        restored = core.stores_restored = []
    for path in jsonfile.pop_restored():
        name = _name_of(core, path)
        if name is not None and name not in restored:
            restored.append(name)
            log.warning("restored %s from its .bak", name)
    savers = getattr(core, "savers", None) or {}
    unsaved = tuple(n for n, s in savers.items() if s.dirty)
    key = (unsaved, tuple(restored))
    if key == getattr(core, "_stores_key", ((), ())):
        return False
    before = getattr(core, "_stores_key", ((), ()))[0]
    for n in unsaved:
        if n not in before:
            log.warning("could not save %s: %s", n,
                        savers[n].last_error or "the save failed")
    for n in before:
        if n not in unsaved:
            log.info("saved %s again", n)
    core._stores_key = key
    core._next_diag = 0.0  # the Checks card shows it on the next loop pass
    return True


def facts(core, now):
    savers = getattr(core, "savers", None) or {}
    return {"stores_unsaved": [n for n, s in savers.items() if s.dirty],
            "stores_restored": list(getattr(core, "stores_restored", None) or [])}


def rows(f, now):
    out = []
    unsaved = [n for n in (f.get("stores_unsaved") or ()) if n in UNSAVED_WORDS]
    if unsaved:
        out.append({"id": "stores_unsaved", "label": "Saved data", "status": "fail",
                    "detail": unsaved_text(unsaved), "fix": UNSAVED_FIX})
    restored = [n for n in (f.get("stores_restored") or ()) if isinstance(n, str)]
    if restored:
        out.append({"id": "stores_restored", "label": "Saved data", "status": "note",
                    "detail": restored_text(restored)})
    return out
