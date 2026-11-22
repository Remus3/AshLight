"""RUN-UNKNOWN-ITEM-TEXT (finding F-185, research 0056 R3; folded into
RUN-REPORT-FIELDS): the session's "Not counted" mod lines, through the
plug seam (decision 0056).

Each item-check press already works out the mod lines no stat weight
counts (the evaluation's "unweighted" list, server/al/theorycraft/
live.py). attach() gives the core one Lines list (core.unknown_items) and
hands its add() to the core's LastEval, so every fresh press adds its
lines: deduplicated (case-insensitive), at most MAX_LINES, the oldest
dropped first. The list lives in memory only and never reaches a file
(decision 0045: item text in memory only); a core restart starts it
empty. No new read: the lines come from the one per-press clipboard text
(decision 0003).

The Checks view shows one note with the count while the list holds any;
the report copied on the player's click lists the lines, redacted
(server/al/report.py, decision 0040). Nothing is sent anywhere.
"""

import collections
import threading

ORDER = 160
MAX_LINES = 200
LINE_MAX = 200       # one stored line is cut to this many characters
ROW_ID = "unknown_items"
LABEL = "Not counted mod lines"


class Lines:
    """A thread-safe, deduplicated, capped list of mod line texts."""

    def __init__(self, cap=MAX_LINES):
        self.cap = int(cap)
        self._lock = threading.Lock()
        self._items = collections.OrderedDict()  # lower-case key -> text

    def add(self, lines):
        """Add each text of `lines` once; returns how many were new."""
        if isinstance(lines, str) or not isinstance(lines, (list, tuple)):
            return 0
        new = 0
        with self._lock:
            for line in lines:
                if not isinstance(line, str):
                    continue
                text = " ".join(line.split())[:LINE_MAX]
                if not text:
                    continue
                key = text.lower()
                if key in self._items:
                    continue
                self._items[key] = text
                new += 1
                while len(self._items) > self.cap:
                    self._items.popitem(last=False)
        return new

    def lines(self):
        with self._lock:
            return list(self._items.values())

    def __len__(self):
        with self._lock:
            return len(self._items)


def attach(core):
    core.unknown_items = Lines()
    last_eval = getattr(core, "last_eval", None)
    if last_eval is not None:
        last_eval.unknown_sink = core.unknown_items.add


def facts(core, now):
    lines = getattr(core, "unknown_items", None)
    return {"unknown_items": len(lines) if lines is not None else 0}


def detail_text(n):
    what = "1 mod line" if n == 1 else f"{n} mod lines"
    return (f"{what} from your item checks this session had no weight. "
            "Copy report lists them.")


def rows(f, now):
    n = f.get("unknown_items")
    if isinstance(n, bool) or not isinstance(n, int) or n <= 0:
        return None
    return {"id": ROW_ID, "label": LABEL, "status": "note", "detail": detail_text(n)}
