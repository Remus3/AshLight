"""TC-UPGRADE-STATS (decision 0037): weighted mod filters in the upgrade link.

Trade stat ids come only from the `trade_stats` field of the cached
repoe-fork stat_translations snapshot (server/al/tradestats.py), are used
only inside the offline ?q= URL, only while web data is on, and a stat
without an id gets no filter. The ids below are invented (no real id table
is bundled in the repo, decision 0009 item 1)."""

import json
import re
import socket
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

from server.al import trade, tradestats, upgrade
from server.al.core import Core
from server.al.theorycraft import codec
from server.al.theorycraft import evaluate as tc_evaluate
from server.al.theorycraft import model
from tc_eval_fixtures import EVAL_BUILD_XML, RARE_GLOVES

ROOT = Path(__file__).resolve().parents[1]
LIFE, FIRE, SPEED = "explicit.stat_1000001", "explicit.stat_1000002", "explicit.stat_1000003"


def _row(tid, text, kind="explicit"):
    return {"id": tid, "text": text, "type": kind, "option": None}


SNAPSHOT = [
    {"ids": ["life"], "English": [], "trade_stats": [
        _row("crafted.stat_1000001", "# to maximum Life", "crafted"),
        _row(LIFE, "# to maximum Life")]},
    {"ids": ["fire"], "trade_stats": [_row(FIRE, "#% to Fire Resistance")]},
    {"ids": ["speed"], "trade_stats": [_row("explicit.stat_1000009", "#% increased Attack Speed"),
                                       _row(SPEED, "#% increased  Attack Speed")]},
    {"ids": ["none"], "trade_stats": None},
    {"ids": ["bad"], "trade_stats": [_row("explicit.stat_12x", "Bad"), _row(5, "Five"),
                                     _row("explicit.stat_7", None), "junk"]},
    "junk",
]


def _decode(url):
    parts = urllib.parse.urlsplit(url)
    qs = urllib.parse.parse_qs(parts.query, strict_parsing=True)
    return json.loads(qs["q"][0])


# -- tradestats: the index ---------------------------------------------------

def test_index_keeps_explicit_ids_lowest_first():
    idx = tradestats.build_index(SNAPSHOT)
    assert idx == {"# to maximum life": LIFE, "#% to fire resistance": FIRE,
                   "#% increased attack speed": SPEED}
    assert tradestats.lookup(idx, "+# to maximum Life") == LIFE
    assert tradestats.lookup(idx, "+#% to Fire Resistance") == FIRE
    assert tradestats.lookup(idx, "+#% to Cold Resistance") is None  # no guess
    assert tradestats.lookup(idx, None) is None and tradestats.lookup(None, "x") is None
    assert tradestats.lookup({"x": "not.an.id"}, "x") is None
    for junk in (None, {}, "x", 5):
        assert tradestats.build_index(junk) == {}


def test_load_index_missing_malformed_oversized(tmp_path, monkeypatch):
    assert tradestats.load_index(tmp_path / "nope.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="ascii")
    assert tradestats.load_index(bad) == {}
    good = tmp_path / tradestats.FILE_NAME
    good.write_text(json.dumps(SNAPSHOT), encoding="ascii")
    assert tradestats.load_index(good)["# to maximum life"] == LIFE
    monkeypatch.setattr(tradestats, "MAX_BYTES", 10)
    assert tradestats.load_index(good) == {}


def test_index_cache_reloads_on_change(tmp_path):
    p = tmp_path / tradestats.FILE_NAME
    cache = tradestats.IndexCache(p)
    assert cache.get() == {}
    p.write_text(json.dumps(SNAPSHOT[:1]), encoding="ascii")
    assert list(cache.get()) == ["# to maximum life"]
    p.write_text(json.dumps(SNAPSHOT), encoding="ascii")
    assert len(cache.get()) == 3


def test_index_reads_the_snapshot_file_the_build_fetches():
    from server.al.theorycraft import snapshot
    assert snapshot.SOURCES["stat_translations"].endswith(
        "/poe2/stat_translations/stat_descriptions.json")
    assert tradestats.FILE_NAME == "stat_translations.json"  # <name>.json in the cache


# -- trade: the weighted group and the URL -----------------------------------

def test_upgrade_query_weight_group():
    q = trade.upgrade_query("Example Gloves", [(LIFE, 1), (FIRE, 0.5), (LIFE, 9),
                                               ("implicit.stat_1", 1), ("explicit.stat_x", 1),
                                               (SPEED, 0), (SPEED, float("nan")), (SPEED, True),
                                               "junk", (SPEED,)])
    assert q["query"]["stats"] == [{"type": "weight", "filters": [
        {"id": LIFE, "value": {"weight": 1.0}}, {"id": FIRE, "value": {"weight": 0.5}}]}]
    assert q["sort"] == {"statgroup.0": "desc"}
    assert q["query"]["type"] == "Example Gloves"
    assert trade.complexity(q) == 2 * trade.STAT_FILTER_COST
    # no usable pair: the plain base + rarity search
    assert trade.upgrade_query("Example Gloves", [(SPEED, -1)]) == trade.upgrade_query(
        "Example Gloves")
    assert "stats" not in trade.upgrade_query("Example Gloves")["query"]


def test_url_length_sane_at_max_filters():
    stats = [(f"explicit.stat_{4000000000 + i}", 123.4567) for i in range(upgrade.MAX_TOP)]
    url = trade.upgrade_link("Expert Sacrificial Garb of the Very Long Base", "L" * 60, stats)
    assert trade.is_search_link(url)
    assert len(url) < 2048  # well under browser and the builder's 4096 cap
    assert trade.complexity(_decode(url)) <= trade.MAX_COMPLEXITY


# -- upgrade.link: filters only for stats with an id -------------------------

def test_link_adds_filters_for_known_ids():
    result = tc_evaluate.evaluate(RARE_GLOVES, model.parse(EVAL_BUILD_XML))
    idx = tradestats.build_index(SNAPSHOT)
    doc = upgrade.link(result, "Example League", idx)
    assert doc["filters"] == [{"key": "#% increased Attack Speed", "id": SPEED, "weight": 2},
                              {"key": "+# to maximum Life", "id": LIFE, "weight": 1},
                              {"key": "+#% to Fire Resistance", "id": FIRE, "weight": 1}]
    q = _decode(doc["url"])
    assert [f["id"] for f in q["query"]["stats"][0]["filters"]] == [SPEED, LIFE, FIRE]
    assert doc["url"] == trade.upgrade_link(doc["base"], "Example League",
                                            [(SPEED, 2), (LIFE, 1), (FIRE, 1)])
    # no index: the unchanged base + rarity link
    plain = upgrade.link(result, "Example League", {})
    assert plain["filters"] == [] and "stats" not in _decode(plain["url"])["query"]
    assert upgrade.link(result, "Example League", None)["url"] == plain["url"]


# -- core: cached snapshot, web data gate, no network ------------------------

def _core(tmp_path, web_data):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    rt = tmp_path / "rt"
    (rt / "gamedata").mkdir(parents=True)
    (rt / "gamedata" / tradestats.FILE_NAME).write_text(json.dumps(SNAPSHOT), encoding="ascii")
    (rt / "local.json").write_text(json.dumps({"league": "Example League",
                                               "web_data": web_data}), encoding="ascii")
    return Core(runtime=rt, log_path=str(log), poll_s=0.05, web_fetch=_no_net)


def _no_net(*a, **k):
    raise AssertionError("network call during an item check")


@pytest.mark.parametrize("web_data", [True, False])
def test_press_uses_cached_ids_only_with_web_data(tmp_path, monkeypatch, web_data):
    for target, name in ((socket.socket, "connect"), (socket, "create_connection"),
                         (urllib.request, "urlopen")):
        monkeypatch.setattr(target, name, _no_net)
    c = _core(tmp_path, web_data)
    try:
        c.builds.load_code(codec.encode(EVAL_BUILD_XML))
        c.eval_press(RARE_GLOVES)
        up = c.state.eval["upgrade"]
        ids = [f["id"] for f in up["filters"]]
        assert ids == ([SPEED, LIFE, FIRE] if web_data else [])
        assert trade.is_search_link(up["url"])
    finally:
        c.close()


# -- floor: no trade endpoint is ever fetched --------------------------------

def test_no_code_fetches_a_trade_endpoint():
    """The only trade-site strings in app code are the offline link builder
    (trade.py) and the refusal check (webfetch.is_trade_url); no module
    names a trade data / API URL (decision 0017, ToU 7i)."""
    # "/api/trade-dismiss" is AshLight's own local route, not the trade site
    pat = re.compile(r"/api/trade2?(?![-\w])|data/stats", re.I)
    hits = []
    for base in ("server", "tools", "scripts", "app", "web"):
        for p in (ROOT / base).rglob("*"):
            if "node_modules" in p.parts or p.suffix not in (".py", ".js", ".ps1", ".html"):
                continue
            for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace")
                                     .splitlines(), 1):
                if pat.search(line):
                    hits.append(f"{p.relative_to(ROOT).as_posix()}:{n}")
    assert hits and all(h.startswith("server/al/webfetch.py:") for h in hits), hits
    src = (ROOT / "server" / "al" / "tradestats.py").read_text(encoding="ascii")
    assert "urllib.request" not in src and "socket" not in src and "http" not in src
