/* AshLight dashboard: collapsible cards (UI-CARD-COLLAPSE; decision 0082
   part 3 and its amendment 2026-11-19).

   Only in the desktop client's companion window (window.alClient present,
   decision 0041): each card of Build and items and of Run gets one button
   at the end of its title row (aria-expanded, aria-controls, a chevron
   plus visually hidden "Collapse <card>" / "Expand <card>", a 24 px
   target). A collapsed card shows its title row only. A plain browser
   shows every card open, with no button, no state and no request. Play's
   regions and Settings never collapse.

   Layout: in the cockpit grid (3 x 2 cards) a column holds two cards. The
   panel gets class cc-on and four row tracks (title row, 1fr, 1fr, title
   row; web/app.css); each column cell gets data-cc-col (1..3) and data-cc
   (cells() below), so an open card whose column-mate is collapsed spans
   the freed tracks. That card carries data-fit="tall" while the cockpit
   classes hold, and the pagers (web/pager.js fitRows, refit; web/search.js
   relayout) show the rows that fit. In the flow class the column simply
   gains the room.

   State: the core's ops/runtime/ui_layout.json through the token-gated
   GET / PUT /api/ui/layout (read once per connect, one PUT per click); no
   localStorage. A missing answer means every card is open. An alert (a
   new build alert, a new death, a new trade request) opens its card for
   that alert without changing the saved state; it stays open until the
   player's click, since nothing collapses by itself. Cards are keyed by
   their section id; the Recent card on Run has none and is found by its
   class (BY_CLASS, key eventsbox).

   No timer, no clipboard, no live region, no inline style (classes and
   data attributes only; CSP style-src 'self').

   UMD like web/pager.js: CommonJS for node --test (app/test and
   tests/test_card_collapse.py) exports the pure parts and panel(); in the
   page it is window.ALCollapse and registers itself with window.ALApp
   (web/registry.js) as "collapse", order 950 (after the cards it
   changes). */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALCollapse = api;
    if (root.ALApp && typeof root.ALApp.register === "function") {
      root.ALApp.register(api.panel(function () { return root.ALApp.host; }, root));
    }
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var NAME = "collapse";
  var ORDER = 950;
  var PATH = "/api/ui/layout";
  // the cards in grid order (server/al/uilayout.py BUILD_CARDS, RUN_CARDS)
  var PANELS = {
    "panel-build": ["buildbox", "healthbox", "searchbox", "evalbox", "pricesbox", "weightsbox"],
    "panel-run": ["summarybox", "actsbox", "mapsbox", "deathsbox", "eventsbox", "charsbox"]
  };
  var COLS = 3;
  // the card an alert opens
  var ALERT_CARD = { build: "buildbox", death: "deathsbox", trade: "eventsbox" };
  // a card section without an id of its own, found by its class in its
  // panel (the Recent card on Run is <section class="card grid-card events">)
  var BY_CLASS = { eventsbox: "events" };

  function isFn(v) { return typeof v === "function"; }
  function isObj(v) { return v !== null && typeof v === "object" && !Array.isArray(v); }

  function allIds() {
    var out = [];
    Object.keys(PANELS).forEach(function (p) { out = out.concat(PANELS[p]); });
    return out;
  }

  /* The cell of each card in grid order from the collapsed flags (one
     per card, 2 rows of COLS): {col, cc, tall}. cc: "top" / "bot" (open,
     mate open), "top-tall" / "bot-tall" (open, mate collapsed: spans the
     freed tracks), "top-head" / "bot-head" (collapsed, title row only),
     "bot-under" (both collapsed: the lower title row sits under the
     upper one). */
  function cells(flags) {
    var f = Array.isArray(flags) ? flags : [];
    var out = [];
    for (var i = 0; i < f.length; i++) {
      var top = i < COLS;
      var mate = top ? i + COLS : i - COLS;
      var mine = f[i] === true;
      var other = mate >= 0 && mate < f.length && f[mate] === true;
      var cc;
      if (top) {
        cc = mine ? "top-head" : (other ? "top-tall" : "top");
      } else {
        cc = mine ? (other ? "bot-under" : "bot-head") : (other ? "bot-tall" : "bot");
      }
      out.push({ col: (i % COLS) + 1, cc: cc, tall: !mine && other });
    }
    return out;
  }

  /* The saved map of a GET / PUT answer: allowed ids with true only. */
  function readState(doc) {
    var got = isObj(doc) && isObj(doc.collapsed) ? doc.collapsed : {};
    var out = {};
    allIds().forEach(function (id) { if (got[id] === true) { out[id] = true; } });
    return out;
  }

  /* What the alert hook compares in one snapshot: the build alert words,
     the death count and the open trade request ids. */
  function seen(s) {
    var a = isObj(s) && isObj(s.build_alert) ? s.build_alert : null;
    var trades = [];
    (isObj(s) && Array.isArray(s.trade_requests) ? s.trade_requests : []).forEach(function (r) {
      if (r && (typeof r.id === "string" || typeof r.id === "number")) { trades.push(String(r.id)); }
    });
    return {
      alert: a && typeof a.text === "string" ? a.text : "",
      deaths: isObj(s) && typeof s.deaths === "number" && isFinite(s.deaths) ? s.deaths : null,
      trades: trades
    };
  }

  /* The cards an alert opens between two seen() values. The first push
     opens only for a build alert already showing (a condition the player
     needs); deaths and trades need a change. */
  function alerts(before, after) {
    var out = [];
    if (!after) { return out; }
    if (after.alert && (!before || after.alert !== before.alert)) { out.push(ALERT_CARD.build); }
    if (before && after.deaths !== null && before.deaths !== null && after.deaths > before.deaths) {
      out.push(ALERT_CARD.death);
    }
    if (before) {
      var open = {};
      before.trades.forEach(function (id) { open[id] = true; });
      if (after.trades.some(function (id) { return !open[id]; })) { out.push(ALERT_CARD.trade); }
    }
    return out;
  }

  /* The cockpit classes hold (web/app.css --al-size-class full or compact)
     and no text-spacing override is on (then rows wrap and tracks grow). */
  function cockpit(win, doc) {
    var de = doc && doc.documentElement;
    if (!de || (isFn(de.getAttribute) && de.getAttribute("data-text-spacing") === "user")) { return false; }
    if (!win || !isFn(win.getComputedStyle)) { return false; }
    var v = String(win.getComputedStyle(de).getPropertyValue("--al-size-class")).trim();
    return v === "full" || v === "compact";
  }

  function panel(getHost, win) {
    var st = {
      doc: null, win: win || null, on: false, saved: {}, alertOpen: {}, last: null,
      buttons: {}, boxes: {}, dismissed: ""
    };

    function collapsed(id) { return st.saved[id] === true && st.alertOpen[id] !== true; }

    function title(box) {
      var h = box.querySelector("h2");
      return h ? String(h.textContent || "").trim() : "card";
    }

    function setButton(id) {
      var b = st.buttons[id];
      if (!b) { return; }
      var shut = collapsed(id);
      b.setAttribute("aria-expanded", shut ? "false" : "true");
      b.setAttribute("aria-controls", controlIds(st.boxes[id], id));
      b.querySelector(".sr-only").textContent = (shut ? "Expand " : "Collapse ") + title(st.boxes[id]);
    }

    function apply() {
      var doc = st.doc;
      if (!doc || !st.on) { return; }
      var tall = cockpit(st.win, doc);
      Object.keys(PANELS).forEach(function (pid) {
        var ids = PANELS[pid].filter(function (id) { return st.boxes[id]; });
        if (ids.length !== PANELS[pid].length) { return; } // a card is missing: leave the grid
        var cs = cells(ids.map(collapsed));
        ids.forEach(function (id, i) {
          var box = st.boxes[id];
          var col = box.parentNode;
          if (collapsed(id)) { box.setAttribute("data-collapsed", "true"); } else { box.removeAttribute("data-collapsed"); }
          if (cs[i].tall && tall) { box.setAttribute("data-fit", "tall"); } else { box.removeAttribute("data-fit"); }
          if (col && isFn(col.setAttribute)) {
            col.setAttribute("data-cc-col", String(cs[i].col));
            col.setAttribute("data-cc", cs[i].cc);
          }
          setButton(id);
        });
      });
      var w = st.win;
      if (w && w.ALPager && isFn(w.ALPager.refit)) { w.ALPager.refit(); }
      if (w && w.ALSearch && isFn(w.ALSearch.relayout)) { w.ALSearch.relayout(); }
    }

    function save(id) {
      var host = getHost();
      if (!host || !isFn(host.api)) { return; }
      var body = { collapsed: {} };
      body.collapsed[id] = st.saved[id] === true;
      // the click's state stays on the page even when the save fails; the
      // core retries a failed write by itself (plug/uilayout.py)
      host.api("PUT", PATH, body).catch(function () { return null; });
    }

    function toggle(id) {
      var shut = !collapsed(id);
      // the build alert showing now was seen: a reconnect does not reopen it
      if (id === ALERT_CARD.build) { st.dismissed = st.last ? st.last.alert : ""; }
      st.alertOpen[id] = false;
      st.saved[id] = shut;
      apply();
      save(id);
    }

    function load() {
      var host = getHost();
      if (!host || !isFn(host.api)) { return; }
      host.api("GET", PATH).then(function (doc) {
        st.saved = readState(doc);
        // a build alert already showing opens its card, unless the player
        // collapsed the card while that alert showed
        if (st.last && st.last.alert && st.last.alert !== st.dismissed) {
          st.alertOpen[ALERT_CARD.build] = true;
        }
        apply();
      }).catch(function () { return null; });
    }

    function controlIds(box, id) {
      var out = [];
      Array.prototype.forEach.call(box.children, function (c, i) {
        if (c.classList.contains("card-head")) { return; }
        if (!c.id) { c.id = id + "-part-" + (c.getAttribute("data-page") || String(i)); }
        out.push(c.id);
      });
      return out.join(" ");
    }

    function addButton(doc, box, id) {
      var head = box.querySelector(".card-head");
      if (!head) { return; }
      var b = doc.createElement("button");
      b.type = "button";
      b.className = "card-collapse btn-24";
      var chev = doc.createElement("span");
      chev.className = "cc-chev";
      chev.setAttribute("aria-hidden", "true");
      var sr = doc.createElement("span");
      sr.className = "sr-only";
      b.appendChild(chev);
      b.appendChild(sr);
      b.addEventListener("click", function () { toggle(id); });
      head.appendChild(b);
      st.buttons[id] = b;
    }

    /* The first card section of a panel's column cells with class cls. */
    function byClass(p, cls) {
      var hit = null;
      Array.prototype.forEach.call(p.children, function (col) {
        Array.prototype.forEach.call(col.children || [], function (c) {
          if (!hit && c.tagName === "SECTION" && c.classList.contains(cls)) { hit = c; }
        });
      });
      return hit;
    }

    /* client: window.alClient (null in a plain browser: nothing happens) */
    function wireDoc(doc, client) {
      if (!doc || !client) { return false; }
      st.doc = doc;
      st.on = true;
      Object.keys(PANELS).forEach(function (pid) {
        var p = doc.getElementById(pid);
        if (!p) { return; }
        p.classList.add("cc-on");
        PANELS[pid].forEach(function (id) {
          var box = BY_CLASS[id] ? byClass(p, BY_CLASS[id]) : doc.getElementById(id);
          if (!box || !box.classList.contains("grid-card")) { return; }
          st.boxes[id] = box;
          addButton(doc, box, id);
        });
      });
      apply();
      var host = getHost();
      if (host && isFn(host.onConnect)) { host.onConnect(load); }
      if (st.win && isFn(st.win.addEventListener)) { st.win.addEventListener("resize", apply); }
      // a text-spacing override (web/textspacing.js) turns the tall fit off
      var MO = st.win && st.win.MutationObserver;
      if (isFn(MO) && doc.documentElement) {
        new MO(apply).observe(doc.documentElement, { attributes: true, attributeFilter: ["data-text-spacing"] });
      }
      return true;
    }

    function paint(s) {
      if (!st.on) { return; }
      var now = seen(s);
      var open = alerts(st.last, now);
      st.last = now;
      var changed = false;
      open.forEach(function (id) {
        if (st.saved[id] === true && st.alertOpen[id] !== true) { st.alertOpen[id] = true; changed = true; }
      });
      if (changed) { apply(); }
    }

    return {
      name: NAME,
      order: ORDER,
      wire: function () {
        var w = st.win;
        wireDoc(w && w.document, w && w.alClient ? w.alClient : null);
      },
      paint: paint,
      // tests
      wireDoc: wireDoc, toggle: toggle, load: load, apply: apply, state: st
    };
  }

  return {
    NAME: NAME, ORDER: ORDER, PATH: PATH, PANELS: PANELS, ALERT_CARD: ALERT_CARD,
    allIds: allIds, cells: cells, readState: readState, seen: seen, alerts: alerts,
    cockpit: cockpit, panel: panel
  };
}));
