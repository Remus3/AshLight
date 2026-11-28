/* AshLight dashboard: the passive tree renderer (PROGRESSION-VIEW,
   decision 0088; design docs/design/tree-view.md).

   Draws one tree view of the core's Progression model (GET
   /api/progression: {box, n: [[id, x, y, kind, state]], e: [[i, j,
   state]], names}) as an own SVG from the GGG export's own positions.
   Every node is an AshLight-drawn shape, never a GGG image: small and
   jewel nodes are small dots and diamonds, notables larger dots,
   keystones large diamonds, a class or ascendancy start a ring. Lines are
   the export's links, straight.

   Cheap by design (decision 0002 dashboard budget, tests/test_dash_perf.py
   1,500 elements): a whole tree is at most 10 elements, one <path> per
   state for the links, one per state for the nodes and one for the
   "newly due" edge; each path holds every node of its state as
   subpaths. States: h planned by this level (filled), d due next (a
   dashed ring), l planned later (a thin ring), o not in the plan (a dim
   dot). The shape and the line style say the state, the colour (design
   tokens only, in web/panels/progression.css) only reinforces it
   (design 0001 C4). A node due since the last change carries a steady
   outer ring; nothing moves (design 0001 principle 3: no motion, so no
   animation and no transition, even for the fit to bounds).

   frame(view, mode) picks the export-unit box to show: the model's own
   box ("full"), or for "mini" the due nodes and their planned
   neighbours (at least MINI_SPAN wide), so the Play mini-tree reads at a
   glance. The SVG viewBox is in screen pixels (the size measured at
   paint), so radii and strokes keep their pixel size at every zoom.

   UMD like web/fmt.js: CommonJS for node --test and pytest, window.ALTree
   in the page. No timer, no request, no storage, no clipboard; nodes get
   no text (names are read by hit() for the one hover line). */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALTree = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var NS = "http://www.w3.org/2000/svg";
  var STATES = ["o", "l", "h", "d"]; // paint order: dim first, due last
  // node radius in export units (small, notable, keystone, jewel, class
  // start, ascendancy start), held between a smallest and a largest screen
  // px size so a far-out frame stays readable and a close one stays neat
  var RADIUS = { s: 40, n: 62, k: 90, j: 50, c: 75, a: 75 };
  var MIN_PX = { s: 2, n: 3.5, k: 5, j: 3, c: 4.5, a: 4.5 };
  var MAX_PX = { s: 6, n: 9, k: 12, j: 7, c: 10, a: 10 };
  var DIAMOND = { k: true, j: true };
  var RING = { c: true, a: true };
  var MINI_SPAN = 1800; // export units: the Play mini-tree's smallest box
  var MINI_NEAR = 900;  // planned nodes this close to a due node join its frame
  var PAD = 300;
  var HIT_PX = 10;

  function num(v) { return typeof v === "number" && isFinite(v); }

  function goodView(view) {
    return !!(view && Array.isArray(view.n) && Array.isArray(view.box) && view.box.length === 4 &&
              view.box[2] > 0 && view.box[3] > 0);
  }

  function bounds(rows) {
    var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    rows.forEach(function (r) {
      x0 = Math.min(x0, r[1]); x1 = Math.max(x1, r[1]);
      y0 = Math.min(y0, r[2]); y1 = Math.max(y1, r[2]);
    });
    return [x0, y0, x1, y1];
  }

  function padBox(b, pad, span) {
    var x0 = b[0] - pad, y0 = b[1] - pad, x1 = b[2] + pad, y1 = b[3] + pad, c;
    if (x1 - x0 < span) { c = (x0 + x1) / 2; x0 = c - span / 2; x1 = c + span / 2; }
    if (y1 - y0 < span) { c = (y0 + y1) / 2; y0 = c - span / 2; y1 = c + span / 2; }
    return [x0, y0, x1 - x0, y1 - y0];
  }

  /* The export-unit box to show. "mini": the due nodes plus the planned
     nodes within MINI_NEAR of one; with nothing due, the model's box. */
  function frame(view, mode) {
    if (!goodView(view)) { return null; }
    if (mode !== "mini") { return view.box.slice(); }
    var due = view.n.filter(function (r) { return r[4] === "d"; });
    if (!due.length) { return view.box.slice(); }
    var near = view.n.filter(function (r) {
      if (r[4] !== "h") { return false; }
      return due.some(function (d) {
        var dx = d[1] - r[1], dy = d[2] - r[2];
        return dx * dx + dy * dy <= MINI_NEAR * MINI_NEAR;
      });
    });
    return padBox(bounds(due.concat(near)), PAD, MINI_SPAN);
  }

  /* Export units to screen px: the box fits the w x h area, centred.
     The returned function carries the scale as .k (px per unit). */
  function mapper(box, w, h) {
    var k = Math.min(w / box[2], h / box[3]);
    var ox = (w - box[2] * k) / 2, oy = (h - box[3] * k) / 2;
    var f = function (x, y) { return [ox + (x - box[0]) * k, oy + (y - box[1]) * k]; };
    f.k = k;
    return f;
  }

  function radius(kind, k) {
    var key = RADIUS[kind] ? kind : "s";
    return Math.max(MIN_PX[key], Math.min(MAX_PX[key], RADIUS[key] * k));
  }

  function r1(v) { return Math.round(v * 10) / 10; }

  function shape(x, y, kind, r) {
    if (DIAMOND[kind]) {
      return "M" + r1(x) + " " + r1(y - r) + "L" + r1(x + r) + " " + r1(y) + "L" + r1(x) + " " +
        r1(y + r) + "L" + r1(x - r) + " " + r1(y) + "Z";
    }
    return "M" + r1(x - r) + " " + r1(y) + "a" + r1(r) + " " + r1(r) + " 0 1 0 " + r1(2 * r) +
      " 0a" + r1(r) + " " + r1(r) + " 0 1 0 " + r1(-2 * r) + " 0Z";
  }

  /* {edges: {state: d}, nodes: {state: d}, fresh: d, rings: d} for a view
     shown in a w x h px area; nodes outside the area are left out. */
  function paths(view, box, w, h, fresh) {
    var out = { edges: { o: "", l: "", h: "", d: "" }, nodes: { o: "", l: "", h: "", d: "" },
                fresh: "", rings: "" };
    if (!goodView(view) || !box || !(w > 0) || !(h > 0)) { return out; }
    var map = mapper(box, w, h);
    var isNew = {};
    (fresh || []).forEach(function (id) { isNew[id] = true; });
    var pos = view.n.map(function (r) { return map(r[1], r[2]); });
    var shown = function (p) { return p[0] >= -8 && p[1] >= -8 && p[0] <= w + 8 && p[1] <= h + 8; };
    (view.e || []).forEach(function (e) {
      var a = pos[e[0]], b = pos[e[1]];
      if (!a || !b || (!shown(a) && !shown(b))) { return; }
      var st = out.edges[e[2]] !== undefined ? e[2] : "o";
      out.edges[st] += "M" + r1(a[0]) + " " + r1(a[1]) + "L" + r1(b[0]) + " " + r1(b[1]);
    });
    view.n.forEach(function (r, i) {
      var p = pos[i];
      if (!shown(p)) { return; }
      var st = out.nodes[r[4]] !== undefined ? r[4] : "o";
      var rad = radius(r[3], map.k);
      if (RING[r[3]]) { out.rings += shape(p[0], p[1], r[3], rad); }
      out.nodes[st] += shape(p[0], p[1], RING[r[3]] ? "s" : r[3], RING[r[3]] ? rad * 0.55 : rad);
      if (isNew[r[0]]) { out.fresh += shape(p[0], p[1], r[3], rad + 3.5); }
    });
    return out;
  }

  function el(doc, name, cls) {
    var n = doc.createElementNS(NS, name);
    if (cls) { n.setAttribute("class", cls); }
    return n;
  }

  /* The fixed child list of one tree <svg>: made once, then only the d
     attributes change (no node is added or removed on a repaint). */
  function ensure(doc, svg) {
    if (svg.__alTree) { return svg.__alTree; }
    var parts = { edges: {}, nodes: {} };
    STATES.forEach(function (st) {
      parts.edges[st] = el(doc, "path", "tv-edge tv-edge-" + st);
      svg.appendChild(parts.edges[st]);
    });
    parts.rings = el(doc, "path", "tv-ring");
    svg.appendChild(parts.rings);
    STATES.forEach(function (st) {
      parts.nodes[st] = el(doc, "path", "tv-node tv-node-" + st);
      svg.appendChild(parts.nodes[st]);
    });
    parts.fresh = el(doc, "path", "tv-fresh");
    svg.appendChild(parts.fresh);
    svg.__alTree = parts;
    return parts;
  }

  function setD(node, d) {
    var v = d || "M0 0";
    if (node.getAttribute("d") !== v) { node.setAttribute("d", v); }
  }

  /* Paint `view` into `svg` (w x h px, the caller's measure). Returns the
     box used, for hit(). */
  function render(doc, svg, view, opts) {
    var o = opts || {};
    var w = Math.max(1, Math.round(o.width || 0)), h = Math.max(1, Math.round(o.height || 0));
    var box = frame(view, o.mode);
    var parts = ensure(doc, svg);
    var vb = "0 0 " + w + " " + h;
    if (svg.getAttribute("viewBox") !== vb) { svg.setAttribute("viewBox", vb); }
    var p = paths(view, box, w, h, o.fresh);
    STATES.forEach(function (st) { setD(parts.edges[st], p.edges[st]); setD(parts.nodes[st], p.nodes[st]); });
    setD(parts.rings, p.rings);
    setD(parts.fresh, p.fresh);
    return box;
  }

  /* The index of the node nearest to (px, py) within HIT_PX, or -1. */
  function hit(view, box, w, h, px, py) {
    if (!goodView(view) || !box) { return -1; }
    var map = mapper(box, w, h), best = -1, bestD = HIT_PX * HIT_PX;
    view.n.forEach(function (r, i) {
      var p = map(r[1], r[2]);
      var dx = p[0] - px, dy = p[1] - py, d = dx * dx + dy * dy;
      if (d <= bestD) { bestD = d; best = i; }
    });
    return best;
  }

  /* The hover line of one node: "Name: first stat" (names of the model),
     else the kind word. */
  var KIND_WORDS = { s: "Passive", n: "Notable passive", k: "Keystone", j: "Jewel socket",
                     c: "Class start", a: "Ascendancy start" };
  var STATE_WORDS = { h: "planned by this level", d: "take next", l: "planned later",
                      o: "not in the plan" };
  function label(view, i) {
    var r = view && view.n && view.n[i];
    if (!r) { return ""; }
    var named = view.names && view.names[String(r[0])];
    var head = named && named[0] ? named[0] : (KIND_WORDS[r[3]] || KIND_WORDS.s);
    var stat = named && named[1] ? ": " + named[1] : "";
    return head + " (" + (STATE_WORDS[r[4]] || STATE_WORDS.o) + ")" + stat;
  }

  function counts(view) {
    var c = { h: 0, d: 0, l: 0, o: 0 };
    ((view && view.n) || []).forEach(function (r) { if (c[r[4]] !== undefined) { c[r[4]] += 1; } });
    return c;
  }

  return {
    NS: NS, STATES: STATES, RADIUS: RADIUS, MIN_PX: MIN_PX, MAX_PX: MAX_PX, radius: radius,
    MINI_SPAN: MINI_SPAN, KIND_WORDS: KIND_WORDS,
    STATE_WORDS: STATE_WORDS, frame: frame, mapper: mapper, paths: paths, render: render,
    hit: hit, label: label, counts: counts
  };
}));
