"""AUTO-10 (NINJA-WATCH, the flag bridge of W7 in docs/plan/06; F-085,
F-140 layer 1; research 0036): the poe.ninja response-shape flag.

A local source: no request, no host, every tick. It reads the flag file
ops/runtime/ninja/SHAPE_DRIFT that the dev host's own core writes when a
poe.ninja 200 body misses read keys of the tracked baseline (package
PRICE shape watch, units F-085 and F-140): JSON
    {"family": "leagues" | "exchange" | "item", "type": "<overview type>",
     "missing": ["<key name>", ...], "first_seen": "<ISO date or time>"}
or a list of such records. An absent flag is "nothing to do". The flag is
under the tree's root (ctx["root"], else this checkout only when
ctx["live"] is true; with neither the source reads nothing).

Finding (template ops/loop/watch_rows/ninja.json): kind "ninjashape"
(NINJA-SHAPE-<YYYYMMDD>, data) with tokens family (league, exchange or
item; "leagues" and "items" map to the singular), n (the missing key
names of that family, distinct, capped at 99) and since (the earliest
first_seen date of that family). One finding per run at most: the family
with the most missing names (league, exchange, item on a tie), keyed
"shape <family> <since>", so the frame's seen list files it once; at most
one finding per local day (data["day"]), because every NINJA-SHAPE row of
one day shares one id. A record that breaks the contract is skipped; a
flag that is not JSON, or holds no usable record, is a shape error.

Python stdlib only; no subprocess, no runtime file outside the root.
"""

import datetime as _dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

NAME = "ninja-shape"
KIND_SHAPE = "ninjashape"
FLAG_REL = Path("ops") / "runtime" / "ninja" / "SHAPE_DRIFT"
FLAG_MAX = 64 * 1024
FAMILIES = {"league": "league", "leagues": "league", "exchange": "exchange",
            "item": "item", "items": "item"}
ORDER = ("league", "exchange", "item")
N_MAX = 99
KEY_RX = re.compile(r"[A-Za-z0-9_.]{1,64}")
DATE_RX = re.compile(r"([0-9]{4}-[0-9]{2}-[0-9]{2})")


def _uw():
    import upstream_watch  # the frame; on sys.path whenever a source runs
    return upstream_watch


def _root(ctx):
    if ctx.get("root") is not None:
        return Path(ctx["root"])
    return ROOT if ctx.get("live") else None


def _date(value):
    """The YYYY-MM-DD of an ISO text or an epoch number, else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return _dt.datetime.fromtimestamp(value).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str) and value.isascii():
        m = DATE_RX.match(value.strip())
        if m:
            try:
                return _dt.date.fromisoformat(m.group(1)).isoformat()
            except ValueError:
                return None
    return None


def record_of(raw):
    """(family, missing names, since) of one flag record, or None."""
    if not isinstance(raw, dict):
        return None
    family = FAMILIES.get(str(raw.get("family") or "").lower())
    missing = raw.get("missing")
    since = _date(raw.get("first_seen"))
    if family is None or since is None or not isinstance(missing, list):
        return None
    names = {m for m in missing if isinstance(m, str) and KEY_RX.fullmatch(m)}
    if not names:
        return None
    return family, names, since


def read_flag(root):
    """The usable records of the flag file ([] when it is absent)."""
    path = Path(root) / FLAG_REL
    if not path.is_file():
        return []
    try:
        raw = path.read_bytes()[:FLAG_MAX + 1]
        if len(raw) > FLAG_MAX:
            raise ValueError("flag file too large")
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        raise _uw().SourceError("shape", "SHAPE_DRIFT is not readable JSON") from None
    items = doc if isinstance(doc, list) else [doc]
    recs = [r for r in (record_of(i) for i in items) if r is not None]
    if not recs:
        raise _uw().SourceError("shape", "SHAPE_DRIFT holds no usable record")
    return recs


def finding_of(recs):
    """At most one ninjashape finding from the flag records."""
    fams = {}
    for family, names, since in recs:
        cur = fams.setdefault(family, [set(), since])
        cur[0] |= names
        cur[1] = min(cur[1], since)
    if not fams:
        return []
    family = max(fams, key=lambda f: (len(fams[f][0]), -ORDER.index(f)))
    names, since = fams[family]
    return [{"kind": KIND_SHAPE, "key": f"shape {family} {since}",
             "tokens": {"family": family, "n": str(min(len(names), N_MAX)),
                        "since": since}}]


def check(state, now, fetch, ctx):
    ctx = ctx if isinstance(ctx, dict) else {}
    root = _root(ctx)
    if root is None:
        return []
    recs = read_flag(root)
    if not recs:
        return []
    found = finding_of(recs)
    data = state.setdefault("data", {})
    if not isinstance(data, dict):
        data = state["data"] = {}
    today = _dt.datetime.fromtimestamp(now).date().isoformat()
    seen = state.get("seen") if isinstance(state.get("seen"), list) else []
    found = [f for f in found if f["key"] not in seen]
    if not found or data.get("day") == today:
        return []
    data["day"] = today
    return found


SOURCE = {
    "name": NAME,
    "home": "loop",
    "cadence_s": 0,  # every tick; a local read
    "window": None,
    "needs_web_data": False,  # local: no request
    "hosts": [],
    "urls": [],
    "check": check,
}
