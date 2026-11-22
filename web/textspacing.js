/* AshLight dashboard: the text-spacing probe (PLAY-TD-22A-A11Y-CSS; TD-22,
   plan 03 section 3.9, WCAG 2.2 SC 1.4.12).

   Composed rows fit one line at the token sizes, even under the four
   text-spacing overrides; a name or any other user style may not. So the
   page keeps one hidden reference row (p#ts-probe.ts-probe, the body step
   of web/app.css, aria-hidden, out of the flow) and compares its box with
   the tokens: its height and computed line height against --al-lh-body
   (rem times the root font size), and its letter spacing, word spacing
   and bottom margin against zero. While any of them differs, the root
   carries data-text-spacing="user" and web/app.css wraps the rows, turns
   the tracks into minimums and lets the page scroll; when they match
   again the attribute goes. Zoom moves the root and the token together,
   so it never counts.

   A ResizeObserver on the reference row re-checks when its box changes
   (an event, never a timer); with no ResizeObserver it checks once at
   wire time. No network, no clipboard, no live region, no focus move.

   Registers {name: textspacing, region: null} with web/regions.js (a
   helper, like the pager). UMD like web/tabs.js: CommonJS for node --test,
   window.ALTextSpacing in the page. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALTextSpacing = api;
    if (root.ALRegions && typeof root.ALRegions.register === "function") {
      root.ALRegions.register(api.spec);
    }
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var NAME = "textspacing";
  var ATTR = "data-text-spacing";
  var USER = "user";
  var PROBE_ID = "ts-probe";
  var PROBE_CLASS = "ts-probe";
  // spaces in it, so a word-spacing override moves its box too
  var PROBE_TEXT = "Act 1 zone level 12";
  var LINE_TOKEN = "--al-lh-body";
  var SLACK = 0.5; // px: sub-pixel rounding is not a user style

  function isFn(v) { return typeof v === "function"; }

  /* A CSS length in px ("22px" -> 22); NaN when it is not one. */
  function px(v) {
    var m = /^\s*(-?[\d.]+)px\s*$/.exec(typeof v === "string" ? v : "");
    return m ? parseFloat(m[1]) : NaN;
  }

  /* letter-spacing / word-spacing: "normal" and "" are 0. */
  function spacing(v) {
    if (v === "normal" || v === "" || v === undefined || v === null) { return 0; }
    return px(v);
  }

  /* The line-box token in px: "1.375rem" at a 16px root -> 22. */
  function remPx(token, rootPx) {
    var m = /^\s*([\d.]+)rem\s*$/.exec(typeof token === "string" ? token : "");
    var r = px(rootPx);
    return m && isFinite(r) ? parseFloat(m[1]) * r : NaN;
  }

  function off(a, b) { return !(isFinite(a) && isFinite(b)) || Math.abs(a - b) > SLACK; }

  /* m = {height, lineHeight, letterSpacing, wordSpacing, marginBottom}
     (height a number, the rest computed style strings); line = the token
     line box in px. True when the reference row is not what the tokens
     say; an unknown line (NaN) is never a difference. */
  function differs(m, line) {
    if (!m || !isFinite(line)) { return false; }
    if (off(m.height, line)) { return true; }
    if (off(px(m.lineHeight), line)) { return true; }
    if (spacing(m.letterSpacing) !== 0 || spacing(m.wordSpacing) !== 0) { return true; }
    return px(m.marginBottom) !== 0;
  }

  function measure(el, view) {
    var cs = view.getComputedStyle(el);
    var box = el.getBoundingClientRect();
    return {
      height: box.height, lineHeight: cs.lineHeight, letterSpacing: cs.letterSpacing,
      wordSpacing: cs.wordSpacing, marginBottom: cs.marginBottom
    };
  }

  function lineToken(doc, view) {
    var cs = view.getComputedStyle(doc.documentElement);
    return remPx(cs.getPropertyValue(LINE_TOKEN), cs.fontSize);
  }

  /* Measure once and set or clear the root attribute; returns true (user
     spacing), false (the tokens) or null (nothing to measure). */
  function check(doc, view, el) {
    if (!doc || !doc.documentElement || !view || !isFn(view.getComputedStyle) || !el) {
      return null;
    }
    var line = lineToken(doc, view);
    if (!isFinite(line)) { return null; }
    var user = differs(measure(el, view), line);
    var rootEl = doc.documentElement;
    if (user) {
      if (rootEl.getAttribute(ATTR) !== USER) { rootEl.setAttribute(ATTR, USER); }
    } else if (rootEl.getAttribute(ATTR) !== null) {
      rootEl.removeAttribute(ATTR);
    }
    return user;
  }

  /* The reference row, made once at the end of the body. */
  function probe(doc) {
    if (!doc || !doc.body) { return null; }
    var el = doc.getElementById(PROBE_ID);
    if (!el) {
      el = doc.createElement("p");
      el.id = PROBE_ID;
      el.className = PROBE_CLASS;
      el.setAttribute("aria-hidden", "true");
      el.textContent = PROBE_TEXT;
      doc.body.appendChild(el);
    }
    return el;
  }

  /* Make the row, check it now and on every change of its box. */
  function install(doc, view) {
    var el = probe(doc);
    if (!el || !view) { return null; }
    var run = function () { check(doc, view, el); };
    run();
    var RO = view.ResizeObserver;
    if (isFn(RO)) {
      var ro = new RO(run);
      ro.observe(el);
    }
    return el;
  }

  var spec = {
    name: NAME,
    region: null,
    wire: function (doc) { install(doc, doc && doc.defaultView ? doc.defaultView : null); }
  };

  return {
    NAME: NAME, ATTR: ATTR, USER: USER, PROBE_ID: PROBE_ID, PROBE_CLASS: PROBE_CLASS,
    LINE_TOKEN: LINE_TOKEN, px: px, remPx: remPx, differs: differs, measure: measure,
    lineToken: lineToken, check: check, probe: probe, install: install, spec: spec
  };
}));
