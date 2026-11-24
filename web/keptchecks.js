/* AshLight dashboard: region U, the kept checks (PLAY-TD-16B-KEPT-CHECKS; plan 03
   TD-16, section 3.4 U and 3.8; design 0001 section 6).

   A review list: the best items checked this session against the CURRENT
   build, best first (decision 0045 re-score; memory only, Q-26 b).
   Track 100 px at s = 1: border 2 + padding 8 + 8 + the label 20 + 3 rows
   of 20 = 98. The compact class keeps the best row only and pads 4 + 4
   (track 52: 50 of content). Every row is 14 px (the meta step), at most
   42 characters, composed and capped by the core (server/al/playcards.py
   kept_view: glyph + word, gain, item, slot, time; the item name takes the
   "..."); its uncut text is the row's title. Empty: one muted line.

   The rows come from snap.play.kept only and pass through
   ALSlots.keptChecks (web/slots.js), which keeps the core's order and
   cuts the list to the size class's row count. Every state push repaints,
   so a build or weight change re-orders U by itself from the next push;
   a window resize (and the once-a-second tick as a backstop) repaints
   only when the size class changed.

   No button, no link, no timer of its own, no network, no clipboard, no
   live region; never calls ALTabs.notify (the legacy path keeps that until
   PLAY-LEGACY-OUT). Registers {name: keptchecks, region: u, retires: []}
   with web/regions.js. UMD like web/tabs.js: CommonJS for node --test,
   window.ALKeptChecks in the page. */
(function (root, factory) {
  "use strict";
  var api;
  if (typeof module === "object" && module.exports) {
    api = factory(require("./slots.js"), root);
    module.exports = api;
  } else {
    api = factory(root.ALSlots, root);
    root.ALKeptChecks = api;
    if (root.ALRegions && typeof root.ALRegions.register === "function") {
      root.ALRegions.register(api.spec);
    }
  }
}(typeof self !== "undefined" ? self : this, function (Slots, root) {
  "use strict";

  var NAME = "keptchecks";
  var REGION = "u";
  var LABEL = "Best checks";
  // play.kept is null until BUILD-LIVE has a list; the core's own empty
  // line wins whenever it sends one
  var EMPTY_NONE = "Check items to rank them.";
  var CLASSES = ["full", "compact", "flow"];

  function isObj(v) { return v !== null && typeof v === "object" && !Array.isArray(v); }
  function str(v) { return typeof v === "string" ? v : ""; }

  /* The size class from the root's --al-size-class (web/app.css): full,
     compact, or flow when no style says otherwise. */
  function sizeClassOf(doc) {
    try {
      var view = (doc && doc.defaultView) || root;
      if (view && typeof view.getComputedStyle === "function" && doc && doc.documentElement) {
        var v = String(view.getComputedStyle(doc.documentElement)
          .getPropertyValue("--al-size-class") || "").trim();
        return CLASSES.indexOf(v) >= 0 ? v : "flow";
      }
    } catch (e) { /* no styles: flow */ }
    return "flow";
  }

  /* snap, sizeClass -> {rows: [{text, full}], empty}. The core sends the
     rows best first; ALSlots.keptChecks ranks by score_delta, so each row
     gets its place in the core's order as its score (the order is kept)
     and the list is cut to the class's rows (3; 1 in compact). */
  function model(snap, sizeClass) {
    var play = isObj(snap) && isObj(snap.play) ? snap.play : null;
    var kept = play && isObj(play.kept) ? play.kept : null;
    var raw = kept && Array.isArray(kept.rows) ? kept.rows.filter(function (r) {
      return isObj(r) && str(r.text) !== "";
    }) : [];
    var items = raw.map(function (r, i) {
      return { score_delta: raw.length - i, at: r.at, row: r };
    });
    var build = isObj(snap) && isObj(snap.build) ? snap.build : null;
    var pick = Slots && typeof Slots.keptChecks === "function"
      ? Slots.keptChecks(items, build, sizeClass)
      : (build && build.loaded === true ? items.slice(0, 3) : []);
    var rows = pick.map(function (x) {
      var text = str(x.row.text);
      return { text: text, full: str(x.row.full) || text };
    });
    var empty = "";
    if (!rows.length) {
      empty = (kept && str(kept.empty)) || EMPTY_NONE;
    }
    return { rows: rows, empty: empty };
  }

  function slotOf(doc) {
    if (!doc || typeof doc.querySelector !== "function") { return null; }
    return doc.querySelector('#play-u [data-slot="u"]');
  }

  function el(doc, tag, cls, id) {
    var n = doc.createElement(tag);
    if (cls) { n.className = cls; }
    if (id) { n.id = id; }
    return n;
  }

  function setText(n, text) { if (n.textContent !== text) { n.textContent = text; } }
  function setAttr(n, k, v) { if (n.getAttribute(k) !== v) { n.setAttribute(k, v); } }

  // the region's nodes, made once by wire() (or the first paint): the
  // the list of 3 reserved rows and the empty line (the label is the
  // region's own visible heading in web/index.html, PLAY-FIT-G5-TOTALS)
  var nodes = { doc: null, root: null, list: null, rows: [], empty: null };
  var state = { cls: null, snap: null, listening: false };

  function build(doc) {
    if (nodes.doc === doc && nodes.root) { return nodes; }
    var slot = slotOf(doc);
    if (!slot || typeof doc.createElement !== "function") { return null; }
    // the slot is the kept-checks box itself (PLAY-FIT-G5-TOTALS: no wrapper)
    var rootEl = slot;
    if ((" " + rootEl.className + " ").indexOf(" kc ") < 0) {
      rootEl.className = rootEl.className ? rootEl.className + " kc" : "kc";
    }
    rootEl.id = "kc";
    var list = el(doc, "ol", "kc-list", "kc-list");
    var rows = [];
    for (var i = 0; i < 3; i++) {
      var li = el(doc, "li", "kc-row row-meta one-line");
      li.hidden = true;
      list.appendChild(li);
      rows.push(li);
    }
    var empty = el(doc, "p", "kc-empty row-meta muted one-line", "kc-empty");
    empty.hidden = true;
    rootEl.appendChild(list);
    rootEl.appendChild(empty);
    nodes = { doc: doc, root: rootEl, list: list, rows: rows, empty: empty };
    return nodes;
  }

  /* Paint U from one snapshot. Idempotent: a node is touched only when
     its text or attribute changes. cls overrides the measured class
     (tests). */
  function paint(doc, snap, now, ctx, cls) {
    var n = build(doc);
    state.snap = snap;
    state.cls = typeof cls === "string" ? cls : sizeClassOf(doc);
    if (!n) { return null; }
    var m = model(snap, state.cls);
    n.rows.forEach(function (li, i) {
      var r = m.rows[i];
      if (!r) {
        li.hidden = true;
        setText(li, "");
        setAttr(li, "title", "");
        return;
      }
      setText(li, r.text);
      setAttr(li, "title", r.full);
      li.hidden = false;
    });
    n.list.hidden = m.rows.length === 0;
    setText(n.empty, m.empty);
    n.empty.hidden = !m.empty;
    setAttr(n.root, "data-rows", String(m.rows.length));
    return m;
  }

  /* Repaint only when the size class changed (a window resize between two
     state pushes). */
  function tick(doc) {
    if (nodes.root && sizeClassOf(doc) !== state.cls) { paint(doc, state.snap); }
  }

  /* wire: make the nodes once, and repaint on a window resize that changes
     the size class, so a compact window never shows the full class's rows
     for up to a second (the once-a-second tick stays as the backstop). */
  function wire(doc) {
    build(doc);
    var view = doc && doc.defaultView;
    if (view && typeof view.addEventListener === "function" && !state.listening) {
      state.listening = true;
      view.addEventListener("resize", function () { tick(doc); });
    }
  }

  /* Tests only: forget the nodes made for an earlier document. */
  function reset() {
    nodes = { doc: null, root: null, list: null, rows: [], empty: null };
    state.cls = null;
    state.snap = null;
    state.listening = false;
  }

  var spec = {
    name: NAME,
    region: REGION,
    retires: [],
    wire: wire,
    paint: function (doc, snap) { paint(doc, snap); },
    tick: function (doc) { tick(doc); }
  };

  return {
    NAME: NAME, REGION: REGION, LABEL: LABEL, EMPTY_NONE: EMPTY_NONE,
    model: model, sizeClassOf: sizeClassOf, paint: paint, wire: wire, tick: tick,
    reset: reset, spec: spec
  };
}));
