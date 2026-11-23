"""HUD-ACT: per-act timer splits and the act / zone level table.

Splits come only from events the core already parses (area generation,
research 0002 section 7); no external data. The zone level table is read
from the build-time game-data cache (`<sidecar>\\Cache\\gamedata\\
world_areas.json`, fetched by theorycraft/snapshot.py under decision 0009
as extended by decision 0020). This module only READS that cache: it never
fetches, and the splits work the same when the file is missing.

Act from an area id (`Generating level N area "<id>"`):
- `G<n>_...` -> Act n. VERIFIED live for G1_1 and G1_town (research 0002
  section 7, 2026-11-16).
- `C_G<n>_...` -> Cruel Act n, `P<n>_...` -> Interlude n. INFERRED from
  the id scheme of the community export, not yet seen live (LIVE-1).
- UTIL-1.0-READY: PoE2 1.0 (2026-12-11, research 0018) adds Acts 5 and 6;
  `G5_...` / `G6_...` read as Act 5 / Act 6 by the same rule (any act
  number up to 99), and their zone levels come with the next repoe-fork
  snapshot (build step). Not yet seen live.
- `Map...` -> an endgame map: closes the open split (the campaign is over).
- Anything else (hideouts, towns of unknown shape, unknown ids) changes
  nothing: the open split keeps running, as a speedrun timer would.

Split rules (one run, oldest first):
- The first entry into an act not seen in this run closes the open split
  and opens a split for that act. Going back to an earlier act (a waypoint
  to an old town) keeps counting into the current split.
- Entering the first campaign zone (G1_1) while the player is level 2 or
  less starts a new run (a new character), unless the run is in Act 1.
- A run that did not start at G1_1 (the core started mid-campaign) marks
  its first split partial: its time counts from the first zone AshLight
  saw (live, or read back from Client.txt at core start).
- Times are receipt times (s). A core restart rebuilds the splits from the
  current game run's area generations in Client.txt, timed by their log
  lines (HUD-ACT-RESUME, decision 0023; still no persisted state, as
  decision 0008). The game run starts at the log's newest opening marker,
  so a run that began mid-campaign stays partial.
"""

import json
import re
from pathlib import Path

from . import hotreload
from .theorycraft import datacredit

FILE_NAME = "world_areas.json"
MAX_BYTES = 64 * 1024 * 1024
MAX_SPLITS = 16
ZONES_PER_ACT = 40
FIRST_AREA = "G1_1"
NEW_RUN_MAX_LEVEL = 2

_ACT = (
    (re.compile(r"^G(\d{1,2})_"), "G", "Act {n}"),
    (re.compile(r"^C_G(\d{1,2})_"), "C", "Cruel Act {n}"),
    (re.compile(r"^P(\d{1,2})_"), "P", "Interlude {n}"),
)
_ENDGAME = re.compile(r"^Map")

# Shown under the zone level table whenever it is (decision 0009 item 2).
ATTRIBUTION = datacredit.ZONE_LEVELS_CREDIT  # one source: theorycraft/datacredit.py
# Dashboard copy (design 0001 section 9); the page prints these as given.
# RUN-NO-DEAD-ENDS (research 0042 R4): no script for a player task; the
# supervisor fetches the game data by itself while web data is on
# (DATA-SNAP-AT-START), so the words name the switch and its place.
EMPTY_TEXT = ("No act times yet. They start by themselves when you enter a "
              "campaign zone.")
NO_LEVELS_TEXT = ("Zone levels aren't downloaded yet. AshLight fetches them by "
                  "itself while \"Use web data\" is ticked under Settings, Reading "
                  "and web data.")
NO_ZONES_TEXT = "Zone levels show here while you are in a campaign act."
# UTIL-1.0-FIXTURES: the player is in an act the downloaded table has no
# rows for (Acts 5-6 before the repoe-fork snapshot is refreshed, research
# 0021); NO_ZONES_TEXT would wrongly say they are not in an act.
ACT_NO_LEVELS_TEXT = ("Zone levels for {act} aren't downloaded yet. They "
                      "show here once the game data has them. AshLight "
                      "fetches newer game data by itself, at most once a "
                      "day, while web data is on.")
PARTIAL_TEXT = "partial: counted from the first zone AshLight saw"


def act_of(area_id):
    """{"key", "label", "n"} for a campaign area id, else None."""
    if not isinstance(area_id, str):
        return None
    for rx, prefix, label in _ACT:
        m = rx.match(area_id)
        if m:
            n = int(m.group(1))
            if n < 1:
                return None
            return {"key": f"{prefix}{n}", "label": label.format(n=n), "n": n}
    return None


def label_of(key):
    """"Act 2" for the act key "G2" (the key act_of gives), else None."""
    if not isinstance(key, str) or len(key) < 2 or not key[1:].isdigit():
        return None
    label = next((lab for _rx, prefix, lab in _ACT if prefix == key[0]), None)
    return label.format(n=int(key[1:])) if label else None


def is_endgame(area_id):
    return isinstance(area_id, str) and bool(_ENDGAME.match(area_id))


# RUN-DIAG-DATA-AGE (F-114): the area kinds the cached world_areas file
# must list; an id of these kinds it lacks means the game data is older
# than the game. Hideouts and other ids never count (a hideout id is not
# needed for zone levels and its naming varies).
DATA_AGE_KINDS = ("campaign", "cruel", "interlude", "map")
_KIND_OF_PREFIX = {"G": "campaign", "C": "cruel", "P": "interlude"}


def area_kind(area_id, known=None):
    """{"kind", "known"} for an area id. kind: campaign, cruel, interlude,
    map, hideout or other (a hideout id wins over the other shapes).
    known: True / False whether `known` (the id set of the cached
    world_areas file, load_ids) lists it; None when that set is empty or
    not given (no snapshot: nothing to compare)."""
    if not isinstance(area_id, str) or not area_id:
        kind = "other"
    elif "hideout" in area_id.lower():
        kind = "hideout"
    else:
        info = act_of(area_id)
        if info is not None:
            kind = _KIND_OF_PREFIX[info["key"][0]]
        elif is_endgame(area_id):
            kind = "map"
        else:
            kind = "other"
    has = None
    if known and isinstance(area_id, str):
        has = area_id in known
    return {"kind": kind, "known": has}


def load_ids(path):
    """frozenset of every area id (the object's keys) in a cached
    world_areas.json; a missing, oversized or malformed file gives an
    empty set. Read only, like load_table."""
    try:
        p = Path(path)
        if p.stat().st_size > MAX_BYTES:
            return frozenset()
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return frozenset()
    return ids_from_doc(doc)


def ids_from_doc(doc):
    """load_ids's set from an already parsed world_areas document
    (RUN-DATAAGE-SHARED-PARSE: the data age check shares TableCache's one
    parse); a document that is not an object gives an empty set."""
    if not isinstance(doc, dict):
        return frozenset()
    return frozenset(k for k in doc if isinstance(k, str) and k)


class ActSplits:
    """Per-act timer splits of the current run. Not thread-safe: the
    SessionState lock guards it."""

    def __init__(self):
        self.splits = []
        self.complete_start = False
        self.finished = False

    def _open(self):
        if self.splits and self.splits[-1]["ended_at"] is None:
            return self.splits[-1]
        return None

    def fold(self, area_id, at, player_level=None):
        """One area generation. Returns True when the splits changed."""
        info = act_of(area_id)
        if info is None:
            cur = self._open()
            if is_endgame(area_id) and cur is not None:
                cur["ended_at"] = at
                self.finished = True
                return True
            return False
        cur = self._open()
        new_char = (player_level is None
                    or (isinstance(player_level, int) and player_level <= NEW_RUN_MAX_LEVEL))
        if (area_id == FIRST_AREA and self.splits and new_char
                and not (cur is not None and cur["key"] == "G1")):
            self.splits = []
            self.finished = False
            cur = None
        if not self.splits:
            self.complete_start = area_id == FIRST_AREA
        if any(s["key"] == info["key"] for s in self.splits) or self.finished:
            return False
        if cur is not None:
            cur["ended_at"] = at
        self.splits.append({"key": info["key"], "label": info["label"],
                            "started_at": at, "ended_at": None})
        if len(self.splits) > MAX_SPLITS:
            del self.splits[0]
            self.complete_start = False
        return True

    def current(self):
        cur = self._open()
        return cur["key"] if cur else None

    def rows(self, now):
        """Split rows, oldest first: label, start / end, time in the act and
        the run total at the act's end (or now while it is open)."""
        out = []
        if not self.splits:
            return out
        start = self.splits[0]["started_at"]
        for i, s in enumerate(self.splits):
            end = s["ended_at"] if s["ended_at"] is not None else now
            out.append({"key": s["key"], "label": s["label"],
                        "started_at": s["started_at"], "ended_at": s["ended_at"],
                        "time_s": max(0.0, end - s["started_at"]),
                        "cumulative_s": max(0.0, end - start),
                        "current": s["ended_at"] is None,
                        "partial": i == 0 and not self.complete_start})
        return out


def load_table(path):
    """{act key: [{"id", "name", "level", "town"}, ...]} from a cached
    world_areas.json (an object keyed by area id; fields `name`,
    `area_level`, `is_town`, as checked 2026-11-17, decision 0020). Only
    campaign ids (act_of) are kept; a name seen twice in one act keeps its
    lowest level; rows sort by level, then name; at most ZONES_PER_ACT per
    act. A missing, oversized or malformed file gives {}; a malformed entry
    is skipped."""
    try:
        p = Path(path)
        if p.stat().st_size > MAX_BYTES:
            return {}
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return table_from_doc(doc)


def table_from_doc(doc):
    """load_table's table from an already parsed world_areas document
    (RUN-PERF-PARSE-ONCE: TableCache and the waypoint graph share one
    parse); a document that is not an object gives {}."""
    if not isinstance(doc, dict):
        return {}
    acts = {}
    for area_id, a in doc.items():
        info = act_of(area_id)
        if info is None or not isinstance(a, dict):
            continue
        name = a.get("name")
        level = a.get("area_level")
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(level, int) or isinstance(level, bool) or level < 1:
            continue
        by_name = acts.setdefault(info["key"], {})
        old = by_name.get(name.strip())
        if old is None or level < old["level"] or (level == old["level"]
                                                   and area_id < old["id"]):
            by_name[name.strip()] = {"id": area_id, "name": name.strip(), "level": level,
                                     "town": a.get("is_town") is True}
    return {k: sorted(v.values(), key=lambda r: (r["level"], r["name"]))[:ZONES_PER_ACT]
            for k, v in acts.items()}


def default_path(environ=None):
    return datacredit.cache_dir(environ) / FILE_NAME


class TableCache(hotreload.Watched):
    """Loads the cached table once and again only when the file changes;
    a malformed rewrite keeps the last good table (HOT-RELOAD, 0042). One
    parse of the file feeds this table and zoneguide.graph_cache's graph
    (RUN-PERF-PARSE-ONCE)."""

    def __init__(self, path):
        super().__init__(path, load_table, name="Zone level table", default=dict,
                         check=hotreload.check_json(MAX_BYTES),
                         from_doc=table_from_doc, share=True)


def view(splits, table, area_id, zone, now):
    """The `acts` part of the state snapshot."""
    rows = splits.rows(now)
    table = table if isinstance(table, dict) else {}
    key = splits.current()
    here = act_of(area_id)
    if here is not None:
        key = here["key"]
    if key is None and rows and not splits.finished and not is_endgame(area_id):
        key = rows[-1]["key"]
    if here is None and (splits.finished or is_endgame(area_id)):
        key = None  # endgame: no campaign zone table (design review HA-2)
    zones, zones_act = [], None
    act_levels_text = ""
    if key is not None and table and not table.get(key) and label_of(key):
        act_levels_text = ACT_NO_LEVELS_TEXT.format(act=label_of(key))
    if key is not None and table.get(key):
        zones_act = label_of(key)
        zones =[{"name": z["name"], "level": z["level"], "town": z["town"],
                  "here": z["id"] == area_id or (zone is not None and z["name"] == zone)}
                 for z in table[key]]
    return {"splits": rows, "current": key, "finished": splits.finished,
            "zones": zones, "zones_act": zones_act, "levels": bool(table),
            "source": ATTRIBUTION if table else None,
            "empty_text": EMPTY_TEXT, "no_levels_text": NO_LEVELS_TEXT,
            "no_zones_text": NO_ZONES_TEXT,
            "act_levels_text": act_levels_text,
            "partial_text": PARTIAL_TEXT}
