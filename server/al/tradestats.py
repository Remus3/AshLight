"""TC-UPGRADE-STATS (decision 0037): trade stat ids for the upgrade link.

The ids come first from the `trade_stats` field of the repoe-fork
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

MATH-TRADESTAT-POB (decision 0037 amendment 2026-11-17): when the OPTIONAL
calc component (decision 0018) is installed, the hash-pinned PoB-PoE2
checkout's src/Data/TradeSiteStats.lua fills ONLY the keys repoe-fork has no
id for. Both relay the same Grinding Gear Games trade site data; AshLight
still calls no trade endpoint. The file is used only when the checkout's
extraction marker names the pinned archive sha256 AND the file's own sha256
equals the pin in config/tc_pins.json ("pob2_files"); it is read as bounded
text by `parse_pob_trade_stats` (never run as Lua), matched by the same
exact `norm`, and repoe-fork wins any conflict (logged).
"""

import hashlib
import json
import logging
import os
import re
import threading
from pathlib import Path

from . import paths
from .theorycraft import datacredit

LOG = logging.getLogger("al.tradestats")

FILE_NAME = "stat_translations.json"
MAX_BYTES = 64 * 1024 * 1024
MAX_TEXT = 200
KIND = "explicit"
# \Z, not $: "$" also matches before a trailing newline (AREA-AUDIT P6-2)
_ID_RE = re.compile(r"^explicit\.stat_[0-9]{1,10}\Z")
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


# --- PoB-PoE2 TradeSiteStats.lua fallback (decision 0037 amendment) -------

POB_REL = "src/Data/TradeSiteStats.lua"
POB_MAX_BYTES = 8 * 1024 * 1024
POB_MAX_LINES = 400000
POB_MARKER = ".al-extracted.json"  # tools/tc_pin.py MARKER
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
# one `["key"] = "value",` line; a value holding a quote or backslash (an
# escaped Lua string) does not match and is skipped, never decoded by guess
_POB_FIELD = re.compile(r'^\s*\["(id|text|type)"\]\s*=\s*"([^"\\]*)",?\s*$')
_POB_OPEN = re.compile(r"^\s*\{\s*$")
_POB_CLOSE = re.compile(r"^\s*\},?\s*$")


def parse_pob_trade_stats(text):
    """{norm text: explicit trade id} from the text of a PoB-PoE2
    TradeSiteStats.lua. A line scanner, not a Lua evaluator: it collects the
    `["id"]`, `["text"]`, `["type"]` lines of each innermost `{ ... }` and
    keeps rows of type "explicit" with an explicit.stat_<digits> id; a text
    with several ids keeps the lowest. More than POB_MAX_LINES lines, or a
    non-string, gives {}."""
    out = {}
    if not isinstance(text, str):
        return out
    lines = text.split("\n")
    if len(lines) > POB_MAX_LINES:
        return {}
    cur = {}
    for line in lines:
        if _POB_OPEN.match(line):
            cur = {}
            continue
        if _POB_CLOSE.match(line):
            tid, key = cur.get("id"), norm(cur.get("text"))
            if (cur.get("type") == KIND and isinstance(tid, str) and _ID_RE.match(tid)
                    and key is not None and (key not in out or tid < out[key])):
                out[key] = tid
            cur = {}
            continue
        m = _POB_FIELD.match(line)
        if m:
            cur[m.group(1)] = m.group(2)
    return out


def pob_source(environ=None, pins=None):
    """(path, pins) of the pinned checkout's TradeSiteStats.lua; (None, None)
    when the pin file is unreadable or its top_dir is not a plain name."""
    try:
        doc = pins if pins is not None else json.loads(
            paths.tc_pins_file(environ).read_text(encoding="ascii"))
        top = doc["pob2"]["top_dir"]
        if not isinstance(top, str) or not re.match(r"^[A-Za-z0-9._-]{1,120}$", top) \
                or ".." in top:
            return None, None
        root = paths.all_runtime_paths(environ)["pob2_cache"] / top
    except (OSError, ValueError, KeyError, TypeError):
        return None, None
    return root / POB_REL, doc


def load_pob_index(path, pins):
    """parse_pob_trade_stats of the pinned file, or {} unless every check
    holds: the checkout marker names the pinned archive sha256, the file is
    at most POB_MAX_BYTES and its sha256 equals
    pins["pob2_files"][POB_REL]["sha256"]. Never raises."""
    try:
        p = Path(path)
        want = pins["pob2_files"][POB_REL]["sha256"]
        archive = pins["pob2"]["archive_sha256"]
        if not (isinstance(want, str) and _HEX64.match(want)):
            return {}
        root = p.parents[len(Path(POB_REL).parts) - 1]
        marker = json.loads((root / POB_MARKER).read_text(encoding="ascii"))
        if not isinstance(marker, dict) or marker.get("archive_sha256") != archive:
            return {}
        if p.stat().st_size > POB_MAX_BYTES:
            return {}
        raw = p.read_bytes()
        if len(raw) > POB_MAX_BYTES or hashlib.sha256(raw).hexdigest() != want:
            return {}
        return parse_pob_trade_stats(raw.decode("utf-8"))
    except (OSError, ValueError, KeyError, TypeError, IndexError, UnicodeDecodeError):
        return {}


def merge(primary, fallback):
    """(index, conflicts): the fallback fills only keys the primary
    (repoe-fork) lacks; a key both hold with different ids keeps the
    primary id and is listed in conflicts."""
    out = dict(fallback) if isinstance(fallback, dict) else {}
    primary = primary if isinstance(primary, dict) else {}
    conflicts = sorted(k for k, v in primary.items() if k in out and out[k] != v)
    out.update(primary)
    return out, conflicts


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


def _stat_sig(path):
    if path is None:
        return None
    try:
        st = os.stat(path)
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


class IndexCache:
    """Loads the index once and again only when a source file changes.
    `pob` is an optional (path, pins) pair for the PoB fallback; without it,
    or with the component absent or unverified, the index is repoe-fork's
    alone."""

    def __init__(self, path, pob=None):
        self.path = Path(path)
        self.pob_path, self.pob_pins = pob if pob else (None, None)
        self._sig = None
        self._index = {}
        self.conflicts = []
        self._lock = threading.Lock()

    def get(self):
        sig = (_stat_sig(self.path), _stat_sig(self.pob_path))
        with self._lock:
            if sig != self._sig:
                primary = load_index(self.path) if sig[0] else {}
                fallback = (load_pob_index(self.pob_path, self.pob_pins)
                            if sig[1] and self.pob_pins else {})
                self._index, self.conflicts = merge(primary, fallback)
                if self.conflicts:
                    LOG.warning("trade stat ids: %d PoB ids differ from repoe-fork; "
                                "repoe-fork kept: %s", len(self.conflicts),
                                ", ".join(self.conflicts[:5]))
                self._sig = sig
            return self._index
