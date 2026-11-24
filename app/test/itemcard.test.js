/* PLAY-TD-16A-ITEMCARD (web/itemcard.js, TD-16, F-151, F-025): region I
   shows the last item check from snap.play.item with the verdict word and
   its glyph first, keeps every row in its place while the card fills,
   shows at most 2 links and 2 actions, and teaches the press with the
   bound key while nothing is checked. Never a clipboard read, never a
   trade call, never ALTabs.notify, no timer. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const IC = require("../../web/itemcard.js");
const Tabs = require("../../web/tabs.js");
const R = require("../../web/regions.js");

const WEB = path.join(__dirname, "..", "..", "web");
const SRC = fs.readFileSync(path.join(WEB, "itemcard.js"), "utf8");
const CSS = fs.readFileSync(path.join(WEB, "itemcard.css"), "utf8");
const HTML = fs.readFileSync(path.join(WEB, "index.html"), "utf8");
const APP_CSS = fs.readFileSync(path.join(WEB, "app.css"), "utf8");

/* A small DOM: ids, parents, children, attributes, text, hidden, click. */
function makeDoc(opts) {
  const o = opts || {};
  const doc = { byId: {}, all: [] };
  function textOf(n) {
    if (n.nodeType === 3) { return n.textContent; }
    return n.children.length ? n.children.map(textOf).join("") : n.own;
  }
  function elem(tag) {
    const n = {
      tagName: tag.toUpperCase(), nodeType: 1, attrs: {}, children: [], parentNode: null,
      hidden: false, disabled: false, own: "", listeners: {},
      get id() { return this.attrs.id || ""; },
      set id(v) { this.attrs.id = String(v); doc.byId[v] = this; },
      get className() { return this.attrs.class || ""; },
      set className(v) { this.attrs.class = String(v); },
      get textContent() { return this.children.length ? textOf(this) : this.own; },
      set textContent(v) { this.children = []; this.own = String(v); },
      get firstChild() { return this.children[0] || null; },
      getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
      setAttribute(k, v) {
        if (k === "id") { this.id = v; return; }
        this.attrs[k] = String(v);
      },
      removeAttribute(k) { delete this.attrs[k]; },
      appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
      insertBefore(c, ref) {
        const i = this.children.indexOf(ref);
        c.parentNode = this;
        this.children.splice(i < 0 ? this.children.length : i, 0, c);
        return c;
      },
      removeChild(c) { this.children = this.children.filter((x) => x !== c); c.parentNode = null; return c; },
      replaceChildren() { this.children = []; },
      addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
      click() { (this.listeners.click || []).forEach((fn) => fn({ type: "click" })); }
    };
    doc.all.push(n);
    return n;
  }
  doc.createElement = elem;
  doc.createTextNode = (t) => ({ nodeType: 3, textContent: String(t) });
  doc.getElementById = (id) => doc.byId[id] || null;
  doc.querySelector = (sel) => {
    assert.equal(sel, '#play-i [data-slot="i"]');
    return doc.slot;
  };
  doc.querySelectorAll = (sel) => {
    const m = /^\[([a-z-]+)\]$/.exec(sel);
    return m ? doc.all.filter((n) => n.nodeType === 1 && n.getAttribute(m[1]) !== null) : [];
  };
  // the page bits I touches: the tab panels, region I with its slot and the
  // legacy group that holds #evalbox (in Play, or in another tab)
  Tabs.TABS.forEach((t) => {
    const b = elem("button");
    b.id = "tab-" + t;
    b.querySelector = () => null;
    const p = elem("div");
    p.id = "panel-" + t;
    p.hidden = t !== "play";
    doc[t] = p;
  });
  const region = doc.play.appendChild(elem("section"));
  region.id = "play-i";
  region.setAttribute("data-region", "i");
  doc.slot = region.appendChild(elem("div"));
  doc.slot.setAttribute("data-slot", "i");
  const legacy = region.appendChild(elem("div"));
  legacy.setAttribute("data-legacy", "i-eval");
  const box = (o.evalboxIn ? doc[o.evalboxIn] : legacy).appendChild(elem("section"));
  box.id = "evalbox";
  doc.legacy = legacy;
  doc.region = region;
  return doc;
}

const URL_T = "https://www.pathofexile.com/trade2/search/poe2/Standard?q=%7B%7D";
const URL_U = "https://www.pathofexile.com/trade2/search/poe2/Standard?q=%7B%22u%22%7D";
function card(extra) {
  return Object.assign({
    kind: "verdict", state: "done", glyph: "[+]", word: "Upgrade", name: "Grim Clutch",
    sentence: ["21 points more than your Gloves."], full: "21 points more than your Gloves.",
    compare: { label: "vs Old Grip", rows: [
      { text: "+30 to maximum Life", value: "+30 points" },
      { text: "+15% to Fire Resistance", value: "+15 points" },
      { text: "", value: "" }, { text: "", value: "" }, { text: "", value: "" }] },
    price: { value: "Trade link ready", source: "" },
    links: [{ label: "Trade search", url: URL_T }, { label: "Upgrade search", url: URL_U }],
    at: 1795099149.9
  }, extra || {});
}
function snapWith(item, extra) { return Object.assign({ play: { item: item } }, extra || {}); }
function txt(doc, id) { return doc.getElementById(id).textContent; }
function shown(n) { for (let p = n; p; p = p.parentNode) { if (p.hidden) { return false; } } return true; }

test("the verdict word comes first with its glyph, then the item name", () => {
  IC.reset();
  const doc = makeDoc();
  IC.wire(doc, { tabs: Tabs, api: null });
  const m = IC.paint(doc, snapWith(card()));
  assert.equal(m.kind, "verdict");
  const head = doc.getElementById("ic-head");
  assert.equal(head.children[0].id, "ic-word", "the word leads the head");
  assert.equal(txt(doc, "ic-word"), "[+] Upgrade");
  assert.equal(head.children[0].children[0].getAttribute("aria-hidden"), "true", "glyph not read");
  assert.equal(txt(doc, "ic-name"), "Grim Clutch");
  assert.equal(doc.getElementById("ic-name").getAttribute("title"), "Grim Clutch");
  assert.equal(doc.getElementById("ic").getAttribute("data-tone"), "ok");
  assert.equal(shown(doc.getElementById("ic-body")), true);
  assert.equal(shown(doc.getElementById("ic-empty")), false);
});

test("the head is the one polite, atomic live region", () => {
  IC.reset();
  const doc = makeDoc();
  IC.wire(doc, { tabs: Tabs });
  IC.paint(doc, snapWith(card()));
  const live = doc.all.filter((n) => n.nodeType === 1 &&
    (n.getAttribute("aria-live") || n.getAttribute("role") === "status"));
  assert.deepEqual(live.map((n) => n.id), ["ic-head"]);
  const head = live[0];
  assert.equal(head.getAttribute("aria-live"), "polite");
  assert.equal(head.getAttribute("aria-atomic"), "true");
  assert.equal(head.getAttribute("role"), "status");
  // a repaint of the same check writes nothing (so nothing is re-announced)
  // the word is the text node after the glyph and its space (no span)
  const word = doc.getElementById("ic-word").children[2];
  assert.equal(word.nodeType, 3);
  let writes = 0;
  let val = word.textContent;
  Object.defineProperty(word, "textContent", { get() { return val; },
    set(v) { writes += 1; val = v; } });
  IC.paint(doc, snapWith(card()));
  assert.equal(writes, 0);
  IC.paint(doc, snapWith(card({ word: "Sidegrade", glyph: "[-]", state: "idle" })));
  assert.equal(writes, 1);
  assert.equal(doc.getElementById("ic").getAttribute("data-tone"), "neutral");
});

test("rows are reserved: 2 sentence rows and 5 compare rows in every card", () => {
  IC.reset();
  const doc = makeDoc();
  IC.wire(doc, { tabs: Tabs });
  IC.paint(doc, snapWith(card()));
  const rows = doc.all.filter((n) => n.nodeType === 1 && n.className.split(" ").includes("ic-cmp-row"));
  const sent = doc.getElementById("ic-body").children
    .filter((n) => n.nodeType === 1 && n.className.split(" ").includes("ic-sent"));
  assert.equal(rows.length, 5);
  assert.equal(sent.length, 2);
  const before = doc.all.length;
  // a thinner card (the staged fill's first step) keeps every node in place
  IC.paint(doc, snapWith(card({ sentence: [], compare: { label: "", rows: [] },
    price: { value: "", source: "" }, links: [], stage: "weights" })));
  assert.equal(doc.all.length, before, "no node is made or removed");
  rows.forEach((r) => assert.equal(shown(r), true));
  sent.forEach((r) => assert.equal(shown(r), true));
  assert.equal(doc.getElementById("ic").getAttribute("data-stage"), "weights");
  assert.equal(rows[0].children[1].textContent, "");
  // the full card fills the same nodes
  IC.paint(doc, snapWith(card()));
  assert.equal(doc.all.length, before + 2, "only the two links are new");
  // a row: its points (floated right) first, then its text as a text node
  assert.equal(rows[0].children[1].textContent, "+30 to maximum Life");
  assert.equal(rows[0].getAttribute("title"), "+30 to maximum Life");
  assert.equal(rows[0].children[0].textContent, "+30 points");
  assert.equal(sent[0].textContent, "21 points more than your Gloves.");
  assert.equal(sent[0].getAttribute("title"), "21 points more than your Gloves.");
  assert.equal(txt(doc, "ic-label"), "vs Old Grip");
});

test("at most 2 links: https only, a new tab, never a trade call", () => {
  IC.reset();
  const doc = makeDoc();
  IC.wire(doc, { tabs: Tabs });
  IC.paint(doc, snapWith(card({ links: [
    { label: "Trade search", url: URL_T }, { label: "Bad", url: "javascript:alert(1)" },
    { label: "Upgrade search", url: URL_U }, { label: "Third", url: URL_T }] })));
  // the row holds the links, then the action buttons
  const links = doc.getElementById("ic-links").children.filter((n) => n.tagName === "A");
  assert.deepEqual(links.map((a) => a.textContent), ["Trade search", "Upgrade search"]);
  links.forEach((a) => {
    assert.equal(a.tagName, "A");
    assert.match(a.getAttribute("href"), /^https:\/\//);
    assert.equal(a.getAttribute("target"), "_blank");
    assert.equal(a.getAttribute("rel"), "noopener noreferrer");
    assert.match(a.getAttribute("aria-label"), /opens in your browser/);
  });
  const code = SRC.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
  for (const bad of ["fetch(", "XMLHttpRequest", "EventSource", "clipboard", "setInterval",
    "setTimeout", "requestAnimationFrame", "innerHTML", "ALTabs", "notify(", "trade2"]) {
    assert.ok(!code.includes(bad), bad);
  }
});

test("Details is not rendered while #evalbox sits on Play", () => {
  IC.reset();
  const doc = makeDoc();
  IC.wire(doc, { tabs: Tabs });
  IC.paint(doc, snapWith(card()));
  assert.equal(IC.detailsTab(doc), null);
  assert.equal(shown(doc.getElementById("ic-details")), false);
  assert.equal(shown(doc.getElementById("ic-wear")), false);
});

test("Details shows the tab that holds #evalbox once it left Play", () => {
  IC.reset();
  const doc = makeDoc({ evalboxIn: "build" });
  IC.wire(doc, { tabs: Tabs });
  IC.paint(doc, snapWith(card()));
  assert.equal(IC.detailsTab(doc), "build");
  const b = doc.getElementById("ic-details");
  assert.equal(shown(b), true);
  assert.equal(b.textContent, "Details");
  assert.equal(b.getAttribute("type"), "button");
  b.click();
  assert.equal(Tabs.current(), "build");
  assert.equal(doc.build.hidden, false);
  Tabs.show(doc, "play", false);
});

test("I wear this shows only with can_wear and posts /api/wear on the click", () => {
  IC.reset();
  const doc = makeDoc();
  const calls = [];
  const api = (method, p, body) => { calls.push([method, p, body]); return Promise.resolve({}); };
  IC.wire(doc, { tabs: Tabs, api });
  IC.paint(doc, snapWith(card()));
  const b = doc.getElementById("ic-wear");
  assert.equal(shown(b), false);
  IC.paint(doc, snapWith(card({ can_wear: true })));
  assert.equal(shown(b), true);
  assert.equal(b.textContent, "I wear this");
  b.click();
  assert.deepEqual(calls, [["POST", "/api/wear", {}]]);
  assert.equal(b.disabled, true, "rests until the next check");
  IC.paint(doc, snapWith(card()));
  assert.equal(shown(b), false);
  assert.equal(b.disabled, false);
});

test("at most 2 links and 2 actions: the control cap of region I is 4", () => {
  IC.reset();
  const doc = makeDoc({ evalboxIn: "build" });
  IC.wire(doc, { tabs: Tabs, api: () => Promise.resolve({}) });
  IC.paint(doc, snapWith(card({ can_wear: true })));
  const inSlot = (n) => { for (let p = n; p; p = p.parentNode) { if (p === doc.slot) { return true; } } return false; };
  const controls = doc.all.filter((n) => n.nodeType === 1 && shown(n) && inSlot(n) &&
    (n.tagName === "A" || n.tagName === "BUTTON"));
  assert.equal(controls.length, 4);
});

test("the empty card teaches the press with the bound key and says where the check stays", () => {
  IC.reset();
  const doc = makeDoc();
  IC.wire(doc, { tabs: Tabs });
  const m = IC.paint(doc, { play: { item: null } });
  assert.equal(m.kind, "empty");
  assert.equal(txt(doc, "ic-word"), "[ ] Nothing checked yet");
  assert.equal(shown(doc.getElementById("ic-body")), false);
  const rows = doc.getElementById("ic-empty").children.map((r) => r.textContent);
  // OVL-KEYS-WEB: no bound key yet, so no key is named
  assert.deepEqual(rows, ["Press Ctrl+C on an item, then the", "item check key.",
    "The check stays here."]);
  rows.forEach((r) => assert.ok(r.length <= IC.ROW_CHARS, r));
  // the bound key from the snapshot (F-026); the card time is no longer
  // repeated here (PLAY-FIT-G5-TOTALS, design 0001 G5)
  IC.paint(doc, { play: {}, hotkeys: { eval: { key: "Ctrl+Shift+F9" } },
    overlay_layout: { card_s: 60 } });
  const again = doc.getElementById("ic-empty").children.map((r) => r.textContent);
  assert.deepEqual(again, ["Press Ctrl+C on an item, then", "Ctrl+Shift+F9.",
    "The check stays here."]);
  // a card time that is not one of the choices reads the default
  assert.equal(IC.cardTime({ overlay_layout: { card_s: 5 } }), 20);
  assert.equal(IC.itemKey({ hotkeys: { eval: { key: "" } } }), "");
  assert.equal(IC.itemKey({ hotkeys: { eval: { key: null, want: "Ctrl+Alt+K" } } }), "");
  assert.equal(IC.itemKey(null), "");
  assert.equal(IC.DEFAULT_KEY, undefined);
});

test("the next press replaces the empty card; no snapshot hides the region", () => {
  IC.reset();
  const doc = makeDoc();
  IC.wire(doc, { tabs: Tabs });
  assert.equal(IC.paint(doc, null), null);
  assert.equal(doc.getElementById("ic").hidden, true);
  IC.paint(doc, {});
  assert.equal(shown(doc.getElementById("ic-empty")), true);
  IC.paint(doc, snapWith(card()));
  assert.equal(shown(doc.getElementById("ic-empty")), false);
  assert.equal(shown(doc.getElementById("ic-body")), true);
});

test("a press error and a waystone use the core's words", () => {
  IC.reset();
  const doc = makeDoc();
  IC.wire(doc, { tabs: Tabs });
  /* RUN-NO-DEAD-ENDS (research 0042 F20 d): a press with no item names none
     and the price row does not repeat the card's words (server/al/playcards.py) */
  IC.paint(doc, snapWith(card({ kind: "error", state: "idle", glyph: "[-]", word: "Not an item",
    name: "", sentence: ["The clipboard did not hold an item."], links: [],
    compare: { label: "", rows: [] },
    price: { value: "No price for this check", source: "" } })));
  assert.equal(txt(doc, "ic-word"), "[-] Not an item");
  assert.equal(doc.getElementById("ic-name").hidden, true);
  assert.equal(txt(doc, "ic-pval"), "No price for this check");
  assert.equal(txt(doc, "ic-psrc"), "");
  assert.equal(doc.getElementById("ic-links").children.filter((n) => n.tagName === "A").length, 0);
  IC.paint(doc, snapWith(card({ kind: "waystone", state: "needs-operator", glyph: "[?]",
    word: "Risky", name: "Waystone (Tier 15)",
    compare: { label: "Rewards and risky mods", rows: [{ text: "+38% rarity", value: "" },
      { text: "Monsters reflect damage", value: "risky" }] } })));
  assert.equal(txt(doc, "ic-word"), "[?] Risky");
  assert.equal(doc.getElementById("ic").getAttribute("data-tone"), "warn");
  assert.equal(txt(doc, "ic-label"), "Rewards and risky mods");
});

test("the item's own asking price is the price row's value", () => {
  IC.reset();
  const doc = makeDoc();
  IC.wire(doc, { tabs: Tabs });
  IC.paint(doc, snapWith(card(), { eval: { value: { price: { kind: "price", amount: 5,
    currency: "exalted", name: "Exalted Orb" } } } }));
  assert.equal(txt(doc, "ic-pval"), "Asking price: 5 Exalted Orb");
  assert.equal(shown(doc.getElementById("ic-psrc")), false);
  assert.equal(IC.askingPrice({ eval: { value: { price: { kind: "b/o", amount: 2.5,
    currency: "divine" } } } }), "Buyout price: 2.5 divine");
  assert.equal(IC.askingPrice({ eval: { value: { price: { amount: 0, currency: "x" } } } }), "");
  IC.paint(doc, snapWith(card()));
  assert.equal(txt(doc, "ic-pval"), "Trade link ready");
});

test("a card with no word falls back to a design mark word, Not checked", () => {
  /* TC-VERDICT-FALLBACK-WORD: the twin of server/al/text/itemcheck.py
     VERDICT_FALLBACK; design 0001 section 9 rule 13 lists it. */
  IC.reset();
  assert.equal(IC.model(snapWith(card({ word: "" }))).word, "Not checked");
  assert.equal(IC.model(snapWith(card({ word: 7 }))).word, "Not checked");
  assert.ok(!/"Checked"/.test(SRC), "no bare Checked fallback left");
});

test("a wrong-typed snapshot reads as missing (fuzz)", () => {
  IC.reset();
  const doc = makeDoc();
  IC.wire(doc, { tabs: Tabs });
  for (const bad of [{ play: 3 }, { play: { item: "x" } }, { play: { item: [] } },
    { play: { item: { compare: 5, rows: null, links: "x", sentence: 7, price: [] } } }]) {
    assert.doesNotThrow(() => IC.paint(doc, bad));
  }
  const m = IC.model({ play: { item: { compare: 5, links: "x", sentence: 7 } } });
  assert.equal(m.rows.length, 5);
  assert.equal(m.sentence.length, 2);
  assert.deepEqual(m.links, []);
});

test("registers as region I and retires the legacy item check group", () => {
  assert.deepEqual(IC.spec, Object.assign({}, IC.spec, { name: "itemcard", region: "i",
    retires: ["i-eval"] }));
  IC.reset();
  const doc = makeDoc();
  const reg = R.create({ warn: () => {} });
  reg.register(IC.spec);
  reg.start(doc, { tabs: Tabs, api: null });
  assert.equal(doc.legacy.hidden, true);
  assert.equal(doc.region.getAttribute("data-fit"), "yes");
  reg.paint(doc, snapWith(card()), 0);
  assert.equal(txt(doc, "ic-word"), "[+] Upgrade");
});

test("the CSS reserves the 342 px of plan 03 3.4 with the shared line boxes (head 32 + 4 = one 36 px box)", () => {
  // every rule is scoped to region I and every size is a type token
  const rules = CSS.replace(/\/\*[\s\S]*?\*\//g, "");
  for (const m of rules.matchAll(/([^{}]+)\{/g)) {
    m[1].split(",").forEach((sel) => assert.match(sel.trim(), /^#play-i /, sel));
  }
  assert.doesNotMatch(rules, /font-size:\s*(?![\s]|var\(--al-fs-)/, "font sizes from tokens only");
  assert.doesNotMatch(rules, /\d+px/, "rem and tokens only, so s scales every row");
  assert.doesNotMatch(rules, /(animation|transition|overflow-y|overflow:\s*(auto|scroll))/);
  assert.match(rules, /\.ic-word \{[^}]*font-size: var\(--al-fs-glance\)[^}]*font-weight: 700/);
  // the line boxes the arithmetic adds up (rem at s = 1, 16 px)
  const lh = (name) => parseFloat(new RegExp("--al-lh-" + name + ":\\s*([\\d.]+)rem").exec(APP_CSS)[1]) * 16;
  const sum = 2 + 12 + 12 + lh("hero") + 2 * lh("body") + 8 + lh("meta") + 5 * lh("body") +
    8 + lh("title") + 28 + 8 + 28;
  assert.equal(sum, 342);
  assert.ok(360 - sum >= 16 && 348 - sum >= 6, "slack 18 full, 6 compact");
  assert.doesNotMatch(SRC + CSS, /[^\x0a\x20-\x7e]/, "ASCII and LF");
  // the page pre-links both files (no index.html edit in this package)
  assert.match(HTML, /<link rel="stylesheet" href="\/web\/itemcard\.css">/);
  assert.match(HTML, /<script src="\/web\/itemcard\.js" defer><\/script>/);
});
