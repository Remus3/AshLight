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
import os
import re
from pathlib import Path

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
EMPTY_TEXT = ("No act times yet. They start by themselves when you enter a "
              "campaign zone.")
NO_LEVELS_TEXT = ("Zone levels aren't downloaded yet. Turn on web data, then run "
                  "AshLight's build step (scripts/build.ps1).")
NO_ZONES_TEXT = "Zone levels show here while you are in a campaign act."
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


class TableCache:
    """Loads the cached table once and again only when the file changes."""

    def __init__(self, path):
        self.path = Path(path)
        self._sig = None
        self._table = {}

    def get(self):
        try:
            st = os.stat(self.path)
            sig = (st.st_mtime_ns, st.st_size)
        except OSError:
            self._sig, self._table = None, {}
            return self._table
        if sig != self._sig:
            self._table = load_table(self.path)
            self._sig = sig
        return self._table


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
            "partial_text": PARTIAL_TEXT}
