"""DATA-PRICE-TYPES-FILE (F-201): the price book's unique and exchange type
lists live in server/al/data/price_types.json, hot reloaded (decision 0042).

The shipped file holds today's 8 + 13 names; a bad edit keeps the last good
lists with a reload note; a dropped type is no longer requested. Mocked GET
only: nothing reaches the network. Tmp files only."""

import json
import os
from urllib.parse import parse_qs, urlparse

from server.al import hotreload, pricebook

UNIQUE = ["UniqueWeapons", "UniqueArmours", "UniqueAccessories",
          "UniqueFlasks", "UniqueCharms", "UniqueJewels",
          "UniqueSanctumRelics", "UniqueTablets"]
EXCHANGE = ["Fragments", "Abyss", "UncutGems", "LineageSupportGems",
            "Essences", "SoulCores", "Idols", "Runes", "Ritual",
            "Expedition", "Delirium", "Breach", "Verisium"]
EMPTY = json.dumps({"core": {"items": [], "primary": "divine"},
                    "lines": [], "items": []}).encode()


def _write(path, doc, n=[0]):
    """Write `doc` (a dict, or raw text) and move the mtime so the stat
    signature always changes."""
    text = doc if isinstance(doc, str) else json.dumps(doc)
    path.write_text(text, encoding="utf-8")
    n[0] += 1
    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + n[0] * 1_000_000_000))


def _use(monkeypatch, tmp_path, doc):
    f = tmp_path / "price_types.json"
    _write(f, doc)
    monkeypatch.setattr(pricebook, "TYPES_PATH", f)
    return f


def test_the_shipped_file_lists_todays_21_types():
    raw = pricebook.TYPES_PATH.read_bytes()
    assert raw.decode("ascii") and b"\r" not in raw
    unique, exchange = pricebook.load_types(pricebook.TYPES_PATH)
    assert list(unique) == UNIQUE and list(exchange) == EXCHANGE
    assert (len(unique), len(exchange)) == (8, 13)
    assert unique == pricebook.BUILTIN_UNIQUE and exchange == pricebook.BUILTIN_EXCHANGE
    assert pricebook.UNIQUE_TYPES == unique
    assert pricebook.EXCHANGE_TYPES == exchange
    kinds = [(n, k) for n, _p, k in pricebook._all_types()]
    assert kinds == ([(n, "unique") for n in UNIQUE]
                     + [(n, "exchange") for n in EXCHANGE])
    doc = json.loads(raw)
    assert doc["schema"] == 1 and doc["src"] and doc["checked"]


def test_a_bad_edit_keeps_the_last_good_lists(monkeypatch, tmp_path):
    good = {"unique": UNIQUE[:2], "exchange": EXCHANGE[:3]}
    f = _use(monkeypatch, tmp_path, good)
    assert pricebook.types() == (tuple(UNIQUE[:2]), tuple(EXCHANGE[:3]))
    bad_edits = [
        "{not json",
        "[]",
        {"unique": UNIQUE[:2]},                                # list missing
        {"unique": "UniqueWeapons", "exchange": []},           # not a list
        {"unique": ["Unique Weapons"], "exchange": []},        # not letters only
        {"unique": ["Unique-Weapons"], "exchange": []},
        {"unique": [7], "exchange": []},
        {"unique": ["UniqueWeapons", "UniqueWeapons"], "exchange": []},
        {"unique": ["Runes"], "exchange": ["Runes"]},          # in both lists
        {"unique": ["Abc" + "x" * i for i in range(41)], "exchange": []},
    ]
    for bad in bad_edits:
        _write(f, bad)
        assert pricebook.types() == (tuple(UNIQUE[:2]), tuple(EXCHANGE[:3])), bad
        note = pricebook._types_watch.error
        assert note and note.startswith("price types did not load"), bad
        assert note in hotreload.REGISTRY.notes()
        assert str(tmp_path) not in note
    # 40 names is the bound, not over it
    forty = ["Abc" + "x" * i for i in range(40)]
    _write(f, {"unique": forty, "exchange": []})
    assert pricebook.types() == (tuple(forty), ())
    assert pricebook._types_watch.error is None
    # a fixed edit is taken at once; a removed file reads as the built-in lists
    _write(f, {"unique": UNIQUE, "exchange": EXCHANGE[1:]})
    assert pricebook.EXCHANGE_TYPES == tuple(EXCHANGE[1:])
    f.unlink()
    assert pricebook.types() == (pricebook.BUILTIN_UNIQUE, pricebook.BUILTIN_EXCHANGE)


def _requested(book, now):
    asked = []

    def get(url, etag):
        asked.append(parse_qs(urlparse(url).query)["type"][0])
        return 200, {}, EMPTY

    out = book.refresh(get, "https://poe.ninja", "Example League", now)
    assert out["errors"] == 0
    return asked


def test_a_dropped_type_is_no_longer_requested(monkeypatch, tmp_path):
    f = _use(monkeypatch, tmp_path, {"unique": UNIQUE, "exchange": EXCHANGE})
    cache = tmp_path / "cache"
    cache.mkdir()
    book = pricebook.PriceBook(cache)
    now = 1_800_000_000.0
    assert _requested(book, now) == UNIQUE + EXCHANGE
    _write(f, {"unique": [n for n in UNIQUE if n != "UniqueTablets"],
               "exchange": [n for n in EXCHANGE if n != "Verisium"]})
    later = now + pricebook.INTERVAL_S + 1
    asked = _requested(book, later)
    assert "UniqueTablets" not in asked and "Verisium" not in asked
    assert len(asked) == 19
    assert "UniqueTablets" not in book.summary() and "Verisium" not in book.summary()
    book.note_press("Verisium", later)
    assert not book.pressed("Verisium", later)
    # an added type is asked at once on the next round, the rest not yet due
    _write(f, {"unique": UNIQUE, "exchange": EXCHANGE + ["Ultimatum"]})
    assert _requested(book, later + 1) == ["UniqueTablets", "Verisium", "Ultimatum"]
