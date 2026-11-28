"""ACTIVE-BUILD-PICK (decision 0096): which build is in use, per character.

One bounded player-data file, build/source.json under the core's runtime
dir (ops/runtime, gitignored; beside the per-character build files, so the
installer's migrate carries it with the build/ tree), schema 1, written
atomically with one `.bak` of its last good copy (jsonfile, F-014) and
read with the .bak restore:

    {"schema": 1, "chars": {"<character>": {"tab": "k1", "at": <unix s>}}}

Only Kindler choices are stored: a character with no entry uses its pasted
build (decision 0045). At most MAX_CHARS characters (decision 0038's
bound); the oldest choice leaves first. A choice whose Kindler tab is gone
or has no result reads as the pasted build and the file is left as it is
until the next choice. Not cleared by Clear run history (the build files
are not either) and not in the settings export. Character names stay on
this computer. Thread safe; standard library only; nothing is read from
the game, nothing is sent.
"""

import re
import threading
from pathlib import Path

from .. import jsonfile, num

DIR_NAME = "build"
FILE_NAME = "source.json"
SCHEMA = 1
MAX_CHARS = 12
MAX_NAME = 64
MAX_BYTES = 16 * 1024
_TAB = re.compile(r"^k[0-9]{1,6}$")


def default_path(runtime):
    return Path(runtime) / DIR_NAME / FILE_NAME


def clean_name(name):
    """A character name the file may hold, or None."""
    if not isinstance(name, str) or not 0 < len(name) <= MAX_NAME:
        return None
    if any(ord(c) < 32 or ord(c) == 127 for c in name):
        return None
    return name


def clean_tab(tab_id):
    return tab_id if isinstance(tab_id, str) and _TAB.match(tab_id) else None


def clean(doc):
    """{name: {"tab", "at"}} of a loaded document; bad entries dropped, at
    most MAX_CHARS (the newest)."""
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        return {}
    chars = doc.get("chars")
    if not isinstance(chars, dict):
        return {}
    out = {}
    for name, entry in chars.items():
        if clean_name(name) is None or not isinstance(entry, dict):
            continue
        tab = clean_tab(entry.get("tab"))
        at = num.finite(entry.get("at"))
        if tab is None or at is None or at < 0 or isinstance(entry.get("at"), bool):
            continue
        out[name] = {"tab": tab, "at": int(at)}
    return _bound(out)


def _bound(chars):
    if len(chars) <= MAX_CHARS:
        return chars
    keep = sorted(chars.items(), key=lambda kv: kv[1]["at"])[-MAX_CHARS:]
    return dict(keep)


class SourceStore:
    """The choices, kept in memory and written on every change. A failed
    write raises OSError with the change kept in memory (the plug marks its
    Saver, which writes it again with back-off)."""

    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._chars = clean(jsonfile.read_json(
            self.path, max_bytes=MAX_BYTES, kind=dict, default=None, backup=True))

    def get(self, name):
        """{"tab", "at"} of the character's Kindler choice, or None."""
        with self._lock:
            got = self._chars.get(name) if isinstance(name, str) else None
            return dict(got) if got else None

    def set(self, name, tab_id, at):
        """Make the Kindler tab the character's build in use. ValueError on
        a bad name or tab id."""
        name, tab_id = clean_name(name), clean_tab(tab_id)
        if name is None or tab_id is None:
            raise ValueError("bad build choice")
        with self._lock:
            self._chars.pop(name, None)
            self._chars[name] = {"tab": tab_id, "at": max(0, int(at))}
            self._chars = _bound(self._chars)
        self.save()

    def drop(self, name):
        """Back to the pasted build for the character. True when a choice
        was removed (and the file written)."""
        with self._lock:
            if not isinstance(name, str) or name not in self._chars:
                return False
            del self._chars[name]
        self.save()
        return True

    def save(self):
        with self._lock:
            doc = {"schema": SCHEMA, "chars": {k: dict(v) for k, v in self._chars.items()}}
        jsonfile.write_json(self.path, doc, backup=True)
