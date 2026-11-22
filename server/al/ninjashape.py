"""DATA-NINJA-SHAPE-WATCH (F-140 layers 1 and 3, research 0036 shape-watch
design, plan 06 W7): poe.ninja drift detection inside the core, with no
extra request.

Layer 1. Every HTTP 200 body the price refresh already fetched (the league
list in ninja._league_id, the Currency overview in ninja._refresh_rates,
each price book type in PriceBook.refresh) goes through record(). It builds
a signature: the key sets at top level, in `core` and across `lines`; for
each key the parser READS (the tracked baseline
server/al/data/ninja_read_keys.json, key names only, hot reloaded) the
share of elements carrying a usable value; counts of lines, kept and named
entries; the Cache-Control class and whether an ETag came; invariants (the
league list is a non-empty list of unique string ids; core.primary is a
string and its own exchange line is worth 1; values finite and positive;
listingCount an integer). Then it compares:

- BREAK: a hard read key on under half the elements, a list that is not a
  list, lines present but nothing kept, under half kept of SHAPE_MIN_LINES
  or more lines, or a league list that breaks its invariant. A break writes
  the flag <runtime>/ninja/SHAPE_DRIFT as JSON {family, type, missing,
  first_seen} (the W7 contract; AUTO-10's loop tick turns it into a row)
  plus "reason". One flag per core: the first break is kept (its
  first_seen survives a restart) until every broken type passes again,
  then the flag is removed.
- CHANGE (information only): new unknown keys since the last body of the
  type, a soft read key under half, another Cache-Control class, an ETag
  that vanished, or a value invariant that failed.
- PASS otherwise.

Layer 3, the league: diag_rows shows "League changed to X" as a note for
LEAGUE_NOTE_S (7 days) after the priced league changed (ninja.py's
league_changed_at), and a failing row while the cached league list is not
a non-empty list of unique string ids. No hourly league re-read (not
adopted: ninja.py keeps its 6 h gate and its rollover hint).

Nothing here makes a request, shows a toast or writes a chat line (as
decision 0044). It stores no price, no item name and no raw body: the
signature keeps key names (bounded and filtered to plain identifiers),
shares and counts, in memory only; the flag holds key names and a time.
record() never raises into the refresh path: observe() swallows and logs.

DATA-PRICE-TYPE-PROOF (F-201): the Currency body is also checked for the
exchange ids the note-price aliases point at (theorycraft.value.alias_ids,
the one list). An id with no priced line is an invariant that failed
("alias_ids", a CHANGE, never a break: the parser still reads) and the
reason names the missing ids, which come from AshLight's own table, never
from the body. An empty Currency body (league start) is not checked.

attach(core) gives core.rates (and its book) the watch; diag_facts /
diag_rows are the DATA-DIAG-SEAM hooks (diag_data.MODULES).
"""

import json
import logging
import math
import re
import threading
import time
from pathlib import Path

from . import hotreload, jsonfile, plug
from .theorycraft import value

log = logging.getLogger("al.ninjashape")

BASELINE_PATH = Path(__file__).resolve().parent / "data" / "ninja_read_keys.json"
FLAG_DIR = "ninja"
FLAG_NAME = "SHAPE_DRIFT"
FAMILIES = ("leagues", "exchange", "item")
PASS, CHANGE, BREAK = "pass", "change", "break"
SHAPE_MIN_LINES = 5   # = pricebook.SHAPE_MIN_LINES: below this a low keep share is no signal
MAX_ELEMENTS = 5000   # = pricebook.MAX_LINES: elements looked at per list
MAX_KEYS = 100        # key names kept per key set
LEAGUE_NOTE_S = 7 * 24 * 3600
FACT = "ninja_shape"
LEAGUE_FACT = "ninja_league"
ALIAS_TYPE = "Currency"  # = ninja.OVERVIEW_TYPE: the body the aliases price from
_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,39}$")
_PATH_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,39}(\.[A-Za-z][A-Za-z0-9_]{0,39}){0,3}$")
_STRING_KEYS = frozenset(("id", "name", "baseType", "primary", "itemId"))
_BOOL_KEYS = frozenset(("corrupted",))
_NUMBER_ENDS = ("Value", "Change", "Count")
_throttle = plug.ErrorThrottle(log)


def _utc(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


# --- the baseline ------------------------------------------------------------

def load_baseline(path):
    """{family: {"read": [paths], "soft": set(paths)}} from the baseline
    file; raises ValueError on a bad shape (hot reload keeps the last good
    copy). Only key paths are allowed: a value that is not a plain dotted
    key name is refused, so the file can hold no price and no item name."""
    doc = json.loads(Path(path).read_text(encoding="ascii"))
    fams = doc.get("families") if isinstance(doc, dict) else None
    if not isinstance(fams, dict):
        raise ValueError("no families")
    out = {}
    for fam, spec in fams.items():
        if fam not in FAMILIES or not isinstance(spec, dict):
            raise ValueError(f"unknown family {str(fam)[:20]}")
        read, soft = spec.get("read"), spec.get("soft", [])
        if not isinstance(read, list) or not isinstance(soft, list):
            raise ValueError(f"{fam}: read and soft must be lists")
        for key in read + soft:
            if not isinstance(key, str) or not _PATH_RE.match(key):
                raise ValueError(f"{fam}: not a key path")
        if not set(soft) <= set(read):
            raise ValueError(f"{fam}: a soft key is not a read key")
        out[fam] = {"read": list(dict.fromkeys(read)), "soft": set(soft)}
    return out


_baseline_watch = None
_baseline_lock = threading.Lock()


def baseline():
    """The tracked baseline, hot reloaded (decision 0042): one stat per
    call, a re-read only when the file moved; a bad edit keeps the last good
    copy and shows a reload note; a missing file reads as no keys."""
    global _baseline_watch
    with _baseline_lock:
        if _baseline_watch is None:
            _baseline_watch = hotreload.register(BASELINE_PATH, load_baseline,
                                                 name="poe.ninja read keys", default=dict)
        w = _baseline_watch
    return w.get()


# --- the signature -----------------------------------------------------------

def _usable(key, value):
    if key in _STRING_KEYS:
        return isinstance(value, str) and bool(value.strip())
    if key in _BOOL_KEYS:
        return isinstance(value, bool)
    if key.endswith(_NUMBER_ENDS):
        return (isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value))
    return value is not None


def _carries(node, parts):
    """True when `node` holds a usable value at the dotted path `parts`; a
    list met on the way counts when any of its dict elements carries the
    rest of the path."""
    for i, part in enumerate(parts):
        if isinstance(node, list):
            rest = parts[i:]
            return any(_carries(e, rest) for e in node[:MAX_ELEMENTS] if isinstance(e, dict))
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return _usable(parts[-1], node)


def _list_share(elems, parts):
    elems = [e for e in elems[:MAX_ELEMENTS] if isinstance(e, dict)]
    if not elems:
        return None
    return sum(1 for e in elems if _carries(e, parts)) / len(elems)


def share(doc, path):
    """The share (0.0 to 1.0) of elements carrying a usable value at
    `path`: the first list on the path (or `doc` itself when it is a list)
    is checked element by element; None when that list is empty (no
    signal). A path through no list reads 1.0 or 0.0; a list ends a path
    only as a value."""
    parts = path.split(".")
    node = doc
    for i, part in enumerate(parts):
        if isinstance(node, list):
            return _list_share(node, parts[i:])
        if not isinstance(node, dict) or part not in node:
            return 0.0
        node = node[part]
    return 1.0 if _usable(parts[-1], node) else 0.0


def _keys(obj):
    """(sorted plain key names, count of other keys) of a dict, bounded."""
    if not isinstance(obj, dict):
        return [], 0
    good = sorted(k for k in obj if isinstance(k, str) and _KEY_RE.match(k))
    return good[:MAX_KEYS], len(obj) - min(len(good), MAX_KEYS)


def _line_keys(lines):
    seen = set()
    other = 0
    for line in lines[:MAX_ELEMENTS] if isinstance(lines, list) else ():
        if isinstance(line, dict):
            good, bad = _keys(line)
            seen.update(good)
            other += bad
    return sorted(seen)[:MAX_KEYS], other


def cache_class(headers):
    """The Cache-Control class of a response: no-store, no-cache, max-age,
    other or none."""
    value = None
    for k, v in (headers or {}).items():
        if isinstance(k, str) and k.lower() == "cache-control":
            value = v
    if not isinstance(value, str) or not value.strip():
        return "none"
    low = value.lower()
    for word in ("no-store", "no-cache", "max-age"):
        if word in low:
            return word
    return "other"


def _has_etag(headers):
    return any(isinstance(k, str) and k.lower() == "etag" and v
               for k, v in (headers or {}).items())


def _finite_pos(v):
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(v) and v > 0)


def _league_list(doc):
    if isinstance(doc, dict):
        doc = doc.get("leagues") or doc.get("result")
    return doc


def league_list_problem(listed):
    """Why a league list breaks its invariant (a non-empty list of unique
    string ids), or None. The words name no league."""
    if not isinstance(listed, list):
        return "not a list"
    if not listed:
        return "empty"
    ids = [e.get("id") if isinstance(e, dict) else None for e in listed]
    if any(not isinstance(i, str) or not i.strip() for i in ids):
        return "an entry has no text id"
    if len(set(ids)) != len(ids):
        return "an id appears twice"
    return None


def alias_missing(lines):
    """The alias ids (value.alias_ids) with no line carrying a usable
    primaryValue, sorted; [] for an empty or unreadable lines list."""
    if not isinstance(lines, list) or not lines:
        return []
    priced = {x.get("id") for x in lines[:MAX_ELEMENTS]
              if isinstance(x, dict) and _finite_pos(x.get("primaryValue"))}
    return [i for i in value.alias_ids() if i not in priced]


def signature(family, doc, headers=None, kept=None, named=None, type_name=None):
    """The signature of one parsed body (key names, shares, counts,
    invariants; no value, no name). For the Currency body (`type_name`
    ALIAS_TYPE) the alias ids with no priced line go in "alias_missing"."""
    spec = baseline().get(family) or {"read": [], "soft": set()}
    sig = {"family": family, "cache": cache_class(headers), "etag": _has_etag(headers),
           "kept": kept if isinstance(kept, int) else None,
           "named": named if isinstance(named, int) else None}
    inv = {}
    if family == "leagues":
        listed = _league_list(doc)
        sig["top"], sig["top_other"] = _keys(doc) if isinstance(doc, dict) else (["(list)"], 0)
        sig["core"], sig["core_other"] = [], 0
        sig["line_keys"], sig["line_other"] = _line_keys(listed)
        sig["lines"] = len(listed) if isinstance(listed, list) else None
        sig["lines_is_list"] = isinstance(listed, list)
        inv["league_list"] = league_list_problem(listed)
        shares = {k: (share(listed, k) if isinstance(listed, list) else 0.0)
                  for k in spec["read"]}
    else:
        top = doc if isinstance(doc, dict) else {}
        core = top.get("core") if isinstance(top.get("core"), dict) else None
        lines = top.get("lines")
        sig["top"], sig["top_other"] = _keys(top)
        sig["core"], sig["core_other"] = _keys(core)
        sig["line_keys"], sig["line_other"] = _line_keys(lines)
        sig["lines_is_list"] = isinstance(lines, list)
        sig["lines"] = (sum(1 for x in lines[:MAX_ELEMENTS] if isinstance(x, dict))
                        if isinstance(lines, list) else None)
        shares = {k: share(top, k) for k in spec["read"]}
        primary = core.get("primary") if core else None
        inv["primary_is_text"] = isinstance(primary, str) and bool(primary)
        values = [x.get("primaryValue") for x in lines[:MAX_ELEMENTS]
                  if isinstance(x, dict) and "primaryValue" in x] \
            if isinstance(lines, list) else []
        inv["values_positive"] = all(_finite_pos(v) for v in values)
        if family == "exchange" and inv["primary_is_text"] and isinstance(lines, list):
            own = [x.get("primaryValue") for x in lines[:MAX_ELEMENTS]
                   if isinstance(x, dict) and x.get("id") == primary]
            inv["primary_worth_1"] = (not own) or all(
                _finite_pos(v) and abs(v - 1) < 1e-9 for v in own)
        if family == "exchange" and type_name == ALIAS_TYPE                 and isinstance(lines, list) and lines:
            sig["alias_missing"] = alias_missing(lines)
            inv["alias_ids"] = not sig["alias_missing"]
        if family == "item" and isinstance(lines, list):
            counts = [x.get("listingCount") for x in lines[:MAX_ELEMENTS]
                      if isinstance(x, dict) and "listingCount" in x]
            inv["listing_count_int"] = all(isinstance(v, int) and not isinstance(v, bool)
                                           for v in counts)
    sig["shares"] = {k: (round(v, 4) if isinstance(v, float) else v)
                     for k, v in shares.items()}
    sig["invariants"] = inv
    return sig


def verdict(sig, previous=None):
    """(BREAK | CHANGE | PASS, missing key names, reason text) of a
    signature against the baseline and the type's previous signature."""
    family = sig["family"]
    spec = baseline().get(family) or {"read": [], "soft": set()}
    lines, kept = sig.get("lines"), sig.get("kept")
    low = [k for k in spec["read"]
           if isinstance(sig["shares"].get(k), float) and sig["shares"][k] < 0.5]
    hard = [k for k in low if k not in spec["soft"]]
    soft = [k for k in low if k in spec["soft"]]
    reasons = []
    if family == "leagues":
        problem = sig["invariants"].get("league_list")
        if problem is not None:
            reasons.append(f"league list {problem}")
    elif not sig.get("lines_is_list"):
        reasons.append("lines is not a list")
    if family != "leagues" and sig.get("lines_is_list") and not lines:
        hard = soft = []  # an empty type (league start) has nothing to read: no key alarm
    if hard:
        reasons.append(f"{len(hard)} read key{'s' if len(hard) != 1 else ''} under half")
    if family != "leagues" and isinstance(lines, int) and lines > 0:
        k = kept if isinstance(kept, int) else 0
        if k <= 0:
            reasons.append(f"{lines} lines but nothing kept")
        elif lines >= SHAPE_MIN_LINES and k * 2 < lines:
            reasons.append(f"kept {k} of {lines} lines")
    if reasons:
        missing = hard or (["id"] if family == "leagues" else ["lines"])
        return BREAK, missing, "; ".join(reasons)
    notes = []
    if soft:
        notes.append(f"soft keys under half: {', '.join(soft)}")
    if any(v is False for v in sig["invariants"].values()):
        notes.append("an invariant failed: " + ", ".join(
            k for k, v in sig["invariants"].items() if v is False))
    if sig.get("alias_missing"):
        notes.append("note currencies without a price: "
                     + ", ".join(sig["alias_missing"][:20]))
    if previous is not None:
        for part in ("top", "core", "line_keys"):
            new = set(sig.get(part) or ()) - set(previous.get(part) or ())
            if new:
                notes.append(f"new {part} keys: {', '.join(sorted(new)[:10])}")
        if previous.get("cache") != sig.get("cache"):
            notes.append(f"cache class {previous.get('cache')} -> {sig.get('cache')}")
        if previous.get("etag") and not sig.get("etag"):
            notes.append("ETag vanished")
    if notes:
        return CHANGE, soft, "; ".join(notes)
    return PASS, [], ""


# --- the watch ---------------------------------------------------------------

class Watch:
    """The core's shape watch: per-type signatures in memory, the flag file
    in `directory` (<runtime>/ninja)."""

    def __init__(self, directory, clock=time.time):
        self.directory = Path(directory)
        self.flag_path = self.directory / FLAG_NAME
        self.clock = clock
        self._lock = threading.Lock()
        self.signatures = {}  # (family, type) -> last signature that was no break
        self.results = {}     # (family, type) -> {"verdict", "missing", "reason", "at"}
        self.broken = {}      # (family, type) -> {"missing", "first_seen", "reason"}
        self.flag = self._read_flag()
        if self.flag is not None:
            # a flag from before a restart stays until its own type passes
            self.broken[(self.flag["family"], self.flag["type"])] = {
                "missing": list(self.flag["missing"]),
                "first_seen": self.flag.get("first_seen"),
                "reason": self.flag.get("reason") or ""}

    def _read_flag(self):
        doc = jsonfile.read_json(self.flag_path, max_bytes=64 * 1024, encoding="ascii",
                                 kind=dict)
        if not isinstance(doc, dict) or doc.get("family") not in FAMILIES:
            return None
        if not isinstance(doc.get("type"), str) or not isinstance(doc.get("missing"), list):
            return None
        return doc

    def record(self, family, type_name, status, headers, doc, kept=None, named=None):
        """Check one HTTP 200 body (`doc` the parsed JSON, or the raw body)
        and return BREAK, CHANGE or PASS. Other statuses are not looked at
        (PASS). Writes or removes the flag."""
        if status != 200 or family not in FAMILIES or not isinstance(type_name, str):
            return PASS
        if isinstance(doc, (bytes, bytearray, str)):
            try:
                doc = json.loads(doc)
            except ValueError:
                doc = None
        key = (family, type_name[:60])
        sig = signature(family, doc, headers, kept, named, type_name)
        now = self.clock()
        with self._lock:
            result, missing, reason = verdict(sig, self.signatures.get(key))
            if result != BREAK:  # changes compare with the last body that read
                self.signatures[key] = sig
            self.results[key] = {"verdict": result, "missing": missing,
                                 "reason": reason, "at": now}
            if result == BREAK:
                before = self.broken.get(key) or {}
                self.broken[key] = {"missing": list(missing), "reason": reason,
                                    "first_seen": before.get("first_seen") or _utc(now)}
                log.warning("poe.ninja %s %s shape break: %s", key[0], key[1], reason)
            else:
                self.broken.pop(key, None)
            self._sync_flag()
        return result

    def _flag_doc(self):
        """The flag for the earliest break still open (W7 contract)."""
        if not self.broken:
            return None
        fk = (self.flag["family"], self.flag["type"]) if self.flag else None
        if fk not in self.broken:
            fk = min(self.broken, key=lambda k: (str(self.broken[k]["first_seen"]), k))
        b = self.broken[fk]
        return {"family": fk[0], "type": fk[1], "missing": list(b["missing"]),
                "first_seen": b["first_seen"], "reason": b["reason"]}

    def _sync_flag(self):
        doc = self._flag_doc()
        if doc is None:
            try:
                self.flag_path.unlink()
            except FileNotFoundError:
                pass
            except OSError as e:
                log.warning("shape flag not removed: %s", e)
                return
            self.flag = None
            return
        if doc == self.flag:
            return  # unchanged: no write
        try:
            jsonfile.write_json(self.flag_path, doc, sort_keys=True)
            self.flag = doc
        except OSError as e:
            log.warning("shape flag not written: %s", e)

    def view(self):
        """The facts view: broken types with their missing key names, the
        flag's first_seen, the types that changed. No value, no name."""
        with self._lock:
            broken = [{"family": f, "type": t, "missing": list(b["missing"])}
                      for (f, t), b in sorted(self.broken.items())]
            changed = sorted(f"{f} {t}" for (f, t), r in self.results.items()
                             if r["verdict"] == CHANGE)
            first = self.flag.get("first_seen") if self.flag else None
        return {"broken": broken, "changed": changed, "first_seen": first}


def observe(watch, family, type_name, status, headers, doc, kept=None, named=None):
    """record() for the refresh paths: None without a watch; never raises
    (a failing watch is logged, throttled, and the refresh goes on)."""
    if watch is None:
        return None
    try:
        return watch.record(family, type_name, status, headers, doc, kept, named)
    except Exception as exc:  # noqa: BLE001 - the watch never breaks a refresh
        _throttle.failed("ninja shape watch", exc)
        return None


# --- DATA-DIAG-SEAM hooks ----------------------------------------------------

def attach(core):
    """Give core.rates (and its price book) the watch; the flag directory is
    core.runtime / FLAG_DIR. Nothing without rates."""
    rates = getattr(core, "rates", None)
    runtime = getattr(core, "runtime", None)
    if rates is None or runtime is None:
        return
    watch = Watch(Path(runtime) / FLAG_DIR, clock=getattr(rates, "clock", time.time))
    rates.shape_watch = watch
    book = getattr(rates, "book", None)
    if book is not None:
        book.shape_watch = watch
    core.ninja_shape = watch


def diag_facts(core):
    """{FACT: watch view, LEAGUE_FACT: {"league", "changed_at", "problem",
    "listed"}} from the core's rates; {} without them. Local reads only."""
    rates = getattr(core, "rates", None)
    if rates is None:
        return {}
    out = {}
    watch = getattr(rates, "shape_watch", None)
    if isinstance(watch, Watch):
        out[FACT] = watch.view()
    doc = getattr(rates, "doc", None)
    if isinstance(doc, dict):
        listed = "leagues" in doc
        changed = doc.get("league_changed_at")
        out[LEAGUE_FACT] = {
            "league": doc.get("league") if isinstance(doc.get("league"), str) else None,
            "changed_at": (changed if isinstance(changed, (int, float))
                           and not isinstance(changed, bool) else None),
            "listed": listed,
            "problem": league_list_problem(doc.get("leagues")) if listed else None}
    return out


SHAPE_FIX = ("Nothing to do: AshLight keeps the last good prices and asks again "
             "by itself. An AshLight update reads the new layout.")
LEAGUES_FIX = ("Nothing to do: AshLight keeps pricing the league it had and reads "
               "the list again by itself.")


def diag_rows(f, now):
    """Checks rows (web data on, contact set): a failing row while a type's
    body breaks the baseline; a failing row while the cached league list is
    not a non-empty list of unique string ids; a note 'League changed to X'
    for 7 days after the priced league changed."""
    if not isinstance(f, dict) or f.get("web_data") is not True or not f.get("contact_set"):
        return []
    from . import diag  # lazy: diag imports much of the core
    rows = []
    fact = f.get(FACT)
    broken = [b for b in (fact.get("broken") or ()) if isinstance(b, dict)] \
        if isinstance(fact, dict) else []
    if broken:
        first = broken[0]
        n = len(first.get("missing") or ())
        what = str(first.get("type") or "")[:40]
        if first.get("family") == "leagues":
            detail = "poe.ninja changed the layout of its league list."
        else:
            detail = f"poe.ninja changed the layout of its {what} prices."
        if n:
            detail += (f" AshLight no longer finds {n} field{'s' if n != 1 else ''} "
                       "it reads there.")
        others = len(broken) - 1
        if others:
            detail += (f" {others} other price type{'s' if others != 1 else ''} "
                       "changed too.")
        rows.append(diag._check("ninja_shape", "Price data layout", diag.FAIL,
                                detail, SHAPE_FIX))
    league = f.get(LEAGUE_FACT)
    if isinstance(league, dict):
        problem = league.get("problem")
        if league.get("listed") and isinstance(problem, str):
            rows.append(diag._check(
                "ninja_leagues", "League list", diag.FAIL,
                f"poe.ninja's league list is not usable ({problem}).", LEAGUES_FIX))
        at, name = league.get("changed_at"), league.get("league")
        if isinstance(at, (int, float)) and isinstance(name, str) and name \
                and isinstance(now, (int, float)) and 0 <= now - at < LEAGUE_NOTE_S:
            rows.append(diag._check("league_changed", "League", diag.NOTE,
                                    f"League changed to {name[:60]}."))
    return rows
