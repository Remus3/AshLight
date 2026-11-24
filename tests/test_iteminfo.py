"""ITEM-INFO-CORE (decision 0083, decision 0082 part 1): the cache-only
item info lookup behind the token-gated GET /api/iteminfo.

An exact item name is matched over the cached repoe-fork base_items, the
cached repoe-fork uniques snapshot and the cached poe.ninja price book
(rates and book, only while web data is on). Unknown fields are absent,
never guessed; an unknown name answers 200 with empty fields; the name is
capped; the token, Host and Origin checks of the handler apply. No socket,
process or network call: the network entry points are patched to raise,
requests run through http.Handler on in-memory streams, runtime state
lives in tmp_path.
"""

import io
import json
import socket
import threading
import urllib.request

import pytest

from server.al import http as al_http
from server.al import iteminfo, ninja, plug, pricebook
from server.al.core import Core
from server.al.plug import iteminfo as iteminfo_plug
from server.al.theorycraft import snapshot

TOKEN = "i" * 48
HOST = "127.0.0.1:8961"
NOW = 1795200000.0
LEAGUE = "Dawn of the Hunt"

BASES = {
    "Metadata/Items/Currency/CurrencyRerollRare": {
        "name": "Chaos Orb", "item_class": "StackableCurrency",
        "release_state": "released", "drop_level": 12,
        "properties": {"description": "Removes a random modifier and augments a "
                                      "[ItemRarity|Rare] item with a new random modifier",
                       "directions": "Right click this item then left click a rare "
                                     "item to apply it.",
                       "stack_size": 20, "full_stack_turns_into": None}},
    "Metadata/Items/Currency/CurrencyUpgradeToMagic": {
        "name": "Orb of Transmutation", "item_class": "StackableCurrency",
        "release_state": "released",
        "properties": {"description": "", "directions": "", "stack_size": 40,
                       "full_stack_turns_into": None}},
    "Metadata/Items/Currency/CurrencyUpgradeToMagicShard": {
        "name": "Transmutation Shard", "item_class": "StackableCurrency",
        "release_state": "released",
        "properties": {"description": "", "directions": "A stack of 10 shards becomes "
                                                       "an [OrbOfTransmutation|Orb of "
                                                       "Transmutation]",
                       "stack_size": 10,
                       "full_stack_turns_into":
                           "Metadata/Items/Currency/CurrencyUpgradeToMagic"}},
    "Metadata/Items/Currency/CurrencyOldThing": {
        "name": "Old Thing", "item_class": "StackableCurrency",
        "release_state": "legacy", "properties": {"stack_size": 10}},
    "Metadata/Items/Armours/Boots/BootsDex1": {
        "name": "Leather Shoes", "item_class": "Boots", "release_state": "released",
        "drop_level": 1, "properties": {"stack_size": 1}},
}

UNIQUES = {
    "1": {"name": "Wanderlust", "item_class": "Boots", "base_item": "Leather Shoes"},
    "2": {"name": "Legacy Belt Thing", "item_class": "Belt",
          "release_state": "legacy"},
}

ICON = "https://web.poecdn.com/gen/image/abc/Wanderlust.png"

BOOK = {"types": {
    "UniqueArmours": {
        "url": "https://poe.ninja/x", "league": LEAGUE, "kind": "unique",
        "unit": "Exalted Orb", "primary": "exalted", "checked_at": NOW - 600,
        "entries": [
            {"name": "Wanderlust", "base": "Leather Shoes", "corrupted": False,
             "value": 3.0, "listings": 40, "change": 12.5, "icon": ICON,
             "flavour": "All the world is my road."},
            {"name": "Wanderlust", "base": "Leather Shoes", "corrupted": True,
             "value": 9.0, "listings": 2, "change": None}]},
    "Essences": {
        "url": "https://poe.ninja/y", "league": LEAGUE, "kind": "exchange",
        "unit": "Exalted Orb", "primary": "exalted", "checked_at": NOW - 300,
        "entries": [{"name": "Essence of Haste", "value": 0.5, "volume": 120.0,
                     "change": -3.0}]},
}}

RATES = {"league": LEAGUE, "primary": "exalted", "checked_at": NOW - 120,
         "rates": {"exalted": {"name": "Exalted Orb", "value": 1.0, "volume": 1000.0},
                   "divine": {"name": "Divine Orb", "value": 200.0, "volume": 50.0},
                   "chaos": {"name": "Chaos Orb", "value": 8.0, "volume": 400.0}}}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Every network entry point raises: the lookup must never reach one."""
    def boom(*a, **k):
        raise AssertionError("network call during an item info lookup")
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", boom)
    monkeypatch.setattr(snapshot, "http_fetch", boom)


def write_caches(root, bases=True, uniques=True, book=True, rates=True):
    gd = root / "gamedata"
    gd.mkdir(parents=True, exist_ok=True)
    if bases:
        (gd / "base_items.json").write_text(json.dumps(BASES), encoding="utf-8")
    if uniques:
        (gd / "uniques.json").write_text(json.dumps(UNIQUES), encoding="utf-8")
    nd = root / "cache" / "ninja"
    nd.mkdir(parents=True, exist_ok=True)
    if book:
        (nd / "book.json").write_text(json.dumps(BOOK), encoding="ascii")
    if rates:
        (nd / "rates.json").write_text(json.dumps(RATES), encoding="ascii")
    return gd, nd


def make_lookup(tmp_path, web=True, **kw):
    gd, nd = write_caches(tmp_path, **kw)
    rates = ninja.RatesClient(nd, enabled=lambda: web, book=pricebook.PriceBook(nd),
                              fetch=lambda *a, **k: (_ for _ in ()).throw(
                                  AssertionError("fetch")))
    return iteminfo.ItemInfo(gd / "base_items.json", gd / "uniques.json",
                             rates=rates, clock=lambda: NOW)


# --- the lookup -----------------------------------------------------------

def test_currency_from_base_items_and_rates(tmp_path):
    info = make_lookup(tmp_path).lookup("Chaos Orb")
    f = info["fields"]
    assert info["name"] == "Chaos Orb"
    assert f["item_class"] == "Stackable Currency"
    assert "rarity" not in f  # currency has no rarity; none is invented
    assert f["stack_size"] == 20
    assert "full_stack_turns_into" not in f
    assert f["description"] == ("Removes a random modifier and augments a Rare item "
                                "with a new random modifier")
    assert f["directions"].startswith("Right click this item")
    assert "release_state" not in f  # released is not shown
    assert "drop_level" not in f  # decision 0083 point 2
    m = f["market"]
    assert m["value"] == 8.0 and m["unit"] == "Exalted Orb"
    assert m["divine"] == pytest.approx(0.04)
    assert m["volume"] == 400.0
    assert m["credit"] == "Prices: poe.ninja"
    assert m["age_s"] == 120
    assert m["league"] == LEAGUE
    assert info["sources"] == ["repoe-fork", "poe.ninja"]


def test_exact_name_only_case_and_spaces_folded(tmp_path):
    look = make_lookup(tmp_path)
    assert look.lookup("  chaos   ORB ")["name"] == "Chaos Orb"
    assert look.lookup("Chaos")["fields"] == {}
    assert look.lookup("Chaos Orbs")["fields"] == {}


def test_shard_names_what_a_full_stack_becomes(tmp_path):
    f = make_lookup(tmp_path).lookup("Transmutation Shard")["fields"]
    assert f["stack_size"] == 10
    assert f["full_stack_turns_into"] == "Orb of Transmutation"
    assert f["directions"] == "A stack of 10 shards becomes an Orb of Transmutation"
    assert "description" not in f  # an empty text is unknown, not shown


def test_release_state_shown_only_when_not_released(tmp_path):
    look = make_lookup(tmp_path)
    assert look.lookup("Old Thing")["fields"]["release_state"] == "legacy"
    assert look.lookup("Legacy Belt Thing")["fields"]["release_state"] == "legacy"
    assert "release_state" not in look.lookup("Wanderlust")["fields"]


def test_stack_size_of_one_is_not_shown(tmp_path):
    f = make_lookup(tmp_path).lookup("Leather Shoes")["fields"]
    assert f == {"item_class": "Boots"}


def test_unique_from_uniques_and_the_book(tmp_path):
    info = make_lookup(tmp_path).lookup("Wanderlust")
    f = info["fields"]
    assert f["rarity"] == "Unique"
    assert f["item_class"] == "Boots"
    assert f["icon"] == ICON
    assert f["flavour"] == "All the world is my road."
    m = f["market"]
    # the uncorrupted, most listed line
    assert m["value"] == 3.0 and m["listings"] == 40 and m["change_7d"] == 12.5
    assert m["divine"] == pytest.approx(0.015)
    assert m["few"] is False
    assert m["age_s"] == 600
    assert info["sources"] == ["repoe-fork", "poe.ninja"]


def test_stackable_from_the_book_without_a_base(tmp_path):
    info = make_lookup(tmp_path).lookup("Essence of Haste")
    assert info["name"] == "Essence of Haste"
    m = info["fields"]["market"]
    assert m["value"] == 0.5 and m["volume"] == 120.0 and m["change_7d"] == -3.0
    assert set(info["fields"]) == {"market"}
    assert info["sources"] == ["poe.ninja"]


def test_web_data_off_leaves_out_every_poe_ninja_field(tmp_path):
    look = make_lookup(tmp_path, web=False)
    f = look.lookup("Wanderlust")["fields"]
    assert f == {"rarity": "Unique", "item_class": "Boots"}
    assert look.lookup("Essence of Haste")["fields"] == {}
    assert look.lookup("Chaos Orb")["sources"] == ["repoe-fork"]


def test_unknown_name_has_empty_fields(tmp_path):
    info = make_lookup(tmp_path).lookup("No Such Item")
    assert info == {"name": "No Such Item", "fields": {}, "sources": []}


def test_missing_caches_give_empty_fields(tmp_path):
    look = make_lookup(tmp_path, bases=False, uniques=False, book=False, rates=False)
    assert look.lookup("Chaos Orb")["fields"] == {}
    assert look.lookup("Wanderlust")["fields"] == {}


def test_malformed_caches_give_empty_fields(tmp_path):
    gd, nd = write_caches(tmp_path)
    (gd / "base_items.json").write_text("{not json", encoding="utf-8")
    (gd / "uniques.json").write_text("[1, 2, 3]", encoding="utf-8")
    look = iteminfo.ItemInfo(gd / "base_items.json", gd / "uniques.json", rates=None)
    assert look.lookup("Chaos Orb")["fields"] == {}
    assert look.lookup("Wanderlust")["fields"] == {}


def test_uniques_as_a_list_and_odd_entries(tmp_path):
    gd, _ = write_caches(tmp_path)
    (gd / "uniques.json").write_text(json.dumps(
        [{"name": "Wanderlust", "item_class": "Boots"}, "x", {"name": 3}, {}]),
        encoding="utf-8")
    look = iteminfo.ItemInfo(gd / "base_items.json", gd / "uniques.json", rates=None)
    assert look.lookup("Wanderlust")["fields"] == {"rarity": "Unique",
                                                   "item_class": "Boots"}


def test_name_cap_and_bad_names(tmp_path):
    look = make_lookup(tmp_path)
    with pytest.raises(ValueError):
        look.lookup("x" * (iteminfo.NAME_MAX + 1))
    for bad in ("", "   ", None, 3, "a\x00b", "a\nb"):
        with pytest.raises(ValueError):
            look.lookup(bad)
    assert look.lookup("x" * iteminfo.NAME_MAX)["fields"] == {}


def test_item_class_words():
    assert iteminfo.class_words("StackableCurrency") == "Stackable Currency"
    assert iteminfo.class_words("Boots") == "Boots"
    assert iteminfo.class_words("LifeFlask") == "Life Flask"
    assert iteminfo.class_words("") is None
    assert iteminfo.class_words(None) is None


def test_markup_is_plain_text():
    assert iteminfo.plain("a [ItemRarity|Rare] b [Quality] c") == "a Rare b Quality c"
    assert iteminfo.plain("  ") is None
    assert iteminfo.plain(None) is None
    assert len(iteminfo.plain("x" * 5000)) == iteminfo.TEXT_MAX


def test_module_imports_no_network_code():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(iteminfo))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names += [node.module or ""] + [a.name for a in node.names]
    for bad in ("urllib", "http", "socket", "ssl", "webfetch", "snapshot"):
        assert not any(bad in n.split(".") for n in names), bad


# --- the price book additions ---------------------------------------------

def test_book_parse_keeps_safe_icon_and_flavour_only():
    body = json.dumps({"core": {"primary": "exalted"}, "lines": [
        {"name": "A", "baseType": "B", "primaryValue": 1, "icon": ICON,
         "flavourText": "Words."},
        {"name": "C", "baseType": "D", "primaryValue": 2,
         "icon": "https://evil.example/x.png", "flavourText": 5},
        {"name": "E", "baseType": "F", "primaryValue": 3, "icon": "/gen/image/x.png"},
    ]})
    entries = pricebook.parse_item_overview(body)["entries"]
    assert entries[0]["icon"] == ICON and entries[0]["flavour"] == "Words."
    assert "icon" not in entries[1] and "flavour" not in entries[1]
    assert "icon" not in entries[2]


def test_book_exchange_parse_keeps_safe_icon():
    body = json.dumps({"core": {"primary": "exalted"},
                       "items": [{"id": "h", "name": "Essence of Haste", "image": ICON},
                                 {"id": "g", "name": "Other", "image": "/gen/x.png"}],
                       "lines": [{"id": "h", "primaryValue": 1},
                                 {"id": "g", "primaryValue": 2}]})
    entries = pricebook.parse_exchange_overview(body)["entries"]
    assert entries[0]["icon"] == ICON
    assert "icon" not in entries[1]


def test_book_info_by_exact_name(tmp_path):
    _, nd = write_caches(tmp_path)
    book = pricebook.PriceBook(nd)
    hit = book.info("wanderlust", league=LEAGUE)
    assert hit["name"] == "Wanderlust" and hit["value"] == 3.0
    assert hit["icon"] == ICON
    assert book.info("Wanderlust", league="Other league") is None
    assert book.info("Essence of Haste", league=LEAGUE)["volume"] == 120.0
    assert book.info("Nothing", league=LEAGUE) is None


# --- the snapshot source --------------------------------------------------

def test_snapshot_fetches_the_uniques_source_by_default(tmp_path):
    assert snapshot.ITEM_SOURCES["uniques"] == "https://repoe-fork.github.io/poe2/uniques.json"
    snapshot._check_url(snapshot.ITEM_SOURCES["uniques"])
    assert "uniques" in snapshot.SOURCE_CAPS
    assert set(snapshot.default_sources()) == set(snapshot.SOURCES) | {"uniques"}
    seen = []

    def fetch(url, headers):
        seen.append(url)
        raise snapshot.FetchError("network: offline (stub)")
    snapshot.main(["--dir", str(tmp_path), "--opt-in"], environ={}, fetch=fetch,
                  contact="", web_data=False)
    assert snapshot.ITEM_SOURCES["uniques"] in seen
    seen.clear()
    snapshot.main(["--dir", str(tmp_path)], environ={}, fetch=fetch, contact="",
                  web_data=False)
    assert seen == []  # web data off: nothing at all


# --- the route ------------------------------------------------------------

@pytest.fixture
def core(tmp_path):
    rt = tmp_path / "rt"
    write_caches(rt)
    (rt / "local.json").write_text(json.dumps({"web_data": True}), encoding="utf-8")
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    c = Core(runtime=rt, log_path=str(log), tail=False)
    yield c
    c.close()


class FakeServer:
    def __init__(self, core):
        self.core = core
        self.token = TOKEN
        self.allowed_hosts = {HOST}
        self.allowed_origins = {f"http://{h}" for h in self.allowed_hosts}
        self.events_tap = False
        self.stopping = threading.Event()
        self.sse_slots = threading.BoundedSemaphore(al_http.MAX_SSE_CLIENTS)


def call(core, path, headers=None, method="GET", host=HOST):
    lines = [f"{method} {path} HTTP/1.1", f"Host: {host}", "Connection: close"]
    lines += [f"{k}: {v}" for k, v in (headers or {}).items()]
    raw = ("\r\n".join(lines) + "\r\n\r\n").encode("ascii")

    class H(al_http.Handler):
        def setup(self):
            self.connection = None
            self.rfile = io.BytesIO(raw)
            self.wfile = io.BytesIO()

        def finish(self):
            H.out = self.wfile.getvalue()

    H(None, ("127.0.0.1", 50000), FakeServer(core))
    head, _, body = H.out.partition(b"\r\n\r\n")
    return int(head.split(b" ", 2)[1]), body


def auth():
    return {"X-AL-Token": TOKEN}


def test_route_is_a_token_gated_plug_get():
    assert ("GET", iteminfo_plug.PATH) in plug.all_routes()
    assert ("POST", iteminfo_plug.PATH) not in plug.all_routes()
    assert al_http.Handler._needs_token(iteminfo_plug.PATH)


def test_route_answers_from_the_caches(core):
    status, body = call(core, "/api/iteminfo?name=Wanderlust", auth())
    assert status == 200
    doc = json.loads(body)
    assert doc["name"] == "Wanderlust"
    assert doc["fields"]["rarity"] == "Unique"
    assert doc["fields"]["market"]["value"] == 3.0
    status, body = call(core, "/api/iteminfo?name=Chaos%20Orb", auth())
    assert status == 200 and json.loads(body)["fields"]["stack_size"] == 20


def test_route_unknown_name_is_200_with_empty_fields(core):
    status, body = call(core, "/api/iteminfo?name=Nope", auth())
    assert status == 200
    assert json.loads(body) == {"name": "Nope", "fields": {}, "sources": []}


def test_route_refuses_bad_names(core):
    long_name = "x" * (iteminfo.NAME_MAX + 1)
    for q in ("", "?name=", f"?name={long_name}", "?name=a&name=b", "?name=a%00b"):
        status, body = call(core, "/api/iteminfo" + q, auth())
        assert status == 400, q
        assert "error" in json.loads(body)


def test_route_needs_the_token(core):
    status, _ = call(core, "/api/iteminfo?name=Wanderlust")
    assert status == 401
    status, _ = call(core, "/api/iteminfo?name=Wanderlust", {"X-AL-Token": "x" * 48})
    assert status == 401


def test_route_checks_host_and_origin(core):
    status, _ = call(core, "/api/iteminfo?name=Wanderlust", auth(), host="evil.example")
    assert status in (400, 403)
    status, _ = call(core, "/api/iteminfo?name=Wanderlust",
                     dict(auth(), Origin="http://evil.example"))
    assert status == 403


def test_route_web_data_off_shows_no_market(core):
    (core.runtime / "local.json").write_text(json.dumps({"web_data": False}),
                                             encoding="utf-8")
    status, body = call(core, "/api/iteminfo?name=Wanderlust", auth())
    assert status == 200
    f = json.loads(body)["fields"]
    assert "market" not in f and "icon" not in f and "flavour" not in f
