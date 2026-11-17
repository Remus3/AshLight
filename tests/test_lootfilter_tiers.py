"""UTIL-FILTER-2 price tiers (decision 0032): ashlight.filter gains value
tiers for uniques and stackables from the CACHED poe.ninja price book (no
new request, web data on only). Conservative documented thresholds in
Divine Orbs; nothing is ever hidden."""

from server.al import ninja
from server.al.theorycraft import lootfilter
from test_lootfilter import BUILD, check_grammar
from test_price_book import Clock, FakeNet, _client


def _prices(tmp_path, on=True):
    net, clock = FakeNet(), Clock()
    c, state = _client(tmp_path, net, clock)
    c.refresh()
    state["on"] = on
    n = len(net.calls)
    out = c.filter_prices()
    assert len(net.calls) == n  # reading the tiers never makes a request
    return out


def test_filter_prices_from_the_cache_in_divines(tmp_path):
    p = _prices(tmp_path)
    uniq = {u["base"]: u["value"] for u in p["uniques"]}
    # the cheapest well-listed unique of each base; the 3-listing corrupted
    # Ember Veil is a thin market and is left out
    assert uniq == {"Silk Robe": 12.5, "Runemastered Silk Robe": 55.0,
                    "Iron Circlet": 0.004}
    stack = {s["name"]: s["value"] for s in p["stackables"]}
    assert stack["Divine Orb"] == 1.0 and stack["Exalted Orb"] == 0.002
    assert stack["Greater Essence of Ruin"] == 0.35
    # almost no trade volume: left out
    assert "Lesser Essence of Ash" not in stack


def test_no_tiers_while_web_data_is_off_or_without_a_divine_rate(tmp_path):
    assert _prices(tmp_path, on=False) is None
    c = ninja.RatesClient(tmp_path / "empty", enabled=lambda: True)
    assert c.filter_prices() is None


def test_tiers_thresholds_are_conservative():
    p = {"uniques": [{"base": "Silk Robe", "value": 12.5}, {"base": "Iron Circlet", "value": 0.004},
                     {"base": "Mid Ring", "value": 0.2}],
         "stackables": [{"name": "Divine Orb", "value": 1.0},
                        {"name": "Greater Essence of Ruin", "value": 0.35},
                        {"name": "Exalted Orb", "value": 0.002},
                        {"name": "Odd (Thing)", "value": 9.0}]}
    t = lootfilter.tiers(p)
    assert t["unique_top"] == ["Silk Robe"] and t["unique_pick"] == ["Mid Ring"]
    assert t["stack_top"] == ["Divine Orb"]
    assert t["stack_pick"] == ["Greater Essence of Ruin"]
    # a name the filter grammar cannot carry as-is is left out, never mangled
    assert "Odd Thing" not in sum(t.values(), [])
    assert lootfilter.TOP_DIVINE == 1.0 and lootfilter.PICK_DIVINE == 0.05
    assert lootfilter.tiers(None) == {"unique_top": [], "unique_pick": [],
                                      "stack_top": [], "stack_pick": []}


def test_generated_filter_with_tiers_follows_the_grammar_and_never_hides(tmp_path):
    p = _prices(tmp_path)
    text = lootfilter.generate(BUILD, prices=p)
    check_grammar(text)
    assert "\nHide\n" not in text and "Hide" not in text.replace("# ", "")
    assert '    BaseType == "Silk Robe" "Runemastered Silk Robe"' in text \
        or '    BaseType == "Runemastered Silk Robe" "Silk Robe"' in text
    assert '    BaseType == "Divine Orb"\n' in text
    assert '    BaseType == "Greater Essence of Ruin"\n' in text
    assert "Iron Circlet" not in text and "Exalted Orb" not in text
    # the tier blocks come before the build block; the build block stays
    assert text.index('"Divine Orb"') < text.index('"Expert Hunting Bow"')
    assert text.count("\nShow\n") == 4
    assert "poe.ninja" in text


def test_tiers_without_a_build_and_unique_bases_checked_against_the_base_list(tmp_path):
    p = _prices(tmp_path)
    names = {"silk robe": "Silk Robe", "divine orb": "Divine Orb"}
    text = lootfilter.generate(None, names, prices=p)
    check_grammar(text)
    assert '    BaseType == "Silk Robe"\n' in text and "Runemastered" not in text
    # the base list holds stackables too and checks them (AREA-AUDIT P4-2)
    assert '"Divine Orb"' in text and "Greater Essence of Ruin" not in text
    assert "# No build loaded" in text


def test_no_prices_keeps_the_old_filter():
    assert lootfilter.generate(BUILD) == lootfilter.generate(BUILD, prices=None)
    assert lootfilter.generate(BUILD).count("\nShow\n") == 1


def test_endpoint_passes_the_cached_prices():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "server" / "al" / "http.py").read_text(
        encoding="ascii")
    block = src.split('if path == "/api/filter":', 1)[1].split("if path ==", 1)[0]
    assert "filter_prices()" in block and "generate(core.builds.build, names, prices)" in block
