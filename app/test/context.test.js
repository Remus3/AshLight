/* PLAY-TD-11-CONTEXT (web/context.js, TD-11, F-068, F-124): region C shows
   exactly one context for the zone - the guide, the town search string, the
   map block or the zone name - from snap.play.context and ALSlots
   contextMode. It fits its track (228 px, 212 compact) in every mode it
   paints, the town row comes and goes with the zone, no build means no
   row, and Copy writes the exact string (at most 250 characters) only on
   the player's click. Never a clipboard read, never ALTabs.notify. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const C = require("../../web/context.js");
const S = require("../../web/slots.js");
const R = require("../../web/regions.js");

const WEB = path.join(__dirname, "..", "..", "web");
const SRC = fs.readFileSync(path.join(WEB, "context.js"), "utf8");
const CSS = fs.readFileSync(path.join(WEB, "context.css"), "utf8");
const APPCSS = fs.readFileSync(path.join(WEB, "app.css"), "utf8");
const HTML = fs.readFileSync(path.join(WEB, "index.html"), "utf8");

/* A small DOM: ids, attributes, classes, children, hidden, click. */
function makeDoc() {
  const doc = { all: [], byId: {}, selected: null };
  function elem(tag) {
    const n = {
      tagName: tag.toUpperCase(), attrs: {}, children: [], parentNode: null,
      hidden: false, listeners: {}, _text: "",
      get textContent() {
        return this.children.length ? this.children.map((c) => c.textContent).join("") : this._text;
      },
      set textContent(v) { this.children = []; this._text = String(v); },
      get id() { return this.attrs.id || ""; },
      set id(v) { this.attrs.id = String(v); doc.byId[v] = this; },
      get className() { return this.attrs.class || ""; },
      set className(v) { this.attrs.class = String(v); },
      getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
      setAttribute(k, v) { if (k === "id") { this.id = v; return; } this.attrs[k] = String(v); },
      removeAttribute(k) { delete this.attrs[k]; },
      appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
      replaceChildren() { this.children = []; this._text = ""; },
      addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
      click() { (this.listeners.click || []).forEach((fn) => fn({ type: "click" })); }
    };
    doc.all.push(n);
    return n;
  }
  doc.createElement = elem;
  doc.getElementById = (id) => doc.byId[id] || null;
  doc.querySelector = (sel) => {
    assert.equal(sel, '#play-c [data-slot="c"]');
    return doc.slot;
  };
  doc.querySelectorAll = (sel) => {
    const m = /^\[([a-z-]+)\]$/.exec(sel);
    return m ? doc.all.filter((n) => n.getAttribute(m[1]) !== null) : [];
  };
  doc.getSelection = () => ({
    removeAllRanges() { doc.selected = null; },
    addRange(r) { doc.selected = r.node; }
  });
  doc.createRange = () => ({ node: null, selectNodeContents(n) { this.node = n; } });
  const region = elem("section");
  region.id = "play-c";
  region.setAttribute("data-region", "c");
  const h = region.appendChild(elem("h2"));
  h.id = "play-c-h";
  h.textContent = "Right now";
  doc.slot = region.appendChild(elem("div"));
  doc.slot.setAttribute("data-slot", "c");
  doc.guide = region.appendChild(elem("div"));
  doc.guide.setAttribute("data-legacy", "c-guide");
  doc.setup = region.appendChild(elem("div"));
  doc.setup.setAttribute("data-legacy", "c-setup");
  doc.region = region;
  return doc;
}

function walk(n, out) {
  out = out || [];
  out.push(n);
  n.children.forEach((c) => walk(c, out));
  return out;
}
function visible(n) {
  for (let p = n; p; p = p.parentNode) { if (p.hidden) { return false; } }
  return true;
}
function find(doc, pred) { return walk(doc.region).filter((n) => pred(n) && visible(n)); }
function byClass(doc, cls) {
  return find(doc, (n) => n.className.split(" ").indexOf(cls) >= 0);
}
function buttons(doc) { return find(doc, (n) => n.tagName === "BUTTON"); }
function paneOf(doc) {
  const p = byClass(doc, "ctx-pane");
  assert.equal(p.length, 1, "exactly one pane shows");
  return p[0];
}

/* -- fixtures: snapshots as the core sends them (server/al/playcards.py) -- */

const CONSENTED = { consented: true, reading: true, path: "Client.txt" };
const WAYSTONE = "\"!rare monsters|reflect|no regen\"";
const GEAR = "\"cold res|fire res|lightning res\"";

function bonusRows() {
  return [
    { kind: "bonus", text: "+10% cold res - beat Beira." },
    { kind: "bonus", text: "Uncut skill gem in a stash." }
  ];
}

const GUIDE_BLOCK = {
  mode: "guide",
  title: "Find the Grelwood exit",
  full: "Find the Grelwood exit; the Mud Burrow cave is a short detour.",
  rows: [
    { kind: "objective", text: "Mud Burrow cave: a short detour." },
    ...bonusRows(),
    { kind: "hint", text: "Boss: cold damage. Your cold res: 20%." },
    { kind: "hint", text: "Carry a life flask." },
    { kind: "layout", text: "Burrow entrance near the waypoint." },
    { kind: "next", text: "Next: Mud Burrow." }
  ],
  facts: "Your level fits."
};

function zoneSnap(over) {
  return Object.assign({ tailer: CONSENTED, game_idle: false, maps: { count: 0 },
    in_hideout: false, zone: "Clearfell", area_id: "G1_2", area_level: 3,
    zone_guide: { kind: "campaign" }, play: { map_ok: false, context: { guide: GUIDE_BLOCK } } },
  over || {});
}

function townBlock(withBuild, text) {
  const rows = [];
  if (withBuild) {
    rows.push({ kind: "copy", text: "Life or energy shield", copy: text || GEAR, id: "defence",
      full: "Finds gear with the defence your build stacks." });
  }
  rows.push({ kind: "text", text: "Town: talk to Renly for a gem, sell, then head into" });
  rows.push({ kind: "text", text: "Clearfell." });
  rows.push({ kind: "next", text: "Next: Clearfell." });
  return { mode: "town", title: "In town", full: "In town", rows, facts: "" };
}

function townSnap(withBuild, text) {
  return zoneSnap({ zone: "Clearfell Encampment", area_id: "G1_town", in_town: true,
    play: { map_ok: false, context: { town: townBlock(withBuild, text) } } });
}

const MAP_BLOCK = {
  mode: "map", title: "Between maps", full: "Between maps",
  rows: [
    { kind: "text", text: "Last map: Sun Temple, 6:12, no deaths" },
    { kind: "text", text: "Maps this session: 2, 4.0 an hour" },
    { kind: "text", text: "Average map: 5:40" },
    { kind: "copy", text: "Waystones without risky mods", copy: WAYSTONE, id: "waystone",
      full: "Finds waystones without the mods that are risky for your build." }
  ],
  facts: "3 deaths in maps"
};

function mapSnap(mapOk) {
  return zoneSnap({ zone: "Your hideout", area_id: "HideoutFelled", in_hideout: true,
    zone_guide: null, maps: { count: 2 },
    play: { map_ok: mapOk, context: { map: MAP_BLOCK, town: { mode: "town",
      title: "In your hideout", full: "In your hideout", rows: [], facts: "" } } } });
}

function fakeNav(fail) {
  const nav = { writes: [], reads: 0, clipboard: {
    writeText(t) { nav.writes.push(t); return fail ? Promise.reject(new Error("no")) : Promise.resolve(); },
    readText() { nav.reads += 1; return Promise.resolve(""); }
  } };
  return nav;
}

function fresh(nav) {
  C.reset({ nav: nav || fakeNav() });
  const doc = makeDoc();
  C.wire(doc, {});
  return doc;
}

const tick = () => new Promise((r) => setImmediate(r));

/* ------------------------------------------------------------------------ */

test("registers as region C and retires the legacy guide group", () => {
  assert.equal(C.spec.name, "context");
  assert.equal(C.spec.region, "c");
  assert.deepEqual(C.spec.retires, ["c-guide"]);
  assert.match(SRC, /root\.ALRegions\.register\(api\.spec\)/);
  const reg = R.create({ warn() {} });
  reg.register(C.spec);
  const doc = fresh();
  reg.start(doc, {});
  assert.equal(doc.guide.hidden, true, "c-guide retired");
  assert.equal(doc.region.getAttribute("data-fit"), "yes");
  reg.paint(doc, zoneSnap(), 0);
  assert.equal(byClass(doc, "ctx-title")[0].textContent, GUIDE_BLOCK.title);
});

test("guide mode: the objective title, at most 7 rows and one facts row", () => {
  const doc = fresh();
  const m = C.paint(doc, zoneSnap(), 0);
  assert.equal(m.mode, "guide");
  const pane = paneOf(doc);
  assert.equal(pane.getAttribute("data-mode"), "guide");
  const title = byClass(doc, "ctx-title");
  assert.equal(title.length, 1);
  assert.equal(title[0].tagName, "H3");
  assert.match(title[0].className, /row-title/);
  assert.equal(title[0].getAttribute("title"), GUIDE_BLOCK.full);
  const rows = byClass(doc, "ctx-row");
  assert.equal(rows.length, 7);
  rows.forEach((r) => assert.match(r.className, /row-body one-line/));
  assert.equal(byClass(doc, "ctx-facts")[0].textContent, GUIDE_BLOCK.facts);
  // PC-1: a bonus row carries the edge, a cue that is not colour alone
  const bonus = rows.filter((r) => r.getAttribute("data-kind") === "bonus");
  assert.equal(bonus.length, 2);
  bonus.forEach((r) => assert.match(r.className, /\bedge\b/));
  // 7 rows: one row is marked to leave in the compact class, the gear hint
  const drop = byClass(doc, "ctx-drop");
  assert.equal(drop.length, 1);
  assert.equal(drop[0].textContent, "Carry a life flask.");
  assert.equal(buttons(doc).length, 0, "the guide has no control");
  assert.equal(doc.setup.hidden, true, "a painted mode hides the legacy setup group");
  assert.ok(!walk(doc.region).some((n) => n.getAttribute("aria-live")), "not a live region");
});

test("rows past 7 and words past the G5 cap leave lowest priority first", () => {
  const many = Object.assign({}, GUIDE_BLOCK, { rows: GUIDE_BLOCK.rows.concat([
    { kind: "bonus", text: "Extra row eight that should never show at all." }]) });
  let m = C.model(zoneSnap({ play: { context: { guide: many } } }), 2);
  assert.equal(m.rows.length, 7);
  const wordy = Object.assign({}, GUIDE_BLOCK, { rows: GUIDE_BLOCK.rows.map((r) =>
    Object.assign({}, r, { text: r.text + " and more words here" })) });
  m = C.model(zoneSnap({ play: { context: { guide: wordy } } }), 2);
  const count = C.words(m.title) + C.words(m.facts) +
    m.rows.reduce((a, r) => a + C.words(r.text), 0);
  assert.ok(count <= C.WORD_CAP - 2, count);
  const kinds = m.rows.map((r) => r.kind);
  assert.equal(kinds[0], "objective", "the objective stays");
  assert.ok(kinds.includes("next"), "the next zone stays longer than layout and hints");
  assert.ok(!kinds.includes("layout"));
});

test("region C fits its track in guide, town, map and none modes (full and compact)", () => {
  for (const cls of ["full", "compact"]) {
    for (const mode of ["guide", "town", "map", "none"]) {
      const lay = S.layout({ mode }, cls);
      assert.ok(lay.regions.c.slack >= 2, `${mode} ${cls}: slack ${lay.regions.c.slack}`);
    }
  }
  assert.equal(S.trackSet("full").tracks.c, 228);
  assert.equal(S.trackSet("compact").tracks.c, 212);
  assert.equal(S.trackSet("full").rows.c, C.ROWS);
  assert.equal(S.trackSet("compact").rows.c, C.ROWS_COMPACT);
  // the line boxes the arithmetic assumes: title 26 (20 px / 600), rows 22,
  // facts 20, the Copy row 32 with the 28 px button, no gaps
  assert.match(APPCSS, /--al-fs-title: 1\.25rem;/);
  assert.match(APPCSS, /--al-lh-title: 1\.625rem;/);
  assert.match(APPCSS, /--al-lh-body: 1\.375rem;/);
  assert.match(APPCSS, /--al-lh-meta: 1\.25rem;/);
  assert.match(CSS, /\.ctx-title \{ font-weight: 600; \}/);
  assert.match(CSS, /min-height: 2rem;/);
  assert.match(CSS, /gap: 0;/);
  // the compact cascade hides the marked row exactly where the track
  // tokens of app.css switch to compact
  const css = (t) => [...t.matchAll(/@media \(min-width: ([\d.]+em)\) and \(min-height: ([\d.]+em)\)/g)]
    .map((x) => x[1] + "/" + x[2]);
  const ours = css(CSS);
  const theirs = css(APPCSS.slice(APPCSS.indexOf("compact or full per scale step")));
  assert.deepEqual(ours, theirs.slice(0, ours.length));
  assert.equal(ours.length, 8);
  const hides = [...CSS.matchAll(/\.ctx-drop \{ display: (none|block); \}/g)].map((x) => x[1]);
  assert.deepEqual(hides, ["none", "block", "none", "block", "none", "block", "none", "block"]);
});

test("a replayed log: entering a town shows the search row, leaving hides it", () => {
  const doc = fresh();
  const replay = [
    ["The Riverbank", zoneSnap({ zone: "The Riverbank", area_id: "G1_1" }), "guide"],
    ["Clearfell Encampment", townSnap(true), "town"],
    ["Clearfell", zoneSnap(), "guide"],
    ["Clearfell Encampment", townSnap(true), "town"]
  ];
  for (const [zone, snap, want] of replay) {
    const m = C.paint(doc, snap, 0);
    assert.equal(m.mode, want, zone);
    const copy = byClass(doc, "ctx-copy");
    if (want === "town") {
      assert.equal(copy.length, 1, zone + ": the search row shows");
      assert.equal(byClass(doc, "ctx-copy-label")[0].textContent, "Life or energy shield");
      assert.equal(buttons(doc).length, 1);
      assert.equal(byClass(doc, "ctx-title")[0].textContent, "In town");
    } else {
      assert.equal(copy.length, 0, zone + ": no search row outside town");
      assert.equal(buttons(doc).length, 0);
    }
  }
});

test("no build means no search row in town", () => {
  const doc = fresh();
  const m = C.paint(doc, townSnap(false), 0);
  assert.equal(m.mode, "town");
  assert.equal(byClass(doc, "ctx-copy").length, 0);
  assert.equal(buttons(doc).length, 0);
  assert.equal(byClass(doc, "ctx-row").length, 3);
});

test("Copy writes the exact string, at most 250 characters, only on the click", async () => {
  const exact = "\"" + "a".repeat(248) + "\"";
  assert.equal(exact.length, 250);
  const nav = fakeNav();
  const doc = fresh(nav);
  C.paint(doc, townSnap(true, exact), 0);
  C.paint(doc, townSnap(true, exact), 0);
  assert.deepEqual(nav.writes, [], "painting never writes the clipboard");
  const btn = buttons(doc)[0];
  assert.equal(btn.textContent, "Copy");
  assert.equal(btn.getAttribute("type"), "button");
  assert.equal(btn.getAttribute("aria-label"), "Copy Life or energy shield search string");
  btn.click();
  await tick();
  assert.deepEqual(nav.writes, [exact]);
  assert.equal(nav.reads, 0, "never a clipboard read");
  assert.equal(byClass(doc, "ctx-said")[0].textContent, C.COPIED);
  assert.match(btn.getAttribute("aria-label"), /\(copied\)$/);
  // the same push again keeps the button and its word (no rebuild)
  C.paint(doc, townSnap(true, exact), 0);
  assert.equal(buttons(doc)[0], btn);
  assert.equal(byClass(doc, "ctx-said")[0].textContent, C.COPIED);
  // one character over the game's limit: no row at all
  const doc2 = fresh(fakeNav());
  C.paint(doc2, townSnap(true, exact + "b"), 0);
  assert.equal(byClass(doc2, "ctx-copy").length, 0);
});

test("a refused clipboard selects the string itself for Ctrl+C", async () => {
  const nav = fakeNav(true);
  const doc = fresh(nav);
  C.paint(doc, townSnap(true), 0);
  buttons(doc)[0].click();
  await tick();
  await tick();
  const label = byClass(doc, "ctx-copy-label")[0];
  assert.equal(label.textContent, GEAR);
  assert.equal(doc.selected, label);
  assert.equal(byClass(doc, "ctx-said")[0].textContent, C.FALLBACK);
});

test("none mode: the zone name, and a map zone while map_ok is false", () => {
  const doc = fresh();
  let m = C.paint(doc, { tailer: CONSENTED, game_idle: false, zone: null, play: {} }, 0);
  assert.equal(m.mode, "none");
  assert.equal(byClass(doc, "ctx-title")[0].textContent, C.NO_ZONE);
  assert.equal(byClass(doc, "ctx-row").length, 1);
  const sun = zoneSnap({ zone: "Sun Temple", area_id: "MapSunTemple", area_level: 65,
    zone_guide: { kind: "endgame" }, maps: { count: 2, current: { inside: true } },
    play: { map_ok: false, context: { map: MAP_BLOCK } } });
  m = C.paint(doc, sun, 0);
  assert.equal(m.mode, "none");
  assert.equal(byClass(doc, "ctx-title")[0].textContent, "Sun Temple");
  assert.equal(byClass(doc, "ctx-row")[0].textContent, "Area level 65.");
  assert.equal(buttons(doc).length, 0);
  // the hideout after a map while map_ok is false is town
  assert.equal(C.paint(doc, mapSnap(false), 0).mode, "town");
  assert.equal(byClass(doc, "ctx-title")[0].textContent, "In your hideout");
});

test("map mode is built from fixtures and shows once map_ok is set", () => {
  const doc = fresh();
  const m = C.paint(doc, mapSnap(true), 0);
  assert.equal(m.mode, "map");
  assert.equal(byClass(doc, "ctx-title")[0].textContent, "Between maps");
  assert.equal(byClass(doc, "ctx-row").length, 3);
  assert.equal(byClass(doc, "ctx-facts")[0].textContent, "3 deaths in maps");
  assert.equal(buttons(doc).length, 1, "one control: the waystone Copy");
});

test("a mode with no painter leaves the legacy setup group; mode() adds one", () => {
  const doc = fresh();
  C.paint(doc, zoneSnap(), 0);
  assert.equal(doc.setup.hidden, true);
  const setup = { tailer: { consented: false }, play: { context: { setup: { title: "Set up" } } } };
  let m = C.paint(doc, setup, 0);
  assert.equal(m.mode, "setup");
  assert.equal(m.own, false);
  assert.equal(doc.slot.hidden, true, "no painter: this slot hides");
  assert.equal(doc.setup.hidden, false, "the legacy group shows again");
  // a group hidden by someone else (a retire) is never shown by this file
  C.paint(doc, zoneSnap(), 0);
  doc.setup.removeAttribute("data-context-hid");
  C.paint(doc, setup, 0);
  assert.equal(doc.setup.hidden, true);
  // PLAY-TD-12 registers its painter: it gets its own pane and the block
  const calls = [];
  assert.equal(C.mode("setup", (d, pane, snap, now, ctx, block) => {
    calls.push(block);
    pane.textContent = "painted";
  }), true);
  assert.equal(C.mode("nonsense", () => {}), false);
  assert.equal(C.mode("idle", "not a function"), false);
  assert.equal(C.hasPainter("setup"), true);
  m = C.paint(doc, setup, 0);
  assert.equal(doc.slot.hidden, false);
  assert.deepEqual(calls, [{ title: "Set up" }]);
  assert.equal(paneOf(doc).getAttribute("data-mode"), "setup");
  assert.equal(C.mode("setup", null), true);
  assert.equal(C.hasPainter("setup"), false);
});

test("a missing block falls back to the zone name, never a blank region", () => {
  const doc = fresh();
  const m = C.paint(doc, zoneSnap({ play: { map_ok: false, context: null } }), 0);
  assert.equal(m.mode, "guide");
  assert.equal(byClass(doc, "ctx-title")[0].textContent, "Clearfell");
  assert.equal(byClass(doc, "ctx-row")[0].textContent, "Area level 3.");
});

test("context.js: no timer, network, clipboard read, live region or notify", () => {
  const code = SRC.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
  for (const bad of ["setInterval", "setTimeout", "requestAnimationFrame", "fetch(",
    "XMLHttpRequest", "EventSource", "readText", "clipboard", "innerHTML", "aria-live",
    "notify", "ALTabs"]) {
    assert.ok(!code.includes(bad), bad);
  }
  assert.match(code, /api\.copy\(r\.copy, navigatorOf\(\)/, "the copy goes through ALSearch.copy");
  for (const [name, text] of [["context.js", SRC], ["context.css", CSS]]) {
    assert.doesNotMatch(text, /[^\x0a\x20-\x7e]/, name + " ASCII and LF");
  }
  assert.doesNotMatch(CSS, /color:/, "no colour of its own: the shared tokens and classes");
  assert.match(HTML, /<script src="\/web\/search\.js" defer><\/script>/);
});
