"""PLAY-F-186A (finding F-186, decision 0074): the player's own notes.

One plain-text note per zone and character, written by the player and shown
by itself on the next entry of that zone as the 'your note' row of the Play
view's guide mode (server/al/playcards.py). Nothing game-side: the key is
the Client.txt area id the log already gives (no new read) and the
character name of decision 0038; the text is whatever the player typed.

- The file is ops/runtime/player_notes.json (the runtime dir comes from
  server/al/paths.py), one bounded document:
  {"schema": 1, "notes": [{"character", "area_id", "text", "at"}, ...]},
  at most MAX_ZONES entries in all, each text at most MAX_NOTE characters,
  at most MAX_CHARACTERS characters. Written through jsonfile (atomic,
  ASCII + LF, one .bak of the last good copy).
- It is written only by save(), which POST /api/player-note calls on the
  player's Save (token, Host / Origin checks, plain text body, size cap).
  An empty text removes the note. Over the cap the oldest notes leave.
- It joins the hot reload registry (decision 0042), stat-throttled: the
  registry poll stats it at most once per CHECK_S (60 s), so the core
  tick's stat budget (B3) is unchanged; a Save refreshes at once (AshLight
  is the only writer), a hand edit is picked up within a minute. A
  malformed file keeps the last good copy and shows one Checks note. At start a malformed file falls back to its
  .bak as the last good copy (the broken file itself is left alone until
  the next Save writes over it).
- Plain text, no markup: whitespace runs fold to one space, control and
  format characters are refused, never cut; a text over MAX_NOTE is
  refused, never cut. Renderers show it as text only.

Names and notes stay local: nothing here is sent, reported or exported
(decision 0074; the settings export option is PLAY-F-186B's, only when the
player picks it). Standard library only.
"""

import copy
import json
import re
import threading
import time
import unicodedata
from pathlib import Path

from . import hotreload
from . import jsonfile
from .text import playernotes as _words

FILE_NAME = "player_notes.json"
SCHEMA = 1
NAME = _words.NAME      # the hot reload / Checks note name
MAX_ZONES = 300         # notes in the whole file
MAX_NOTE = 200          # characters of one note
MAX_CHARACTERS = 12     # decision 0038's character bound
MAX_NAME = 64           # characters of a character name
# worst case: 300 entries of a 200-character note and a 64-character name,
# every character an escaped surrogate pair (12 bytes), plus the keys
MAX_BYTES = 2 * 1024 * 1024
AREA_RE = re.compile(r"^[A-Za-z0-9_]{1,64}$")
_BAD_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Cn")


# The player sentences live in server/al/text/playernotes.py (design gate,
# copy sheet docs/design/copy/playernotes.md); re-exported, same objects.
# PN-2: refusals the Save shows, each a sentence with a next step
TEXT_LONG = _words.text_long(MAX_NOTE)
TEXT_BAD = _words.TEXT_BAD
NO_CHARACTER = _words.NO_CHARACTER
NO_ZONE = _words.NO_ZONE
# PN-1: why a notes file did not load (the hot reload note's reason)
FILE_FORMAT = _words.FILE_FORMAT
FILE_ROW = _words.FILE_ROW
FILE_TWO = _words.FILE_TWO
FILE_LONG = _words.file_long(MAX_NOTE)
FILE_MANY = _words.file_many(MAX_ZONES)
FILE_CHARS = _words.file_chars(MAX_CHARACTERS)
FILE_BIG = _words.FILE_BIG
FIX_TAIL = _words.FIX_TAIL
# B3 (tests/test_budget_tick.py): the registry poll stats the file at most
# once per CHECK_S; a Save refreshes at once, so only an outside edit waits
CHECK_S = 60.0


class NoteError(ValueError):
    """A note the store refuses; str() is the reason, safe to show."""


def clean_text(text):
    """The note as stored ('' removes it), or NoteError. Whitespace runs
    (new lines and tabs too) fold to one space; nothing is cut."""
    if not isinstance(text, str):
        raise NoteError(TEXT_BAD)
    text = " ".join(text.split())
    if len(text) > MAX_NOTE:
        raise NoteError(TEXT_LONG)
    if any(unicodedata.category(ch) in _BAD_CATEGORIES for ch in text):
        raise NoteError(TEXT_BAD)
    return text


def clean_area(area_id):
    if not isinstance(area_id, str) or not AREA_RE.match(area_id):
        raise NoteError(NO_ZONE)
    return area_id


def clean_name(name):
    if (not isinstance(name, str) or not name or len(name) > MAX_NAME
            or name != name.strip()
            or any(unicodedata.category(ch) in _BAD_CATEGORIES for ch in name)):
        raise NoteError(NO_CHARACTER)
    return name


def _at(v):
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        raise ValueError(FILE_ROW)
    return v


def from_doc(doc):
    """{character: {area id: {"text", "at"}}} from a parsed file; ValueError
    on anything outside the bounds (the hot reload keeps the last good
    copy then)."""
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise ValueError(FILE_FORMAT)
    rows = doc.get("notes")
    if not isinstance(rows, list):
        raise ValueError(FILE_FORMAT)
    if len(rows) > MAX_ZONES:
        raise ValueError(FILE_MANY)
    book = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(FILE_ROW)
        raw = row.get("text")
        if isinstance(raw, str) and len(raw) > MAX_NOTE:
            raise ValueError(FILE_LONG)
        try:
            name = clean_name(row.get("character"))
            area = clean_area(row.get("area_id"))
            text = clean_text(raw)
        except NoteError:
            raise ValueError(FILE_ROW) from None
        if not text or text != raw:
            raise ValueError(FILE_ROW)
        per = book.setdefault(name, {})
        if area in per:
            raise ValueError(FILE_TWO)
        per[area] = {"text": text, "at": _at(row.get("at"))}
    if len(book) > MAX_CHARACTERS:
        raise ValueError(FILE_CHARS)
    return book


def check(path):
    """The hot reload check: size cap, JSON object, then from_doc's bounds
    (so a bad file is refused before it replaces the last good copy)."""
    p = Path(path)
    if p.stat().st_size > MAX_BYTES:
        raise ValueError(FILE_BIG)
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, RecursionError):
        raise ValueError(FILE_FORMAT) from None
    from_doc(doc)
    return doc


def count(book):
    return sum(len(per) for per in book.values())


def to_doc(book):
    """The file document of a book, oldest note first."""
    rows = [{"character": name, "area_id": area, "text": e["text"], "at": e["at"]}
            for name, per in book.items() for area, e in per.items()]
    rows.sort(key=lambda r: (r["at"], r["character"], r["area_id"]))
    return {"schema": SCHEMA, "notes": rows}


def _trim(book, keep):
    """Drop the oldest notes (never `keep`, the one just saved) until the
    book is inside both bounds."""
    while len(book) > MAX_CHARACTERS:
        oldest = min((n for n in book if n != keep[0]),
                     key=lambda n: max(e["at"] for e in book[n].values()))
        del book[oldest]
    while count(book) > MAX_ZONES:
        name, area = min(((n, a) for n, per in book.items() for a in per
                          if (n, a) != keep),
                         key=lambda k: (book[k[0]][k[1]]["at"], k))
        del book[name][area]
        if not book[name]:
            del book[name]


class _NotesWatch(hotreload.Watched):
    """The notes file's Watched (decision 0042) with two changes: get()
    stats at most once per CHECK_S unless forced (the registry poll runs it
    every core tick, B3), and a held last good copy says how to fix it."""

    def __init__(self, *a, clock=time.monotonic, **kw):
        self._mono = clock
        self._checked = None
        super().__init__(*a, **kw)

    def _note(self, text):
        if text.endswith(_words.HELD_TAIL):
            text = f"{text} {FIX_TAIL}"
        super()._note(text)

    def _notify(self, value):
        """Every fresh load, the first too (a file made after start: the
        base class skips loads == 1, which the start read already covers)."""
        if self.on_change is not None:
            try:
                self.on_change(value)
            except Exception:  # noqa: BLE001 - a listener never breaks a load
                hotreload.LOG.exception("hot reload listener failed for %s",
                                        self.name)

    def get(self, force=False):
        now = self._mono()
        if (not force and self._checked is not None
                and now - self._checked < CHECK_S):
            with self._lock:
                return self._value
        self._checked = now
        return super().get()


class PlayerNotes:
    """The notes file of one runtime dir. Thread safe: HTTP handler threads
    call save(); the core reads book() (no stat)."""

    def __init__(self, path, registry=None, clock=time.time, on_change=None,
                 mono=time.monotonic):
        """on_change(book), optional: called after a re-read made by the
        hot reload registry's throttled poll (a hand edit, or this store's
        own write), so the core publishes it with no stat of its own (B3).
        mono: the monotonic clock of the throttle (tests replace it)."""
        self.path = Path(path)
        self._clock = clock
        self._lock = threading.RLock()
        self._listener = on_change
        self._seen = self._book = None
        self.watch = _NotesWatch(self.path, hotreload.load_json, name=NAME,
                                 default=dict, check=check, from_doc=from_doc,
                                 registry=registry, on_change=self._loaded,
                                 clock=mono)
        self._seen = self.watch.get()
        self._book = self._seen
        if self.watch.error:
            self._book = self._from_bak()

    def _from_bak(self):
        """The .bak as the last good copy when the file is malformed at
        start ({} when the .bak is missing or bad too)."""
        try:
            return from_doc(check(jsonfile.bak_path(self.path)))
        except (OSError, ValueError, RecursionError):
            return {}

    def _loaded(self, value):
        with self._lock:
            if value is not self._seen:
                self._seen = value
                self._book = value
            book = self._book
        if self._listener is not None:
            self._listener(book)

    def book(self):
        """The current book with no stat (the registry's poll keeps it
        fresh). Do not change it: save() makes a new one."""
        with self._lock:
            return self._book

    @property
    def error(self):
        return self.watch.error

    def get(self):
        """The current book (one stat; a re-read only on a change). Do not
        change it: save() makes a new one."""
        # forced, outside the lock: a re-read calls _loaded
        value = self.watch.get(force=True)
        with self._lock:
            if value is not self._seen:  # a fresh good load (hand edit, our write)
                self._seen = value
                self._book = value
            return self._book

    def note(self, character, area_id):
        """{"area_id", "text", "at"} of this character's note for the zone,
        or None."""
        if not isinstance(character, str) or not isinstance(area_id, str):
            return None
        e = self.get().get(character, {}).get(area_id)
        return {"area_id": area_id, "text": e["text"], "at": e["at"]} if e else None

    def save(self, character, area_id, text, now=None):
        """Store (or with an empty text remove) one note and write the file.
        Returns the note dict or None when removed. NoteError for a refused
        note; OSError when the file could not be written (nothing changed
        in memory)."""
        name, area, text = clean_name(character), clean_area(area_id), clean_text(text)
        at = int(self._clock() if now is None else now)
        with self._lock:
            book = copy.deepcopy(self._book)
            if text:
                book.setdefault(name, {})[area] = {"text": text, "at": at}
                _trim(book, (name, area))
            elif area in book.get(name, {}):
                del book[name][area]
                if not book[name]:
                    del book[name]
            jsonfile.write_json(self.path, to_doc(book), backup=True)
            self._book = book
        return {"area_id": area, "text": text, "at": at} if text else None


def default_path(runtime):
    return Path(runtime) / FILE_NAME
