"""UTIL-MAP-LADDER: maps, deaths, median map time and level-ups earned in
maps per map area level (research 0032 sections 2 and 5.4; research 0031
ruling I).

Every number comes from lines the core already parses from the opted-in
Client.txt: the area level of a map's "Generating level N area <id>" line
(UTIL-MAPS, runs.py), the deaths and level-ups the player had while inside
it, and its time in the map. Stated facts only: no advice to push higher
or step down.

This session: ladder() over the session's map runs (runs.MapRuns rows,
bounded by runs.MAX_MAPS; LIVE-RESUME rebuilds them, so a restart keeps
them). Across sessions, only with run history on (decision 0036): each
finished map is saved to one bounded JSON file in the runtime dir
(ops/runtime, gitignored) per character, as the run history keys them
(decision 0038). A map rebuilt after a restart matches its saved record by
area id, seed and open time (MATCH_S), so it is never counted twice. The
run-history switch turns saving off and its clear button empties the file.

RUN-LADDER-TICK (AUDIT-P8-LOW P8-5): the saved maps of a character are
indexed by (area id, seed), so a match looks only at the records of that
instance, and the all-sessions view is cached and rebuilt only when the
saved list (rev) or the session rows that shape it changed. An open map's
running time does not shape the view (only finished maps count to the
median), so a tick inside a map rebuilds nothing.
"""

from pathlib import Path

from . import jsonfile, num, runhistory

FILE_NAME = "map_ladder.json"
SCHEMA = 1
MAX_SAVED = 500  # finished maps per character
MAX_CHARACTERS = 12
MAX_ID = 64
MAX_BYTES = 2 * 1024 * 1024
MATCH_S = 120.0
MAX_ROWS = 10  # area levels shown, highest first
MAX_COUNT = 9999

TITLE_SESSION = "This session"
TITLE_ALL = "All saved sessions"
EMPTY_TEXT = "No map levels yet. They show here by themselves as you play maps."
MEDIAN_NOTE = "Median time counts finished maps."


def _clock(s):
    s = int(max(0, s))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def _int(v):
    if isinstance(v, bool) or not isinstance(v, int):
        return None
    return v


def _count(v):
    v = _int(v)
    return min(v, MAX_COUNT) if v is not None and v >= 0 else 0


def median(values):
    vals = sorted(values)
    if not vals:
        return None
    mid = len(vals) // 2
    if len(vals) % 2:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / 2.0


def _plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def ladder(rows, title=TITLE_SESSION):
    """The ladder view of map rows ({"area_level", "time_s", "deaths",
    "level_ups", "done"}). A row with no area level is left out; the
    median time counts finished maps only (an open map's time is not
    final). Highest area level first, at most MAX_ROWS levels."""
    by = {}
    for r in rows:
        lvl = _int(r.get("area_level"))
        if lvl is None or lvl < 0:
            continue
        b = by.setdefault(lvl, {"maps": 0, "deaths": 0, "level_ups": 0, "times": []})
        b["maps"] += 1
        b["deaths"] += _count(r.get("deaths"))
        b["level_ups"] += _count(r.get("level_ups"))
        t = num.finite(r.get("time_s"))
        if r.get("done") and t is not None and t >= 0:
            b["times"].append(t)
    levels = []
    for lvl in sorted(by, reverse=True)[:MAX_ROWS]:
        b = by[lvl]
        med = median(b["times"])
        levels.append({"area_level": lvl, "maps": b["maps"], "deaths": b["deaths"],
                       "level_ups": b["level_ups"], "median_s": med,
                       "median_text": _clock(med) if med is not None else "--:--"})
    highest = max(by) if by else None
    total = sum(b["maps"] for b in by.values())
    text = ""
    if highest is not None:
        text = (f"Highest map level: {highest}, over "
                f"{_plural(total, 'map')}. {MEDIAN_NOTE}")
    return {"title": title, "levels": levels, "highest": highest, "maps": total,
            "text": text, "empty_text": "" if levels else EMPTY_TEXT}


def clean(rec):
    """A bounded, valid saved map record, or None."""
    if not isinstance(rec, dict):
        return None
    area_id = rec.get("area_id")
    if not isinstance(area_id, str) or not area_id:
        return None
    opened = num.finite(rec.get("opened_at"))
    lvl = _int(rec.get("area_level"))
    t = num.finite(rec.get("time_s"))
    if opened is None or opened < 0 or lvl is None or lvl < 0 or t is None or t < 0:
        return None
    seed = _int(rec.get("seed"))
    return {"area_id": area_id[:MAX_ID], "seed": seed, "opened_at": opened,
            "area_level": lvl, "time_s": round(t, 1),
            "deaths": _count(rec.get("deaths")),
            "level_ups": _count(rec.get("level_ups"))}


def same_map(a, b):
    return (a["area_id"] == b["area_id"] and a.get("seed") == b.get("seed")
            and abs(a["opened_at"] - b["opened_at"]) <= MATCH_S)


def load(path):
    """{character key: [records oldest first]} ({} when missing, oversized
    or bad)."""
    doc = jsonfile.read_json(path, max_bytes=MAX_BYTES, kind=dict, backup=True)
    chars = doc.get("characters") if isinstance(doc, dict) else None
    out = {}
    if not isinstance(chars, dict):
        return out
    for key, entry in chars.items():
        if not isinstance(key, str) or len(key) > MAX_ID:
            continue
        raw = entry.get("maps") if isinstance(entry, dict) else None
        if not isinstance(raw, list):
            continue
        recs = [r for r in (clean(x) for x in raw[-MAX_SAVED:]) if r is not None]
        if recs:
            out[key] = sorted(recs, key=lambda r: r["opened_at"])
    return _cap(out)


def _cap(by):
    for k in by:
        by[k] = by[k][-MAX_SAVED:]
    keep = sorted(by, key=lambda k: by[k][-1]["opened_at"])[-MAX_CHARACTERS:]
    return {k: by[k] for k in keep}


def _row_sig(r):
    """What of a session row shapes the all-sessions view: its match key,
    the ladder fields and, for a finished map, its time (an open map's
    time is not final and never counts, only whether clean() keeps it)."""
    t = r.get("time_s")
    done = bool(r.get("done"))
    if not done:
        t = num.finite(t)
        t = t is not None and t >= 0
    return (r.get("area_id"), r.get("seed"), r.get("opened_at"), r.get("area_level"),
            r.get("deaths"), r.get("level_ups"), done, t)


class MapLadder:
    """The saved maps and their ladder. Not thread-safe: the core calls it
    from its loop tick and the clear request under its lock."""

    def __init__(self, path):
        self.path = Path(path)
        self.by = load(self.path)
        self.rev = 0  # moves on with every change of `by` in memory
        self._index = {}  # character key: {(area id, seed): [opened_at]}
        self._view_sig = None
        self._view = None

    def _changed(self):
        self.rev += 1
        self._index = {}

    def _keys(self, key):
        """The (area id, seed) index of one character's saved maps, built
        on first use after a change."""
        idx = self._index.get(key)
        if idx is None:
            idx = {}
            for s in self.by.get(key, []):
                idx.setdefault((s["area_id"], s.get("seed")), []).append(s["opened_at"])
            self._index[key] = idx
        return idx

    @staticmethod
    def _known(idx, rec):
        """True when `rec` matches an indexed map (same_map)."""
        opened = idx.get((rec["area_id"], rec.get("seed")))
        return bool(opened) and any(abs(rec["opened_at"] - o) <= MATCH_S for o in opened)

    def _save(self):
        """Write the ladder file with one .bak of it (F-014)."""
        jsonfile.write_json(self.path, {
            "schema": SCHEMA,
            "characters": {k: {"maps": v} for k, v in self.by.items()}},
            backup=True)

    def record(self, character, maps):
        """Save the finished maps not saved yet under `character` (None is
        the unknown character ""). True when the file was written."""
        key = (character or "")[:MAX_ID]
        saved = self.by.get(key, [])
        idx = self._keys(key)
        new = []
        seen = {}
        for m in maps:
            rec = clean(m)
            if rec is None or self._known(idx, rec) or self._known(seen, rec):
                continue
            new.append(rec)
            seen.setdefault((rec["area_id"], rec.get("seed")), []).append(rec["opened_at"])
        if not new:
            return False
        self.by[key] = sorted(saved + new, key=lambda r: r["opened_at"])
        self.by = _cap(self.by)
        self._changed()
        self._save()
        return True

    def clear(self):
        """Forget every saved map; the .bak goes with the data."""
        self.by = {}
        self._changed()
        self._save()
        runhistory.drop_bak(self.path)

    def view(self, character, session_rows):
        """The all-sessions ladder of `character`: the saved maps plus this
        session's rows not saved yet (the open map, a map closed since the
        last save), each map once. The last view is returned again while
        neither the saved list nor the rows' shaping fields changed."""
        key = (character or "")[:MAX_ID]
        sig = (key, self.rev, tuple(_row_sig(r) for r in session_rows))
        if sig == self._view_sig:
            return self._view
        saved = self.by.get(key, [])
        idx = self._keys(key)
        rows = [dict(r, done=True) for r in saved]
        for r in session_rows:
            rec = clean(r)
            if rec is not None and self._known(idx, rec):
                continue
            rows.append(r)
        self._view = ladder(rows, title=TITLE_ALL)
        self._view_sig = sig
        return self._view
