"""UTIL-MAPS and UTIL-DEATHS: the map run tracker and the death recap.

Both fold only events the core already parses from Client.txt (area
generation, scene change, death; research 0002 section 7). No external
data, no network, no input to the game. The core sends every sentence in
the snapshot; the dashboard only prints them (design 0001 section 9).

Map runs (UTIL-MAPS):
- An area generation whose id starts with `Map` (acts.is_endgame) is a new
  map: it closes the open one and opens a new one. A campaign area
  generation (acts.act_of) closes the open map. Hideout and other ids
  change nothing (a portal trip keeps the map open).
- The first non-hideout scene after a map's generation names it and starts
  its clock; the clock runs only while the player's scene is that map, so
  hideout trips and loading screens do not count. A map that never got a
  scene is named from its id (`MapCrypt` -> `Crypt`).
- A death counts into the map only while the player is in it.
- History is in memory, like the rest of the session (decision 0008); at
  core start replay() rebuilds the current game run's maps and deaths from
  the backward scan of Client.txt (UTIL-MAPS-RESUME), nothing persisted.

Death recap (UTIL-DEATHS): each of the player's deaths with the zone, its
area level, the character level and the time spent in the zone before it.
"""

import collections
import re

from . import acts

MAX_MAPS = 200
RECENT_MAPS = 5
RECENT_DEATHS = 5
MAX_DEATHS = 500

MAPS_EMPTY_TEXT = ("No maps yet. Map times start by themselves when you "
                   "open a map.")
DEATHS_EMPTY_TEXT = ("No deaths this session. Each one shows here with its "
                     "zone and level.")


def clock_text(s):
    """Seconds as m:ss or h:mm:ss, the dashboard's timer form."""
    if s is None:
        return "--:--"
    s = max(0, int(s))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def map_name(area_id, scene):
    if scene:
        return scene
    rest = area_id[3:] if isinstance(area_id, str) else ""
    # MapSunTemple -> "Sun Temple"; ids with "_" keep their parts.
    rest = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", rest.replace("_", " ")).strip()
    return rest or "Map"


def _plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


class MapRuns:
    """Map runs of this session. Not thread-safe: the SessionState lock
    guards it."""

    def __init__(self):
        self.cur = None
        self.closed = collections.deque(maxlen=MAX_MAPS)
        self.count = 0
        self.done = 0
        self.done_s = 0.0
        self.deaths = 0

    def _time(self, m, now):
        t = m["in_s"]
        if m["entered_at"] is not None:
            t += max(0.0, now - m["entered_at"])
        return t

    def _close(self, at):
        m = self.cur
        if m is None:
            return False
        m["in_s"] = self._time(m, at)
        m["entered_at"] = None
        self.closed.append(m)
        self.done += 1
        self.done_s += m["in_s"]
        self.cur = None
        return True

    def on_generated(self, area_id, at, area_level):
        """One area generation. Returns True when the maps changed."""
        if acts.is_endgame(area_id):
            self._close(at)
            self.count += 1
            self.cur = {"area_id": area_id, "area_level": area_level,
                        "scene": None, "in_s": 0.0, "entered_at": None,
                        "deaths": 0}
            return True
        if acts.act_of(area_id) is not None:
            return self._close(at)
        return False

    def on_scene(self, scene, at, is_hideout):
        """The player's zone changed to `scene`."""
        m = self.cur
        if m is None or not scene:
            return False
        if m["scene"] is None and not is_hideout:
            m["scene"] = scene
        if scene == m["scene"]:
            if m["entered_at"] is None:
                m["entered_at"] = at
                return True
            return False
        if m["entered_at"] is not None:
            m["in_s"] = self._time(m, at)
            m["entered_at"] = None
            return True
        return False

    def on_death(self, at):
        m = self.cur
        if m is None or m["entered_at"] is None:
            return False
        m["deaths"] += 1
        self.deaths += 1
        return True

    def _row(self, m, now):
        return {"name": map_name(m["area_id"], m["scene"]),
                "area_level": m["area_level"], "time_s": self._time(m, now),
                "deaths": m["deaths"]}

    def view(self, now):
        """The `maps` part of the state snapshot."""
        cur = None
        if self.cur is not None:
            cur = dict(self._row(self.cur, now),
                       inside=self.cur["entered_at"] is not None)
        recent = [self._row(m, now) for m in reversed(self.closed)][:RECENT_MAPS]
        avg = self.done_s / self.done if self.done else None
        avg_text = (f"Average map: {clock_text(avg)} over "
                    f"{_plural(self.done, 'finished map')}." if self.done else "")
        if not self.count:
            deaths_text = ""
        elif self.deaths:
            deaths_text = _plural(self.deaths, "death") + " in maps."
        else:
            deaths_text = "No deaths in maps."
        return {"count": self.count, "done": self.done, "current": cur,
                "recent": recent, "avg_s": avg, "avg_text": avg_text,
                "deaths_text": deaths_text, "empty_text": MAPS_EMPTY_TEXT}


def death_text(zone, area_level, level, zone_s):
    text = "Died"
    if zone:
        text += f" in {zone}"
        if isinstance(area_level, int):
            text += f" (area level {area_level})"
    if isinstance(level, int):
        text += f" at level {level}"
    if zone and zone_s is not None:
        text += f", {clock_text(zone_s)} into the zone"
    return text + "."


class DeathLog:
    """The player's deaths this session, newest last. Not thread-safe."""

    def __init__(self):
        self.rows = collections.deque(maxlen=MAX_DEATHS)
        self.by_zone = collections.Counter()

    def add(self, at, zone, area_level, level, zone_s):
        self.rows.append({"at": at, "zone": zone, "area_level": area_level,
                          "level": level,
                          "text": death_text(zone, area_level, level, zone_s)})
        if zone:
            self.by_zone[zone] += 1

    def view(self):
        """The `death_recap` part of the state snapshot."""
        recent = [dict(r) for r in reversed(self.rows)][:RECENT_DEATHS]
        worst = ""
        if self.by_zone:
            zone, n = self.by_zone.most_common(1)[0]
            if n >= 2:
                worst = f"Most deaths: {zone} ({n})."
        return {"recent": recent, "worst_text": worst,
                "empty_text": DEATHS_EMPTY_TEXT}


def replay(events, me=None):
    """UTIL-MAPS-RESUME: rebuild (MapRuns, DeathLog) from the current game
    run's events, oldest first, each with an epoch `at` (resume.state_fields
    `run_events`). The folds are the ones SessionState.apply makes, so a
    restart mid-map keeps the map's time and the run's deaths. `me` names
    the player; None counts every death, as the live state does before a
    character is known."""
    maps = MapRuns()
    log = DeathLog()
    zone = None
    entered = None
    area_level = None
    mine = [e.get("level") for e in events
            if e.get("type") == "level_up" and e.get("character") == me]
    level = (mine[0] - 1) if mine and isinstance(mine[0], int) else None
    for e in events:
        t = e.get("type")
        at = e.get("at")
        if not isinstance(at, (int, float)):
            continue
        if t in ("scene_changed", "area_entered"):
            if t == "scene_changed":
                if e.get("is_null") or e.get("is_transient"):
                    continue
                scene = e.get("scene")
                hideout = bool(e.get("is_hideout"))
            else:
                scene = e.get("name")
                hideout = "hideout" in (scene or "").lower()
            if scene and scene != zone:
                zone = scene
                entered = at
                maps.on_scene(zone, at, hideout)
        elif t == "area_generated":
            area_level = e.get("area_level")
            maps.on_generated(e.get("area_id"), at, area_level)
        elif t == "level_up":
            if e.get("character") == me:
                level = e.get("level")
        elif t == "death":
            if me is None or e.get("character") == me:
                log.add(at=at, zone=zone, area_level=area_level, level=level,
                        zone_s=(max(0.0, at - entered) if entered else None))
                maps.on_death(at)
    return maps, log
