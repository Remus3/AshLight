"""Wiring: consent -> tailer -> parser -> bus -> state.

Decision 0003: the tailer never starts until the user's opt-in is recorded in
ops/runtime/consent.json. Revoking consent stops it.
"""

import datetime as _dt
import json
import os
import threading
import time
from pathlib import Path

from . import VERSION, acts, layout, logfile, ninja, parser, paths, price, resume, webfetch
from .bus import EventBus
from .state import SessionState
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
        self._configured_log = log_path or cfg.get("client_log")
        self.log_path = None
        self.tailer = None
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
        # TC-EVAL: editable stat weights, defaults written on first start.
        self.weights = weights_mod.WeightsStore(weights_mod.default_path(self.runtime))
        # TC-VIEW / TC-EVAL-UI: build summary and last item check in the state.
        self.last_eval = tc_live.attach(self.builds, self.weights, self.state)
        # Web data (decision 0013): one default-off opt-in, "web_data" in the
        # local config; every outbound request goes through server/al/webfetch.py
        # with an injectable transport (tests pass web_fetch, never the network).
        self.web_fetch = web_fetch
        rates_dir = (ninja.cache_dir() if runtime is None
                     else self.runtime / "cache" / "ninja")
        # UA-CONTACT: poe.ninja also needs the "contact" key.
        self.rates = ninja.RatesClient(rates_dir, enabled=self.web_data_enabled,
                                       league=self.configured_league, fetch=web_fetch,
                                       contact=self.contact)
        # PRICE-TRADE-LINK (decision 0017): one offline trade-search link per
        # item-hotkey press (POST /api/eval), published as the decision 0016
        # card with the press time. No trade-site request is ever made and
        # the core never opens the link.
        self.price = price.PriceChecker(league=self.configured_league,
                                        card=self.state.set_price)

    def eval_press(self, text, slot=None):
        """One item-hotkey press (POST /api/eval): the item check and at most
        one price check, both stamped with the same press time so the
        overlay merges them (decision 0016 Fork 2). The text is the app's one
        clipboard read for this press; nothing here reads the clipboard. The
        price check is an offline trade-search link (decision 0017)."""
        at = self.state.now()
        result = self.last_eval.run(text, slot, at=at)
        self.price.request(text, at=at)
        return result

    # -- web data opt-in (decision 0013)
    def _config(self):
        try:
            cfg = json.loads(self.config_path.read_text(encoding="utf-8"))
            return cfg if isinstance(cfg, dict) else {}
        except (OSError, ValueError):
            return {}

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

    def set_web_data(self, enabled):
        """Persist the opt-in in the local config, keeping every other key
        (the contact included; it is never written here)."""
        with self._lock:
            cfg = self._config()
            cfg["web_data"] = bool(enabled)
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.config_path.with_name(self.config_path.name + ".tmp")
            with open(tmp, "w", encoding="ascii", newline="\n") as fh:
                fh.write(json.dumps(cfg, indent=2, ensure_ascii=True) + "\n")
            tmp.replace(self.config_path)
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
        recovered = [k for k in ("zone", "character", "class", "level", "area_id")
                     if fields.get(k) is not None]
        recovered += [k for k in ("deaths", "level_ups") if fields.get(k)]
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

    def close(self):
        self.stop_tailing()
