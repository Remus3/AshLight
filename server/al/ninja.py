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

PRICE-UNIQUE / PRICE-STACKABLES / UTIL-MOVERS: an optional PriceBook
(pricebook.py) refreshes the unique and stackable overviews inside the same
refresh (same opt-in, contact, User-Agent, league, one request at a time),
each type on its own gate and ETag; snapshot() adds the movers.

UTIL-1.0-READY (league rollover, research 0019): the auto league is
re-read at most every LEAGUE_INTERVAL_S (6 h); after the current league's
overview answers 404 or has no lines, the next hourly refresh re-reads it
(within the hour, decision 0026 item 4; AREA-AUDIT P3-5), so a new league
(PoE2 1.0, 2026-12-11) is picked up the same day.

DATA-LEAGUE-IDENTITY (finding F-031): the leagues list is cached whole as
id plus name (leagues.py) and re-read with If-None-Match, so an unchanged
list costs no body. The id goes into every poe.ninja URL; doc["league"]
stays the DISPLAY name (what Core.trade_league and the card label read),
doc["league_id"] holds the id and doc["league_changed_at"] the time the
priced league last changed. A configured league may be an id or a name and
resolves through the cached list (never a list request of its own).

DATA-PRICE-POLITE (F-045, research 0036 R5): a 429, 403 or 503 on any
poe.ninja GET stops the round and sets doc["backoff_until"] = now +
Retry-After (webfetch.retry_after_s, bounded to 1 h - 24 h; 1 h when the
header is absent), saved in rates.json, so a restart honours it; while it
holds, refresh() returns "backoff" and sends nothing, force included. Every
GET asks for a gzip body (Accept-Encoding: gzip; webfetch.request inflates
it with the size cap applied after inflation). The book's GETs are spaced
2 s apart (pricebook.GAP_S, the injected sleep): the 23 GETs of a full
round have 22 gaps. The User-Agent purpose says "prices", since 22 of the
23 requests fetch other prices than currency.

DATA-PRICE-CADENCE (F-046, decision 0072): Currency stays hourly here; the
book asks its 22 types every 3 h, hourly for a type a press matched in the
last 24 h (lookup() calls book.note_press on a press hit), so a day with no
press makes at most 24 + 176 = 200 overview GETs. RELEASE_POLLING is the
release gate: while it is False an installed copy (paths.install_mode() ==
"installed") makes no poe.ninja request at all (refresh() returns
"off: release build", refresh_async() starts nothing, snapshot()["blocked"]
says REASON_RELEASE); the press still builds its offline trade link. A
source checkout polls as before. The constant flips only by a decision
recording poe.ninja's written yes, an approved mirror or the operator's
written ruling; silence is not consent. DEP-08's release build reads the
name RELEASE_POLLING.

DATA-PRICE-SHAPE-GUARD (F-085): the Currency overview gets the price
book's shape guard (pricebook.shape_error): a 200 body with lines but no
usable rate, or fewer than half of 5 or more lines kept, keeps the last
good rates and ETag and sets last_error "shape: ...". snapshot()["types"]
publishes every type's state (Currency first, then the book's), counts and
errors only; the Checks row is the book's DATA-DIAG-SEAM hook.
"""

import json
import logging
import math
import threading
import time
import urllib.parse
from pathlib import Path

from . import jsonfile, leagues, num, paths, pricebook, webfetch

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
UA_PURPOSE = "prices from poe.ninja"
USER_AGENT = webfetch.user_agent(UA_PURPOSE)  # base form; requests add the contact
# DATA-PRICE-POLITE: these answers stop the round and start a back-off
BACKOFF_STATUSES = (429, 403, 503)
BACKOFF_DEFAULT_S = webfetch.RETRY_AFTER_LO_S  # no (readable) Retry-After: 1 h
MIN_INTERVAL_S = 3600  # PoE2 data refreshes about hourly (research 0005)
LEAGUE_INTERVAL_S = 6 * 3600
STALE_AFTER_S = 2 * 3600
MAX_BYTES = 4 * 1024 * 1024
MAX_LINES = 2000
CACHE_NAME = "rates.json"
# UTIL-FILTER-2 (decision 0032): thin markets never set a filter tier
FILTER_MIN_LISTINGS = 10  # = pricebook.FEW_LISTINGS
FILTER_MIN_VOLUME = 1.0  # = pricebook.MOVERS_MIN_VOLUME
# DATA-PRICE-CADENCE (decision 0072): False = an installed (release) copy
# sends poe.ninja nothing until a decision records poe.ninja's yes
RELEASE_POLLING = False
REASON_RELEASE = "release build"


def _installed_default():
    """True in an installed copy (paths.install_mode, DEP-05); False when
    that function is missing or fails (a source checkout)."""
    mode = getattr(paths, "install_mode", None)
    if not callable(mode):
        return False
    try:
        return mode() == "installed"
    except Exception:  # noqa: BLE001 - an unreadable mode never blocks a checkout
        return False


def cache_dir(environ=None):
    return paths.sidecar_dir("Cache", environ) / "ninja"


def _utc(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


_num = num.finite  # FUZZ-4 / AREA-AUDIT P3-2: huge JSON ints read as None


def parse_leagues(body):
    """The first league id of the leagues list (the current challenge
    league). A wrapper over leagues.parse_list, kept for its callers."""
    return leagues.parse_list(body)[0]["id"]


def parse_overview(body):
    """{"primary", "rates": {id: {"value", "name"?}}, "lines"} from an
    exchange overview. Defensive: unknown fields are ignored, bad lines
    skipped; "lines" counts the dict lines read (DATA-PRICE-SHAPE-GUARD).
    DATA-NINJA-NAMES: line names come from the TOP-LEVEL `items` array (id,
    name, category, detailsId; research 0013, the real response), and
    `core.items` (only the reference currencies there) fills any gap."""
    doc = json.loads(body)
    if not isinstance(doc, dict) or not isinstance(doc.get("lines"), list):
        raise ValueError("overview has no lines")
    core = doc.get("core") if isinstance(doc.get("core"), dict) else {}
    names = {}
    for items in (doc.get("items"), core.get("items")):  # first wins
        for it in items[:MAX_LINES] if isinstance(items, list) else []:
            if isinstance(it, dict) and isinstance(it.get("id"), str):
                name = it.get("name") or it.get("text")
                if isinstance(name, str) and name and it["id"] not in names:
                    names[it["id"]] = name[:120]
    rates = {}
    lines = 0
    for line in doc["lines"][:MAX_LINES]:
        if not isinstance(line, dict):
            continue
        lines += 1
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
    return {"primary": primary, "rates": rates, "lines": lines}


class BackedOff(webfetch.FetchError, pricebook.StopRound):
    """poe.ninja answered 429, 403 or 503: the round stops (the price book
    sees it as its StopRound) and the back-off is already saved."""


def _no_wait(_seconds):
    return None


class RatesClient:
    """Cached poe.ninja currency rates.

    enabled: callable -> bool, the web-data opt-in (read on every call).
    league: callable -> str or None, a user-configured league (no lookup).
    fetch: injectable transport fetch(method, url, headers, body).
    contact: callable -> str or None, the User-Agent contact (UA-CONTACT);
    poe.ninja asks for one, so without it nothing is requested.
    sleep: sleep(seconds), the wait between the book's GETs (DATA-PRICE-POLITE);
    None = time.sleep with the real transport, no wait with an injected
    fetch (a mock transport has no server to be polite to).
    installed: callable -> bool, True in an installed (release) copy
    (DATA-PRICE-CADENCE); None = paths.install_mode() == "installed".
    """

    def __init__(self, directory=None, enabled=lambda: False, league=lambda: None,
                 fetch=None, clock=time.time, contact=lambda: None, book=None,
                 sleep=None, installed=None):
        self.directory = Path(directory) if directory is not None else cache_dir()
        self.path = self.directory / CACHE_NAME
        self.enabled = enabled
        self.contact = contact
        self._ua = USER_AGENT
        self.league = league
        self.fetch = fetch
        self.clock = clock
        if sleep is None:
            sleep = time.sleep if fetch is None else _no_wait
        self.sleep = sleep
        self._lock = threading.Lock()
        self._busy = False
        self.doc = self._load()
        self.book = book  # pricebook.PriceBook or None
        self.installed = installed if installed is not None else _installed_default

    def _load(self):
        return jsonfile.read_json(self.path, encoding="ascii", kind=dict, default={})

    def _save(self):
        try:
            jsonfile.write_json(self.path, self.doc, sort_keys=True)
        except OSError as e:
            log.warning("rates cache not written: %s", e)

    # -- gating
    def release_blocked(self):
        """DATA-PRICE-CADENCE: True while RELEASE_POLLING is off and this is
        an installed copy (read on every call; an unreadable answer counts
        as installed, the stricter reading)."""
        if RELEASE_POLLING:
            return False
        try:
            return bool(self.installed() if callable(self.installed) else self.installed)
        except Exception:  # noqa: BLE001 - unknown counts as installed
            return True

    def blocked_reason(self):
        """Why nothing is requested now: REASON_OFF, REASON_RELEASE,
        REASON_CONTACT or None."""
        enabled = bool(self.enabled() if callable(self.enabled) else self.enabled)
        if not enabled:
            return webfetch.REASON_OFF
        if self.release_blocked():
            return REASON_RELEASE
        return webfetch.blocked_reason(enabled, self.contact)

    def _due(self, key, interval, now):
        last = self.doc.get(key)
        return not isinstance(last, (int, float)) or not 0 <= now - last < interval

    def due(self, now=None):
        now = self.clock() if now is None else now
        return self._due("overview_attempt_at", MIN_INTERVAL_S, now)

    def any_due(self, now=None):
        """The currency overview or any price book type is due."""
        now = self.clock() if now is None else now
        if self.backed_off(now):
            return False
        return self.due(now) or (self.book is not None and self.book.due(now))

    def backed_off(self, now=None):
        """True while a saved poe.ninja back-off holds. A value further
        ahead than the 24 h bound (a clock moved back, a bad cache) is
        ignored rather than blocking for ever."""
        now = self.clock() if now is None else now
        until = _num(self.doc.get("backoff_until"))
        return until is not None and 0 < until - now <= webfetch.RETRY_AFTER_HI_S

    def _back_off(self, status, rh):
        """Record the back-off of a 429 / 403 / 503 answer and raise BackedOff."""
        now = self.clock()
        wait = webfetch.retry_after_s(rh, now)
        if wait is None:
            wait = BACKOFF_DEFAULT_S
        self.doc["backoff_until"] = now + wait
        self.doc["last_error"] = f"HTTP {status}: poe.ninja asked to wait {int(wait)} s"
        self._save()
        raise BackedOff(f"HTTP {status}")

    def _get(self, url, etag=None):
        """One GET (gzip accepted, inflated by webfetch.request); a 429,
        403 or 503 answer saves the back-off and raises BackedOff."""
        headers = {"User-Agent": self._ua, "Accept": "application/json",
                   "Accept-Encoding": "gzip"}
        if etag:
            headers["If-None-Match"] = etag
        status, rh, body = webfetch.request("GET", url, headers, ALLOWED_HOSTS,
                                            fetch=self.fetch, max_bytes=MAX_BYTES)
        if status in BACKOFF_STATUSES:
            self._back_off(status, rh)
        return status, rh, body

    def _configured(self):
        configured = self.league() if callable(self.league) else self.league
        if isinstance(configured, str) and configured.strip():
            return configured.strip()
        return None

    def _named(self, league_id):
        """(id, display name) of a league id, the name from the cached list."""
        return league_id, leagues.name_of(self.doc.get("leagues"), league_id) or league_id

    def _league_id(self, now):
        """(id, name) of the league to price: the configured one (an id or a
        name, resolved through the cached list; unknown -> used as both),
        else the first of poe.ninja's list, re-read every LEAGUE_INTERVAL_S
        (hourly after a rollover hint) with If-None-Match."""
        configured = self._configured()
        if configured:
            hit = leagues.entry_of(self.doc.get("leagues"), configured)
            return (hit["id"], hit["name"]) if hit else (configured, configured)
        cached = self.doc.get("league_auto")
        # a rollover hint (404 / empty overview) shortens the wait to an hour
        wait = MIN_INTERVAL_S if self.doc.get("league_stale") else LEAGUE_INTERVAL_S
        if cached and not self._due("league_attempt_at", wait, now):
            return self._named(cached)
        if cached is None and not self._due("league_attempt_at", MIN_INTERVAL_S, now):
            raise webfetch.FetchError("league lookup waits for its interval")
        self.doc["league_attempt_at"] = now
        self._save()
        listed = self.doc.get("leagues")
        etag = self.doc.get("league_list_etag") if cached and isinstance(listed, list) \
            and listed else None
        try:
            status, rh, body = self._get(BASE + LEAGUES_PATH, etag)
            if status == 304 and etag:
                self.doc["league_stale"] = False  # the list is unchanged
            elif status == 200:
                listed = leagues.parse_list(body)
                self.doc.update({"leagues": listed, "league_auto": listed[0]["id"],
                                 "league_stale": False,
                                 "league_list_etag": webfetch.header(rh, "ETag")})
            else:
                raise webfetch.FetchError(f"leagues HTTP {status}")
            self._save()
        except BackedOff:
            raise  # DATA-PRICE-POLITE: the round stops, the cached league waits too
        except (ValueError, webfetch.FetchError) as e:
            if cached:
                return self._named(cached)
            raise webfetch.FetchError(f"league lookup failed: {e}") from e
        return self._named(self.doc["league_auto"])

    def refresh(self, force=False):
        """One refresh when due (or force=True ignores only the interval, never
        the opt-in or the contact). Returns 'off', 'off: contact not set',
        'fresh' (not due), 'unchanged' (304), 'fetched', 'backoff' (a saved
        429 / 403 / 503 back-off holds or this round hit one) or 'error: ...'.
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
        if self.release_blocked():  # decision 0072: no request until a yes
            return "off: " + REASON_RELEASE
        contact = webfetch.contact_value(self.contact)
        if contact is None:
            return "off: " + webfetch.REASON_CONTACT
        self._ua = webfetch.user_agent(UA_PURPOSE, contact)
        now = self.clock()
        if self.backed_off(now):  # poe.ninja asked to wait; force never overrides it
            return "backoff"
        rates_due = force or self.due(now)
        book_due = self.book is not None and (force or self.book.due(now))
        if not rates_due and not book_due:
            return "fresh"
        try:
            league_id, name = self._league_id(now)
        except BackedOff:
            return "backoff"
        except (ValueError, webfetch.FetchError) as e:
            self.doc["last_error"] = str(e)[:200]
            self._save()
            return f"error: {e}"
        outcome = "fresh"
        if rates_due:
            outcome = self._refresh_rates(league_id, name, now)
            if outcome == "backoff":
                return outcome  # the Currency GET hit a 429 / 403 / 503
        # DATA-PRICE-CADENCE: a new league prices its book types within the
        # hour even when their 3 h gate has not passed (decision 0026 item 4)
        book_due = book_due or (self.book is not None and self.book.due(now, league_id))
        if book_due:
            # the Currency GET (when due) comes first; the book sleeps
            # GAP_S before each of its GETs and stops on BackedOff
            self.book.refresh(lambda url, etag: self._get(url, etag), BASE, league_id,
                              now, force=force, name=name, sleep=self.sleep)
        return outcome

    def _rollover(self, league_id):
        """The auto league's overview is gone or empty: re-read the
        leagues list on the next refresh (the hourly gate still applies)."""
        if self._configured():
            return
        if self.doc.get("league_auto") == league_id:
            self.doc["league_stale"] = True

    def _set_league(self, league_id, name, now):
        """Store the priced league (display name and id); a different id than
        the last priced one records league_changed_at (F-031). The first
        league ever priced is not a change. A cache from before the id was
        kept holds the id in "league" (they were equal then)."""
        before = self.doc.get("league_id") or self.doc.get("league")
        if isinstance(before, str) and before and before != league_id:
            self.doc["league_changed_at"] = now
        self.doc["league"] = name
        self.doc["league_id"] = league_id

    def _refresh_rates(self, league_id, name, now):
        try:
            query = urllib.parse.urlencode({"league": league_id, "type": OVERVIEW_TYPE})
            url = f"{BASE}{OVERVIEW_PATH}?{query}"
            same = self.doc.get("url") == url
            self.doc["overview_attempt_at"] = now
            self._save()
            status, rh, body = self._get(url, self.doc.get("etag") if same else None)
            if status == 404:
                self._rollover(league_id)
                raise webfetch.FetchError("HTTP 404")
            if status == 304 and same and self.doc.get("rates") is not None:
                self.doc["checked_at"] = now
                self.doc["last_error"] = None
                self._set_league(league_id, name, now)  # a renamed id keeps its rates
                outcome = "unchanged"
            elif status == 200:
                parsed = parse_overview(body)
                if not parsed["rates"]:
                    self._rollover(league_id)
                bad = pricebook.shape_error(parsed["lines"], len(parsed["rates"]))
                if bad is not None:
                    raise ValueError(bad)  # the last good rates and ETag stay
                self._set_league(league_id, name, now)
                self.doc.update({"url": url, "primary": parsed["primary"],
                                 "rates": parsed["rates"], "fetched_at": now,
                                 "checked_at": now, "last_error": None,
                                 "etag": webfetch.header(rh, "ETag")})
                outcome = "fetched"
            else:
                raise webfetch.FetchError(f"HTTP {status}")
        except BackedOff:
            outcome = "backoff"  # last_error and backoff_until set by _back_off
        except (ValueError, webfetch.FetchError) as e:
            self.doc["last_error"] = str(e)[:200]
            outcome = f"error: {e}"
        self._save()
        return outcome

    def refresh_async(self):
        """Start a background refresh when the opt-in is on and one is due;
        returns True when a thread was started. Never blocks a request."""
        if self.blocked_reason() is not None:
            return False
        if self._busy or not self.any_due():
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
        blocked = self.blocked_reason()
        changed = doc.get("league_changed_at")
        listed = doc.get("leagues") if isinstance(doc.get("leagues"), list) else []
        return {"web_data": enabled, "source": "poe.ninja",
                "contact_set": webfetch.contact_value(self.contact) is not None,
                "blocked": blocked,
                "attribution": ATTRIBUTION, "credit": SHORT_CREDIT,
                "league": doc.get("league"),
                "league_id": doc.get("league_id") or doc.get("league"),
                "leagues": [{"id": e["id"], "name": e["name"]}
                            for e in leagues.entries(listed)],
                "league_changed_at": (_utc(changed) if isinstance(changed, (int, float))
                                      else None),
                "primary": doc.get("primary"),
                "rates": doc.get("rates") or {},
                "fetched_at": _utc(fetched) if isinstance(fetched, (int, float)) else None,
                "checked_at": _utc(checked) if isinstance(checked, (int, float)) else None,
                "age_s": int(age) if age is not None else None,
                "stale": age is None or age > STALE_AFTER_S,
                "next_refresh_in_s": next_in if blocked is None else None,
                "refreshing": self._busy, "last_error": doc.get("last_error"),
                "movers": self.movers(), "types": self.types()}

    def types(self):
        """DATA-PRICE-SHAPE-GUARD: {type: {"entries", "league",
        "last_error", "state"}}, Currency (these rates) first, then the
        book's types; state one of pricebook.STATES. Counts and errors only,
        never a request."""
        doc = self.doc
        rates = doc.get("rates") if isinstance(doc.get("rates"), dict) else {}
        err = doc.get("last_error")
        out = {OVERVIEW_TYPE: {"entries": len(rates), "league": doc.get("league"),
                               "last_error": err,
                               "state": pricebook.state_of(len(rates), err)}}
        if self.book is not None:
            out.update(self.book.summary())
        return out

    def movers(self):
        """UTIL-MOVERS: the cached price book's biggest 7-day risers and
        fallers of the current league; empty while web data is off (the
        cache is not shown then) or without a book. Never a request."""
        empty = {"up": [], "down": []}
        enabled = bool(self.enabled() if callable(self.enabled) else self.enabled)
        if self.book is None or not enabled or not self.doc.get("league"):
            return empty
        return self.book.movers(league=self.doc.get("league"))

    def lookup(self, item):
        """PRICE-UNIQUE / PRICE-STACKABLES: the cached poe.ninja price for a
        parsed item, or None; currency from the rates, the rest from the
        book, current league only. Web data off -> None. Never a request:
        the press reads the cache only. A hit carries league_changed_at
        (epoch seconds like checked_at, or None) for the card text.
        DATA-PRICE-CADENCE: a book hit for a pressed item (a parsed item
        object, what PriceChecker passes) calls book.note_press, in memory
        only; a plain dict (the price watch's cache re-read) is no press."""
        hit = self._lookup(item)
        if hit is not None:
            hit["league_changed_at"] = self.doc.get("league_changed_at")
            if self.book is not None and not isinstance(item, dict) \
                    and hit.get("type") != OVERVIEW_TYPE:
                self.book.note_press(hit.get("type"), self.clock())
        return hit

    def _lookup(self, item):
        enabled = bool(self.enabled() if callable(self.enabled) else self.enabled)
        league = self.doc.get("league")
        if not enabled or not league:
            return None
        get = (item.get if isinstance(item, dict)
               else lambda k, d=None: getattr(item, k, d))
        base = " ".join(str(get("base") or "").split()).lower()
        if base and str(get("rarity") or "").upper() == "CURRENCY":
            rates = self.doc.get("rates") or {}
            for entry in rates.values():
                name = entry.get("name") if isinstance(entry, dict) else None
                if isinstance(name, str) and name.lower() == base:
                    primary = self.doc.get("primary")
                    unit = (rates.get(primary) or {}).get("name") or primary
                    return {"kind": "stackable", "type": OVERVIEW_TYPE, "name": name,
                            "value": entry.get("value"), "unit": unit,
                            "primary": primary, "listings": None, "few": False,
                            "volume": entry.get("volume"), "change": None,
                            "league": league,
                            "checked_at": self.doc.get("checked_at")}
        if self.book is None:
            return None
        return self.book.lookup(item, league=league)

    def filter_prices(self):
        """UTIL-FILTER-2 (decision 0032): cached prices for the loot filter's
        value tiers, in Divine Orbs: {"uniques": [{base, value}] (the
        cheapest well-listed unique of each base), "stackables": [{name,
        value}] (currency rates plus the book's exchange kinds), "league":
        the cached league the prices are for (TC-FILTER-ONE-CONTROL: the
        filter header names it)}. None while web data is off, without a
        league or without a Divine Orb rate.
        Reads the cache only, never a request."""
        enabled = bool(self.enabled() if callable(self.enabled) else self.enabled)
        league = self.doc.get("league")
        rates = self.doc.get("rates") or {}
        primary = self.doc.get("primary")
        if not enabled or not league or not isinstance(rates, dict):
            return None
        did = next((k for k, e in rates.items() if isinstance(e, dict)
                    and (e.get("name") == "Divine Orb" or k == "divine")), None)
        div = (rates.get(did) or {}).get("value") if did else None
        if not (isinstance(div, (int, float)) and div > 0):
            div = 1.0 if did is not None and did == primary else None
        if div is None:
            return None

        def in_div(value, unit_id):
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                return None
            if unit_id in (None, primary):
                return round(value / div, 6)
            rate = (rates.get(unit_id) or {}).get("value")
            if isinstance(rate, (int, float)) and rate > 0:
                return round(value * rate / div, 6)
            return None

        stack = {}
        for e in rates.values():
            if not isinstance(e, dict) or not isinstance(e.get("name"), str):
                continue
            vol = e.get("volume")
            if isinstance(vol, (int, float)) and vol < FILTER_MIN_VOLUME:
                continue
            v = in_div(e.get("value"), primary)
            if v is not None:
                stack.setdefault(e["name"], v)
        uniques = {}
        if self.book is not None:
            for _n, t, e in self.book._entries(league, ("unique", "exchange")):
                v = in_div(e.get("value"), t.get("primary"))
                if v is None or not isinstance(e.get("name"), str):
                    continue
                if t.get("kind") == "exchange":
                    vol = e.get("volume")
                    if not isinstance(vol, (int, float)) or vol >= FILTER_MIN_VOLUME:
                        stack.setdefault(e["name"], v)
                    continue
                listings = e.get("listings")
                base = e.get("base")
                if not isinstance(listings, int) or listings < FILTER_MIN_LISTINGS \
                        or not isinstance(base, str) or not base:
                    continue  # a thin market's price is noise
                uniques[base] = min(v, uniques.get(base, v))
        return {"uniques": [{"base": b, "value": v} for b, v in sorted(uniques.items())],
                "stackables": [{"name": n, "value": v} for n, v in sorted(stack.items())],
                "league": league}
