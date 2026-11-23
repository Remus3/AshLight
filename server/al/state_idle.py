"""SessionState's idle and session summary as IdleMixin (TEST-STATE-MIXIN-C,
F-192, research 0047 R5 (2); the pattern is the loop's mixins,
tools/loop_inbox.py and tools/loop_merge.py).

UTIL-SESSION-SUMMARY: the open play stretch and its summary card;
TEST-LIVE-EXIT (decision 0029): the log idle state ("game may be closed",
Client.txt staleness only, never a process check) and the LIVE-RESUME
mtime seed. The methods moved verbatim from state.py: the lock is
SessionState's one lock, the event dispatcher (apply / _apply_locked) stays
in state.py and calls the helpers here. Stdlib only.
"""

from . import summary as summary_mod


class IdleMixin:
    """Mixed into state.SessionState. _init_idle() runs from __init__,
    _view_idle(now) from snapshot()."""

    def _init_idle(self):
        # UTIL-SESSION-SUMMARY: the open play stretch and its last card.
        self.stretch = summary_mod.Tracker()
        self.session_summary = None
        self._summary_ids = 0
        self._idle_paused_map = False  # AREA-AUDIT P3-4

    def _view_idle(self, now):
        """Caller holds the lock. The snapshot's idle and summary keys."""
        return {
            # decision 0029 amendment (DESKTOP-CLIENT): the 0029 idle
            # "game may be closed" state as one boolean; the overlay
            # hides while it is true
            "game_idle": bool(self.tailer.get("consented") and self.tailer.get("idle")),
            "session_summary": (dict(self.session_summary)
                                if self.session_summary else None),
        }

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
