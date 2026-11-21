"""RUN-LEDGER-WIRE (finding F-061, research 0051 R1, research 0050 R11,
test C26; decision 0071): the parse ledger's wiring, through the plug
seam (decision 0056).

attach() gives the core one Wire (core.ledger_wire). Core.feed_line hands
it every tailed line with the event parser.parse_line made of it, and
Core.eval_press hands it the item text of each press. The wire keeps:

- the in-memory class counters and the drift counter
  (logshapes.Counters, logshapes.Drift). They run under the Client.txt
  opt-in alone and are never written;
- while the ledger's own consent is on (the "ledger" flag the core keeps
  in its tailer state, re-checked against consent.json before each
  write), the hit and shape ledger (logshapes.Ledger), five read-back
  booleans and the masked property-block shape of waystone presses.

The write tick puts the ledger in ops/runtime/logshapes.json at most once
a minute (WRITE_EVERY_S) and only when something changed. A write and the
core's ledger delete (revoking the consent) share core.ledger_lock, and a
revoke empties the in-memory ledger, so a revoked ledger is never written
again. A failed write keeps the changes and is tried again a minute later.

Read-back booleans (TEST-LIVE-CLICKS): zone, character, level, act and
session timer, each True once the state held a value for it after a
tailed line reached the ledger. Only True / False is stored, never the
value itself.

Waystone shape (LIVE-WAYSTONE): the first section after the header of a
waystone's item text (its property block), one line per "Key: value"
property. A key the game is known to print (KNOWN_KEYS) is kept in lower
case; any other key and every value goes through the logshapes allow-list
mask, so numbers become <n> and other words <w>. No item name, mod line
or note text is stored.

Checks notes (counts only): one when DRIFT_NOTE_AT anchored lines
("Generating level", "[SCENE]", "is now level", "has been slain") in one
game run matched no pattern (kept for the life of the core), and one
while the start-up resume scan stopped at its 32 MB cap before the game
session's start (research 0050 F15).

Nothing here reads Client.txt or the clipboard, starts a process or
makes a request.
"""

import json
import logging
import os
import re
import threading
import time

from .. import acts, jsonfile, logshapes, resume
from ..theorycraft import item as item_mod
from ..theorycraft import waystone as waystone_mod

ORDER = 150

log = logging.getLogger("al.ledger")

WRITE_EVERY_S = 60.0
READBACK = ("zone", "character", "level", "act", "session_timer")

MAX_WAYSTONE_SHAPES = 4    # distinct property-block shapes kept
MAX_WAYSTONE_LINES = 12    # property lines per shape
MAX_PRESS_CHARS = 16384    # longer press text is not looked at

# Property names the game prints in a waystone's property block (research
# 0031 4.3, theorycraft/waystone.py REWARDS keys), kept as they are.
KNOWN_KEYS = frozenset((
    "waystone tier", "revives available", "item quantity", "item rarity",
    "monster pack size", "pack size", "magic monsters", "rare monsters",
    "number of magic monsters", "number of rare monsters",
    "waystone drop chance", "waystones found", "item level", "area level",
    "quality"))
KEY_WORDS = frozenset(w for k in KNOWN_KEYS for w in k.split())
VALUE_WORDS = frozenset(("augmented",))
_HOUR_OK = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}$")
_SAFE_WORDS = logshapes.ALLOW | logshapes.TEMPLATE_WORDS | KEY_WORDS | VALUE_WORDS

ROW_DRIFT = "log_drift"
ROW_CAP = "log_resume_cap"
LABEL = "Game log"
DRIFT_TEXT = ("Some game log lines look different from what AshLight knows, "
              "maybe after a game update. Zone, level or death counts may "
              "stop updating.")
CAP_TEXT = ("The game log is very large, so AshLight read only its newest "
            "32 MB at start. Deaths and level-ups from earlier in this "
            "session may be missing.")


# -- the waystone property block -------------------------------------------

def _is_property(line):
    key, sep, _ = line.partition(":")
    return bool(sep) and 0 < len(key) <= 40 and key[:1].isalpha() and key[:1].isupper()


def _mask_key(key):
    low = " ".join(key.lower().split())
    return low if low in KNOWN_KEYS else logshapes.mask(key)


def waystone_shape(text):
    """The masked property-block shape of a waystone's item text, as a
    tuple of lines, or None for any other text."""
    if not isinstance(text, str) or len(text) > MAX_PRESS_CHARS:
        return None
    parsed = item_mod.parse(text)
    if not parsed.is_item or not waystone_mod.is_waystone(parsed):
        return None
    sections, cur = [], []
    for ln in text.replace("\r\n", "\n").split("\n"):
        ln = ln.strip()
        if ln == item_mod.SEPARATOR:
            if cur:
                sections.append(cur)
            cur = []
        elif ln:
            cur.append(ln)
    if cur:
        sections.append(cur)
    if len(sections) < 2:
        return None
    out = []
    for ln in sections[1]:
        if not _is_property(ln):
            continue
        key, _, value = ln.partition(":")
        k = _mask_key(key)
        v = logshapes.mask(value, logshapes.ALLOW | VALUE_WORDS) if value.strip() else ""
        line = f"{k}: {v}" if v else f"{k}:"
        if is_safe_line(line):
            out.append(line)
        if len(out) >= MAX_WAYSTONE_LINES:
            break
    return tuple(out) if out else None


def is_safe_line(line):
    """True when every token of a stored waystone line is an allowed word,
    a known key word, a placeholder or ASCII punctuation."""
    return (isinstance(line, str) and 0 < len(line) <= logshapes.MAX_SHAPE_CHARS
            and line.isascii()
            and all(logshapes.is_safe_token(t, _SAFE_WORDS) for t in line.split(" ")))


# -- the wire ----------------------------------------------------------------

class Wire:
    """The ledger's state between feed_line, the press and the write tick.
    Thread safe: the tailer thread feeds, an HTTP thread presses, the core
    loop ticks."""

    def __init__(self, core):
        self.core = core
        self.lock = threading.Lock()
        self.clock = time.monotonic   # tests replace it
        self.wall = time.time         # hour stamps of waystone shapes
        self.counters = logshapes.Counters()
        self.drift = logshapes.Drift()
        self.drift_seen = False       # DRIFT_NOTE_AT misses in one run, sticky
        self._drift_new = False
        self.last_write = None
        self.writes = 0
        self.write_failed = False
        self._clear()

    def _clear(self):
        self.ledger = logshapes.Ledger()
        self.readback = dict.fromkeys(READBACK, False)
        self.waystones = {}           # tuple of lines -> [n, first, last]; LRU
        self.dirty = False            # read-back or waystone change
        self.fed = False              # a line reached the ledger since the tick

    def on(self):
        """The ledger consent as the core's tailer state holds it (an
        in-memory flag set at start and by every consent change)."""
        return self.core.state.tailer.get("ledger") is True

    def path(self):
        return self.core.ledger_path()

    # -- inputs
    def feed(self, line, ev):
        """One tailed line and its event (None for none)."""
        split = logshapes.classify(line, ev)
        on = self.on()
        with self.lock:
            self.counters.observe(line, ev, split)
            if self.drift.observe(line, ev) and self.drift.due and not self.drift_seen:
                self.drift_seen = True
                self._drift_new = True
            if on:
                self.ledger.observe(line, ev, split=split)
                self.fed = True

    def press(self, text):
        """One item press: a waystone's masked property block, while the
        ledger consent is on. Returns the shape recorded, or None."""
        if not self.on():
            return None
        shape = waystone_shape(text)
        if shape is None:
            return None
        hour = logshapes.hour_of(self.wall())
        with self.lock:
            rec = self.waystones.pop(shape, None)
            if rec is None:
                while len(self.waystones) >= MAX_WAYSTONE_SHAPES:
                    self.waystones.pop(next(iter(self.waystones)))
                rec = [0, hour, hour]
                self.dirty = True
            rec[0] += 1
            if rec[2] != hour:
                rec[2] = hour
                self.dirty = True
            self.waystones[shape] = rec
        return shape

    # -- read-back
    def _readback_now(self):
        st = self.core.state
        level = st.level
        started = st.session_started_at
        return {
            "zone": isinstance(st.zone, str) and bool(st.zone),
            "character": isinstance(st.character, str) and bool(st.character),
            "level": isinstance(level, int) and not isinstance(level, bool),
            "act": acts.act_of(st.area_id) is not None or bool(st.acts.splits),
            "session_timer": (isinstance(started, (int, float))
                              and not isinstance(started, bool)
                              and st.events_seen > 0),
        }

    # -- the file
    def to_dict(self):
        doc = self.ledger.to_dict()
        doc["readback"] = dict(self.readback)
        doc["waystone"] = [[list(k)] + list(v) for k, v in self.waystones.items()]
        return doc

    def dumps(self):
        """The file text, under logshapes.MAX_BYTES (least recently seen
        shapes go first, then waystone shapes)."""
        while True:
            text = json.dumps(self.to_dict(), separators=(",", ":"))
            if len(text) < logshapes.MAX_BYTES:
                return text
            if self.ledger.shapes:
                self.ledger._evict()
            elif self.waystones:
                self.waystones.pop(next(iter(self.waystones)))
            else:
                return text

    def load(self, data):
        """Take back a file's content; anything malformed is dropped."""
        led = logshapes.Ledger.from_dict(data)
        rb = dict.fromkeys(READBACK, False)
        ways = {}
        if isinstance(data, dict) and data.get("schema") == logshapes.SCHEMA:
            got = data.get("readback")
            if isinstance(got, dict):
                for k in READBACK:
                    if got.get(k) is True:
                        rb[k] = True
            rows = data.get("waystone")
            for row in rows if isinstance(rows, list) else ():
                if not (isinstance(row, list) and len(row) == 4
                        and isinstance(row[0], list)
                        and 0 < len(row[0]) <= MAX_WAYSTONE_LINES
                        and all(is_safe_line(x) for x in row[0])
                        and isinstance(row[1], int) and not isinstance(row[1], bool)
                        and row[1] >= 0
                        and all(isinstance(h, str) and _HOUR_OK.match(h) for h in row[2:])):
                    continue
                if len(ways) >= MAX_WAYSTONE_SHAPES:
                    ways.pop(next(iter(ways)))
                ways[tuple(row[0])] = [row[1], row[2], row[3]]
        with self.lock:
            self.ledger = led
            self.readback = rb
            self.waystones = ways
            self.dirty = False
            self.fed = False

    def load_file(self):
        """Read the existing file back (at start, with the consent on)."""
        data = jsonfile.read_json(self.path(), max_bytes=2 * logshapes.MAX_BYTES,
                                  encoding="ascii", kind=dict, default=None)
        if data is not None:
            self.load(data)
        return data is not None

    def reset(self):
        """The ledger consent was revoked: forget everything it kept (the
        core deletes the file). Counters and drift stay (Client.txt)."""
        with self.lock:
            self._clear()

    def tick(self, now=None):
        """From the core loop. True when the file was written."""
        if self._drift_new:
            self._drift_new = False
            self.core._next_diag = 0.0  # the Checks card shows the note next pass
        if not self.on():
            if self.dirty or self.fed or self.ledger.hits or self.waystones:
                self.reset()
            return False
        with self.lock:
            if self.fed:
                self.fed = False
                for k, v in self._readback_now().items():
                    if v and not self.readback[k]:
                        self.readback[k] = True
                        self.dirty = True
            changed = self.dirty or self.ledger.dirty
        if not changed:
            return False
        now = self.clock() if now is None else now
        if self.last_write is not None and now - self.last_write < WRITE_EVERY_S:
            return False
        return self.write(now)

    def write(self, now):
        lock = getattr(self.core, "ledger_lock", None) or threading.Lock()
        with lock:
            if not self.core.ledger_consented():
                self.reset()
                return False
            with self.lock:
                text = self.dumps()
                self.ledger.dirty = False
                self.dirty = False
            self.last_write = now
            try:
                jsonfile.write_text(self.path(), text + "\n")
                try:
                    os.chmod(self.path(), 0o600)
                except OSError:
                    pass
            except (OSError, ValueError) as exc:
                with self.lock:
                    self.dirty = True  # tried again after WRITE_EVERY_S
                if not self.write_failed:
                    log.warning("could not write the parse ledger: %s",
                                type(exc).__name__)
                self.write_failed = True
                return False
        if self.write_failed:
            log.info("wrote the parse ledger again")
        self.write_failed = False
        self.writes += 1
        return True


# -- plug hooks ----------------------------------------------------------------

def attach(core):
    wire = Wire(core)
    core.ledger_wire = wire
    if core.ledger_consented():
        wire.load_file()
    core.add_tick("tick_ledger", wire.tick)


def resume_capped(core):
    """True when the start-up resume scan stopped at its byte cap before
    it reached the game session's start line."""
    res = core.state.tailer.get("resume")
    if not isinstance(res, dict) or res.get("hit_marker"):
        return False
    n = res.get("bytes")
    return (isinstance(n, int) and not isinstance(n, bool)
            and n >= resume.DEFAULT_MAX_BYTES)


def facts(core, now):
    wire = getattr(core, "ledger_wire", None)
    return {"log_drift": bool(wire is not None and wire.drift_seen),
            "log_resume_capped": resume_capped(core)}


def rows(f, now):
    out = []
    if f.get("log_drift") is True:
        out.append({"id": ROW_DRIFT, "label": LABEL, "status": "note",
                    "detail": DRIFT_TEXT})
    if f.get("log_resume_capped") is True:
        out.append({"id": ROW_CAP, "label": LABEL, "status": "note",
                    "detail": CAP_TEXT})
    return out
