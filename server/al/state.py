"""Derived session state, built only from bus events.

Times are wall-clock receipt times (time.time()); the line's own timestamp is
local time without a zone, so it is kept for display only. Every buffer is
bounded.
"""

import collections
import copy
import threading
import time

from . import acts as acts_mod
from . import campaign as campaign_mod
from . import hints as hints_mod
from . import langguard as langguard_mod
from . import overlayview as overlayview_mod
from . import parser as parser_mod
from . import pace as pace_mod
from . import playview as playview_mod
from . import runs as runs_mod
from . import summary as summary_mod
from . import underlevel as underlevel_mod
from . import zoneguide as zoneguide_mod
from .state_cards import CardsMixin
from .state_trades import (  # noqa: F401 - re-exported, state.<name> stays
    TRADE_EXPIRE_S, TRADE_FIELDS, TRADE_REQUESTS, TradesMixin)
from .text.buildlive import (  # noqa: F401 - re-exported, state.<name> stays
    ALERT_ROUTES, _a_class, _fit, _upgrade_delta, build_alert_text, upgrade_notice_text,
    upgrades_text)
from .text.common import (  # noqa: F401 - re-exported, state.<name> stays
    CARD_LINE, _amount, _dict, _dicts, _is_time, _key, _num_text, _points,
    _short_list, _signed, _signed_points, _text)
from .text.events import (  # noqa: F401 - re-exported, state.<name> stays
    FALLBACK_TEXT, RESET_READ_TEXT, RESET_TEXT, UNKNOWN_CHARACTER, UNKNOWN_PLAYER,
    UNKNOWN_ZONE, _trade_text, _trade_where, summarize, trade_card_text)
from .text.itemcheck import (  # noqa: F401 - re-exported, state.<name> stays
    CALC_CACHED_TEXT, CALC_NOTICE_TEXT, EVAL_ERROR_TEXT, VERDICT_WORD, WEAPON_TYPE_HEAD,
    WEAPON_TYPE_LINE, _calc_text, _comp_calc, _compare_sentence, _equipped_name,
    _eval_lines, _has_pob, _pct_text, _stat_rows, _swap_where, _weapon_skill,
    _weapon_type_calc, eval_card_text, stat_delta_text)
from .text.overlaycard import (  # noqa: F401 - re-exported, state.<name> stays
    EVAL_CARD_S, PRICE_CARD_S, SAME_PRESS_S, _fresh, overlay_card, price_until)
from .text.price import (  # noqa: F401 - re-exported, state.<name> stays
    EMPTY_CLIPBOARD, EMPTY_CLIPBOARD_TEXT, LEAGUE_NEW_S, PRICE_AGED_S, PRICE_LISTINGS,
    PRICE_OLD_S, PRICE_STATUSES, PRICE_TEXT, _age_s, _listing_text, _ninja_amount,
    _price_amount, ninja_text, price_card_text)
from .text.waystone import (  # noqa: F401 - re-exported, state.<name> stays
    WAYSTONE_LISTED, _reward_pct, _waystone_risk_text, waystone_rewards_text,
    waystone_text)

RECENT_EVENTS = 30

# Event types shown in the dashboard's recent list. UX-COPY: not
# session_connect - the game logs one before every zone change, so
# "Connected to a game server" doubled every "Entered <zone>" row and
# pushed deaths and whispers out of the 30-row list sooner.
LISTED = {"scene_changed", "area_entered", "level_up", "death", "whisper_in",
          "whisper_out", "afk_changed", "dnd_changed", "player_joined_area",
          "player_left_area", "trade_accepted", "tailer_started", "tailer_reset",
          "tailer_unreadable", "tailer_readable", "tailer_restarted"}


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
# RUN-ZONE-RESET (F-088): the per-zone fields. SessionState._enter_zone()
# is the one place they are reset (tests/test_bus_state.py lists them), and
# every reset moves the zone generation (_zone_gen) on, so a per-zone card
# or timer of the zone before never publishes.
ZONE_FIELDS = ("zone", "area_id", "area_level", "zone_entered_at", "in_hideout",
               "in_town", "_area_fresh", "_zone_cards")
ZONE_CARDS = 4  # zone cards kept per zone; the oldest drops
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


class SessionState(CardsMixin, TradesMixin):
    """TEST-STATE-MIXIN-A (F-192): the press cards (state_cards.CardsMixin)
    and the trade cards (state_trades.TradesMixin) live in per-concern
    mixins, each with its _init_<x>() called from __init__ and its
    _view_<x>(now) called from snapshot(); the lock and the event
    dispatcher (apply / _apply_locked) stay here."""

    def __init__(self, character=None, clock=time.time):
        self._lock = threading.Lock()
        self._clock = clock
        # TEST-FULLSTACK-SSE-IDLE: on_change() runs (under the lock) on every
        # version bump outside apply(); the core points it at the bus wake so
        # a change with no log line (idle, the summary card, a trade card
        # expiring, the calc or price book status) reaches SSE clients at
        # once instead of on the next heartbeat. apply() bumps are pushed
        # with their event, so they do not wake.
        self.on_change = None
        self._applying = False
        self._version = 0
        # The calc and price book status (core tick_sources); no request.
        self.sources = {"calc_on": False, "calc_running": False,
                        "rates_checked_at": None, "book_checked_at": None}
        # REL-UPDATE-WIRE (decision 0065): the release check view the core
        # publishes (updates.UpdateClient.view); None until its first tick.
        self.update_view = None
        # TEST-STATE-PUBLISH: the views the core only stores (publish())
        self._published = {k: None for k in PUBLISHED_KEYS}
        self.session_started_at = clock()
        # The pace counts only level-ups seen live, so its hourly base stays
        # the core start even when LIVE-RESUME moves the Session tile back
        # to the log opening (UX-NEW-CARDS).
        self.pace_started_at = self.session_started_at
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
        # OVL-HIDEOUT-AREA: town flag from the area id; _area_fresh is True
        # while the last area generation line still waits for its scene
        self.in_town = False
        self._area_fresh = False
        # RUN-ZONE-RESET: the zone generation and the cards scheduled for
        # the zone of that generation (schedule_zone_card / zone_cards)
        self._zone_gen = 0
        self._zone_cards = collections.deque(maxlen=ZONE_CARDS)
        self.deaths = 0
        self.level_ups = 0
        self.afk = False
        self.dnd = False
        self.events_seen = 0
        self.recent_events = collections.deque(maxlen=RECENT_EVENTS)
        self._init_trades()
        self.overlay_layout = None
        # OVL-CARD-SLOT (F-118): the one owner of the overlay card slot
        self.overlay = overlayview_mod.OverlayView()
        self._init_cards()
        # HUD-ACT: per-act splits; zone level table from the game-data cache.
        self.acts = acts_mod.ActSplits()
        self.zone_table = {}
        # ZONE-GUIDE (decision 0043): the guide file, the snapshot area
        # graph and the zones each character entered (zoneguide.py).
        self.zone_guide = {}
        self.area_graph = {}
        self.visits = zoneguide_mod.VisitBook()
        # PLAY-F-186A (decision 0074): the player's own notes book
        # {character: {area id: {"text", "at"}}}, set by the core
        self.player_notes = {}
        # UTIL-MAPS / UTIL-DEATHS: map runs and the death recap (runs.py).
        self.maps = runs_mod.MapRuns()
        self.death_log = runs_mod.DeathLog()
        # UTIL-PACE: levelling pace from the player's level-ups (pace.py).
        self.pace = pace_mod.Pace()
        # UTIL-SESSION-SUMMARY: the open play stretch and its last card.
        self.stretch = summary_mod.Tracker()
        self.session_summary = None
        self._summary_ids = 0
        # TEST-LIVE-EXIT (decision 0029): "idle" = no Client.txt line for
        # summary.IDLE_S while consented (the game may be closed; a killed
        # game writes no line). Log staleness only, no process check.
        self.tailer = {"consented": False, "reading": False, "path": None,
                       "last_reset": None, "idle": False,
                       "last_line_at": None, "unreadable": False}
        # RUN-TAIL-HEAL-CORE: the file is gone (a "missing" reset and no
        # start or other reset since); with "unreadable" it decides the
        # reading flag on the tailer's later status events.
        self._tail_missing = False
        self._idle_paused_map = False  # AREA-AUDIT P3-4
        # UTIL-UNDERLEVEL: the gap threshold ("underlevel_gap" setting).
        self.underlevel_gap = underlevel_mod.DEFAULT_GAP
        # UTIL-CAMPAIGN-CHECKS (ruling H): the loaded build's facts, the
        # snapshot flask table and the boots level setting (campaign.py).
        self.campaign_facts = None
        self.flask_table = {}
        self.boots_level = campaign_mod.DEFAULT_BOOTS_LEVEL
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
        # UTIL-MAP-LADDER: the all-sessions ladder the core publishes
        # (mapladder.py; None while run history is off).
        self.map_ladder_all = None
        # NEWBIE-HINTS (ruling L): first-hours hints; memory only until the
        # core gives the store file (use_hint_store).
        self.hints = hints_mod.Hints()
        # LANG-GUARD (ruling K, decision 0040): the in-memory language
        # verdict from the log; DIAG-SELF (ruling J): the core's checks view.
        self.lang = langguard_mod.LangGuard()
        # HOTKEYS-LIVE (decision 0058, OVL-KEYS-CORE): the effective keys
        # view the core publishes (hotkeys.view), None until its first tick.
        self.hotkeys = None

    @property
    def version(self):
        return self._version

    @version.setter
    def version(self, value):
        self._version = value
        if not self._applying and self.on_change is not None:
            try:
                self.on_change()
            except Exception:  # noqa: BLE001 - a wake never breaks a state change
                pass

    # -- updates
    def set_sources(self, **fields):
        """TEST-FULLSTACK-SSE-IDLE: the calc on / running and the poe.ninja
        rates / price book check times, from the core's loop tick. Bumps
        the version (so SSE pushes it) only when one changed."""
        with self._lock:
            fields = {k: v for k, v in fields.items() if k in self.sources}
            changed = any(self.sources.get(k) != v for k, v in fields.items())
            if changed:
                self.sources.update(fields)
                self.version += 1
            return changed

    def set_update(self, view):
        """REL-UPDATE-WIRE (decision 0065): the release check view from the
        core (installed, latest, notes, releases_url, checked_at,
        ack_needed, ...), published as the snapshot's 'update' block. It
        is never an event and carries no card text. Bumps the version only
        when it changed; returns whether it did."""
        view = copy.deepcopy(view) if isinstance(view, dict) else None
        with self._lock:
            if view == self.update_view:
                return False
            self.update_view = view
            self.version += 1
            return True

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

    @property
    def card_s(self):
        """OVL-TD18-CARD-TIME (TD-18): how long the press card shows, in
        seconds: the overlay layout's card_s, 20 without one. OverlayView
        passes it to overlay_card()."""
        from . import layout as layout_mod  # local: keeps the import block as is
        return layout_mod.card_seconds(self.overlay_layout)

    def _card_time(self, default):
        """The snapshot's card time: EVAL_CARD_S / PRICE_CARD_S (`default`)
        while the layout keeps the default card time, else its card_s."""
        from . import layout as layout_mod
        n = self.card_s
        return default if n == layout_mod.CARD_S[0] else n

    def now(self):
        """The state clock (server time, s); PRICE-1-WIRE stamps one press
        with it so the item check and the price check share `at`."""
        return self._clock()

    def set_overlay_sample(self):
        """OVL-CARD-SLOT: the Settings button's 10 s sample card. Display
        state only: no event, eval, price or run history entry."""
        with self._lock:
            now = self._clock()
            self.overlay.set_sample(now)
            self.version += 1
            return self.overlay.card(self, now)

    def overlay_doc(self, failed=False):
        """OVL-CARD-SLOT: the overlay view store document to save, clearing
        its dirty flag; failed=True marks it unsaved again (a failed write)."""
        with self._lock:
            if failed:
                self.overlay.dirty = True
                return None
            self.overlay.dirty = False
            return self.overlay.to_doc()

    def set_campaign(self, facts=False, flasks=False, boots_level=False):
        """UTIL-CAMPAIGN-CHECKS: any of the build facts
        (campaign.build_facts()), the flask table (campaign.load_flasks())
        and the boots level setting; an argument left out keeps its value.
        Bumps the version only on a change; returns whether it changed."""
        with self._lock:
            new = {"campaign_facts": self.campaign_facts, "flask_table": self.flask_table,
                   "boots_level": self.boots_level}
            if facts is not False:
                new["campaign_facts"] = dict(facts) if isinstance(facts, dict) else None
            if flasks is not False:
                new["flask_table"] = flasks if isinstance(flasks, dict) else {}
            if boots_level is not False:
                new["boots_level"] = campaign_mod.boots_level_setting(boots_level)
            if all(getattr(self, k) == v for k, v in new.items()):
                return False
            for k, v in new.items():
                setattr(self, k, v)
            self.version += 1
            return True

    def set_underlevel_gap(self, value):
        """UTIL-UNDERLEVEL: the threshold from the local config (core
        tick). Bumps the version only when it changed."""
        value = underlevel_mod.gap_setting(value)
        with self._lock:
            if value == self.underlevel_gap:
                return False
            self.underlevel_gap = value
            self.version += 1
            return True

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

    def _place_now(self, scene_word):
        """OVL-HIDEOUT-AREA (F-118): (in_hideout, in_town) for the zone a
        real scene line names. The area id of the generation line that
        came before it decides, the same in every client language; the
        English scene word is only the hideout fallback when no generation
        line was seen for this zone (then in_town is False). Caller holds
        the lock."""
        if self._area_fresh and isinstance(self.area_id, str) and self.area_id:
            return (parser_mod.is_hideout_area(self.area_id),
                    parser_mod.is_town_area(self.area_id))
        return bool(scene_word), False

    # -- RUN-ZONE-RESET (F-088): the one per-zone reset
    def _enter_zone(self, now, gen=None, scene=None):
        """Reset the per-zone fields (ZONE_FIELDS) for a zone entry. Caller
        holds the lock.
        - gen=(area_id, area_level): an area generation line, a new area
          instance; its scene line follows and names it.
        - scene=(name, hideout_word): a real scene or area-entered line;
          the flags come from _place_now. A scene with no fresh generation
          line before it is a zone entry of its own; one naming the zone
          the player is in (a new area under the same scene name) sets the
          flags only.
        - neither: no zone (a game start; the player is at the login
          screen).
        Every entry moves the zone generation on and drops the zone cards,
        so a generation line and its scene line are one entry. Returns True
        when a field changed."""
        if gen is None and scene is None:
            self.zone = self.area_id = self.area_level = None
            self.zone_entered_at = None
            self.in_hideout = self.in_town = self._area_fresh = False
            self._next_zone_gen()
            return True
        if gen is not None:
            self.area_id, self.area_level = gen
            self._area_fresh = True
            self._next_zone_gen()
        if scene is None:
            return True
        name, word = scene
        place = self._place_now(word)
        paired, self._area_fresh = self._area_fresh, False
        if name == self.zone:
            # its generation line, if any, moved the generation on
            if place == (self.in_hideout, self.in_town):
                return gen is not None
            self.in_hideout, self.in_town = place
            return True
        if not paired:
            self._next_zone_gen()
        self.in_hideout, self.in_town = place
        self.zone = name
        self.zone_entered_at = now
        self.maps.on_scene(self.zone, now, self.in_hideout)
        return True

    def _next_zone_gen(self):
        """A new zone generation: the old zone's cards never publish.
        Caller holds the lock."""
        self._zone_gen += 1
        self._zone_cards = collections.deque(maxlen=ZONE_CARDS)

    @property
    def zone_gen(self):
        """The zone generation (RUN-ZONE-RESET): it moves on at every zone
        entry. A per-zone timer or card takes it when it starts and
        publishes only while it is unchanged."""
        with self._lock:
            return self._zone_gen

    def schedule_zone_card(self, card, at=None, gen=None):
        """RUN-ZONE-RESET: schedule a card for the zone the player is in;
        zone_cards() shows it from `at` (default now) while the player stays
        in that zone, and any zone entry drops it. `gen`: the zone_gen the
        producer took when it started (a slow producer); a card of an older
        zone is refused. Returns True when the card was kept."""
        with self._lock:
            if gen is not None and gen != self._zone_gen:
                return False
            at = self._clock() if at is None else at
            if not _is_time(at) or not isinstance(card, dict):
                return False
            self._zone_cards.append({"card": dict(card), "at": float(at),
                                     "gen": self._zone_gen})
            return True

    def zone_cards(self, now=None):
        """RUN-ZONE-RESET: the scheduled cards of the current zone that are
        due at `now` (default the state clock), oldest first. A card checks
        the zone generation before it publishes."""
        with self._lock:
            now = self._clock() if now is None else now
            return [dict(c["card"]) for c in self._zone_cards
                    if c["gen"] == self._zone_gen and c["at"] <= now]

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

    def checks_facts(self):
        """RUN-QUIET-FEED (F-093): the few state facts the Checks rows read
        (Core.diag_facts), without building a snapshot: the tailer flags,
        whether a character is known and its name (masked in the report,
        never shown), the language verdict, the price book / rates check
        times and whether zone levels are loaded. No event text."""
        with self._lock:
            src = self.sources
            return {"tailer": dict(self.tailer),
                    "character": self.character,
                    "lang": self.lang.verdict(),
                    "book_checked_at": src.get("book_checked_at"),
                    "rates_checked_at": src.get("rates_checked_at"),
                    "levels": bool(isinstance(self.zone_table, dict) and self.zone_table)}

    def set_hotkeys(self, view):
        """HOTKEYS-LIVE (OVL-KEYS-CORE): the effective keys view (core
        tick_diag and set_hotkey); bumps only on a change."""
        with self._lock:
            if view != self.hotkeys:
                self.hotkeys = copy.deepcopy(view) if view else None
                self.version += 1
                return True
            return False

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

    def apply(self, ev):
        """Fold one event in. Returns True when the snapshot changed."""
        t = ev.get("type")
        now = ev.get("recv_ts") or self._clock()
        with self._lock:
            self._applying = True
            try:
                return self._apply_locked(ev, t, now)
            finally:
                self._applying = False

    def _apply_locked(self, ev, t, now):
        """apply() under the lock (its bumps do not wake: see on_change)."""
        self.events_seen += 1
        changed = False
        listed = t in LISTED
        # LANG-GUARD: the language verdict from area loads and system lines
        if ev.get("source") != "tailer" and self.lang.feed(ev, now):
            changed = True
        # TEST-LIVE-EXIT: any line proves the log is alive again. The
        # tailer's own status events (source "tailer") are not log
        # lines (AREA-AUDIT P3-1): they neither refresh the last line
        # (which would overwrite the resume mtime seed) nor clear idle.
        if ev.get("source") != "tailer":
            self.tailer["last_line_at"] = now
            if self.tailer.get("idle"):
                self.tailer["idle"] = False
                changed = True
                # AREA-AUDIT P3-4: the map clock idle froze runs again
                # from this line while the player is still in that map
                # (a zone change below then decides as usual); a game
                # restart (log_opened) keeps it stopped.
                if self._idle_paused_map and t != "log_opened":
                    self.maps.on_scene(self.zone, now, self.in_hideout)
            self._idle_paused_map = False
        active = t in summary_mod.ACTIVITY
        if active:
            self.stretch.begin(self._counters())
        if t == "log_opened":
            # UTIL-SESSION-SUMMARY: a new game run; the last one closed
            changed = self._close_stretch("game_closed")
        if t == "scene_changed":
            # Null and transient scenes (LIVE-1) keep the zone and its
            # timer and are not listed; only a real zone change is.
            listed = False
            real = not ev.get("is_null") and not ev.get("is_transient")
            if real:
                listed = ev.get("scene") != self.zone
                if self._enter_zone(now, scene=(ev.get("scene"), ev.get("is_hideout"))):
                    changed = True
            # ZONE-GUIDE: the zone this character entered (quest tracker)
            if real and not self.in_hideout and ev.get("scene"):
                if self.visits.visit(self.character, self.area_id, ev.get("scene")):
                    changed = True
        elif t == "area_generated":
            self._enter_zone(now, gen=(ev.get("area_id"), ev.get("area_level")))
            self.acts.fold(self.area_id, now, self.level)
            if self.area_id == acts_mod.FIRST_AREA:
                self._first_gen_at = now
            self.maps.on_generated(self.area_id, now, self.area_level,
                                   ev.get("seed"))
            self._hint(self.hints.on_area(self.character, self.area_id,
                                          self.level, now), now)
            changed = True
        elif t == "area_entered":
            if ev.get("name") != self.zone:
                self._enter_zone(now, scene=(ev.get("name"), parser_mod.is_hideout(
                    ev.get("name") or "")))
                changed = True
        elif t == "log_opened":
            # TEST-LIVE-RESTART: a new game run. The player is at the
            # login screen, so the old run's zone, area, zone timer and
            # AFK / DND are void. Character, level and counts stay.
            if self.maps.pause(now):
                changed = True
            self._others.clear()
            self._start_window = True
            self._relog_window = False
            self._game_start_at = now
            self._party_since_start = False
            if (self.zone is not None or self.area_id is not None
                    or self.area_level is not None or self.in_hideout
                    or self.zone_entered_at is not None
                    or self.afk or self.dnd):
                changed = True
            self._enter_zone(now)  # no zone: the login screen
            self.afk = self.dnd = False
        elif t == "level_up":
            # The first level-up names the character unless one was
            # configured; other players' level-ups are listed, not counted.
            if self.character is None:
                if ev.get("character") not in self._others:
                    self.character = ev.get("character")
            elif self._may_switch(ev.get("character")):
                # UTIL-MULTICHAR: another of the player's characters
                self._switch(ev.get("character"), now)
            self._close_windows(ev.get("character"))
            if ev.get("character") == self.character:
                self._first_gen_at = None
                self.char_class = ev.get("class")
                self.level = ev.get("level")
                self.level_ups += 1
                self.pace.on_level(self.level, now)
                self.maps.on_level_up(now)  # UTIL-MAP-LADDER
                self._hint(self.hints.on_level(self.character, self.level, now), now)
                changed = True
        elif t == "death":
            if self._may_switch(ev.get("character")):
                self._switch(ev.get("character"), now)
            self._close_windows(ev.get("character"))
            if self._is_me(ev.get("character")):
                self._first_gen_at = None
                self.deaths += 1
                self.death_log.add(
                    at=now, zone=self.zone, area_level=self.area_level,
                    level=self.level,
                    zone_s=(max(0.0, now - self.zone_entered_at)
                            if self.zone_entered_at else None))
                self.maps.on_death(now)
                # UTIL-RUN-HISTORY: campaign deaths per zone of this run
                if self.acts.splits and not self.acts.finished and self.zone:
                    self._run_counter()[self.zone] += 1
                self._hint(self.hints.on_death(self.character, self.area_id,
                                               self.level, now), now)
                changed = True
        elif t in ("player_joined_area", "player_left_area"):
            self._note_other(ev.get("character"))
            self._party_since_start = True
        elif t == "char_select":
            # Decision 0038 amendment 2026-11-22: a relog through character
            # select (no log file opening marker). The names seen joining
            # or leaving this game run stay; zone, character and counts
            # are untouched until the next name line.
            self._relog_window = True
            self._party_since_start = False
            # RUN-P8-8-CHARMIX: maps opened from here on are the next
            # character's if the relog switches (_switch)
            self._game_start_at = now
        elif t in ("whisper_in", "whisper_out"):
            if t == "whisper_in" and ev.get("trade"):
                self._expire_trades(now)
                if not self._refresh_trade(ev, now):
                    self.trade_requests.append(self._trade_row(ev, now))
            changed = True
        elif t in ("trade_accepted", "trade_cancelled"):
            self._expire_trades(now)
            if self._close_trade(ev.get("name")):
                changed = True
        elif t == "afk_changed":
            self.afk = bool(ev.get("on"))
            changed = True
        elif t == "dnd_changed":
            self.dnd = bool(ev.get("on"))
            changed = True
        elif t == "tailer_started":
            self._tail_missing = False
            self.tailer["reading"] = not self.tailer.get("unreadable")
            self.tailer["path"] = ev.get("path")
            changed = True
        elif t == "tailer_reset":
            self.tailer["last_reset"] = ev.get("reason")
            self._tail_missing = ev.get("reason") == "missing"
            self.tailer["reading"] = self._tail_can_read()
            changed = True
        elif t == "tailer_unreadable":
            # RUN-TAIL-HEAL-CORE: the file exists but every open or read
            # failed for UNREADABLE_POLLS polls (a lock, rights, a mount)
            self.tailer["unreadable"] = True
            self.tailer["reading"] = False
            changed = True
        elif t == "tailer_readable":
            self.tailer["unreadable"] = False
            self.tailer["reading"] = self._tail_can_read()
            changed = True
        elif t == "tailer_restarted":
            # the core restarted a dead reader thread on its own offset
            self.tailer["reading"] = self._tail_can_read()
            changed = True
        if listed:
            self.recent_events.append(self._row(ev, now))
            changed = True
        if active:
            self.stretch.touch(now, self._counters())
        if self.overlay.on_event(ev, self, now):
            changed = True
        if changed:
            self.version += 1
        return changed

    # -- UTIL-SESSION-SUMMARY
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

    def _counters(self):
        return {"level": self.level, "level_ups": self.level_ups,
                "deaths": self.deaths, "maps": self.maps.count}

    def _close_stretch(self, reason, movers=None):
        """Close the open play stretch into the summary card. Caller holds
        the lock. True when a card was made."""
        card = self.stretch.close(reason, movers)
        if card is None:
            return False
        self._summary_ids += 1
        self.session_summary = dict(card, id=self._summary_ids)
        return True

    def session_end_due(self, now=None):
        """True when the open stretch has been idle for IDLE_S (cheap; the
        core reads the movers only then)."""
        with self._lock:
            return self.stretch.due(self._clock() if now is None else now)

    def check_session_end(self, now=None, movers=None):
        """From the core's main loop: close the stretch after IDLE_S with no
        game activity. Returns the new card, or None."""
        with self._lock:
            now = self._clock() if now is None else now
            if not self.stretch.due(now):
                return None
            if not self._close_stretch("idle", movers):
                return None
            self.version += 1
            return dict(self.session_summary)

    # -- TEST-LIVE-EXIT (decision 0029)
    def _idle_due(self, now):
        tl = self.tailer
        last = tl.get("last_line_at")
        return (bool(tl.get("consented")) and not tl.get("idle")
                and last is not None and now - last >= summary_mod.IDLE_S)

    def seed_last_line(self, at):
        """LIVE-RESUME: the resumed log's last write time (file mtime)
        stands in for the last line until a live one comes, so a game that
        closed before the core started turns idle too."""
        with self._lock:
            if self.tailer.get("last_line_at") is None and isinstance(at, (int, float)):
                self.tailer["last_line_at"] = float(at)

    def log_idle_due(self, now=None):
        """True when Client.txt has been quiet for IDLE_S while consented
        and the idle state is not set yet (cheap; the core reads the
        movers only then)."""
        with self._lock:
            return self._idle_due(self._clock() if now is None else now)

    def check_log_idle(self, now=None, movers=None):
        """From the core's main loop: after IDLE_S with no Client.txt line
        the game may be closed (a killed game writes nothing). Set the idle
        state, keep the zone, freeze the zone and map clocks at the last
        line and close the play stretch into the summary card. The next
        line clears it (apply). True when the state turned idle."""
        with self._lock:
            now = self._clock() if now is None else now
            if not self._idle_due(now):
                return False
            last = self.tailer["last_line_at"]
            self.tailer["idle"] = True
            self._idle_paused_map = self.maps.pause(last)
            if self.stretch.start is not None:
                self._close_stretch("idle", movers)
            self.version += 1
            return True

    def set_session_summary(self, card):
        """A saved card loaded at core start (shown until a new one)."""
        with self._lock:
            if isinstance(card, dict) and self.session_summary is None:
                self.session_summary = dict(card)
                self._summary_ids = max(self._summary_ids,
                                        card.get("id") if isinstance(card.get("id"), int) else 0)
                self.version += 1

    _RESTORE = {"zone": "zone", "in_hideout": "in_hideout", "area_id": "area_id",
                "area_level": "area_level", "zone_entered_at": "zone_entered_at",
                "class": "char_class", "level": "level", "deaths": "deaths",
                "level_ups": "level_ups", "afk": "afk", "dnd": "dnd",
                "session_started_at": "session_started_at"}

    def restore(self, fields):
        """LIVE-RESUME: set state fields recovered from the end of Client.txt
        (server/al/resume.py). Nothing is listed. A configured character is
        kept; another character's level, class and counts are ignored.
        Act splits are run-wide and are rebuilt for any character."""
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
            # OVL-HIDEOUT-AREA: the scanned area id (the run's newest
            # generation line) decides the flags like the live arms; the
            # scanned scene word is the hideout fallback.
            if "area_id" in fields or "in_hideout" in fields:
                self._area_fresh = True
                self.in_hideout, self.in_town = self._place_now(self.in_hideout)
                self._area_fresh = False
            # RUN-ZONE-RESET: the scanned zone is a new zone entry, so no
            # card of the zone before it publishes
            if any(k in fields for k in ("zone", "area_id", "area_level",
                                         "zone_entered_at", "in_hideout")):
                self._next_zone_gen()
            # HUD-ACT-RESUME: rebuild the act splits from the run's area
            # generations (decision 0023); none keeps the current splits.
            rebuilt = acts_mod.ActSplits()
            for a in fields.get("act_areas") or ():
                rebuilt.fold(a.get("area_id"), a.get("at"), a.get("level"))
            if rebuilt.splits:
                self.acts = rebuilt
            # UTIL-MAPS-RESUME: replay the run's map runs and death recap;
            # no run events keep the current ones.
            events = fields.get("run_events")
            if events and not self.character_fixed:
                # UTIL-MULTICHAR: the run's character by the live rule
                self._restore_chars(events,
                                    fields.get("session_started_at") is not None)
            if events:
                self.maps, self.death_log = runs_mod.replay(events,
                                                            self.character)
            # ZONE-GUIDE: the run's entered zones for the tracker
            if events:
                zoneguide_mod.replay(events, self.visits, self.character)
            # UTIL-RUN-HISTORY: this run's deaths per zone from the
            # replayed death recap (its rows are capped, like the card)
            start = self.acts.splits[0]["started_at"] if self.acts.splits else None
            self._run_start = start
            self.run_deaths = collections.Counter(
                r["zone"] for r in self.death_log.rows
                if start is not None and r.get("zone")
                and isinstance(r.get("at"), (int, float)) and r["at"] >= start)
            self.version += 1
            return True

    _REPLAY_TYPES = ("scene_changed", "area_entered", "area_generated", "death",
                     "level_up", "player_joined_area", "player_left_area",
                     "log_opened", "char_select")

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
        tmp = SessionState(clock=self._clock)
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

    def _tail_can_read(self):
        """RUN-TAIL-HEAL-CORE: the reading flag the tailer's status events
        leave: the file is there and readable."""
        return not self._tail_missing and not self.tailer.get("unreadable")

    @staticmethod
    def _row(ev, now):
        return {"seq": ev.get("seq"), "type": ev.get("type"), "at": now,
                "text": summarize(ev), "trade": bool(ev.get("trade")),
                "whisper": ev.get("type") in ("whisper_in", "whisper_out")}

    def _zone_until(self, now):
        if self.tailer.get("idle") and self.tailer.get("last_line_at") is not None:
            return self.tailer["last_line_at"]
        return now

    # -- read
    def snapshot(self):
        with self._lock:
            now = self._clock()
            self._expire_trades(now)
            # BUILD-LIVE (decision 0045): the stale-build alert, once; the
            # item check words carry its caveat (TC-VERDICT-CAVEAT, F-043)
            cards = self._view_cards(now)
            alert = cards["build_alert"]
            trades = self._view_trades(now)
            guide = self._zone_guide_view()
            snap = {
                "version": self.version,
                "now": now,
                "session_started_at": self.session_started_at,
                "session_s": max(0.0, now - self.session_started_at),
                "character": self.character,
                # RUN-CHARACTER-PIN: the picker's pin is pressed
                "character_pinned": self.character_fixed,
                "class": self.char_class,
                "level": self.level,
                "zone": self.zone,
                "area_id": self.area_id,
                "area_level": self.area_level,
                "zone_entered_at": self.zone_entered_at,
                # TEST-LIVE-EXIT: idle freezes the zone clock at the last line
                "zone_s": (max(0.0, self._zone_until(now) - self.zone_entered_at)
                           if self.zone_entered_at else None),
                "in_hideout": self.in_hideout,
                # OVL-HIDEOUT-AREA: a town by the area id (a hideout is
                # in_hideout, not in_town)
                "in_town": self.in_town,
                "deaths": self.deaths,
                "level_ups": self.level_ups,
                "afk": self.afk,
                "dnd": self.dnd,
                "events_seen": self.events_seen,
                "recent_events": list(self.recent_events),
                "trade_requests": trades["trade_requests"],
                "overlay_layout": dict(self.overlay_layout) if self.overlay_layout else None,
                "tailer": dict(self.tailer),
                # decision 0029 amendment (DESKTOP-CLIENT): the 0029 idle
                # "game may be closed" state as one boolean; the overlay
                # hides while it is true
                "game_idle": bool(self.tailer.get("consented") and self.tailer.get("idle")),
                "eval": cards["eval"],
                "price": cards["price"],
                # The one overlay card chosen at this moment (decision 0016),
                # by the card-slot holder order (OVL-CARD-SLOT)
                "card": self.overlay.card(self, now, alert),
                "overlay": self.overlay.view(now),
                "build": cards["build"],
                # BUILD-LIVE (decision 0045): stale build, upgrades now
                "build_alert": alert,
                "upgrades": cards["upgrades"],
                "acts": acts_mod.view(self.acts, self.zone_table, self.area_id,
                                      self.zone, now),
                "maps": dict(self.maps.view(now),
                             ladder_all=(dict(self.map_ladder_all)
                                         if self.map_ladder_all else None)),
                # UTIL-UNDERLEVEL (ruling B): log area level minus player level
                "underlevel": underlevel_mod.view(
                    self.level, self.area_level, self.area_id, self.zone,
                    self.in_hideout, self.zone_table, self.underlevel_gap),
                # ZONE-GUIDE (decision 0043): the live zone guide and tracker
                "zone_guide": guide,
                # PLAY-F-186A (decision 0074): the player's own note for this
                # zone and character, or None
                "player_note": self._player_note_view(),
                # UTIL-CAMPAIGN-CHECKS (ruling H, decision 0039); the boss
                # element comes from the guide entry (DATA-GUIDE-BOSS)
                "campaign": campaign_mod.view(self.level, self.area_id,
                                              self.campaign_facts, self.flask_table,
                                              self.boots_level,
                                              boss=(guide or {}).get("boss")),
                "death_recap": self.death_log.view(self.deaths),
                # NEWBIE-HINTS: the first-hours hint on show, or None
                "hint": self.hints.view(now),
                "pace": self.pace.view(now, self.pace_started_at),
                # UTIL-MULTICHAR: every character's numbers, current first
                "characters": self._characters_view(now),
                "session_summary": (dict(self.session_summary)
                                    if self.session_summary else None),
                "sources": dict(self.sources),
                # UTIL-RUN-HISTORY / UTIL-PRICE-WATCH (core-published views)
                "run_history": self._published_view("run_history"),
                "price_watch": self._published_view("price_watch"),
                # LANG-GUARD / DIAG-SELF (rulings K, J; decision 0040)
                "lang": self.lang.view(),
                "diag": self._published_view("diag"),
                # HOTKEYS-LIVE (decision 0058): the keys really bound
                "hotkeys": copy.deepcopy(self.hotkeys) if self.hotkeys else None,
                # REL-UPDATE-WIRE (decision 0065): the release check, no event text
                "update": copy.deepcopy(self.update_view) if self.update_view else None,
            }
            # TEST-STATE-PUBLISH: every other published view, as it is
            for key in self._published:
                if key not in snap:
                    snap[key] = self._published_view(key)
            # PLAY-TD-07A: the Play rows, composed and capped at the source
            snap["play"] = playview_mod.view(snap)
            return snap
