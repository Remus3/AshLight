"""UTIL-PACE: levelling pace from the player's level-up lines.

Client.txt carries no experience numbers, only `<name> (<class>) is now
level <n>`, so pace is measured in levels: the average time per level over
the last few level-ups and the levels gained per hour this session. Only
the player's own level-ups count (SessionState filters them). In memory,
like the rest of the session (decision 0008). No network, no game input.
"""

import collections

LAST_LEVELS = 5
MIN_HOUR_S = 600.0  # levels an hour shows after 10 minutes of session


def _clock(s):
    s = max(0, int(s))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


class Pace:
    """Not thread-safe: the SessionState lock guards it."""

    def __init__(self):
        self.ups = collections.deque(maxlen=LAST_LEVELS + 1)
        self.gained = 0
        self.reset_at = None

    def on_level(self, level, at):
        if not isinstance(level, int) or at is None:
            return False
        if self.ups and level <= self.ups[-1][0]:
            # A lower or equal level is another character: start over.
            self.ups.clear()
            self.gained = 0
            self.reset_at = at
        self.ups.append((level, at))
        self.gained += 1
        return True

    def view(self, now, session_started_at):
        """The `pace` part of the state snapshot. The hourly rate needs 2+
        level-ups (one is no rate) and counts from the session start, or
        from the character change that reset the count."""
        per = None
        n = len(self.ups) - 1
        if n >= 1:
            span = self.ups[-1][1] - self.ups[0][1]
            gained = self.ups[-1][0] - self.ups[0][0]
            if gained > 0 and span >= 0:
                per = span / gained
        per_hour = None
        base = self.reset_at if self.reset_at is not None else session_started_at
        elapsed = None if base is None or now is None else now - base
        if self.gained >= 2 and elapsed is not None and elapsed >= MIN_HOUR_S:
            per_hour = self.gained / (elapsed / 3600.0)
        parts = []
        if per is not None:
            gained = self.ups[-1][0] - self.ups[0][0]
            if gained == 1:
                parts.append(f"about {_clock(per)} for the last level")
            else:
                parts.append(f"about {_clock(per)} per level over the last "
                             f"{gained} levels")
        if per_hour is not None:
            rate = f"{per_hour:.1f}"
            parts.append(f"{rate} level{'' if rate == '1.0' else 's'} an hour "
                         "this session")
        text = ("Pace: " + ", ".join(parts) + ".") if parts else ""
        return {"per_level_s": per, "per_hour": per_hour, "text": text}
