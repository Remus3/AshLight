/* AshLight dashboard: region B, the build line (PLAY-TD-15-BUILDLINE; plan 03
   TD-15, F-041; design 0001 section 6).

   Two rows, always in the same place (track 68 px at s = 1):
   - row 1: the state glyph and word at 20 px / 600 ("[+] Build fits",
     "[?] Old build", "[?] Wrong class", "[ ] No build"), then the build
     name and level (16 px, ellipsis, full text in title). While no build
     is loaded it carries the one button "Paste a build" (24 px).
   - row 2 (16 px, muted): the source line or the one-line fix.

   The words come composed from the core: this file reads snap.play.build
   only (server/al/playview.py build_view) and never builds Play wording
   itself, never calls window.ALBuildLive and never calls ALTabs.notify
   (the legacy path keeps that until PLAY-LEGACY-OUT). The build alert is a
   state of this region, never a card in a queue.

   The button shows the tab that holds #build-paste (Build and items) and
   focuses the paste box. The build stays user-pasted text (decision
   0004): no clipboard read, no timer, no network, no live region.

   Registers {name: buildline, region: b, retires: [b-alert]} with
   web/regions.js. UMD like web/tabs.js: CommonJS for node --test,
   window.ALBuildLine in the page. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALBuildLine = api;
    if (root.ALRegions && typeof root.ALRegions.register === "function") {
      root.ALRegions.register(api.spec);
    }
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var NAME = "buildline";
  var REGION = "b";
  var RETIRES = ["b-alert"];
  var PASTE_ID = "build-paste";
  var PASTE_LABEL = "Paste a build";
  var FALLBACK_TAB = "build";
  // the four states of design 0001 section 6 (the kit word stale is not used for Old build)
  var STATES = {
    fits: { glyph: "[+]", word: "Build fits", tone: "neutral" },
    old: { glyph: "[?]", word: "Old build", tone: "warn" },
    wrong_class: { glyph: "[?]", word: "Wrong class", tone: "warn" },
    none: { glyph: "[ ]", word: "No build", tone: "neutral" }
  };

  function isObj(v) { return v !== null && typeof v === "object" && !Array.isArray(v); }
  function str(v) { return typeof v === "string" ? v : ""; }

  /* snap -> what B shows, or null while the snapshot has no play.build.
     The core's own glyph and word are used when they are strings; the
     table above only stands in for a missing one. */
  function model(snap) {
    var play = isObj(snap) && isObj(snap.play) ? snap.play : null;
    var b = play && isObj(play.build) ? play.build : null;
    if (!b) { return null; }
    var key = Object.prototype.hasOwnProperty.call(STATES, b.state) ? b.state : "none";
    var row = STATES[key];
    return {
      state: key,
      tone: row.tone,
      glyph: str(b.glyph) || row.glyph,
      word: str(b.word) || row.word,
      name: key === "none" ? "" : str(b.row1),
      row2: str(b.row2),
      canPaste: b.can_paste === true
    };
  }

  /* The tab id whose panel holds #build-paste (panel-<id>), else "build". */
  function pasteTab(doc) {
    var n = doc && typeof doc.getElementById === "function" ? doc.getElementById(PASTE_ID) : null;
    for (var p = n ? n.parentNode : null; p; p = p.parentNode) {
      var id = typeof p.getAttribute === "function" ? p.getAttribute("id") : p.id;
      if (typeof id === "string" && id.indexOf("panel-") === 0 && id.length > 6) {
        return id.slice(6);
      }
    }
    return FALLBACK_TAB;
  }

  /* The button's act: show the paste tab (no tab focus), focus the box. */
  function showPaste(doc, tabs) {
    var id = pasteTab(doc);
    if (tabs && typeof tabs.show === "function") { tabs.show(doc, id, false); }
    var box = doc && typeof doc.getElementById === "function" ? doc.getElementById(PASTE_ID) : null;
    if (box && typeof box.focus === "function") { box.focus(); }
    return id;
  }

  function slotOf(doc) {
    if (!doc || typeof doc.querySelector !== "function") { return null; }
    return doc.querySelector('#play-b [data-slot="b"]');
  }

  function el(doc, tag, cls, id) {
    var n = doc.createElement(tag);
    if (cls) { n.className = cls; }
    if (id) { n.id = id; }
    return n;
  }

  // the region's nodes, made once by wire() (or the first paint)
  var nodes = { doc: null, root: null, word: null, name: null, button: null, row2: null };
  var wired = { tabs: null };

  function build(doc) {
    if (nodes.doc === doc && nodes.root) { return nodes; }
    var slot = slotOf(doc);
    if (!slot || typeof doc.createElement !== "function") { return null; }
    var root = el(doc, "div", "bl", "bl");
    root.hidden = true;
    var r1 = el(doc, "p", "bl-row1 row-title");
    var word = el(doc, "span", "bl-word", "bl-word");
    var name = el(doc, "span", "bl-name row-body one-line", "bl-name");
    var button = el(doc, "button", "bl-paste secondary btn-24", "bl-paste");
    button.setAttribute("type", "button");
    button.textContent = PASTE_LABEL;
    button.hidden = true;
    var r2 = el(doc, "p", "bl-row2 row-body muted one-line", "bl-row2");
    r1.appendChild(word);
    r1.appendChild(name);
    r1.appendChild(button);
    root.appendChild(r1);
    root.appendChild(r2);
    slot.appendChild(root);
    if (typeof button.addEventListener === "function") {
      button.addEventListener("click", function () { showPaste(doc, wired.tabs); });
    }
    nodes = { doc: doc, root: root, word: word, name: name, button: button, row2: r2 };
    return nodes;
  }

  function setText(n, text) { if (n.textContent !== text) { n.textContent = text; } }
  function setAttr(n, k, v) { if (n.getAttribute(k) !== v) { n.setAttribute(k, v); } }

  /* Paint B from one snapshot (each state push). Idempotent: a node is
     touched only when its text or attribute changes. */
  function paint(doc, snap) {
    var m = model(snap);
    var n = build(doc);
    if (!n) { return null; }
    if (!m) {
      n.root.hidden = true;
      return null;
    }
    setAttr(n.root, "data-state", m.state);
    setAttr(n.root, "data-tone", m.tone);
    setText(n.word, m.glyph + " " + m.word);
    setText(n.name, m.name);
    setAttr(n.name, "title", m.name);
    n.name.hidden = !m.name;
    n.button.hidden = !m.canPaste;
    setText(n.row2, m.row2);
    setAttr(n.row2, "title", m.row2);
    n.row2.hidden = !m.row2;
    n.root.hidden = false;
    return m;
  }

  function wire(doc, ctx) {
    wired.tabs = ctx && ctx.tabs ? ctx.tabs : null;
    build(doc);
  }

  /* Tests only: forget the nodes made for an earlier document. */
  function reset() {
    nodes = { doc: null, root: null, word: null, name: null, button: null, row2: null };
    wired.tabs = null;
  }

  var spec = {
    name: NAME,
    region: REGION,
    retires: RETIRES.slice(),
    wire: wire,
    paint: function (doc, snap) { paint(doc, snap); }
  };

  return {
    NAME: NAME, REGION: REGION, RETIRES: RETIRES, STATES: STATES, PASTE_LABEL: PASTE_LABEL,
    model: model, pasteTab: pasteTab, showPaste: showPaste, paint: paint, wire: wire,
    reset: reset, spec: spec
  };
}));
