"""UTIL-MAP-STATS: per-map stats by map area id (research 0064 G5).

Runs, deaths, median time and the last run of each map area id, from the
same map rows the map ladder counts (mapladder.ladder: this session's
runs.MapRuns rows, and with run history on the saved map_ladder.json
records of decision 0036). Every number comes from lines the core already
parses from the opted-in Client.txt; no new read, no new file, no request.
The saved store keeps mapladder's bounds (MAX_SAVED maps per character,
MAX_CHARACTERS characters) and Clear run history empties it, so the table
empties with it.

table(rows, title) is the view, published as the `by_map` part of each
ladder view; here(maps, area_id) picks the entry of the map the player is
in for the Play tab's map context card (server/al/playcards.py). Words:
server/al/text/mapstats.py. Pure, stdlib only.
"""

import re
import statistics

from . import num
from .text import mapstats as text

MAX_AREAS = 30  # table rows, the most recently opened map first
MAX_COUNT = 9999
MAX_NAME = 48


def clock_text(s):
    """Seconds as m:ss or h:mm:ss (runs.clock_text's form; kept here so
    this module needs no runs import, as runs imports mapladder)."""
    s = max(0, int(s))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def area_name(area_id):
    """The map's name from its area id: runs.map_name's rule with no scene
    (a saved record keeps none), MapSunTemple -> 'Sun Temple'.
    tests/test_map_stats.py checks the two agree."""
    rest = area_id[3:] if isinstance(area_id, str) else ""
    rest = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", rest.replace("_", " ")).strip()
    return (rest or "Map")[:MAX_NAME]


def _count(v):
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        return 0
    return min(v, MAX_COUNT)


def table(rows, title):
    """The per-map view of map rows ({"area_id", "opened_at", "time_s",
    "deaths", "done"}): one entry per area id, the most recently opened
    first, at most MAX_AREAS. A row with no area id is left out; the
    median counts finished runs only (an open map's time is not final)."""
    by = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        aid = r.get("area_id")
        if not isinstance(aid, str) or not aid:
            continue
        b = by.setdefault(aid, {"runs": 0, "deaths": 0, "times": [], "last_at": None})
        b["runs"] = min(b["runs"] + 1, MAX_COUNT)
        b["deaths"] = min(b["deaths"] + _count(r.get("deaths")), MAX_COUNT)
        t = num.finite(r.get("time_s"))
        if r.get("done") and t is not None and t >= 0:
            b["times"].append(t)
        at = num.finite(r.get("opened_at"))
        if at is not None and (b["last_at"] is None or at > b["last_at"]):
            b["last_at"] = at
    order = sorted(by, key=lambda a: (by[a]["last_at"] is not None,
                                      by[a]["last_at"] or 0.0, a), reverse=True)
    areas = []
    for aid in order[:MAX_AREAS]:
        b = by[aid]
        med = statistics.median(b["times"]) if b["times"] else None
        med_text = clock_text(med) if med is not None else ""
        name = area_name(aid)
        areas.append({"area_id": aid, "name": name, "runs": b["runs"],
                      "deaths": b["deaths"], "median_s": med,
                      "median_text": med_text, "last_at": b["last_at"],
                      "text": text.row_text(name, b["runs"], b["deaths"], med_text),
                      "here": text.here_text(b["runs"], b["deaths"], med_text)})
    return {"areas": areas,
            "text": text.head_text(len(by), title) if areas else "",
            "empty_text": "" if areas else text.EMPTY_TEXT}


def here(maps, area_id):
    """The entry of `area_id` from a snapshot `maps` part: from the
    all-sessions table while run history is on (it holds this session's
    rows too), else from this session's, or None."""
    if not isinstance(maps, dict) or not isinstance(area_id, str) or not area_id:
        return None
    for key in ("ladder_all", "ladder"):
        lad = maps.get(key)
        st = lad.get("by_map") if isinstance(lad, dict) else None
        if isinstance(st, dict):
            for a in st.get("areas") or ():
                if isinstance(a, dict) and a.get("area_id") == area_id:
                    return a
            return None
    return None
