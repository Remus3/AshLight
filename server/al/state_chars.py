"""SessionState's characters as CharsMixin (TEST-STATE-MIXIN-B, F-192,
research 0047 R5 (2); the pattern is the loop's mixins, tools/loop_inbox.py
and tools/loop_merge.py).

UTIL-MULTICHAR (decision 0038 and its amendments): the current character's
field set, the parked characters, the other players' names of this game
run, the switch rule and its game-start and relog windows, the characters
view and the resume replay (_restore_chars); UTIL-RUN-HISTORY: the current
run's deaths per zone and its history record; RUN-P8-8-CHARMIX: the maps
that move at a switch (_split_maps / _merge_maps). The methods moved
verbatim from state.py: the lock is SessionState's one lock, the event
dispatcher (apply / _apply_locked) stays in state.py and calls the helpers
here. state.py re-exports every module name here, so state.<name> stays.
Stdlib only.
"""

import collections

from . import acts as acts_mod
from . import pace as pace_mod
from . import runs as runs_mod

# UTIL-MULTICHAR (decision 0038): at most this many characters are kept
# (the current one included); names seen joining / leaving the area this
# game run are other players and never switch the current character, and
# a switch happens only on the first name line after a game start.
MAX_CHARACTERS = 12
MAX_OTHERS = 64
# The per-character fields; SessionState holds the current character's
# set as attributes and parks the others' sets by name.
# RUN-P8-8-CHARMIX (AUDIT-P8-LOW P8-8): "maps" is per character, so the
# "This session" ladder and the Maps card never mix characters.
CHAR_FIELDS = ("char_class", "level", "level_ups", "deaths", "acts", "pace",
               "run_deaths", "_run_start", "maps")


def _split_maps(runs, since):
    """RUN-P8-8-CHARMIX: take the maps opened at or after `since` out of
    `runs` (a runs.MapRuns) into a new MapRuns, moving their counts with
    them. The maps of the game run in which a switch happens are the new
    character's (AREA-AUDIT P8-1)."""
    moved = runs_mod.MapRuns()

    def late(m):
        at = m.get("opened_at")
        return isinstance(at, (int, float)) and at >= since

    keep = [m for m in runs.closed if not late(m)]
    take = [m for m in runs.closed if late(m)]
    cur = runs.cur if runs.cur is not None and late(runs.cur) else None
    if not take and cur is None:
        return moved
    runs.closed = collections.deque(keep, maxlen=runs.closed.maxlen)
    moved.closed.extend(take)
    if cur is not None:
        runs.cur = None
        moved.cur = cur
    opened = take + ([cur] if cur is not None else [])
    moved.count = len(opened)
    moved.done = len(take)
    moved.done_s = sum(m["in_s"] for m in take)
    moved.deaths = sum(m["deaths"] for m in opened)
    moved.first_at = min(m["opened_at"] for m in opened)
    runs.count = max(0, runs.count - moved.count)
    runs.done = max(0, runs.done - moved.done)
    runs.done_s = max(0.0, runs.done_s - moved.done_s)
    runs.deaths = max(0, runs.deaths - moved.deaths)
    if not runs.count:
        runs.first_at = None
    return moved


def _merge_maps(runs, moved):
    """RUN-P8-8-CHARMIX: add the moved maps (_split_maps) to a character's
    own runs. A map that character left open (paused when it was parked)
    closes where the first moved map opened, as one session's runs would
    have closed it; with nothing moved it stays open for that character."""
    if not moved.count:
        return runs
    if not runs.count:
        return moved
    opened = list(moved.closed) + ([moved.cur] if moved.cur is not None else [])
    runs._close(min(m["opened_at"] for m in opened))
    runs.closed.extend(moved.closed)
    runs.cur = moved.cur
    runs.count += moved.count
    runs.done += moved.done
    runs.done_s += moved.done_s
    runs.deaths += moved.deaths
    if runs.first_at is None:
        runs.first_at = moved.first_at
    return runs


class CharsMixin:
    """Mixed into state.SessionState. _init_chars() runs from __init__,
    _view_chars(now) from snapshot()."""

    def _init_chars(self):
        # UTIL-RUN-HISTORY: the player's deaths per zone in the current
        # campaign run (keyed by the run's first split start), and the
        # history view the core publishes (runhistory.py).
        self.run_deaths = collections.Counter()
        self._run_start = None
        # UTIL-MULTICHAR: the other characters' field sets by name (oldest
        # use first) and the other players' names of this game run.
        self._parked = collections.OrderedDict()
        self._others = set()
        # Decision 0038 switch rule: True from a game start (log_opened)
        # until its first level-up or death line; party is True once
        # another player joined or left the area since that game start.
        self._start_window = False
        self._party_since_start = False
        # Decision 0038 amendment 2026-11-22 (relog): True from a relog
        # through character select (char_select) until the first level-up
        # or death line of a name never seen joining or leaving; the party
        # flag does not apply to it.
        self._relog_window = False
        # AREA-AUDIT P8-1 / RUN-P8-8-CHARMIX: the time of the last game start
        # or relog through character select; at a character switch the maps
        # opened since then move to the new character (None: no start seen).
        self._game_start_at = None
        # The time of the first campaign zone generated since the last name
        # line: a brand-new character's run starts there, not at its first
        # level-up (decision 0038).
        self._first_gen_at = None

    def _view_chars(self, now):
        """Caller holds the lock. The snapshot's character keys."""
        return {"character": self.character,
                # RUN-CHARACTER-PIN: the picker's pin is pressed
                "character_pinned": self.character_fixed,
                # UTIL-MULTICHAR: every character's numbers, current first
                "characters": self._characters_view(now)}

    def _run_counter(self):
        """UTIL-RUN-HISTORY: the deaths counter of the current run, reset
        when the act splits start a new run. Caller holds the lock."""
        start = self.acts.splits[0]["started_at"] if self.acts.splits else None
        if start != self._run_start:
            self._run_start = start
            self.run_deaths = collections.Counter()
        return self.run_deaths

    def run_record(self):
        """UTIL-RUN-HISTORY: the current campaign run as a history record
        (runhistory.clean_run shape) plus "closed" (closed split count),
        or None before the first act split. Only closed, complete splits
        carry a time (a partial or open split is no best)."""
        with self._lock:
            if not self.acts.splits:
                return None
            self._run_counter()
            return self._record_of(self.character,
                                   {f: getattr(self, f) for f in CHAR_FIELDS})

    def _record_of(self, name, fields):
        """A history record of one character's field set. Caller holds the
        lock and has reset a stale death counter."""
        acts = fields["acts"]
        rows = acts.rows(self._clock())
        closed = [r for r in rows if not r["current"]]
        start = acts.splits[0]["started_at"]
        deaths = fields["run_deaths"] if fields["_run_start"] == start else {}
        return {"started_at": start,
                "character": name, "class": fields["char_class"],
                "splits": [{"key": r["key"], "label": r["label"],
                            "time_s": r["time_s"]}
                           for r in closed if not r["partial"]],
                "deaths": dict(deaths), "finished": acts.finished,
                "closed": len(closed)}

    def _is_me(self, name):
        return self.character is None or name == self.character

    # -- UTIL-MULTICHAR (decision 0038)
    @staticmethod
    def _fresh_fields(now):
        p = pace_mod.Pace()
        p.reset_at = now  # its hourly rate counts from the switch
        return {"char_class": None, "level": None, "level_ups": 0, "deaths": 0,
                "acts": acts_mod.ActSplits(), "pace": p,
                "run_deaths": collections.Counter(), "_run_start": None,
                "maps": runs_mod.MapRuns()}

    def _may_switch(self, name):
        """True when a name line should make `name` the current character
        (decision 0038): only the first level-up or death line after a game
        start (log_opened), and only while no other player has joined or
        left the area since that start. Never mid-session: a party member
        already in the area levels up with no join line of their own. A
        configured character never switches; other players' names (seen
        joining or leaving the area this game run) never do. The first
        level-up when no character is known yet names it (apply).
        Amendment 2026-11-22: after a relog through character select
        (char_select) the first name line of a name never seen joining or
        leaving switches too, whatever the party flag says, because a party
        member can join between the relog and the player's first line."""
        if (self.character_fixed or not name or name == self.character
                or self.character is None or name in self._others):
            return False
        return self._relog_window or (
            self._start_window and not self._party_since_start)

    def _close_windows(self, name):
        """A name line closes the game-start window; it closes the relog
        window only when the name is not a known other player."""
        if name:
            self._start_window = False
            if name not in self._others:
                self._relog_window = False

    def _switch(self, name, now):
        """Park the current character's fields and load `name`'s (fresh
        when new). Caller holds the lock."""
        # AREA-AUDIT P8-1 / RUN-P8-8-CHARMIX: the maps opened since the last
        # game start or relog are the new character's; a map the old one
        # left open stays its own, paused, and is saved under it when it
        # closes (the core saves the current character's maps).
        since = self._game_start_at if self._game_start_at is not None else now
        moved = _split_maps(self.maps, since)
        self.maps.pause(now)
        if self.character is not None:
            self._parked[self.character] = {f: getattr(self, f) for f in CHAR_FIELDS}
            self._parked.move_to_end(self.character)
        loaded = self._parked.pop(name, None)
        if loaded is None:
            loaded = self._fresh_fields(now)
            if self._first_gen_at is not None:
                loaded["acts"].fold(acts_mod.FIRST_AREA, self._first_gen_at, None)
        loaded["maps"] = _merge_maps(loaded["maps"], moved)
        for f in CHAR_FIELDS:
            setattr(self, f, loaded[f])
        self.character = name
        while len(self._parked) > MAX_CHARACTERS - 1:
            self._parked.popitem(last=False)

    def set_character(self, name):
        """RUN-CHARACTER-PIN (F-157): the one setter that fixes or frees the
        character (the "character" setting, from the picker's pin or an edit
        of config/local.json, applied by the core without a restart). A name
        makes it the configured character (decision 0038: a configured
        character never switches): the current one is parked and `name`
        loaded when it differs; with no character known yet the fields seen
        so far become its own. None or "" frees it: the character being
        played stays and later name lines may switch again. Returns True on
        a change."""
        name = name.strip() if isinstance(name, str) else None
        name = name or None
        with self._lock:
            if name is None:
                if not self.character_fixed:
                    return False
                self.character_fixed = False
            else:
                if self.character_fixed and name == self.character:
                    return False
                self._others.discard(name)
                if self.character is None:
                    self.character = name
                elif name != self.character:
                    self._switch(name, self._clock())
                self.character_fixed = True
            self.version += 1
            return True

    def _note_other(self, name):
        if name and name != self.character and len(self._others) < MAX_OTHERS:
            self._others.add(name)

    def character_names(self):
        """The current character first, then the others, newest use first."""
        with self._lock:
            names = [self.character] if self.character else []
            return names + [n for n in reversed(self._parked) if n not in names]

    def _char_view(self, name, fields, now, current):
        acts_v = acts_mod.view(fields["acts"], self.zone_table,
                               self.area_id if current else None,
                               self.zone if current else None, now)
        return {"name": name, "current": current, "class": fields["char_class"],
                "level": fields["level"], "deaths": fields["deaths"],
                "level_ups": fields["level_ups"], "acts": acts_v,
                "pace": fields["pace"].view(now, self.pace_started_at)}

    def _characters_view(self, now):
        """The snapshot `characters` list (current first, at most
        MAX_CHARACTERS). Caller holds the lock."""
        out = []
        if self.character:
            out.append(self._char_view(self.character,
                                       {f: getattr(self, f) for f in CHAR_FIELDS},
                                       now, True))
        for name in reversed(self._parked):
            if len(out) >= MAX_CHARACTERS:
                break
            out.append(self._char_view(name, self._parked[name], now, False))
        return out

    def parked_record(self, name):
        """UTIL-MULTICHAR: a parked character's run as a history record
        (run_record shape), or None."""
        with self._lock:
            fields = self._parked.get(name)
            if not fields or not fields["acts"].splits:
                return None
            return self._record_of(name, fields)

    def _restore_chars(self, events, run_start_known):
        """UTIL-MULTICHAR: replay the current game run's events through a
        scratch state seeded with the scanned character (the newest
        level-up) and a game start when the scan reached the run's marker,
        so the decision 0038 switch rule decides the run's character the
        same way it does live: the first name line after the start, unless
        another player joined or left the area first. When the rule keeps
        the scanned character, the single-character restore above stays;
        otherwise the run's character takes its name, class, level and
        counts from the replay.
        A scanned name that the run shows joining or leaving the area is
        another player: the character becomes unknown, so the player's
        next level-up names it. Pace counts live level-ups only
        (UTIL-PACE), so it starts fresh. Caller holds the lock."""
        tmp = type(self)(clock=self._clock)
        tmp.character = self.character
        first = next((e["at"] for e in events
                      if isinstance(e.get("at"), (int, float))), None)
        if run_start_known and first is not None:
            tmp.apply({"type": "log_opened", "recv_ts": first})
        for e in events:
            if e.get("type") in self._REPLAY_TYPES and isinstance(e.get("at"), (int, float)):
                tmp.apply(dict(e, recv_ts=e["at"]))
        self._start_window = tmp._start_window
        self._relog_window = tmp._relog_window
        self._party_since_start = tmp._party_since_start
        joined = {e.get("character") for e in events
                  if e.get("type") in ("player_joined_area", "player_left_area")
                  and e.get("character")}
        self._others = set(list(tmp._others | joined)[:MAX_OTHERS])
        if tmp.character is not None and tmp.character in joined:
            self.character = None
            self.char_class = self.level = None
            self.level_ups = self.deaths = 0
            return
        if tmp.character is None or tmp.character == self.character:
            return
        # The act splits stay the run-wide rebuild above (decision 0023):
        # one game run is one character now, and its first campaign zone
        # still starts a brand-new character's run.
        self.character = tmp.character
        for f in ("char_class", "level", "level_ups", "deaths"):
            setattr(self, f, getattr(tmp, f))
        self.pace = pace_mod.Pace()
