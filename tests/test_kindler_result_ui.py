"""KINDLER-UI-RESULT (decision 0081 points 10 and 14 to 17): the Kindler
plan card.

Static checks read web/kindler.js (the card is made by the script, text
through textContent only, no new timer, no live region, the plan op and
never a Generate) and web/panels/kindler.css (the cockpit columns, no
motion). Behavioural checks drive web/kindler.js under node with a small
fake DOM and a fake core whose plan answers are real ones: the plan of
the first authored template from theorycraft.kindlerplan.build_plan and
the stage its current_stage resolver picks. They skip without node."""

import json
import re
import shutil
import subprocess

import pytest

import srcpaths
from server.al.theorycraft import archetypes, kindlerplan

JS = srcpaths.read("kindler.js")
CSS = srcpaths.read("panels/kindler.css")
HTML = srcpaths.read("index.html")


def _code(src):
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


# --- static ------------------------------------------------------------------

def test_plan_card_is_built_by_the_script_not_carried_in_the_page():
    assert 'id="kindler-plan"' not in HTML
    code = _code(JS)
    assert 'h(d, "section", { id: "kindler-plan", "class": "card kindler-card kindler-plan"' in code
    assert '"aria-labelledby": "kindler-plan-title"' in code
    assert re.search(r'h\(d, "h2", \{ id: "kindler-plan-title"', code)
    assert '"aria-pressed": "true"' in code and '"class": "chip"' in code
    assert 'role: "group", "aria-label": "Plan parts"' in code
    assert 'op: "plan"' in code


def test_script_adds_no_timer_live_region_or_markup_string():
    code = _code(JS)
    for bad in ("innerHTML", "outerHTML", "insertAdjacentHTML", "setInterval", "aria-live",
                '"status"', '"alert"', "clipboard", "window.open", "localStorage.setItem"):
        assert bad not in code, bad
    # the page's one timer stays the bounded re-read (the plan uses later())
    assert code.count("setTimeout(") == 1
    assert "s.ctl.later(" in code


def test_no_score_number_reaches_the_plan_card():
    """Decision 0081 point 5 and 18: the plan shows Path of Building's
    order, never a weight; planView drops the weights."""
    code = _code(JS)
    start = code.index("function planView(")
    body = code[start:code.index("function triggerText(", start)]
    assert "weight" not in body
    assert "dps" not in code[code.index("function paintPlan("):].split("function syncPlan(")[0]


def test_sheet_places_the_plan_beside_the_editor_without_motion():
    css = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    assert "#panel-build:has(> #kindler-plan:not([hidden])) > #kindlerbox { grid-column: 1; }" in css
    assert "#panel-build > #kindler-plan { grid-column: 2 / -1; }" in css
    assert not re.search(r"(?<![-\w])(animation|transition)\s*:", css)
    assert '[data-text-spacing="user"] #panel-build > #kindler-plan { grid-column: 1 / -1; }' in css


# --- behaviour under node ----------------------------------------------------

def _node():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not found")
    return node


def _fixtures():
    view = archetypes.resolve(archetypes.load())
    template = view["templates"][0]
    plan = kindlerplan.build_plan(template, note=kindlerplan.FOCUS_CALC_OFF)
    # one support Path of Building says does not apply (the bridge's word)
    plan["stages"][1]["skills"][0]["supports"][0]["applies"] = False
    here1 = {"area_id": "G1_1", "area_level": 1, "level": 2}
    here2 = {"area_id": "G2_1", "area_level": 20, "level": 18}
    return {"plan": plan,
            "here1": here1, "cur1": kindlerplan.current_stage(plan, here1),
            "here2": here2, "cur2": kindlerplan.current_stage(plan, here2)}


HARNESS = r"""
const path = require("path");
const fs = require("fs");
const web = process.argv[process.argv.length - 2];
const FX = JSON.parse(fs.readFileSync(process.argv[process.argv.length - 1], "utf8"));
const K = require(path.join(web, "kindler.js"));

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

function walk(n, out) {
  out.push(n);
  n.children.forEach((c) => walk(c, out));
  return out;
}

/* a fake core: tabs like genstore's view, plan answers from the fixtures */
function fakeCore(tabs) {
  const core = { tabs: tabs, shown: tabs[0].id, log: [], focus: "calc_off" };
  function viewDoc() {
    return { tabs: core.tabs.map((t) => Object.assign({ label: "", custom_label: false, "class": "",
      league: "", toggles: {}, follow: true, result: null }, t)), shown: core.shown, max: 6, full: false,
      full_text: "" };
  }
  core.request = (method, p, body) => {
    core.log.push({ method: method, path: p, body: body === undefined ? null : body });
    if (p === "/api/kindler-generate") {
      if (body.op !== "plan") { return Promise.resolve({ status: 200, body: { state: "none", result: null } }); }
      const t = core.tabs.find((x) => x.id === body.id);
      const here = core.here || FX.here1;
      const cur = t.follow === false ? null : (here === FX.here2 ? FX.cur2 : FX.cur1);
      return Promise.resolve({ status: 200, body: { state: "done", plan: FX.plan, focus: core.focus,
        current: cur } });
    }
    if (method === "POST" && body.op === "set") {
      const t = core.tabs.find((x) => x.id === body.id);
      if ("follow" in body) { t.follow = body.follow; }
    }
    if (method === "POST" && body.op === "show") { core.shown = body.id; }
    return Promise.resolve({ status: 200, body: Object.assign(viewDoc(), { saved: true }) });
  };
  return core;
}

const tick = () => new Promise((r) => setTimeout(r, 0));
async function settle() { for (let i = 0; i < 8; i++) { await tick(); } }
function memStore(v) {
  const m = v ? { "ashlight.buildsub": v } : {};
  return { getItem: (k) => (k in m ? m[k] : null), setItem: (k, x) => { m[k] = x; } };
}
const plans = (core) => core.log.filter((l) => l.body && l.body.op === "plan").length;
const gens = (core) => core.log.filter((l) => l.path === "/api/kindler-generate" &&
  !(l.body && (l.body.op === "read" || l.body.op === "plan"))).length;
const $ = (doc, id) => doc.getElementById(id);
function bodyView(doc) {
  const body = $(doc, "kindler-plan-body");
  const all = walk(body, []);
  return { text: body.textContent,
    heads: all.filter((n) => n.tagName === "H4").map((n) => n.textContent),
    items: all.filter((n) => n.className.indexOf("iteminfo-name") >= 0).map((n) => ({
      item: n.getAttribute("data-item"), controls: n.getAttribute("aria-controls"),
      type: n.type, expanded: n.getAttribute("aria-expanded") })),
    lists: all.filter((n) => n.tagName === "OL" || n.tagName === "UL").map((n) => n.children.length) };
}
function stageView(doc) {
  return { name: $(doc, "kindler-stage-name").textContent, why: $(doc, "kindler-stage-why").textContent,
    now: !$(doc, "kindler-here").hidden, prevOff: $(doc, "kindler-stage-prev").getAttribute("aria-disabled"),
    nextOff: $(doc, "kindler-stage-next").getAttribute("aria-disabled") };
}

async function main() {
  const out = {};
  const pv = K.planView({ plan: FX.plan, focus: "calc_off", current: FX.cur1 });
  out.pure = {
    stages: pv.stages.length, label: pv.label, asc: pv.ascendancy, focus: pv.focus, current: pv.current,
    weights: JSON.stringify(pv).indexOf("weight"),
    bad: K.planView({ plan: { stages: [{ label: 3, skills: "x", gems: [{ name: "A", action: "eat" }],
      focus: [{ slot: "Helmet", stats: [] }] }] }, focus: "nonsense", current: { stage: 7 } }),
    none: K.planView(null),
    triggers: [K.triggerText({ kind: "level", min: 1, max: 12 }), K.triggerText({ kind: "act", act: 2 }),
      K.triggerText({ kind: "area_level", min: 65, max: 70 }), K.triggerText({ kind: "zone", zone: "G1_1" }),
      K.triggerText(null)],
    gems: [K.gemStep({ name: "Spark", action: "pick", level: 3, checked: true, forName: "" }),
      K.gemStep({ name: "Arc", action: "swap", level: 8, checked: false, forName: "Spark" }),
      K.gemStep({ name: "Arc", action: "drop", level: null, checked: false, forName: "" }),
      K.gemStep({ name: "Arc", action: "pick", level: null, checked: false, forName: "" })],
    ordinals: [K.ordinal(1), K.ordinal(2), K.ordinal(0), K.ordinal(9), K.ordinal("2")],
    here: [K.hereOf(null), K.hereOf({ area_id: "G1_1", area_level: 2, level: 3.5, zone: "x" })]
  };

  // 1. a tab with a result: the plan card is made; nothing read before a snapshot
  const timers = [];
  let doc = makeDoc();
  let core = fakeCore([{ id: "k1", label: "Bow idea", custom_label: true,
    result: { template: FX.plan.template, at: 5, dps: null, ehp: null, partial: false, scored: false,
      stale: false, key: "abc" } }, { id: "k2" }]);
  K.attach(doc, { request: core.request, store: memStore("kindler"), later: (fn, ms) => { timers.push([fn, ms]); },
    leagues: () => null });
  await settle();
  const panel = $(doc, "panel-build");
  out.before = { plans: plans(core), card: !!$(doc, "kindler-plan"), hidden: $(doc, "kindler-plan").hidden,
    empty: $(doc, "kindler-plan-empty").textContent, main: $(doc, "kindler-plan-main").hidden,
    order: panel.children.map((c) => c.getAttribute("id")),
    follow: $(doc, "kindler-follow").getAttribute("aria-pressed"),
    followWhy: $(doc, "kindler-follow-why").textContent };

  // 2. the snapshot paint reads the plan once; the matched stage shows with Now
  K.follow({ area_id: "G1_1", area_level: 1, level: 2, zone: "Riverbank" });
  await settle();
  out.first = { plans: plans(core), post: core.log.filter((l) => l.body && l.body.op === "plan")[0].body,
    name: $(doc, "kindler-plan-name").textContent, stage: stageView(doc), body: bodyView(doc),
    empty: $(doc, "kindler-plan-empty").hidden, main: $(doc, "kindler-plan-main").hidden,
    pages: ["skills", "passives", "items"].map((p) => [$(doc, "kindler-page-" + p).getAttribute("aria-current"),
      $(doc, "kindler-page-" + p).getAttribute("tabindex")]),
    credit: $(doc, "kindler-plan-credit").hidden };
  K.follow({ area_id: "G1_1", area_level: 1, level: 2, zone: "Riverbank", xp: 9 });
  await settle();
  out.same = plans(core);

  // 3. Next / Previous: the player's pick; focus stays on the pressed button
  const next = $(doc, "kindler-stage-next");
  next.focus();
  fire(next, "click");
  out.next = { stage: stageView(doc), body: bodyView(doc), focus: doc.activeElement === next,
    credit: $(doc, "kindler-plan-credit").textContent, title: $(doc, "kindler-stage-name").getAttribute("title") };
  fire($(doc, "kindler-stage-prev"), "click");
  fire($(doc, "kindler-stage-prev"), "click");
  out.prev = stageView(doc);

  // 4. the guidance moves: the plan is read again and the stage follows by itself
  core.here = FX.here2;
  K.follow(Object.assign({ zone: "Vastiri Outskirts" }, FX.here2));
  await settle();
  out.moved = { plans: plans(core), stage: stageView(doc), body: bodyView(doc) };

  // 5. pages: Item focus by click, Passives by arrow key (focus moves)
  fire($(doc, "kindler-plan-pages"), "click", { target: $(doc, "kindler-page-items") });
  out.items = { body: bodyView(doc), credit: $(doc, "kindler-plan-credit").textContent,
    creditHidden: $(doc, "kindler-plan-credit").hidden,
    current: $(doc, "kindler-page-items").getAttribute("aria-current") };
  const kev = fire($(doc, "kindler-plan-pages"), "keydown", { key: "ArrowLeft", target: $(doc, "kindler-page-items") });
  out.passives = { prevented: !!kev.prevented, focus: doc.activeElement && doc.activeElement.getAttribute("id"),
    body: bodyView(doc), creditHidden: $(doc, "kindler-plan-credit").hidden };
  K.stage(1);
  out.asc = bodyView(doc);
  K.planPage("skills");

  // 6. the follow toggle: one store change, the plan read again, no Now badge
  await K.setFollow();
  await settle();
  out.off = { post: core.log.filter((l) => l.body && l.body.op === "set").slice(-1)[0].body,
    pressed: $(doc, "kindler-follow").getAttribute("aria-pressed"),
    why: $(doc, "kindler-follow-why").textContent, plans: plans(core), stage: stageView(doc) };
  K.follow({ area_id: "G1_1", area_level: 1, level: 2 });
  await settle();
  out.offMove = { plans: plans(core), stage: stageView(doc) };

  // 7. the Pasted build hides the plan card; nothing generated anywhere
  K.show("pasted", "click");
  out.pasted = { hidden: $(doc, "kindler-plan").hidden, gens: gens(core) };

  // 8. a tab with no result: no plan card at all; no read
  doc = makeDoc();
  core = fakeCore([{ id: "k1" }]);
  K.attach(doc, { request: core.request, store: memStore("kindler"), later: () => {}, leagues: () => null });
  await settle();
  K.follow(FX.here1);
  await settle();
  out.noResult = { card: $(doc, "kindler-plan"), plans: plans(core), editor: !!$(doc, "kindlerbox") };

  // 9. pending focus: re-read on the page's timer until Path of Building answers
  doc = makeDoc();
  core = fakeCore([{ id: "k1", result: { template: FX.plan.template, at: 1, scored: true, dps: 5, ehp: 6,
    partial: false, stale: false, key: "p" } }]);
  core.focus = "pending";
  const later = [];
  K.attach(doc, { request: core.request, store: memStore("kindler"), later: (fn, ms) => { later.push(ms); setTimeout(fn, 0); },
    leagues: () => null });
  await settle();
  K.follow(FX.here1);
  await settle();
  K.planPage("items");
  out.pending = { credit: $(doc, "kindler-plan-credit").textContent };
  core.focus = "pob";
  await settle();
  await settle();
  out.pob = { later: later.slice(), plans: plans(core), credit: $(doc, "kindler-plan-credit").textContent,
    text: $(doc, "kindler-plan").textContent };
  // bounded: a focus that never leaves pending stops after PLAN_MAX re-reads
  doc = makeDoc();
  core = fakeCore([{ id: "k1", result: { template: FX.plan.template, at: 1, scored: true, partial: false,
    stale: false, key: "q" } }]);
  core.focus = "pending";
  let n = 0;
  K.attach(doc, { request: core.request, store: memStore("kindler"), later: (fn) => { n += 1; setTimeout(fn, 0); },
    leagues: () => null });
  await settle();
  K.follow(FX.here1);
  for (let i = 0; i < 40; i++) { await settle(); }
  out.bounded = { later: n, plans: plans(core) };

  // 10. a refused plan read says so, never "Reading" for ever
  doc = makeDoc();
  core = fakeCore([{ id: "k1", result: { template: "x", at: 1, scored: false, partial: false, stale: false, key: "r" } }]);
  const inner = core.request;
  core.request = (m, p, b) => (b && b.op === "plan" ? Promise.resolve({ status: 500, body: null }) : inner(m, p, b));
  K.attach(doc, { request: core.request, store: memStore("kindler"), later: () => {}, leagues: () => null });
  await settle();
  K.follow(FX.here1);
  await settle();
  out.failed = { empty: $(doc, "kindler-plan-empty").textContent, main: $(doc, "kindler-plan-main").hidden };

  // 11. a long stage is cut into card parts of at most PART_ROWS rows
  const big = { template: "big", label: "Big", stages: [{ id: "s", label: "Long", trigger: { kind: "act", act: 1 },
    level: 10, skills: [0, 1, 2, 3, 4, 5].map((i) => ({ name: "Skill " + i, level: 1, checked: true, sockets: 4,
      supports: [0, 1, 2, 3].map((j) => ({ name: "Sup " + i + j, level: 1, checked: true, applies: null })) })),
    gems: [0, 1, 2, 3, 4, 5].map((i) => ({ name: "Gem " + i, action: "pick", level: 2, checked: true })),
    passives: [], points: 0, budget: 0, ascendancy: null, focus: [] }] };
  doc = makeDoc();
  core = fakeCore([{ id: "k1", result: { template: "big", at: 1, scored: false, partial: false, stale: false, key: "b" } }]);
  const inner2 = core.request;
  core.request = (m, p, b) => (b && b.op === "plan" ? Promise.resolve({ status: 200, body: { state: "done",
    plan: big, focus: "calc_off", current: null } }) : inner2(m, p, b));
  K.attach(doc, { request: core.request, store: memStore("kindler"), later: () => {}, leagues: () => null });
  await settle();
  K.follow(FX.here1);
  await settle();
  const seen = [];
  const pn = $(doc, "kindler-part-next");
  pn.focus();
  for (let i = 0; i < 5; i++) {
    seen.push({ label: $(doc, "kindler-part-label").textContent, text: $(doc, "kindler-plan-body").textContent,
      lis: walk($(doc, "kindler-plan-body"), []).filter((x) => x.tagName === "LI").length,
      nextOff: pn.getAttribute("aria-disabled"), navHidden: $(doc, "kindler-parts").hidden });
    fire(pn, "click");
  }
  out.parts = { seen: seen, focus: doc.activeElement === pn, cut: K.parts([{ head: "A", rows: 1 },
    { para: "x", rows: 9 }, { head: "B", rows: 1 }, { li: 1, rows: 1 }]).map((p) => p.length) };
  process.stdout.write(JSON.stringify(out));
}
main().catch((e) => { process.stderr.write(String(e && e.stack || e)); process.exit(1); });
"""


@pytest.fixture(scope="module")
def fx():
    return _fixtures()


@pytest.fixture(scope="module")
def run(fx, tmp_path_factory):
    path = tmp_path_factory.mktemp("kplan") / "fx.json"
    path.write_text(json.dumps(fx), encoding="ascii")
    res = subprocess.run([_node(), "-e", HARNESS, str(srcpaths.WEB), str(path)],
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


def test_fixture_plan_has_the_stages_the_card_walks(fx):
    assert fx["cur1"]["stage"] == 0 and fx["cur1"]["by"] == "zone"
    assert fx["cur2"]["by"] == "act" and fx["cur2"]["stage"] > 1
    assert any(st["ascendancy"] for st in fx["plan"]["stages"])


def test_plan_view_checks_every_field_and_drops_weights(run, fx):
    p = run["pure"]
    assert p["stages"] == len(fx["plan"]["stages"])
    assert p["label"] == fx["plan"]["label"] and p["asc"] == fx["plan"]["ascendancy"]
    assert p["focus"] == "calc_off" and p["current"] == {"stage": 0, "by": "zone"}
    assert p["weights"] == -1
    bad = p["bad"]
    assert bad["focus"] == "" and bad["current"] is None
    st = bad["stages"][0]
    assert st["label"] == "Stage" and st["skills"] == [] and st["gems"] == [] and st["focus"] == []
    assert p["none"]["plan"] is False and p["none"]["stages"] == []
    assert p["triggers"] == ["For character level 1 to 12", "For Act 2", "For area level 65 to 70", "", ""]
    pick, swap, drop, bare = p["gems"]
    assert pick == [{"text": "Pick up "}, {"item": "Spark"}, {"text": ", usable from level 3"}]
    assert swap == [{"text": "Swap "}, {"item": "Spark"}, {"text": " for "}, {"item": "Arc"},
                    {"text": ", planned for level 8"}]
    assert drop == [{"text": "Drop "}, {"item": "Arc"}]
    assert bare == [{"text": "Pick up "}, {"item": "Arc"}, {"text": ""}]
    assert p["ordinals"] == ["first", "second", "", "", ""]
    assert p["here"] == [None, {"area_id": "G1_1", "area_level": 2, "level": None}]


def test_card_comes_after_the_editor_and_reads_nothing_before_a_snapshot(run):
    b = run["before"]
    assert b["plans"] == 0 and b["card"] is True and b["hidden"] is False
    assert b["order"] == ["kindler-bar", "kindlerbox", "kindler-plan"]
    assert b["empty"] == "Reading the plan." and b["main"] is True
    assert b["follow"] == "true"
    assert b["followWhy"] == "Shows the stage that matches where you are."


def test_snapshot_reads_the_plan_once_and_shows_the_matched_stage(run, fx):
    f = run["first"]
    assert f["plans"] == 1 and f["post"] == {"id": "k1", "op": "plan"}
    assert f["name"] == fx["plan"]["label"] + ", " + fx["plan"]["ascendancy"]
    first = fx["plan"]["stages"][0]
    n = len(fx["plan"]["stages"])
    assert f["stage"]["name"] == "Stage 1 of %d: %s" % (n, first["label"])
    assert f["stage"]["now"] is True
    assert f["stage"]["why"] == "This stage matches your zone."
    assert f["stage"]["prevOff"] == "true" and f["stage"]["nextOff"] is None
    assert f["empty"] is True and f["main"] is False
    assert f["pages"] == [["true", "0"], [None, "-1"], [None, "-1"]]
    assert f["credit"] is True
    body = f["body"]
    assert body["heads"] == ["Skills", "Gem changes"]
    gem = first["skills"][0]["name"]
    assert {"item": gem, "controls": "iteminfo-pop", "type": "button", "expanded": "false"} in body["items"]
    assert "Pick up " + gem in body["text"]
    # an unchanged guidance reads nothing new
    assert run["same"] == 1


def test_previous_and_next_pick_a_stage_and_keep_focus(run, fx):
    nx = run["next"]
    second = fx["plan"]["stages"][1]
    assert nx["focus"] is True
    assert nx["stage"]["name"].startswith("Stage 2 of ") and nx["stage"]["now"] is False
    assert nx["stage"]["why"] == "For Act 1."
    # a support Path of Building says does not apply is said so, in words
    assert "Links: " + second["skills"][0]["supports"][0]["name"] + \
        " (not used by this skill)" in nx["body"]["text"]
    assert nx["credit"] == "Path of Building says which links a skill uses."
    assert nx["title"] == nx["stage"]["name"]
    pv = run["prev"]
    assert pv["name"].startswith("Stage 1 of ") and pv["prevOff"] == "true" and pv["now"] is True


def test_the_stage_follows_the_guidance_by_itself(run, fx):
    m = run["moved"]
    at = fx["cur2"]["stage"]
    assert m["plans"] == 2
    assert m["stage"]["name"].startswith("Stage %d of " % (at + 1))
    assert m["stage"]["now"] is True
    assert m["stage"]["why"] == "For Act %d. This stage matches your act." % fx["plan"]["stages"][at]["trigger"]["act"]


def test_item_focus_and_passive_pages(run, fx):
    it = run["items"]
    at = fx["cur2"]["stage"]
    focus = fx["plan"]["stages"][at]["focus"]
    assert it["current"] == "true"
    assert [x["item"] for x in it["body"]["items"]] == [s["stat"] for f in focus for s in f["stats"]]
    assert it["body"]["lists"] == [len(focus)]
    assert focus[0]["slot"] + ": " in it["body"]["text"]
    assert it["credit"] == "AshLight's own order (calc off). Turn the calc on in Settings, Checks."
    assert it["creditHidden"] is False
    ps = run["passives"]
    assert ps["prevented"] is True and ps["focus"] == "kindler-page-passives"
    assert ps["creditHidden"] is True
    st = fx["plan"]["stages"][at]
    assert ps["body"]["text"].startswith("%d passives to take, in this order. %d of %d points planned so far."
                                         % (len(st["passives"]), st["points"], st["budget"]))
    assert sum(ps["body"]["lists"]) <= 2 * 10
    nxt = fx["plan"]["stages"][at + 1]
    nth = ["first", "second", "third", "fourth"][nxt["ascendancy"]["trial"] - 1]
    assert "After your %s Ascendancy trial:" % nth in run["asc"]["text"]
    assert run["asc"]["heads"] == ["Ascendancy"]
    # no score digits anywhere: names and plan counts only, never DPS / EHP
    assert "DPS" not in run["asc"]["text"] and "EHP" not in it["body"]["text"]


def test_follow_toggle_is_one_store_change_and_drops_the_now_badge(run):
    off = run["off"]
    assert off["post"] == {"op": "set", "id": "k1", "follow": False}
    assert off["pressed"] == "false"
    assert off["why"] == "Pick a stage with Previous stage and Next stage."
    assert off["plans"] == 3 and off["stage"]["now"] is False
    # with follow off the stage stays the player's while the guidance moves
    om = run["offMove"]
    assert om["stage"]["name"] == off["stage"]["name"] and om["stage"]["now"] is False


def test_pasted_build_hides_the_card_and_nothing_generates(run):
    assert run["pasted"] == {"hidden": True, "gens": 0}


def test_no_result_makes_no_plan_card(run):
    assert run["noResult"] == {"card": None, "plans": 0, "editor": True}


def test_pending_focus_rereads_on_the_page_timer_and_is_bounded(run):
    assert run["pending"]["credit"].startswith("AshLight's own order for now.")
    pob = run["pob"]
    assert pob["later"] and set(pob["later"]) == {3000}
    assert pob["credit"] == "Stats ranked by Path of Building for this build."
    assert pob["plans"] == len(pob["later"]) + 1
    # the scored result's numbers stay on the editor line, never on the plan
    assert "DPS" not in pob["text"]
    b = run["bounded"]
    assert b["later"] == 20 and b["plans"] == 21


def test_a_refused_plan_read_says_so(run):
    assert run["failed"] == {"empty": "Can't read the plan right now. AshLight tries again when "
                                      "something changes.", "main": True}


def test_a_long_stage_pages_in_card_parts(run):
    seen = run["parts"]["seen"]
    labels = [x["label"] for x in seen]
    # 2 headings, 6 skills of 2 rows (4 links), 6 gem steps: 20 rows -> 3 parts
    assert labels[:3] == ["Part 1 of 3", "Part 2 of 3", "Part 3 of 3"]
    assert labels[3] == labels[4] == "Part 3 of 3"  # Next at the end does nothing
    assert seen[0]["navHidden"] is False and seen[2]["nextOff"] == "true"
    assert sum(x["lis"] for x in seen[:3]) == 12  # every skill and gem step, none lost
    assert "Skill 0" in seen[0]["text"] and "Gem 5" in seen[2]["text"]
    # a heading never ends a part
    assert not any(x["text"].endswith("Gem changes") for x in seen)
    assert run["parts"]["focus"] is True
    # the cut keeps a heading with the row after it
    assert run["parts"]["cut"] == [2, 2]
