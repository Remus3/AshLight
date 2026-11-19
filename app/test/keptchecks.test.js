/* PLAY-TD-16B-KEPT-CHECKS (web/keptchecks.js): region U lists the best
   checks of this session from snap.play.kept through ALSlots.keptChecks,
   3 rows in the full class, 1 in compact, one muted line when empty, and
   re-orders by itself on the next state push after a build change. No
   button, no live region, never ALTabs.notify, never a clipboard read. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const KC = require("../../web/keptchecks.js");
const R = require("../../web/regions.js");

const WEB = path.join(__dirname, "..", "..", "web");
const SRC = fs.readFileSync(path.join(WEB, "keptchecks.js"), "utf8");
const CSS = fs.readFileSync(path.join(WEB, "keptchecks.css"), "utf8");
const HTML = fs.readFileSync(path.join(WEB, "index.html"), "utf8");
const CAP_KEPT = 42;

/* A small DOM: ids, parents, children, attributes, hidden; the size class
   is the computed --al-size-class of the root. */
function makeDoc(cls) {
  const doc = { all: [], cls: cls || "full" };
  function elem(tag) {
    const n = {
      tagName: tag.toUpperCase(), attrs: {}, children: [], parentNode: null,
      hidden: false, textContent: "", writes: 0,
      get id() { return this.attrs.id || ""; },
      set id(v) { this.attrs.id = String(v); },
      get className() { return this.attrs.class || ""; },
      set className(v) { this.attrs.class = String(v); },
      getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
      setAttribute(k, v) { this.attrs[k] = String(v); },
      appendChild(c) { c.parentNode = this; this.children.push(c); return c; }
    };
    doc.all.push(n);
    return n;
  }
  doc.createElement = elem;
  doc.documentElement = elem("html");
  doc.defaultView = {
    listeners: {},
    addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
    getComputedStyle: () => ({ getPropertyValue: (k) => (k === "--al-size-class" ? " " + doc.cls : "") })
  };
  const region = elem("section");
  region.setAttribute("data-region", "u");
  doc.slot = region.appendChild(elem("div"));
  doc.slot.setAttribute("data-slot", "u");
  doc.region = region;
  doc.querySelector = (sel) => {
    assert.equal(sel, '#play-u [data-slot="u"]');
    return doc.slot;
  };
  doc.querySelectorAll = (sel) => {
    const m = /^\[([a-z-]+)\]$/.exec(sel);
    return m ? doc.all.filter((n) => n.getAttribute(m[1]) !== null) : [];
  };
  return doc;
}

function row(name, gain, slot, at) {
  const text = "[+] Upgrade " + gain + ", " + name + ", " + slot + ", 10:4" + (at % 10);
  return { glyph: "[+]", word: "Upgrade", gain, item: name, slot, at,
           text: text.slice(0, CAP_KEPT), full: "Upgrade " + gain + ": " + name + ", " + slot };
}

const ROWS = [row("Storm Staff", "+12%", "Weapon", 3), row("Iron Ring", "+6%", "Ring", 1),
              row("Leather Belt", "+2%", "Belt", 2)];

function snapWith(rows, extra) {
  return Object.assign({ build: { loaded: true },
                         play: { kept: { rows, empty: rows.length ? "" : "None of your checks is an upgrade now.",
                                         checked: rows.length } } }, extra || {});
}

function shown(doc) {
  const kc = doc.slot.children[0];
  const list = kc.children[1];
  return list.hidden ? [] : list.children.filter((li) => !li.hidden).map((li) => li.textContent);
}

function emptyLine(doc) {
  const e = doc.slot.children[0].children[2];
  return e.hidden ? null : e.textContent;
}

test("spec registers region u with no legacy group", () => {
  assert.equal(KC.spec.name, "keptchecks");
  assert.equal(KC.spec.region, "u");
  assert.deepEqual(KC.spec.retires, []);
  const reg = R.create({ warn: () => {} });
  reg.register(KC.spec);
  assert.deepEqual(reg.names(), ["keptchecks"]);
});

test("full class: label and the 3 rows best first, full text in title", () => {
  KC.reset();
  const doc = makeDoc("full");
  KC.wire(doc);
  KC.paint(doc, snapWith(ROWS));
  const kc = doc.slot.children[0];
  assert.equal(kc.children[0].textContent, "Best checks");
  assert.deepEqual(shown(doc), ROWS.map((r) => r.text));
  assert.equal(kc.children[1].children[0].getAttribute("title"), ROWS[0].full);
  assert.equal(emptyLine(doc), null);
  assert.equal(kc.getAttribute("data-rows"), "3");
  for (const t of shown(doc)) { assert.ok(t.length <= CAP_KEPT, t); }
});

test("compact class keeps the best row only", () => {
  KC.reset();
  const doc = makeDoc("compact");
  KC.paint(doc, snapWith(ROWS));
  assert.deepEqual(shown(doc), [ROWS[0].text]);
  // a resize to full repaints on the next tick, no push needed
  doc.cls = "full";
  KC.tick(doc);
  assert.equal(shown(doc).length, 3);
});

test("a resize that changes the size class repaints at once", () => {
  KC.reset();
  const doc = makeDoc("full");
  KC.wire(doc);
  KC.wire(doc);
  assert.equal(doc.defaultView.listeners.resize.length, 1, "one listener");
  KC.paint(doc, snapWith(ROWS));
  assert.equal(shown(doc).length, 3);
  doc.cls = "compact";
  doc.defaultView.listeners.resize.forEach((fn) => fn());
  assert.deepEqual(shown(doc), [ROWS[0].text]);
});

test("a build change re-orders the rows from the next state push", () => {
  KC.reset();
  const doc = makeDoc("full");
  KC.paint(doc, snapWith(ROWS));
  const next = [ROWS[2], ROWS[0]];
  KC.spec.paint(doc, snapWith(next));
  assert.deepEqual(shown(doc), next.map((r) => r.text));
  assert.equal(doc.slot.children.length, 1, "the nodes are made once");
});

test("empty: one muted line, the core's text first", () => {
  KC.reset();
  const doc = makeDoc("full");
  KC.paint(doc, snapWith([]));
  assert.deepEqual(shown(doc), []);
  assert.equal(emptyLine(doc), "None of your checks is an upgrade now.");
  const e = doc.slot.children[0].children[2];
  assert.match(e.className, /\bmuted\b/);
  KC.paint(doc, { build: { loaded: false },
                  play: { kept: { rows: [], empty: "Load a build to rank your checks.", checked: 0 } } });
  assert.equal(emptyLine(doc), "Load a build to rank your checks.");
  // play.kept is null before BUILD-LIVE has a list
  KC.paint(doc, { play: { kept: null } });
  assert.equal(emptyLine(doc), KC.EMPTY_NONE);
  KC.paint(doc, null);
  assert.equal(emptyLine(doc), KC.EMPTY_NONE);
});

test("model goes through ALSlots.keptChecks: no loaded build, no rows", () => {
  assert.deepEqual(KC.model(snapWith(ROWS, { build: { loaded: false } }), "full").rows, []);
  assert.equal(KC.model(snapWith(ROWS), "flow").rows.length, 3);
  assert.equal(KC.model(snapWith(ROWS), "compact").rows.length, 1);
  assert.match(SRC, /Slots\.keptChecks\(/);
});

test("no size class style reads as flow", () => {
  assert.equal(KC.sizeClassOf({}), "flow");
  assert.equal(KC.sizeClassOf(makeDoc("compact")), "compact");
});

test("floor: no control, no live region, no notify, no clipboard, no timer, no network", () => {
  const code = SRC.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  assert.doesNotMatch(code, /ALTabs|notify\(/);
  assert.doesNotMatch(code, /clipboard|setInterval|setTimeout|fetch\(|XMLHttpRequest|aria-live/);
  assert.doesNotMatch(code, /el\(doc, "(button|a|input)"/);
});

test("page wiring: pre-linked files, the U section and its slot", () => {
  assert.match(HTML, /<link rel="stylesheet" href="\/web\/keptchecks\.css">/);
  assert.match(HTML, /<script src="\/web\/keptchecks\.js" defer><\/script>/);
  assert.ok(HTML.indexOf("/web/slots.js") < HTML.indexOf("/web/keptchecks.js"));
  assert.match(HTML, /id="play-u"[^>]*data-region="u"/);
  assert.match(HTML, /data-slot="u"/);
});

test("css: meta rows, no margins, the label at 600", () => {
  assert.match(SRC, /kc-row row-meta one-line/);
  assert.match(SRC, /kc-label row-meta one-line/);
  assert.match(CSS, /\.kc-label \{[^}]*font-weight: 600/);
  assert.match(CSS, /\.kc-list \{[^}]*margin: 0; padding: 0; list-style: none/);
  assert.doesNotMatch(CSS, /font-size/);
  assert.ok(/^[\x00-\x7f]*$/.test(SRC + CSS));
});
