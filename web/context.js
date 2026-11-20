/* AshLight dashboard: region C, the context card (PLAY-TD-11-CONTEXT; plan 03
   TD-11, F-068, F-124; sections 3.4 and 3.5).

   Region C shows exactly ONE context for the zone, the mode web/slots.js
   contextMode picks from the snapshot (first match): the zone guide, the
   town search string, the map block or the zone name. The rows come
   composed from the core (snap.play.context, server/al/playcards.py); this
   file only lays them out. Nothing here moves by a timer: the mode changes
   with the zone, by itself.

   Layout (line boxes at s = 1, design 0001 section 3): a title at 20 px /
   600 (26), at most 7 body rows of 22 (6 in the compact class), each one
   line with the ellipsis and its full text in title, and one facts row at
   14 px (20). A Copy row is 32 (the 28 px button). Over 52 words in the
   region (G5, the hidden region heading counted) or over the row count,
   the lowest-priority row leaves first (gear hint, later bonus, layout,
   boss, first bonus, next zone; the title, the objective and the Copy row
   stay). With 7 rows the row that goes first in the compact class is
   marked .ctx-drop and context.css hides it there.

   Modes: guide, town and map are painted from their block; none (and a
   painted mode whose block is missing) shows the zone name with one plain
   row. Campaign hints (snap.campaign.hints, at most 3; design finding
   LO-1) are hint rows: a core guide block carries them already, every
   other painted view adds them from the snapshot, none when it has none. map shows only once the core sets play.map_ok (PLAY-MAP-MODE-ON);
   until then a map zone is mode none. setup, error and idle belong to
   PLAY-TD-12-CONTEXT-SETUP, which registers them with mode(name, painter);
   a mode with no painter hides this slot and leaves the legacy c-setup
   group showing. A painted mode hides that group (and only a group this
   file hid is shown again).

   Copy (F-124, decisions 0014 and 0030): the town or between-maps row
   names the search string in plain words and carries one Copy button. The
   string is written to the clipboard only inside that button's click
   handler, through ALSearch.copy (web/search.js); exactly the string the
   core sent, at most 250 characters, else there is no row. There is no
   clipboard read and nothing is sent to the game. Copied or the Ctrl+C
   fallback is said beside the button; the button's own name gains the
   outcome. The guide is not a live region. ALTabs.notify is not called
   (the legacy path keeps doing that until PLAY-LEGACY-OUT).

   Registers {name: context, region: c, retires: [c-guide]} with
   web/regions.js. UMD like web/tabs.js: CommonJS for node --test
   (app/test/context.test.js), window.ALContext in the page. */
(function (root, factory) {
  "use strict";
  var common = typeof module === "object" && module.exports;
  var slots = common ? require("./slots.js") : root.ALSlots;
  var search = common ? require("./search.js") : null;
  var api = factory(slots, search, root);
  if (common) {
    module.exports = api;
  } else {
    root.ALContext = api;
    if (root.ALRegions && typeof root.ALRegions.register === "function") {
      root.ALRegions.register(api.spec);
    }
  }
}(typeof self !== "undefined" ? self : this, function (S, SEARCH, ROOT) {
  "use strict";

  var NAME = "context";
  var REGION = "c";
  var RETIRES = ["c-guide"];
  var LEGACY_SETUP = "c-setup";
  var OWN = ["guide", "town", "map", "none"];   // painted here
  var MODES = ["setup", "error", "idle", "map", "town", "guide", "none"];
  var ROWS = 7;          // body rows, full class
  var ROWS_COMPACT = 6;  // the compact class hides the .ctx-drop row
  var WORD_CAP = 52;     // G5: region C, its hidden heading included
  var SEARCH_MAX = 250;  // decision 0030: the game's search box limit
  var HINTS = 3;         // campaign hint rows (snap.campaign.hints)
  var COPY_LABEL = "Copy";
  var COPIED = "Copied";
  var FALLBACK = "Press Ctrl+C";
  var FALLBACK_SAID = "can't copy here, the text is selected, press Ctrl+C";
  var NO_ZONE = "No zone yet";
  var NO_ZONE_ROW = "Enter a zone in game and its guide shows here.";
  var NO_GUIDE_ROW = "No guide for this zone.";
  var HID = "data-context-hid";

  function isObj(v) { return v !== null && typeof v === "object" && !Array.isArray(v); }
  function isFn(v) { return typeof v === "function"; }
  function str(v) { return typeof v === "string" ? v : ""; }
  function isNum(v) { return typeof v === "number" && isFinite(v); }

  function words(text) {
    return str(text).split(/\s+/).filter(function (w) { return /[A-Za-z0-9]/.test(w); }).length;
  }

  /* ---- the model (pure) ------------------------------------------------- */

  /* A copy row is kept only with an exact, non-empty string of at most 250
     characters (decision 0030); the core already filters, this is the
     renderer's own guard. */
  function copyOk(row) {
    var t = row && row.copy;
    return typeof t === "string" && t.length > 0 && t.length <= SEARCH_MAX;
  }

  /* The drop rank of a row: a higher rank leaves first; -1 never leaves. */
  function rank(row, firstBonus) {
    var kind = str(row.kind);
    if (kind === "copy" || kind === "objective") { return -1; }
    if (kind === "hint") { return /^Boss:/.test(str(row.text)) ? 3 : 7; }
    if (kind === "bonus") { return firstBonus ? 2 : 6; }
    if (kind === "layout") { return 4; }
    if (kind === "text") { return 5; }
    if (kind === "next") { return 1; }
    return 5;
  }

  /* The index of the row that leaves first, or -1. Ties: the later row. */
  function dropAt(rows) {
    var best = -1;
    var bestRank = -1;
    var seenBonus = false;
    rows.forEach(function (r, i) {
      var first = r.kind === "bonus" && !seenBonus;
      if (r.kind === "bonus") { seenBonus = true; }
      var k = rank(r, first);
      if (k >= 0 && k >= bestRank) { best = i; bestRank = k; }
    });
    return best;
  }

  function cleanRows(list) {
    return (Array.isArray(list) ? list : []).filter(function (r) {
      if (!isObj(r) || !str(r.text)) { return false; }
      return r.kind !== "copy" || copyOk(r);
    }).map(function (r) {
      var out = { kind: str(r.kind) || "text", text: r.text, full: str(r.full) || r.text };
      if (r.kind === "copy") {
        out.copy = r.copy;
        out.id = str(r.id);
      }
      return out;
    });
  }

  function viewWords(v) {
    var n = words(v.title) + words(v.facts);
    v.rows.forEach(function (r) {
      n += words(r.text);
      if (r.kind === "copy") { n += words(COPY_LABEL) + words(COPIED); }
    });
    return n;
  }

  /* The boss hint in one row, as the core words it in a guide block
     (playcards._boss_text): the element and the build's resistance from
     the hint's own sentence; the sentence stays the row's full text. */
  function bossText(text) {
    var el = /mostly (\w+) damage/.exec(text);
    if (!el) { return text; }
    var res = /has (-?\d+)% /.exec(text);
    return "Boss: " + el[1] + " damage. Your " + el[1] + " res: " +
      (res ? res[1] + "%." : "unknown.");
  }

  /* snap.campaign.hints (server/al/campaign.py view): at most HINTS rows
     of kind "hint", none when the snapshot carries none. */
  function hintRows(snap) {
    var camp = snap && isObj(snap.campaign) ? snap.campaign : null;
    var list = camp && Array.isArray(camp.hints) ? camp.hints : [];
    var out = [];
    list.forEach(function (h) {
      if (out.length >= HINTS || !isObj(h)) { return; }
      var full = str(h.text).trim();
      if (!full) { return; }
      var text = h.id === "boss" ? bossText(full) : full;
      out.push({ kind: "hint", text: text, full: full });
    });
    return out;
  }

  /* The zone name with one plain row: mode none, and a painted mode whose
     block did not come. */
  function noneView(snap) {
    var zone = str(snap.zone).trim();
    var row = NO_ZONE_ROW;
    if (zone) {
      row = isNum(snap.area_level) && snap.area_level > 0
        ? "Area level " + snap.area_level + "." : NO_GUIDE_ROW;
    }
    return { mode: "none", title: zone || NO_ZONE, full: zone || NO_ZONE,
             rows: [{ kind: "text", text: row, full: row }], facts: "" };
  }

  /* What C shows for one snapshot: {mode, own, title, full, rows, facts,
     drop, block}. own is false for a mode painted elsewhere (setup, error,
     idle); headWords: the words of the hidden region heading (default 2). */
  function model(snap, headWords) {
    var s = isObj(snap) ? snap : null;
    var mode = S && isFn(S.contextMode) ? S.contextMode(s) : "none";
    var play = s && isObj(s.play) ? s.play : {};
    var blocks = isObj(play.context) ? play.context : {};
    var block = isObj(blocks[mode]) ? blocks[mode] : null;
    if (OWN.indexOf(mode) < 0) {
      return { mode: mode, own: false, block: block };
    }
    var v;
    var fromBlock = !(mode === "none" || !block || !str(block.title));
    if (!fromBlock) {
      v = noneView(s || {});
      v.mode = mode;
    } else {
      v = { mode: mode, title: block.title, full: str(block.full) || block.title,
            rows: cleanRows(block.rows), facts: str(block.facts) };
    }
    v.own = true;
    v.block = block;
    v.rows = v.rows.slice(0, ROWS);
    /* LO-1: the campaign hints come as hint rows. A guide block from the
       core already holds them (playcards.guide_block ranks and drops them
       itself); every other painted view takes them from the snapshot. */
    if (!(mode === "guide" && fromBlock)) {
      v.rows = v.rows.concat(hintRows(s));
    }
    var cap = WORD_CAP - (isNum(headWords) ? headWords : 2);
    while (v.rows.length > ROWS) {
      var over = dropAt(v.rows);
      if (over < 0) { break; }
      v.rows.splice(over, 1);
    }
    while (v.rows.length && viewWords(v) > cap) {
      var at = dropAt(v.rows);
      if (at < 0) { break; }
      v.rows.splice(at, 1);
    }
    v.drop = v.rows.length > ROWS_COMPACT ? dropAt(v.rows) : -1;
    if (v.drop < 0 && v.rows.length > ROWS_COMPACT) { v.drop = v.rows.length - 1; }
    return v;
  }

  /* ---- painters ---------------------------------------------------------- */

  var painters = {};  // mode -> painter(doc, pane, snap, now, ctx, block)

  /* PLAY-TD-12-CONTEXT-SETUP registers setup, error and idle here; a
     painter may also replace a mode painted here. null removes it. */
  function mode(name, painter) {
    if (MODES.indexOf(name) < 0) { return false; }
    if (painter === null || painter === undefined) {
      delete painters[name];
      return true;
    }
    if (!isFn(painter)) { return false; }
    painters[name] = painter;
    return true;
  }

  function hasPainter(name) {
    return isFn(painters[name]) || OWN.indexOf(name) >= 0;
  }

  /* ---- the DOM ------------------------------------------------------------ */

  var nodes = { doc: null, slot: null, root: null, panes: {} };
  var env = { nav: null, ctx: null };

  function navigatorOf() {
    if (env.nav) { return env.nav; }
    return ROOT && ROOT.navigator ? ROOT.navigator : null;
  }

  function searchApi() {
    if (SEARCH) { return SEARCH; }
    return ROOT && ROOT.ALSearch ? ROOT.ALSearch : null;
  }

  function el(doc, tag, cls) {
    var n = doc.createElement(tag);
    if (cls) { n.className = cls; }
    return n;
  }

  function setText(n, text) { if (n.textContent !== text) { n.textContent = text; } }
  function setAttr(n, k, v) { if (n.getAttribute(k) !== v) { n.setAttribute(k, v); } }
  function setHidden(n, h) { if (n.hidden !== h) { n.hidden = h; } }

  function clear(n) {
    if (isFn(n.replaceChildren)) {
      n.replaceChildren();
    } else {
      while (n.children && n.children.length) { n.removeChild(n.children[0]); }
      n.textContent = "";
    }
  }

  function slotOf(doc) {
    if (!doc || !isFn(doc.querySelector)) { return null; }
    return doc.querySelector('#play-c [data-slot="c"]');
  }

  function build(doc) {
    if (nodes.doc === doc && nodes.root) { return nodes; }
    var slot = slotOf(doc);
    if (!slot || !isFn(doc.createElement)) { return null; }
    var root = el(doc, "div", "ctx");
    root.id = "ctx";
    root.hidden = true;
    slot.appendChild(root);
    nodes = { doc: doc, slot: slot, root: root, panes: {} };
    return nodes;
  }

  function pane(n, name) {
    if (n.panes[name]) { return n.panes[name]; }
    var p = el(n.doc, "div", "ctx-pane");
    p.setAttribute("data-mode", name);
    p.hidden = true;
    n.root.appendChild(p);
    n.panes[name] = p;
    return p;
  }

  /* The legacy setup group: hidden while a painted mode shows; shown
     again only when this file was the one that hid it. */
  function legacySetup(doc, show) {
    if (!isFn(doc.querySelectorAll)) { return; }
    var list = doc.querySelectorAll("[data-legacy]") || [];
    for (var i = 0; i < list.length; i++) {
      var g = list[i];
      if (!g || g.getAttribute("data-legacy") !== LEGACY_SETUP) { continue; }
      if (show) {
        if (g.getAttribute(HID) === "yes") {
          g.hidden = false;
          if (isFn(g.removeAttribute)) { g.removeAttribute(HID); } else { g.setAttribute(HID, ""); }
        }
      } else if (g.hidden !== true) {
        g.hidden = true;
        g.setAttribute(HID, "yes");
      }
    }
  }

  function copyRow(doc, r) {
    var row = el(doc, "div", "ctx-copy");
    var label = el(doc, "span", "ctx-copy-label row-body one-line");
    label.textContent = r.text;
    label.setAttribute("title", r.full);
    var btn = el(doc, "button", "secondary btn-28 ctx-copy-btn");
    btn.setAttribute("type", "button");
    btn.textContent = COPY_LABEL;
    var name = "Copy " + r.text + " search string";
    btn.setAttribute("aria-label", name);
    var said = el(doc, "span", "ctx-said row-body muted");
    row.appendChild(label);
    row.appendChild(btn);
    row.appendChild(said);
    function tell(text, state) {
      said.textContent = text;
      btn.setAttribute("aria-label", name + " (" + state + ")");
    }
    btn.addEventListener("click", function () {
      var api = searchApi();
      var fail = function () {
        /* the string itself, selected, so the player can press Ctrl+C */
        label.textContent = r.copy;
        selectText(doc, label);
        tell(FALLBACK, FALLBACK_SAID);
      };
      if (!api || !isFn(api.copy)) { fail(); return; }
      api.copy(r.copy, navigatorOf(), function () { tell(COPIED, "copied"); }, fail);
    });
    return row;
  }

  function selectText(doc, node) {
    var sel = isFn(doc.getSelection) ? doc.getSelection() : null;
    if (!sel || !isFn(doc.createRange)) { return; }
    var range = doc.createRange();
    range.selectNodeContents(node);
    sel.removeAllRanges();
    sel.addRange(range);
  }

  /* Fill a pane from a view {title, full, rows, facts, drop}. Rebuilt only
     when the view changes, so a focused Copy button and its word stay. */
  function renderView(doc, p, v) {
    var key = JSON.stringify([v.title, v.full, v.rows, v.facts, v.drop]);
    if (p.getAttribute("data-key") === key) { return false; }
    clear(p);
    var h = el(doc, "h3", "ctx-title row-title one-line");
    h.textContent = v.title;
    h.setAttribute("title", v.full || v.title);
    p.appendChild(h);
    if (v.rows.length) {
      var list = el(doc, "div", "ctx-rows");
      v.rows.forEach(function (r, i) {
        var n;
        if (r.kind === "copy") {
          n = copyRow(doc, r);
        } else {
          n = el(doc, "p", "ctx-row row-body one-line");
          n.textContent = r.text;
          n.setAttribute("title", r.full);
          /* PC-1: a bonus row's cue is its edge, never the colour alone */
          if (r.kind === "bonus") { n.className += " edge"; }
        }
        n.setAttribute("data-kind", r.kind);
        if (i === v.drop) { n.className += " ctx-drop"; }
        list.appendChild(n);
      });
      p.appendChild(list);
    }
    if (v.facts) {
      var f = el(doc, "p", "ctx-facts row-meta muted one-line");
      f.textContent = v.facts;
      f.setAttribute("title", v.facts);
      p.appendChild(f);
    }
    p.setAttribute("data-key", key);
    return true;
  }

  function headWords(doc) {
    var h = doc && isFn(doc.getElementById) ? doc.getElementById("play-c-h") : null;
    return h ? words(h.textContent) : 2;
  }

  /* Paint C from one snapshot (each state push). Returns the model. */
  function paint(doc, snap, now, ctx) {
    var n = build(doc);
    if (!n) { return null; }
    var m = model(snap, headWords(doc));
    var show = hasPainter(m.mode);
    setHidden(n.slot, !show);
    legacySetup(doc, !show);
    if (!show) {
      setHidden(n.root, true);
      return m;
    }
    var p = pane(n, m.mode);
    Object.keys(n.panes).forEach(function (k) { setHidden(n.panes[k], k !== m.mode); });
    if (isFn(painters[m.mode])) {
      painters[m.mode](doc, p, snap, now, ctx || env.ctx, m.block);
    } else {
      renderView(doc, p, m);
    }
    setAttr(n.root, "data-mode", m.mode);
    setHidden(n.root, false);
    return m;
  }

  function wire(doc, ctx) {
    env.ctx = ctx || null;
    build(doc);
  }

  /* Tests only: forget the nodes, painters and navigator. */
  function reset(opts) {
    nodes = { doc: null, slot: null, root: null, panes: {} };
    painters = {};
    env = { nav: opts && opts.nav ? opts.nav : null, ctx: null };
  }

  var spec = {
    name: NAME,
    region: REGION,
    retires: RETIRES.slice(),
    wire: wire,
    paint: function (doc, snap, now, ctx) { paint(doc, snap, now, ctx); }
  };

  return {
    NAME: NAME, REGION: REGION, RETIRES: RETIRES, MODES: MODES, OWN: OWN,
    ROWS: ROWS, ROWS_COMPACT: ROWS_COMPACT, WORD_CAP: WORD_CAP, SEARCH_MAX: SEARCH_MAX,
    COPIED: COPIED, FALLBACK: FALLBACK, NO_ZONE: NO_ZONE,
    model: model, mode: mode, hasPainter: hasPainter, renderView: renderView,
    paint: paint, wire: wire, reset: reset, words: words, spec: spec
  };
}));
