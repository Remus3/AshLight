"""DATA-SNAP-PROBE (finding F-143): probe a fetched game-data file before
it replaces the cached copy.

theorycraft/snapshot.py calls `probe(name, doc)` on every fetched body
after its JSON check and before the write: the top-level type, a minimum
entry count and the fields AshLight's own readers use (acts.py,
zoneguide.py, campaign.py, basetypes.py, tradestats.py, treedata.py). A
failing body never replaces the cache; snapshot.py reports
'error: probe: ...' and keeps the old file and its manifest entry.

`stats(name, doc)` counts the entries and how many carry each field (and,
for stat_translations, how many of weights.DEFAULT_WEIGHTS keys map to a
trade id); `drift(old, new)` compares two such counts: a field the old
file had and the new one lost, and an entry or field count that moved by
more than DRIFT_SHARE. snapshot.py writes the drift lines to
<sidecar>/Logs/snapshot-drift.log and the per-source verdicts to
ops/runtime/snapshot/probe.json (`report`, schema 1: source, verdict,
missing-key count, time), the file AUTO-18 reads.

`diag_facts` / `diag_rows` are the DATA-DIAG-SEAM hooks (diag_data.py):
one failing Checks row per source whose last probe failed or lost a field
its reader uses, naming the source.

Pure: no request, no import of snapshot.py or of a network module; the
only file it reads is probe.json, for the Checks row. A source name not in
the table (a test's own table, for example) is not probed (probe -> None).
"""

import os
import re
import threading
import time
from pathlib import Path

from .. import jsonfile

SCHEMA = 1
DRIFT_SHARE = 0.20      # a count change over 20 percent is reported
MAX_FIELDS = 64         # field counts kept per source (most common first)
MAX_REASON = 160
REPORT_MAX_BYTES = 256 * 1024
REPORT_DIR = "snapshot"     # under the runtime dir (ops/runtime/snapshot/)
REPORT_NAME = "probe.json"
LOG_NAME = "snapshot-drift.log"
PASS, FAIL = "pass", "fail"
VERDICTS = (PASS, FAIL)

# source name -> probe spec. kind: the top-level JSON type ("object" or
# "list"); container: an object field that holds the entries (else the
# top level does); min: the fewest entries a real file has (about a
# quarter of the 2026-11-21 cache, so a normal release never trips it);
# fields: what the reader takes from an entry (each must be carried by at
# least one entry); weights: count the DEFAULT_WEIGHTS keys it maps;
# names: the fewest entries that yield a gem name the way
# archetypes.gem_index reads one (top level, base_item or active_skill
# display_name), so a reshaped gems file is caught whatever key holds it.
PROBES = {
    # basetypes.load_names (name, release_state), campaign.load_flasks
    # (item_class, name, drop_level, release_state)
    "base_items": {"kind": "object", "min": 1000,
                   "fields": ("name", "item_class", "drop_level", "release_state")},
    # no reader yet: type and size only
    "mods": {"kind": "object", "min": 4000, "fields": ()},
    "stats": {"kind": "object", "min": 5000, "fields": ()},
    # tradestats.build_index (trade_stats rows)
    "stat_translations": {"kind": "list", "min": 2000, "fields": ("trade_stats",),
                          "weights": True},
    # treedata.parse: the nodes object, each node's name and stats
    "skilltree": {"kind": "object", "container": "nodes", "min": 500,
                  "fields": ("name", "stats")},
    # acts.load_table (name, area_level, is_town), zoneguide.load_graph
    # (has_waypoint, connections)
    "world_areas": {"kind": "object", "min": 100,
                    "fields": ("name", "area_level", "is_town", "has_waypoint",
                               "connections")},
    # DATA-GEMS-SNAP: archetypes.gem_index (display_name, level); the name
    # may sit at the top or under base_item / active_skill, so the probe
    # counts readable names instead of naming one field
    "gems": {"kind": "object", "min": 150, "fields": (), "names": 100},
}

# the Checks row's words for a source
SOURCE_WORDS = {
    "base_items": "item base list",
    "mods": "mod list",
    "stats": "stat list",
    "stat_translations": "stat text list",
    "skilltree": "passive tree",
    "world_areas": "zone list",
    "gems": "skill gem list",
}

_SAFE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_ .-]{0,63}\Z")


def _utc(ts=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _kind(doc):
    if isinstance(doc, dict):
        return "object"
    if isinstance(doc, list):
        return "list"
    return "other"


def _entries(spec, doc):
    """(entries list, None) or (None, reason) for one spec."""
    if spec.get("kind") not in ("object", "list"):
        return None, "top level is not a JSON object or list"
    if _kind(doc) != spec["kind"]:
        return None, f"top level is not a JSON {spec['kind']}"
    box = spec.get("container")
    if box:
        doc = doc.get(box)
        if not isinstance(doc, dict):
            return None, f"no '{box}' object"
    return list(doc.values() if isinstance(doc, dict) else doc), None


def _field_counts(entries):
    """{field: entries carrying it}, safe field names only, at most
    MAX_FIELDS (most common first, then by name), sorted by name."""
    counts = {}
    for e in entries or ():
        if isinstance(e, dict):
            for k in e:
                if isinstance(k, str) and _SAFE.match(k):
                    counts[k] = counts.get(k, 0) + 1
    keep = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:MAX_FIELDS]
    return dict(sorted(keep))


def weight_coverage(doc):
    """{"keys": N, "mapped": M}: how many weights.DEFAULT_WEIGHTS keys get
    a trade id from a stat_translations document (tradestats' own exact
    match, never a guess)."""
    from .. import tradestats  # lazy: only the stat_translations probe needs it
    from . import weights
    keys = list(weights.DEFAULT_WEIGHTS)
    cover = tradestats.coverage(tradestats.build_index(doc), keys)
    return {"keys": len(keys), "mapped": len(cover["mapped"])}


def gem_names(doc):
    """How many distinct gem names a gems document yields, read by
    archetypes.gem_index itself (the reader's own rule, never a copy)."""
    from . import archetypes  # lazy: only the gems probe needs it
    return len(archetypes.gem_index(doc))


def probe(name, doc, table=None):
    """The verdict for one fetched document, or None when `name` is not in
    the probe table. {"source", "verdict" (pass / fail), "reason",
    "missing" (the reader fields no entry carries), "count"} plus
    "weights" for a source that counts weight coverage."""
    table = PROBES if table is None else table
    spec = table.get(name)
    if not isinstance(spec, dict):
        return None
    fields = tuple(spec.get("fields") or ())
    entries, why = _entries(spec, doc)
    out = {"source": name, "verdict": PASS, "reason": "", "missing": [], "count": 0}
    if why:
        out.update(verdict=FAIL, reason=why, missing=list(fields))
        return out
    counts = _field_counts(entries)
    out["count"] = len(entries)
    out["missing"] = [f for f in fields if not counts.get(f)]
    if spec.get("weights"):
        out["weights"] = weight_coverage(doc)
    named = int(spec.get("names") or 0)
    if named:
        out["names"] = gem_names(doc)
    least = int(spec.get("min") or 0)
    if len(entries) < least:
        out.update(verdict=FAIL, reason=f"only {len(entries)} entries, at least {least} expected")
    elif named and out["names"] < named:
        out.update(verdict=FAIL,
                   reason=f"only {out['names']} gem names, at least {named} expected")
    elif out["missing"]:
        out.update(verdict=FAIL, reason="no entry has " + ", ".join(out["missing"]))
    return out


def stats(name, doc, table=None):
    """{"kind", "count", "fields": {field: entries carrying it}} for one
    document (plus "weights" where the spec counts it); a source not in the
    table counts its top level."""
    table = PROBES if table is None else table
    spec = table.get(name) if isinstance(table.get(name), dict) else {"kind": _kind(doc)}
    entries, why = _entries(spec, doc)
    out = {"kind": _kind(doc), "count": 0 if why else len(entries),
           "fields": {} if why else _field_counts(entries)}
    if spec.get("weights") and not why:
        out["weights"] = weight_coverage(doc)
    return out


def _moved(old, new):
    """True when the count moved by more than DRIFT_SHARE of the old one."""
    if not isinstance(old, int) or not isinstance(new, int):
        return False
    if old <= 0:
        return new > 0
    return abs(new - old) > DRIFT_SHARE * old


def drift(old, new):
    """What changed from stats `old` to stats `new`: {"lost": [fields the
    old file had and the new one has not], "count": [old, new] or None
    (moved over DRIFT_SHARE), "fields": [[field, old, new], ...] (moved over
    DRIFT_SHARE), "weights": [old mapped, new mapped] or None (any change),
    "changed": bool}. No old stats (a first fetch) means no drift."""
    out = {"lost": [], "count": None, "fields": [], "weights": None, "changed": False}
    if not isinstance(old, dict) or not isinstance(new, dict):
        return out
    of = old.get("fields") if isinstance(old.get("fields"), dict) else {}
    nf = new.get("fields") if isinstance(new.get("fields"), dict) else {}
    out["lost"] = sorted(k for k, n in of.items() if n and not nf.get(k))
    if _moved(old.get("count"), new.get("count")):
        out["count"] = [old.get("count"), new.get("count")]
    out["fields"] = [[k, of[k], nf[k]] for k in sorted(of)
                     if of[k] and nf.get(k) and _moved(of[k], nf[k])]
    ow, nw = old.get("weights"), new.get("weights")
    if isinstance(ow, dict) and isinstance(nw, dict) and ow.get("mapped") != nw.get("mapped"):
        out["weights"] = [ow.get("mapped"), nw.get("mapped")]
    out["changed"] = bool(out["lost"] or out["count"] or out["fields"] or out["weights"])
    return out


def drift_line(name, result, d, now=None):
    """One ASCII log line for a probed source: its verdict, entry count
    and what drifted against the previous file."""
    parts = [_utc(now), name, (result or {}).get("verdict", "?"),
             f"entries {(result or {}).get('count', 0)}"]
    reason = (result or {}).get("reason")
    if reason:
        parts.append(f"reason: {reason}")
    d = d or {}
    if d.get("count"):
        parts.append(f"count {d['count'][0]} -> {d['count'][1]}")
    if d.get("lost"):
        parts.append("lost: " + ", ".join(d["lost"]))
    if d.get("fields"):
        parts.append("moved: " + ", ".join(f"{k} {o} -> {n}" for k, o, n in d["fields"]))
    if d.get("weights"):
        parts.append(f"weight keys mapped {d['weights'][0]} -> {d['weights'][1]}")
    line = " | ".join(str(p) for p in parts)
    return line.encode("ascii", "replace").decode("ascii")


def record(result, d, now=None, table=None):
    """The probe.json entry for one probed source: source, verdict,
    missing (the missing-key count), missing_keys, lost (reader fields
    lost against the previous file), count, reason, time."""
    table = PROBES if table is None else table
    name = result["source"]
    spec = table.get(name) if isinstance(table.get(name), dict) else {}
    readers = set(spec.get("fields") or ())
    lost = [k for k in (d or {}).get("lost") or () if k in readers]
    out = {"source": name, "verdict": result["verdict"],
           "missing": len(result.get("missing") or ()),
           "missing_keys": list(result.get("missing") or ()), "lost": lost,
           "count": result.get("count", 0),
           "reason": str(result.get("reason") or "")[:MAX_REASON], "time": _utc(now)}
    if isinstance(result.get("weights"), dict):
        out["weights"] = dict(result["weights"])
    return out


def report(previous, records, now=None):
    """The probe.json document: the previous document's entries with each
    source in `records` replaced, sorted by source."""
    keep = {}
    if isinstance(previous, dict) and isinstance(previous.get("sources"), list):
        for e in previous["sources"]:
            if isinstance(e, dict) and isinstance(e.get("source"), str):
                keep[e["source"]] = e
    for r in records or ():
        keep[r["source"]] = r
    return {"schema": SCHEMA, "updated": _utc(now),
            "sources": [keep[k] for k in sorted(keep)]}


def report_path(runtime):
    return Path(runtime) / REPORT_DIR / REPORT_NAME


# --- DATA-DIAG-SEAM hooks -------------------------------------------------

FACT = "snap_probe"
ROW_PREFIX = "snap_probe_"
LABEL = "Game data"
FIX = ("Nothing to do: AshLight keeps using the copy it had and checks again "
       "at the next game data refresh.")

_cache_lock = threading.Lock()
_cache = {}  # path text -> ((mtime_ns, size), entries)


def _clean(e):
    if not isinstance(e, dict):
        return None
    src, verdict, missing = e.get("source"), e.get("verdict"), e.get("missing")
    if not (isinstance(src, str) and _SAFE.match(src) and verdict in VERDICTS
            and isinstance(missing, int) and not isinstance(missing, bool) and missing >= 0):
        return None
    lost = [k for k in e.get("lost") or () if isinstance(k, str) and _SAFE.match(k)] \
        if isinstance(e.get("lost"), list) else []
    reason = e.get("reason") if isinstance(e.get("reason"), str) else ""
    reason = reason[:MAX_REASON].encode("ascii", "replace").decode("ascii")
    return {"source": src, "verdict": verdict, "missing": missing, "lost": lost,
            "reason": reason, "time": e.get("time") if isinstance(e.get("time"), str) else None}


def read_report(path):
    """The cleaned entries of a probe.json ([] when missing or malformed);
    re-read only when its size or mtime changes."""
    key = str(path)
    try:
        st = os.stat(path)
        sig = (st.st_mtime_ns, st.st_size)
    except OSError:
        return []
    with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] == sig:
            return list(hit[1])
    doc = jsonfile.read_json(path, max_bytes=REPORT_MAX_BYTES, kind=dict, default={})
    rows = doc.get("sources") if isinstance(doc.get("sources"), list) else []
    entries = [c for c in (_clean(e) for e in rows) if c is not None]
    with _cache_lock:
        _cache[key] = (sig, entries)
    return list(entries)


def diag_facts(core):
    """{FACT: [probe.json entries]} from the core's runtime dir; {} when
    there is no report."""
    runtime = getattr(core, "runtime", None)
    if runtime is None:
        return {}
    entries = read_report(report_path(runtime))
    return {FACT: entries} if entries else {}


def _detail(e):
    what = SOURCE_WORDS.get(e["source"], e["source"])
    if e["verdict"] == FAIL:
        text = f"The newest {what} download ({e['source']}) didn't look right"
        if e["reason"]:
            text += f": {e['reason']}"
        return text + ". AshLight kept the copy it had."
    return (f"The newest {what} download ({e['source']}) dropped data AshLight reads: "
            + ", ".join(e["lost"]) + ".")


def diag_rows(f, now):
    """One failing Checks row per source whose last probe failed or lost a
    field its reader uses; [] otherwise."""
    entries = f.get(FACT) if isinstance(f, dict) else None
    if not isinstance(entries, list):
        return []
    from .. import diag  # lazy: diag imports much of the core
    out = []
    for e in entries:
        e = _clean(e)
        if e is None or (e["verdict"] == PASS and not e["lost"]):
            continue
        out.append(diag._check(ROW_PREFIX + e["source"], LABEL, diag.FAIL, _detail(e), FIX))
    return out
