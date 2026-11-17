"""TC-UPGRADE-STATS (decision 0037): trade stat ids for the upgrade link.

The ids come ONLY from the `trade_stats` field of the repoe-fork
`stat_translations` file that the build-time snapshot already fetches into
the sidecar cache (decision 0009, behind web_data, decision 0013). repoe-fork
relays them from Grinding Gear Games' trade site data; AshLight never calls
any trade endpoint to get or check them (decision 0017), bundles no id
table, and never guesses an id: a stat without an id gets no filter.

Read only, no network, no clipboard, nothing sent to the game.
`load_index(path)` maps a normalised mod text (the weights key form,
"+# to maximum Life") to its explicit trade id ("explicit.stat_3299347043").

MATH-TRADESTAT-COVER: the match is exact on the normalised template text.
Only about 290 of the ~10800 entries in the cached file carry
`trade_stats`; repoe-fork attaches none to an entry whose English string
holds game markup ("{0}% to [Resistances|Fire Resistance]",
"{0} to [Strength|Strength]", "{0}% increased [Armour|Armour]"), which is
every resistance, attribute, armour / evasion / energy shield and most
damage mod. Those keys therefore have no id in the file and stay
unfiltered: the trade number is never derived from the stat name (that
would be a guess, decision 0037 item 3). `coverage(index, keys)` reports
which keys map.
"""

import json
import os
import re
import threading
from pathlib import Path

from .theorycraft import datacredit

FILE_NAME = "stat_translations.json"
MAX_BYTES = 64 * 1024 * 1024
MAX_TEXT = 200
KIND = "explicit"
_ID_RE = re.compile(r"^explicit\.stat_[0-9]{1,10}$")
_SPACE_RE = re.compile(r"\s+")
# game markup "[Tag|Shown text]" / "[Shown]" -> the shown text, so a
# marked-up template still compares exactly with its plain twin
_MARKUP_RE = re.compile(r"\[(?:[^\[\]|]*\|)?([^\[\]|]*)\]")


def norm(text):
    """The match form of a mod text: markup shown text only, no "+" signs,
    single spaces, lower case ("+#% to Fire Resistance" and
    "#% to [Resistances|Fire Resistance]" -> "#% to fire resistance");
    None for a non-string or an over-long text."""
    if not isinstance(text, str) or len(text) > MAX_TEXT:
        return None
    text = _MARKUP_RE.sub(r"\1", text)
    out = _SPACE_RE.sub(" ", text.replace("+", "")).strip().lower()
    return out or None


def build_index(doc):
    """{norm text: explicit trade id} from a parsed stat_translations list.
    Only `trade_stats` rows of type "explicit" with an id of the form
    explicit.stat_<digits> count; a text with several ids keeps the lowest
    (string order) so the result is deterministic. Malformed rows are
    skipped; anything that is not a list gives {}."""
    out = {}
    if not isinstance(doc, list):
        return out
    for entry in doc:
        rows = entry.get("trade_stats") if isinstance(entry, dict) else None
        for row in rows if isinstance(rows, list) else ():
            if not isinstance(row, dict) or row.get("type") != KIND:
                continue
            tid, key = row.get("id"), norm(row.get("text"))
            if not (isinstance(tid, str) and _ID_RE.match(tid)) or key is None:
                continue
            if key not in out or tid < out[key]:
                out[key] = tid
    return out


def load_index(path):
    """build_index of a cached file; {} when missing, oversized or malformed."""
    try:
        p = Path(path)
        if p.stat().st_size > MAX_BYTES:
            return {}
        return build_index(json.loads(p.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return {}


def lookup(index, key):
    """The trade id for a weights key, or None (no guess)."""
    k = norm(key)
    if k is None or not isinstance(index, dict):
        return None
    tid = index.get(k)
    return tid if isinstance(tid, str) and _ID_RE.match(tid) else None


def coverage(index, keys):
    """{"mapped": {key: id}, "unmapped": [key]} for weights keys against an
    index, in the keys' order; a diagnostic, it never guesses."""
    mapped, unmapped = {}, []
    for key in keys if isinstance(keys, (list, tuple, dict)) else ():
        tid = lookup(index, key)
        if tid is None:
            unmapped.append(key)
        else:
            mapped[key] = tid
    return {"mapped": mapped, "unmapped": unmapped}


def default_path(environ=None):
    return datacredit.cache_dir(environ) / FILE_NAME


class IndexCache:
    """Loads the index once and again only when the file changes."""

    def __init__(self, path):
        self.path = Path(path)
        self._sig = None
        self._index = {}
        self._lock = threading.Lock()

    def get(self):
        try:
            st = os.stat(self.path)
            sig = (st.st_mtime_ns, st.st_size)
        except OSError:
            with self._lock:
                self._sig, self._index = None, {}
            return {}
        with self._lock:
            if sig != self._sig:
                self._index = load_index(self.path)
                self._sig = sig
            return self._index
