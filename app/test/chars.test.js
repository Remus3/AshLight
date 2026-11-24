/* UTIL-MULTICHAR: exact output of the per-character selector helpers
   (web/chars.js, decision 0038). Synthetic names only. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const ch = web.load("chars.js");

const SNAP = {
  character: "Sable", "class": "Witch", level: 4, deaths: 2, level_ups: 3,
  pace: { text: "Pace: now." }, underlevel: { text: "3 levels under this zone." },
  acts: { splits: [{ key: "G1" }], zones: [{ name: "Clearfell" }], current: "G1",
    empty_text: "No act times yet." },
  characters: [
    { name: "Sable", current: true, "class": "Witch", level: 4, deaths: 2, level_ups: 3,
      pace: { text: "Pace: now." }, acts: { splits: [{ key: "G1" }] } },
    { name: "Quill", current: false, "class": "Monk", level: 20, deaths: 5, level_ups: 2,
      pace: { text: "" }, acts: { splits: [{ key: "G1" }, { key: "G2" }] } }],
  run_history: { on: true, best: [{ key: "G1" }], by_character: {
    Quill: { on: true, best: [{ key: "G2" }] }, Old: { on: true, best: [] } } },
};

test("chars: names list the current one first, then live, then saved only", () => {
  assert.deepEqual(ch.names(SNAP), [{ name: "Sable", current: true },
    { name: "Quill", current: false }, { name: "Old", current: false }]);
  assert.deepEqual(ch.names(null), []);
});

test("chars: names are capped at 12", () => {
  const by = {};
  for (let i = 0; i < 20; i++) { by["C" + i] = { best: [] }; }
  assert.equal(ch.names({ characters: [], run_history: { by_character: by } }).length, ch.MAX);
  assert.equal(ch.MAX, 12);
});

test("chars: view keeps the snapshot for the current character", () => {
  assert.equal(ch.view(SNAP, ""), SNAP);
  assert.equal(ch.view(SNAP, "Sable"), SNAP);
  assert.equal(ch.view(SNAP, "Nobody"), SNAP);
});

test("chars: view swaps in a live character's numbers", () => {
  const v = ch.view(SNAP, "Quill");
  assert.equal(v.character, "Quill");
  assert.equal(v["class"], "Monk");
  assert.equal(v.level, 20);
  assert.equal(v.deaths, 5);
  assert.equal(v.acts.splits.length, 2);
  assert.deepEqual(v.run_history.best, [{ key: "G2" }]);
  assert.equal(v.underlevel, null);
  assert.equal(v.who_note, " (not playing)");
  assert.equal(SNAP.character, "Sable"); // the snapshot is not changed
});

test("chars: a saved-only character shows its run history, no live numbers", () => {
  const v = ch.view(SNAP, "Old");
  assert.equal(v.level, null);
  assert.equal(v.deaths, 0);
  assert.deepEqual(v.acts.splits, []);
  assert.deepEqual(v.acts.zones, []);
  assert.equal(v.acts.empty_text, "No act times yet.");
  assert.deepEqual(v.run_history.best, []);
  assert.equal(v.who_note, " (history only)");
  assert.equal(SNAP.acts.splits.length, 1);
});

test("chars: a name past the 12-name cap is not picked", () => {
  const by = {};
  for (let i = 0; i < 20; i++) { by["C" + i] = { best: [] }; }
  const snap = { character: "Sable", characters: [], run_history: { by_character: by } };
  assert.equal(ch.view(snap, "C19"), snap);
  assert.notEqual(ch.view(snap, "C0"), snap);
});

test("chars: Object.prototype names are kept (AUDIT-P6-LOW P6-3)", () => {
  const snap = {
    character: "constructor",
    characters: [{ name: "constructor", current: true }, { name: "toString", current: false }],
    run_history: { by_character: JSON.parse(
      '{"__proto__": {"best": []}, "hasOwnProperty": {"best": []}}') },
  };
  assert.deepEqual(ch.names(snap), [{ name: "constructor", current: true },
    { name: "toString", current: false }, { name: "__proto__", current: false },
    { name: "hasOwnProperty", current: false }]);
  assert.equal(ch.view(snap, "__proto__").character, "__proto__");
});

/* ---- a small fake DOM: enough for the card pages and the pagers -------- */
function matches(n, sel) {
  let m;
  if ((m = /^\[([\w-]+)="([^"]*)"\]$/.exec(sel))) { return n.attrs[m[1]] === m[2]; }
  if ((m = /^\[([\w-]+)\]$/.exec(sel))) { return m[1] in n.attrs; }
  if (sel.charAt(0) === ".") { return n.className.split(/\s+/).includes(sel.slice(1)); }
  return n.tagName === sel.toUpperCase();
}

function fakeDoc(size) {
  const doc = { activeElement: null, els: {} };
  doc.createElement = (tag) => ({
    tagName: tag.toUpperCase(), className: "", hidden: false, children: [], parentNode: null,
    attrs: {}, listeners: {}, _text: "", value: "", checked: false,
    get firstChild() { return this.children[0] || null; },
    get textContent() { return this._text + this.children.map((c) => c.textContent).join(""); },
    set textContent(v) { this.children = []; this._text = String(v); },
    appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
    insertBefore(c, ref) {
      const i = this.children.indexOf(ref);
      if (i < 0) { return this.appendChild(c); }
      c.parentNode = this; this.children.splice(i, 0, c); return c;
    },
    removeChild(c) { this.children = this.children.filter((x) => x !== c); return c; },
    replaceChildren(...kids) { this.children = []; this._text = ""; kids.forEach((k) => this.appendChild(k)); },
    setAttribute(k, v) { this.attrs[k] = String(v); if (k === "id") { doc.els[v] = this; } },
    getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
    hasAttribute(k) { return k in this.attrs; },
    removeAttribute(k) { delete this.attrs[k]; },
    addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
    click() { (this.listeners.click || []).forEach((fn) => fn({ target: this })); },
    contains(x) { return x === this || this.walk().includes(x); },
    walk(out) {
      out = out || [];
      this.children.forEach((c) => { out.push(c); if (c.walk) { c.walk(out); } });
      return out;
    },
    querySelector(sel) { return this.querySelectorAll(sel)[0] || null; },
    querySelectorAll(sel) { return this.walk().filter((c) => matches(c, sel)); },
    focus() { doc.activeElement = this; }
  });
  doc.getElementById = (id) => doc.els[id] || null;
  doc.defaultView = { getComputedStyle: () => ({ getPropertyValue: () => size || "full" }) };
  return doc;
}

function mk(doc, tag, attrs, kids) {
  const n = doc.createElement(tag);
  Object.keys(attrs || {}).forEach((k) => {
    if (k === "class") { n.className = attrs[k]; } else if (k === "hidden") { n.hidden = !!attrs[k]; } else {
      n.setAttribute(k, attrs[k]);
    }
  });
  (kids || []).forEach((k) => n.appendChild(k));
  return n;
}

const listOf = (d, id) => d.getElementById(id).children[0].children[0]; // host > ul
const texts = (ul) => ul.children.map((li) => li.textContent);

/* The Characters card as web/index.html builds it. */
function charsCard(size) {
  const d = fakeDoc(size);
  mk(d, "section", { id: "charsbox", class: "card grid-card chars" }, [
    mk(d, "div", { class: "card-page", "data-page": "main" }, [
      mk(d, "p", { id: "char-pick-box", hidden: true }, [mk(d, "label", { for: "char-pick" }), mk(d, "select", { id: "char-pick" })]),
      mk(d, "p", { id: "chars-empty" }), mk(d, "div", { id: "chars-rows", hidden: true })])]);
  return d;
}

test("chars: one row per character, who is playing, level, deaths and best times", () => {
  assert.deepEqual(ch.charRows(SNAP).map((r) => r.text), [
    "Sable (playing now): Witch, level 4, 2 deaths",
    "Quill (not playing): Monk, level 20, 5 deaths",
    "Old (history only)"]);
  const timed = Object.assign({}, SNAP, { run_history: { on: true,
    best: [{ key: "G1", label: "Act 1", best_text: "20:00" }, { key: "G2", label: "Act 2", best_text: "15:00" }],
    by_character: { Old: { on: true, best: [{ key: "G1", label: "Act 1", best_text: "19:00" }] } } } });
  assert.deepEqual(ch.charRows(timed).map((r) => r.text), [
    "Sable (playing now): Witch, level 4, 2 deaths; best Act 1 20:00, Act 2 15:00",
    "Quill (not playing): Monk, level 20, 5 deaths",
    "Old (history only): best Act 1 19:00"]);
  const one = { characters: [{ name: "Solo", current: true, "class": "Monk", level: 1, deaths: 1 }] };
  assert.deepEqual(ch.charRows(one).map((r) => r.text), ["Solo (playing now): Monk, level 1, 1 death"]);
  assert.deepEqual(ch.charRows(null), []);
  assert.equal(ch.bestsText(null), "");
});

test("chars paint: the picker shows with 2+ characters, the rows page at 8 (6 compact)", () => {
  const d = charsCard();
  ch.paint(d, SNAP, "");
  assert.equal(d.getElementById("char-pick-box").hidden, false);
  const sel = d.getElementById("char-pick");
  assert.deepEqual(sel.children.map((o) => o.textContent), ["Sable (playing now)", "Quill", "Old"]);
  assert.deepEqual(sel.children.map((o) => o.value), ["", "Quill", "Old"]);
  assert.equal(sel.value, "");
  assert.equal(texts(listOf(d, "chars-rows")).length, 3);
  assert.equal(d.getElementById("chars-empty").hidden, true);
  ch.paint(d, SNAP, "Quill");
  assert.equal(sel.value, "Quill");
  // the player's change picks
  const picked = [];
  ch.wire(d, (name) => picked.push(name));
  sel.value = "Old";
  (sel.listeners.change || []).forEach((fn) => fn({ target: sel }));
  assert.deepEqual(picked, ["Old"]);
  // nobody yet: the sentence in place of the rows, no picker
  ch.paint(d, { characters: [], run_history: null }, "");
  assert.equal(d.getElementById("char-pick-box").hidden, true);
  assert.equal(d.getElementById("chars-rows").hidden, true);
  assert.equal(d.getElementById("chars-empty").hidden, false);
  // 12 names: 5 rows a page (4 compact; CP-1, the wrapped picker)
  const by = {};
  for (let i = 0; i < 12; i += 1) { by["C" + i] = { best: [] }; }
  ["full", "compact"].forEach((size) => {
    const c = charsCard(size);
    ch.paint(c, { characters: [], run_history: { by_character: by } }, "");
    assert.equal(listOf(c, "chars-rows").children.length, size === "full" ? 5 : 4, size);
  });
  assert.deepEqual(ch.ROWS, { full: 5, compact: 4 });
});

test("the Characters card in the markup: the picker and its rows, after Recent", () => {
  const html = web.source("index.html");
  const at = html.indexOf('id="charsbox"');
  const box = html.slice(at, html.indexOf("</section>", at));
  assert.match(box, /^id="charsbox" class="card grid-card chars"/);
  ["char-pick-box", "char-pick", "chars-empty"].forEach((id) => assert.ok(box.includes('id="' + id + '"'), id));
  assert.ok(box.includes('<label for="char-pick">Show numbers for</label>'));
  assert.ok(box.includes('id="chars-rows" class="pager-slot"'));
  assert.ok(html.indexOf('id="events-title"') < at);
  // the picker moved: one picker on the page
  assert.equal(html.split('id="char-pick"').length, 2);
});

/* RUN-CHARACTER-PIN (F-157): the 'This is my character' pin in the picker. */
test("chars pin: one click pins the shown character, a click on the pressed pin frees it", async () => {
  const d = charsCard();
  const calls = [];
  let reply = { character: "Sable", pinned: true };
  ch.wire(d, () => {}, (method, path, body) => { calls.push([method, path, body]); return Promise.resolve(reply); });
  ch.paint(d, SNAP, "");
  const pin = d.getElementById("char-pin");
  assert.ok(pin, "the pin is in the picker line");
  assert.equal(pin.parentNode, d.getElementById("char-pick-box"));
  // CP-1: DOM (= visual and Tab) order label, pin, select, failure line
  assert.deepEqual(d.getElementById("char-pick-box").children.map((c) => c.tagName + (c.getAttribute("id") ? "#" + c.getAttribute("id") : "")),
    ["LABEL", "BUTTON#char-pin", "SELECT#char-pick", "SPAN#char-pin-said"]);
  assert.equal(pin.tagName, "BUTTON");
  assert.equal(pin.getAttribute("type"), "button");
  assert.equal(pin.textContent, ch.PIN_LABEL);
  assert.equal(ch.PIN_LABEL, "This is my character");
  assert.equal(pin.getAttribute("aria-pressed"), "false");
  // one click: the character being played is pinned
  pin.click();
  await new Promise((r) => setImmediate(r));
  assert.deepEqual(calls, [["POST", "/api/character", { name: "Sable" }]]);
  assert.equal(pin.getAttribute("aria-pressed"), "true");
  // the next snapshot says pinned: pressed; a click frees it
  const pinned = Object.assign({}, SNAP, { character_pinned: true });
  ch.paint(d, pinned, "");
  assert.equal(pin.getAttribute("aria-pressed"), "true");
  reply = { character: "Sable", pinned: false };
  pin.click();
  await new Promise((r) => setImmediate(r));
  assert.deepEqual(calls[1], ["POST", "/api/character", { name: "" }]);
  assert.equal(pin.getAttribute("aria-pressed"), "false");
  // a picked character: the pin acts on that one, and is not pressed
  ch.paint(d, pinned, "Quill");
  assert.equal(pin.getAttribute("aria-pressed"), "false");
  reply = { character: "Quill", pinned: true };
  pin.click();
  await new Promise((r) => setImmediate(r));
  assert.deepEqual(calls[2], ["POST", "/api/character", { name: "Quill" }]);
  // one button only, however often the card paints
  ch.paint(d, pinned, "");
  assert.equal(d.getElementById("char-pick-box").querySelectorAll("button").length, 1);
});

test("chars pin: shows with one character, says a failed save, no picker with nobody", async () => {
  const d = charsCard();
  ch.wire(d, () => {}, () => Promise.reject(new Error("down")));
  const one = { character: "Solo", characters: [{ name: "Solo", current: true }] };
  ch.paint(d, one, "");
  assert.equal(d.getElementById("char-pick-box").hidden, false);
  const pin = d.getElementById("char-pin");
  assert.equal(pin.hidden, false);
  pin.click();
  await new Promise((r) => setImmediate(r));
  assert.equal(d.getElementById("char-pin-said").textContent, ch.PIN_FAILED);
  assert.equal(pin.getAttribute("aria-pressed"), "false");
  assert.equal(pin.getAttribute("aria-disabled"), "false");
  ch.paint(d, { characters: [], run_history: null }, "");
  assert.equal(d.getElementById("char-pick-box").hidden, true);
  assert.equal(ch.shownName(SNAP, "Old"), "Old");
  assert.equal(ch.shownName(SNAP, "Nobody"), "Sable");
  assert.equal(ch.pinPressed(Object.assign({}, SNAP, { character_pinned: true }), "Quill"), false);
});

/* CP-2 (RUN-CHARACTER-PIN design finding S3): a failed pin save keeps its
   muted line and is also said in the header's polite #tab-news through
   ALTabs.say (web/tabs.js, the page's one shared polite line). */
test("chars pin: a failed save is said on the header's polite line, a good one is not", async () => {
  const d = charsCard();
  const news = mk(d, "p", { id: "tab-news", role: "status", "aria-live": "polite" });
  let fail = true;
  ch.wire(d, () => {}, () => (fail ? Promise.reject(new Error("down"))
    : Promise.resolve({ character: "Sable", pinned: true })));
  ch.paint(d, SNAP, "");
  const pin = d.getElementById("char-pin");
  pin.click();
  assert.equal(news.textContent, "", "saving says nothing");
  await new Promise((r) => setImmediate(r));
  assert.equal(d.getElementById("char-pin-said").textContent, ch.PIN_FAILED);
  assert.equal(news.textContent, ch.PIN_FAILED);
  assert.equal(news.getAttribute("aria-live"), "polite");
  // the same failure again is said again (cleared, then written)
  pin.click();
  await new Promise((r) => setImmediate(r));
  assert.equal(news.textContent, ch.PIN_FAILED);
  // a save that works clears the muted line and says nothing new
  news.textContent = "";
  fail = false;
  pin.click();
  await new Promise((r) => setImmediate(r));
  assert.equal(d.getElementById("char-pin-said").textContent, "");
  assert.equal(news.textContent, "");
  assert.equal(pin.getAttribute("aria-pressed"), "true");
  // the throw arm (api() itself throws) is said too
  const d2 = charsCard();
  const n2 = mk(d2, "p", { id: "tab-news" });
  ch.wire(d2, () => {}, () => { throw new Error("x"); });
  ch.paint(d2, SNAP, "");
  d2.getElementById("char-pin").click();
  await new Promise((r) => setImmediate(r));
  assert.equal(n2.textContent, ch.PIN_FAILED);
  // a page with no header line: only the muted line, no error
  const d3 = charsCard();
  ch.wire(d3, () => {}, () => Promise.reject(new Error("down")));
  ch.paint(d3, SNAP, "");
  d3.getElementById("char-pin").click();
  await new Promise((r) => setImmediate(r));
  assert.equal(d3.getElementById("char-pin-said").textContent, ch.PIN_FAILED);
  // the words fit N6's 12-word cap
  assert.ok(ch.PIN_FAILED.split(/\s+/).length <= 12);
});
