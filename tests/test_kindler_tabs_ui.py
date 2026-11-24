"""KINDLER-UI-TABS (decision 0081 points 7 to 11): the Build sub-tabs.

Static checks read web/index.html (the sub-tab group, the editor card and
the script tag), web/kindler.js (no window.confirm, no timer but the
bounded run re-read, text through textContent only) and
web/panels/kindler.css (linked by the al:panels marker; adjudicator
ruling 2026-11-23). The sub-tabs are a labelled button group with
aria-current, never tab roles (adjudicator ruling 2026-11-23).
Behavioural checks drive web/kindler.js under node with a small fake DOM
and a fake core that keeps the tabs like theorycraft/genstore.py; they
skip without node. The store round trip (the tabs and their order survive
a reload) runs on the real GenStore."""

import json
import re
import shutil
import subprocess

import pytest

import srcpaths
from server.al.theorycraft import genstore

HTML = srcpaths.read("index.html")
JS = srcpaths.read("kindler.js")
CSS = srcpaths.read("panels/kindler.css")


def _code(src):
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def _between(start, end):
    i = HTML.index(start)
    return HTML[i:HTML.index(end, i)]


# --- the markup -------------------------------------------------------------

def test_sub_tabs_are_a_labelled_group_inside_the_build_panel():
    panel = HTML[HTML.index('id="panel-build"'):HTML.index('id="panel-run"')]
    bar = _between('<div id="kindler-bar"', "</div>")
    assert bar in panel
    head = bar.split(">", 1)[0]
    assert 'role="group"' in head and 'aria-label="Builds"' in head
    # no tab roles: the page keeps one tab list (adjudicator ruling 2026-11-23)
    assert 'role="tab' not in bar
    assert bar.count('aria-current="true"') == 1
    assert bar.count('tabindex="0"') == 1
    pasted = re.search(r'<button id="kindler-pasted"[^>]*>Pasted build</button>', bar)
    assert pasted and 'class="subtab"' in pasted.group(0)
    assert re.search(r'<button id="kindler-new"[^>]*>New Kindler tab</button>', bar)
    # the bar comes before the six card cells
    assert panel.index('id="kindler-bar"') < panel.index('<div class="col">')


def test_editor_card_is_built_by_the_script_with_no_live_region():
    """The card is made by web/kindler.js on first show (dashboard element
    cap, tests/test_dash_perf.py), not carried in the page."""
    assert 'id="kindlerbox"' not in HTML
    code = _code(JS)
    for bad in ("aria-live", '"status"', '"alert"', '"details"', "primary"):
        assert bad not in code, bad
    for word, cid in (("Move left", "kindler-left"), ("Move right", "kindler-right"),
                      ("Rename", "kindler-rename"), ("Close tab", "kindler-close"),
                      ("Close", "kindler-yes"), ("Keep", "kindler-keep")):
        assert re.search(r'b24\("%s", "%s"' % (cid, word), code), cid
    assert re.search(r'"button", \{ id: "kindler-generate", type: "submit"', code)
    assert 'id: "kindler-name", type: "text", maxlength: String(MAX_LABEL)' in code
    assert '"aria-labelledby": "kindler-title"' in code
    assert re.search(r'h\(d, "h2", \{ id: "kindler-title", "class": "one-line", tabindex: "-1" \}', code)
    assert '"for": "kindler-class"' in code and '"for": "kindler-league"' in code


def test_script_tag_loads_before_slots_and_the_sheet_comes_from_the_marker():
    tag = '<script src="/web/kindler.js" defer></script>'
    assert HTML.count(tag) == 1
    assert HTML.index('src="/web/iteminfo.js"') < HTML.index(tag) < HTML.index('src="/web/slots.js"')
    assert "/web/kindler.css" not in HTML


# --- the script --------------------------------------------------------------

def test_script_never_confirms_by_dialog_or_writes_html():
    code = _code(JS)
    for bad in ("confirm(", "alert(", "prompt(", "innerHTML", "outerHTML",
                "insertAdjacentHTML", "setInterval", "aria-live", "XMLHttpRequest",
                "EventSource", "clipboard", "window.open", "draggable", "dragstart",
                'role", "tab'):
        assert bad not in code, bad
    # the one timer is the page's later() for the bounded run re-read
    assert code.count("setTimeout(") == 1
    assert '"/api/gen-builds"' in code and '"/api/kindler-generate"' in code


def test_script_registers_itself_after_item_info():
    assert 'var NAME = "kindler";' in JS
    assert "var ORDER = 175;" in JS
    assert "root.ALApp.register(" in JS


def test_toggles_and_classes_match_the_store_and_the_templates():
    toggles = re.findall(r'\["(\w+)", "[^"]+", (TRI|DEFENCE)\]', JS)
    assert tuple(k for k, _ in toggles) == genstore.TOGGLE_KEYS
    assert dict(toggles)["defence"] == "DEFENCE"
    tri = re.search(r"var TRI = \[(.*?)\];", JS).group(1)
    assert tuple(re.findall(r'\["(\w+)", ', tri)) == genstore.TRI
    dfc = re.search(r"var DEFENCE = \[(.*?)\];", JS, re.S).group(1)
    assert tuple(re.findall(r'\["(\w+)", ', dfc)) == genstore.DEFENCE
    assert '"Not sure"' in tri
    classes = set(re.findall(r'"(\w+)"', re.search(r"var CLASSES = \[(.*?)\];", JS, re.S).group(1)))
    doc = json.loads(srcpaths.ROOT.joinpath("server", "al", "data", "archetypes.json")
                     .read_text(encoding="utf-8"))
    for t in doc["templates"]:
        assert t["class"] in classes, t["class"]
    assert "var MAX_LABEL = %d;" % genstore.MAX_LABEL in JS


# --- the sheet ---------------------------------------------------------------

def test_sheet_marks_the_shown_sub_tab_by_edge_and_weight_without_motion():
    css = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    m = re.search(r'button\.subtab\[aria-current="true"\] \{([^}]*)\}', css)
    assert m and "border-bottom-color: var(--fk-accent)" in m.group(1)
    assert "font-weight: 600" in m.group(1)
    assert re.search(r"button\.subtab \{[^}]*min-height: 1\.5rem;", css)
    assert re.search(r'#panel-build\[data-sub="kindler"\] > \.col \{ display: none; \}', css)
    assert "grid-template-rows: auto repeat(2, minmax(0, 1fr))" in css
    assert not re.search(r"(?<![-\w])(animation|transition)\s*:", css)
    assert 'button.subtab[aria-current="true"] { border-bottom-color: Highlight; }' in css


# --- the store keeps the tabs and their order (the reload) --------------------

def test_tabs_and_their_order_survive_a_reload(tmp_path):
    path = tmp_path / genstore.FILE_NAME
    store = genstore.GenStore(path)
    a = store.add()
    b = store.add()
    store.rename(b, "Bow\x07 idea")
    assert store.move(b, -1) is True
    store.show(a)
    again = genstore.GenStore(path).view()
    assert [t["id"] for t in again["tabs"]] == [b, a]
    assert again["tabs"][0]["label"] == "Bow idea"
    assert again["shown"] == a
    assert all(v == "unsure" for v in again["tabs"][1]["toggles"].values())
    assert again["tabs"][1]["follow"] is True


# --- behaviour under node ----------------------------------------------------

def _node():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not found")
    return node


HARNESS = r"""
const path = require("path");
const K = require(path.join(process.argv[process.argv.length - 1], "kindler.js"));

function makeDoc() {
  const doc = { byId: {}, activeElement: null };
  function node(tag) {
    const n = {
      tagName: tag.toUpperCase(), className: "", hidden: false, children: [], attrs: {},
      listeners: {}, parentNode: null, _text: "", value: "", checked: false, type: "", name: "",
      get firstChild() { return this.children[0] || null; },
      get nextSibling() {
        if (!this.parentNode) { return null; }
        const c = this.parentNode.children;
        return c[c.indexOf(this) + 1] || null;
      },
      get textContent() {
        return this.children.length ? this.children.map((c) => c.textContent).join("") : this._text;
      },
      set textContent(v) { this.children = []; this._text = String(v); },
      appendChild(c) { return this.insertBefore(c, null); },
      insertBefore(c, ref) {
        if (c.parentNode) { c.parentNode.removeChild(c); }
        if (doc.activeElement === c) { doc.activeElement = null; doc.blurs = (doc.blurs || 0) + 1; }
        const i = ref ? this.children.indexOf(ref) : -1;
        if (i < 0) { this.children.push(c); } else { this.children.splice(i, 0, c); }
        c.parentNode = this;
        return c;
      },
      removeChild(c) { this.children = this.children.filter((x) => x !== c); c.parentNode = null; return c; },
      setAttribute(k, v) { this.attrs[k] = String(v); if (k === "id") { doc.byId[v] = this; } },
      getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
      removeAttribute(k) { delete this.attrs[k]; },
      addEventListener(t, fn) { (this.listeners[t] = this.listeners[t] || []).push(fn); },
      closest(sel) {
        for (let x = this; x; x = x.parentNode) { if (x.tagName === sel.toUpperCase()) { return x; } }
        return null;
      },
      focus() { doc.activeElement = this; }
    };
    return n;
  }
  doc.createElement = node;
  doc.getElementById = (id) => doc.byId[id] || null;
  function mk(tag, id, parent, text) {
    const n = node(tag);
    n.setAttribute("id", id);
    if (text) { n.textContent = text; }
    (parent || doc.root).appendChild(n);
    return n;
  }
  doc.root = node("main");
  const panel = mk("div", "panel-build");
  const bar = mk("div", "kindler-bar", panel);
  mk("button", "kindler-pasted", bar, "Pasted build");
  mk("button", "kindler-new", bar, "New Kindler tab");
  mk("span", "kindler-full", bar).hidden = true;
  return doc;
}

function fire(n, type, ev) {
  ev = ev || {};
  ev.target = ev.target || n;
  ev.currentTarget = n;
  ev.preventDefault = () => { ev.prevented = true; };
  (n.listeners[type] || []).forEach((fn) => fn(ev));
  return ev;
}

/* a fake core: the genstore view, its changes and the Generate route */
function fakeCore(tabs, opts) {
  opts = opts || {};
  const core = { tabs: tabs.map((t) => Object.assign({ toggles: {}, result: null, label: "", "class": "",
    league: "" }, t)), shown: opts.shown || (tabs[0] ? tabs[0].id : ""), next: tabs.length + 1,
    log: [], runs: opts.runs || [] };
  function viewDoc() {
    const full = core.tabs.length >= 6;
    return { tabs: core.tabs.map((t) => Object.assign({}, t, {
      label: t.label || ("Kindler " + t.id.slice(1)), custom_label: !!t.label,
      toggles: Object.assign({ melee: "unsure", spell: "unsure", minion: "unsure", bow: "unsure",
        crit: "unsure", defence: "unsure" }, t.toggles) })),
      shown: core.shown, max: 6, full: full,
      full_text: full ? "You can keep 6 Kindler tabs. Close one to add another." : "" };
  }
  core.request = (method, p, body) => {
    core.log.push({ method: method, path: p, body: body === undefined ? null : body });
    if (p === "/api/kindler-generate") {
      const r = core.runs.length ? core.runs.shift() : { state: "none", result: null };
      if (r.state === "done" && r.result && r.result.best) {
        const t = core.tabs.find((x) => x.id === body.id);
        if (t) { t.result = { template: r.result.best.template, at: 1, dps: r.result.best.dps || null,
          ehp: r.result.best.ehp || null, partial: false, scored: !!r.result.scored, stale: false, key: "" }; }
      }
      return Promise.resolve({ status: 200, body: r });
    }
    if (method === "GET") { return Promise.resolve({ status: 200, body: viewDoc() }); }
    const i = core.tabs.findIndex((t) => t.id === body.id);
    if (body.op === "add") {
      if (core.tabs.length >= 6) {
        return Promise.resolve({ status: 400, body: { error: "You can keep 6 Kindler tabs. Close one to add another." } });
      }
      const t = { id: "k" + core.next++, toggles: {}, result: null, label: "", "class": "", league: "" };
      core.tabs.push(t);
      core.shown = t.id;
    } else if (body.op === "rename") { core.tabs[i].label = body.label;
    } else if (body.op === "move") {
      const j = i + (body.dir === "left" ? -1 : 1);
      const x = core.tabs[i]; core.tabs[i] = core.tabs[j]; core.tabs[j] = x;
    } else if (body.op === "close") {
      core.tabs.splice(i, 1);
      if (core.shown === body.id) { core.shown = core.tabs.length ? core.tabs[Math.min(i, core.tabs.length - 1)].id : ""; }
    } else if (body.op === "show") { core.shown = body.id;
    } else if (body.op === "set") {
      const t = core.tabs[i];
      if (body.toggles) { t.toggles = Object.assign({}, t.toggles, body.toggles); if (t.result) { t.result.stale = true; } }
      if ("class" in body) { t["class"] = body["class"]; }
      if ("league" in body) { t.league = body.league; }
    }
    return Promise.resolve({ status: 200, body: Object.assign(viewDoc(), { saved: true }) });
  };
  return core;
}

const tick = () => new Promise((r) => setTimeout(r, 0));
async function settle() { for (let i = 0; i < 8; i++) { await tick(); } }

function memStore(v) {
  const m = v ? { "ashlight.buildsub": v } : {};
  return { getItem: (k) => (k in m ? m[k] : null), setItem: (k, x) => { m[k] = x; }, m: m };
}

function barIds(doc) {
  return doc.getElementById("kindler-bar").children.filter((c) => c.tagName === "BUTTON")
    .map((c) => c.getAttribute("id"));
}
function currentIds(doc) {
  return doc.getElementById("kindler-bar").children.filter((c) => c.getAttribute("aria-current") === "true")
    .map((c) => c.getAttribute("id"));
}
function stops(doc) {
  return doc.getElementById("kindler-bar").children.filter((c) => c.getAttribute("tabindex") === "0")
    .map((c) => c.getAttribute("id"));
}
function gens(core) {
  return core.log.filter((l) => l.path === "/api/kindler-generate" && !(l.body && l.body.op === "read")).length;
}

async function main() {
  const out = {};
  out.clean = K.cleanLabel("  My\u0007 bow\tbuild that has a name far too long for it  ");
  out.cleanEmpty = K.cleanLabel(null);
  out.step = [K.step("ArrowRight", ["pasted", "k1", "k2"], "k2"), K.step("ArrowLeft", ["pasted", "k1"], "pasted"),
    K.step("Home", ["pasted", "k1", "k2"], "k2"), K.step("End", ["pasted", "k1", "k2"], "pasted"),
    K.step("a", ["pasted"], "pasted")];
  out.leagues = [K.leagueNames(null), K.leagueNames({ web_data: false, leagues: ["Dawn"] }),
    K.leagueNames({ web_data: true, leagues: ["Dawn", 3, "Standard"] })];
  out.results = [
    K.resultText({ result: null }, null).text,
    K.resultText({ result: null }, { result: { best: null, note: "no_match" } }).text,
    K.resultText({ result: { template: "bow_a", scored: true, dps: 12345.6, ehp: 6789, partial: true, stale: false } },
      { result: { best: { template: "bow_a", label: "Lightning bow" } } }).text,
    K.resultText({ result: { template: "bow_a", scored: false, dps: null, ehp: null, partial: false, stale: true } },
      { result: { best: { template: "bow_a", label: "Lightning bow" }, note: "calc_off" } }),
    K.resultText({ result: { template: "bow_a", scored: false, dps: 5, ehp: 5, partial: false, stale: false } }, null).text
  ];

  // 1. load: Pasted build first, the store's order, New last; Pasted shown
  let doc = makeDoc();
  let core = fakeCore([{ id: "k1" }, { id: "k2", label: "Bow idea" }], { shown: "k2" });
  let store = memStore();
  const s1 = K.attach(doc, { request: core.request, store: store, later: () => {}, leagues: () => null });
  await settle();
  out.load = { bar: barIds(doc), current: currentIds(doc), stops: stops(doc),
    card: doc.getElementById("kindlerbox"),
    sub: doc.getElementById("panel-build").getAttribute("data-sub"),
    labels: barIds(doc).map((id) => doc.getElementById(id).textContent) };

  // 2. keyboard: Right from Pasted shows the first Kindler tab and focuses it
  const pasted = doc.getElementById("kindler-pasted");
  pasted.focus();
  const ev = fire(doc.getElementById("kindler-bar"), "keydown", { key: "ArrowRight", target: pasted });
  await settle();
  out.right = { prevented: !!ev.prevented, current: currentIds(doc), stops: stops(doc),
    focus: doc.activeElement && doc.activeElement.getAttribute("id"),
    cardHidden: doc.getElementById("kindlerbox").hidden,
    sub: doc.getElementById("panel-build").getAttribute("data-sub"),
    title: doc.getElementById("kindler-title").textContent,
    posts: core.log.filter((l) => l.method === "POST").map((l) => l.body), stored: store.m["ashlight.buildsub"],
    checked: ["melee", "spell", "minion", "bow", "crit", "defence"].map((k) =>
      doc.getElementById("kt-" + k + "-unsure").checked),
    leftOff: doc.getElementById("kindler-left").getAttribute("aria-disabled"),
    rightOff: doc.getElementById("kindler-right").getAttribute("aria-disabled") };
  out.toggleInputs = doc.getElementById("kindler-toggles").children.map((fs) =>
    fs.children.filter((c) => c.tagName === "LABEL").map((l) => l.children[0].value));
  out.classOptions = doc.getElementById("kindler-class").children.map((o) => o.value);
  const card = doc.getElementById("kindlerbox");
  out.cardPlace = { last: doc.getElementById("panel-build").children.slice(-1)[0] === card,
    labelled: card.getAttribute("aria-labelledby"), cls: card.className };
  const ev2 = fire(doc.getElementById("kindler-bar"), "keydown", { key: "End", target: doc.activeElement });
  await settle();
  out.end = { current: currentIds(doc), focus: doc.activeElement && doc.activeElement.getAttribute("id"),
    blurs: doc.blurs || 0 };
  fire(doc.getElementById("kindler-bar"), "keydown", { key: "Home", target: doc.activeElement });
  await settle();
  out.home = { current: currentIds(doc), cardHidden: doc.getElementById("kindlerbox").hidden,
    stored: store.m["ashlight.buildsub"], posts: core.log.filter((l) => l.method === "POST").length };

  // 3. the Kindler editor: move, rename, close with Close / Keep
  K.show("k1", "click");
  await settle();
  core.log.length = 0;
  await K.move("left"); // first tab: refused here, nothing posted
  out.moveFirst = core.log.length;
  await K.move("right");
  out.moved = { bar: barIds(doc), post: core.log[core.log.length - 1].body };
  K.openRename();
  out.renameOpen = { focus: doc.activeElement.getAttribute("id"),
    tools: doc.getElementById("kindler-tools").hidden, form: doc.getElementById("kindler-rename-form").hidden };
  doc.getElementById("kindler-name").value = "  Fire\u0001 witch with a very long name past the cap ";
  await K.saveRename();
  out.renamed = { post: core.log[core.log.length - 1].body, focus: doc.activeElement.getAttribute("id"),
    label: doc.getElementById("kindler-tab-k1").textContent, title: doc.getElementById("kindler-title").textContent };
  core.log.length = 0;
  K.openConfirm();
  out.confirm = { q: doc.getElementById("kindler-confirm-q").textContent,
    focus: doc.activeElement.getAttribute("id"), shown: !doc.getElementById("kindler-confirm").hidden,
    tools: doc.getElementById("kindler-tools").hidden };
  fire(doc.getElementById("kindler-confirm"), "keydown", { key: "Escape" });
  out.kept = { focus: doc.activeElement.getAttribute("id"), shown: !doc.getElementById("kindler-confirm").hidden,
    posts: core.log.length };
  K.openConfirm();
  fire(doc.getElementById("kindler-yes"), "click");
  await settle();
  out.closed = { post: core.log[core.log.length - 1].body, bar: barIds(doc), current: currentIds(doc),
    focus: doc.activeElement && doc.activeElement.getAttribute("id") };

  // 4. toggles and the class mark nothing generated; Generate is one click
  core.log.length = 0;
  const radio = doc.getElementById("kt-melee-yes");
  radio.checked = true;
  fire(doc.getElementById("kindler-toggles"), "change", { target: radio });
  doc.getElementById("kindler-class").value = "Ranger";
  fire(doc.getElementById("kindler-class"), "change");
  await settle();
  out.sets = core.log.filter((l) => l.method === "POST").map((l) => l.body);
  out.gensBefore = gens(core);

  // 5. Generate: started, re-read on the page's timer, then done
  const timers = [];
  const said = [];
  doc = makeDoc();
  core = fakeCore([{ id: "k1" }], { shown: "k1", runs: [
    { state: "started", result: null },
    { state: "running", result: null },
    { state: "done", result: { scored: true, best: { template: "bow_a", label: "Lightning bow", dps: 1000, ehp: 2000 } } }
  ] });
  K.attach(doc, { request: core.request, store: memStore("kindler"), later: (fn, ms) => { timers.push(ms); fn(); },
    leagues: () => ({ web_data: true, leagues: ["Dawn", "Standard"] }), say: (t) => said.push(t) });
  await settle();
  out.restored = { sub: doc.getElementById("panel-build").getAttribute("data-sub"), current: currentIds(doc),
    gens: gens(core) };
  K.paintLeagues();
  out.leagueList = doc.getElementById("kindler-leagues").children.map((o) => o.value);
  const st = await K.generate();
  await settle();
  out.generate = { state: st, timers: timers, gens: gens(core),
    reads: core.log.filter((l) => l.body && l.body.op === "read").length,
    result: doc.getElementById("kindler-result").textContent,
    status: doc.getElementById("kindler-status").textContent, said: said.slice(),
    tabTitle: doc.getElementById("kindler-tab-k1").getAttribute("title"),
    headTitle: doc.getElementById("kindler-title").getAttribute("title") };
  // a busy engine is said on the polite line; a result over Play is not
  said.length = 0;
  core.runs.push({ state: "running", result: null });
  await K.generate();
  doc.getElementById("panel-build").hidden = true;
  core.runs.push({ state: "done", result: { scored: true, best: { template: "bow_a", label: "L", dps: 1, ehp: 2 } } });
  await K.generate();
  await settle();
  out.saidLater = said.slice();

  // 6. six tabs: New refuses with the note and posts nothing
  doc = makeDoc();
  core = fakeCore(["k1", "k2", "k3", "k4", "k5", "k6"].map((id) => ({ id: id })));
  K.attach(doc, { request: core.request, store: memStore(), later: () => {}, leagues: () => null });
  await settle();
  core.log.length = 0;
  fire(doc.getElementById("kindler-bar"), "click", { target: doc.getElementById("kindler-new") });
  await settle();
  out.full = { disabled: doc.getElementById("kindler-new").getAttribute("aria-disabled"),
    note: doc.getElementById("kindler-full").textContent, hidden: doc.getElementById("kindler-full").hidden,
    posts: core.log.length };

  // 7. New on an empty list: one add, the editor shows with focus on its title
  doc = makeDoc();
  core = fakeCore([]);
  K.attach(doc, { request: core.request, store: memStore(), later: () => {}, leagues: () => null });
  await settle();
  await K.addTab();
  out.added = { bar: barIds(doc), current: currentIds(doc), focus: doc.activeElement.getAttribute("id"),
    sub: doc.getElementById("panel-build").getAttribute("data-sub"), gens: gens(core) };
  // closing the last tab goes back to the Pasted build
  K.openConfirm();
  await K.closeTab();
  out.lastClosed = { bar: barIds(doc), current: currentIds(doc), focus: doc.activeElement.getAttribute("id"),
    cardHidden: doc.getElementById("kindlerbox").hidden };
  process.stdout.write(JSON.stringify(out));
}
main().catch((e) => { process.stderr.write(String(e && e.stack || e)); process.exit(1); });
"""


@pytest.fixture(scope="module")
def run():
    res = subprocess.run([_node(), "-e", HARNESS, str(srcpaths.WEB)], capture_output=True,
                         text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


def test_pure_helpers(run):
    assert len(run["clean"]) <= 32 and "\u0007" not in run["clean"] and "\t" not in run["clean"]
    assert run["clean"].startswith("My bowbuild")
    assert run["cleanEmpty"] == ""
    assert run["step"] == ["pasted", "k1", "pasted", "k2", None]
    assert run["leagues"] == [["Standard"], ["Standard"], ["Dawn", "Standard"]]
    none, nomatch, scored, unscored, plain = run["results"]
    assert none == "No result yet. Pick what you want, then press Generate."
    assert nomatch.startswith("No build fits these choices.")
    assert scored.startswith("Lightning bow: 12,346 DPS, 6,789 EHP. Scored by Path of Building.")
    assert "Time ran out" in scored
    assert unscored == {"text": "Lightning bow: not scored (calc off). Turn the calc on in "
                        "Settings, Checks.", "stale": True}
    # decision 0081 point 5: no number without Path of Building's score
    assert plain == "bow_a: not scored."


def test_load_puts_pasted_build_first_in_the_store_order(run):
    load = run["load"]
    assert load["bar"] == ["kindler-pasted", "kindler-tab-k1", "kindler-tab-k2", "kindler-new"]
    assert load["labels"] == ["Pasted build", "Kindler 1", "Bow idea", "New Kindler tab"]
    assert load["current"] == ["kindler-pasted"] and load["stops"] == ["kindler-pasted"]
    assert load["card"] is None and load["sub"] is None  # built on first show
    assert run["toggleInputs"] == [["yes", "no", "unsure"]] * 5 + [["life", "energy_shield", "hybrid", "unsure"]]
    assert run["classOptions"][0] == "" and "Ranger" in run["classOptions"]
    assert run["cardPlace"] == {"last": True, "labelled": "kindler-title",
                                "cls": "card kindler-card"}


def test_arrow_keys_move_and_show_with_one_tab_stop(run):
    r = run["right"]
    assert r["prevented"] is True
    assert r["current"] == ["kindler-tab-k1"] and r["stops"] == ["kindler-tab-k1"]
    assert r["focus"] == "kindler-tab-k1"
    assert r["cardHidden"] is False and r["sub"] == "kindler"
    assert r["title"] == "Kindler 1"
    assert r["posts"] == [{"op": "show", "id": "k1"}]
    assert r["stored"] == "kindler"
    # every toggle starts at Not sure
    assert r["checked"] == [True] * 6
    assert r["leftOff"] == "true" and r["rightOff"] is None
    assert run["end"]["current"] == ["kindler-tab-k2"] and run["end"]["focus"] == "kindler-tab-k2"
    assert run["end"]["blurs"] == 0  # a repaint never moves the focused sub-tab
    home = run["home"]
    assert home["current"] == ["kindler-pasted"] and home["cardHidden"] is True
    assert home["stored"] == "pasted"
    assert home["posts"] == 2  # showing the Pasted build posts nothing


def test_move_rename_and_close_with_an_inline_confirm(run):
    assert run["moveFirst"] == 0
    assert run["moved"]["post"] == {"op": "move", "id": "k1", "dir": "right"}
    assert run["moved"]["bar"] == ["kindler-pasted", "kindler-tab-k2", "kindler-tab-k1", "kindler-new"]
    ro = run["renameOpen"]
    assert ro == {"focus": "kindler-name", "tools": True, "form": False}
    rn = run["renamed"]
    assert rn["post"]["op"] == "rename" and rn["post"]["id"] == "k1"
    assert len(rn["post"]["label"]) <= 32 and "\u0001" not in rn["post"]["label"]
    assert rn["post"]["label"].startswith("Fire witch with")
    assert rn["focus"] == "kindler-rename"
    assert rn["label"] == rn["post"]["label"] == rn["title"]
    c = run["confirm"]
    assert c["q"] == "Close %s?" % rn["post"]["label"]
    assert c["focus"] == "kindler-keep" and c["shown"] and c["tools"]
    assert run["kept"] == {"focus": "kindler-close", "shown": False, "posts": 0}
    cl = run["closed"]
    assert cl["post"] == {"op": "close", "id": "k1"}
    assert cl["bar"] == ["kindler-pasted", "kindler-tab-k2", "kindler-new"]
    assert cl["current"] == ["kindler-tab-k2"] and cl["focus"] == "kindler-tab-k2"


def test_changes_save_and_nothing_generates_by_itself(run):
    assert run["sets"] == [{"op": "set", "id": "k2", "toggles": {"melee": "yes"}},
                           {"op": "set", "id": "k2", "class": "Ranger"}]
    assert run["gensBefore"] == 0
    assert run["restored"]["gens"] == 0


def test_tabs_come_back_and_generate_is_one_click(run):
    r = run["restored"]
    assert r["sub"] == "kindler" and r["current"] == ["kindler-tab-k1"]
    assert run["leagueList"] == ["Dawn", "Standard"]
    g = run["generate"]
    assert g["state"] == "started" and g["gens"] == 1
    assert g["timers"] == [3000, 3000] and g["reads"] == 2
    assert g["result"] == "Lightning bow: 1,000 DPS, 2,000 EHP. Scored by Path of Building."
    assert g["status"] == ""
    assert g["said"] == ["Kindler 1: result ready."]
    assert g["tabTitle"] == "Kindler 1" and g["headTitle"] == "Kindler 1"
    assert run["saidLater"] == ["Another Kindler tab is generating. Press Generate again when it "
                                "is done."]


def test_a_seventh_tab_is_refused_with_a_note(run):
    f = run["full"]
    assert f["disabled"] == "true" and f["hidden"] is False
    assert f["note"] == genstore.FULL_TEXT
    assert f["posts"] == 0


def test_new_tab_shows_its_editor_and_the_last_close_returns_to_pasted(run):
    a = run["added"]
    assert a["bar"] == ["kindler-pasted", "kindler-tab-k1", "kindler-new"]
    assert a["current"] == ["kindler-tab-k1"] and a["focus"] == "kindler-title"
    assert a["sub"] == "kindler" and a["gens"] == 0
    lc = run["lastClosed"]
    assert lc["bar"] == ["kindler-pasted", "kindler-new"]
    assert lc["current"] == ["kindler-pasted"] and lc["focus"] == "kindler-pasted"
    assert lc["cardHidden"] is True
