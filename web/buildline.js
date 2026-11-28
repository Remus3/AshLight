/* AshLight dashboard: region B, the build line (PLAY-TD-15-BUILDLINE; plan 03
   TD-15, F-041; design 0001 section 6).

   Two rows, always in the same place (track 68 px at s = 1):
   - row 1: the state glyph and word at 20 px / 600 ("[+] Build fits",
     "[?] Old build", "[?] Wrong class", "[ ] No build"), then the build
     name and level (16 px, ellipsis, full text in title). While no build
     is loaded it carries the one button "Paste a build" (28 px).
   - row 2 (16 px, muted): the source line or the one-line fix.

   The words come composed from the core: this file reads snap.play.build
   only (server/al/playview.py build_view) and never builds Play wording
   itself, never calls window.ALBuildLive and never calls ALTabs.notify
   (the legacy path keeps that until PLAY-LEGACY-OUT). The build alert is a
   state of this region, never a card in a queue.

   The button shows the tab that holds #build-paste (Build and items) and
   focuses the paste box. ACTIVE-BUILD-PICK (decision 0096): in its place,
   when the core composes one (play.build.switch), one switch button,
   "Use Kindler plan" or "Use pasted build", posts the player's click to
   POST /api/build-source (ctx.api); the next state push repaints B. A
   refusal says why: the answer's fixed reason word picks the core's own
   sentence (server/al/text/buildsource.py REASONS), else the general
   line. When the switch hides while it holds focus, focus moves to the
   paste button that takes its place, else to the region's heading
   (BUILD-SWITCH-COPY). The build stays user-pasted text (decision
   0004): no clipboard read, no timer, no live region, and no request but
   the switch's one POST through ctx.api.

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
  var SOURCE_PATH = "/api/build-source"; // ACTIVE-BUILD-PICK (decision 0096)
  // BUILD-SWITCH-COPY: a refusal with one of these reason words says the
  // core's sentence after this lead; the words are the core's
  // (text/buildsource.py REASONS), never free text from elsewhere
  var SWITCH_REFUSED = "The build didn't switch. ";
  var SWITCH_FAILED = SWITCH_REFUSED + "Try again.";
  var REASONS = ["bad", "no_character", "no_result"];
  var HEADING_ID = "play-b-h";
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
      canPaste: b.can_paste === true,
      // ACTIVE-BUILD-PICK: the one switch between the pasted build and a
      // Kindler plan ({label, use, id}), composed by the core, or null
      switchTo: isObj(b.switch) && str(b.switch.label) &&
        (b.switch.use === "pasted" || b.switch.use === "kindler")
        ? { label: str(b.switch.label), use: b.switch.use, id: str(b.switch.id) } : null
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
  var nodes = { doc: null, root: null, word: null, name: null, button: null, row2: null,
    swap: null };
  var wired = { tabs: null, api: null, want: null };

  /* ACTIVE-BUILD-PICK: the switch's act, one POST /api/build-source; the
     next state push repaints B. A refusal is said on the page's polite
     line when the page has one. */
  function useSource(want) {
    if (!want || typeof wired.api !== "function") { return null; }
    var body = want.use === "kindler" ? { use: "kindler", id: want.id } : { use: "pasted" };
    return wired.api("POST", SOURCE_PATH, body).then(function (r) { return r; }, function (e) {
      var t = wired.tabs;
      if (t && typeof t.say === "function") { t.say(nodes.doc, refusedLine(e)); }
      return null;
    });
  }

  /* The line a failed switch says: the core's sentence for a known
     reason word, else the general line (no reach, no body, an unknown
     word). */
  function refusedLine(e) {
    var b = e && isObj(e.body) ? e.body : null;
    if (b && REASONS.indexOf(b.reason) >= 0 && str(b.error) && b.error.length <= 120) {
      return SWITCH_REFUSED + b.error;
    }
    return SWITCH_FAILED;
  }

  /* BUILD-SWITCH-COPY: the switch is about to hide while it holds focus;
     move focus to the paste button when it shows, else to the region's
     heading (made focusable by script only, tabindex -1). The caller
     checks focus before it hides the switch, so a browser's own focus
     fix-up cannot win the race. */
  function hasFocus(doc, n) { return !!doc && doc.activeElement === n.swap && !n.swap.hidden; }

  function keepPlace(doc, n, noButton) {
    var to = !noButton && n.button && !n.button.hidden ? n.button : null;
    if (!to && typeof doc.getElementById === "function") {
      to = doc.getElementById(HEADING_ID);
      if (to && to.getAttribute("tabindex") === null) { to.setAttribute("tabindex", "-1"); }
    }
    if (to && typeof to.focus === "function") { to.focus(); }
    return to;
  }

  function build(doc) {
    if (nodes.doc === doc && nodes.root) { return nodes; }
    var slot = slotOf(doc);
    if (!slot || typeof doc.createElement !== "function") { return null; }
    // the slot is the build line itself (PLAY-FIT-G5-TOTALS: no wrapper)
    var root = slot;
    if ((" " + root.className + " ").indexOf(" bl ") < 0) {
      root.className = root.className ? root.className + " bl" : "bl";
    }
    root.id = "bl";
    root.hidden = true;
    var r1 = el(doc, "p", "bl-row1 row-title");
    var word = el(doc, "span", "bl-word", "bl-word");
    var name = el(doc, "span", "bl-name row-body one-line", "bl-name");
    var button = el(doc, "button", "bl-paste secondary btn-28", "bl-paste");
    button.setAttribute("type", "button");
    button.textContent = PASTE_LABEL;
    button.hidden = true;
    var swap = el(doc, "button", "bl-swap secondary btn-28", "bl-swap");
    swap.setAttribute("type", "button");
    swap.hidden = true;
    var r2 = el(doc, "p", "bl-row2 row-body muted one-line", "bl-row2");
    r1.appendChild(word);
    r1.appendChild(name);
    r1.appendChild(button);
    r1.appendChild(swap);
    root.appendChild(r1);
    root.appendChild(r2);
    if (typeof button.addEventListener === "function") {
      button.addEventListener("click", function () { showPaste(doc, wired.tabs); });
      swap.addEventListener("click", function () { useSource(wired.want); });
    }
    nodes = { doc: doc, root: root, word: word, name: name, button: button, row2: r2,
      swap: swap };
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
      var lost = hasFocus(doc, n);
      n.swap.hidden = true;
      n.root.hidden = true;
      if (lost) { keepPlace(doc, n, true); }
      return null;
    }
    setAttr(n.root, "data-state", m.state);
    setAttr(n.root, "data-tone", m.tone);
    setText(n.word, m.glyph + " " + m.word);
    setText(n.name, m.name);
    setAttr(n.name, "title", m.name);
    n.name.hidden = !m.name;
    n.button.hidden = !m.canPaste;
    wired.want = m.switchTo;
    if (m.switchTo) { setText(n.swap, m.switchTo.label); }
    var hide = !m.switchTo || m.canPaste;
    var lost = hide && hasFocus(doc, n);
    n.swap.hidden = hide;
    if (lost) { keepPlace(doc, n, false); }
    setText(n.row2, m.row2);
    setAttr(n.row2, "title", m.row2);
    n.row2.hidden = !m.row2;
    n.root.hidden = false;
    return m;
  }

  function wire(doc, ctx) {
    wired.tabs = ctx && ctx.tabs ? ctx.tabs : null;
    wired.api = ctx && typeof ctx.api === "function" ? ctx.api : null;
    build(doc);
  }

  /* Tests only: forget the nodes made for an earlier document. */
  function reset() {
    nodes = { doc: null, root: null, word: null, name: null, button: null, row2: null,
      swap: null };
    wired.tabs = null;
    wired.api = null;
    wired.want = null;
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
    useSource: useSource, SOURCE_PATH: SOURCE_PATH, refusedLine: refusedLine,
    REASONS: REASONS,
    reset: reset, spec: spec
  };
}));
