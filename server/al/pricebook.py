"""PRICE-UNIQUE, PRICE-STACKABLES and UTIL-MOVERS: more poe.ninja PoE2
overviews, cached, looked up offline on the item-check press.

Only poe.ninja's documented economy endpoints (research 0019,
https://poe.ninja/docs/api, accessed 2026-11-17):
- GET /poe2/api/economy/stash/current/item/overview?league=&type=<Unique*>
  -> lines with name, baseType, corrupted, primaryValue, listingCount,
  sparkLine.totalChange (7 days);
- GET /poe2/api/economy/exchange/current/overview?league=&type=<kind>
  -> lines with id, primaryValue, volumePrimaryValue, sparkline; names in
  the top-level `items` array (research 0013 DATA-NINJA-NAMES).

The book owns no transport and no gate of its own opt-in: RatesClient
(ninja.py) calls refresh() from its own refresh, after the web-data opt-in
and the contact are checked, with its GET (truthful User-Agent, allowlist)
and its league. Every type keeps its own ETag and is requested at most once
per ninja.MIN_INTERVAL_S (a failed attempt counts), so a restart never
refetches early. Nothing here runs while web_data is off (decision 0013).

The press never makes a request: lookup() reads the cache only (decision
0015: price shares the item-check hotkey; decision 0017: prices from
poe.ninja only, trade as a link). movers() builds the dashboard's price
movers from the same cache, no extra request (UTIL-MOVERS).
Cache: <sidecar>\\Cache\\ninja\\book.json (compact entries, never raw bodies).

DATA-PRICE-POLITE (F-045, research 0036 R5): refresh() sleeps GAP_S before
each of its GETs (after the rates' Currency GET, so a full round of 23 GETs
has 22 gaps); a StopRound raised by the get callable (poe.ninja answered
429, 403 or 503) ends the round at once. A type that failed FAILS_DAILY
times in a row is asked only once per DAILY_S until it succeeds; a failure
never brings a faster retry.
"""

import json
import logging
import urllib.parse
from pathlib import Path

from . import jsonfile, num

log = logging.getLogger("al.pricebook")

ITEM_PATH = "/poe2/api/economy/stash/current/item/overview"
EXCHANGE_PATH = "/poe2/api/economy/exchange/current/overview"
UNIQUE_TYPES = ("UniqueWeapons", "UniqueArmours", "UniqueAccessories",
                "UniqueFlasks", "UniqueCharms", "UniqueJewels",
                "UniqueSanctumRelics", "UniqueTablets", "PrecursorTablets")
# Currency itself stays in RatesClient (rates.json); these are the other
# stackable kinds of the exchange overview (research 0019).
EXCHANGE_TYPES = ("Fragments", "Abyss", "UncutGems", "LineageSupportGems",
                  "Essences", "SoulCores", "Idols", "Runes", "Ritual",
                  "Expedition", "Delirium", "Breach", "Verisium")
CACHE_NAME = "book.json"
MAX_LINES = 5000
FEW_LISTINGS = 10  # a unique with fewer listings is a thin market
MOVERS_N = 5
MOVERS_MIN_LISTINGS = 20  # movers ignore thin uniques (noise)
MOVERS_MIN_VOLUME = 1.0  # and stackables with almost no trade volume
GAP_S = 2.0  # DATA-PRICE-POLITE: the wait before each book GET
FAILS_DAILY = 3  # failures in a row after which a type is asked daily
DAILY_S = 24 * 3600


class StopRound(Exception):
    """Raised by the get callable to end the round now (a server back-off)."""


_num = num.finite  # FUZZ-4 / AREA-AUDIT P3-2: huge JSON ints read as None


def _key(text):
    return " ".join(text.split()).lower() if isinstance(text, str) else ""


def _change(line):
    for k in ("sparkLine", "sparkline", "lowConfidenceSparkLine"):
        sp = line.get(k)
        if isinstance(sp, dict):
            v = _num(sp.get("totalChange"))
            if v is not None:
                return v
    return None


def _unit(core):
    """(primary id, its display name) from the overview's `core`."""
    pid = core.get("primary") if isinstance(core.get("primary"), str) else None
    name = None
    for it in core.get("items") if isinstance(core.get("items"), list) else ():
        if isinstance(it, dict) and it.get("id") == pid and isinstance(it.get("name"), str):
            name = it["name"][:60]
            break
    return pid, name or pid


def _doc(body):
    doc = json.loads(body)
    if not isinstance(doc, dict) or not isinstance(doc.get("lines"), list):
        raise ValueError("overview has no lines")
    core = doc.get("core") if isinstance(doc.get("core"), dict) else {}
    return doc, core


def parse_item_overview(body):
    """{"primary", "unit", "entries": [{name, base, corrupted, value,
    listings, change}]} from a stash item overview (uniques). Defensive:
    a line without a name or a number is skipped."""
    doc, core = _doc(body)
    pid, unit = _unit(core)
    entries = []
    for line in doc["lines"][:MAX_LINES]:
        if not isinstance(line, dict):
            continue
        name = line.get("name")
        value = _num(line.get("primaryValue"))
        if not isinstance(name, str) or not name.strip() or value is None:
            continue
        base = line.get("baseType") if isinstance(line.get("baseType"), str) else ""
        listings = _num(line.get("listingCount"))
        entries.append({"name": name.strip()[:120], "base": base.strip()[:120],
                        "corrupted": line.get("corrupted") is True,
                        "value": value,
                        "listings": int(listings) if listings is not None else None,
                        "change": _change(line)})
    return {"primary": pid, "unit": unit, "entries": entries}


def parse_exchange_overview(body):
    """{"primary", "unit", "entries": [{name, value, volume, change}]} from
    an exchange overview; names from the top-level `items` (then
    `core.items`). A line with no name is skipped: it cannot match an item."""
    doc, core = _doc(body)
    pid, unit = _unit(core)
    names = {}
    for items in (doc.get("items"), core.get("items")):
        for it in items[:MAX_LINES] if isinstance(items, list) else []:
            if isinstance(it, dict) and isinstance(it.get("id"), str):
                nm = it.get("name") or it.get("text")
                if isinstance(nm, str) and nm.strip() and it["id"] not in names:
                    names[it["id"]] = nm.strip()[:120]
    entries = []
    for line in doc["lines"][:MAX_LINES]:
        if not isinstance(line, dict):
            continue
        lid = line.get("id") or line.get("itemId")
        value = _num(line.get("primaryValue"))
        if not isinstance(lid, str) or lid not in names or value is None:
            continue
        entries.append({"name": names[lid], "value": value,
                        "volume": _num(line.get("volumePrimaryValue")),
                        "change": _change(line)})
    return {"primary": pid, "unit": unit, "entries": entries}


def _all_types():
    return ([(t, ITEM_PATH, "unique") for t in UNIQUE_TYPES]
            + [(t, EXCHANGE_PATH, "exchange") for t in EXCHANGE_TYPES])


class PriceBook:
    """Cached unique and stackable overviews. Not a client: RatesClient
    drives refresh() under its own lock, opt-in and contact checks."""

    def __init__(self, directory, interval_s=3600):
        self.path = Path(directory) / CACHE_NAME
        self.interval_s = interval_s
        self.doc = self._load()

    def _load(self):
        doc = jsonfile.read_json(self.path, encoding="ascii", kind=dict)
        if doc is not None and isinstance(doc.get("types"), dict):
            return doc
        return {"types": {}}

    def _save(self):
        try:
            jsonfile.write_json(self.path, self.doc, sort_keys=True)
        except OSError as e:
            log.warning("price book not written: %s", e)

    def _type(self, name):
        return self.doc["types"].setdefault(name, {})

    def _type_due(self, t, now):
        """A type is due once its interval passed: interval_s, or DAILY_S
        after FAILS_DAILY failures in a row (until a success)."""
        last = t.get("attempt_at")
        fails = t.get("fails")
        wait = (DAILY_S if isinstance(fails, int) and fails >= FAILS_DAILY
                else self.interval_s)
        return not isinstance(last, (int, float)) or not 0 <= now - last < wait

    def due(self, now):
        return any(self._type_due(self.doc["types"].get(name) or {}, now)
                   for name, _p, _k in _all_types())

    def refresh(self, get, base, league, now, force=False, name=None, sleep=None):
        """Request each due type once: get(url, etag) -> (status, headers,
        body), the caller's GET. Returns {"fetched", "unchanged", "errors",
        "stopped"}. A league change drops the old league's entries.
        DATA-LEAGUE-IDENTITY: `league` is poe.ninja's league id (the URL);
        `name` is the display name stored as each type's league (what
        lookup() and movers() match); without it the id is stored.
        DATA-PRICE-POLITE: sleep(GAP_S) runs before each GET (None = no
        wait); a StopRound from get ends the round (not a type failure)."""
        stored = name if isinstance(name, str) and name else league
        out = {"fetched": 0, "unchanged": 0, "errors": 0, "stopped": False}
        for name, path, kind in _all_types():
            t = self._type(name)
            if not force and not self._type_due(t, now):
                continue
            if sleep is not None:
                sleep(GAP_S)
            query = urllib.parse.urlencode({"league": league, "type": name})
            url = f"{base}{path}?{query}"
            same = t.get("url") == url
            if not same:
                t.pop("entries", None)
                t.pop("etag", None)
            t["attempt_at"] = now
            try:
                status, rh, body = get(url, t.get("etag") if same else None)
                if status == 304 and same and t.get("entries") is not None:
                    t.update(checked_at=now, last_error=None, league=stored, fails=0)
                    out["unchanged"] += 1
                elif status == 200:
                    parse = parse_item_overview if kind == "unique" else parse_exchange_overview
                    p = parse(body)
                    etag = None
                    for k, v in (rh or {}).items():
                        if k.lower() == "etag":
                            etag = v
                    t.update(url=url, league=stored, kind=kind, unit=p["unit"],
                             primary=p["primary"], entries=p["entries"],
                             fetched_at=now, checked_at=now, last_error=None,
                             etag=etag, fails=0)
                    out["fetched"] += 1
                else:
                    raise ValueError(f"HTTP {status}")
            except StopRound as e:  # the server asked to wait: no more GETs now
                t["last_error"] = str(e)[:200]
                out["stopped"] = True
                self._save()
                break
            except Exception as e:  # noqa: BLE001 - one bad type never stops the rest
                t["last_error"] = str(e)[:200]
                fails = t.get("fails")
                t["fails"] = (fails if isinstance(fails, int) and fails > 0 else 0) + 1
                out["errors"] += 1
            # AREA-AUDIT P3-7: on disk per request, so a core killed mid-loop
            # (up to 22 GETs x 10 s) does not re-request these types early.
            self._save()
        return out

    # -- offline reads
    def _entries(self, league, kinds):
        for name, _p, kind in _all_types():
            t = self.doc["types"].get(name) or {}
            if kind not in kinds or not isinstance(t.get("entries"), list):
                continue
            if league is not None and t.get("league") != league:
                continue
            for e in t["entries"]:
                if isinstance(e, dict):
                    yield name, t, e

    def lookup(self, item, league=None):
        """The cached price for one parsed item (theorycraft.item ParsedItem
        or a dict with rarity, name, base, flags), or None. Uniques match
        name + base type (+ corrupted), then name + base type; stackables
        match the base name. Never makes a request."""
        get = (item.get if isinstance(item, dict)
               else lambda k, d=None: getattr(item, k, d))
        rarity = (get("rarity") or "").upper()
        name, base = _key(get("name")), _key(get("base"))
        flags = get("flags") or {}
        corrupted = bool(flags.get("corrupted") or flags.get("twice_corrupted"))
        if rarity == "UNIQUE" and name:
            same = [(n, t, e) for n, t, e in self._entries(league, ("unique",))
                    if _key(e.get("name")) == name and (not base or _key(e.get("base")) == base)]
            pick = [x for x in same if x[2].get("corrupted") == corrupted] or same
            if not pick:
                return None
            # several lines left (variants): the most listed one
            n, t, e = max(pick, key=lambda x: x[2].get("listings") or 0)
            return self._result("unique", n, t, e)
        if base and rarity in ("CURRENCY", "GEM", "NORMAL", ""):
            for n, t, e in self._entries(league, ("exchange",)):
                if _key(e.get("name")) == base:
                    return self._result("stackable", n, t, e)
        return None

    @staticmethod
    def _result(kind, type_name, t, e):
        listings = e.get("listings")
        return {"kind": kind, "type": type_name, "name": e.get("name"),
                "value": e.get("value"), "unit": t.get("unit"),
                "primary": t.get("primary"), "listings": listings,
                "few": isinstance(listings, int) and listings < FEW_LISTINGS,
                "volume": e.get("volume"), "change": e.get("change"),
                "league": t.get("league"), "checked_at": t.get("checked_at")}

    def movers(self, league=None, n=MOVERS_N):
        """The biggest 7-day risers and fallers across the cached types
        (UTIL-MOVERS): [{name, type, value, unit, change}], thin markets
        left out. Never makes a request."""
        rows = []
        for name, t, e in self._entries(league, ("unique", "exchange")):
            ch, val = e.get("change"), e.get("value")
            if ch is None or val is None or ch == 0:
                continue
            if t.get("kind") == "unique":
                if not isinstance(e.get("listings"), int) or e["listings"] < MOVERS_MIN_LISTINGS:
                    continue
            elif (e.get("volume") or 0) < MOVERS_MIN_VOLUME:
                continue
            rows.append({"name": e.get("name"), "type": name, "value": val,
                         "unit": t.get("unit"), "change": ch})
        up = sorted((r for r in rows if r["change"] > 0), key=lambda r: -r["change"])[:n]
        down = sorted((r for r in rows if r["change"] < 0), key=lambda r: r["change"])[:n]
        return {"up": up, "down": down}

    def summary(self):
        """Per-type state for the rates snapshot (counts and errors only)."""
        out = {}
        for name, _p, _k in _all_types():
            t = self.doc["types"].get(name) or {}
            out[name] = {"entries": len(t.get("entries") or []),
                         "league": t.get("league"),
                         "last_error": t.get("last_error")}
        return out
