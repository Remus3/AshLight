"""Wiring: consent -> tailer -> parser -> bus -> state.

Decision 0003: the tailer never starts until the user's opt-in is recorded in
ops/runtime/consent.json. Revoking consent stops it.
"""

import datetime as _dt
import hashlib
import json
import os
import threading
import time
from pathlib import Path

from . import (VERSION, acts, campaign, layout, logfile, ninja, parser, paths, price, pricebook,
               pricewatch, resume, runhistory, settingsio, tradestats, underlevel,
               webfetch)
from . import hints, mapladder  # NEWBIE-HINTS, UTIL-MAP-LADDER
from . import summary as summary_mod
from .bus import EventBus
from .state import SessionState
from .theorycraft import basetypes
from .theorycraft import calcwire, health, pobout, skillsplit
from .theorycraft import item as item_mod
from .theorycraft import live as tc_live
from .theorycraft import shareurl
from .theorycraft import store as build_store
from .theorycraft import treedata
from .theorycraft import weights as weights_mod


def _utc_now():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_private(path, text):
    """Write text, then restrict to the owner where the OS allows (0600)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="ascii", newline="\n") as fh:
        fh.write(text)
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


# TEST-E2E: how often a consented core without a running tailer looks for
# Client.txt again (a few stat calls and one libraryfolders.vdf read).
LOCATE_RETRY_S = 5.0


class ConfigUnreadable(OSError):
    """AREA-AUDIT P5-1: config/local.json exists but is not a JSON object;
    nothing is written over it."""


class Core:
    def __init__(self, runtime=None, log_path=None, tail=True, poll_s=None,
                 character=None, start_at_end=True, config_path=None, web_fetch=None):
        self.runtime = Path(runtime) if runtime else paths.runtime_dir()
        self.consent_path = self.runtime / "consent.json"
        # A test core (runtime given) never reads or writes the real config.
        if config_path is not None:
            self.config_path = Path(config_path)
        elif runtime is None:
            self.config_path = paths.local_config_file()
        else:
            self.config_path = self.runtime / "local.json"
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
        self._lock = threading.Lock()
        self.locate_log()
        self.state.set_tailer(consented=self.consented())
        self.state.set_overlay_layout(layout.load(self.config_path))
        # TC-CODE: the last loaded PoB build reloads on start (no click).
        # DATA-TREE-SRC: node names from the cached GGG tree export when the
        # build-time snapshot fetched it; a test core never reads the sidecar.
        tree_path = (treedata.default_path() if runtime is None
                     else self.runtime / "gamedata" / treedata.FILE_NAME)
        self.builds = build_store.BuildStore(build_store.default_path(self.runtime),
                                             tree=treedata.TreeCache(tree_path))
        # HUD-ACT: zone levels from the cached world areas export when the
        # build-time snapshot fetched it (decision 0020); read only, no fetch.
        zones_path = (acts.default_path() if runtime is None
                      else self.runtime / "gamedata" / acts.FILE_NAME)
        self.zone_table = acts.TableCache(zones_path)
        self.state.set_zone_table(self.zone_table.get())
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
        self.last_eval = tc_live.attach(self.builds, self.weights, self.state,
                                        league=self.trade_league,
                                        calc=lambda: (self.tc_calc if self.tc_calc is not None
                                                      else self.tc_provider()),
                                        rates=lambda: self.rates.snapshot(),
                                        trade_ids=lambda: (self.trade_ids.get()
                                                           if self.web_data_enabled() else {}))
        # MATH-NEXT-LOOK: the build view ranks "look for next" stats with the
        # weights PoB measured for this build (never another build's)
        self.builds.weights_for = self.last_eval.pob_weights.fallback
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
        # NEWBIE-HINTS (ruling L): hashed character keys and hint ids only
        self.state.use_hint_store(self.runtime / hints.FILE_NAME)
        # UTIL-PRICE-WATCH: the last priced presses, one bounded runtime
        # file; re-read from the cache on a price book refresh only.
        self.watch = pricewatch.PriceWatch(self.runtime / pricewatch.FILE_NAME)
        self._watch_key = None

    def _outputs_ready(self):
        """A new PoB output table for the loaded build: the build view is
        read again (the state's build summary gets a new calc_rev). AREA-AUDIT
        P7-4: the bump runs under the state lock (no read-then-write here)."""
        self.state.bump_calc_rev()

    def eval_press(self, text, slot=None):
        """One item-hotkey press (POST /api/eval): the item check and at most
        one price check, both stamped with the same press time so the
        overlay merges them (decision 0016 Fork 2). The text is the app's one
        clipboard read for this press; nothing here reads the clipboard. The
        price check is an offline trade-search link (decision 0017)."""
        at = self.state.now()
        result = self.last_eval.run(text, slot, at=at)
        doc = self.price.request(text, at=at)
        self._watch_press(text, doc, at)
        return result

    def _watch_press(self, text, doc, at):
        """UTIL-PRICE-WATCH: remember what this press already priced (the
        cached poe.ninja value on its card); nothing more is read."""
        ninja = doc.get("ninja") if isinstance(doc, dict) else None
        if not ninja or not isinstance(doc.get("item"), dict):
            return False
        flags = getattr(item_mod.parse(text), "flags", None) or {}
        item = dict(doc["item"], corrupted=bool(flags.get("corrupted")
                                                or flags.get("twice_corrupted")))
        try:
            with self._lock:
                saved = self.watch.record(item, ninja, at)
        except OSError:
            return False
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
            raise ConfigUnreadable("config/local.json is unreadable") from e
        if not isinstance(cfg, dict):
            raise ConfigUnreadable("config/local.json is not a JSON object")
        return cfg

    def _write_config(self, update):
        """Merge `update` into the local config and persist it, keeping
        every other key (the contact included; never written here).
        Raises ConfigUnreadable (an OSError) on a hand-broken file."""
        with self._lock:
            cfg = self._read_config_strict()
            cfg.update(update)
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.config_path.with_name(self.config_path.name + ".tmp")
            with open(tmp, "w", encoding="ascii", newline="\n") as fh:
                fh.write(json.dumps(cfg, indent=2, ensure_ascii=True) + "\n")
            tmp.replace(self.config_path)
            return cfg

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

    # -- UTIL-RUN-HISTORY
    def history_enabled(self):
        return runhistory.enabled_setting(self._config().get(runhistory.CONFIG_KEY))

    def tick_history(self):
        """From the core's loop: save the current run when an act split
        closed or the run finished (and history is on), then publish the
        history view. No request. True when the file was written."""
        rec = self.state.run_record()
        on = self.history_enabled()
        wrote = False
        key = None
        if rec is not None:
            key = (rec["started_at"], rec["closed"], rec["finished"])
        if on and rec is not None and rec["closed"] and key != self._history_key:
            try:
                with self._lock:
                    wrote = self.history.record(rec)
                self._history_key = key
            except OSError:
                pass  # the view still shows; the next tick tries again
        # UTIL-MULTICHAR (decision 0038): the player's other characters'
        # runs (rebuilt at core start, or parked by a switch) are saved
        # too, each under its own name, and every character gets a view.
        names = self.state.character_names()
        current = names[0] if names else None
        for name in names[1:]:
            prec = self.state.parked_record(name)
            if not on or prec is None or not prec["closed"]:
                continue
            pkey = (prec["started_at"], prec["closed"], prec["finished"])
            if self._parked_keys.get(name) == pkey:
                continue
            try:
                with self._lock:
                    wrote = self.history.record(prec) or wrote
                self._parked_keys[name] = pkey
            except OSError:
                pass
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

    def tick_ladder(self, on=None):
        """UTIL-MAP-LADDER: save the session's finished maps (run history
        on) and publish the all-sessions ladder; off publishes none. True
        when the file was written."""
        if on is None:
            on = self.history_enabled()
        if not on:
            self.state.set_map_ladder(None)
            return False
        character, rows = self.state.map_ladder_rows()
        since = self._ladder_since
        if since is not None:
            rows = [r for r in rows if isinstance(r.get("opened_at"), (int, float))
                    and r["opened_at"] > since]
        wrote = False
        try:
            with self._lock:
                wrote = self.ladder.record(character, [r for r in rows if r.get("done")])
        except OSError:
            pass  # the view still shows; the next tick tries again
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
                self._ladder_since = self.state.now()
                self._history_key = ((rec["started_at"], rec["closed"], rec["finished"])
                                     if rec else None)
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
        if key != self._watch_key:
            if on:
                try:
                    with self._lock:
                        changed = self.watch.refresh(self.rates.lookup)
                except OSError:
                    pass
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
            cfg = {}
        self._config_cache = (key, cfg if isinstance(cfg, dict) else {}, digest, stable)
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

    def configured_league(self):
        value = self._config().get("league")
        return value if isinstance(value, str) and value.strip() else None

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
        (the contact included; it is never written here). AREA-AUDIT
        P5-1: raises ConfigUnreadable on a hand-broken file."""
        self._write_config({"web_data": bool(enabled)})
        if enabled:
            self.rates.refresh_async()
        return bool(enabled)

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
        found = logfile.discover_client_log(self._configured_log)
        if found is None and self._configured_log:
            found = Path(self._configured_log)  # may appear later
        self.log_path = found
        self.state.set_tailer(path=str(found) if found else None)
        return found

    # -- consent
    def consent_record(self):
        try:
            return json.loads(self.consent_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def consented(self):
        return bool(self.consent_record().get("consented"))

    def record_consent(self, consented, path=None):
        if path and not logfile.consent_path_ok(path):
            # AUDIT-HTTP-HARDEN S4: checked before any file system access.
            raise ValueError("path must be a local Client.txt or the folder holding it")
        if path:
            self._configured_log = path
            self.locate_log()
        rec = {"consented": bool(consented), "at": _utc_now(), "app_version": VERSION,
               "file": "Client.txt", "derives": ["zone", "level", "deaths",
                                                 "whispers", "session times"]}
        write_private(self.consent_path, json.dumps(rec, indent=1) + "\n")
        self.state.set_tailer(consented=bool(consented))
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
        self.state.set_overlay_layout(saved)
        return saved

    def displays(self):
        return layout.read_displays(self.runtime)

    # -- tailing
    def feed_line(self, line):
        ev = parser.parse_line(line)
        if ev is not None:
            self.bus.publish(ev)
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
        LOCATE_RETRY_S. True when a tailer was started."""
        now = time.monotonic() if now is None else now
        if now < self._next_locate:
            return False
        self._next_locate = now + LOCATE_RETRY_S
        if not self.tail_enabled or not self.consented():
            return False
        t = self.tailer
        if t is None:
            return self.start_tailing()
        if self._configured_log or not t._missing:
            return False
        found = logfile.discover_client_log(None)
        if found is None or Path(found) == t.path:
            return False
        self.stop_tailing()
        with self._lock:
            self.log_path = Path(found)
        self.state.set_tailer(path=str(found))
        return self.start_tailing()

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
        card = self.state.session_summary
        if not card or card.get("id") == self._summary_saved:
            return None
        self._summary_saved = card.get("id")
        try:
            summary_mod.save(self.summary_path, card)
        except OSError:
            pass  # the card still shows; the next one tries again
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

    def tick_calc(self):
        """AREA-AUDIT P3-6, from the core's main loop: stop the shared calc
        process once the user turned "tc_calc" off. True when it stopped."""
        return self.tc_provider.reap()

    def close(self):
        self.stop_tailing()
        self.tc_provider.close()  # AUDIT-TC-WIRE: stop the bridge if started
