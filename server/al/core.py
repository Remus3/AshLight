"""Wiring: consent -> tailer -> parser -> bus -> state.

Decision 0003: the tailer never starts until the user's opt-in is recorded in
ops/runtime/consent.json. Revoking consent stops it.
"""

import datetime as _dt
import json
import os
import threading
from pathlib import Path

from . import VERSION, layout, logfile, parser, paths
from .bus import EventBus
from .state import SessionState
from .theorycraft import store as build_store


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
                 character=None, start_at_end=True, config_path=None):
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
        self.builds = build_store.BuildStore(build_store.default_path(self.runtime))

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
                                         start_at_end=self.start_at_end)
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
