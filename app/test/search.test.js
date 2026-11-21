"use strict";
/* UTIL-SEARCHSTR: the search string card (web/search.js). The core builds
   every string; this lists them and copies only on a click. Fixture values
   are invented. PLAY-TD-19C-BUILD-GRID: the card is a fixed card of the
   Build and items grid; its list pages (rowPager) instead of growing. */
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const s = web.load("search.js");
const P = web.load("pager.js");

const DOC = { loaded: true, search_strings: [
  { id: "resists", label: "Resistances you still need", why: "Finds gear.",
    text: "\"cold res|chaos res\"", terms: 2, dropped: 0 },
  { id: "bases", label: "Your gear bases", why: "", text: "\"a|b\"", terms: 2, dropped: 3 },
  { id: "junk", label: 5, text: "" }] };

/* a small fake DOM: enough for the pagers (no browser, no timers) */
function fakeDoc(ids) {
  const doc = { activeElement: null, selected: null };
  doc.createElement = (tag) => {
    const n = {
      tagName: tag.toUpperCase(), className: "", hidden: false, children: [], dataset: {},
      parentNode: null, attrs: {}, listeners: {}, _text: "",
      get firstChild() { return this.children[0] || null; },
      get textContent() { return this._text + this.children.map((c) => c.textContent).join(""); },
      set textContent(v) { this.children = []; this._text = String(v); },
      appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
      removeChild(c) { this.children = this.children.filter((x) => x !== c); return c; },
      replaceChildren(...kids) { this.children = []; this._text = ""; kids.forEach((k) => this.appendChild(k)); },
      setAttribute(k, v) { this.attrs[k] = String(v); },
      getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
      removeAttribute(k) { delete this.attrs[k]; },
      addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
      click() { (this.listeners.click || []).forEach((fn) => fn({ target: this })); },
      walk(out) {
        out = out || [];
        this.children.forEach((c) => { out.push(c); if (c.walk) { c.walk(out); } });
        return out;
      },
      querySelector(sel) { return this.querySelectorAll(sel)[0] || null; },
      querySelectorAll(sel) {
        return this.walk().filter((c) => (sel === "[data-copy]" ? "data-copy" in c.attrs
          : sel === ".al-row-txt" ? c.className === "al-row-txt" : false));
      },
      focus() { doc.activeElement = this; }
    };
    return n;
  };
  doc.getSelection = () => ({ removeAllRanges() {}, addRange(r) { doc.selected = r.node; } });
  doc.createRange = () => ({ selectNodeContents(n) { this.node = n; } });
  doc.els = {};
  (ids || []).forEach((id) => { doc.els[id] = doc.createElement("div"); });
  doc.getElementById = (id) => doc.els[id] || null;
  return doc;
}

const rowsOf = (pg) => pg.list.children;

test("view lists strings with text only and says what was left out", () => {
  const rows = s.view(DOC);
  assert.equal(rows.length, 2);
  assert.equal(rows[0].label, "Resistances you still need");
  assert.equal(rows[0].note, "");
  assert.equal(rows[1].note, "Shortened to fit the search box: 3 terms left out.");
  assert.deepEqual(s.view(null), []);
  assert.deepEqual(s.view({ loaded: false, search_strings: DOC.search_strings }), []);
  assert.deepEqual(s.view({ loaded: true, search_strings: "x" }), []);
});

test("copy writes only through the clipboard API it is handed", async () => {
  const wrote = [];
  const nav = { clipboard: { writeText: (t) => { wrote.push(t); return Promise.resolve(); } } };
  await new Promise((done) => s.copy("\"x\"", nav, done, () => assert.fail("no fallback")));
  assert.deepEqual(wrote, ["\"x\""]);
  let fell = false;
  s.copy("y", {}, () => assert.fail("no clipboard"), () => { fell = true; });
  assert.ok(fell);
});

test("the clipboard is written only inside a click handler", () => {
  const src = web.source("search.js", "ascii");
  assert.equal(src.split("copy(text, nav, function").length - 1, 1);
  const at = src.indexOf("copy(text, nav, function");
  assert.ok(src.lastIndexOf("addEventListener(\"click\"", at) > src.lastIndexOf("function copyButton", at));
  assert.ok(src.lastIndexOf("function copyButton", at) > 0);
  assert.equal(src.split("writeText(").length - 1, 1);
  assert.ok(!/setInterval|setTimeout|fetch\(|XMLHttpRequest|aria-live/.test(src));
});

test("a Copy click says the outcome on the button only, the last one clicked", async () => {
  const doc = fakeDoc(["searchbox", "search-list"]);
  const nav = { clipboard: { writeText: () => Promise.resolve() } };
  s.paint(doc, DOC, nav);
  const list = doc.els["search-list"].children[0].children[0];
  const [a, b] = rowsOf({ list }).map((li) => li.children[1]);
  assert.equal(a.textContent, "Copy");
  assert.equal(a.attrs["aria-label"], "Copy Resistances you still need search string");
  a.click();
  await new Promise((r) => setImmediate(r));
  assert.equal(a.textContent, "Copied");
  assert.equal(a.attrs.title, s.COPIED);
  assert.equal(a.attrs["aria-label"], "Copy Resistances you still need search string (copied)");
  b.click();
  await new Promise((r) => setImmediate(r));
  assert.equal(a.textContent, "Copy", "only the last clicked button says anything");
  assert.equal(b.textContent, "Copied");
});

test("a refused clipboard selects the string so Ctrl+C copies it", async () => {
  const doc = fakeDoc(["searchbox", "search-list"]);
  s.paint(doc, DOC, {});
  const li = doc.els["search-list"].children[0].children[0].children[0];
  li.children[1].click();
  await new Promise((r) => setImmediate(r));
  assert.equal(li.children[1].textContent, "Press Ctrl+C");
  assert.equal(doc.selected.textContent, "\"cold res|chaos res\"");
});

test("PLAY-TD-19C-BUILD-GRID: the card always shows; with no build it says so in one row", () => {
  const doc = fakeDoc(["searchbox", "search-list"]);
  doc.els.searchbox.hidden = true;
  s.paint(doc, null, {});
  assert.equal(doc.els.searchbox.hidden, false);
  const list = doc.els["search-list"].children[0].children[0];
  assert.deepEqual(list.children.map((li) => li.textContent), [s.EMPTY]);
  s.paint(doc, { loaded: true, search_strings: [] }, {});
  assert.deepEqual(list.children.map((li) => li.textContent), [s.NONE]);
});

test("PLAY-TD-19C-BUILD-GRID: strings page at 7 (5 compact), one line each with the full text", () => {
  const many = { loaded: true, search_strings: Array.from({ length: 12 }, (_, i) => ({
    id: "s" + i, label: "String " + i, text: "\"term " + i + "\"" })) };
  const doc = fakeDoc(["searchbox", "search-list"]);
  s.paint(doc, many, {});
  const host = doc.els["search-list"].children[0];
  const [list, bar] = host.children;
  assert.equal(host.className, P.CLS.host);
  assert.equal(list.children.length, s.SIZE.full);
  assert.equal(bar.children[0].textContent, "1-7 of 12");
  const row = list.children[0];
  assert.equal(row.className, "al-row-ctl");
  assert.equal(row.children[0].className, P.CLS.row);
  assert.equal(row.children[0].attrs.title, "String 0: \"term 0\"");
  bar.children[2].click(); // Next
  assert.equal(bar.children[0].textContent, "8-12 of 12");
  assert.equal(list.children.length, 5);
  s.paint(doc, many, {}); // a data change keeps the page
  assert.equal(bar.children[0].textContent, "8-12 of 12");
});

test("rowPager: compact size, Full text entries that fit a smaller block", () => {
  const doc = fakeDoc([]);
  const rows = Array.from({ length: 9 }, (_, i) => ({ t: "row " + i }));
  const pg = s.rowPager(doc, { rows, label: "things", size: { full: 4, compact: 2 },
    sizeClass: "compact", text: (r) => r.t,
    controls: (d) => { const b = d.createElement("button"); b.textContent = "Go"; return [b]; } });
  assert.equal(pg.state().items.length, 2);
  assert.equal(pg.count.textContent, "1-2 of 9");
  assert.equal(pg.prev.attrs["aria-disabled"], "true");
  pg.press("toggle");
  // 2 control rows of 24 px = 48 px: one entry of 2 lines (2 x 22 = 44)
  assert.equal(pg.state().mode, "text");
  assert.equal(pg.list.children.length, 1);
  assert.equal(pg.list.children[0].className, P.CLS.entry);
  assert.equal(pg.toggle.textContent, "List");
  const twelve = Array.from({ length: 12 }, (_, i) => ({ t: "row " + i }));
  const big = s.rowPager(doc, { rows: twelve, label: "big", text: (r) => r.t, sizeClass: "full" });
  assert.equal(big.state().items.length, P.LIST_ROWS.full);
  big.press("toggle");
  assert.equal(big.list.children.length, P.TEXT.full.entries);
});

test("the page keeps the card markup: no live region, filter page, intro words", () => {
  const html = web.source("index.html", "ascii");
  const card = html.split("id=\"searchbox\"")[1].split("</section>")[0];
  assert.ok(card.indexOf("aria-live") < 0 && card.indexOf("role=\"status\"") < 0);
  assert.match(html, /<section id="searchbox" class="card search grid-card"[^>]*>/);
  assert.doesNotMatch(card.split(">")[0], /hidden/);
  assert.match(card, /class="card-page" data-page="main"/);
  assert.match(card, /data-card-open="filter"/);
  assert.match(card, /<details id="filter-more" class="card-page tool-page" data-page="filter"[^>]*open hidden>/);
  assert.match(card, />Copy one, paste it in game\.</);
});
