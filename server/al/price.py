"""PRICE-1 / PRICE-TRADE-LINK (decision 0017): one trade-search link per
AshLight hotkey press (server side).

The item text comes from the app's ONE clipboard read per press of the item
hotkey (app/eval_hotkey.js -> POST /api/eval, decision 0003); this module
never reads the clipboard and never sends anything to the game. On that same
POST the server calls `PriceChecker.request(text)`, which builds, offline,
the trade2 search URL for the item (trade.search_link: name, base type and
rarity; the league from config/local.json, else Standard) and publishes it.

The app calls no trade-site endpoint (decision 0017): there is no search,
no fetch, no stat or league table, and nothing here touches the network, so
the web-data opt-in and the contact do not gate the link. The core never
opens the URL; the dashboard shows it as a link the user may click. Prices
shown by the app come from poe.ninja only (decision 0013 item 3).

The checker keeps its own result doc (decision 0015: id, status link |
skipped, reason, item, league, url, at) and pushes it through `card_of()`
(a pure adapter) into the decision 0016 card (status link | error, url,
item, league, error; wait_s / count / listings stay empty) via the `card`
callable (the core passes `SessionState.set_price`) with at=<press time>,
so the overlay merges it with the item check of that press.

PRICE-UNIQUE / PRICE-STACKABLES: the same press also reads the cached
poe.ninja price (`lookup`, the core passes RatesClient.lookup: cache only,
never a request; None while web data is off) and the card carries it as
`ninja` {kind, name, value, unit, listings, few, change, league}.
"""

import threading
import time

from . import trade
from .theorycraft import item as item_mod

DEFAULT_LEAGUE = trade.DEFAULT_LEAGUE

# the exact source strings card_of matches (trade.build_query); anything
# else is free text
NOT_AN_ITEM = "not an item"
NO_BASE_TYPE = "item has no base type"


def card_of(doc):
    """The decision 0016 card for a decision 0015 result doc (pure).
    link with a trade search URL -> link with `url`; skipped with reason
    "not an item" -> error "not an item"; "item has no base type" -> error
    "no base type"; anything else (a link without a valid URL included) ->
    error, free text."""
    doc = doc if isinstance(doc, dict) else {}
    raw = doc.get("item") if isinstance(doc.get("item"), dict) else {}
    item = {"name": raw.get("name"), "base": raw.get("base"), "rarity": raw.get("rarity")}
    status = doc.get("status")
    card = {"status": "error", "wait_s": None, "item": item, "league": doc.get("league"),
            "count": None, "listings": [], "error": None, "url": None,
            "ninja": ninja_of(doc.get("ninja"))}
    if status == "link" and trade.is_search_link(doc.get("url")):
        card.update(status="link", url=doc["url"])
    elif status == "skipped" and doc.get("reason") == NOT_AN_ITEM:
        card["error"] = NOT_AN_ITEM
    elif status == "skipped" and doc.get("reason") == NO_BASE_TYPE:
        card["error"] = "no base type"
    else:
        err = doc.get("error") or doc.get("reason")
        card["error"] = err[:200] if isinstance(err, str) and err else "price check failed"
    return card


NINJA_KEYS = ("kind", "name", "value", "unit", "listings", "few", "change", "league")


def ninja_of(found):
    """The card's `ninja` part: a cached poe.ninja price with a finite
    value, else None (pure)."""
    if not isinstance(found, dict):
        return None
    v = found.get("value")
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v in (
            float("inf"), float("-inf")) or v < 0:
        return None
    return {k: found.get(k) for k in NINJA_KEYS}


class PriceChecker:
    """One per core. league: a callable read at call time (the configured
    league or None). publish(doc): receives every decision 0015 doc
    (internal; tests). card(card, at=, keep_time=): receives its decision
    0016 card (the core passes SessionState.set_price)."""

    def __init__(self, league=lambda: None, publish=None, card=None, clock=time.time,
                 lookup=None):
        self.league = league
        self.lookup = lookup  # cached poe.ninja price for a parsed item, or None
        self.publish = publish or (lambda doc: None)
        self.card = card or (lambda card, at=None, keep_time=False: None)
        self.clock = clock
        self._lock = threading.Lock()
        self._gen = 0
        self.doc = None

    def _new_doc(self, status, at, **fields):
        with self._lock:
            self._gen += 1
            self.doc = dict({"id": self._gen, "status": status, "reason": None,
                             "item": None, "league": None, "url": None, "at": float(at)},
                            **fields)
            doc = dict(self.doc)
            # inside the lock: two presses publish in doc order
            self.publish(doc)
            self.card(card_of(doc), at=doc["at"], keep_time=False)
        return doc

    def latest(self):
        with self._lock:
            return {"price": dict(self.doc) if self.doc else None}

    def request(self, text, at=None):
        """Build the trade link for one hotkey press. `at` is the press
        time (the same value that stamps the item check); default now.
        Returns the published doc, None for non-text. Never raises for a
        bad item; never touches the network."""
        if not isinstance(text, str):
            return None
        press = self.clock() if at is None else float(at)
        parsed = item_mod.parse(text)
        if not parsed.is_item:
            return self._new_doc("skipped", press, reason=NOT_AN_ITEM)
        item = {"name": parsed.name, "base": parsed.base, "rarity": parsed.rarity}
        configured = self.league() if callable(self.league) else self.league
        league = trade.league_or_default(configured)
        try:
            url = trade.search_link(parsed, league)
        except ValueError as e:
            return self._new_doc("skipped", press, reason=str(e), item=item)
        return self._new_doc("link", press, item=item, league=league, url=url,
                             ninja=self._ninja(parsed))

    def _ninja(self, parsed):
        if not callable(self.lookup):
            return None
        try:
            return ninja_of(self.lookup(parsed))
        except Exception:  # noqa: BLE001 - a cache read never breaks the link
            return None
