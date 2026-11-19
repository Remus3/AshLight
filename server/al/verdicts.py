"""RUN-VERDICTS-CORE (finding F-062, OPEN-27; decision 0040 amendment
2026-11-18): the 'Tried in game' verdict store.

Some checks only the player can make in game: does an AshLight-made
.build load, does a search string do what it says, does the filter
snippet or a merged filter import, does the overlay keep its FPS budget.
The player records each try with one dashboard click, Worked or Refused,
plus an optional short note. The record is one bounded local file,
ops/runtime/verdicts.json (gitignored); nothing is sent to the game or
anywhere else, and nothing is read from the game.

- Check ids are a fixed list (CHECKS); any other id is refused.
- A result is "worked" or "refused".
- A note is optional, printable ASCII (0x20 to 0x7e) of at most MAX_NOTE
  characters after trimming; anything else is refused, never cut.
- The file keeps the newest MAX_ROWS rows; the newest row of a check is
  its verdict. Written through jsonfile (atomic, durable, one .bak).

tools/live_verdicts.py reads the file back and drafts the ROADMAP flips.
Standard library only.
"""

import threading
import time
from pathlib import Path

from . import jsonfile

FILE_NAME = "verdicts.json"
SCHEMA = 1
MAX_ROWS = 50
MAX_NOTE = 200
MAX_BYTES = 64 * 1024  # 50 rows of a 200-char note fit with room to spare

# (check id, what the player tried). Order is the card's order.
CHECKS = (
    ("TC-BUILDFILE-LIVE", "An AshLight-made .build file loaded in game"),
    ("LIVE-SEARCHSTR", "A copied search string pasted into a game search box"),
    ("LIVE-FILTER", "The downloaded AshLight filter snippet imported in game"),
    ("LIVE-FILTER-MERGE", "A merged filter (your filter plus AshLight's blocks) loaded in game"),
    ("OVL-FPS", "One map played with the overlay shown, FPS as usual"),
)
CHECK_IDS = tuple(c for c, _ in CHECKS)
LABELS = dict(CHECKS)
RESULTS = ("worked", "refused")


class VerdictError(ValueError):
    """A verdict the store refuses; str() is the reason, safe to show."""


def clean_note(note):
    """The trimmed note ('' for None), or VerdictError."""
    if note is None:
        return ""
    if not isinstance(note, str):
        raise VerdictError("note must be text")
    note = note.strip()
    if len(note) > MAX_NOTE:
        raise VerdictError(f"note is longer than {MAX_NOTE} characters")
    if any(not (0x20 <= ord(ch) <= 0x7e) for ch in note):
        raise VerdictError("note must be plain ASCII letters, digits and punctuation")
    return note


def make_row(check, result, note=None, now=None):
    """A clean verdict row, or VerdictError."""
    if not isinstance(check, str) or check not in LABELS:
        raise VerdictError("unknown check id")
    if result not in RESULTS:
        raise VerdictError("result must be worked or refused")
    at = int(time.time() if now is None else now)
    return {"check": check, "result": result, "note": clean_note(note), "at": at}


def _clean_row(raw):
    """A row read from the file, cleaned, or None."""
    if not isinstance(raw, dict):
        return None
    at = raw.get("at")
    if isinstance(at, bool) or not isinstance(at, int) or at < 0:
        return None
    try:
        return make_row(raw.get("check"), raw.get("result"), raw.get("note"), now=at)
    except VerdictError:
        return None


def load(path):
    """The clean rows of the file, oldest first, at most MAX_ROWS ([] when
    missing, oversized or broken; a broken file falls back to its .bak)."""
    doc = jsonfile.read_json(path, max_bytes=MAX_BYTES, kind=dict, backup=True)
    raw = doc.get("rows") if isinstance(doc, dict) else None
    if not isinstance(raw, list):
        return []
    rows = [r for r in (_clean_row(x) for x in raw[-MAX_ROWS:]) if r is not None]
    return rows[-MAX_ROWS:]


def latest(rows):
    """{check id: its newest row} over `rows` (oldest first)."""
    out = {}
    for r in rows:
        out[r["check"]] = r
    return out


def view(rows):
    """The API / read-back document: every check with its newest verdict
    (None when untried) and the rows, newest first."""
    last = latest(rows)
    return {"schema": SCHEMA,
            "checks": [{"id": cid, "label": label, "verdict": last.get(cid)}
                       for cid, label in CHECKS],
            "results": list(RESULTS),
            "max_note": MAX_NOTE,
            "rows": list(reversed(rows))}


class VerdictStore:
    """The verdict file of one runtime dir. Thread safe: HTTP handler
    threads call add() and snapshot()."""

    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.rows = load(self.path)

    def add(self, check, result, note=None, now=None):
        """Record one verdict and write the file. Returns the row.
        VerdictError for a refused verdict (nothing changed); OSError when
        the file could not be written (nothing changed in memory)."""
        row = make_row(check, result, note, now)
        with self._lock:
            rows = (self.rows + [row])[-MAX_ROWS:]
            jsonfile.write_json(self.path, {"schema": SCHEMA, "rows": rows},
                                backup=True)
            self.rows = rows
        return dict(row)

    def snapshot(self):
        with self._lock:
            rows = [dict(r) for r in self.rows]
        return view(rows)


def default_path(runtime):
    return Path(runtime) / FILE_NAME
