"""PLAY-TD-19E-ITEM-TEXT: each worn item's raw item text on the gear
pager's Full text page.

The Build card's Health and next gear page lists one line per gear row
(slot, name, base, rarity). A row that carries item text (g.text from
web/tc.js buildView) hands that text to the pager as the row's whole
text, so the Full text page (and the row's title) shows it, one press of
Full text away: "slot: name - " and the item text's own lines joined by
"; ", minus what the row line already says and PoB's bookkeeping lines,
so the first mods fit the 3 x 47 page (design-reviewer D-1). A row
without text keeps its one-line text there. No
details fold comes back (a fold can grow a fixed card, PLAY-TD-19C).

Static checks read web/panels/pager.js (linkPager, the shared pager
plumbing, moved there from web/app.js by TEST-WEB-PANELS-C2) and
web/panels/build.js (renderBuild, moved there by TEST-WEB-PANELS-A;
adjudicated 2026-11-21). One behavioural check drives web/search.js
rowPager under node with the options linkPager builds, one runs
gearFull on a realistic PoB item; they skip without node."""

import json
import re
import shutil
import subprocess

import pytest

import srcpaths

APP = srcpaths.read("app.js")
PAGER = srcpaths.read("panels/pager.js")
BUILD = srcpaths.read("panels/build.js")


def _block(src, start, end_pat=r"\n    \}\);\n"):
    i = src.index(start)
    m = re.compile(end_pat).search(src, i)
    assert m, "end of block not found after " + start
    return src[i:m.end()]


def _gear_call():
    return _block(BUILD, 'linkPager("build-gear"')


def _link_pager():
    return _block(PAGER, "function linkPager(", r"\n    \}\n")


def _gear_full_src():
    return _block(BUILD, "  var ITEM_META", r"\n  \}\n")


def test_gear_rows_carry_item_text_as_full_text():
    call = _gear_call()
    # the row's whole text comes from the gear row's item text (gearFull)
    assert re.search(r"full:\s*gearFull\(g, line\)", call), call
    assert re.search(r"full:\s*function\s*\(r\)\s*\{\s*return r\.full \|\| r\.text;", call), call
    src = _gear_full_src()
    assert "g.text" in src and "g.slot" in src


def test_visible_row_line_stays_slot_name_base_rarity():
    call = _gear_call()
    assert re.search(r"var line = g\.slot \+ \": \" \+ g\.name", call), call
    assert "g.base" in call and "g.rarity" in call
    assert re.search(r"text:\s*line\b", call), call
    assert re.search(r"text:\s*function\s*\(r\)\s*\{\s*return r\.text;", call), call
    # the empty build keeps its one row
    assert '"No gear yet - paste a build code that includes items."' in call


def test_row_without_text_keeps_its_one_line_text():
    call = _gear_call()
    assert "gearFull(g, line)" in call
    # no item lines -> the same one-line text (behaviour: test_gear_full_*)
    assert re.search(r"return mods\.length \? .+ : line;", _gear_full_src())


def test_link_pager_forwards_full_text_and_list_line():
    fn = _link_pager()
    assert re.search(r"text:\s*full \|\| opts\.text", fn), fn
    assert re.search(r"parts:\s*full \? function \(r\) \{ return \[\{ text: opts\.text\(r\) \}\]; \}"
                     r" : undefined", fn), fn
    # a caller without full is unchanged: text stays opts.text, no parts
    assert 'typeof opts.full === "function" ? opts.full : null' in fn


def test_no_details_fold_comes_back():
    call = _gear_call()
    assert "details" not in call.lower()
    render = _block(BUILD, "function renderBuild()", r"\n  \}\n")
    assert "details" not in render.lower()
    for src in (APP, PAGER):
        assert "createElement(\"details\")" not in src and "createElement('details')" not in src
    html = srcpaths.index_html()
    m = re.search(r'<div id="build-gear"[^>]*>(.*?)</div>', html, re.S)
    assert m and "<details" not in m.group(1)


GEAR_CHECK = r"""
const fs = require("fs");
const P = require(process.argv[3]);
const gearFull = new Function(fs.readFileSync(process.argv[2], "ascii") + "\nreturn gearFull;")();
// a realistic PoB item: header, bookkeeping lines, tagged mods
const g = { slot: "Helmet", name: "Doom Crown", base: "Iron Hat", rarity: "Rare",
  text: "Rarity: RARE\nDoom Crown\nIron Hat\nUnique ID: 0123456789abcdef0123456789abcdef\n" +
    "Item Level: 82\nQuality: 20\nLevelReq: 60\nImplicits: 0\n{tags:life}+80 to maximum Life\n" +
    "{crafted}+30% to Fire Resistance\n+25% to Cold Resistance\n--------\n+12 to Strength" };
const line = "Helmet: Doom Crown, Iron Hat (Rare)";
const out = {
  full: gearFull(g, line),
  none: gearFull({ slot: "Ring 1", name: "Plain Ring", base: "", text: "" }, "Ring 1: Plain Ring"),
  header: gearFull({ slot: "Belt", name: "Rope", base: "", text: "Rarity: NORMAL\nRope\n" }, "Belt: Rope"),
};
out.page = P.wrap(out.full, P.TEXT.full.cols, P.TEXT.full.lines);
out.compact = P.wrap(out.full, P.TEXT.compact.cols, P.TEXT.compact.lines);
console.log(JSON.stringify(out));
"""


def _node():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not found")
    return node


def test_gear_full_text_starts_with_the_mods(tmp_path):
    node = _node()
    src = tmp_path / "gearfull.js"
    src.write_text(_gear_full_src(), encoding="ascii")
    script = tmp_path / "gear.js"
    script.write_text(GEAR_CHECK, encoding="ascii")
    res = subprocess.run([node, str(script), str(src), str(srcpaths.path("pager.js"))],
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout.strip().splitlines()[-1])
    assert out["full"] == ("Helmet: Doom Crown - Quality: 20; +80 to maximum Life; "
                           "+30% to Fire Resistance; +25% to Cold Resistance; +12 to Strength")
    # the first mod is on the Full text page, in both size classes
    assert "+80 to maximum Life" in " ".join(out["page"])
    assert "+80 to maximum" in " ".join(out["compact"])
    # no item text, or only header lines: the row's one line
    assert out["none"] == "Ring 1: Plain Ring"
    assert out["header"] == "Belt: Rope"


NODE_CHECK = r"""
const s = require(process.argv[2]);
function fakeDoc() {
  const doc = {};
  doc.createElement = (tag) => {
    const n = {
      tagName: tag.toUpperCase(), className: "", hidden: false, children: [], attrs: {},
      listeners: {},
      get firstChild() { return this.children[0] || null; },
      get textContent() { return this.children.map((c) => c.textContent).join(""); },
      // a text node child, as in the DOM, so the pager's clear() removes it
      set textContent(v) { this.children = [{ textContent: String(v), children: [] }]; },
      appendChild(c) { this.children.push(c); return c; },
      removeChild(c) { this.children = this.children.filter((x) => x !== c); return c; },
      setAttribute(k, v) { this.attrs[k] = String(v); },
      getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
      removeAttribute(k) { delete this.attrs[k]; },
      addEventListener(t, fn) { (this.listeners[t] = this.listeners[t] || []).push(fn); }
    };
    return n;
  };
  return doc;
}
const raw = "Rarity: RARE\nDoom Crown\nIron Hat\n+50 to maximum Life";
const rows = [
  { text: "Helmet: Doom Crown, Iron Hat (Rare)", full: "Helmet: " + raw },
  { text: "Ring 1: Plain Ring", full: "Ring 1: Plain Ring" }
];
const opts = { text: (r) => r.text, full: (r) => r.full || r.text };
const pg = s.rowPager(fakeDoc(), {
  rows, label: "gear", size: { full: 9, compact: 7 }, sizeClass: "full",
  text: opts.full, parts: (r) => [{ text: opts.text(r) }],
  controls: () => []
});
const out = { list: pg.list.children.map((li) => li.textContent) };
pg.press("toggle");
out.toggle = pg.toggle.textContent;
out.titles = pg.list.children.map((li) => li.getAttribute("title"));
out.lines = pg.list.children.map((li) => li.children.map((c) => c.textContent));
console.log(JSON.stringify(out));
"""


def test_full_text_page_shows_raw_item_text(tmp_path):
    node = _node()
    script = tmp_path / "check.js"
    script.write_text(NODE_CHECK, encoding="ascii")
    res = subprocess.run([node, str(script), str(srcpaths.path("search.js"))],
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout.strip().splitlines()[-1])
    # the list page: the one-line rows
    assert out["list"] == ["Helmet: Doom Crown, Iron Hat (Rare)", "Ring 1: Plain Ring"]
    # one press: the Full text page, raw item text first, a textless row unchanged
    assert out["toggle"] == "List"
    assert out["titles"][0] == "Helmet: Rarity: RARE\nDoom Crown\nIron Hat\n+50 to maximum Life"
    assert " ".join(out["lines"][0]).startswith("Helmet: Rarity: RARE Doom Crown Iron Hat")
    assert out["titles"][1] == "Ring 1: Plain Ring"
