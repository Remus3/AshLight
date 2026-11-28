/* AshLight dashboard: the Progression view (PROGRESSION-VIEW, decision
   0092; design docs/design/tree-view.md, copy sheet
   docs/design/copy/progression.md).

   One view of the character's progression, built from the core's model
   (server/al/theorycraft/progression.py): the passive tree and the
   ascendancy tree (drawn by web/panels/tree.js), the skill gems with
   their supports, the point lines and the next-up strip. It shows in two
   places, with the same parts:

   - Play, region I (the item check region), as a compact "Next up" view:
     the strip (at most 3 steps, 20 px rows) over a mini-tree framed on the
     nodes due next. The first paint shows the item card (its empty state
     teaches the item key). The region swaps to the progression by itself,
     with no click, when the published progression moves on (a level-up
     between two known levels, or a change of build or tree) and no newer
     item check came in; an item check under HOLD_S old holds the swap
     until the first push after the hold (no timer). A new item check
     gives the region back to the item card (web/itemcard.js keeps painting
     its own slot). While the view shows, one "Item check" button gives
     the card back. While the item card shows and the progression has
     something to draw, one "Next up" button at the region's top right
     opens the view at once (PROGRESSION-OFFER: the view must not wait
     for a level-up to be found). The swap is decided in the
     page's push hook, before the regions paint, so the item card's live
     region is shown again before it changes (decision 0092, design review
     PG-8); region I's heading reads "Next up" or "Item check". The region
     keeps its fixed track (no scroll, nothing grows; design 0001 N7).
   - Build and items, a full Progression card opened from the
     "Progression" button at the end of the Builds row; it spans the card
     grid like the Kindler card (the Pasted build cells are not drawn
     while it shows) and "Back to build" closes it. Two columns: the tree,
     then Next up, Skills and supports, Ascendancy and Points stacked. Gem
     names are the shared item info popover's buttons (web/iteminfo.js), as
     on the Kindler plan card; a tree node is read on the one hover line
     under the tree. Skill and point rows wrap; when the column would
     overflow, the last rows leave for a "+n more" line (measured, no
     scroll).

   Zero-click: the core publishes the model's small summary in the
   snapshot ("progression": key, next steps, counts) and the page reads
   the whole model (token-gated GET /api/progression) only when that key
   changes, from the state push itself: no timer, no polling; at most 2
   failed reads per key. While a new key loads the last tree stays drawn.
   A hidden page paints nothing (web/app.js render() returns before the
   regions paint); on its return the swap is not counted as a move. Words
   come composed from the core; this file holds only its headings, button
   labels and legend. Text through textContent only; no clipboard, no
   storage, no live region, no motion. Each drawn svg has one
   ResizeObserver, so it is drawn again at its new size after a window or
   layout change (no timer).

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
  var HOLD_S = 20;      // an item check this fresh holds the level-up swap
  var MAX_FAILS = 2;    // failed model reads per key before it waits for a new key
  var STEPS = 3;
  var MINI_W = 480, MINI_H = 170, FULL_W = 560, FULL_H = 420, ASC_W = 300, ASC_H = 128;

  var WORDS = {
    miniHead: "Next up",
    regionItem: "Item check",
    level: "Level ",
    levelUnknown: "Level unknown",
    legend: "Filled: planned. Dashed: next. Thin: later.",
    itemCheck: "Item check",
    offer: "Next up",
    offerLabel: "Next up and passive tree",
    open: "Progression",
    title: "Progression",
    back: "Back to build",
    next: "Next up",
    skills: "Skills and supports",
    asc: "Ascendancy",
    points: "Points",
    tip: "Hover a node to read it.",
    fullLegend: "Filled: planned by this level. Dashed ring: take next. Thin ring: later. " +
      "Dot: not in the plan. Grey lines: context. Outer ring: new since the last change.",
    treeLabel: "Passive tree",
    ascLabel: "Ascendancy tree",
    noTree: "No tree to draw yet.",
    more: "+{n} more"
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
    return { doc: null, ctx: null, key: null, model: null, loading: null, fails: {},
             mode: null, lastEval: null, evalAt: null, lastLevel: null, lastLine: null,
             pending: false, resync: false, stepped: null, open: false,
             drawn: {}, boxes: {}, args: {}, filled: null };
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
  /* An svg element has no hidden property (HTMLElement only), so it gets
     the attribute, which the page's [hidden] rule hides. */
  function show(n, on) {
    if (!n) { return; }
    if (n.namespaceURI === "http://www.w3.org/2000/svg") {
      if (on) { n.removeAttribute("hidden"); } else { n.setAttribute("hidden", ""); }
      return;
    }
    if (n.hidden === !!on) { n.hidden = !on; }
  }

  function summaryOf(snap) {
    var p = snap && snap.progression;
    return p && typeof p === "object" && typeof p.key === "string" ? p : null;
  }
  function evalOf(snap) {
    var ev = snap && snap.eval;
    var id = ev && typeof ev === "object" ? ev.id : null;
    return typeof id === "string" || typeof id === "number" ? String(id) : "";
  }
  function nowOf(snap) {
    return snap && typeof snap.now === "number" ? snap.now : Date.now() / 1000;
  }
  function hasContent(sum) {
    return !!(sum && (sum.tree || (Array.isArray(sum.next) && sum.next.length)));
  }
  function known(v) { return v !== null && v !== undefined; }

  /* Region I's view for this push (pure, for tests): {mode, pending}.
     The first paint shows the item card (design review PG-12). A new item
     check shows the card. A move (a level-up between two known levels, a
     change between two known source lines, or a move held before) shows
     the progression, unless an item check under HOLD_S old holds it: then
     the mode stays and the move is pending until a later push. */
  function decide(st, sum, evalId, now) {
    if (!hasContent(sum) || st.mode === null) { return { mode: "item", pending: false }; }
    if (evalId && evalId !== st.lastEval) { return { mode: "item", pending: false }; }
    var moved = st.pending ||
      (known(st.lastLevel) && known(sum.level) && sum.level !== st.lastLevel) ||
      (known(st.lastLine) && known(sum.source_line) && sum.source_line !== st.lastLine);
    if (!moved || st.mode === "progress") { return { mode: st.mode, pending: false }; }
    if (evalId && known(st.evalAt) && now - st.evalAt < HOLD_S) {
      return { mode: st.mode, pending: true };
    }
    return { mode: "progress", pending: false };
  }

  function levelWord(level) {
    return typeof level === "number" ? WORDS.level + level : WORDS.levelUnknown;
  }

  /* One push: decide region I's view and flip its marks before the
     regions paint. Idempotent for the same snapshot. */
  function step(doc, snap) {
    if (!snap || S.stepped === snap) { return; }
    S.stepped = snap;
    var sum = summaryOf(snap), evalId = evalOf(snap), now = nowOf(snap);
    if (S.resync) {
      /* back from a hidden page: what moved meanwhile is not news */
      S.resync = false;
      if (sum) { S.lastLevel = sum.level; S.lastLine = sum.source_line; }
    }
    var d = decide(S, sum, evalId, now);
    if (evalId && evalId !== S.lastEval) { S.evalAt = now; }
    S.mode = d.mode;
    S.pending = d.pending;
    S.lastEval = evalId;
    if (sum) {
      if (known(sum.level)) { S.lastLevel = sum.level; }
      if (known(sum.source_line)) { S.lastLine = sum.source_line; }
    }
    flip(doc || S.doc);
  }

  function flip(doc) {
    var region = doc && doc.getElementById ? doc.getElementById("play-i") : null;
    if (!region) { return; }
    var on = S.mode === "progress";
    if (region.getAttribute("data-pg") !== (on ? "on" : "off")) {
      region.setAttribute("data-pg", on ? "on" : "off");
    }
    setText(doc.getElementById("play-i-h"), on ? WORDS.miniHead : WORDS.regionItem);
  }

  /* -- data --------------------------------------------------------- */

  function load(sum) {
    if (!S.ctx || typeof S.ctx.api !== "function" || S.loading === sum.key) { return; }
    if ((S.fails[sum.key] || 0) >= MAX_FAILS) { return; }
    S.loading = sum.key;
    S.ctx.api("GET", PATH).then(function (m) {
      S.loading = null;
      if (!m || typeof m.key !== "string") { S.fails[sum.key] = (S.fails[sum.key] || 0) + 1; return; }
      S.model = m;
      S.key = m.key;
      var d = S.doc;
      if (d && !d.hidden && S.ctx.getSnap) { paint(d, S.ctx.getSnap()); }
    }, function () {
      S.loading = null;
      S.fails[sum.key] = (S.fails[sum.key] || 0) + 1;
    });
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
      S.pending = false;
      flip(doc);
      paintRegion(doc, S.ctx && S.ctx.getSnap ? S.ctx.getSnap() : null);
      var o = doc.getElementById("pg-offer");
      if (o && !o.hidden && o.focus) { o.focus(); }
    });
    foot.appendChild(back);
    box.appendChild(foot);
    region.appendChild(box);
    return box;
  }

  function fillSteps(doc, list, steps, empty, cap, cls) {
    var want = steps.slice(0, cap);
    if (!want.length) { want = [{ kind: "none", text: empty || "" }]; }
    while (list.children.length > want.length) { list.removeChild(list.lastChild); }
    while (list.children.length < want.length) { list.appendChild(el(doc, "li", cls)); }
    want.forEach(function (st, i) {
      var li = list.children[i];
      setText(li, st.text);
      li.setAttribute("title", st.text);
      li.setAttribute("data-kind", st.kind || "");
      li.className = cls + (st.kind === "none" ? " muted" : "");
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
  function follow(doc, node, fn) {
    if (node.__alSized || typeof root.ResizeObserver !== "function") { return; }
    node.__alSized = new root.ResizeObserver(function () { if (!doc.hidden) { fn(); } });
    node.__alSized.observe(node);
  }

  function draw(doc, node, view, mode, defW, defH) {
    var T = tree();
    if (!T || !node) { return null; }
    S.args[node.id] = [view, mode, defW, defH];
    follow(doc, node, function () {
      var a = S.args[node.id];
      if (a) { draw(doc, node, a[0], a[1], a[2], a[3]); }
    });
    var wh = size(node, defW, defH);
    var newIds = S.model && Array.isArray(S.model["new"]) ? S.model["new"] : [];
    var sig = [S.key, mode, Math.round(wh[0]), Math.round(wh[1])].join(" ");
    if (S.drawn[node.id] === sig) { return S.boxes[node.id]; }
    S.drawn[node.id] = sig;
    S.boxes[node.id] = T.render(doc, node, view, { mode: mode, width: wh[0], height: wh[1],
                                                  fresh: newIds });
    return S.boxes[node.id];
  }

  /* PROGRESSION-OFFER: the item card's way to the view, so Play shows
     the tree is there before any level-up moves it. One button, made
     once, absolute at the region's top right (the region's track never
     changes); the item card's head keeps room for it while it shows. */
  function paintOffer(doc, region, want) {
    var b = doc.getElementById("pg-offer");
    if (want && !b) {
      b = el(doc, "button", "secondary btn-24 pg-offer", WORDS.offer);
      b.type = "button";
      b.id = "pg-offer";
      b.setAttribute("aria-label", WORDS.offerLabel);
      b.setAttribute("title", WORDS.offerLabel);
      b.addEventListener("click", function () {
        S.mode = "progress";
        S.pending = false;
        flip(doc);
        paintRegion(doc, S.ctx && S.ctx.getSnap ? S.ctx.getSnap() : null);
        var m = doc.getElementById("pg-mini-item");
        if (m && m.focus) { m.focus(); }
      });
      /* first in the region: read and reached where it is seen, at the
         top, before the item card (design review F2) */
      region.insertBefore(b, region.firstChild);
    }
    show(b, want);
    if (region.getAttribute("data-pg-offer") !== (want ? "on" : "off")) {
      region.setAttribute("data-pg-offer", want ? "on" : "off");
    }
  }

  function paintRegion(doc, snap) {
    var region = doc.getElementById("play-i");
    if (!region) { return; }
    var sum = summaryOf(snap);
    var on = S.mode === "progress" && hasContent(sum);
    var box = on ? buildMini(doc) : doc.getElementById("pg-mini");
    show(box, on);
    paintOffer(doc, region, !on && hasContent(sum));
    if (!on || !box) { return; }
    setText(doc.getElementById("pg-mini-sub"), levelWord(sum.level));
    fillSteps(doc, doc.getElementById("pg-mini-next"), sum.next || [], sum.empty, STEPS,
      "row-title one-line pg-step");
    show(doc.getElementById("pg-mini-item"), true);
    var t = doc.getElementById("pg-mini-tree");
    /* the last model's tree stays drawn while a new key loads (PG-2) */
    var view = S.model && S.model.tree ? S.model.tree : null;
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
    c1.appendChild(el(doc, "p", "row-meta muted pg-legend", WORDS.fullLegend));
    var c2 = el(doc, "div", "pg-col pg-col-side");
    c2.id = "pg-side";
    c2.appendChild(h3(doc, WORDS.next));
    var next = el(doc, "ul", "pg-list");
    next.id = "pg-next";
    c2.appendChild(next);
    c2.appendChild(h3(doc, WORDS.skills));
    var skills = el(doc, "ul", "pg-list");
    skills.id = "pg-skills";
    c2.appendChild(skills);
    c2.appendChild(h3(doc, WORDS.asc, "pg-asc-h"));
    var asc = svg(doc, "pg-asc", "pg-svg pg-asc", WORDS.ascLabel);
    c2.appendChild(asc);
    var ascNone = el(doc, "p", "row-meta muted pg-asc-none");
    ascNone.id = "pg-asc-none";
    show(ascNone, false);
    c2.appendChild(ascNone);
    c2.appendChild(h3(doc, WORDS.points));
    var pts = el(doc, "ul", "pg-list");
    pts.id = "pg-points";
    c2.appendChild(pts);
    body.appendChild(c1);
    body.appendChild(c2);
    card.appendChild(body);
    panel.appendChild(card);
    hover(big, tip, "tree");
    hover(asc, tip, "asc");
    follow(doc, c2, function () { S.filled = null; fitSide(doc); });
    var info = itemInfo();
    if (info && typeof info.attach === "function") { info.attach(card, {}); }
    return card;
  }

  function hover(node, tip, part) {
    var T = tree();
    if (!T || !node.addEventListener) { return; }
    node.addEventListener("pointermove", function (e) {
      var view = S.model && S.model[part];
      var box = S.boxes[node.id];
      if (!view || !box) { return; }
      var r = node.getBoundingClientRect();
      var i = T.hit(view, box, r.width, r.height, e.clientX - r.left, e.clientY - r.top);
      setText(tip, i >= 0 ? T.label(view, i) : WORDS.tip);
      if (i >= 0) { tip.setAttribute("title", T.label(view, i)); }
    });
    node.addEventListener("pointerleave", function () { setText(tip, WORDS.tip); });
  }

  function moreRow(doc, n) {
    return el(doc, "li", "row-meta muted pg-wrap", WORDS.more.replace("{n}", String(n)));
  }

  /* The gem level of a skill row for the popover: the pasted PoB build's
     socket level ("level"); a Kindler row has none (its levels are
     character levels), so it sends none and the popover shows level 1. */
  function gemLevel(r) {
    return typeof r.level === "number" && r.level >= 1 ? r.level : undefined;
  }

  function fillSkills(doc, list, rows, count) {
    var info = itemInfo();
    list.replaceChildren();
    var shown = rows.slice(0, count);
    shown.forEach(function (r) {
      var li = el(doc, "li", "row-meta pg-wrap pg-skill");
      li.appendChild(info && typeof info.button === "function" ? info.button(doc, r.name, gemLevel(r))
        : el(doc, "span", "", r.name));
      var rest = " " + r.meta + "; " + r["with"];
      li.appendChild(el(doc, "span", "muted", rest));
      li.setAttribute("title", r.name + rest);
      list.appendChild(li);
    });
    if (rows.length > shown.length) { list.appendChild(moreRow(doc, rows.length - shown.length)); }
  }

  function fillLines(doc, list, lines, count) {
    list.replaceChildren();
    lines.slice(0, count).forEach(function (t) {
      var li = el(doc, "li", "row-meta pg-wrap", t);
      li.setAttribute("title", t);
      list.appendChild(li);
    });
    if (lines.length > count) { list.appendChild(moreRow(doc, lines.length - count)); }
  }

  function over(node) { return node.scrollHeight > node.clientHeight + 1; }

  /* Fill the skill and point rows, then give rows back (skills first,
     down to one, then points) while the side column would overflow. */
  function fitSide(doc) {
    var m = S.model;
    var side = doc.getElementById("pg-side");
    if (!m || !side || S.filled === m.key) { return; }
    S.filled = m.key;
    var skills = m.skills || [], points = m.points || [];
    var ns = skills.length, np = points.length;
    var sl = doc.getElementById("pg-skills"), pl = doc.getElementById("pg-points");
    fillSkills(doc, sl, skills, ns);
    fillLines(doc, pl, points, np);
    while (over(side) && (ns > 1 || np > 1)) {
      if (ns > 1) { ns -= 1; fillSkills(doc, sl, skills, ns); } else { np -= 1; fillLines(doc, pl, points, np); }
    }
  }

  function paintCard(doc, snap) {
    var card = doc.getElementById("pgbox");
    if (!card || card.hidden) { return; }
    var sum = summaryOf(snap);
    var m = S.model;
    setText(doc.getElementById("pg-source"),
      sum ? sum.source_line + " - " + levelWord(sum.level) : "");
    var note = doc.getElementById("pg-note");
    setText(note, (sum && sum.note) || (m && m.note) || "");
    show(note, !!note.textContent);
    fillSteps(doc, doc.getElementById("pg-next"), (sum && sum.next) || [],
      (sum && sum.empty) || "", STEPS, "row-body one-line pg-step");
    if (!m) { return; }
    fitSide(doc);
    var big = doc.getElementById("pg-tree");
    show(big, !!m.tree);
    if (m.tree) { draw(doc, big, m.tree, "full", FULL_W, FULL_H); }
    setText(doc.getElementById("pg-tip"), m.tree ? WORDS.tip : WORDS.noTree);
    var asc = doc.getElementById("pg-asc");
    show(asc, !!m.asc);
    setText(doc.getElementById("pg-asc-h"), m.asc ? WORDS.asc + ": " + m.asc.name : WORDS.asc);
    if (m.asc) { draw(doc, asc, m.asc, "full", ASC_W, ASC_H); }
    /* nothing to draw: the server's one line says why (PROGRESSION-ASC-EMPTY) */
    var ascNone = doc.getElementById("pg-asc-none");
    setText(ascNone, m.asc ? "" : (m.asc_note || ""));
    show(ascNone, !!(ascNone && ascNone.textContent));
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
      S.filled = null;
      paintCard(doc, S.ctx && S.ctx.getSnap ? S.ctx.getSnap() : null);
      var t = doc.getElementById("pg-title");
      if (focus && t && t.focus) { t.focus(); }
    } else if (focus && btn && btn.focus) { btn.focus(); }
  }

  function wire(doc, ctx) {
    S.doc = doc;
    S.ctx = ctx || {};
    /* decide region I before the regions paint (PG-8): the page's push hook */
    var host = root && root.ALApp && root.ALApp.host;
    if (host && typeof host.onPush === "function") {
      host.onPush(function (s) { step(doc, s); });
    }
    if (doc.addEventListener) {
      doc.addEventListener("visibilitychange", function () { if (doc.hidden) { S.resync = true; } });
    }
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
    step(doc, snap);
    var sum = summaryOf(snap);
    if (!sum) { S.model = null; S.key = null; }
    else if (sum.key !== S.key) { load(sum); }
    paintRegion(doc, snap);
    paintCard(doc, snap);
  }

  function reset() { S = fresh(); }
  function state() { return S; }

  return {
    NAME: NAME, WORDS: WORDS, HOLD_S: HOLD_S, MAX_FAILS: MAX_FAILS, decide: decide,
    hasContent: hasContent, levelWord: levelWord, gemLevel: gemLevel, paint: paint, wire: wire, step: step,
    reset: reset, state: state, setOpen: setOpen,
    spec: { name: NAME, region: REGION, paint: paint, wire: wire }
  };
}));
