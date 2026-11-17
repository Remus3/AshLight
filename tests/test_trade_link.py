"""PRICE-TRADE-LINK (decision 0017): the app calls no trade-site endpoint.
build_query and search_link build a trade2 search URL offline (name, base
type, rarity only) for the user to open in their own browser; no code path
sends a request to the trade site, and no pathofexile.com host is in any
webfetch allowlist."""

import importlib
import json
import pkgutil
import re
import urllib.parse
from pathlib import Path

import pytest

import server.al
from server.al import trade, webfetch
from server.al.theorycraft import item as item_mod
from tc_eval_fixtures import ADVANCED_RING, CURRENCY, RARE_GLOVES, UNIQUE_STAFF

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "https://www.pathofexile.com/trade2/search/poe2/"


def _decode(url):
    """(league, query object) of a search link."""
    assert url.startswith(PREFIX)
    parts = urllib.parse.urlsplit(url)
    league = urllib.parse.unquote(parts.path[len("/trade2/search/poe2/"):])
    qs = urllib.parse.parse_qs(parts.query, strict_parsing=True)
    assert list(qs) == ["q"] and len(qs["q"]) == 1
    return league, json.loads(qs["q"][0])


# -- build_query: name, base type, rarity only --------------------------------

def test_build_query_rare_is_base_and_rarity_only():
    q = trade.build_query(item_mod.parse(ADVANCED_RING))
    assert q == {"query": {"status": {"option": "online"}, "type": "Example Ring",
                           "filters": {"type_filters": {"filters": {
                               "rarity": {"option": "rare"}}}}},
                 "sort": {"price": "asc"}}


def test_build_query_has_no_stat_filters_and_no_flags():
    q = trade.build_query(item_mod.parse(RARE_GLOVES))
    assert "stats" not in q["query"]
    assert set(q["query"]["filters"]) == {"type_filters"}
    assert q["query"]["type"] == "Example Gloves"


def test_build_query_unique_by_name_and_base():
    q = trade.build_query(item_mod.parse(UNIQUE_STAFF))["query"]
    assert q["name"] == "Example Unique" and q["type"] == "Example Quarterstaff"
    # "unique" as a rarity option is unverified (research 0016): name + base
    # select the unique, as Exiled-Exchange-2 does
    assert "filters" not in q


def test_build_query_refuses_non_items():
    with pytest.raises(ValueError, match="^not an item$"):
        trade.build_query(item_mod.parse("hello"))
    with pytest.raises(ValueError, match="^not an item$"):
        trade.build_query(None)


def test_build_query_currency_has_no_rarity_filter():
    it = item_mod.parse(CURRENCY)
    try:
        q = trade.build_query(it)
    except ValueError as e:
        assert str(e) in ("not an item", "item has no base type")
        return
    assert "filters" not in q["query"]


# -- search_link: offline URL, round trip ------------------------------------

def test_search_link_round_trip():
    it = item_mod.parse(ADVANCED_RING)
    url = trade.search_link(it, "Rise of the Abyssal")
    assert url.startswith(PREFIX + "Rise%20of%20the%20Abyssal?q=")
    league, q = _decode(url)
    assert league == "Rise of the Abyssal"
    assert q == trade.build_query(it)
    assert url.isascii() and " " not in url and len(url) < 2048


def test_search_link_league_defaults_to_standard():
    it = item_mod.parse(UNIQUE_STAFF)
    for league in (None, "", "   ", 5):
        url = trade.search_link(it, league)
        assert _decode(url)[0] == "Standard"
        assert url.startswith(PREFIX + "Standard?q=")
    assert _decode(trade.search_link(it, " Example League "))[0] == "Example League"


def test_search_link_escapes_everything():
    it = item_mod.parse(UNIQUE_STAFF)
    url = trade.search_link(it, "a/b?c#d&e")
    assert url.startswith(PREFIX + "a%2Fb%3Fc%23d%26e?q=")
    assert _decode(url)[0] == "a/b?c#d&e"
    q = url.split("?q=", 1)[1]
    assert re.fullmatch(r"[A-Za-z0-9%._~-]+", q)  # fully percent-encoded JSON


def test_search_link_refuses_like_build_query():
    with pytest.raises(ValueError, match="^not an item$"):
        trade.search_link(item_mod.parse("hello"), "Standard")


# -- no trade request from the app (decision 0017) ---------------------------

def _server_modules():
    out = []
    for info in pkgutil.walk_packages(server.al.__path__, "server.al."):
        out.append(importlib.import_module(info.name))
    return out


def test_no_pathofexile_host_in_any_webfetch_allowlist():
    found = {}
    for mod in _server_modules():
        for name, value in vars(mod).items():
            if "ALLOWED_HOSTS" in name and isinstance(value, (tuple, list, set, frozenset)):
                found[f"{mod.__name__}.{name}"] = list(value)
    assert found, "no allowlists found: the scan is broken"
    for where, hosts in found.items():
        for h in hosts:
            assert not str(h).lower().rstrip(".").endswith("pathofexile.com"), (where, h)


def test_trade_module_has_no_network_code():
    for gone in ("TradeClient", "Job", "RateLimiter", "ALLOWED_HOSTS", "fetch_url",
                 "search_url", "USER_AGENT"):
        assert not hasattr(trade, gone), gone
    src = (ROOT / "server" / "al" / "trade.py").read_text(encoding="ascii")
    imports = [ln for ln in src.splitlines() if ln.startswith(("import ", "from "))]
    # math: the weight checks of the TC-UPGRADE-STATS stat group (decision 0037)
    assert imports == ["import json", "import math", "import urllib.parse"], imports


def test_no_code_path_names_a_trade_api_endpoint():
    pat = re.compile(r"/api/trade2?/|trade2/(data|fetch)|/data/stats|/data/leagues")
    hits = []
    for base in ("server", "app", "web", "tools", "scripts"):
        for p in (ROOT / base).rglob("*"):
            if "node_modules" in p.parts or not p.is_file():
                continue
            if p.suffix not in (".py", ".js", ".html", ".ps1", ".json"):
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            if pat.search(text):
                hits.append(str(p.relative_to(ROOT)))
    assert hits == []


@pytest.mark.parametrize("url", [
    "https://www.pathofexile.com/api/trade2/search/poe2/Standard",
    "https://www.pathofexile.com/api/trade2/fetch/a1?query=Q1",
    "https://www.pathofexile.com/api/trade2/data/stats",
    "https://pathofexile.com/api/trade/data/leagues",
    "https://WWW.PathOfExile.com/trade2/search/poe2/Standard?q=%7B%7D",
    "https://www.pathofexile.com/API/Trade2/data/leagues",
])
def test_webfetch_refuses_trade_urls_even_if_allowlisted(url):
    calls = []

    def fetch(*a):
        calls.append(a)
        return 200, {}, b"{}"

    hosts = ("www.pathofexile.com", "pathofexile.com")
    with pytest.raises(webfetch.UrlNotAllowed, match="trade"):
        webfetch.check_url(url, hosts)
    with pytest.raises(webfetch.UrlNotAllowed):
        webfetch.request("GET", url, {"User-Agent": "x"}, hosts, fetch=fetch)
    assert calls == []


def test_webfetch_refuses_a_redirect_into_the_trade_site():
    def fetch(method, url, headers, body=None):
        return 302, {"Location": "https://www.pathofexile.com/api/trade2/data/stats"}, b""

    with pytest.raises(webfetch.UrlNotAllowed):
        webfetch.request("GET", "https://www.pathofexile.com/developer/docs", {"User-Agent": "x"},
                         ("www.pathofexile.com",), fetch=fetch)


def test_webfetch_still_allows_other_ggg_paths():
    assert webfetch.check_url("https://www.pathofexile.com/developer/docs",
                              ("www.pathofexile.com",))
