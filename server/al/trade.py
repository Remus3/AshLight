"""PRICE-TRADE-LINK (decision 0017): an offline trade2 search link for a
parsed item.

The app calls no trade-site endpoint: this module has no network code, and
server/al/webfetch.py refuses every trade URL. `search_link` builds
https://www.pathofexile.com/trade2/search/poe2/<league>?q=<url-encoded JSON>
that the user may open in their own browser from the dashboard; the core
never opens it. The `?q=` form carries the same object as a trade search
body (research 0016: community tools build this link; GGG does not document
it). The query holds the item name (uniques), base type and rarity only, no
stat filters (TC-UPGRADE-STATS has no permitted stat-id source yet).

This module never reads the clipboard and never sends anything to the game.
"""

import json
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
    if rarity in _RARITY:
        q["filters"] = {"type_filters": {"filters": {"rarity": {"option": _RARITY[rarity]}}}}
    return {"query": q, "sort": {"price": "asc"}}


def league_or_default(league):
    """The configured league text, else DEFAULT_LEAGUE (nothing is fetched)."""
    if isinstance(league, str) and league.strip():
        return league.strip()
    return DEFAULT_LEAGUE


def search_link(item, league=None):
    """The trade2 search URL for a parsed item in `league` (else Standard).
    Pure: builds text only. Raises ValueError like build_query."""
    body = json.dumps(build_query(item), separators=(",", ":"), sort_keys=True,
                      ensure_ascii=True)
    path = SEARCH_PAGE.format(league=urllib.parse.quote(league_or_default(league), safe=""))
    return TRADE_SITE + path + "?q=" + urllib.parse.quote(body, safe="")


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
