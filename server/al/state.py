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
# DS-TRADE-EXPIRE (design 0001 N5): a card clears by itself this long after
# it arrived; the dashboard states the rule and Dismiss stays.
TRADE_EXPIRE_S = 600
TRADE_FIELDS = ("kind", "item", "price_amount", "price_currency", "want_amount",
                "league", "stash_tab", "left", "top")

# Event types shown in the dashboard's recent list.
LISTED = {"scene_changed", "area_entered", "level_up", "death", "whisper_in",
          "whisper_out", "afk_changed", "dnd_changed", "player_joined_area",
          "player_left_area", "trade_accepted", "session_connect",
          "tailer_started", "tailer_reset"}


FALLBACK_TEXT = "Something happened in the log"
UNKNOWN_CHARACTER = "Unknown character"
UNKNOWN_PLAYER = "Unknown player"
UNKNOWN_ZONE = "an unknown zone"

# tailer_reset reasons, as plain sentences (design 0001 section 9).
RESET_TEXT = {
    "missing": "Client.txt is missing - waiting for the game",
    "replaced": "Client.txt was replaced - reading the new file",
    "truncated": "Client.txt was cleared - reading from the start",
}


def _text(value, default):
    """A field as display text; missing or empty reads as the default."""
    if value is None:
        return default
    value = str(value)
    return value if value.strip() else default


def _amount(value):
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


def _trade_text(sender, tr):
    """<from> wants <item> - <price> (design 0001 section 9)."""
    item = _text(tr.get("item"), "an item")
    if tr.get("kind") == "exchange":
        if tr.get("want_amount") is not None:
            item = f"{_amount(tr['want_amount'])} {item}"
        price = "no price set"
        if tr.get("price_amount") is not None:
            price = " ".join(p for p in ("for", _amount(tr["price_amount"]),
                                         _text(tr.get("price_currency"), "")) if p)
    elif tr.get("price_amount") is not None:
        price = " ".join(p for p in (_amount(tr["price_amount"]),
                                     _text(tr.get("price_currency"), "")) if p)
    else:
        price = "no price set"
    return f"{sender} wants {item} - {price}"


def summarize(ev):
    """One natural sentence for an event (design 0001 section 9). This is
    the only place event wording is made; every template has an exact-output
    test in tests/test_summarize.py. Missing fields read honestly, never
    "None", and internal ids never show."""
    t = ev.get("type")
    if t in ("scene_changed", "area_entered"):
        zone = _text(ev.get("scene") if t == "scene_changed" else ev.get("name"),
                     UNKNOWN_ZONE)
        tag = " (hideout)" if t == "scene_changed" and ev.get("is_hideout") else ""
        return f"Entered {zone}{tag}"
    if t == "area_generated":
        return f"Area level {_text(ev.get('area_level'), 'unknown')}"
    if t == "level_up":
        who = _text(ev.get("character"), UNKNOWN_CHARACTER)
        if ev.get("level") is None:
            return f"{who} reached a new level (level unknown)"
        return f"{who} reached level {ev['level']}"
    if t == "death":
        who = _text(ev.get("character"), UNKNOWN_CHARACTER)
        return f"{who} died" + (" (self-inflicted)" if ev.get("suicide") else "")
    if t == "whisper_in":
        sender = _text(ev.get("from"), UNKNOWN_PLAYER)
        tr = ev.get("trade")
        if isinstance(tr, dict):
            return _trade_text(sender, tr)
        body = _text(ev.get("text"), "")
        return f'{sender}: "{body}"' if body else f"{sender} sent an empty whisper"
    if t == "whisper_out":
        to = _text(ev.get("to"), "unknown player")
        body = _text(ev.get("text"), "")
        return f'To {to}: "{body}"' if body else f"Sent an empty whisper to {to}"
    if t == "afk_changed":
        return "You're AFK" if ev.get("on") else "You're back"
    if t == "dnd_changed":
        return "Do not disturb on" if ev.get("on") else "Do not disturb off"
    if t == "player_joined_area":
        return f"{_text(ev.get('character'), UNKNOWN_CHARACTER)} joined the area"
    if t == "player_left_area":
        return f"{_text(ev.get('character'), UNKNOWN_CHARACTER)} left the area"
    if t == "trade_accepted":
        return "Trade accepted"
    if t == "trade_cancelled":
        return "Trade cancelled"
    if t == "session_connect":
        return "Connected to a game server"
    if t == "tailer_started":
        return "Reading Client.txt"
    if t == "tailer_reset":
        return RESET_TEXT.get(ev.get("reason"), "Client.txt was reset")
    return FALLBACK_TEXT


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

    def _expire_trades(self, now):
        """Drop trade cards older than TRADE_EXPIRE_S. Caller holds the
        lock. Bumps the version when one goes, so the change is pushed."""
        kept = [r for r in self.trade_requests if now - r["at"] < TRADE_EXPIRE_S]
        if len(kept) != len(self.trade_requests):
            self.trade_requests.clear()
            self.trade_requests.extend(kept)
            self.version += 1

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
                    self._expire_trades(now)
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

    _RESTORE = {"zone": "zone", "in_hideout": "in_hideout", "area_id": "area_id",
                "area_level": "area_level", "zone_entered_at": "zone_entered_at",
                "class": "char_class", "level": "level", "deaths": "deaths",
                "level_ups": "level_ups", "afk": "afk", "dnd": "dnd"}

    def restore(self, fields):
        """LIVE-RESUME: set state fields recovered from the end of Client.txt
        (server/al/resume.py). Nothing is listed. A configured character is
        kept; another character's level, class and counts are ignored."""
        with self._lock:
            name = fields.get("character")
            other = bool(name) and self.character_fixed and name != self.character
            if name and not self.character_fixed:
                self.character = name
            for key, attr in self._RESTORE.items():
                if other and key in ("class", "level", "deaths", "level_ups"):
                    continue
                if key in fields:
                    setattr(self, attr, fields[key])
            self.version += 1
            return True

    @staticmethod
    def _row(ev, now):
        return {"seq": ev.get("seq"), "type": ev.get("type"), "at": now,
                "text": summarize(ev), "trade": bool(ev.get("trade")),
                "whisper": ev.get("type") in ("whisper_in", "whisper_out")}

    # -- read
    def snapshot(self):
        with self._lock:
            now = self._clock()
            self._expire_trades(now)
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
