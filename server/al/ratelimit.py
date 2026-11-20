"""TC-GGG-RATELIMIT: a header-driven rate limiter for GGG API calls.

GGG's developer docs say the rate limit headers "should be parsed and
followed by your application" and that the limits "are dynamic and can
change at any time" (research 0001). This module follows them; it hard
codes no GGG limit:

- X-Rate-Limit-Policy: the policy name (kept for display only).
- X-Rate-Limit-Rules: a comma list of rule names. Any name is obeyed,
  known or not (Ip, Account, Client, or one GGG adds later).
- X-Rate-Limit-<rule>: comma list of windows "hits:period:restrict".
- X-Rate-Limit-<rule>-State: comma list "current:period:active", where
  active is the seconds of a restriction now in force (0 = none).
- Retry-After: delta-seconds or an HTTP-date; when present it replaces
  the block taken from an active restriction (shorter or longer). A
  window the server reports full still waits out its period (the
  stricter reading).
- A 429 with neither Retry-After nor an active restriction backs off by
  a floor (FLOOR_429_S), doubled per consecutive bare 429 up to
  FLOOR_429_MAX_S, reset by the next non-429 response.

Callers (the later GGG client, TC-GGG-CLIENT-CORE) use one key per
endpoint group: `wait_s(key)` before a request (sleep that long, or skip),
`note_request(key)` when it is sent, `observe(key, status, headers)` on
the answer. The clock is injected (`clock` monotonic seconds, `wall`
epoch seconds for an HTTP-date Retry-After). The wait is never negative
and never above MAX_WAIT_S.

Pure module: no request, no transport import, no file. State lives only
in this object's memory; a new limiter starts empty.
"""

import email.utils
import time

FLOOR_429_S = 60.0
FLOOR_429_MAX_S = 3600.0
MAX_WAIT_S = 86400.0          # a wait further out is clamped, never trusted past a day
MAX_HEADER_CHARS = 512        # a longer rate limit header is ignored as malformed
MAX_RULES = 16
MAX_WINDOWS = 16
MAX_PERIOD_S = 86400
MAX_HITS_KEPT = 4096          # own request times kept per key


def _header(headers, name):
    """Case-insensitive header lookup over a dict, a list of pairs or an
    email.message.Message; None when absent or too long."""
    if headers is None:
        return None
    want = name.lower()
    items = headers.items() if hasattr(headers, "items") else headers
    try:
        for k, v in items:
            if isinstance(k, str) and k.lower() == want:
                text = str(v).strip()
                if len(text) > MAX_HEADER_CHARS:
                    return None
                return text
    except (TypeError, ValueError):
        return None
    return None


def _ints(text, n):
    parts = text.strip().split(":")
    if len(parts) != n:
        return None
    out = []
    for p in parts:
        p = p.strip()
        if not p.isdigit():
            return None
        out.append(int(p))
    return out


def parse_windows(text):
    """'hits:period:restrict,...' -> [(hits, period, restrict)]; bad
    entries are dropped."""
    out = []
    if not text:
        return out
    for part in text.split(",")[:MAX_WINDOWS]:
        v = _ints(part, 3)
        if v is None or v[1] <= 0 or v[1] > MAX_PERIOD_S:
            continue
        out.append(tuple(v))
    return out


def parse_rules(text):
    """'Ip,Account' -> ['Ip', 'Account']; names are header tokens only."""
    out = []
    if not text:
        return out
    for name in text.split(",")[:MAX_RULES]:
        name = name.strip()
        if name and all(c.isalnum() or c in "-_" for c in name):
            out.append(name)
    return out


def retry_after_s(text, wall_now):
    """Seconds from a Retry-After value (delta-seconds or HTTP-date), or
    None when absent or unreadable. Never negative."""
    if not text:
        return None
    text = text.strip()
    if text.isdigit():
        return float(int(text))
    try:
        when = email.utils.parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None
    if when is None or when.tzinfo is None:
        return None
    return max(0.0, when.timestamp() - wall_now)


class _Window:
    __slots__ = ("hits", "period", "restrict", "server_current", "seen_at")

    def __init__(self, hits, period, restrict):
        self.hits = hits
        self.period = period
        self.restrict = restrict
        self.server_current = 0
        self.seen_at = None


class _Key:
    __slots__ = ("policy", "rules", "sent", "blocked_until", "bare_429s")

    def __init__(self):
        self.policy = None
        self.rules = {}          # rule name -> [_Window]
        self.sent = []           # monotonic times of own requests
        self.blocked_until = 0.0
        self.bare_429s = 0


class RateLimiter:
    """Per-key limiter following GGG's rate limit headers (memory only)."""

    def __init__(self, clock=None, wall=None):
        self._clock = clock or time.monotonic
        self._wall = wall or time.time
        self._keys = {}

    def _key(self, key):
        st = self._keys.get(key)
        if st is None:
            st = self._keys[key] = _Key()
        return st

    def _longest_period(self, st):
        best = 0
        for windows in st.rules.values():
            for w in windows:
                best = max(best, w.period)
        return best

    def note_request(self, key):
        """Record that a request under `key` is being sent now."""
        st = self._key(key)
        now = self._clock()
        st.sent.append(now)
        self._prune(st, now)

    def _prune(self, st, now):
        keep = self._longest_period(st)
        if keep:
            st.sent = [t for t in st.sent if t > now - keep]
        if len(st.sent) > MAX_HITS_KEPT:
            st.sent = st.sent[-MAX_HITS_KEPT:]

    def observe(self, key, status, headers):
        """Take the rate limit headers of one response under `key`."""
        st = self._key(key)
        now = self._clock()
        policy = _header(headers, "X-Rate-Limit-Policy")
        if policy:
            st.policy = policy
        names = parse_rules(_header(headers, "X-Rate-Limit-Rules"))
        if names:
            st.rules = {}
        restricted = 0.0
        for name in names:
            windows = [_Window(*w) for w in
                       parse_windows(_header(headers, "X-Rate-Limit-" + name))]
            states = parse_windows(_header(headers, "X-Rate-Limit-" + name + "-State"))
            for cur, period, active in states:
                if active > 0:
                    restricted = max(restricted, float(active))
                for w in windows:
                    if w.period == period:
                        w.server_current = cur
                        w.seen_at = now
            if windows:
                st.rules[name] = windows
        if restricted > 0:
            self._block(st, now, restricted)
        retry = retry_after_s(_header(headers, "Retry-After"), self._wall())
        if retry is not None:
            st.blocked_until = now + min(retry, MAX_WAIT_S)
        if status == 429:
            if retry is None and restricted <= 0:
                floor = min(FLOOR_429_S * (2 ** min(st.bare_429s, 16)),
                            FLOOR_429_MAX_S)
                st.bare_429s += 1
                self._block(st, now, floor)
            else:
                st.bare_429s = 0
        else:
            st.bare_429s = 0
        self._prune(st, now)

    def _block(self, st, now, seconds):
        st.blocked_until = max(st.blocked_until, now + min(seconds, MAX_WAIT_S))

    def wait_s(self, key):
        """Seconds to wait before the next request under `key` (>= 0)."""
        st = self._keys.get(key)
        if st is None:
            return 0.0
        now = self._clock()
        wait = st.blocked_until - now
        for windows in st.rules.values():
            for w in windows:
                wait = max(wait, self._window_wait(st, w, now))
        return max(0.0, min(wait, MAX_WAIT_S))

    def _window_wait(self, st, w, now):
        if w.hits <= 0:
            return float(w.period)
        start = now - w.period
        own = sorted(t for t in st.sent if t > start)
        wait = 0.0
        if len(own) >= w.hits:
            # the oldest hit that keeps the window full must age out
            wait = own[len(own) - w.hits] + w.period - now
        if w.seen_at is not None and w.seen_at > start:
            # the server's count at seen_at, plus own hits since then
            later = sum(1 for t in own if t > w.seen_at)
            if w.server_current + later >= w.hits:
                wait = max(wait, w.seen_at + w.period - now)
        return wait

    def policy(self, key):
        st = self._keys.get(key)
        return st.policy if st else None

    def rules(self, key):
        """{rule: [(hits, period, restrict)]} as last seen (a copy)."""
        st = self._keys.get(key)
        if st is None:
            return {}
        return {name: [(w.hits, w.period, w.restrict) for w in ws]
                for name, ws in st.rules.items()}
