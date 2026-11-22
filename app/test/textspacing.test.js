/* TD-22 text-spacing probe (web/textspacing.js, PLAY-TD-22A-A11Y-CSS; plan
   03 section 3.9, WCAG 2.2 SC 1.4.12): the root gets
   data-text-spacing="user" while the hidden reference row's box differs
   from the tokens, loses it when the row matches again, and re-checks only
   on a ResizeObserver event, never on a timer. A small fake DOM; no
   browser. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const T = web.load("textspacing.js");

const SRC = web.source("textspacing.js");
const CSS = web.source("app.css");

// the four WCAG 1.4.12 overrides at the body step (16 px)
const TOKENS = { height: 22, lineHeight: "22px", letterSpacing: "normal",
  wordSpacing: "0px", marginBottom: "0px" };
const OVERRIDES = { height: 24, lineHeight: "24px", letterSpacing: "1.92px",
  wordSpacing: "2.56px", marginBottom: "32px" };

function el(tag, doc) {
  return {
    tagName: tag.toUpperCase(), id: "", className: "", attrs: {}, children: [],
    _text: "",
    set textContent(v) { this._text = String(v); },
    get textContent() { return this._text; },
    setAttribute(k, v) { this.attrs[k] = String(v); if (this === doc.documentElement) { doc.writes += 1; } },
    getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
    removeAttribute(k) { delete this.attrs[k]; if (this === doc.documentElement) { doc.writes += 1; } },
    appendChild(c) { this.children.push(c); return c; }
  };
}

/* A page whose reference row measures `m` (changed by setBox) under a
   root of `rootPx` and the --al-lh-body token `token`. */
function fakePage(m, opts) {
  const o = opts || {};
  const doc = { writes: 0 };
  doc.documentElement = el("html", doc);
  doc.body = el("body", doc);
  doc.createElement = (tag) => el(tag, doc);
  doc.getElementById = (id) => doc.body.children.find((c) => c.id === id) || null;
  const state = { m: Object.assign({}, m), observers: [] };
  const view = {
    getComputedStyle(node) {
      if (node === doc.documentElement) {
        return { fontSize: o.rootPx || "16px",
          getPropertyValue: (n) => (n === "--al-lh-body" ? (o.token || " 1.375rem") : "") };
      }
      return state.m;
    }
  };
  if (o.ro !== false) {
    view.ResizeObserver = function (fn) {
      const ob = { fn, seen: [] };
      state.observers.push(ob);
      this.observe = (n) => { ob.seen.push(n); };
    };
  }
  doc.defaultView = view;
  // measure() reads the box from getBoundingClientRect
  const make = doc.createElement;
  doc.createElement = (tag) => {
    const n = make(tag);
    n.getBoundingClientRect = () => ({ height: state.m.height, width: 120 });
    return n;
  };
  function setBox(next) {
    state.m = Object.assign({}, next);
    state.observers.forEach((ob) => ob.fn([]));
  }
  return { doc, view, state, setBox };
}

test("the tokens are no difference, each of the four overrides is", () => {
  assert.equal(T.differs(TOKENS, 22), false);
  assert.equal(T.differs(Object.assign({}, TOKENS, { letterSpacing: "0px" }), 22), false);
  assert.equal(T.differs(Object.assign({}, TOKENS, { height: 22.4 }), 22), false, "sub-pixel");
  for (const k of ["lineHeight", "letterSpacing", "wordSpacing", "marginBottom"]) {
    const m = Object.assign({}, TOKENS, { [k]: OVERRIDES[k] });
    assert.equal(T.differs(m, 22), true, k);
  }
  assert.equal(T.differs(Object.assign({}, TOKENS, { height: 44 }), 22), true, "box height");
  assert.equal(T.differs(Object.assign({}, TOKENS, { lineHeight: "normal" }), 22), true);
  assert.equal(T.differs(TOKENS, NaN), false, "an unknown token never switches");
});

test("the token line box is rem times the root font size", () => {
  assert.equal(T.remPx(" 1.375rem", "16px"), 22);
  assert.equal(T.remPx("1.375rem", "20px"), 27.5);
  assert.ok(Number.isNaN(T.remPx("22px", "16px")));
  assert.ok(Number.isNaN(T.remPx("", "16px")));
});

test("the probe sets data-text-spacing=user when its box differs from the tokens", () => {
  const p = fakePage(OVERRIDES);
  const row = T.install(p.doc, p.view);
  assert.equal(p.doc.documentElement.getAttribute("data-text-spacing"), "user");
  assert.equal(row.id, "ts-probe");
  assert.equal(row.className, "ts-probe");
  assert.equal(row.getAttribute("aria-hidden"), "true");
  assert.match(row.textContent, / /, "the row has spaces, so word spacing moves it");
  assert.deepEqual(p.doc.body.children, [row]);
});

test("at the token values the root carries no attribute, and a resize re-checks", () => {
  const p = fakePage(TOKENS, { rootPx: "20px" });
  p.state.m.height = 27.5;
  p.state.m.lineHeight = "27.5px";
  T.install(p.doc, p.view);
  assert.equal(p.doc.documentElement.getAttribute("data-text-spacing"), null);
  assert.equal(p.doc.writes, 0, "nothing written on the root while it matches");
  assert.equal(p.state.observers.length, 1);
  p.setBox(Object.assign({}, OVERRIDES, { height: 30, lineHeight: "30px" }));
  assert.equal(p.doc.documentElement.getAttribute("data-text-spacing"), "user");
  const writes = p.doc.writes;
  p.setBox(Object.assign({}, OVERRIDES, { height: 31, lineHeight: "31px" }));
  assert.equal(p.doc.writes, writes, "the same answer is not written again");
  p.setBox(Object.assign({}, TOKENS, { height: 27.5, lineHeight: "27.5px" }));
  assert.equal(p.doc.documentElement.getAttribute("data-text-spacing"), null);
});

test("without a ResizeObserver it checks once; a second install reuses the row", () => {
  const p = fakePage(OVERRIDES, { ro: false });
  const a = T.install(p.doc, p.view);
  const b = T.probe(p.doc);
  assert.equal(a, b);
  assert.equal(p.doc.body.children.length, 1);
  assert.equal(p.doc.documentElement.getAttribute("data-text-spacing"), "user");
  assert.equal(T.install({}, p.view), null, "no body, no probe");
  assert.equal(T.check(p.doc, null, a), null);
});

test("wire runs through the region registry with the page's own view", () => {
  assert.equal(T.spec.name, "textspacing");
  assert.equal(T.spec.region, null);
  const p = fakePage(OVERRIDES);
  T.spec.wire(p.doc, {});
  assert.equal(p.doc.documentElement.getAttribute("data-text-spacing"), "user");
});

test("an event, never a timer; no network, clipboard or live region", () => {
  const code = SRC.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
  for (const bad of ["setTimeout", "setInterval", "requestAnimationFrame", "fetch(",
    "XMLHttpRequest", "clipboard", "aria-live", ".focus("]) {
    assert.ok(!code.includes(bad), bad);
  }
  assert.match(code, /new RO\(run\)/);
  assert.doesNotMatch(SRC, /[^\x0a\x20-\x7e]/, "ASCII and LF");
});

test("app.css styles the probe at the body token and wraps rows under user", () => {
  const css = CSS.replace(/\/\*[\s\S]*?\*\//g, "");
  const probe = /\.ts-probe \{([^}]*)\}/.exec(css);
  assert.ok(probe, ".ts-probe rule");
  for (const decl of ["position: absolute", "font-size: var(--al-fs-body)",
    "line-height: var(--al-lh-body)", "white-space: nowrap", "visibility: hidden"]) {
    assert.ok(probe[1].includes(decl), decl);
  }
  assert.match(css, /\[data-text-spacing="user"\] \.one-line \{ white-space: normal; overflow: visible; \}/);
  assert.match(css, /\[data-text-spacing="user"\] \.panel-grid > \.col \{ max-height: none; overflow: visible; \}/);
  assert.match(css, /:root:not\(\[data-text-spacing="user"\]\) body:not\(:has\(#panel-play:not\(\[hidden\]\)\)\) \{ height: 100vh; \}/);
});
