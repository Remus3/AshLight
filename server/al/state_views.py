"""SessionState's published views as ViewsMixin (TEST-STATE-MIXIN-C, F-192,
research 0047 R5 (2); the pattern is the loop's mixins, tools/loop_inbox.py
and tools/loop_merge.py).

TEST-STATE-PUBLISH: the views the core only stores (publish() and its
wrappers); UTIL-MAP-LADDER: the all-sessions ladder and this session's
rows; HUD-ACT / ZONE-GUIDE (decision 0043): the zone level table, the
guide, the area graph and the visited zones; PLAY-F-186A (decision 0074):
the player notes book; NEWBIE-HINTS (ruling L): the hint store. The methods
moved verbatim from state.py: the lock is SessionState's one lock, the event
dispatcher (apply / _apply_locked) stays in state.py and calls the helpers
here. state.py re-exports every module name here, so state.<name> stays.
Stdlib only.
"""

from . import acts as acts_mod
from . import hints as hints_mod
from . import zoneguide as zoneguide_mod

# TEST-STATE-PUBLISH (research 0047 R5 (1)): views the core only stores
# and the snapshot carries as they are. These keys are always in the
# snapshot (None until published); publish() takes any other new key too.
PUBLISHED_KEYS = ("run_history", "price_watch", "diag")
# The snapshot keys snapshot() builds itself; publish() refuses them, so a
# published view never shadows one (tests/test_state_publish.py checks the
# list against a real snapshot).
BUILTIN_SNAPSHOT_KEYS = frozenset((
    "version", "now", "session_started_at", "session_s", "character",
    "character_pinned", "class", "level", "zone", "area_id", "area_level",
    "zone_entered_at", "zone_s", "in_hideout", "in_town", "deaths",
    "level_ups", "afk", "dnd", "events_seen", "recent_events",
    "trade_requests", "overlay_layout", "tailer", "game_idle", "eval",
    "price", "card", "overlay", "build", "build_alert", "upgrades", "acts",
    "maps", "underlevel", "zone_guide", "player_note", "campaign",
    "death_recap", "hint", "pace", "characters", "session_summary",
    "sources", "lang", "hotkeys", "update", "play"))


class ViewsMixin:
    """Mixed into state.SessionState. _init_views() runs from __init__,
    _view_views(now) from snapshot()."""

    def _init_views(self):
        # TEST-STATE-PUBLISH: the views the core only stores (publish())
        self._published = {k: None for k in PUBLISHED_KEYS}
        # HUD-ACT: the zone level table from the game-data cache.
        self.zone_table = {}
        # ZONE-GUIDE (decision 0043): the guide file, the snapshot area
        # graph and the zones each character entered (zoneguide.py).
        self.zone_guide = {}
        self.area_graph = {}
        self.visits = zoneguide_mod.VisitBook()
        # PLAY-F-186A (decision 0074): the player's own notes book
        # {character: {area id: {"text", "at"}}}, set by the core
        self.player_notes = {}
        # UTIL-MAP-LADDER: the all-sessions ladder the core publishes
        # (mapladder.py; None while run history is off).
        self.map_ladder_all = None
        # NEWBIE-HINTS (ruling L): first-hours hints; memory only until the
        # core gives the store file (use_hint_store).
        self.hints = hints_mod.Hints()

    def _view_views(self, now):
        """Caller holds the lock. The snapshot's published-view keys: the
        all-sessions map ladder, the zone guide, the player's note and the
        three core-published views."""
        return {
            "ladder_all": (dict(self.map_ladder_all)
                           if self.map_ladder_all else None),
            "zone_guide": self._zone_guide_view(),
            "player_note": self._player_note_view(),
            "run_history": self._published_view("run_history"),
            "price_watch": self._published_view("price_watch"),
            "diag": self._published_view("diag"),
        }

    def publish(self, key, view):
        """TEST-STATE-PUBLISH: store a view the core only publishes under
        `key`; snapshot() carries it as it is (a dict or list is copied, an
        empty view is None), so a new core-published view needs no other
        state.py edit. Bumps the version only on a change and returns True
        then. A key snapshot() builds itself (BUILTIN_SNAPSHOT_KEYS) or a
        key that is not a non-empty str is refused with ValueError."""
        if not isinstance(key, str) or not key or key in BUILTIN_SNAPSHOT_KEYS:
            raise ValueError("publish: refused key")
        if not view:
            value = None
        elif isinstance(view, dict):
            value = dict(view)
        elif isinstance(view, (list, tuple)):
            value = list(view)
        else:
            raise ValueError("publish: a view is a dict, a list or None")
        with self._lock:
            if key in self._published and value == self._published[key]:
                return False
            self._published[key] = value
            self.version += 1
            return True

    def _published_view(self, key):
        """A copy of one published view for the snapshot. Caller holds the
        lock."""
        v = self._published.get(key)
        if isinstance(v, dict):
            return dict(v)
        if isinstance(v, list):
            return list(v)
        return v

    # The published views keep their old attribute names for readers that
    # hold the lock already (overlayview reads run_history); no lock taken.
    @property
    def run_history(self):
        return self._published.get("run_history")

    @property
    def price_watch(self):
        return self._published.get("price_watch")

    @property
    def diag(self):
        return self._published.get("diag")

    def set_run_history(self, view):
        """UTIL-RUN-HISTORY: the history view (core tick)."""
        return self.publish("run_history", view)

    def use_hint_store(self, path):
        """NEWBIE-HINTS: keep the hint store in `path` (core start)."""
        with self._lock:
            self.hints.use_file(path)

    def reset_hints(self):
        """NEWBIE-HINTS: the dashboard's "reset hints" click."""
        with self._lock:
            self.hints.reset()
            self.version += 1
            return hints_mod.RESET_TEXT

    def _hint(self, shown, now):
        """List a hint that just started in the event list. Caller holds
        the lock."""
        if shown is None:
            return False
        self.recent_events.append({"seq": None, "type": "hint", "at": now,
                                   "text": shown["text"], "trade": False,
                                   "whisper": False})
        return True

    def map_ladder_rows(self):
        """UTIL-MAP-LADDER: (character, this session's map rows) for the
        core's saved ladder. The map runs are per character (CHAR_FIELDS,
        RUN-P8-8-CHARMIX), so the rows are the current character's only;
        each carries its "character" (mapladder takes that character's
        rows only)."""
        with self._lock:
            rows = self.maps.ladder_rows(self._clock())
            for r in rows:
                r["character"] = self.character
            return self.character, rows

    def set_map_ladder(self, view):
        """UTIL-MAP-LADDER: the all-sessions ladder view, or None."""
        with self._lock:
            if view != self.map_ladder_all:
                self.map_ladder_all = dict(view) if view else None
                self.version += 1

    def set_price_watch(self, view):
        """UTIL-PRICE-WATCH: the price watch view (core tick)."""
        return self.publish("price_watch", view)

    def set_zone_table(self, table):
        """HUD-ACT: the act / zone level table (acts.load_table())."""
        with self._lock:
            table = table if isinstance(table, dict) else {}
            # HOT-RELOAD: polled every tick; the same object is no change
            if table is not self.zone_table and table != self.zone_table:
                self.zone_table = table
                self.lang.set_table(table)
                self.version += 1

    def set_zone_guide(self, guide=False, graph=False):
        """ZONE-GUIDE: the guide document and / or the snapshot area graph
        (an argument left out keeps its value). Bumps only on a change."""
        with self._lock:
            changed = False
            if guide is not False:
                guide = guide if isinstance(guide, dict) else {}
                if guide is not self.zone_guide and guide != self.zone_guide:
                    self.zone_guide, changed = guide, True
            if graph is not False:
                graph = graph if isinstance(graph, dict) else {}
                if graph is not self.area_graph and graph != self.area_graph:
                    self.area_graph, changed = graph, True
            if changed:
                self.version += 1
            return changed

    def set_player_notes(self, book):
        """PLAY-F-186A: the player notes book (playernotes.PlayerNotes.get);
        bumps only on a change."""
        book = book if isinstance(book, dict) else {}
        with self._lock:
            if book is self.player_notes or book == self.player_notes:
                return False
            self.player_notes = book
            self.version += 1
            return True

    def _player_note_view(self):
        """PLAY-F-186A: this character's note for the zone the player is
        in, {"area_id", "text", "at"}, or None. Caller holds the lock."""
        per = self.player_notes.get(self.character) if self.character else None
        e = per.get(self.area_id) if isinstance(per, dict) and self.area_id else None
        if not isinstance(e, dict) or not isinstance(e.get("text"), str):
            return None
        return {"area_id": self.area_id, "text": e["text"], "at": e.get("at")}

    def visits_doc(self):
        """ZONE-GUIDE: (version, file document) of the visited zones."""
        with self._lock:
            return self.visits.version, self.visits.to_doc()

    def load_visits(self, doc):
        """ZONE-GUIDE: merge the saved visited zones in (core start)."""
        with self._lock:
            if self.visits.load_doc(doc):
                self.version += 1
                return True
            return False

    def clear_visits(self):
        with self._lock:
            self.visits.clear()
            self.version += 1

    def set_diag(self, view):
        """DIAG-SELF: the self-check view (core tick_diag); bumps only on
        a change."""
        return self.publish("diag", view)

    def _zone_guide_view(self):
        """ZONE-GUIDE: the guide for the zone the player is in. Caller
        holds the lock."""
        zone_level = None
        info = acts_mod.act_of(self.area_id)
        if info is not None and self.zone:
            row = next((r for r in self.zone_table.get(info["key"], ())
                        if r["id"] == self.area_id or r["name"] == self.zone), None)
            zone_level = row["level"] if row else None
        visits = (self.visits.by_name.get(self.character or "")
                  if self.visits.by_name else None)
        return zoneguide_mod.view(self.zone_guide, self.area_graph, self.area_id,
                                  self.zone, self.in_hideout, self.level,
                                  self.area_level, visits, zone_level,
                                  self.underlevel_gap)
