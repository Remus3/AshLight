"""UI-CARD-COLLAPSE (decision 0082 part 3 and its 2026-11-19 amendment):
the collapsed cards of the desktop client's companion window.

One small file in the runtime dir, ops/runtime/ui_layout.json, schema 1:

    {"schema": 1, "collapsed": {"<card id>": true | false, ...}}

Only the ids in CARD_IDS (the cards of Build and items and of Run) are
kept; an unknown id, a value that is not a boolean or a file that is not
an object is dropped on read (decision 0036 style bounds), and a missing
or unreadable file means every card is open. Each save keeps one .bak
(jsonfile write_json backup=True) and a damaged file is restored from it
on read (RUN-DURABLE-STORES). Play's regions and Settings never collapse,
so they have no id here.

A view preference, not player data: not in the settings export and not
emptied by Clear run history. Nothing is read from the game; nothing is
sent anywhere. Standard library only.
"""

import threading
from pathlib import Path

from . import jsonfile

SCHEMA = 1
FILE_NAME = "ui_layout.json"
MAX_BYTES = 4096

# the cards that collapse, in page order: Build and items, then Run
BUILD_CARDS = ("buildbox", "healthbox", "searchbox", "evalbox", "pricesbox", "weightsbox")
RUN_CARDS = ("summarybox", "actsbox", "mapsbox", "deathsbox", "eventsbox", "charsbox")
CARD_IDS = BUILD_CARDS + RUN_CARDS

BAD_BODY = "That layout change was not understood."


class LayoutError(ValueError):
    """A refused change; str() is the player's sentence."""


def default_path(runtime):
    return Path(runtime) / FILE_NAME


def clean(doc):
    """The {id: bool} map of a parsed document: allowed ids with boolean
    values only; anything else is dropped."""
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        return {}
    got = doc.get("collapsed")
    if not isinstance(got, dict):
        return {}
    return {k: v for k, v in got.items() if k in CARD_IDS and isinstance(v, bool)}


class UiLayout:
    """The collapsed state, kept in memory and written on every change."""

    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._collapsed = clean(jsonfile.read_json(
            self.path, max_bytes=MAX_BYTES, kind=dict, default=None, backup=True))

    def view(self):
        """{"schema", "cards", "collapsed"}: every allowed id, open (false)
        unless saved as collapsed."""
        with self._lock:
            got = dict(self._collapsed)
        return {"schema": SCHEMA, "cards": list(CARD_IDS),
                "collapsed": {k: bool(got.get(k, False)) for k in CARD_IDS}}

    def update(self, body):
        """Merge {"collapsed": {id: bool}} into the state (unknown ids are
        dropped, as on read) and save. Raises LayoutError for a body of
        another shape (nothing changes) and OSError when the write fails
        (the change stays in memory; the caller marks its Saver)."""
        if not isinstance(body, dict) or set(body) != {"collapsed"}:
            raise LayoutError(BAD_BODY)
        got = body["collapsed"]
        if not isinstance(got, dict) or not all(
                isinstance(k, str) and isinstance(v, bool) for k, v in got.items()):
            raise LayoutError(BAD_BODY)
        with self._lock:
            for k, v in got.items():
                if k in CARD_IDS:
                    self._collapsed[k] = v
        self.save()

    def save(self):
        """Write the state (one .bak). Only collapsed cards are listed, so
        an all-open layout is an empty map."""
        with self._lock:
            doc = {"schema": SCHEMA,
                   "collapsed": {k: True for k in CARD_IDS if self._collapsed.get(k)}}
        jsonfile.write_json(self.path, doc, backup=True)
