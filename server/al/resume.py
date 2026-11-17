"""LIVE-RESUME: recover the current state from the end of Client.txt.

The tailer starts at the end of the file so old events are never re-listed.
That left zone, character, class, level and deaths empty after a core restart
until the next zone change or level-up. scan() reads the file BACKWARDS from
the tailer's start offset in fixed chunks, bounded by a byte cap, and returns
the state fields only; nothing is published on the bus (decision 0008).

Rules (newest line first):
- The current game run starts at the newest `***** LOG FILE OPENING *****`
  marker. Zone, area, AFK / DND and the death and level-up counts come from
  the current run only; a zone of an earlier run is not current.
- Character, class and level come from the newest level-up of the character
  (the configured one, else the newest level-up seen), across runs, because a
  character's level persists.
- The scan stops at the marker once the character is known, or at the cap.
- HUD-ACT-RESUME (decision 0023): the current run's campaign and endgame
  area generations come back as `act_areas`, oldest first, with their line
  time and the character's level then, so the act splits rebuild at core
  start instead of starting empty. A streak of ids in one act (or of maps)
  keeps only its first entry, except the first campaign zone, which may
  start a new character's run; that is all acts.ActSplits.fold needs.
- UTIL-MAPS-RESUME (decision 0023 pattern): the current run's scenes, area
  generations, deaths and level-ups come back as `run_events`, oldest
  first, at most MAX_RUN_EVENTS (the newest kept), so the map runs and the
  death recap are replayed at core start (runs.replay). Scene lines are
  therefore read for the whole current run.

Speed: only lines holding a keyword (scene, area generation, system line,
marker) are decoded and parsed; the keyword search runs in C over each chunk.
Read only, with full sharing, exactly like the tailer (decision 0003).
"""

import os
import re
import time

from . import acts, logfile, parser

CHUNK = 1024 * 1024
DEFAULT_MAX_BYTES = 32 * 1024 * 1024
MAX_RUN_EVENTS = 20000
_RUN_TYPES = ("scene_changed", "area_entered", "area_generated", "death",
              "level_up",
              # UTIL-MULTICHAR: other players' names, so a restart keeps
              # them from switching the current character (decision 0038)
              "player_joined_area", "player_left_area")
MARKER = b"***** LOG FILE OPENING *****"
_MARKER_TS = re.compile(rb"^(\d{4})/(\d{2})/(\d{2}) (\d{2}:\d{2}:\d{2}) ")
_KEY = re.compile(rb"\] (?:\[SCENE\] |Generating level |: )|\*\*\*\*\* LOG FILE OPENING")
# Before the current run only level-ups and the marker matter.
_KEY_LVL = re.compile(rb"\) is now level \d|\*\*\*\*\* LOG FILE OPENING")
_BOM = b"\xef\xbb\xbf"


def _lines_newest_first(seg, key=_KEY):
    """Keyword lines of one complete-lines segment, newest first."""
    out = []
    last_start = -1
    for m in key.finditer(seg):
        p = m.start()
        start = seg.rfind(b"\n", 0, p) + 1
        if start == last_start:
            continue
        last_start = start
        stop = seg.find(b"\n", p)
        out.append(seg[start:stop if stop >= 0 else len(seg)])
    out.reverse()
    return out


def _chunks_backward(fh, end, floor):
    """Yield complete-line segments from end back to floor, newest first, and
    the start offset reached. A line cut by the cap or by `end` is dropped."""
    pos = end
    carry = b""
    tail_open = True  # the bytes before `end` may end in an unterminated line
    while pos > floor:
        start = max(floor, pos - CHUNK)
        fh.seek(start)
        data = fh.read(pos - start) + carry
        pos = start
        if tail_open:
            cut = data.rfind(b"\n")
            if cut < 0:
                carry = b""  # all of it belongs to the unterminated line
                continue
            tail_open = False
            data = data[:cut + 1]
        if start > 0:
            nl = data.find(b"\n")
            if nl < 0:
                carry = data
                if start == floor:
                    return
                continue
            carry = data[:nl + 1] if start > floor else b""
            data = data[nl + 1:]
        else:
            carry = b""
            if data.startswith(_BOM):
                data = data[len(_BOM):]
        yield data, start


def scan(path, end=None, max_bytes=DEFAULT_MAX_BYTES, character=None):
    """State fields from the newest lines of Client.txt up to byte `end`
    (default: the current size), reading at most max_bytes backwards.
    Returns None when the file cannot be read."""
    try:
        size = os.stat(path).st_size
    except OSError:
        return None
    end = size if end is None else min(int(end), size)
    floor = max(0, end - int(max_bytes))
    fixed = character or None
    out = {"zone": None, "in_hideout": False, "zone_ts_local": None,
           "area_id": None, "area_level": None, "character": None,
           "class": None, "level": None, "deaths": 0, "level_ups": 0,
           "afk": None, "dnd": None, "hit_marker": False, "run_ts_local": None,
           "bytes_scanned": 0,
           "end": end}
    in_run = True
    deaths = []
    ups = []
    seq = []  # in-run area generations and level-ups, newest first
    run_ev = []  # in-run events for runs.replay, newest first
    reached = end
    try:
        fh = logfile._open_shared(path)
    except OSError:
        return None
    try:
        for seg, start in _chunks_backward(fh, end, floor):
            reached = start
            done = False
            # In the current run scenes are needed for the map clock
            # (UTIL-MAPS-RESUME); before it only level-ups matter.
            key = _KEY if in_run else _KEY_LVL
            for raw in _lines_newest_first(seg, key):
                if MARKER in raw[:64]:
                    if in_run:
                        in_run = False
                        out["hit_marker"] = True
                        out["run_ts_local"] = _marker_ts(raw)
                    if out["character"] is not None:
                        done = True
                        break
                    continue
                ev = parser.parse_line(raw.rstrip(b"\r").decode("utf-8", "replace"))
                if ev is None:
                    continue
                t = ev["type"]
                if in_run and t in _RUN_TYPES and len(run_ev) < MAX_RUN_EVENTS:
                    run_ev.append(ev)
                if t == "level_up":
                    name = ev.get("character")
                    if out["character"] is None and (fixed is None or name == fixed):
                        out["character"] = name
                        out["class"] = ev.get("class")
                        out["level"] = ev.get("level")
                    if in_run:
                        ups.append(name)
                        seq.append(("l", name, ev.get("level")))
                    elif out["character"] is not None:
                        done = True
                        break
                    continue
                if not in_run:
                    continue
                if t == "scene_changed":
                    if (out["zone"] is None and not ev.get("is_null")
                            and not ev.get("is_transient") and ev.get("scene")):
                        out["zone"] = ev["scene"]
                        out["in_hideout"] = bool(ev.get("is_hideout"))
                        out["zone_ts_local"] = ev.get("ts_local")
                elif t == "area_generated":
                    if out["area_id"] is None:
                        out["area_id"] = ev.get("area_id")
                        out["area_level"] = ev.get("area_level")
                    aid = ev.get("area_id")
                    if acts.act_of(aid) is not None or acts.is_endgame(aid):
                        seq.append(("a", aid, ev.get("ts_local")))
                elif t == "death":
                    deaths.append(ev.get("character"))
                elif t == "afk_changed":
                    if out["afk"] is None:
                        out["afk"] = bool(ev.get("on"))
                elif t == "dnd_changed":
                    if out["dnd"] is None:
                        out["dnd"] = bool(ev.get("on"))
            if done:
                break
    finally:
        fh.close()
    me = out["character"]
    out["deaths"] = sum(1 for n in deaths if me is None or n == me)
    out["level_ups"] = sum(1 for n in ups if me is not None and n == me)
    out["afk"] = bool(out["afk"])
    out["dnd"] = bool(out["dnd"])
    out["bytes_scanned"] = end - reached
    out["act_areas"] = _act_areas(seq, me, out["level"])
    out["run_events"] = _run_events(run_ev)
    return out


_EV_KEYS = ("type", "ts_local", "scene", "is_null", "is_transient",
            "is_hideout", "area_id", "area_level", "seed", "character",
            "level", "class", "name")


def _run_events(newest_first):
    """Oldest-first compact copies of the run's events for runs.replay."""
    return [{k: ev[k] for k in _EV_KEYS if k in ev}
            for ev in reversed(newest_first)]


def _streak_key(area_id):
    info = acts.act_of(area_id)
    return info["key"] if info else "Map"


def _act_areas(seq, me, level_now):
    """Oldest-first area generations of the run with the character's level
    at each; streaks compressed (see the module notes)."""
    seq = list(reversed(seq))
    mine = [lv for kind, name, lv in seq if kind == "l" and name == me]
    level = (mine[0] - 1) if mine and isinstance(mine[0], int) else level_now
    out = []
    prev = None
    for kind, a, b in seq:
        if kind == "l":
            if a == me:
                level = b
            continue
        key = _streak_key(a)
        if key != prev or a == acts.FIRST_AREA:
            out.append({"area_id": a, "ts_local": b, "level": level})
        prev = key
    return out


def _marker_ts(raw):
    """The local ISO time of a LOG FILE OPENING line, or None."""
    m = _MARKER_TS.match(raw)
    if not m:
        return None
    y, mo, d, hms = (g.decode("ascii") for g in m.groups())
    return f"{y}-{mo}-{d}T{hms}"


def local_ts_to_epoch(ts_local, now=None):
    """Epoch seconds for a line's local ISO time, never in the future; None
    when it does not parse."""
    if not ts_local:
        return None
    try:
        t = time.mktime(time.strptime(ts_local, "%Y-%m-%dT%H:%M:%S"))
    except (ValueError, OverflowError):
        return None
    now = time.time() if now is None else now
    return min(t, now)


def state_fields(result, now=None):
    """The SessionState.restore() fields for a scan() result."""
    if not result:
        return {}
    fields = {k: result[k] for k in ("zone", "in_hideout", "area_id", "area_level",
                                     "character", "class", "level", "deaths",
                                     "level_ups", "afk", "dnd")}
    if result["zone"] is not None:
        fields["zone_entered_at"] = local_ts_to_epoch(result["zone_ts_local"], now)
    # UX-NEW-CARDS: the Session tile counts from the game's log opening, the
    # same run the resumed deaths, level-ups and act splits come from, so
    # it never reads shorter than the zone or act timer next to it.
    started = local_ts_to_epoch(result.get("run_ts_local"), now)
    if started is not None:
        fields["session_started_at"] = started
    areas = []
    for a in result.get("act_areas") or ():
        at = local_ts_to_epoch(a["ts_local"], now)
        if at is not None:
            areas.append({"area_id": a["area_id"], "at": at, "level": a["level"]})
    fields["act_areas"] = areas
    events = []
    for ev in result.get("run_events") or ():
        at = local_ts_to_epoch(ev.get("ts_local"), now)
        if at is not None:
            events.append(dict(ev, at=at))
    fields["run_events"] = events
    return fields
