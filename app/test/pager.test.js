/* TD-19 pager (web/pager.js, PLAY-TD-19A-PAGER): 23 rows page as 1-10 of
   23 with Prev / Next (8 a page compact), the Full text page holds 3
   entries of up to 3 wrapped lines (2 x 4 compact), a page changes only on
   a press, and focus stays on the pressed button. A small fake DOM; no
   browser, no timers. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const P = require("../../web/pager.js");

const SRC = fs.readFileSync(path.join(__dirname, "..", "..", "web", "pager.js"), "utf8");

function fakeDoc() {
  const doc = { activeElement: null, created: 0 };
  doc.createElement = (tag) => {
    doc.created += 1;
    const n = {
      tagName: tag.toUpperCase(), className: "", hidden: false, children: [],
      parentNode: null, attrs: {}, listeners: {}, _text: "",
      get firstChild() { return this.children[0] || null; },
      get textContent() { return this._text + this.children.map((c) => c.textContent).join(""); },
      set textContent(v) { this.children = []; this._text = String(v); },
      appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
      removeChild(c) {
        this.children = this.children.filter((x) => x !== c);
        c.parentNode = null;
        if (doc.activeElement === c) { doc.activeElement = null; }
        return c;
      },
      setAttribute(k, v) { this.attrs[k] = String(v); },
      getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
      removeAttribute(k) { delete this.attrs[k]; },
      addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
      focus() { doc.activeElement = this; },
      click() { (this.listeners.click || []).forEach((fn) => fn({ target: this })); }
    };
    return n;
  };
  return doc;
}

const rows23 = Array.from({ length: 23 }, (_, i) => "row " + (i + 1));
const texts = (pg) => pg.list.children.map((li) => li.textContent);

test("page(): 23 rows page as 1-10 of 23, 8 a page compact", () => {
  let p = P.page(rows23, P.LIST_ROWS.full, 0);
  assert.equal(P.LIST_ROWS.full, 10);
  assert.equal(P.LIST_ROWS.compact, 8);
  assert.equal(p.label, "1-10 of 23");
  assert.deepEqual([p.pages, p.from, p.to, p.hasPrev, p.hasNext], [3, 1, 10, false, true]);
  p = P.page(rows23, 10, 2);
  assert.equal(p.label, "21-23 of 23");
  assert.equal(p.items.length, 3);
  assert.equal(p.hasNext, false);
  assert.equal(P.page(rows23, 10, 99).index, 2, "index clamps to the last page");
  assert.equal(P.page(rows23, 10, -4).index, 0);
  p = P.page(rows23, P.LIST_ROWS.compact, 1);
  assert.equal(p.label, "9-16 of 23");
  assert.equal(p.pages, 3);
  assert.equal(P.page(rows23.slice(0, 10), 10, 0).label, "", "one page needs no count");
  const empty = P.page([], 10, 3);
  assert.deepEqual([empty.pages, empty.index, empty.from, empty.to, empty.items.length], [1, 0, 0, 0, 0]);
  assert.equal(P.page(null, 10, 0).total, 0);
});

test("the line arithmetic of section 4 holds", () => {
  assert.equal(P.ROW_PX, 22);
  assert.equal(P.PAGER_PX, 28);
  assert.deepEqual(P.TEXT.full, { entries: 3, lines: 3, cols: 47 });
  assert.deepEqual(P.TEXT.compact, { entries: 2, lines: 4, cols: 37 });
  // card: border 2 + padding 24 + title 26 + rows + pager row, in 322 (full) / 292 (compact)
  assert.equal(2 + 24 + 26 + P.LIST_ROWS.full * P.ROW_PX + P.PAGER_PX, 300);
  assert.equal(2 + 24 + 26 + P.LIST_ROWS.compact * P.ROW_PX + P.PAGER_PX, 256);
  assert.ok(P.TEXT.full.entries * P.TEXT.full.lines * P.ROW_PX <= P.LIST_ROWS.full * P.ROW_PX);
  assert.ok(P.TEXT.compact.entries * P.TEXT.compact.lines * P.ROW_PX <= P.LIST_ROWS.compact * P.ROW_PX);
});

test("wrap(): a 120 character string fits 3 x 47 and 4 x 37 lines", () => {
  const words = "Lightning resistance on the boots would cap you for act four bosses, swap the ring with cold".split(" ");
  let s = "";
  for (let i = 0; s.length < 120; i++) { s += (s ? " " : "") + words[i % words.length]; }
  s = s.slice(0, 120);
  for (const k of ["full", "compact"]) {
    const t = P.TEXT[k];
    const lines = P.wrap(s, t.cols, t.lines);
    assert.ok(lines.length <= t.lines, k + " lines");
    lines.forEach((l) => assert.ok(l.length <= t.cols, k + " width: " + l));
    assert.ok(!lines[lines.length - 1].endsWith("..."), k + " nothing cut");
    assert.equal(lines.join(" "), s.replace(/\s+/g, " ").trim());
  }
  const long = P.wrap("x".repeat(200), 47, 3);
  assert.equal(long.length, 3);
  assert.ok(long[2].endsWith("..."));
  assert.ok(long.every((l) => l.length <= 47));
  assert.deepEqual(P.wrap("", 47, 3), []);
});

test("rowRule(): one line, the ellipsis class, the full text in title", () => {
  const doc = fakeDoc();
  const li = P.rowRule(doc.createElement("li"), "A very long unique item name");
  assert.equal(li.className, P.CLS.row);
  assert.equal(li.textContent, "A very long unique item name");
  assert.equal(li.getAttribute("title"), "A very long unique item name");
});

test("build(): list pages with Prev / Next and the count", () => {
  const doc = fakeDoc();
  const pg = P.build(doc, { rows: rows23, label: "Prices" });
  assert.equal(pg.node.children[0], pg.list);
  assert.equal(pg.node.children[1], pg.bar);
  assert.equal(pg.count.textContent, "1-10 of 23");
  assert.deepEqual(texts(pg), rows23.slice(0, 10));
  pg.list.children.forEach((li) => {
    assert.equal(li.className, P.CLS.row);
    assert.equal(li.getAttribute("title"), li.textContent);
  });
  assert.equal(pg.prev.textContent, "Prev");
  assert.equal(pg.next.textContent, "Next");
  assert.equal(pg.toggle.textContent, "Full text");
  assert.equal(pg.prev.getAttribute("type"), "button");
  assert.equal(pg.prev.getAttribute("aria-disabled"), "true");
  pg.next.click();
  assert.equal(pg.count.textContent, "11-20 of 23");
  assert.equal(pg.prev.getAttribute("aria-disabled"), null);
  pg.next.click();
  assert.equal(pg.count.textContent, "21-23 of 23");
  assert.equal(pg.next.getAttribute("aria-disabled"), "true");
  pg.next.click(); // an end button does nothing
  assert.equal(pg.count.textContent, "21-23 of 23");
  pg.prev.click();
  assert.equal(pg.count.textContent, "11-20 of 23");
  const small = P.build(fakeDoc(), { rows: ["a", "b"] });
  assert.equal(small.count.textContent, "");
  assert.equal(small.prev.hidden, true);
  assert.equal(small.next.hidden, true);
  assert.equal(small.toggle.hidden, false, "the switch is always there");
});

test("build(): 8 rows a page in the compact class", () => {
  let k = "compact";
  const pg = P.build(fakeDoc(), { rows: rows23, sizeClass: () => k });
  assert.equal(pg.count.textContent, "1-8 of 23");
  assert.equal(pg.list.children.length, 8);
  pg.next.click();
  assert.equal(pg.count.textContent, "9-16 of 23");
  k = "flow"; // anything else counts as full
  pg.render();
  assert.equal(pg.count.textContent, "11-20 of 23");
});

test("the Full text page: 3 entries of up to 3 lines, 2 x 4 compact", () => {
  const long = Array.from({ length: 7 }, (_, i) =>
    "Entry " + (i + 1) + " " + "with a long reason that needs more than one line ".repeat(2).trim());
  for (const [k, t] of [["full", P.TEXT.full], ["compact", P.TEXT.compact]]) {
    const pg = P.build(fakeDoc(), { rows: long, sizeClass: k });
    pg.toggle.click();
    assert.equal(pg.toggle.textContent, "List");
    assert.equal(pg.state().mode, "text");
    assert.ok(pg.list.className.includes(P.CLS.text));
    assert.equal(pg.list.children.length, t.entries, k + " entries");
    pg.list.children.forEach((li, i) => {
      assert.equal(li.className, P.CLS.entry);
      assert.equal(li.getAttribute("title"), long[i]);
      assert.ok(li.children.length >= 2 && li.children.length <= t.lines, k + " lines " + li.children.length);
      li.children.forEach((line) => assert.ok(line.textContent.length <= t.cols));
    });
    assert.equal(pg.count.textContent, "1-" + t.entries + " of 7");
    pg.toggle.click();
    assert.equal(pg.toggle.textContent, "Full text");
    assert.ok(pg.list.children.every((li) => li.className === P.CLS.row));
  }
});

test("the switch keeps the first shown row in view", () => {
  const pg = P.build(fakeDoc(), { rows: rows23 });
  pg.next.click(); // rows 11-20
  pg.toggle.click(); // Full text page holding row 11
  assert.equal(pg.count.textContent, "10-12 of 23");
  pg.next.click(); // 13-15
  pg.toggle.click(); // back to the list page holding row 13
  assert.equal(pg.count.textContent, "11-20 of 23");
});

test("a page changes only on a press", () => {
  assert.doesNotMatch(SRC, /setTimeout|setInterval|requestAnimationFrame|aria-live|fetch\(|navigator\.clipboard/);
  const pg = P.build(fakeDoc(), { rows: rows23 });
  pg.next.click();
  for (let i = 0; i < 5; i++) { pg.render(); }
  assert.equal(pg.count.textContent, "11-20 of 23", "a render never advances");
  pg.set(rows23.concat(["row 24", "row 25"]));
  assert.equal(pg.count.textContent, "11-20 of 25", "new data keeps the page");
  pg.set(rows23.slice(0, 12));
  assert.equal(pg.count.textContent, "11-12 of 12");
  pg.set(rows23.slice(0, 4));
  assert.equal(pg.count.textContent, "", "clamped to the one page left");
  assert.deepEqual(texts(pg), rows23.slice(0, 4));
  pg.press("bogus");
  assert.deepEqual(texts(pg), rows23.slice(0, 4));
});

test("focus stays on the pressed button", () => {
  const doc = fakeDoc();
  const pg = P.build(doc, { rows: rows23 });
  const kids = pg.bar.children.slice();
  for (const b of [pg.next, pg.next, pg.next, pg.prev, pg.toggle, pg.next, pg.toggle, pg.prev, pg.prev]) {
    b.focus();
    b.click();
    assert.equal(doc.activeElement, b);
    assert.equal(b.parentNode, pg.bar);
    assert.equal(b.hidden, false);
    assert.equal(b.getAttribute("disabled"), null, "never disabled: that would drop focus");
  }
  assert.deepEqual(pg.bar.children, kids, "the bar's buttons are never re-created");
});

test("UMD, ASCII and LF, no inline style", () => {
  assert.match(SRC, /module\.exports = api;/);
  assert.match(SRC, /root\.ALPager = api;/);
  assert.doesNotMatch(SRC, /[^\x0a\x20-\x7e]/);
  assert.doesNotMatch(SRC, /\.style\b|innerHTML/);
});
