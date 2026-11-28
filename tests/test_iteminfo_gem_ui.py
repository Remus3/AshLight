"""ITEM-INFO-GEM-DETAIL (decision 0083 amendment 2026-11-28): the item
popover's gem rows and stat-line sections (web/iteminfo.js view /
gemView / button), driven under node; skips without node."""

import json
import re
import shutil
import subprocess

import pytest

import srcpaths

JS = srcpaths.read("iteminfo.js")

HARNESS = r"""
const path = require("path");
const I = require(path.join(process.argv[2], "iteminfo.js"));
const spark = {name: "Spark", sources: ["repoe-fork"], fields: {
  item_class: "Active Skill Gem", description: "Launch a spray of sparks.",
  gem: {kind: "active", tags: ["Spell", "Lightning"], cast_time_s: 0.7, max_level: 40,
        level: 1, costs: [{type: "Mana", amount: 5}, {type: "Strange", amount: 2}],
        sets: [{label: "Base", crit_pct: 9, lines: ["Deals 1 to 10 Lightning Damage",
                                                   "Fires 4 Projectiles"]},
               {label: "Cold-Infused", lines: ["Fires 12 Projectiles in a circle"]},
               {lines: ["Third line"]}]}}};
const support = {name: "Brutality I", sources: ["repoe-fork"], fields: {gem: {
  kind: "support", max_level: 1, level: 1, cost_multiplier: 120,
  sets: [{lines: ["Supported Skills deal 25% more Physical Damage"]}]}}};
const herald = {name: "Herald of Ice", sources: ["repoe-fork"], fields: {gem: {
  kind: "spirit", max_level: 40, level: 5, spirit: 30, cooldown_s: 1.5, cost_multiplier: 0,
  sets: [{label: "Explosion", damage_pct: 102, lines: []}]}}};
const strike = {name: "Ice Strike", sources: [], fields: {gem: {kind: "active",
  sets: [{damage_pct: 60, lines: ["Converts 80% to Cold"]}]}}};
function fakeDoc() {
  return {createElement: (t) => ({tag: t, attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }})};
}
const b20 = I.button(fakeDoc(), "Spark", 20);
const bBad = I.button(fakeDoc(), "Spark", 41);
const bNone = I.button(fakeDoc(), "Spark");
console.log(JSON.stringify({spark: I.view(spark), support: I.view(support),
  herald: I.view(herald), strike: I.view(strike), gemOnly: I.view({fields: {gem: {}}}, "X"),
  b20: b20.attrs["data-level"] || null, bBad: bBad.attrs["data-level"] || null,
  bNone: bNone.attrs["data-level"] || null}));
"""


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    node = shutil.which("node")
    if not node:
        pytest.skip("node not found")
    script = tmp_path_factory.mktemp("gemui") / "harness.js"
    script.write_text(HARNESS, encoding="ascii")
    res = subprocess.run([node, str(script), str(srcpaths.WEB)],
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout.strip().splitlines()[-1])


def test_spark_shows_its_game_details(run):
    v = run["spark"]
    assert v["rows"] == [
        {"label": "Item class", "value": "Active Skill Gem"},
        {"label": "Gem", "value": "Skill gem"},
        {"label": "Tags", "value": "Spell, Lightning"},
        {"label": "Gem level", "value": "1"},
        {"label": "Cost", "value": "5 Mana"},          # an unknown cost type is left out
        {"label": "Cast time", "value": "0.7 s"},
    ]
    assert v["texts"] == [{"cls": "iteminfo-desc", "text": "Launch a spray of sparks."}]
    assert v["gem"] == [
        {"title": "At gem level 1: Base", "rows": ["Critical hit chance: 9%",
                                                   "Deals 1 to 10 Lightning Damage",
                                                   "Fires 4 Projectiles"]},
        {"title": "At gem level 1: Cold-Infused", "rows": ["Fires 12 Projectiles in a circle"]},
        {"title": "At gem level 1: Set 3", "rows": ["Third line"]},   # no label: its place
    ]
    assert v["credits"] == ["Item data: RePoE fork export. Game data (c) Grinding Gear Games"]
    assert v["empty"] is False


def test_support_has_no_level_row_and_one_effect_section(run):
    v = run["support"]
    assert v["rows"] == [{"label": "Gem", "value": "Support gem"},
                         {"label": "Cost multiplier", "value": "120%"}]
    assert v["gem"] == [{"title": "Effect",
                         "rows": ["Supported Skills deal 25% more Physical Damage"]}]


def test_spirit_gem_rows_and_a_damage_only_set(run):
    v = run["herald"]
    assert {"label": "Reservation", "value": "30 Spirit"} in v["rows"]
    assert {"label": "Cooldown", "value": "1.5 s"} in v["rows"]
    assert {"label": "Gem level", "value": "5"} in v["rows"]
    assert "Cost multiplier" not in json.dumps(v["rows"])   # a 0 is left out
    assert v["gem"] == [{"title": "At gem level 5",
                         "rows": ["Attack damage: 102% of base"]}]


def test_unknown_fields_stay_out_and_credit_needs_the_source(run):
    assert run["strike"]["gem"] == [{"title": "Effect",
                                     "rows": ["Attack damage: 60% of base",
                                              "Converts 80% to Cold"]}]
    assert run["strike"]["credits"] == []
    assert run["gemOnly"]["empty"] is True and run["gemOnly"]["gem"] == []


def test_button_carries_only_a_valid_gem_level(run):
    assert run["b20"] == "20" and run["bBad"] is None and run["bNone"] is None


def test_popover_asks_for_the_level_only_in_its_query_and_paints_text_only():
    code = re.sub(r"/\*.*?\*/", "", JS, flags=re.S)
    assert '"&level=" + lvl' in code and "/^[1-9][0-9]?$/.test(lvl)" in code
    assert "innerHTML" not in code
