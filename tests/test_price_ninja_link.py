"""DATA-PRICE-NINJA-LINK (folded into DATA-GUIDE-ONE-BLOCK; research 0036
R12, decision 0016 amendment 2026-11-23): the price card carries
`ninja_url`, the poe.ninja category page of the checked item, only for a
category and league whose page form was read from poe.ninja's public pages.
The app requests nothing for it; the player's browser opens it.

No network: a request attempt fails the test. Fixture values are invented.
"""

import ast
import socket
import urllib.request
from pathlib import Path

import pytest

from server.al import ninjalink, price

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "server" / "al" / "ninjalink.py"
UNIQUE_TEXT = """Item Class: Staves
Rarity: Unique
Example Staff Name
Example Staff
--------
Item Level: 70
"""


def _hit(type_name="UniqueWeapons", league="Standard"):
    return {"kind": "unique", "type": type_name, "name": "Example Staff Name",
            "value": 3.5, "unit": "Divine Orb", "primary": "divine", "listings": 40,
            "few": False, "volume": None, "change": None, "league": league,
            "checked_at": 100.0}


def _press(lookup, text=UNIQUE_TEXT):
    cards = []
    c = price.PriceChecker(league=lambda: "Standard", lookup=lookup,
                           card=lambda card, at=None, keep_time=False: cards.append(card),
                           clock=lambda: 1000.0)
    c.request(text, at=5.0)
    return cards[-1]


@pytest.fixture
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("the price card made a request")
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)


def test_card_carries_an_https_poe_ninja_url_for_a_unique(no_network):
    card = _press(lambda item: _hit())
    assert card["status"] == "link" and card["ninja"]["value"] == 3.5
    assert card["ninja_url"] == "https://poe.ninja/poe2/economy/standard/unique-weapons"
    assert ninjalink.is_page_url(card["ninja_url"])
    # a leagues-list entry works as well as an id
    assert ninjalink.url_for("UniqueArmours", {"id": "Forbidden Rites", "name": "x"}) == \
        "https://poe.ninja/poe2/economy/forbiddenrites/unique-armours"
    # card_of keeps only a page URL of the allowed shape
    doc = {"status": "link", "url": "https://www.pathofexile.com/trade2/search/poe2/S?q=%7B%7D",
           "item": {}, "ninja_url": "https://poe.ninja/poe2/economy/standard/currency"}
    assert price.card_of(doc)["ninja_url"] == doc["ninja_url"]
    for bad in ("http://poe.ninja/poe2/economy/standard/currency",
                "https://poe.ninja.evil/poe2/economy/standard/currency",
                "https://poe.ninja/poe2/economy/standard/currency?x=1",
                "https://poe.ninja/poe2/" + "api/economy/leagues", "javascript:x", 5, None):
        assert price.card_of(dict(doc, ninja_url=bad))["ninja_url"] is None, bad


def test_no_url_for_an_unknown_category(no_network):
    for type_name in ("Abyss", "Ritual", "Delirium", "Breach", "UniqueSanctumRelics",
                      "Maps", "", None, 7):
        assert ninjalink.url_for(type_name, "Standard") is None, type_name
        assert _press(lambda item, t=type_name: _hit(t))["ninja_url"] is None, type_name
    # a league whose page form was not read gets no link either
    for league in ("HC Forbidden Rites", "Some New League", "", None, {"name": "Standard"}):
        assert ninjalink.url_for("UniqueWeapons", league) is None, league
        assert _press(lambda item, lg=league: _hit(league=lg))["ninja_url"] is None
    # no cached price (web data off) -> no category known -> no link
    card = _press(lambda item: None)
    assert card["ninja"] is None and card["ninja_url"] is None
    assert price.card_of({"status": "skipped", "reason": "not an item"})["ninja_url"] is None


def test_the_app_requests_nothing_for_the_link(no_network):
    card = _press(lambda item: _hit("Currency"))
    assert card["ninja_url"] == "https://poe.ninja/poe2/economy/standard/currency"
    # the module is pure: no network, file or process import
    tree = ast.parse(SRC.read_text(encoding="ascii"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add((node.module or "").split(".")[0])
    assert names <= {"re"}, names
    # a lookup that raises still leaves a link card with no page link
    def boom(item):
        raise RuntimeError("cache unreadable")
    card = _press(boom)
    assert card["status"] == "link" and card["ninja_url"] is None


def test_ninjalink_table_has_no_api_route():
    for table in (ninjalink.CATEGORY_PAGES, ninjalink.LEAGUE_PAGES):
        for key, slug in table.items():
            for form in (key, slug, slug.upper(), ninjalink.BASE + slug):
                assert "/api/" not in form and "api" not in slug.split("-"), form
    for type_name in ninjalink.CATEGORY_PAGES:
        for league in ninjalink.LEAGUE_PAGES:
            url = ninjalink.url_for(type_name, league)
            assert url is not None and "/api/" not in url and ninjalink.is_page_url(url)
    assert "/api/" not in ninjalink.BASE and ninjalink.BASE.startswith("https://poe.ninja/")
    assert not ninjalink.is_page_url("https://poe.ninja/poe2/api/economy/x")
