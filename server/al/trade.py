"""PRICE-TRADE-LINK (decision 0017): an offline trade2 search link for a
parsed item.

The app calls no trade-site endpoint: this module has no network code, and
server/al/webfetch.py refuses every trade URL. `search_link` builds
https://www.pathofexile.com/trade2/search/poe2/<league>?q=<url-encoded JSON>
that the user may open in their own browser from the dashboard; the core
never opens it. The `?q=` form carries the same object as a trade search
body (research 0016: community tools build this link; GGG does not document
it). The price query holds the item name (uniques), base type and rarity
only. The upgrade query may add one weighted stat group whose ids come from
the cached repoe-fork snapshot (server/al/tradestats.py, decision 0037).
TC-UPGRADE reuses the same builder: `upgrade_link` searches rare items of
the base the build wears in the checked slot (server/al/upgrade.py).

This module never reads the clipboard and never sends anything to the game.
"""

import json
import math
import urllib.parse

TRADE_SITE = "https://www.pathofexile.com"
SEARCH_PAGE = "/trade2/search/poe2/{league}"
DEFAULT_LEAGUE = "Standard"
# rarity words of theorycraft.item (upper case) -> the trade rarity filter.
# "unique" is not in it: no source confirms that option (research 0016), and
# name + base already select a unique.
_RARITY = {"NORMAL": "normal", "MAGIC": "magic", "RARE": "rare"}


def build_query(item):
    """A trade2 search object for a parsed item (theorycraft.item.ParsedItem):
    uniques by name + base type, other items by base type and rarity. Raises
    ValueError "not an item" / "item has no base type"."""
    if item is None or not getattr(item, "is_item", False):
        raise ValueError("not an item")
    q = {"status": {"option": "online"}}
    rarity = (item.rarity or "").upper()
    if rarity == "UNIQUE" and item.name:
        q["name"] = item.name
        if item.base:
            q["type"] = item.base
    elif item.base:
        q["type"] = item.base
    else:
        raise ValueError("item has no base type")
    return _search(q, rarity)


def _search(q, rarity):
    """The search object around query `q`, with the rarity filter for an
    upper-case rarity word that has one (shared by both builders)."""
    if rarity in _RARITY:
        q["filters"] = {"type_filters": {"filters": {"rarity": {"option": _RARITY[rarity]}}}}
    return {"query": q, "sort": {"price": "asc"}}


# TC-UPGRADE (decision 0017 item 3): the trade site caps a search at a
# complexity of 200, 4 per stat filter (research 0010 section 4, PoB's
# TradeQueryGenerator). The upgrade link carries at most upgrade.MAX_TOP
# weighted stat filters (TC-UPGRADE-STATS, decision 0037); the cap is
# checked anyway.
MAX_COMPLEXITY = 200
STAT_FILTER_COST = 4
UPGRADE_RARITY = "RARE"


def complexity(search):
    """STAT_FILTER_COST per stat filter in a search object (0 without stats)."""
    q = search.get("query") if isinstance(search, dict) else None
    groups = q.get("stats") if isinstance(q, dict) else None
    n = 0
    for g in groups if isinstance(groups, list) else ():
        filters = g.get("filters") if isinstance(g, dict) else None
        n += len(filters) if isinstance(filters, list) else 0
    return n * STAT_FILTER_COST


def _weight_group(stats):
    """One trade "weight" stat group from [(trade id, weight)] pairs
    (TC-UPGRADE-STATS, decision 0037): ids of the form explicit.stat_<n>,
    weights finite and > 0, first id wins on a repeat; None when no pair is
    usable."""
    filters, seen = [], set()
    for pair in stats or ():
        try:
            tid, w = pair
        except (TypeError, ValueError):
            continue
        if not (isinstance(tid, str) and tid.startswith("explicit.stat_")
                and tid[len("explicit.stat_"):].isdigit()) or tid in seen:
            continue
        if isinstance(w, bool) or not isinstance(w, (int, float))                 or not math.isfinite(w) or w <= 0:
            continue
        seen.add(tid)
        filters.append({"id": tid, "value": {"weight": round(float(w), 4)}})
    return {"type": "weight", "filters": filters} if filters else None


def upgrade_query(base, stats=None):
    """A trade2 search object for an upgrade candidate: rare items of `base`
    (the base the build wears in the slot, else the checked item's). With
    `stats` ([(explicit trade id, weight)], TC-UPGRADE-STATS) it adds one
    weighted stat group and sorts by its sum; without, base type and rarity
    only. Raises ValueError "no base type" for a missing base, "too complex"
    past MAX_COMPLEXITY."""
    if not isinstance(base, str) or not base.strip():
        raise ValueError("no base type")
    search = _search({"status": {"option": "online"}, "type": base.strip()}, UPGRADE_RARITY)
    group = _weight_group(stats)
    if group is not None:
        search["query"]["stats"] = [group]
        search["sort"] = {"statgroup.0": "desc"}
    if complexity(search) > MAX_COMPLEXITY:
        raise ValueError("too complex")
    return search


def league_or_default(league):
    """The configured league text, else DEFAULT_LEAGUE (nothing is fetched)."""
    if isinstance(league, str) and league.strip():
        return league.strip()
    return DEFAULT_LEAGUE


def link_for(search, league=None):
    """The trade2 search URL for a search object in `league` (else Standard).
    Pure: builds text only; the one URL builder of both links."""
    body = json.dumps(search, separators=(",", ":"), sort_keys=True, ensure_ascii=True)
    path = SEARCH_PAGE.format(league=urllib.parse.quote(league_or_default(league), safe=""))
    return TRADE_SITE + path + "?q=" + urllib.parse.quote(body, safe="")


def search_link(item, league=None):
    """The trade2 search URL for a parsed item in `league` (else Standard).
    Pure: builds text only. Raises ValueError like build_query."""
    return link_for(build_query(item), league)


def upgrade_link(base, league=None, stats=None):
    """The trade2 search URL for upgrade candidates of `base` in `league`,
    weighted by `stats` when given. Pure. Raises ValueError like
    upgrade_query."""
    return link_for(upgrade_query(base, stats), league)


def is_search_link(url):
    """True for a URL of exactly the search_link shape (https, the trade
    site host, the trade2 search page, one q parameter)."""
    if not isinstance(url, str) or len(url) > 4096 or not url.isascii():
        return False
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    return (parts.scheme == "https" and parts.netloc == "www.pathofexile.com"
            and parts.path.startswith("/trade2/search/poe2/") and not parts.fragment
            and parts.query.startswith("q=") and "&" not in parts.query)
