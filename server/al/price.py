"""PRICE-1: one trade2 price check per AshLight hotkey press (server side).

The item text comes from the app's ONE clipboard read per press of the item
hotkey (app/eval_hotkey.js -> POST /api/eval, decision 0003); this module
never reads the clipboard and never sends anything to the game. On that same
POST the server calls `PriceChecker.request(text)`, which queues at most ONE
search for the press:

1. the trade2 stat-id table (GET /api/trade2/data/stats, research 0004),
   cached under <sidecar>\\Cache\\trade\\ and fetched at most once a day
   (the attempt time is persisted, a failed attempt counts);
2. the league: "league" from config/local.json, else the current league
   from GET /api/trade2/data/leagues (cached, at most once a day), else
   "Standard";
3. trade.build_query -> one search -> one fetch of the first FETCH_N result
   ids -> a compact summary (min / median of the cheapest listings, their
   currency, listing count).

Every request goes through the shared trade.TradeClient queue and its
RateLimiter (X-Rate-Limit-* parsed dynamically, Retry-After obeyed); while
the limiter defers, `latest()` says "waiting" with the seconds left.
Nothing is sent unless web_data is on AND a User-Agent contact is set
(UA-CONTACT); otherwise the result says why ("web data off" / "contact not
set") and zero requests are made. The same text posted again within
DEDUPE_S reuses the last result (no second search). A press arriving while
an older check has not searched yet supersedes it, so a press never causes
more than one search.

PRICE-1-WIRE: the checker keeps its own result doc (decision 0015: id,
status incl. queued / skipped, reason, wait_s, league, summary, error) and
pushes every change through `card_of()` (a pure adapter) into the card
contract of decision 0016 Fork 1 (status searching | waiting | done | off |
error, wait_s, item, league, count, listings, error) via the `card`
callable (the core passes `SessionState.set_price`): the first publish of a
press with at=<press time>, later updates of the same check with the same
`at` and keep_time=True, so the overlay merges it with the item check of
that press.

The summary is UNVERIFIED against live trade2 responses (research 0004:
the fetch result shape listing.price {amount, currency} follows the trade
site and community tools).
"""

import hashlib
import json
import logging
import math
import statistics
import threading
import time
from pathlib import Path

from . import paths, trade, webfetch
from .theorycraft import item as item_mod

log = logging.getLogger("al.price")

STATS_URL = trade.BASE + "/api/trade2/data/stats"
LEAGUES_URL = trade.BASE + "/api/trade2/data/leagues"
DATA_INTERVAL_S = 24 * 3600
DEDUPE_S = 30.0
FETCH_N = trade.FETCH_BATCH
SUMMARY_N = 5  # min / median over the cheapest SUMMARY_N listings
MAX_PRICES = 10
MAX_STATS = 50000
JOB_TIMEOUT_S = trade.MAX_WAIT_S + 120.0
POLL_S = 0.25
CACHE_NAME = "trade_data.json"
DEFAULT_LEAGUE = "Standard"
_SKIP_LEAGUE_WORDS = ("hardcore", "hc ", "ssf", "solo self-found", "ruthless", "standard")


def cache_dir(environ=None):
    return paths.sidecar_dir("Cache", environ) / "trade"


def parse_stats(doc):
    """{mod_key(text): stat id} from a /data/stats response. Explicit ids win
    over other types for the same text (build_query searches explicit mods)."""
    out = {}
    groups = doc.get("result") if isinstance(doc, dict) else None
    for group in groups if isinstance(groups, list) else []:
        entries = group.get("entries") if isinstance(group, dict) else None
        for e in entries if isinstance(entries, list) else []:
            if not isinstance(e, dict):
                continue
            sid, text = e.get("id"), e.get("text")
            if not (isinstance(sid, str) and isinstance(text, str)) or len(sid) > 120:
                continue
            key = trade.mod_key(text)[:200]
            have = out.get(key)
            if have is None or (sid.startswith("explicit.")
                                and not have.startswith("explicit.")):
                out[key] = sid
            if len(out) >= MAX_STATS:
                return out
    return out


def parse_leagues(doc):
    """The current softcore trade league id from a /data/leagues response
    (first poe2-realm entry that is not Standard / Hardcore / SSF /
    Ruthless), else None. The list order is UNVERIFIED (research 0004)."""
    rows = doc.get("result") if isinstance(doc, dict) else None
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        lid, realm = row.get("id"), row.get("realm")
        if not isinstance(lid, str) or not lid.strip() or len(lid) > 80:
            continue
        if realm not in (None, "poe2"):
            continue
        low = lid.lower() + " "
        if any(w in low for w in _SKIP_LEAGUE_WORDS):
            continue
        return lid.strip()
    return None


def _num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    v = float(v)
    return v if math.isfinite(v) and v > 0 else None


def summarize(doc, total=None):
    """Compact price summary of a /fetch response: the most common listing
    currency, min and median of its cheapest SUMMARY_N amounts, the listing
    count, the search total, and the first MAX_PRICES prices in order."""
    rows = doc.get("result") if isinstance(doc, dict) else None
    prices = []
    for row in rows if isinstance(rows, list) else []:
        listing = row.get("listing") if isinstance(row, dict) else None
        price = listing.get("price") if isinstance(listing, dict) else None
        if not isinstance(price, dict):
            continue
        amount, cur = _num(price.get("amount")), price.get("currency")
        if amount is None or not isinstance(cur, str) or not cur or len(cur) > 40:
            continue
        prices.append({"amount": amount, "currency": cur})
    counts = {}
    for p in prices:
        counts[p["currency"]] = counts.get(p["currency"], 0) + 1
    out = {"listings": len(prices), "total": total if isinstance(total, int) else None,
           "currency": None, "min": None, "median": None, "prices": prices[:MAX_PRICES],
           "currencies": counts}
    if prices:
        main = max(counts, key=counts.get)  # ties: the first seen (insertion order)
        amounts = sorted(p["amount"] for p in prices if p["currency"] == main)[:SUMMARY_N]
        out.update(currency=main, min=amounts[0],
                   median=round(statistics.median(amounts), 4))
    return out


# the exact source strings card_of matches (trade.build_query /
# trade.search_url, webfetch.blocked_reason); anything else is free text
NOT_AN_ITEM = "not an item"
LEAGUE_REQUIRED = "league required"
OFF_NO_CONTACT = "contact not set"
NO_BASE_TYPE = "item has no base type"


def card_of(doc):
    """The decision 0016 card for a decision 0015 result doc (pure).
    queued / searching -> searching; waiting -> waiting with wait_s; done
    -> done with count and the listings (cheapest first: the search sorts
    by price ascending, so the fetch order is kept); off -> off, with
    error "contact not set" when that is why (null for web data off);
    skipped with reason "not an item" -> error "not an item", with
    trade.build_query's "item has no base type" -> error "no base type"; the exact
    trade.search_url error "league required" -> error "no league"; any
    other failure or skip reason -> error, free text (PRICE-1-COPY)."""
    doc = doc if isinstance(doc, dict) else {}
    raw = doc.get("item") if isinstance(doc.get("item"), dict) else {}
    item = {"name": raw.get("name"), "base": raw.get("base"), "rarity": raw.get("rarity")}
    status = doc.get("status")
    card = {"status": "error", "wait_s": None, "item": item, "league": doc.get("league"),
            "count": None, "listings": [], "error": None}
    if status in ("queued", "searching"):
        card["status"] = "searching"
    elif status == "waiting":
        w = doc.get("wait_s")
        ok = isinstance(w, (int, float)) and not isinstance(w, bool) and w > 0
        card.update(status="waiting", wait_s=int(math.ceil(w)) if ok else 1)
    elif status == "done":
        summary = doc.get("summary") if isinstance(doc.get("summary"), dict) else {}
        listings = [{"amount": p["amount"], "currency": p["currency"]}
                    for p in (summary.get("prices") or [])
                    if isinstance(p, dict) and "amount" in p and "currency" in p]
        listings = listings[:MAX_PRICES]
        total = summary.get("total")
        count = (total if isinstance(total, int) and not isinstance(total, bool)
                 and total >= len(listings) else len(listings))
        card.update(status="done", count=count, listings=listings)
    elif status == "off":
        card["status"] = "off"
        if doc.get("reason") == OFF_NO_CONTACT:
            card["error"] = OFF_NO_CONTACT
    elif status == "skipped" and doc.get("reason") == NOT_AN_ITEM:
        card["error"] = NOT_AN_ITEM
    elif status == "skipped" and doc.get("reason") == NO_BASE_TYPE:
        card["error"] = "no base type"
    else:
        err = doc.get("error") or doc.get("reason")
        text = err if isinstance(err, str) and err else "price check failed"
        card["error"] = "no league" if text == LEAGUE_REQUIRED else text[:200]
    return card


def _write_atomic(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="ascii", newline="\n") as fh:
        fh.write(json.dumps(doc, sort_keys=True, ensure_ascii=True) + "\n")
    tmp.replace(path)


class _Superseded(Exception):
    pass


class PriceChecker:
    """One per core. client: the shared trade.TradeClient. enabled /
    contact / league: callables read at call time. publish(doc): receives
    every new or changed decision 0015 doc (internal; tests). card(card,
    at=, keep_time=): receives the decision 0016 card of the same change
    (the core passes SessionState.set_price). spawn(fn, *args): runs a
    check (default: a daemon thread; tests may run it inline)."""

    def __init__(self, client, directory=None, enabled=lambda: False,
                 contact=lambda: None, league=lambda: None, publish=None,
                 clock=time.time, spawn=None, poll_s=POLL_S, card=None):
        self.client = client
        self.directory = Path(directory) if directory is not None else cache_dir()
        self.path = self.directory / CACHE_NAME
        self.enabled = enabled
        self.contact = contact
        self.league = league
        self.publish = publish or (lambda doc: None)
        self.card = card or (lambda card, at=None, keep_time=False: None)
        self.clock = clock
        self.spawn = spawn or self._thread
        self.poll_s = poll_s
        self._lock = threading.Lock()
        self._run_lock = threading.Lock()
        # one publish at a time, in doc order: a stale check's late update
        # can never overwrite the card of a newer press
        self._pub_lock = threading.RLock()
        self._gen = 0
        self._last_key = None
        self._last_at = None
        self._active_kind = None
        self.doc = None
        self.data = self._load()

    @staticmethod
    def _thread(fn, *args):
        threading.Thread(target=fn, args=args, name="al-price", daemon=True).start()

    # -- cache
    def _load(self):
        try:
            doc = json.loads(self.path.read_text(encoding="ascii"))
            return doc if isinstance(doc, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self):
        try:
            _write_atomic(self.path, self.data)
        except OSError as e:
            log.warning("trade data cache not written: %s", e)

    def _due(self, key, now):
        last = self.data.get(key)
        return not isinstance(last, (int, float)) or not 0 <= now - last < DATA_INTERVAL_S

    # -- state
    def blocked_reason(self):
        return webfetch.blocked_reason(self.enabled, self.contact)

    def _emit(self, doc, keep_time):
        self.publish(doc)
        self.card(card_of(doc), at=doc["at"], keep_time=keep_time)

    def _set(self, gen, **fields):
        """Update the doc of check `gen` (ignored once a newer one exists)."""
        with self._pub_lock:
            with self._lock:
                if self.doc is None or self.doc.get("id") != gen:
                    return False
                if all(self.doc.get(k) == v for k, v in fields.items()):
                    return True  # unchanged: no state bump, no push
                self.doc = dict(self.doc, **fields)
                doc = dict(self.doc)
            self._emit(doc, keep_time=True)
        return True

    def _new_doc(self, status, at=None, **fields):
        """A new check (or a press that makes none). `at`: the press time."""
        with self._pub_lock:
            with self._lock:
                self._gen += 1
                self.doc = dict({"id": self._gen, "status": status, "reason": None,
                                 "item": None, "league": None, "wait_s": 0,
                                 "summary": None, "error": None,
                                 "at": self.clock() if at is None else float(at)},
                                **fields)
                doc = dict(self.doc)
            self._emit(doc, keep_time=False)
        return doc

    def latest(self):
        """The latest result plus the live limiter wait ("waiting" while
        the limiter defers the next request of the running check)."""
        with self._lock:
            doc = dict(self.doc) if self.doc else None
            kind = self._active_kind
        wait = {k: round(self.client.limiter.wait_s(k), 1) for k in ("search", "fetch", "data")}
        live = doc is not None and (doc["status"] in ("searching", "waiting")
                                    or (doc["status"] == "queued" and kind))
        if live:
            w = wait.get(kind, 0.0) if kind else 0.0
            doc["status"] = "waiting" if w > 0 else "searching"
            doc["wait_s"] = int(math.ceil(w))
        return {"price": doc, "limiter_wait_s": wait, "blocked": self.blocked_reason()}

    # -- the press
    def request(self, text, at=None):
        """Queue at most one price check for one hotkey press. `at` is the
        press time (the server clock at the POST /api/eval, the same value
        that stamps the item check); default now. Returns the published
        doc. Never raises for a bad item or a missing opt-in."""
        if not isinstance(text, str):
            return None
        press = self.clock() if at is None else float(at)
        parsed = item_mod.parse(text)
        item = ({"name": parsed.name, "base": parsed.base, "rarity": parsed.rarity}
                if parsed.is_item else None)
        reason = self.blocked_reason()
        if reason is not None:
            return self._new_doc("off", at=press, reason=reason, item=item)
        key = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()
        now = self.clock()
        with self._pub_lock:
            with self._lock:
                reuse = (self._last_key == key and self.doc is not None
                         and self._last_at is not None
                         and 0 <= now - self._last_at < DEDUPE_S
                         and self.doc["status"] not in ("off", "skipped"))
                if reuse:
                    # the same result re-stamped with this press, so the
                    # overlay groups it with this press's item check
                    self.doc = dict(self.doc, at=press)
                    doc = dict(self.doc)
            if reuse:
                self._emit(doc, keep_time=False)
                return dict(doc, reused=True)
        if not parsed.is_item:
            return self._new_doc("skipped", at=press, reason="not an item")
        try:
            trade.build_query(parsed)
        except ValueError as e:
            return self._new_doc("skipped", at=press, reason=str(e), item=item)
        doc = self._new_doc("queued", at=press, item=item)
        with self._lock:
            self._last_key, self._last_at = key, now
        self.spawn(self._run, doc["id"], parsed)
        return doc

    def _current(self, gen):
        with self._lock:
            if gen != self._gen:
                raise _Superseded()

    def _call(self, gen, kind, method, url, body=None):
        with self._lock:
            self._active_kind = kind
        deadline = time.monotonic() + JOB_TIMEOUT_S
        try:
            job = self.client.submit(kind, method, url, body)
            while not job.done.wait(self.poll_s):
                w = self.client.limiter.wait_s(kind)
                if w > 0:
                    self._set(gen, status="waiting", wait_s=int(math.ceil(w)))
                if time.monotonic() > deadline:
                    raise webfetch.FetchError("trade request timed out")
        finally:
            with self._lock:
                self._active_kind = None
        if job.error:
            raise webfetch.FetchError(job.error)
        return job.result

    def _stat_ids(self, gen):
        now = self.clock()
        stats = self.data.get("stats") if isinstance(self.data.get("stats"), dict) else {}
        if not self._due("stats_attempt_at", now):
            return stats
        self.data["stats_attempt_at"] = now
        self._save()
        try:
            fresh = parse_stats(self._call(gen, "data", "GET", STATS_URL))
            if fresh:
                self.data["stats"] = fresh
                self.data["stats_at"] = now
                self._save()
                return fresh
        except webfetch.FetchError as e:
            if self.blocked_reason() is not None:
                raise
            log.info("trade stats table not refreshed: %s", e)
        return stats

    def _league(self, gen):
        configured = self.league() if callable(self.league) else self.league
        if isinstance(configured, str) and configured.strip():
            return configured.strip()
        now = self.clock()
        cached = self.data.get("league")
        if not self._due("league_attempt_at", now):
            return cached or DEFAULT_LEAGUE
        self.data["league_attempt_at"] = now
        self._save()
        try:
            found = parse_leagues(self._call(gen, "data", "GET", LEAGUES_URL))
            if found:
                self.data["league"] = found
                self._save()
                return found
        except webfetch.FetchError as e:
            if self.blocked_reason() is not None:
                raise
            log.info("trade league list not refreshed: %s", e)
        return cached or DEFAULT_LEAGUE

    def _run(self, gen, parsed):
        with self._run_lock:  # checks run one after another
            try:
                self._current(gen)
                stat_ids = self._stat_ids(gen)
                league = self._league(gen)
                body = trade.build_query(parsed, stat_ids)
                self._current(gen)  # a newer press before the search: skip this one
                self._set(gen, status="searching", league=league)
                found = self._call(gen, "search", "POST", trade.search_url(league), body)
                if not isinstance(found, dict):
                    raise ValueError("search reply is not an object")
                ids = [i for i in (found.get("result") or []) if isinstance(i, str)]
                total = found.get("total")
                if ids and isinstance(found.get("id"), str):
                    fetched = self._call(gen, "fetch", "GET",
                                         trade.fetch_url(ids[:FETCH_N], found["id"]))
                    summary = summarize(fetched, total)
                else:
                    summary = summarize({}, total if isinstance(total, int) else 0)
                self._set(gen, status="done", wait_s=0, summary=summary,
                          query_id=found.get("id") if isinstance(found.get("id"), str)
                          else None)
            except _Superseded:
                return
            except (webfetch.FetchError, ValueError) as e:
                reason = self.blocked_reason()
                if reason is not None:
                    self._set(gen, status="off", reason=reason, wait_s=0)
                else:
                    self._set(gen, status="error", error=str(e)[:200], wait_s=0)
