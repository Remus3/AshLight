"""Wiring: consent -> tailer -> parser -> bus -> state.

Decision 0003: the tailer never starts until the user's opt-in is recorded in
ops/runtime/consent.json. Revoking consent stops it.

Decision 0071 (RUN-LEDGER-CONSENT): the parse ledger has its own opt-in, the
"ledger" key of the same file, never implied by the Client.txt opt-in; it
can be given only while the Client.txt opt-in is on, and revoking either
one turns it off and deletes ops/runtime/logshapes.json.
"""

import datetime as _dt
import hashlib
import json
import logging
import os
import threading
import time
from pathlib import Path

from . import (VERSION, acl, acts, campaign, diag, layout, logfile, ninja, parser, paths, ports,
               price, pricebook, pricewatch, procs, resume, runhistory, settingsio, tradestats, underlevel,
               upgrade, zoneguide,
               webfetch)
from . import metrics  # RUN-METRICS-SITES (decision 0067): press counters
from . import hints, mapladder  # NEWBIE-HINTS, UTIL-MAP-LADDER
from . import exitrecord  # OBS-CRASH: last-exit.json, client-exit.json
from . import hotkeys  # HOTKEYS-LIVE (decision 0058, OVL-KEYS-CORE)
from . import hotreload  # HOT-RELOAD (decision 0042)
from . import jsonfile  # RUN-DURABLE-STORES (F-014): .bak, Saver
from . import plug  # RUN-SEAMS (decision 0056)
from . import diag_data, leagues  # DATA-DIAG-SEAM, DATA-LEAGUE-PICKER-API
from . import pricerefresh  # DATA-PRICE-REFRESH-CORE (F-036)
from . import summary as summary_mod
from .bus import EventBus
from .state import EMPTY_CLIPBOARD, SessionState
from .theorycraft import basetypes
from .theorycraft import calcwire, health, pobout, skillsplit
from .theorycraft import item as item_mod
from .theorycraft import live as tc_live
from .theorycraft import press as tc_press
from .theorycraft import shareurl
from .theorycraft import store as build_store
from .theorycraft import treedata
from .theorycraft import weights as weights_mod
from .theorycraft import worngear


def _utc_now():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_private(path, text, backup=False):
    """Write text (ASCII, LF) through the hardened jsonfile helper (unique
    temp, fsync, retried replace; F-014), then restrict it to the owner
    where the OS allows (0600). backup=True also keeps one `.bak` of it
    (the consent record); the token file keeps none (RUN-DURABLE-STORES:
    a second copy of a secret buys nothing, a new one is made each start)."""
    path = Path(path)
    jsonfile.write_text(path, text, backup=backup)
    for p in ((path, jsonfile.bak_path(path)) if backup else (path,)):
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass


# TEST-E2E: how often a consented core without a running tailer looks for
# Client.txt again (a few stat calls and one libraryfolders.vdf read).
LOCATE_RETRY_S = 5.0
# RUN-TAIL-HEAL-CORE (research 0050 R1, F10): a reader thread found dead is
# restarted at once, then at most once per this many seconds while it keeps
# dying, so a reader bug cannot spin the core's loop.
RESTART_MIN_S = 5.0
LOG = logging.getLogger("al.core")
# TC-WORN-WIRE (decision 0052): the local config switch (on by default) and
# the two "nothing filed" answers of POST /api/wear
WORN_KEY = "worn_gear"
WORN_OFF = "worn gear off"
WORN_NOTHING = "nothing to wear"
# RUN-LEDGER-CONSENT (decision 0071): the parse ledger's file under the
# runtime dir and what its own consent line says it keeps
LEDGER_FILE = "logshapes.json"
LEDGER_KEEPS = ["pattern hit counts", "masked line shapes"]


def discover_default(runtime, log_path):
    """SEC-NO-DISCOVERY: may a core built with these arguments run the Steam
    library scan? Only the real entry point: no runtime dir and no log
    path. A configured "client_log" still wins over the scan (locate_log)."""
    return runtime is None and not log_path


class ConfigUnreadable(OSError):
    """AREA-AUDIT P5-1: config/local.json exists but is not a JSON object;
    nothing is written over it."""


# RUN-SEAMS (decision 0056): the core loop's built-in ticks, in the order
# the old __main__ loop called them; plug ticks (server/al/plug/) follow.
TICK_ORDER = ("ensure_tailing",  # TEST-E2E: log found later / moved
              "tick_build",      # BUILD-LIVE: this character's build, hot reload
              "tick_summary",    # UTIL-SESSION-SUMMARY: idle -> card
              "tick_calc",       # AREA-AUDIT P3-6: tc_calc off -> stop luajit
              "tick_sources",    # TEST-FULLSTACK-SSE-IDLE: calc / prices
              "tick_guide",      # ZONE-GUIDE: hot reload, save visits
              "tick_history",    # UTIL-RUN-HISTORY: save closed acts
              "tick_watch",      # UTIL-PRICE-WATCH: moves on book refresh
              "tick_diag",       # DIAG-SELF: the Checks card (ruling J)
              "tick_reload")     # HOT-RELOAD: data files, web/ (0042)


class Core:
    def __init__(self, runtime=None, log_path=None, tail=True, poll_s=None,
                 character=None, start_at_end=True, config_path=None, web_fetch=None,
                 discover=None):
        # SEC-NO-DISCOVERY: only the real entry point with no log path looks
        # for the live Client.txt in the Steam libraries. A core given a
        # runtime dir (a test or demo core) or a log path never scans,
        # unless a test passes discover=True on purpose.
        self.discover = discover_default(runtime, log_path) if discover is None else bool(discover)
        self.runtime = Path(runtime) if runtime else paths.runtime_dir()
        self.consent_path = self.runtime / "consent.json"
        # A test core (runtime given) never reads or writes the real config.
        if config_path is not None:
            self.config_path = Path(config_path)
        elif runtime is None:
            self.config_path = paths.local_config_file()
        else:
            self.config_path = self.runtime / "local.json"
        # SEC-ACL-APPLY (decision 0051): only the real core's config/local.json
        # gets the private ACL after a write (a replaced file takes the
        # folder's ACL); a test or demo core never changes an ACL
        self.private_config = runtime is None and config_path is None
        cfg = paths.load_local_config() if runtime is None else {}
        self.poll_s = float(poll_s or cfg.get("poll_ms", 250) / 1000.0)
        self.tail_enabled = tail
        self.start_at_end = start_at_end
        self.bus = EventBus()
        self.state = SessionState(character=character or cfg.get("character"))
        self.bus.add_listener(self.state.apply)
        # TEST-FULLSTACK-SSE-IDLE: a state change outside a log event wakes
        # the SSE streams at once (no new timer; see SessionState.on_change).
        self.state.on_change = self.bus.wake_all
        # UTIL-SESSION-SUMMARY: the last saved card shows until a new one;
        # cards are saved only under the runtime dir.
        self.summary_path = self.runtime / summary_mod.summary_file().name
        self.state.set_session_summary(summary_mod.load_last(self.summary_path))
        last = self.state.session_summary
        self._summary_saved = last.get("id") if last else None
        self._configured_log = log_path or cfg.get("client_log")
        self.log_path = None
        self.tailer = None
        self._next_locate = 0.0
        self._next_restart = 0.0  # RUN-TAIL-HEAL-CORE
        self.tailer_restarts = 0
        self._lock = threading.Lock()
        self.locate_log()
        self.state.set_tailer(consented=self.consented(),
                              ledger=self.ledger_consented())
        self.state.set_overlay_layout(layout.load(self.config_path))
        # TC-CODE: the last loaded PoB build reloads on start (no click).
        # DATA-TREE-SRC: node names from the cached GGG tree export when the
        # build-time snapshot fetched it; a test core never reads the sidecar.
        tree_path = (treedata.default_path() if runtime is None
                     else self.runtime / "gamedata" / treedata.FILE_NAME)
        # BUILD-LIVE (decision 0045): one build per character the log names;
        # tick_build swaps to the character being played and hot-reloads
        # its file when it changes on disk (no click)
        self.builds = build_store.BuildStore(build_store.default_path(self.runtime),
                                             tree=treedata.TreeCache(tree_path),
                                             per_character=True)
        self.builds.character_of = lambda: self.state.character
        # HUD-ACT: zone levels from the cached world areas export when the
        # build-time snapshot fetched it (decision 0020); read only, no fetch.
        zones_path = (acts.default_path() if runtime is None
                      else self.runtime / "gamedata" / acts.FILE_NAME)
        self.zone_table = acts.TableCache(zones_path)
        self._zones_path = Path(zones_path)
        self.state.set_zone_table(self.zone_table.get())
        # ZONE-GUIDE (decision 0043): our own guide file (hot reloaded on a
        # new mtime) and the waypoint graph from the same cached export.
        self.guide = zoneguide.guide_cache()
        self.area_graph = zoneguide.graph_cache(zones_path)
        self.state.set_zone_guide(guide=self.guide.get(), graph=self.area_graph.get())
        # MATH-MAGIC-BASE: a magic item's base from the cached snapshot base
        # list when the build fetched it (decision 0009); read only, no fetch.
        bases_path = (basetypes.default_path() if runtime is None
                      else self.runtime / "gamedata" / basetypes.FILE_NAME)
        self.base_names = basetypes.NamesCache(bases_path)
        # UTIL-CAMPAIGN-CHECKS (ruling H): flask base drop levels from the same
        # cached base list; read only, no fetch, nothing tracked.
        self.flask_table = campaign.FlaskCache(bases_path)
        self.state.set_campaign(flasks=self.flask_table.get())
        item_mod.set_base_names(self.base_names.get)
        # TC-UPGRADE-STATS (decision 0037): trade stat ids from the cached
        # repoe-fork snapshot, used only in the offline upgrade link and
        # only while web data is on; read only, no fetch, no trade call.
        ids_path = (tradestats.default_path() if runtime is None
                    else self.runtime / "gamedata" / tradestats.FILE_NAME)
        # MATH-TRADESTAT-POB (0037 amendment): the hash-pinned PoB checkout's
        # TradeSiteStats.lua fills only keys repoe-fork lacks, when the
        # optional calc component is installed; none with a test runtime.
        self.trade_ids = tradestats.IndexCache(
            ids_path, pob=tradestats.pob_source() if runtime is None else None)
        # TC-EVAL: editable stat weights, defaults written on first start.
        self.weights = weights_mod.WeightsStore(weights_mod.default_path(self.runtime))
        # TC-VIEW / TC-EVAL-UI: build summary and last item check in the state.
        # TC-UPGRADE: the item check card carries an offline upgrade-search link
        # for the checked slot, in the configured league (decision 0017).
        # TC-DELTA (decision 0024): the optional PoB calc callable; None while
        # the component is off (TC-BRIDGE sets it), and the item check then
        # scores with the stat weights and says so on the card.
        # MATH-VALUE: the card's `value` reads the cached rates at run time
        # (self.rates is made below; a lambda defers the lookup).
        # AUDIT-TC-WIRE: the calc comes from theorycraft.calcwire when the
        # user opted in ("tc_calc": true in config/local.json) and setup
        # installed the hash-pinned component; else None (off notice).
        # `tc_calc`, when set (tests), overrides the provider.
        self.tc_calc = None
        self.tc_provider = calcwire.Provider(self.tc_calc_enabled)
        # TC-WORN-WIRE (decision 0052): the worn-gear store, one bounded file
        # under the runtime dir; filed by POST /api/wear (wear()), emptied by
        # Clear run history, used while the worn_gear switch is on (default)
        self.worn = worngear.WornGear(worngear.default_path(self.runtime))
        self.last_eval = tc_live.attach(self.builds, self.weights, self.state,
                                        league=self.trade_league,
                                        calc=lambda: (self.tc_calc if self.tc_calc is not None
                                                      else self.tc_provider()),
                                        rates=lambda: self.rates.snapshot(),
                                        trade_ids=lambda: (self.trade_ids.get()
                                                           if self.web_data_enabled() else {}),
                                        staged=True, worn=self.worn)
        # TC-WORN-WIRE: the worn_gear switch is read at every use
        self.last_eval.worn_on = self.worn_enabled
        # TC-CARD-PARTS: the card parts' ctx gets the config and the area
        self.last_eval.ctx_extra = {"config": self._config, "area_id": lambda: self.state.area_id}
        # MATH-NEXT-LOOK: the build view ranks "look for next" stats with the
        # weights PoB measured for this build (never another build's)
        self.builds.weights_for = self.last_eval.pob_weights.fallback
        # TC-UPGRADE-PER-SLOT: each "look for next" row carries the offline
        # upgrade-search link (decision 0017) in the trade league, with trade
        # stat ids only while web data is on (decision 0037); never a request
        self.builds.link_for = lambda base, slot, top: upgrade.slot_link(
            base, slot, top, self.trade_league(),
            self.trade_ids.get() if self.web_data_enabled() else {})
        # MATH-SKILL-SPLIT / MATH-DEF-BREAKDOWN: PoB's calc-only outputs for
        # the loaded build, fetched in the background when the calc is on;
        # a ready table bumps the build view (no click)
        self.pob_outputs = pobout.OutputsCache(
            lambda: self.tc_calc if self.tc_calc is not None else self.tc_provider(),
            health.CALC_KEYS + skillsplit.KEYS, on_ready=self._outputs_ready)
        self.builds.calc_outputs = self.pob_outputs.get
        # AREA-AUDIT P7-5: the calc switch apart from "table ready", so the
        # card never says "once the calc is on" while it is on and pending
        self.builds.calc_active = self.pob_outputs.active
        self.builds.add_listener(self.pob_outputs.get)
        # Web data (decision 0013): one default-off opt-in, "web_data" in the
        # local config; every outbound request goes through server/al/webfetch.py
        # with an injectable transport (tests pass web_fetch, never the network).
        self.web_fetch = web_fetch
        rates_dir = (ninja.cache_dir() if runtime is None
                     else self.runtime / "cache" / "ninja")
        # UA-CONTACT: poe.ninja also needs the "contact" key.
        # PRICE-UNIQUE / PRICE-STACKABLES: the unique and stackable overviews
        # share the rates' refresh, gate, opt-in and contact (pricebook.py).
        self.rates = ninja.RatesClient(rates_dir, enabled=self.web_data_enabled,
                                       league=self.configured_league, fetch=web_fetch,
                                       contact=self.contact,
                                       book=pricebook.PriceBook(rates_dir))
        # DATA-PRICE-REFRESH-CORE: the loop's refresh gate and the last
        # /api/rates read (monotonic s; tick_prices / note_rates_read)
        self.price_gate, self.rates_read_at = pricerefresh.Gate(), None
        # PRICE-TRADE-LINK (decision 0017): one offline trade-search link per
        # item-hotkey press (POST /api/eval), published as the decision 0016
        # card with the press time. No trade-site request is ever made and
        # the core never opens the link.
        self.price = price.PriceChecker(league=self.trade_league,
                                        card=self.state.set_price,
                                        lookup=self.rates.lookup)
        # UTIL-RUN-HISTORY (decision 0036): finished act splits and deaths
        # per zone across runs, one bounded file under the runtime dir.
        self.history = runhistory.RunHistory(self.runtime / runhistory.FILE_NAME)
        self._history_key = None
        self._parked_keys = {}  # UTIL-MULTICHAR: saved key per parked character
        # UTIL-MAP-LADDER (ruling I): finished maps per area level across
        # sessions, under the same run-history switch, one bounded file.
        self.ladder = mapladder.MapLadder(self.runtime / mapladder.FILE_NAME)
        self._ladder_since = None  # maps opened before a clear stay unsaved
        # ZONE-GUIDE: zones each character entered, one bounded runtime file
        # under the same run-history switch (decision 0036).
        self.visits_path = self.runtime / zoneguide.FILE_NAME
        self.state.load_visits(zoneguide.read_visits(self.visits_path))
        self._visits_saved = self.state.visits_doc()[0]
        # NEWBIE-HINTS (ruling L): hashed character keys and hint ids only
        self.state.use_hint_store(self.runtime / hints.FILE_NAME)
        # UTIL-PRICE-WATCH: the last priced presses, one bounded runtime
        # file; re-read from the cache on a price book refresh only.
        self.watch = pricewatch.PriceWatch(self.runtime / pricewatch.FILE_NAME)
        self._watch_key = None
        # RUN-DURABLE-STORES (F-014): a store save that fails is not lost and
        # not retried at 2 Hz; the store's Saver writes its in-memory state
        # again from a later tick, after 1, 5, 30, then every 60 s. Saves
        # run under self._lock (lock order: self._lock, then the Saver's).
        # plug/stores.py shows one Checks row while any of them is dirty.
        self.store_clock = time.monotonic  # tests replace it
        self._summary_pending = []  # session cards not yet written
        self.savers = {name: jsonfile.Saver(fn, clock=lambda: self.store_clock())
                       for name, fn in (("history", self._save_history),
                                        ("ladder", self._save_ladder),
                                        ("watch", self._save_watch),
                                        ("visits", self._save_visits),
                                        ("summary", self._save_summaries))}
        self.stores_restored = []  # plug/stores.py: store names restored from .bak
        # DIAG-SELF (ruling J): passive local checks, re-read every
        # DIAG_TICK_S from the core loop. The port is the served one (the
        # entry point sets it); a test core reads no process list or
        # sidecar log unless it injects them.
        self.port = ports.AL_PORT
        self.started_at = time.time()  # OBS-CRASH: exit records newer than this start
        self._real = runtime is None
        self.procs_status = ((lambda: procs.status(self.runtime)) if self._real
                             else (lambda: None))
        self.overlay_log = (paths.sidecar_dir("Logs") / "overlay.log" if self._real
                            else self.runtime / "overlay.log")
        self.calc_status = calcwire.component_status if self._real else (lambda: None)
        self._next_diag = 0.0
        # HOTKEYS-LIVE (decision 0058, OVL-KEYS-CORE): the client's
        # ops/runtime/hotkeys.json, re-read only when its stat changed
        # (tick_diag); the effective keys go to the snapshot and Checks.
        self.hotkeys_path = self.runtime / hotkeys.FILE_NAME
        self._hotkeys_stat = None
        self._hotkeys_runtime = None
        # HOT-RELOAD (decision 0042): data files re-read on change (always,
        # hotreload.REGISTRY); web/ edits reload the open dashboard through
        # an SSE "reload" event only in a source checkout (dev_enabled); the
        # supervisor's code reload status shows on the Checks card. A test
        # core watches no web root.
        self.hot = bool(self._real and hotreload.dev_enabled(cfg))
        self.web_watch = (hotreload.TreeWatch([paths.repo_root() / "web"])
                          if self.hot else None)
        self.reload_web = 0
        self.code_status = hotreload.Watched(self.runtime / hotreload.STATUS_FILE,
                                             hotreload.load_json, name="Code reload",
                                             default=dict, registry=False)
        self._reload_notes = []
        # RUN-SEAMS (decision 0056): the tick list tick_all runs, built-ins
        # first (looked up by name at each pass, so a subclass or a test
        # override is honoured), then each plug module's attach(core).
        self.ticks = []
        self.tick_ms = {}
        self.loop_at = None
        self._tick_errors = plug.ErrorThrottle(logging.getLogger("al"))
        # RUN-LEDGER-WIRE (F-061): plug/ledger.py sets the wire feed_line and
        # eval_press hand their lines and presses to; its write and the
        # ledger delete (revoking the consent) share ledger_lock
        self.ledger_wire = None
        self.ledger_lock = threading.Lock()
        for name in TICK_ORDER:
            self.add_tick(name)
        plug.attach_all(self)
        # SEC-ACL-CHECK (F-011): one read-only ACL audit of the runtime dir,
        # the AshLight folder and the sidecar root per start, on a
        # background thread (never on the diag tick); real core only, a
        # test core sets acl_open itself.
        self.acl_open = None
        self._acl_thread = None
        self._acl_stop = threading.Event()
        if self._real:
            self.start_acl_audit()
        diag_data.attach(self)  # DATA-DIAG-SEAM: the data modules' attach(core), once

    # SEC-ACL-CHECK: the entry point makes the runtime dir private right
    # after Core() (start_token); the audit waits this long so it reads the
    # repaired ACL, not the one being replaced.
    ACL_AUDIT_DELAY_S = 5.0

    def start_acl_audit(self, audit=None, delay=None):
        """Start the one ACL audit thread (a second call returns the same
        thread). It sets acl_open to the folder names anyone else can write
        to (acl.audit), or leaves None when the audit fails; the next diag
        tick shows the row. `audit` (tests) replaces the real one."""
        if self._acl_thread is not None:
            return self._acl_thread
        if audit is None:
            def audit():
                return acl.audit(self.runtime, paths.repo_root(), paths.sidecar_root())
        wait_s = self.ACL_AUDIT_DELAY_S if delay is None else float(delay)

        def run():
            if wait_s > 0 and self._acl_stop.wait(wait_s):
                return
            try:
                found = audit()
            except Exception:  # noqa: BLE001 - an unreadable ACL reads unknown
                found = None
            if isinstance(found, list):
                self.acl_open = [n for n in found if isinstance(n, str)]
                self._next_diag = 0.0  # show the row on the next loop pass

        self._acl_thread = threading.Thread(target=run, name="al-acl-audit", daemon=True)
        self._acl_thread.start()
        return self._acl_thread

    def add_tick(self, name, fn=None):
        """Append a tick to the loop list. fn None = the Core method `name`
        (looked up at each pass). A name already in the list is refused."""
        if not isinstance(name, str) or not name:
            raise ValueError("a tick needs a name")
        if fn is not None and not callable(fn):
            raise ValueError(f"tick {name}: not callable")
        if any(n == name for n, _ in self.ticks):
            raise ValueError(f"tick {name} is already in the list")
        self.ticks.append((name, fn))

    def tick_all(self, log=None, now=None):
        """One pass of the core loop (every 0.5 s from __main__): each tick
        in list order. A tick that raises never stops the loop or the ticks
        after it; its first error is logged with the traceback, then one
        line a minute with a count (C22). Records loop_at (monotonic, the
        pass start) and tick_ms (the last duration of each tick, ms).
        `now` (monotonic) is for tests of the throttle."""
        if log is not None and self._tick_errors.log is not log:
            self._tick_errors.log = log
        self.loop_at = time.monotonic()
        for name, fn in list(self.ticks):
            t0 = time.monotonic()
            try:
                (fn if fn is not None else getattr(self, name))()
            except Exception as exc:  # noqa: BLE001 - never stops the core loop
                self._tick_errors.failed(name, exc,
                                         now if now is not None else time.monotonic())
            self.tick_ms[name] = round((time.monotonic() - t0) * 1000.0, 3)

    def _outputs_ready(self):
        """A new PoB output table for the loaded build: the build view is
        read again (the state's build summary gets a new calc_rev). AREA-AUDIT
        P7-4: the bump runs under the state lock (no read-then-write here)."""
        self.state.bump_calc_rev()

    def tick_build(self):
        """BUILD-LIVE (decision 0045), from the core loop: follow the
        character being played and re-read its build file when it changed
        on disk. The store's listeners re-publish the build summary,
        re-score the last item and the checked items. Returns what
        happened ("switch", "reload" or None)."""
        return self.builds.sync()

    def eval_press(self, text, slot=None):
        """One item-hotkey press (POST /api/eval): the item check and at most
        one price check, both stamped with the same press time so the
        overlay merges them (decision 0016 Fork 2). The text is the app's one
        clipboard read for this press; nothing here reads the clipboard. The
        price check is an offline trade-search link (decision 0017).
        TC-PRESS-BUILD (ruling Q-02): text that holds a PoB code, character
        JSON or share link loads that build for the character being played
        (theorycraft/press.py) and publishes a "Build loaded" card instead;
        such a press asks for no price check and adds no price-watch row.
        TC-PRESS-STAGED-LIVE (decision 0024 amendment 2026-11-19): returns the
        first stage's result (the stat-weight card, published at once); the
        Path of Building stages follow on the LastEval worker as card
        updates that keep this press's time.
        RUN-METRICS-SITES (decision 0067): each press is counted as
        `press|<outcome>` (item, unscored, build, empty or error) with its
        milliseconds in the `press_ms` ring; never the item text."""
        t0 = time.monotonic()
        outcome = "error"
        try:
            try:
                self.tick_build()  # BUILD-LIVE: score against this character's build
            except Exception:  # noqa: BLE001 - the press must still be checked
                pass
            at = self.state.now()
            if isinstance(text, str) and not text.strip():
                outcome = "empty"
                return self._empty_press(slot, at)
            doc = tc_press.load(self, text, at=at)
            if doc is not None:
                outcome = "build"
                return doc
            result = self.last_eval.run(text, slot, at=at)
            outcome = "item" if isinstance(result, dict) and result.get("ok") else "unscored"
            self._ledger_press(text)  # RUN-LEDGER-WIRE: a waystone's masked block
            doc = self.price.request(text, at=at)
            self._watch_press(text, doc, at)
            return result
        finally:
            ms = round((time.monotonic() - t0) * 1000.0, 1)
            metrics.inc(f"press|{outcome}")
            metrics.timing("press_ms", ms)
            metrics.emit("press", outcome=outcome, ms=ms)

    def _ledger_press(self, text):
        """RUN-LEDGER-WIRE (LIVE-WAYSTONE): the press text goes to the parse
        ledger, which keeps only a waystone's masked property-block shape
        and only while the ledger consent is on. Never fails the press."""
        wire = self.ledger_wire
        if wire is None:
            return None
        try:
            return wire.press(text)
        except Exception:  # noqa: BLE001 - the press must still be answered
            LOG.warning("the parse ledger could not look at an item press")
            return None

    def _empty_press(self, slot, at):
        """OVL-COPY-FIRST (F-054): the press found a blank clipboard (it
        landed before the game wrote the item). The item check publishes
        the "empty clipboard" status card ("Copy the item first") and no
        price check is asked for. The player copies the item and presses
        again: no retry, no wait for a change, no timer (decision 0003).
        As a new press it cancels an older press's pending Path of
        Building stages and leaves no item to re-score (LastEval.clear,
        TC-EVAL-CLEAR-API)."""
        result = {"ok": False, "error": EMPTY_CLIPBOARD, "slot": slot or None,
                  "build_loaded": self.builds.build is not None}
        card = dict(tc_live.compact(result), upgrade=None, value=None, waystone=None)
        self.last_eval.clear(card=card, result=result, at=at)
        return dict(card)

    # -- TC-WORN-WIRE (decision 0052)
    def worn_enabled(self):
        """The worn_gear switch: on unless the local config says false."""
        return self._config().get(WORN_KEY) is not False

    def wear(self, slot=None, text=None):
        """POST /api/wear: file the last checked item (or `text`, the item
        text the optional wear key's own press sends) as the current
        character's worn item of its slot (`slot`: an explicit slot, else
        the store's choice). Nothing here reads the clipboard (decision
        0003). Returns {"ok", "slot", "error"}; with the switch off nothing
        is stored."""
        if not self.worn_enabled():
            return {"ok": False, "slot": None, "error": WORN_OFF}
        filed = self.last_eval.wear_last(slot=slot, text=text)
        if filed is None:
            return {"ok": False, "slot": None, "error": WORN_NOTHING}
        return {"ok": True, "slot": filed, "error": None}

    def _watch_press(self, text, doc, at):
        """UTIL-PRICE-WATCH: remember what this press already priced (the
        cached poe.ninja value on its card); nothing more is read."""
        ninja = doc.get("ninja") if isinstance(doc, dict) else None
        if not ninja or not isinstance(doc.get("item"), dict):
            return False
        flags = getattr(item_mod.parse(text), "flags", None) or {}
        item = dict(doc["item"], corrupted=bool(flags.get("corrupted")
                                                or flags.get("twice_corrupted")))
        saved = self._store_op("watch", lambda: self.watch.record(item, ninja, at))
        if saved:
            self._watch_key = None  # republish on the next tick
        return saved

    def _read_config_strict(self):
        """The local config for a write: {} when the file is missing,
        else its object. AREA-AUDIT P5-1: a file the user broke by hand
        (bad JSON, not an object) raises ConfigUnreadable instead of
        reading as {}, so a write never wipes the contact and paths
        (the layout.save rule)."""
        try:
            text = self.config_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        try:
            cfg = json.loads(text)
        except ValueError as e:
            cfg = self._config_from_bak()
            if cfg is None:
                raise ConfigUnreadable("config/local.json is unreadable") from e
        if not isinstance(cfg, dict):
            cfg = self._config_from_bak()
            if cfg is None:
                raise ConfigUnreadable("config/local.json is not a JSON object")
        return cfg

    def _config_from_bak(self):
        """RUN-DURABLE-STORES: a damaged config/local.json restored from the
        .bak of its last good write (jsonfile records the restore; Checks
        then shows one note); None when there is no good .bak."""
        return jsonfile.read_json(self.config_path, kind=dict, backup=True)

    def _write_config(self, update):
        """Merge `update` into the local config and persist it, keeping
        every other key (the contact included; only set_contact writes it).
        Atomic, ASCII + LF, with one .bak of the written copy (F-014).
        Raises ConfigUnreadable (an OSError) on a hand-broken file that
        no .bak can restore."""
        with self._lock:
            cfg = self._read_config_strict()
            cfg.update(update)
            jsonfile.write_json(self.config_path, cfg, indent=2, backup=True)
            self._private_config()
            return cfg

    def _private_config(self):
        """SEC-ACL-APPLY: re-apply the private ACL to the config file after
        a write, real core only (decision 0051)."""
        if self.private_config:
            acl.make_private(self.config_path)
            # RUN-DURABLE-STORES: its .bak holds the same keys (the contact)
            bak = jsonfile.bak_path(self.config_path)
            if bak.is_file():
                acl.make_private(bak)

    # -- UX-SETTINGS-IO (ruling E)
    def export_settings(self):
        """AshLight's own settings for the download (allow-list only: no
        contact, token, cookie or path)."""
        return settingsio.export_doc(self._config(), VERSION)

    def import_settings(self, doc):
        """Merge an imported settings file's allowed keys into the local
        config; web data is never switched on here. Returns the report;
        raises settingsio.SettingsError with nothing applied."""
        update, report = settingsio.parse_import(doc, self._config())
        if update:
            self._write_config(update)
            self.state.set_overlay_layout(layout.load(self.config_path))
        return report

    # -- RUN-DURABLE-STORES (F-014): store saves with retry and back-off
    def _save_history(self):
        """Saver callable: the run history as it is in memory."""
        runhistory.save(self.history.path, self.history.runs)

    def _save_ladder(self):
        """Saver callable: the map ladder as it is in memory."""
        self.ladder._save()

    def _save_watch(self):
        """Saver callable: the watched prices as they are in memory."""
        self.watch._save()

    def _save_visits(self):
        """Saver callable: the visited zones as the state has them (an
        empty book also removes the .bak, zoneguide.write_visits)."""
        version, doc = self.state.visits_doc()
        zoneguide.write_visits(self.visits_path, doc)
        self._visits_saved = version

    def _save_summaries(self):
        """Saver callable: append the pending session cards, oldest first;
        a card leaves the queue only once it is written."""
        while self._summary_pending:
            summary_mod.save(self.summary_path, self._summary_pending[0])
            self._summary_pending.pop(0)

    def _flush(self, name, force=False):
        """Save store `name` when it has unsaved changes and its back-off
        allows (force: a click, ignore the back-off). True when nothing of
        it is left unsaved."""
        with self._lock:
            return self.savers[name].flush(force=force)

    def _store_op(self, name, fn):
        """Run one store change (its memory update and its own save) under
        the lock. A failed save leaves the change in memory and marks the
        store's Saver, which writes it from a later tick with back-off.
        fn's result, or False after a failed save."""
        with self._lock:
            try:
                return fn()
            except OSError:
                self.savers[name].mark()
                return False

    # -- UTIL-RUN-HISTORY
    def history_enabled(self):
        return runhistory.enabled_setting(self._config().get(runhistory.CONFIG_KEY))

    def tick_history(self):
        """From the core's loop: save the current run when an act split
        closed or the run finished (and history is on), then publish the
        history view. No request. True when the file was written.
        RUN-DURABLE-STORES: an unsaved change is retried first; while it
        stays unsaved new runs wait in the state (they are read again on
        the next tick), so a failing disk costs one write per back-off
        step, not one per tick."""
        rec = self.state.run_record()
        on = self.history_enabled()
        wrote = False
        key = None
        if rec is not None:
            key = (rec["started_at"], rec["closed"], rec["finished"])
        saver = self.savers["history"]
        was_dirty = saver.dirty
        if self._flush("history") and was_dirty:
            wrote = True
        if (not saver.dirty and on and rec is not None and rec["closed"]
                and key != self._history_key):
            wrote = self._store_op("history", lambda: self.history.record(rec)) or wrote
            self._history_key = key
        # UTIL-MULTICHAR (decision 0038): the player's other characters'
        # runs (rebuilt at core start, or parked by a switch) are saved
        # too, each under its own name, and every character gets a view.
        names = self.state.character_names()
        current = names[0] if names else None
        for name in names[1:]:
            prec = self.state.parked_record(name)
            if saver.dirty or not on or prec is None or not prec["closed"]:
                continue
            pkey = (prec["started_at"], prec["closed"], prec["finished"])
            if self._parked_keys.get(name) == pkey:
                continue
            wrote = self._store_op("history", lambda: self.history.record(prec)) or wrote
            self._parked_keys[name] = pkey
        view = self.history.view(rec, enabled=on)
        # the selector also lists characters seen only in the saved file
        others = names[1:] + [n for n in reversed(self.history.characters())
                              if n and n != current and n not in names]
        view["by_character"] = {
            name: self.history.view(self.state.parked_record(name), enabled=on,
                                    character=name)
            for name in others[:runhistory.MAX_CHARACTERS - 1]}
        self.state.set_run_history(view)
        return self.tick_ladder(on) or wrote

    # -- ZONE-GUIDE (decision 0043)
    def tick_guide(self):
        """From the core's loop: re-read the guide file and the area graph
        when their files changed (one stat each), and save the visited
        zones when they changed and run history is on. No request. True
        when the visits file was written. RUN-DURABLE-STORES: the save goes
        through the visits Saver (a failed one is retried with back-off)."""
        self.state.set_zone_guide(guide=self.guide.get(), graph=self.area_graph.get())
        saver = self.savers["visits"]
        version, _ = self.state.visits_doc()
        if version != self._visits_saved and self.history_enabled():
            saver.mark()
        if not saver.dirty:
            return False
        return self._flush("visits")

    def _clear_visits(self):
        """Caller holds self._lock. The empty book is written at once (a
        click; a failure is retried by the visits Saver) and the .bak is
        removed even when that write fails: a cleared store keeps no copy
        (decision 0036 amendment 2026-11-18)."""
        self.state.clear_visits()
        saver = self.savers["visits"]
        saver.mark()
        saver.flush(force=True)
        runhistory.drop_bak(self.visits_path)

    def tick_ladder(self, on=None):
        """UTIL-MAP-LADDER: save the session's finished maps (run history
        on) and publish the all-sessions ladder; off publishes none. True
        when the file was written. RUN-DURABLE-STORES: an unsaved change
        is retried first; new maps wait in the state while it fails."""
        if on is None:
            on = self.history_enabled()
        saver = self.savers["ladder"]
        was_dirty = saver.dirty
        wrote = self._flush("ladder") and was_dirty
        if not on:
            self.state.set_map_ladder(None)
            return wrote
        character, rows = self.state.map_ladder_rows()
        since = self._ladder_since
        if since is not None:
            rows = [r for r in rows if isinstance(r.get("opened_at"), (int, float))
                    and r["opened_at"] > since]
        if not saver.dirty:
            done = [r for r in rows if r.get("done")]
            wrote = self._store_op("ladder",
                                   lambda: self.ladder.record(character, done)) or wrote
        with self._lock:
            view = self.ladder.view(character, rows)
        self.state.set_map_ladder(view)
        return wrote

    def set_history(self, enabled=None, clear=False):
        """The dashboard switch and clear button."""
        if enabled is not None:
            self._write_config({runhistory.CONFIG_KEY: bool(enabled)})
        if clear:
            # the current run is cleared too: it is saved again only when
            # its next act split closes
            rec = self.state.run_record()
            with self._lock:
                self.history.clear()
                self.ladder.clear()  # UTIL-MAP-LADDER: same switch, same button
                self._clear_visits()  # ZONE-GUIDE: same switch, same button
                self._ladder_since = self.state.now()
                self._history_key = ((rec["started_at"], rec["closed"], rec["finished"])
                                     if rec else None)
                # TC-WORN-WIRE (decision 0052): the worn set, same button;
                # a failed write leaves it empty in memory (the next wear
                # writes the file again)
                try:
                    self.worn.clear()
                except OSError:
                    LOG.warning("worn gear clear: the file was not written")
                # UTIL-MULTICHAR: the parked characters' runs likewise
                self._parked_keys = {}
                for name in self.state.character_names()[1:]:
                    prec = self.state.parked_record(name)
                    if prec is not None:
                        self._parked_keys[name] = (prec["started_at"], prec["closed"],
                                                   prec["finished"])
        self.tick_history()
        return self.state.snapshot()["run_history"]

    # -- NEWBIE-HINTS
    def reset_hints(self):
        """The dashboard's "reset hints" click."""
        return self.state.reset_hints()

    # -- UTIL-PRICE-WATCH
    def watch_pct(self):
        return pricewatch.pct_setting(self._config().get(pricewatch.CONFIG_KEY))

    def tick_watch(self):
        """From the core's loop: while web data is on, re-read the watched
        items from the cached price book once per book refresh (no
        request), then publish the view. True when a price changed."""
        on = self.web_data_enabled()
        book = getattr(self.rates, "book", None)
        stamps = []
        if book is not None:
            stamps = sorted(t.get("checked_at") for t in (book.doc.get("types") or {}).values()
                            if isinstance(t, dict)
                            and isinstance(t.get("checked_at"), (int, float)))
        key = (on, tuple(stamps), self.rates.doc.get("checked_at"), len(self.watch.items))
        changed = False
        # RUN-DURABLE-STORES: a refresh or press whose save failed is
        # written again from here with back-off (the prices are in memory)
        self._flush("watch")
        if key != self._watch_key:
            if on:
                changed = self._store_op("watch",
                                         lambda: self.watch.refresh(self.rates.lookup))
            self._watch_key = key
        self.state.set_price_watch(self.watch.view(on, self.watch_pct()))
        return changed

    def clear_watch(self):
        with self._lock:
            self.watch.clear()
        self._watch_key = None
        self.tick_watch()
        return self.state.snapshot()["price_watch"]

    # -- web data opt-in (decision 0013)
    # AREA-AUDIT P5-4: FAT keeps a 2 s mtime, SMB / exFAT can be as coarse.
    CONFIG_COARSE_S = 2.0

    def _read_config_bytes(self):
        return self.config_path.read_bytes()

    def _config(self):
        """The local config as a fresh dict ({} when missing or bad).
        AREA-AUDIT P4-4: the 0.5 s loop tick asks for it, so the file is
        stat-ed each call and read and parsed only when its mtime or size
        changed. AREA-AUDIT P5-4: on a coarse-timestamp filesystem a
        same-size rewrite inside one tick keeps (mtime, size), so while
        the last read was within CONFIG_COARSE_S of the file's mtime the
        bytes are re-read and compared (a hash); once a read lands later
        than that, any further write must move the mtime and the stat
        alone decides again."""
        try:
            st = self.config_path.stat()
            key = (st.st_mtime_ns, st.st_size)
        except OSError:
            self._config_cache = None
            return {}
        cache = getattr(self, "_config_cache", None)
        if cache is not None and cache[0] == key and cache[3]:
            return dict(cache[1])
        read_at = time.time()
        try:
            raw = self._read_config_bytes()
        except OSError:
            self._config_cache = None
            return {}
        digest = hashlib.blake2b(raw, digest_size=16).digest()
        stable = read_at - st.st_mtime_ns / 1e9 > self.CONFIG_COARSE_S
        if cache is not None and cache[0] == key and cache[2] == digest:
            self._config_cache = (key, cache[1], digest, stable)
            return dict(cache[1])
        try:
            cfg = json.loads(raw.decode("utf-8"))
        except ValueError:
            cfg = None
        if not isinstance(cfg, dict):
            # RUN-DURABLE-STORES: a damaged file comes back from its .bak
            # (rewritten on disk, so the next call stats a new key; if that
            # write failed, the damaged file's key keeps the restored copy
            # cached, so the .bak is not re-read on every call)
            restored = self._config_from_bak()
            cfg = restored if restored is not None else {}
        self._config_cache = (key, cfg, digest, stable)
        return dict(self._config_cache[1])

    def tc_calc_enabled(self):
        """AUDIT-TC-WIRE: the optional PoB calc opt-in (default off)."""
        return self._config().get("tc_calc") is True

    def web_data_enabled(self):
        """True only when the user turned web data on (default off)."""
        return self._config().get("web_data") is True

    def contact(self):
        """UA-CONTACT: the User-Agent contact from the gitignored local
        config ("contact"), cleaned; None when unset or unusable."""
        return webfetch.clean_contact(self._config().get(webfetch.CONTACT_KEY))

    def web_blocked_reason(self):
        """Why poe.ninja fetches are off now ("web data off",
        "contact not set") or None."""
        return webfetch.blocked_reason(self.web_data_enabled, self.contact)

    def league_setting(self):
        """The "league" key of the local config as the player set it (the
        picker or a hand edit), or None."""
        value = self._config().get("league")
        return value if isinstance(value, str) and value.strip() else None

    def configured_league(self):
        """The configured league to price and link: league_setting(), with
        a solo league mapped to its trade league from the cached list
        (DATA-LEAGUE-PICKER-API, leagues.trade_league_of), so RatesClient
        and the trade links both use the trade league. None when unset."""
        value = self.league_setting()
        rates = getattr(self, "rates", None)  # None while __init__ builds it
        if value is None or rates is None:
            return value
        return leagues.trade_league_of(value, rates.doc.get("leagues"))

    def league_names(self):
        """The display names of poe.ninja's cached leagues list, in its
        order (newest first); [] while none is cached. Never a request."""
        return [e["name"] for e in leagues.entries(self.rates.doc.get("leagues"))]

    def league_auto(self):
        """The display name of the auto league (the first of the cached
        list, decision 0026), or None. Never a request."""
        auto = self.rates.doc.get("league_auto")
        if not (isinstance(auto, str) and auto.strip()):
            return None
        return leagues.name_of(self.rates.doc.get("leagues"), auto) or auto

    def league_choice(self, value):
        """DATA-LEAGUE-PICKER-API: the value set_league would store for
        `value`: the cached entry's display name, or '' for '' / blank
        (clears the key). Raises ValueError (settingsio.SettingsError) for a
        value settingsio.ALLOWED["league"] refuses or one outside the
        cached leagues list. Writes nothing."""
        if not isinstance(value, str):
            raise ValueError("the league must be text")
        if not value.strip():
            return ""
        checked = settingsio.ALLOWED["league"](value)
        hit = leagues.entry_of(self.rates.doc.get("leagues"), checked)
        if hit is None:
            raise ValueError("not a league in the cached list")
        return hit["name"]

    def set_league(self, value):
        """DATA-LEAGUE-PICKER-API (F-141): store the league picked in the
        dashboard as "league" in the local config; '' (or blank) removes
        the key, so the auto league is followed again (decision 0026).
        Checked by league_choice first, nothing written on a refusal.
        Makes no request: the next due refresh prices the new league
        (the hourly gates decide). Raises ValueError for a refused value
        and ConfigUnreadable (an OSError) on a hand-broken file. Returns
        the stored name or None."""
        stored = self.league_choice(value)
        with self._lock:
            cfg = self._read_config_strict()
            if stored:
                cfg["league"] = stored
            else:
                cfg.pop("league", None)
            jsonfile.write_json(self.config_path, cfg, indent=2, backup=True)
            self._private_config()
        return stored or None

    def trade_league(self):
        """UTIL-1.0-READY: the league for the offline trade links and the
        price card label: the configured one, else the current league read
        from poe.ninja's cached leagues list while web data is on (so a new
        league, e.g. PoE2 1.0's, is followed without a setting), else None
        (trade.py then uses Standard). Never a request."""
        configured = self.configured_league()
        if configured:
            return configured
        if not self.web_data_enabled():
            return None
        league = self.rates.doc.get("league")
        return league.strip() if isinstance(league, str) and league.strip() else None

    def set_web_data(self, enabled):
        """Persist the opt-in in the local config, keeping every other key
        (the contact included; only set_contact writes it). AREA-AUDIT
        P5-1: raises ConfigUnreadable on a hand-broken file."""
        self._write_config({"web_data": bool(enabled)})
        if enabled:
            self.rates.refresh_async()
        return bool(enabled)

    def set_contact(self, value):
        """DATA-CONTACT-FIELD (F-018): store the User-Agent contact typed
        in the dashboard as "contact" in the gitignored local config, its
        only store (decision 0015); '' (or blank) removes the key. The value
        is never returned, echoed or logged. Raises ValueError for an
        unusable value (webfetch.clean_contact) with nothing written, and
        ConfigUnreadable (an OSError) on a hand-broken file. A set contact
        starts a due price refresh at once (the opt-in and the hourly gates
        still decide). Returns True when a contact is now set."""
        if not isinstance(value, str):
            raise ValueError("the contact must be text")
        cleaned = webfetch.clean_contact(value) if value.strip() else ""
        if cleaned is None:
            raise ValueError("unusable contact")
        with self._lock:
            cfg = self._read_config_strict()
            if cleaned:
                cfg[webfetch.CONTACT_KEY] = cleaned
            else:
                cfg.pop(webfetch.CONTACT_KEY, None)
            jsonfile.write_json(self.config_path, cfg, indent=2, backup=True)
            self._private_config()
        if cleaned:
            self.rates.refresh_async()
        return bool(cleaned)

    def note_rates_read(self, now=None):
        """DATA-PRICE-REFRESH-CORE: a page read /api/rates (monotonic s)."""
        self.rates_read_at = time.monotonic() if now is None else now

    def tick_prices(self, now=None):
        """DATA-PRICE-REFRESH-CORE (F-036), from the core loop: at most once
        a minute, while web data is on and either the log is active
        (consented and not idle, decision 0029) or /api/rates was read in
        the last 10 minutes, start a due price refresh. The hourly gates,
        the back-off and the contact rule of RatesClient.refresh_async still
        decide; no request is made here. True when a refresh started."""
        now = time.monotonic() if now is None else now
        gate = self.price_gate
        if not gate.ready(now):
            return False
        web_on = self.web_data_enabled()
        idle = True
        if web_on:
            # read the way diag_facts reads it, once a minute at most
            tl = self.state.snapshot().get("tailer") or {}
            idle = not tl.get("consented") or bool(tl.get("idle"))
        if not gate.due(now, web_on, idle, self.rates_read_at):
            return False
        return bool(self.rates.refresh_async())

    def load_share_url(self, url):
        """TC-URL: fetch a pasted share URL once (opt-in, allowlist, size cap,
        no redirect off the allowlist) and load the fetched build text like
        a paste. Raises webfetch.FetchError (WebDataOff / UrlNotAllowed
        included), codec.CodeError or model.BuildError."""
        text = shareurl.fetch_build_text(url, enabled=self.web_data_enabled,
                                         fetch=self.web_fetch)
        return self.builds.load_code(text)

    # -- Client.txt location
    def locate_log(self):
        """A configured path is used as is, existing or not (it may appear
        later; Checks says when it is missing) and never falls through to
        the Steam scan. Without one, the scan runs only when self.discover
        (SEC-NO-DISCOVERY)."""
        if self._configured_log:
            found = logfile.discover_client_log(self._configured_log)
        elif self.discover:
            found = logfile.discover_client_log(None)
        else:
            found = None
        self.log_path = found
        self.state.set_tailer(path=str(found) if found else None)
        return found

    # -- consent
    def consent_record(self):
        """The saved opt-in ({} when missing or bad). RUN-DURABLE-STORES: a
        half-written consent.json is restored from its .bak."""
        return jsonfile.read_json(self.consent_path, kind=dict, default={}, backup=True)

    def consented(self):
        return bool(self.consent_record().get("consented"))

    def ledger_consented(self):
        """RUN-LEDGER-CONSENT (decision 0071): the parse ledger's own opt-in,
        the "ledger" key of consent.json. Only an explicit {"consented":
        true} there counts, and only while the Client.txt opt-in is on; the
        Client.txt opt-in alone never grants it."""
        rec = self.consent_record()
        led = rec.get("ledger")
        return (bool(rec.get("consented")) and isinstance(led, dict)
                and led.get("consented") is True)

    def ledger_path(self):
        return self.runtime / LEDGER_FILE

    def _delete_ledger(self):
        """Revoking the ledger deletes its file (and a .bak of it): the
        player's choice to stop keeping it removes what was kept.
        RUN-LEDGER-WIRE: under ledger_lock, so a write in flight finishes
        first, and the in-memory ledger is emptied too."""
        with self.ledger_lock:
            wire = self.ledger_wire
            if wire is not None:
                wire.reset()
            for p in (self.ledger_path(), jsonfile.bak_path(self.ledger_path())):
                try:
                    p.unlink()
                except FileNotFoundError:
                    pass
                except OSError:
                    LOG.warning("could not delete the parse ledger file")

    def record_ledger_consent(self, consented):
        """POST /api/consent {"ledger": bool}: record the parse ledger's own
        opt-in. Allowing it needs the Client.txt opt-in first (ValueError,
        nothing changed); revoking it deletes ops/runtime/logshapes.json.
        Returns the whole consent record."""
        rec = dict(self.consent_record())
        if consented and not rec.get("consented"):
            raise ValueError("the parse record needs the Client.txt opt-in first")
        rec["ledger"] = {"consented": bool(consented), "at": _utc_now(),
                         "file": LEDGER_FILE, "keeps": list(LEDGER_KEEPS)}
        write_private(self.consent_path, json.dumps(rec, indent=1) + "\n", backup=True)
        if not consented:
            self._delete_ledger()
        self.state.set_tailer(ledger=bool(consented))
        return rec

    def record_consent(self, consented, path=None):
        if path and not logfile.consent_path_ok(path):
            # AUDIT-HTTP-HARDEN S4: checked before any file system access.
            raise ValueError("path must be a local Client.txt or the folder holding it")
        if path and Path(path).name.lower() != logfile.LOG_NAME and Path(path).is_file():
            # SEC-NO-DISCOVERY: an existing file must be named Client.txt;
            # nothing is changed (the API answers 400).
            raise ValueError("path must be a local Client.txt or the folder holding it")
        if path:
            self._configured_log = path
            self.locate_log()
        rec = {"consented": bool(consented), "at": _utc_now(), "app_version": VERSION,
               "file": "Client.txt", "derives": ["zone", "level", "deaths",
                                                 "whispers", "session times"]}
        # RUN-LEDGER-CONSENT (decision 0071): the ledger's own key is kept
        # while the Client.txt opt-in stays on; revoking the Client.txt
        # opt-in turns the ledger off too and deletes its file
        old = self.consent_record().get("ledger")
        if consented and isinstance(old, dict):
            rec["ledger"] = old
        elif not consented and isinstance(old, dict) and old.get("consented") is True:
            rec["ledger"] = dict(old, consented=False, at=_utc_now())
        write_private(self.consent_path, json.dumps(rec, indent=1) + "\n", backup=True)
        if not consented:
            self._delete_ledger()
        self.state.set_tailer(consented=bool(consented),
                              ledger=self.ledger_consented())
        if consented:
            self.start_tailing()
        else:
            self.stop_tailing()
        return rec

    # -- overlay layout (OVL-POS)
    def overlay_layout(self):
        return layout.load(self.config_path)

    def set_overlay_layout(self, changes):
        """Merge changes into the stored layout, persist, publish. Raises
        layout.LayoutError on a bad field."""
        if not isinstance(changes, dict):
            raise layout.LayoutError("layout must be an object")
        merged = dict(self.overlay_layout())
        merged.update(changes)
        with self._lock:
            saved = layout.save(self.config_path, merged)
            self._private_config()
        self.state.set_overlay_layout(saved)
        return saved

    def displays(self):
        return layout.read_displays(self.runtime)

    # -- tailing
    def feed_line(self, line):
        """One tailed line: parse, publish, then the parse ledger
        (RUN-LEDGER-WIRE, F-061): class and drift counters always, hit
        counts and masked shapes only while the ledger consent is on. A
        ledger error never stops the tailer."""
        ev = parser.parse_line(line)
        if ev is not None:
            self.bus.publish(ev)
        wire = self.ledger_wire
        if wire is not None:
            try:
                wire.feed(line, ev)
            except Exception as exc:  # noqa: BLE001 - the tailer must read on
                self._tick_errors.failed("ledger feed", exc)
        return ev

    def _on_status(self, ev):
        ev.setdefault("source", "tailer")
        self.bus.publish(ev)

    def _resume(self, path, end):
        """LIVE-RESUME: recover zone, character, class, level and deaths
        from the bytes before the tailer's start offset (decision 0008)."""
        t0 = time.perf_counter()
        fixed = self.state.character if self.state.character_fixed else None
        result = resume.scan(path, end=end, character=fixed)
        if result is None:
            # RUN-TAIL-HEAL-CORE: the counts are not recovered this time;
            # say so in the log (the tailer reads on either way).
            LOG.warning("the Client.txt resume scan could not read the file; "
                        "counts are not recovered")
            return
        fields = resume.state_fields(result)
        self.state.restore(fields)
        try:  # TEST-LIVE-EXIT: a game closed before the core started
            self.state.seed_last_line(os.path.getmtime(path))
        except OSError:
            pass
        recovered = [k for k in ("zone", "character", "class", "level", "area_id")
                     if fields.get(k) is not None]
        recovered += [k for k in ("deaths", "level_ups") if fields.get(k)]
        snap = self.state.snapshot()
        if snap["acts"]["splits"] and fields.get("act_areas"):
            recovered.append("acts")
        if fields.get("run_events") and snap["maps"]["count"]:
            recovered.append("maps")
        self.state.set_tailer(resume={
            "bytes": result["bytes_scanned"], "hit_marker": result["hit_marker"],
            "ms": round((time.perf_counter() - t0) * 1000.0, 1),
            "recovered": recovered})

    def start_tailing(self):
        """Start the tailer when enabled, consented and the file is known."""
        with self._lock:
            if self.tailer is not None or not self.tail_enabled:
                return False
            if not self.consented():
                return False
            if self.log_path is None and self.locate_log() is None:
                return False
            self.tailer = logfile.Tailer(self.log_path, self.feed_line, self._on_status,
                                         poll_s=self.poll_s,
                                         start_at_end=self.start_at_end,
                                         on_resume=self._resume)
            self.tailer.start()
            return True

    def ensure_tailing(self, now=None):
        """TEST-E2E, ZERO-CLICK: called from the core's main loop. With
        consent recorded, start the tailer once Client.txt is found (the game
        installed after the core started, a Steam library added), and follow
        a DISCOVERED log that vanished and shows up in another library. A
        configured path is never second-guessed. Rate limited to one look per
        LOCATE_RETRY_S. True when a tailer was started.

        RUN-TAIL-HEAL-CORE (research 0050 R1, F10): a reader whose thread
        died is restarted on the first call that sees it (not rate limited
        by the locate look), then at most once per RESTART_MIN_S; it goes
        on from its own offset, so nothing is read twice."""
        now = time.monotonic() if now is None else now
        restarted = self._heal_reader(now)
        if restarted is not None:
            return restarted
        if now < self._next_locate:
            return False
        self._next_locate = now + LOCATE_RETRY_S
        if not self.tail_enabled or not self.consented():
            return False
        t = self.tailer
        if t is None:
            return self.start_tailing()
        if self._configured_log or not t._missing or not self.discover:
            return False
        found = logfile.discover_client_log(None)
        if found is None or Path(found) == t.path:
            return False
        self.stop_tailing()
        with self._lock:
            self.log_path = Path(found)
        self.state.set_tailer(path=str(found))
        return self.start_tailing()

    def reader_alive(self):
        """True while a tailer exists and its thread runs."""
        t = self.tailer
        return bool(t is not None and t.running)

    def _heal_reader(self, now):
        """None when there is no dead reader; else True when it was
        restarted now, False while the restart waits for RESTART_MIN_S."""
        t = self.tailer
        if t is None or t.running or not self.tail_enabled:
            return None
        if now < self._next_restart:
            return False
        self._next_restart = now + RESTART_MIN_S
        with self._lock:
            if self.tailer is not t:
                return False  # stopped or replaced meanwhile
            t.start()
        self.tailer_restarts += 1
        if self.tailer_restarts == 1:
            LOG.warning("the Client.txt reader had stopped; restarted it")
        else:
            LOG.warning("the Client.txt reader had stopped again; restarted it "
                        "(%d restarts)", self.tailer_restarts)
        self._on_status({"type": "tailer_restarted", "restarts": self.tailer_restarts})
        return True

    def stop_tailing(self):
        with self._lock:
            t, self.tailer = self.tailer, None
        if t is not None:
            t.stop()
        self.state.set_tailer(reading=False)

    def replay(self, lines):
        """Feed fixture lines through the parser (demos and tests)."""
        n = 0
        for line in lines:
            if self.feed_line(line) is not None:
                n += 1
        return n

    def tick_summary(self, now=None):
        """UTIL-SESSION-SUMMARY, ZERO-CLICK: from the core's main loop. Set
        the quiet-log idle state (TEST-LIVE-EXIT) and close an idle play
        stretch (with the price movers the dashboard has; no
        request) and save any new card. Returns the saved card or None."""
        idle = self.state.log_idle_due(now)  # TEST-LIVE-EXIT (decision 0029)
        if idle or self.state.session_end_due(now):
            movers = None
            if self.web_data_enabled():
                movers = self.rates.snapshot().get("movers")
            if idle:
                self.state.check_log_idle(now=now, movers=movers)
            self.state.check_session_end(now=now, movers=movers)
        # RUN-DURABLE-STORES: a card whose save failed waits in the queue
        # and is written from a later tick with back-off
        self._flush("summary")
        card = self.state.session_summary
        if not card or card.get("id") == self._summary_saved:
            return None
        self._summary_saved = card.get("id")
        with self._lock:
            self._summary_pending.append(card)
            del self._summary_pending[:-summary_mod.MAX_SAVED]
            self.savers["summary"].mark()
        self._flush("summary")
        return card

    def tick_sources(self, now=None):
        """TEST-FULLSTACK-SSE-IDLE, from the core's main loop: expire trade
        cards and publish the calc on / running state and the poe.ninja
        rates / price book check times in the snapshot, so turning the calc
        on or off and a price book refresh reach SSE clients at once. No
        request (one local config stat per tick; read only on change)."""
        self.state.expire_trades(now)
        # UTIL-UNDERLEVEL: the threshold setting (read only on change)
        self.state.set_underlevel_gap(self._config().get(underlevel.CONFIG_KEY))
        # UTIL-CAMPAIGN-CHECKS: the boots level setting (read only on change)
        self.state.set_campaign(boots_level=self._config().get(campaign.CONFIG_KEY))
        # AREA-AUDIT P7-6: the flask table again when its file changed (one
        # stat per tick; FlaskCache reads only on a new mtime / size)
        self.state.set_campaign(flasks=self.flask_table.get())
        # HOT-RELOAD: the zone level table likewise (it was read at start only)
        self.state.set_zone_table(self.zone_table.get())
        try:
            calc_on = self.tc_calc_enabled()
        except Exception:  # noqa: BLE001 - a bad config reads as off
            calc_on = False
        book = getattr(self.rates, "book", None)
        book_at = None
        if book is not None:
            stamps = [t.get("checked_at") for t in (book.doc.get("types") or {}).values()
                      if isinstance(t, dict) and isinstance(t.get("checked_at"), (int, float))]
            book_at = max(stamps) if stamps else None
        rates_at = self.rates.doc.get("checked_at")
        return self.state.set_sources(
            calc_on=calc_on, calc_running=self.tc_provider.running(),
            rates_checked_at=rates_at if isinstance(rates_at, (int, float)) else None,
            book_checked_at=book_at)

    def reload_notes(self):
        """HOT-RELOAD: one line per data file holding its last good copy,
        then the supervisor's code reload error, if any."""
        notes = list(hotreload.REGISTRY.notes())
        code = hotreload.read_code_error(self.code_status.get())
        if code:
            notes.append(code)
        return notes

    def tick_reload(self):
        """HOT-RELOAD, ZERO-CLICK, from the core's main loop: stat the
        registered data files (re-read on change), and in a source checkout
        scan web/ (stat only, at most once a second); a change bumps
        reload_web, which every SSE stream sends as a "reload" event. A new
        or cleared note refreshes the Checks card at once. True when the
        dashboard was told to reload."""
        hotreload.REGISTRY.poll()
        notes = self.reload_notes()
        if notes != self._reload_notes:
            self._reload_notes = notes
            self.tick_diag(force=True)
        if self.web_watch is not None and self.web_watch.poll():
            self.reload_web += 1
            self.bus.wake_all()
            return True
        return False

    def tick_calc(self):
        """AREA-AUDIT P3-6, from the core's main loop: stop the shared calc
        process once the user turned "tc_calc" off. True when it stopped."""
        return self.tc_provider.reap()

    # -- DIAG-SELF (ruling J)
    DIAG_TICK_S = 5.0

    def diag_facts(self, now=None):
        """The local facts the checks read (diag.checks). Keys starting
        with "_" are the values the report must mask, never shown.
        RUN-SEAMS: plug modules' facts(core, now) are merged in; a
        built-in key always wins."""
        now = time.time() if now is None else now
        snap = self.state.snapshot()
        tl = snap.get("tailer") or {}
        log = self.log_path
        try:
            log_found = bool(log) and Path(log).is_file()
        except OSError:
            log_found = False
        rates = self.rates.doc if isinstance(self.rates.doc, dict) else {}
        calc_on = self.tc_calc_enabled()
        st = None
        try:
            st = self.procs_status()
        except Exception:  # noqa: BLE001 - a process list error reads unknown
            st = None
        def live(name):
            return bool(((st or {}).get(name) or {}).get("live")) if st else None
        overlay = live("overlay")
        hk_file = self.hotkeys_runtime()
        try:
            zones_at = self._zones_path.stat().st_mtime
        except OSError:
            zones_at = None
        all_paths = {}
        if self._real:
            try:
                all_paths = {"_repo": str(paths.repo_root()),
                             "_sidecar": str(paths.sidecar_root())}
            except Exception:  # noqa: BLE001
                all_paths = {}
        built = dict(all_paths, **{
            "log_found": log_found, "log_configured": bool(self._configured_log),
            "consented": bool(tl.get("consented")),
            # RUN-TAIL-HEAL-CORE: the flag follows the reader thread, so a
            # dead reader never reads PASS before it is restarted
            "reading": bool(tl.get("reading")) and self.reader_alive(),
            "unreadable": bool(tl.get("unreadable")),
            "last_line_at": tl.get("last_line_at"),
            "idle": bool(tl.get("idle")), "character_seen": bool(snap.get("character")),
            "lang": (snap.get("lang") or {}).get("verdict"),
            "web_data": self.web_data_enabled(), "contact_set": self.contact() is not None,
            "book_checked_at": (snap.get("sources") or {}).get("book_checked_at")
                               or (snap.get("sources") or {}).get("rates_checked_at"),
            "book_error": rates.get("last_error"),
            "calc_on": calc_on, "calc_status": self.calc_status() if calc_on else None,
            "snapshot": bool((snap.get("acts") or {}).get("levels")),
            "snapshot_at": zones_at,
            "overlay": overlay, "supervisor": live("supervisor"),
            # HOTKEYS-LIVE (OVL-KEYS-CORE): the keys view from the client's
            # runtime file; the overlay log is read only while there is none
            "hotkeys": self.hotkeys_view() if hk_file is not None else None,
            "hotkey": (diag.hotkey_registered(self.overlay_log)
                       if overlay and hk_file is None else None),
            "port": self.port,
            "reload_notes": self.reload_notes(),
            # GGG-DOCS-WATCH (decision 0044): tools/ggg_docs_watch.py flag
            "ggg_reg_open": self._ggg_reg_open(),
            # SEC-ACL-CHECK: folder names from the start-up audit, no path
            "acl_open": list(self.acl_open) if self.acl_open is not None else None,
            # OBS-CRASH: why the core and the desktop client last exited
            # (this core's runtime dir; missing file = None)
            "last_exit": exitrecord.read(self.runtime),
            "client_exit": exitrecord.read_client(self.runtime),
            "started_at": self.started_at,
            "_log_path": str(log) if log else None,
            "_contact": self.contact(), "_character": snap.get("character"),
        })
        return dict(diag_data.facts(self, plug.collect_facts(self, now)), **built)

    def _ggg_reg_open(self):
        """True while the dev docs watch's REG_OPEN flag exists (a stat of a
        local file; a test core never reads the live runtime dir)."""
        if not self._real:
            return False
        try:
            return (paths.runtime_dir() / "ggg_docs" / "REG_OPEN").is_file()
        except OSError:
            return False

    def hotkeys_runtime(self):
        """The client's hotkeys file (hotkeys.read_runtime), re-read only
        when its (mtime, size) changed; None while it is missing."""
        try:
            st = self.hotkeys_path.stat()
            key = (st.st_mtime_ns, st.st_size)
        except OSError:
            key = None
        if key != self._hotkeys_stat:
            self._hotkeys_stat = key
            self._hotkeys_runtime = (hotkeys.read_runtime(self.runtime)
                                     if key is not None else None)
        return self._hotkeys_runtime

    def hotkeys_view(self):
        """The effective keys view (hotkeys.view) from the config and the
        client's runtime file."""
        return hotkeys.view(self._config(), self.hotkeys_runtime())

    def publish_hotkeys(self):
        """Publish the keys view; True when it changed."""
        return self.state.set_hotkeys(self.hotkeys_view())

    def set_hotkey(self, name, key):
        """POST /api/hotkeys: store one shortcut ("eval" or "toggle") in
        config/local.json (eval_hotkey / overlay_toggle), canonical. The
        client re-registers on its config change hook (decision 0058); the
        core registers nothing and sends nothing anywhere. Raises
        ValueError with the refusal sentence (a game key, the other
        shortcut's key) and ConfigUnreadable (an OSError) on a broken file;
        returns the published view."""
        ok = hotkeys.check_new(name, key, self._config(), self.hotkeys_view())
        self._write_config({hotkeys.CONFIG_KEYS[name]: ok})
        view = self.hotkeys_view()
        self.state.set_hotkeys(view)
        return view

    def tick_diag(self, now=None, force=False):
        """DIAG-SELF, ZERO-CLICK: from the core's loop, at most once per
        DIAG_TICK_S, publish the checks view. No request, no game probe.
        HOTKEYS-LIVE: the keys view is published on every pass (a stat of
        the client's runtime file; read only when it changed)."""
        self.publish_hotkeys()
        mono = time.monotonic()
        if not force and mono < self._next_diag:
            return False
        self._next_diag = mono + self.DIAG_TICK_S
        now = time.time() if now is None else now
        return self.state.set_diag(diag.view(self.diag_facts(now), VERSION, now=now))

    def close(self):
        stop = getattr(self, "_acl_stop", None)
        if stop is not None:
            stop.set()  # SEC-ACL-CHECK: a pending audit never starts
        self.stop_tailing()
        # TC-PRESS-STAGED-LIVE: no stage is published after close; the
        # worker is joined once the bridge stop ends a calc call in flight
        self.last_eval.close(timeout=0)
        self.tc_provider.close()  # AUDIT-TC-WIRE: stop the bridge if started
        self.last_eval.close()
