"""poe.ninja PoE2 currency rates (ROADMAP DATA-NINJA, research 0005).

Only poe.ninja's documented economy endpoints are used (research 0005,
https://poe.ninja/docs/api, accessed 2026-11-16):
- GET /poe2/api/economy/leagues -> [{id, name}], first = current league;
- GET /poe2/api/economy/exchange/current/overview?league=<id>&type=Currency.

Etiquette kept: conditional requests (If-None-Match with the stored ETag),
at most one request per endpoint per MIN_INTERVAL_S (the league list at most
once per LEAGUE_INTERVAL_S, and never when the user configured a league), a
truthful User-Agent, one request at a time. The last-attempt time is
persisted with the cache, so a restart never refetches early; a failed
attempt counts as a request.

Nothing is requested unless the web-data opt-in is on (webfetch.WebDataOff)
and a User-Agent contact is configured (UA-CONTACT: poe.ninja's API docs ask
for one; `snapshot()["blocked"]` says "contact not set");
offline or opted out, `snapshot()` returns the cached rates with their age.
Cache: <sidecar>\\Cache\\ninja\\rates.json (server/al/paths.py).
"""

import json
import logging
import threading
import time
import urllib.parse
from pathlib import Path

from . import paths, webfetch

log = logging.getLogger("al.ninja")

ATTRIBUTION = ("Currency rates from poe.ninja (poe.ninja is not affiliated with or "
               "endorsed by Grinding Gear Games). This product isn't affiliated with "
               "or endorsed by Grinding Gear Games in any way.")
SHORT_CREDIT = "Prices: poe.ninja"
BASE = "https://poe.ninja"
ALLOWED_HOSTS = ("poe.ninja",)
LEAGUES_PATH = "/poe2/api/economy/leagues"
OVERVIEW_PATH = "/poe2/api/economy/exchange/current/overview"
OVERVIEW_TYPE = "Currency"
UA_PURPOSE = "currency rates from poe.ninja"
USER_AGENT = webfetch.user_agent(UA_PURPOSE)  # base form; requests add the contact
MIN_INTERVAL_S = 3600  # PoE2 data refreshes about hourly (research 0005)
LEAGUE_INTERVAL_S = 24 * 3600
STALE_AFTER_S = 2 * 3600
MAX_BYTES = 4 * 1024 * 1024
MAX_LINES = 2000
CACHE_NAME = "rates.json"


def cache_dir(environ=None):
    return paths.sidecar_dir("Cache", environ) / "ninja"


def _utc(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v) if v == v and abs(v) != float("inf") else None


def parse_leagues(body):
    """The first league id of the leagues list (the current challenge league)."""
    doc = json.loads(body)
    if isinstance(doc, dict):  # tolerate {"leagues": [...]} as well
        doc = doc.get("leagues") or doc.get("result") or []
    for entry in doc if isinstance(doc, list) else []:
        if isinstance(entry, dict):
            lid = entry.get("id") or entry.get("name")
            if isinstance(lid, str) and lid.strip():
                return lid.strip()[:80]
    raise ValueError("no league in the leagues response")


def parse_overview(body):
    """{"primary", "rates": {id: {"value", "name"?}}} from an exchange
    overview. Defensive: unknown fields are ignored, bad lines skipped."""
    doc = json.loads(body)
    if not isinstance(doc, dict) or not isinstance(doc.get("lines"), list):
        raise ValueError("overview has no lines")
    core = doc.get("core") if isinstance(doc.get("core"), dict) else {}
    names = {}
    items = core.get("items")
    if isinstance(items, list):
        for it in items:
            if isinstance(it, dict) and isinstance(it.get("id"), str):
                name = it.get("name") or it.get("text")
                if isinstance(name, str):
                    names[it["id"]] = name[:120]
    rates = {}
    for line in doc["lines"][:MAX_LINES]:
        if not isinstance(line, dict):
            continue
        lid = line.get("id") or line.get("itemId")
        value = _num(line.get("primaryValue"))
        if not isinstance(lid, str) or not lid or value is None:
            continue
        entry = {"value": value}
        vol = _num(line.get("volumePrimaryValue"))
        if vol is not None:
            entry["volume"] = vol
        if lid in names:
            entry["name"] = names[lid]
        rates[lid[:120]] = entry
    primary = core.get("primary") if isinstance(core.get("primary"), str) else None
    return {"primary": primary, "rates": rates}


def _write_atomic(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="ascii", newline="\n") as fh:
        fh.write(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n")
    tmp.replace(path)


class RatesClient:
    """Cached poe.ninja currency rates.

    enabled: callable -> bool, the web-data opt-in (read on every call).
    league: callable -> str or None, a user-configured league (no lookup).
    fetch: injectable transport fetch(method, url, headers, body).
    contact: callable -> str or None, the User-Agent contact (UA-CONTACT);
    poe.ninja asks for one, so without it nothing is requested.
    """

    def __init__(self, directory=None, enabled=lambda: False, league=lambda: None,
                 fetch=None, clock=time.time, contact=lambda: None):
        self.directory = Path(directory) if directory is not None else cache_dir()
        self.path = self.directory / CACHE_NAME
        self.enabled = enabled
        self.contact = contact
        self._ua = USER_AGENT
        self.league = league
        self.fetch = fetch
        self.clock = clock
        self._lock = threading.Lock()
        self._busy = False
        self.doc = self._load()

    def _load(self):
        try:
            doc = json.loads(self.path.read_text(encoding="ascii"))
            return doc if isinstance(doc, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self):
        try:
            _write_atomic(self.path, self.doc)
        except OSError as e:
            log.warning("rates cache not written: %s", e)

    # -- gating
    def _due(self, key, interval, now):
        last = self.doc.get(key)
        return not isinstance(last, (int, float)) or not 0 <= now - last < interval

    def due(self, now=None):
        now = self.clock() if now is None else now
        return self._due("overview_attempt_at", MIN_INTERVAL_S, now)

    def _get(self, url, etag=None):
        headers = {"User-Agent": self._ua, "Accept": "application/json"}
        if etag:
            headers["If-None-Match"] = etag
        return webfetch.request("GET", url, headers, ALLOWED_HOSTS, fetch=self.fetch,
                                max_bytes=MAX_BYTES)

    def _league_id(self, now):
        configured = self.league() if callable(self.league) else self.league
        if isinstance(configured, str) and configured.strip():
            return configured.strip()
        cached = self.doc.get("league_auto")
        if cached and not self._due("league_attempt_at", LEAGUE_INTERVAL_S, now):
            return cached
        if cached is None and not self._due("league_attempt_at", MIN_INTERVAL_S, now):
            raise webfetch.FetchError("league lookup waits for its interval")
        self.doc["league_attempt_at"] = now
        self._save()
        try:
            status, _rh, body = self._get(BASE + LEAGUES_PATH)
            if status != 200:
                raise webfetch.FetchError(f"leagues HTTP {status}")
            self.doc["league_auto"] = parse_leagues(body)
        except (ValueError, webfetch.FetchError) as e:
            if cached:
                return cached
            raise webfetch.FetchError(f"league lookup failed: {e}") from e
        return self.doc["league_auto"]

    def refresh(self, force=False):
        """One refresh when due (or force=True ignores only the interval, never
        the opt-in or the contact). Returns 'off', 'off: contact not set',
        'fresh' (not due), 'unchanged' (304), 'fetched' or 'error: ...'.
        Never raises for network trouble."""
        with self._lock:
            if self._busy:
                return "busy"
            self._busy = True
        try:
            return self._refresh(force)
        finally:
            with self._lock:
                self._busy = False

    def _refresh(self, force):
        try:
            webfetch.require_opt_in(self.enabled)
        except webfetch.WebDataOff:
            return "off"
        contact = webfetch.contact_value(self.contact)
        if contact is None:
            return "off: " + webfetch.REASON_CONTACT
        self._ua = webfetch.user_agent(UA_PURPOSE, contact)
        now = self.clock()
        if not force and not self.due(now):
            return "fresh"
        try:
            league = self._league_id(now)
            query = urllib.parse.urlencode({"league": league, "type": OVERVIEW_TYPE})
            url = f"{BASE}{OVERVIEW_PATH}?{query}"
            same = self.doc.get("url") == url
            self.doc["overview_attempt_at"] = now
            self._save()
            status, rh, body = self._get(url, self.doc.get("etag") if same else None)
            if status == 304 and same and self.doc.get("rates") is not None:
                self.doc["checked_at"] = now
                self.doc["last_error"] = None
                outcome = "unchanged"
            elif status == 200:
                parsed = parse_overview(body)
                self.doc.update({"url": url, "league": league, "primary": parsed["primary"],
                                 "rates": parsed["rates"], "fetched_at": now,
                                 "checked_at": now, "last_error": None,
                                 "etag": webfetch.header(rh, "ETag")})
                outcome = "fetched"
            else:
                raise webfetch.FetchError(f"HTTP {status}")
        except (ValueError, webfetch.FetchError) as e:
            self.doc["last_error"] = str(e)[:200]
            outcome = f"error: {e}"
        self._save()
        return outcome

    def refresh_async(self):
        """Start a background refresh when the opt-in is on and one is due;
        returns True when a thread was started. Never blocks a request."""
        if webfetch.blocked_reason(self.enabled, self.contact) is not None:
            return False
        if self._busy or not self.due():
            return False
        threading.Thread(target=self.refresh, name="al-ninja", daemon=True).start()
        return True

    def snapshot(self, now=None):
        """Cached rates with their age; never makes a request."""
        now = self.clock() if now is None else now
        doc = self.doc
        fetched = doc.get("fetched_at")
        checked = doc.get("checked_at")
        age = (now - checked) if isinstance(checked, (int, float)) else None
        attempt = doc.get("overview_attempt_at")
        next_in = 0
        if isinstance(attempt, (int, float)):
            next_in = max(0, int(attempt + MIN_INTERVAL_S - now))
        enabled = bool(self.enabled() if callable(self.enabled) else self.enabled)
        blocked = webfetch.blocked_reason(enabled, self.contact)
        return {"web_data": enabled, "source": "poe.ninja",
                "contact_set": webfetch.contact_value(self.contact) is not None,
                "blocked": blocked,
                "attribution": ATTRIBUTION, "credit": SHORT_CREDIT,
                "league": doc.get("league"), "primary": doc.get("primary"),
                "rates": doc.get("rates") or {},
                "fetched_at": _utc(fetched) if isinstance(fetched, (int, float)) else None,
                "checked_at": _utc(checked) if isinstance(checked, (int, float)) else None,
                "age_s": int(age) if age is not None else None,
                "stale": age is None or age > STALE_AFTER_S,
                "next_refresh_in_s": next_in if blocked is None else None,
                "refreshing": self._busy, "last_error": doc.get("last_error")}
