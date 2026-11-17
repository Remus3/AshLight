"""Derived session state, built only from bus events.

Times are wall-clock receipt times (time.time()); the line's own timestamp is
local time without a zone, so it is kept for display only. Every buffer is
bounded.
"""

import collections
import threading
import time

RECENT_EVENTS = 30
RECENT_WHISPERS = 10
TRADE_REQUESTS = 5  # open trade whisper cards (HUD-WHISPER); oldest drops
TRADE_FIELDS = ("kind", "item", "price_amount", "price_currency", "want_amount",
                "league", "stash_tab", "left", "top")

# Event types shown in the dashboard's recent list.
LISTED = {"scene_changed", "area_entered", "level_up", "death", "whisper_in",
          "whisper_out", "afk_changed", "dnd_changed", "player_joined_area",
          "player_left_area", "trade_accepted", "session_connect",
          "tailer_started", "tailer_reset"}


def summarize(ev):
    """One short display line for an event."""
    t = ev.get("type")
    if t == "scene_changed":
        return f"Entered {ev.get('scene')}" + (" (hideout)" if ev.get("is_hideout") else "")
    if t == "area_entered":
        return f"Entered {ev.get('name')}"
    if t == "area_generated":
        return f"Area level {ev.get('area_level')} ({ev.get('area_id')})"
    if t == "level_up":
        return f"{ev.get('character')} is now level {ev.get('level')}"
    if t == "death":
        return f"{ev.get('character')} died" + (" (suicide)" if ev.get("suicide") else "")
    if t == "whisper_in":
        tr = ev.get("trade")
        if tr:
            price = ""
            if tr.get("price_amount") is not None:
                price = f" for {tr['price_amount']} {tr.get('price_currency')}"
            return f"Trade from {ev.get('from')}: {tr.get('item')}{price}"
        return f"From {ev.get('from')}: {ev.get('text')}"
    if t == "whisper_out":
        return f"To {ev.get('to')}: {ev.get('text')}"
    if t == "afk_changed":
        return "AFK on" if ev.get("on") else "AFK off"
    if t == "dnd_changed":
        return "DND on" if ev.get("on") else "DND off"
    if t == "player_joined_area":
        return f"{ev.get('character')} joined"
    if t == "player_left_area":
        return f"{ev.get('character')} left"
    if t == "trade_accepted":
        return "Trade accepted"
    if t == "session_connect":
        return "Connected to an instance"
    if t == "tailer_started":
        return "Reading Client.txt"
    if t == "tailer_reset":
        return f"Client.txt {ev.get('reason')}"
    return t or "event"


class SessionState:
    def __init__(self, character=None, clock=time.time):
        self._lock = threading.Lock()
        self._clock = clock
        self.version = 0
        self.session_started_at = clock()
        # "" (the shipped config default) means "learn it from the log".
        self.character = character or None
        self.character_fixed = bool(character)
        self.char_class = None
        self.level = None
        self.zone = None
        self.area_id = None
        self.area_level = None
        self.zone_entered_at = None
        self.in_hideout = False
        self.deaths = 0
        self.level_ups = 0
        self.afk = False
        self.dnd = False
        self.events_seen = 0
        self.recent_whispers = collections.deque(maxlen=RECENT_WHISPERS)
        self.recent_events = collections.deque(maxlen=RECENT_EVENTS)
        self.trade_requests = collections.deque(maxlen=TRADE_REQUESTS)
        self.overlay_layout = None
        self._trade_ids = 0
        self.tailer = {"consented": False, "reading": False, "path": None,
                       "last_reset": None}

    # -- updates
    def set_tailer(self, **fields):
        with self._lock:
            changed = any(self.tailer.get(k) != v for k, v in fields.items())
            self.tailer.update(fields)
            if changed:
                self.version += 1
            return changed

    def set_overlay_layout(self, layout):
        with self._lock:
            if layout != self.overlay_layout:
                self.overlay_layout = dict(layout)
                self.version += 1

    def dismiss_trade(self, trade_id=None):
        """Drop one open trade card by id, or all of them (trade_id None).
        Returns how many were dismissed. Dashboard only: nothing goes to the
        game."""
        with self._lock:
            before = len(self.trade_requests)
            if trade_id is None:
                self.trade_requests.clear()
            else:
                kept = [r for r in self.trade_requests if r["id"] != trade_id]
                self.trade_requests.clear()
                self.trade_requests.extend(kept)
            n = before - len(self.trade_requests)
            if n:
                self.version += 1
            return n

    def _trade_row(self, ev, now):
        self._trade_ids += 1
        row = {"id": self._trade_ids, "at": now, "from": ev.get("from")}
        trade = ev.get("trade") or {}
        for k in TRADE_FIELDS:
            if k in trade:
                row[k] = trade[k]
        return row

    def _is_me(self, name):
        return self.character is None or name == self.character

    def apply(self, ev):
        """Fold one event in. Returns True when the snapshot changed."""
        t = ev.get("type")
        now = ev.get("recv_ts") or self._clock()
        with self._lock:
            self.events_seen += 1
            changed = False
            listed = t in LISTED
            if t == "scene_changed":
                # Null and transient scenes (LIVE-1) keep the zone and its
                # timer and are not listed; only a real zone change is.
                listed = False
                if (not ev.get("is_null") and not ev.get("is_transient")
                        and ev.get("scene") != self.zone):
                    self.zone = ev.get("scene")
                    self.in_hideout = bool(ev.get("is_hideout"))
                    self.zone_entered_at = now
                    listed = True
                    changed = True
            elif t == "area_generated":
                self.area_id = ev.get("area_id")
                self.area_level = ev.get("area_level")
                changed = True
            elif t == "area_entered":
                if ev.get("name") != self.zone:
                    self.zone = ev.get("name")
                    self.in_hideout = "hideout" in (self.zone or "").lower()
                    self.zone_entered_at = now
                    changed = True
            elif t == "level_up":
                # The first level-up names the character unless one was
                # configured; other players' level-ups are listed, not counted.
                if self.character is None:
                    self.character = ev.get("character")
                if ev.get("character") == self.character:
                    self.char_class = ev.get("class")
                    self.level = ev.get("level")
                    self.level_ups += 1
                    changed = True
            elif t == "death":
                if self._is_me(ev.get("character")):
                    self.deaths += 1
                    changed = True
            elif t in ("whisper_in", "whisper_out"):
                self.recent_whispers.append(self._row(ev, now))
                if t == "whisper_in" and ev.get("trade"):
                    self.trade_requests.append(self._trade_row(ev, now))
                changed = True
            elif t == "afk_changed":
                self.afk = bool(ev.get("on"))
                changed = True
            elif t == "dnd_changed":
                self.dnd = bool(ev.get("on"))
                changed = True
            elif t == "tailer_started":
                self.tailer["reading"] = True
                self.tailer["path"] = ev.get("path")
                changed = True
            elif t == "tailer_reset":
                self.tailer["last_reset"] = ev.get("reason")
                if ev.get("reason") == "missing":
                    self.tailer["reading"] = False
                changed = True
            if listed:
                self.recent_events.append(self._row(ev, now))
                changed = True
            if changed:
                self.version += 1
            return changed

    @staticmethod
    def _row(ev, now):
        return {"seq": ev.get("seq"), "type": ev.get("type"), "at": now,
                "text": summarize(ev), "trade": bool(ev.get("trade")),
                "whisper": ev.get("type") in ("whisper_in", "whisper_out")}

    # -- read
    def snapshot(self):
        with self._lock:
            now = self._clock()
            return {
                "version": self.version,
                "now": now,
                "session_started_at": self.session_started_at,
                "session_s": max(0.0, now - self.session_started_at),
                "character": self.character,
                "class": self.char_class,
                "level": self.level,
                "zone": self.zone,
                "area_id": self.area_id,
                "area_level": self.area_level,
                "zone_entered_at": self.zone_entered_at,
                "zone_s": (max(0.0, now - self.zone_entered_at)
                           if self.zone_entered_at else None),
                "in_hideout": self.in_hideout,
                "deaths": self.deaths,
                "level_ups": self.level_ups,
                "afk": self.afk,
                "dnd": self.dnd,
                "events_seen": self.events_seen,
                "recent_whispers": list(self.recent_whispers),
                "recent_events": list(self.recent_events),
                "trade_requests": [dict(r) for r in self.trade_requests],
                "overlay_layout": dict(self.overlay_layout) if self.overlay_layout else None,
                "tailer": dict(self.tailer),
            }
