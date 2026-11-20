/* AshLight dashboard: tabs (UI-GLANCE). The page is a few tabs instead of
   one long column, so nothing needs a scroll at 1080p or in the ~1280x800
   desktop window. Play is the primary tab: the 7 Play regions (strip,
   context, feed, notice, build line, item check, kept checks).
   ARIA tablist (WAI-ARIA APG "tabs with automatic activation"): Left /
   Right / Home / End move between tabs, one Tab stop for the row.
   The picked tab is remembered per viewer in localStorage (try/catch; the
   page works without it). ZERO-CLICK: a new item check, trade request or
   build alert shows Play again by itself (notify, called only by the
   news hook of web/regions.js), unless the player is working in another
   tab (focus inside it); then the Play tab carries a "new" word instead.
   Nothing animates (design 0001 rule 3); a card, trade or notice never
   moves focus, and the automatic return moves it only from the tab row
   to the Play tab (notify, G-13).
   PLAY-TD-19B-FOUR-TABS (TD-19, F-067): four tabs, Play, Build and items,
   Run, Settings; Items and prices merged into Build and items, and a
   remembered "items" opens Build and items (then "build" is remembered).
   The slot other code fills: fill(doc, "zone-guide", node), the zone
   guide in the Run tab's Act times card (PLAY-LEGACY-OUT-2 moved it off
   Play); see the comment in web/index.html.
   UMD: CommonJS for node --test (app/test/tabs.test.js), window.ALTabs
   for the page. No timers, no network. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALTabs = api;
    if (typeof document !== "undefined") {
      var go = function () {
        var store = null;
        try { store = root.localStorage; } catch (e) { store = null; }
        api.start(document, store);
      };
      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", go);
      } else {
        go();
      }
    }
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var TABS = ["play", "build", "run", "settings"];
  var PRIMARY = "play";
  var STORE_KEY = "ashlight.tab";
  var SLOTS = ["zone-guide"];
  var GRACE_MS = 10000; // a click, key or scroll in the shown tab holds it
  /* retired tab ids -> the tab that now holds their cards */
  var MOVED = { items: "build" };

  /* A stored value -> a known tab id (anything else gives Play). A retired
     id gives the tab its cards moved to; show() then stores that id, so
     the old value is mapped once. */
  function pick(stored) {
    if (typeof stored === "string" && Object.prototype.hasOwnProperty.call(MOVED, stored)) {
      return MOVED[stored];
    }
    return TABS.indexOf(stored) >= 0 ? stored : PRIMARY;
  }

  /* Arrow-key move in the tab row: key name, current id -> next id or null. */
  function step(key, current) {
    var i = TABS.indexOf(current);
    if (i < 0) { i = 0; }
    var n = TABS.length;
    if (key === "ArrowRight") { return TABS[(i + 1) % n]; }
    if (key === "ArrowLeft") { return TABS[(i - 1 + n) % n]; }
    if (key === "Home") { return TABS[0]; }
    if (key === "End") { return TABS[n - 1]; }
    return null;
  }

  /* Auto-switch rule. ctx: {current, focusTab: the tab whose panel holds
     focus or null, pageFocused, recent: the player clicked, typed or
     scrolled in the shown tab or the tab row within GRACE_MS}. Switch
     when Play is not shown and the player is not working in the shown
     tab: the page has no focus (the game has it), or focus is outside the
     shown panel and nothing was done there just now. */
  function shouldSwitch(ctx) {
    if (ctx.current === PRIMARY) { return false; }
    if (!ctx.pageFocused) { return true; }
    if (ctx.recent) { return false; }
    return ctx.focusTab !== ctx.current;
  }

  function readStore(store) {
    if (!store) { return null; }
    try { return store.getItem(STORE_KEY); } catch (e) { return null; }
  }

  function writeStore(store, id) {
    if (!store) { return; }
    try { store.setItem(STORE_KEY, id); } catch (e) { /* private window */ }
  }

  var state = { doc: null, store: null, current: PRIMARY, marks: {}, touched: -Infinity,
    clock: function () { return Date.now(); } };

  function tab(doc, id) { return doc.getElementById("tab-" + id); }
  function panel(doc, id) { return doc.getElementById("panel-" + id); }

  /* Paint each tab's mark word; the shown tab never carries one. */
  function paintMarks(doc) {
    TABS.forEach(function (t) {
      var b = tab(doc, t);
      var m = b && b.querySelector ? b.querySelector(".tab-mark") : null;
      if (!m) { return; }
      var word = t === state.current ? "" : (state.marks[t] || "");
      if (m.textContent !== word) { m.textContent = word; }
      m.hidden = !word;
    });
  }

  /* Show one tab. focus: also move focus to its tab (keyboard use only).
     Showing Play clears its "new" word (the news is now in view). */
  function show(doc, id, focus) {
    id = pick(id);
    TABS.forEach(function (t) {
      var b = tab(doc, t);
      var p = panel(doc, t);
      var on = t === id;
      if (b) {
        b.setAttribute("aria-selected", on ? "true" : "false");
        b.setAttribute("tabindex", on ? "0" : "-1");
      }
      if (p) { p.hidden = !on; }
    });
    state.current = id;
    if (id === PRIMARY) { delete state.marks[PRIMARY]; news(doc, ""); }
    if (doc === state.doc) { writeStore(state.store, id); }
    paintMarks(doc);
    if (focus) {
      var b = tab(doc, id);
      if (b && b.focus) { b.focus(); }
    }
    return id;
  }

  /* A short word beside a tab's name ("new", "fix"); "" clears it. The
     word is kept while that tab is shown and painted again when it is not. */
  function mark(doc, id, word) {
    if (TABS.indexOf(id) < 0) { return; }
    if (word) { state.marks[id] = word; } else { delete state.marks[id]; }
    paintMarks(doc);
  }

  /* Which tab's panel holds the focused element, or null. */
  function focusTab(doc) {
    var a = doc.activeElement;
    if (!a) { return null; }
    for (var i = 0; i < TABS.length; i++) {
      var p = panel(doc, TABS[i]);
      if (p && p.contains && p.contains(a)) { return TABS[i]; }
    }
    return null;
  }

  /* Focus sits on the tab row (one of the tab buttons): the only place the
     automatic return may move focus from (G-13, F-096). */
  function focusOnRow(doc) {
    var a = doc.activeElement;
    if (!a) { return false; }
    for (var i = 0; i < TABS.length; i++) {
      if (tab(doc, TABS[i]) === a) { return true; }
    }
    var row = doc.getElementById("tabs");
    return !!(row && row.contains && row !== a && row.contains(a));
  }

  /* "trade request" -> "Trade request" (the start of a sentence). */
  function said(what) {
    return what ? what.charAt(0).toUpperCase() + what.slice(1) : "";
  }

  /* The header's polite line (visually hidden): "New on Play: <what>."
     while Play stays hidden, "Showing Play. <What>." once on the
     automatic return. The same text twice is cleared and written again,
     so it is said again. */
  function news(doc, text) {
    var n = doc.getElementById("tab-news");
    if (!n) { return; }
    if (text && n.textContent === text) { n.textContent = ""; }
    if (n.textContent !== text) { n.textContent = text; }
  }

  /* Something new for Play arrived. what: the news words of
     web/regions.js ("item check", "trade request", "build alert", or
     several joined, e.g. "trade request and build alert"), said in the
     header line.
     PLAY-TD-22B-TAB-FOCUS (TD-22, F-096, design G-13): the automatic
     return never fires within GRACE_MS of a click, key press or scroll in
     the shown tab or the tab row, whether or not the page has focus, so a
     player arrowing across the tabs is never pulled away. When it fires,
     focus moves to the Play tab only if it sat on the tab row; a focus
     inside a panel is never moved. The return is said once in the polite
     header line: "Showing Play. <What>." */
  function notify(doc, what) {
    doc = doc || state.doc;
    if (!doc) { return false; }
    var ctx = {
      current: state.current,
      focusTab: focusTab(doc),
      pageFocused: typeof doc.hasFocus === "function" ? doc.hasFocus() : false,
      recent: state.clock() - state.touched < GRACE_MS
    };
    if (!ctx.recent && shouldSwitch(ctx)) {
      show(doc, PRIMARY, focusOnRow(doc));
      news(doc, what ? "Showing Play. " + said(what) + "." : "Showing Play.");
      return true;
    }
    if (state.current !== PRIMARY) {
      mark(doc, PRIMARY, "new");
      news(doc, "New on Play: " + (what || "news") + ".");
    }
    return false;
  }

  /* Fill a slot (zone-guide) with a node, or empty it with null; filling
     it is never news for Play.
     The node must carry its own words: an edge or colour of the slot only
     repeats them (design 0001, never colour alone). */
  function fill(doc, id, node) {
    if (SLOTS.indexOf(id) < 0) { return; }
    var box = doc.getElementById(id);
    if (!box) { return; }
    if (node) { box.replaceChildren(node); } else { box.replaceChildren(); }
    box.hidden = !node;
  }

  function start(doc, store) {
    var row = doc.getElementById("tabs");
    if (!row) { return null; }
    state.doc = doc;
    state.store = store;
    state.marks = {};
    state.touched = -Infinity;
    /* the player's own use of the shown tab or the tab row holds it */
    var touch = function (e) {
      var p = panel(doc, state.current);
      var t = e && e.target;
      if (t && ((p && p.contains && p.contains(t)) || (row.contains && row.contains(t)))) {
        state.touched = state.clock();
      }
    };
    ["pointerdown", "keydown", "wheel"].forEach(function (k) {
      if (doc.addEventListener) { doc.addEventListener(k, touch, true); }
    });
    TABS.forEach(function (t) {
      var b = tab(doc, t);
      if (!b) { return; }
      b.addEventListener("click", function () { show(doc, t, false); });
    });
    row.addEventListener("keydown", function (e) {
      if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) { return; } // Alt+Left is Back
      var next = step(e.key, state.current);
      if (!next) { return; }
      e.preventDefault();
      show(doc, next, true);
    });
    show(doc, pick(readStore(store)), false);
    return state;
  }

  function current() { return state.current; }

  /* tests only: a fake clock */
  function setClock(fn) { state.clock = fn; }

  return { TABS: TABS, PRIMARY: PRIMARY, STORE_KEY: STORE_KEY, SLOTS: SLOTS,
    pick: pick, step: step, shouldSwitch: shouldSwitch, show: show, mark: mark,
    notify: notify, fill: fill, start: start, current: current, setClock: setClock,
    GRACE_MS: GRACE_MS };
}));
