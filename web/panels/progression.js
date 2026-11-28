/* AshLight dashboard: the Progression view (PROGRESSION-VIEW, decision
   0088; design docs/design/tree-view.md, copy sheet
   docs/design/copy/progression.md).

   One view of the character's progression, built from the core's model
   (server/al/theorycraft/progression.py): the passive tree and the
   ascendancy tree (drawn by web/panels/tree.js), the skill gems with
   their supports, the point lines and the next-up strip. It shows in two
   places, with the same parts:

   - Play, region I (the item check region), as a compact "Next up" view:
     the strip (at most 3 steps) over a mini-tree framed on the nodes due
     next. Region I shows it by itself, with no click, when the published
     progression moves on (a level-up, a new build, tree or plan) and no
     newer item check came in; a new item check gives the region back to
     the item card (web/itemcard.js, which keeps painting its own slot).
     While it shows and an item check exists, one "Item check" button
     gives the card back. The region keeps its fixed track: the view sits
     inside the region's box (no scroll, nothing grows; design 0001 N7).
   - Build and items, a full Progression card opened from the
     "Progression" button at the end of the Builds row; it spans the card
     grid like the Kindler card (the Pasted build cells are not drawn
     while it shows) and "Back to build" closes it. Gem names are the
     shared item info popover's buttons (web/iteminfo.js), as on the
     Kindler plan card; a tree node is read on the one hover line under
     the tree.

   Zero-click: the core publishes the model's small summary in the
   snapshot ("progression": key, next steps, counts) and the page reads
   the whole model (token-gated GET /api/progression) only when that key
   changes, from the state push itself: no timer, no polling. A hidden
   page paints nothing (web/app.js render() returns before the regions
   paint), and a read that answers while the page is hidden waits for the
   next paint (RUN-FEED-TRUTH). Words come composed from the core; this
   file holds only its headings, button labels and legend. Text through
   textContent only; no clipboard, no storage, no live region, no motion.
   Each drawn svg has one ResizeObserver, so it is drawn again at its new
   size after a window or layout change (no timer).

   Registers {name: progression, region: i} with web/regions.js. UMD:
   CommonJS for node and pytest, window.ALProgression in the page. */
(function (root, factory) {
  "use strict";
  var api = factory(root);
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALProgression = api;
    if (root.ALRegions && typeof root.ALRegions.register === "function") {
      root.ALRegions.register(api.spec);
    }
  }
}(typeof self !== "undefined" ? self : this, function (root) {
  "use strict";

  var NAME = "progression";
  var REGION = "i";
  var PATH = "/api/progression";
  var SKILL_ROWS = 6;
  var POINT_ROWS = 6;
  var MINI_W = 480, MINI_H = 170, FULL_W = 560, FULL_H = 420, ASC_W = 300, ASC_H = 150;

  var WORDS = {
    miniHead: "Next up",
    level: "Level ",
    levelUnknown: "Level unknown",
    legend: "Filled: planned. Dashed: next.",
    itemCheck: "Item check",
    open: "Progression",
    title: "Progression",
    back: "Back to build",
    next: "Next up",
    skills: "Skills and supports",
    asc: "Ascendancy",
    points: "Points",
    tip: "Point at a node to read it.",
    fullLegend: "Filled: planned by this level. Dashed ring: take next. Thin ring: later. " +
      "Dot: not in the plan. Outer ring: new since the last change.",
    treeLabel: "Passive tree",
    ascLabel: "Ascendancy tree",
    noTree: "No tree to draw yet.",
    moreSkills: "+{n} more"
  };

  function tree() {
    if (root && root.ALTree) { return root.ALTree; }
    if (typeof module === "object" && module.exports && typeof require === "function") {
      try { return require("./tree.js"); } catch (e) { return null; }
    }
    return null;
  }

  function itemInfo() {
    if (root && root.ALItemInfo) { return root.ALItemInfo; }
    return null;
  }

  function fresh() {
    return { doc: null, ctx: null, key: null, model: null, loading: null, mode: null,
             lastEval: null, lastLevel: undefined, lastLine: null, open: false,
             drawn: {}, boxes: {}, args: {} };
  }
  var S = fresh();

  function el(doc, tag, cls, text) {
    var n = doc.createElement(tag);
    if (cls) { n.className = cls; }
    if (text !== undefined && text !== null) { n.textContent = text; }
    return n;
  }
  function svg(doc, id, cls, label) {
    var T = tree();
    var n = doc.createElementNS(T ? T.NS : "http://www.w3.org/2000/svg", "svg");
    if (id) { n.setAttribute("id", id); }
    n.setAttribute("class", cls);
    n.setAttribute("role", "img");
    n.setAttribute("aria-label", label);
    n.setAttribute("focusable", "false");
    n.setAttribute("preserveAspectRatio", "xMidYMid meet");
    return n;
  }
  function setText(n, text) { if (n && n.textContent !== text) { n.textContent = text; } }
  function show(n, on) { if (n && n.hidden === !!on) { n.hidden = !on; } }

  function summaryOf(snap) {
    var p = snap && snap.progression;
    return p && typeof p === "object" && typeof p.key === "string" ? p : null;
  }
  function evalOf(snap) {
    var ev = snap && snap.eval;
    var id = ev && typeof ev === "object" ? ev.id : null;
    return typeof id === "string" || typeof id === "number" ? String(id) : "";
  }
  function hasContent(sum) {
    return !!(sum && (sum.tree || (Array.isArray(sum.next) && sum.next.length)));
  }

  /* Which view region I shows: "item" or "progress" (pure, for tests).
     The first paint shows the item card when a check exists; after that a
     new check shows the card, and a level, source or build change shows
     the progression. */
  function decide(st, sum, evalId) {
    if (!hasContent(sum)) { return "item"; }
    if (st.mode === null) { return evalId ? "item" : "progress"; }
    if (evalId && evalId !== st.lastEval) { return "item"; }
    var moved = (st.lastLevel !== undefined && sum.level !== st.lastLevel) ||
      (st.lastLine !== null && sum.source_line !== st.lastLine);
    return moved ? "progress" : st.mode;
  }

  function levelWord(level) {
    return typeof level === "number" ? WORDS.level + level : WORDS.levelUnknown;
  }

  /* -- data --------------------------------------------------------- */

  function load(sum) {
    if (!S.ctx || typeof S.ctx.api !== "function" || S.loading === sum.key) { return; }
    S.loading = sum.key;
    S.ctx.api("GET", PATH).then(function (m) {
      S.loading = null;
      if (!m || typeof m.key !== "string") { return; }
      S.model = m;
      S.key = m.key;
      var d = S.doc;
      if (d && !d.hidden && S.ctx.getSnap) { paint(d, S.ctx.getSnap()); }
    }, function () { S.loading = null; });
  }

  /* -- region I ------------------------------------------------------ */

  function buildMini(doc) {
    var region = doc.getElementById("play-i");
    if (!region) { return null; }
    var box = doc.getElementById("pg-mini");
    if (box) { return box; }
    box = el(doc, "div", "pg-mini");
    box.id = "pg-mini";
    box.hidden = true;
    var head = el(doc, "p", "pg-mini-head");
    head.appendChild(el(doc, "span", "pg-mini-word row-title", WORDS.miniHead));
    var sub = el(doc, "span", "pg-mini-sub row-meta one-line muted");
    sub.id = "pg-mini-sub";
    head.appendChild(sub);
    box.appendChild(head);
    var list = el(doc, "ul", "pg-mini-next");
    list.id = "pg-mini-next";
    box.appendChild(list);
    box.appendChild(svg(doc, "pg-mini-tree", "pg-svg pg-mini-tree", WORDS.treeLabel));
    var foot = el(doc, "p", "pg-mini-foot");
    foot.appendChild(el(doc, "span", "row-meta one-line muted pg-mini-legend", WORDS.legend));
    var back = el(doc, "button", "secondary btn-24 pg-mini-back", WORDS.itemCheck);
    back.type = "button";
    back.id = "pg-mini-item";
    back.addEventListener("click", function () {
      S.mode = "item";
      paintRegion(doc, S.ctx && S.ctx.getSnap ? S.ctx.getSnap() : null);
    });
    foot.appendChild(back);
    box.appendChild(foot);
    region.appendChild(box);
    return box;
  }

  function fillSteps(doc, list, steps, empty, cap) {
    var want = steps.slice(0, cap);
    if (!want.length) { want = [{ kind: "none", text: empty || "" }]; }
    while (list.children.length > want.length) { list.removeChild(list.lastChild); }
    while (list.children.length < want.length) { list.appendChild(el(doc, "li", "row-body one-line")); }
    want.forEach(function (st, i) {
      var li = list.children[i];
      setText(li, st.text);
      li.setAttribute("title", st.text);
      li.setAttribute("data-kind", st.kind || "");
      li.className = "row-body one-line" + (st.kind === "none" ? " muted" : "");
    });
  }

  function size(node, w, h) {
    var r = node && node.getBoundingClientRect ? node.getBoundingClientRect() : null;
    if (r && r.width > 1 && r.height > 1) { return [r.width, r.height]; }
    return [w, h];
  }

  /* A drawn svg follows its own box: a resize (window, scale step, the
     Build tab showing) re-draws it at its new size. Event-driven, no
     timer; a hidden page draws nothing. */
  function follow(doc, node) {
    if (node.__alSized || typeof root.ResizeObserver !== "function") { return; }
    node.__alSized = new root.ResizeObserver(function () {
      var a = S.args[node.id];
      if (!a || doc.hidden) { return; }
      draw(doc, node, a[0], a[1], a[2], a[3]);
    });
    node.__alSized.observe(node);
  }

  function draw(doc, node, view, mode, defW, defH) {
    var T = tree();
    if (!T || !node) { return null; }
    S.args[node.id] = [view, mode, defW, defH];
    follow(doc, node);
    var wh = size(node, defW, defH);
    var newIds = S.model && Array.isArray(S.model["new"]) ? S.model["new"] : [];
    var sig = [S.key, mode, Math.round(wh[0]), Math.round(wh[1])].join(" ");
    if (S.drawn[node.id] === sig) { return S.boxes[node.id]; }
    S.drawn[node.id] = sig;
    S.boxes[node.id] = T.render(doc, node, view, { mode: mode, width: wh[0], height: wh[1],
                                                  fresh: newIds });
    return S.boxes[node.id];
  }

  function paintRegion(doc, snap) {
    var region = doc.getElementById("play-i");
    if (!region) { return; }
    var sum = summaryOf(snap);
    var evalId = evalOf(snap);
    var mode = decide(S, sum, evalId);
    S.mode = hasContent(sum) ? mode : S.mode;
    S.lastEval = evalId;
    if (sum) { S.lastLevel = sum.level; S.lastLine = sum.source_line; }
    var on = mode === "progress";
    if (region.getAttribute("data-pg") !== (on ? "on" : "off")) {
      region.setAttribute("data-pg", on ? "on" : "off");
    }
    var box = on ? buildMini(doc) : doc.getElementById("pg-mini");
    show(box, on);
    if (!on || !box) { return; }
    setText(doc.getElementById("pg-mini-sub"), levelWord(sum.level));
    fillSteps(doc, doc.getElementById("pg-mini-next"), sum.next || [], sum.empty, 3);
    show(doc.getElementById("pg-mini-item"), !!evalId);
    var t = doc.getElementById("pg-mini-tree");
    var view = S.model && S.model.key === sum.key ? S.model.tree : null;
    show(t, !!view);
    if (view) { draw(doc, t, view, "mini", MINI_W, MINI_H); }
  }

  /* -- Build and items card ----------------------------------------- */

  function h3(doc, text, id) {
    var n = el(doc, "h3", "card-h3 pg-h3", text);
    if (id) { n.id = id; }
    return n;
  }

  function buildCard(doc) {
    var panel = doc.getElementById("panel-build");
    if (!panel) { return null; }
    var card = doc.getElementById("pgbox");
    if (card) { return card; }
    card = el(doc, "section", "card pg-card");
    card.id = "pgbox";
    card.setAttribute("aria-labelledby", "pg-title");
    card.hidden = true;
    var head = el(doc, "div", "pg-head");
    var title = el(doc, "h2", "pg-title one-line", WORDS.title);
    title.id = "pg-title";
    title.setAttribute("tabindex", "-1");
    head.appendChild(title);
    var src = el(doc, "span", "row-meta one-line muted pg-source");
    src.id = "pg-source";
    head.appendChild(src);
    var back = el(doc, "button", "secondary btn-24 pg-back", WORDS.back);
    back.type = "button";
    back.id = "pg-back";
    back.addEventListener("click", function () { setOpen(doc, false, true); });
    head.appendChild(back);
    card.appendChild(head);
    var note = el(doc, "p", "row-meta pg-note");
    note.id = "pg-note";
    note.hidden = true;
    card.appendChild(note);
    var body = el(doc, "div", "pg-body");
    var c1 = el(doc, "div", "pg-col pg-col-tree");
    var big = svg(doc, "pg-tree", "pg-svg pg-tree", WORDS.treeLabel);
    c1.appendChild(big);
    var tip = el(doc, "p", "row-meta one-line pg-tip", WORDS.tip);
    tip.id = "pg-tip";
    c1.appendChild(tip);
    c1.appendChild(el(doc, "p", "row-micro muted pg-legend", WORDS.fullLegend));
    var c2 = el(doc, "div", "pg-col");
    c2.appendChild(h3(doc, WORDS.next));
    var next = el(doc, "ul", "pg-list");
    next.id = "pg-next";
    c2.appendChild(next);
    c2.appendChild(h3(doc, WORDS.skills));
    var skills = el(doc, "ul", "pg-list");
    skills.id = "pg-skills";
    c2.appendChild(skills);
    var c3 = el(doc, "div", "pg-col");
    c3.appendChild(h3(doc, WORDS.asc, "pg-asc-h"));
    var asc = svg(doc, "pg-asc", "pg-svg pg-asc", WORDS.ascLabel);
    c3.appendChild(asc);
    var atip = el(doc, "p", "row-meta one-line pg-tip", "");
    atip.id = "pg-asc-tip";
    c3.appendChild(atip);
    c3.appendChild(h3(doc, WORDS.points));
    var pts = el(doc, "ul", "pg-list");
    pts.id = "pg-points";
    c3.appendChild(pts);
    body.appendChild(c1);
    body.appendChild(c2);
    body.appendChild(c3);
    card.appendChild(body);
    panel.appendChild(card);
    hover(big, tip, "tree");
    hover(asc, atip, "asc");
    var info = itemInfo();
    if (info && typeof info.attach === "function") { info.attach(card, {}); }
    return card;
  }

  function hover(node, tip, part) {
    var T = tree();
    if (!T || !node.addEventListener) { return; }
    var rest = part === "tree" ? WORDS.tip : "";
    node.addEventListener("pointermove", function (e) {
      var view = S.model && S.model[part];
      var box = S.boxes[node.id];
      if (!view || !box) { return; }
      var r = node.getBoundingClientRect();
      var i = T.hit(view, box, r.width, r.height, e.clientX - r.left, e.clientY - r.top);
      setText(tip, i >= 0 ? T.label(view, i) : rest);
      if (i >= 0) { tip.setAttribute("title", T.label(view, i)); }
    });
    node.addEventListener("pointerleave", function () { setText(tip, rest); });
  }

  function fillSkills(doc, list, rows) {
    var info = itemInfo();
    list.replaceChildren();
    var shown = rows.slice(0, rows.length > SKILL_ROWS ? SKILL_ROWS - 1 : SKILL_ROWS);
    shown.forEach(function (r) {
      var li = el(doc, "li", "row-meta one-line pg-skill");
      li.appendChild(info && typeof info.button === "function" ? info.button(doc, r.name)
        : el(doc, "span", "", r.name));
      var rest = " " + r.meta + "; " + r["with"];
      li.appendChild(el(doc, "span", "muted", rest));
      li.setAttribute("title", r.name + rest);
      list.appendChild(li);
    });
    if (rows.length > shown.length) {
      list.appendChild(el(doc, "li", "row-meta one-line muted",
        WORDS.moreSkills.replace("{n}", String(rows.length - shown.length))));
    }
  }

  function fillLines(doc, list, lines, cap) {
    list.replaceChildren();
    lines.slice(0, cap).forEach(function (t) {
      var li = el(doc, "li", "row-meta one-line", t);
      li.setAttribute("title", t);
      list.appendChild(li);
    });
  }

  function paintCard(doc, snap) {
    var card = doc.getElementById("pgbox");
    if (!card || card.hidden) { return; }
    var sum = summaryOf(snap);
    var m = S.model && sum && S.model.key === sum.key ? S.model : null;
    setText(doc.getElementById("pg-source"),
      sum ? sum.source_line + " - " + levelWord(sum.level) : "");
    var note = doc.getElementById("pg-note");
    setText(note, m && m.note ? m.note : (sum && sum.note) || "");
    show(note, !!note.textContent);
    fillSteps(doc, doc.getElementById("pg-next"), (sum && sum.next) || [],
      (sum && sum.empty) || "", 3);
    if (!m) { return; }
    if (S.drawnSkills !== m.key) {
      S.drawnSkills = m.key;
      fillSkills(doc, doc.getElementById("pg-skills"), m.skills || []);
      fillLines(doc, doc.getElementById("pg-points"), m.points || [], POINT_ROWS);
    }
    var big = doc.getElementById("pg-tree");
    show(big, !!m.tree);
    if (m.tree) { draw(doc, big, m.tree, "full", FULL_W, FULL_H); }
    setText(doc.getElementById("pg-tip"), m.tree ? WORDS.tip : WORDS.noTree);
    var asc = doc.getElementById("pg-asc");
    show(asc, !!m.asc);
    setText(doc.getElementById("pg-asc-h"), m.asc ? WORDS.asc + ": " + m.asc.name : WORDS.asc);
    if (m.asc) { draw(doc, asc, m.asc, "full", ASC_W, ASC_H); }
  }

  function setOpen(doc, on, focus) {
    var panel = doc.getElementById("panel-build");
    var btn = doc.getElementById("pg-open");
    var card = on ? buildCard(doc) : doc.getElementById("pgbox");
    S.open = on;
    if (panel) {
      if (on) { panel.setAttribute("data-view", "progress"); } else { panel.removeAttribute("data-view"); }
    }
    show(card, on);
    if (btn) { btn.setAttribute("aria-pressed", on ? "true" : "false"); }
    if (on) {
      S.drawn = {};
      S.drawnSkills = null;
      paintCard(doc, S.ctx && S.ctx.getSnap ? S.ctx.getSnap() : null);
      var t = doc.getElementById("pg-title");
      if (focus && t && t.focus) { t.focus(); }
    } else if (focus && btn && btn.focus) { btn.focus(); }
  }

  function wire(doc, ctx) {
    S.doc = doc;
    S.ctx = ctx || {};
    var bar = doc.getElementById("kindler-bar");
    if (!bar || doc.getElementById("pg-open")) { return; }
    var b = el(doc, "button", "secondary btn-24 pg-open", WORDS.open);
    b.type = "button";
    b.id = "pg-open";
    b.setAttribute("aria-pressed", "false");
    b.addEventListener("click", function () { setOpen(doc, !S.open, true); });
    bar.appendChild(b);
    /* picking a build sub-tab (Pasted build or a Kindler tab) closes it */
    bar.addEventListener("click", function (e) {
      var t = e.target && e.target.closest ? e.target.closest("button.subtab") : null;
      if (t && S.open) { setOpen(doc, false, false); }
    });
  }

  function paint(doc, snap) {
    if (!S.doc) { S.doc = doc; }
    var sum = summaryOf(snap);
    if (!sum) { S.model = null; S.key = null; }
    else if (sum.key !== S.key) { load(sum); }
    paintRegion(doc, snap);
    paintCard(doc, snap);
  }

  function reset() { S = fresh(); }
  function state() { return S; }

  return {
    NAME: NAME, WORDS: WORDS, decide: decide, hasContent: hasContent, levelWord: levelWord,
    paint: paint, wire: wire, reset: reset, state: state, setOpen: setOpen,
    spec: { name: NAME, region: REGION, paint: paint, wire: wire }
  };
}));
