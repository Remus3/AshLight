"""TC-CAMPAIGN-KEEP (decision 0057): keep or vendor with no build loaded.

AshLight's own levelling rule table, `server/al/data/level_rules.json`:
level bands, each with thresholds for life, each resistance and boots
movement speed, plus a count-of-N rule ("need"). The conditions are plain
JSON data read by this module, never evaluated as code. The table is hot
reloaded (decision 0042): one stat per core tick; a malformed edit keeps
the last good table and shows a Checks note; a removed file reads as no
table (the item check then gives no keep part).

Inputs are the item text of the one item-check press (already parsed by
the caller) and the player level from the opted-in Client.txt tail. Nothing
here reads the clipboard, the screen or the game, or sends anything
anywhere.
"""

import json
import re
from pathlib import Path

from .. import hotreload

PATH = Path(__file__).resolve().parent.parent / "data" / "level_rules.json"
MAX_BYTES = 256 * 1024
SCHEMA = 1
MIN_LEVEL, MAX_LEVEL = 1, 100
MAX_BANDS = 32
MAX_CHECKS = 12
MAX_STATS = 12
LABEL_MAX = 16
TEXT_MAX = 200
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ID = re.compile(r"^[a-z][a-z0-9_]{0,23}$")


def _is_level(v):
    return isinstance(v, int) and not isinstance(v, bool) and MIN_LEVEL <= v <= MAX_LEVEL


def _is_num(v):
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and v == v and 0 < v < 1e6)


def _text(v, limit=TEXT_MAX):
    return isinstance(v, str) and v.strip() != "" and v.isascii() and len(v) <= limit


def _check(entry, where):
    if not isinstance(entry, dict):
        raise ValueError(f"{where} is not an object")
    if not (isinstance(entry.get("id"), str) and _ID.match(entry["id"])):
        raise ValueError(f"{where} has no valid id")
    if not _text(entry.get("label"), LABEL_MAX):
        raise ValueError(f"{where} has no short label")
    if not _is_num(entry.get("min")):
        raise ValueError(f"{where} has no positive min")
    stats = entry.get("stats")
    if not (isinstance(stats, list) and 0 < len(stats) <= MAX_STATS
            and all(_text(s) for s in stats)):
        raise ValueError(f"{where} has no stats list")
    if not _text(entry.get("src")):
        raise ValueError(f"{where} has no src")
    if not (isinstance(entry.get("checked"), str) and _DATE.match(entry["checked"])):
        raise ValueError(f"{where} has no checked date")
    if "must" in entry and not isinstance(entry["must"], bool):
        raise ValueError(f"{where} must is not true or false")
    slots = entry.get("slots")
    if slots is not None and not (isinstance(slots, list) and slots
                                  and all(_text(s, 32) for s in slots)):
        raise ValueError(f"{where} slots is not a list of slot names")
    return {"id": entry["id"], "label": entry["label"], "min": entry["min"],
            "stats": [" ".join(s.split()).lower() for s in stats],
            "must": entry.get("must") is True,
            "slots": list(slots) if slots is not None else None,
            "src": entry["src"], "checked": entry["checked"]}


def validate(doc):
    """The cleaned table, or ValueError naming the first problem. Bands
    must cover levels 1 to 100 in order, with no gap or overlap."""
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise ValueError(f"schema is not {SCHEMA}")
    slots = doc.get("slots")
    if not (isinstance(slots, list) and slots and all(_text(s, 32) for s in slots)):
        raise ValueError("slots is not a list of slot names")
    bands = doc.get("bands")
    if not (isinstance(bands, list) and 0 < len(bands) <= MAX_BANDS):
        raise ValueError("bands is not a list")
    out, expect = [], MIN_LEVEL
    for i, band in enumerate(bands, 1):
        where = f"band {i}"
        if not isinstance(band, dict):
            raise ValueError(f"{where} is not an object")
        lo, hi = band.get("min_level"), band.get("max_level")
        if not (_is_level(lo) and _is_level(hi) and lo <= hi):
            raise ValueError(f"{where} has no valid level range")
        if lo != expect:
            raise ValueError(f"{where} does not start at level {expect}")
        expect = hi + 1
        checks = band.get("checks")
        if not (isinstance(checks, list) and 0 < len(checks) <= MAX_CHECKS):
            raise ValueError(f"{where} has no checks")
        cleaned = [_check(c, f"{where} check {j}") for j, c in enumerate(checks, 1)]
        if len({c["id"] for c in cleaned}) != len(cleaned):
            raise ValueError(f"{where} repeats a check id")
        need = band.get("need")
        if not (isinstance(need, int) and not isinstance(need, bool)
                and 1 <= need <= len(cleaned)):
            raise ValueError(f"{where} need is not 1 to {len(cleaned)}")
        out.append({"min_level": lo, "max_level": hi, "need": need, "checks": cleaned})
    if expect != MAX_LEVEL + 1:
        raise ValueError(f"bands do not reach level {MAX_LEVEL}")
    return {"schema": SCHEMA, "slots": list(slots), "bands": out}


def load(path=PATH):
    """The validated table of `path`; raises on any problem (Watched then
    keeps the last good copy)."""
    p = Path(path)
    if p.stat().st_size > MAX_BYTES:
        raise ValueError(f"larger than {MAX_BYTES} bytes")
    return validate(json.loads(p.read_text(encoding="ascii")))


def watch(path=PATH, registry=None):
    """A hot-reloaded table for `path` (registry None: the core's)."""
    return hotreload.Watched(path, load, name="Levelling rules", default=dict,
                             registry=registry)


_watch = watch(PATH)


def table():
    """The current tracked table ({} when the file is missing)."""
    return _watch.get()


def band_for(doc, level):
    """The band holding `level`, or None."""
    if not _is_level(level) or not isinstance(doc, dict):
        return None
    for band in doc.get("bands") or ():
        if band["min_level"] <= level <= band["max_level"]:
            return band
    return None


def stat_totals(stats):
    """{lowercased stat key: summed value} from evaluate.stats_of()."""
    out = {}
    for key, value in (stats or {}).items():
        if not (isinstance(key, str) and isinstance(value, (int, float))
                and not isinstance(value, bool) and value == value and abs(value) < 1e6):
            continue
        k = " ".join(key.split()).lower()
        out[k] = out.get(k, 0) + value
    return out


def verdict(doc, level, slots, stats):
    """The keep / vendor answer for an item in `slots` with `stats`
    ({stat key: value}) at `level`, or None when the table does not cover
    it (no table, no level, no slot the table covers):
    {"status": "keep" | "vendor", "level", "need", "of", "count",
     "met": [{"id", "label", "min", "have"}], "missed_must": [...] }."""
    band = band_for(doc, level)
    if band is None:
        return None
    covered = [s for s in (slots or ()) if s in doc.get("slots", ())]
    if not covered:
        return None
    totals = stat_totals(stats)
    counted, met, missed_must = [], [], []
    for check in band["checks"]:
        if check["slots"] is not None and not any(s in check["slots"] for s in covered):
            continue
        counted.append(check)
        have = sum(totals.get(k, 0) for k in check["stats"])
        if isinstance(have, float) and have.is_integer():
            have = int(have)
        row = {"id": check["id"], "label": check["label"], "min": check["min"],
               "have": round(have, 1) if isinstance(have, float) else have}
        if have >= check["min"]:
            met.append(row)
        elif check["must"]:
            missed_must.append(row)
    if not counted:
        return None
    need = min(band["need"], len(counted))
    keep = len(met) >= need and not missed_must
    return {"status": "keep" if keep else "vendor", "level": level, "need": need,
            "of": len(counted), "count": len(met), "met": met,
            "missed_must": missed_must}
