"""PRICE-1 (server part): the ONE shared trade2 rate limiter, its request
queue, and a search-query builder for a parsed item (research 0004).

Rate limits are never hard-coded (official docs: limits "can change at any
time"). Every response's headers are parsed:
- X-Rate-Limit-Policy: the policy name; endpoints may share one, and then
  they share one limiter state;
- X-Rate-Limit-Rules: the rule names (ip, account, client, ...);
- X-Rate-Limit-<rule>: "max:period:restriction[,...]";
- X-Rate-Limit-<rule>-State: "hits:period:active restriction[,...]";
- Retry-After on 429 (fallback 60 s).
Before the first response of a policy only one request is in flight (the
queue is serial anyway). One hit of headroom under the tightest window is
kept because state headers lag. A 429 or an active restriction stops every
request of that policy until it expires.

Nothing is sent unless the web-data opt-in is on; no cookie is ever sent
(no POESESSID); the User-Agent names AshLight and its version. This module
never reads the clipboard and never sends anything to the game.
"""

import collections
import json
import logging
import queue
import re
import threading
import time
import urllib.parse

from . import webfetch

log = logging.getLogger("al.trade")

BASE = "https://www.pathofexile.com"
ALLOWED_HOSTS = ("www.pathofexile.com",)
SEARCH_PATH = "/api/trade2/search/poe2/{league}"
FETCH_PATH = "/api/trade2/fetch/{ids}?query={query}"
USER_AGENT = webfetch.user_agent("price check on user request")
RETRY_AFTER_DEFAULT_S = 60.0
HEADROOM = 1
MAX_BYTES = 2 * 1024 * 1024
FETCH_BATCH = 10
MAX_WAIT_S = 3600.0


def _floats(text):
    out = []
    for part in (text or "").split(","):
        bits = part.strip().split(":")
        if len(bits) != 3:
            continue
        try:
            out.append(tuple(float(b) for b in bits))
        except ValueError:
            continue
    return out


def parse_rate_headers(headers):
    """{"policy", "rules": {rule: [{"max", "period", "restrict", "hits",
    "active"}]}, "retry_after"} from response headers (missing parts
    omitted / None)."""
    policy = webfetch.header(headers, "X-Rate-Limit-Policy")
    names = [n.strip() for n in (webfetch.header(headers, "X-Rate-Limit-Rules") or "").split(",")
             if n.strip()]
    rules = {}
    for name in names:
        limits = _floats(webfetch.header(headers, f"X-Rate-Limit-{name}"))
        states = _floats(webfetch.header(headers, f"X-Rate-Limit-{name}-State"))
        windows = []
        for i, (mx, period, restrict) in enumerate(limits):
            hits, active = 0.0, 0.0
            # match the state window by period, else by position
            match = [s for s in states if s[1] == period] or (
                [states[i]] if i < len(states) else [])
            if match:
                hits, active = match[0][0], match[0][2]
            windows.append({"max": int(mx), "period": period, "restrict": restrict,
                            "hits": int(hits), "active": active})
        for hits, period, active in states:  # a state with no limit line
            if not any(w["period"] == period for w in windows) and active > 0:
                windows.append({"max": 0, "period": period, "restrict": active,
                                "hits": int(hits), "active": active})
        rules[name.lower()] = windows
    retry = webfetch.header(headers, "Retry-After")
    try:
        retry = float(retry) if retry is not None else None
    except ValueError:
        retry = None
    return {"policy": policy, "rules": rules, "retry_after": retry}


class _Policy:
    def __init__(self):
        self.windows = []  # from the last response: dicts as parse_rate_headers
        self.reported_at = None
        self.sent = collections.deque(maxlen=1000)  # our own request times
        self.blocked_until = 0.0
        self.known = False


class RateLimiter:
    """Data-driven limiter keyed by policy. Endpoint kinds ("search",
    "fetch", ...) map to the policy their responses name, so endpoints that
    share a policy share its state. Thread-safe."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self._lock = threading.Lock()
        self._kind_policy = {}
        self._policies = {}

    def _policy(self, kind):
        name = self._kind_policy.get(kind, "kind:" + kind)
        return self._policies.setdefault(name, _Policy())

    def wait_s(self, kind, now=None):
        """Seconds to wait before a request of this kind may be sent (0 = now)."""
        now = self.clock() if now is None else now
        with self._lock:
            p = self._policy(kind)
            wait = max(0.0, p.blocked_until - now)
            for w in p.windows:
                period, cap = w["period"], w["max"]
                if cap <= 0 or period <= 0:
                    continue
                allowed = max(1, cap - HEADROOM) if cap > 1 else cap
                own = [t for t in p.sent if now - t < period]
                reported = w["hits"] if (p.reported_at is not None
                                         and now - p.reported_at < period) else 0
                if max(len(own), reported) < allowed:
                    continue
                if len(own) >= allowed:
                    # wait until enough of our own hits leave the window
                    idx = len(own) - allowed
                    wait = max(wait, own[idx] + period - now)
                else:
                    wait = max(wait, p.reported_at + period - now)
            return min(wait, MAX_WAIT_S)

    def note_sent(self, kind, now=None):
        now = self.clock() if now is None else now
        with self._lock:
            self._policy(kind).sent.append(now)

    def update(self, kind, status, headers, now=None):
        """Feed a response: learn the policy, its windows, restrictions."""
        now = self.clock() if now is None else now
        info = parse_rate_headers(headers)
        with self._lock:
            old = self._policy(kind)
            if info["policy"]:
                name = info["policy"]
                if self._kind_policy.get(kind) != name:
                    self._kind_policy[kind] = name
                    p = self._policies.setdefault(name, _Policy())
                    p.sent.extend(old.sent)
                    p.blocked_until = max(p.blocked_until, old.blocked_until)
            p = self._policy(kind)
            windows = [w for ws in info["rules"].values() for w in ws]
            if windows:
                p.windows = windows
                p.reported_at = now
                p.known = True
            active = max([w["active"] for w in windows] or [0.0])
            if active > 0:
                p.blocked_until = max(p.blocked_until, now + active)
            if status == 429:
                retry = info["retry_after"]
                if retry is None or retry < 0:
                    retry = RETRY_AFTER_DEFAULT_S
                p.blocked_until = max(p.blocked_until, now + max(retry, active))
            return info

    def status(self, now=None):
        now = self.clock() if now is None else now
        with self._lock:
            return {name: {"blocked_s": round(max(0.0, p.blocked_until - now), 1),
                           "windows": [dict(w) for w in p.windows], "known": p.known}
                    for name, p in self._policies.items()}


class TradeClient:
    """One serial queue in front of the shared limiter. submit() returns a
    Future-like Job; the worker waits for the limiter, sends, and feeds the
    response headers back. enabled() is the web-data opt-in."""

    def __init__(self, enabled=lambda: False, fetch=None, limiter=None,
                 sleep=time.sleep, clock=time.monotonic):
        self.enabled = enabled
        self.fetch = fetch
        self.limiter = limiter or RateLimiter(clock=clock)
        self.sleep = sleep
        self._q = queue.Queue()
        self._worker = None
        self._wlock = threading.Lock()

    def _ensure_worker(self):
        with self._wlock:
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._run, name="al-trade",
                                                daemon=True)
                self._worker.start()

    def submit(self, kind, method, url, body=None):
        webfetch.require_opt_in(self.enabled)
        webfetch.check_url(url, ALLOWED_HOSTS)
        job = Job(kind, method, url, body)
        self._q.put(job)
        self._ensure_worker()
        return job

    def run_one(self, job):
        """Send one job now (after the limiter wait). Used by the worker and
        by tests; re-checks the opt-in right before sending."""
        try:
            while True:
                webfetch.require_opt_in(self.enabled)
                wait = self.limiter.wait_s(job.kind)
                if wait <= 0:
                    break
                job.waiting_s = wait
                self.sleep(min(wait, 5.0))
            headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
            data = None
            if job.body is not None:
                headers["Content-Type"] = "application/json"
                data = json.dumps(job.body, separators=(",", ":")).encode("utf-8")
            self.limiter.note_sent(job.kind)
            status, rh, raw = webfetch.request(job.method, job.url, headers, ALLOWED_HOSTS,
                                               body=data, fetch=self.fetch,
                                               max_bytes=MAX_BYTES, max_redirects=0)
            self.limiter.update(job.kind, status, rh)
            if status != 200:
                raise webfetch.FetchError(f"trade HTTP {status}")
            job.result = json.loads(raw)
        except (webfetch.FetchError, ValueError) as e:
            job.error = str(e)
        finally:
            job.done.set()
        return job

    def _run(self):
        while True:
            try:
                job = self._q.get(timeout=30)
            except queue.Empty:
                return
            self.run_one(job)


class Job:
    def __init__(self, kind, method, url, body):
        self.kind, self.method, self.url, self.body = kind, method, url, body
        self.result = None
        self.error = None
        self.waiting_s = 0.0
        self.done = threading.Event()

    def wait(self, timeout=None):
        self.done.wait(timeout)
        return self


# -- query building -------------------------------------------------------

def search_url(league):
    if not isinstance(league, str) or not league.strip():
        raise ValueError("league required")
    return BASE + SEARCH_PATH.format(league=urllib.parse.quote(league.strip(), safe=""))


def fetch_url(ids, query_id):
    ids = [i for i in ids if isinstance(i, str) and i.isalnum()][:FETCH_BATCH]
    if not ids or not isinstance(query_id, str) or not query_id.isalnum():
        raise ValueError("result ids and query id required")
    return BASE + FETCH_PATH.format(ids=",".join(ids), query=query_id)


_MIN_FACTOR = 0.9  # search mods at >= 90 percent of the rolled value
_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def build_query(item, stat_ids=None, online=True):
    """A trade2 search body for a parsed item (theorycraft.item.ParsedItem).

    Uniques search by name + base; other items by base type plus each mod
    whose text maps to a trade stat id in stat_ids (mod text with numbers
    replaced by "#" -> "explicit.stat_..."), min at 90 percent of the roll.
    Without stat_ids only the base / name query is built (the stat-id table
    comes from /api/trade2/data/stats, not fetched yet: PRICE-1 remains).
    The "misc_filters" / "corrupted" filter names follow the trade site's
    query shape and are UNVERIFIED for trade2 (research 0004)."""
    if item is None or not getattr(item, "is_item", False):
        raise ValueError("not an item")
    q = {"status": {"option": "online" if online else "any"}}
    rarity = (item.rarity or "").lower()
    if rarity == "unique" and item.name:
        q["name"] = item.name
        if item.base:
            q["type"] = item.base
    elif item.base:
        q["type"] = item.base
    else:
        raise ValueError("item has no base type")
    filters = []
    for mod in item.mods if rarity != "unique" else []:
        key = mod_key(mod.text)
        sid = (stat_ids or {}).get(key)
        if not sid:
            continue
        f = {"id": sid}
        nums = [v for v in mod.values if isinstance(v, (int, float))]
        if nums:
            f["value"] = {"min": round(nums[0] * _MIN_FACTOR, 2)}
        filters.append(f)
    if filters:
        q["stats"] = [{"type": "and", "filters": filters}]
    misc = {}
    if item.flags.get("corrupted"):
        misc["corrupted"] = {"option": "true"}
    if misc:
        q["filters"] = {"misc_filters": {"filters": misc}}
    return {"query": q, "sort": {"price": "asc"}}


def mod_key(text):
    """Mod text with every number replaced by "#", signs kept (the trade
    stat text form, e.g. "+#% to Fire Resistance")."""
    return _NUM_RE.sub("#", (text or "").strip())
