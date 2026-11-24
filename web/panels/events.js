/* AshLight dashboard panel: Run > Recent, the recent events list, moved
   out of web/app.js by TEST-WEB-PANELS-C1 (finding F-135; research 0047
   R4 (c)). The trades block of that move is not recreated: the redesign
   replaced it by Play's feed region (web/feed.js), so no trades panel
   exists any more.

   UX-PERF: most state pushes (timers, trades, HUD fields) leave the
   recent list as it was; rebuild its rows only when the list changed.
   PLAY-TD-20B-RUN-CARDS: Run > Recent is a grid card, the twin of Play's
   feed: every recent event newest first in one-line rows that page at 8
   (6 compact) through web/pager.js (ALSearch.rowPager; the whole text in
   title and on the Full text page). A row is the local time, a muted tag
   (From / To for whispers, no edge; Death in the bad state colour) and
   the core's sentence. The chips All, Deaths and Trades (aria-pressed)
   filter the rows; a chip press starts the list at its first page.

   The block moved verbatim: evTag, evShows, evChips, evStart and
   renderEvents, plus the "events" entry's paint. What the panel shares
   with the page ($, setText) is reached through window.ALApp.host, which
   app.js sets before start().

   Paint and the chip clicks only: no clipboard, no timer, no request.

   UMD like web/fmt.js: CommonJS for node --test (app/test/panels.test.js)
   exports {name, order, panel}; in the page the file registers itself with
   window.ALApp (web/registry.js) as "events", order 90: the name and order
   app.js gave this entry before the move, so the paint order of today's
   page is kept. The core links this file at the panels marker of
   index.html (TEST-WEB-ASSEMBLE). */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALApp.register(api.panel(function () { return root.ALApp.host; }));
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var NAME = "events";
  var ORDER = 90; // app.js gave "events" 90 before the move

  /* the page's shared helpers (window.ALApp.host, set by web/app.js) */
  var $, setText;
  var D = null; // web/status.js: pure view helpers
  var clock = null; // web/fmt.js clock, through the host
  var bound = false;

  function bind(host) {
    if (bound) { return; }
    if (!host || typeof host.$ !== "function") {
      throw new TypeError("events: no page host (web/app.js sets ALApp.host)");
    }
    $ = host.$; setText = host.setText;
    D = window.ALDash;
    clock = host.clock;
    bound = true;
  }

  var renderedEvents = "";
  var evRows = [];
  var evFilter = "all";
  var evPager = null;
  var EV_SIZE = { full: 8, compact: 6 };
  var EV_NONE = { death: "No deaths among your recent events.",
    trade: "No trades among your recent events." };

  function evTag(kind) { return kind.charAt(0).toUpperCase() + kind.slice(1); }

  function evShows(kind, filter) {
    return filter === "all" || kind === filter;
  }

  function evChips() {
    return Array.prototype.slice.call(document.querySelectorAll("[data-ev-filter]"));
  }

  function evStart() {
    var slot = $("events");
    if (!slot || !window.ALSearch) { return null; }
    var S = window.ALSearch;
    evPager = S.rowPager(document, {
      label: "recent events",
      size: EV_SIZE,
      sizeClass: function () { return S.sizeClass(document); },
      text: function (r) { return r.text; },
      parts: function (r) {
        return [{ text: r.time ? r.time + " " : "", cls: "ev-time" },
          { text: r.tag + " ", cls: "ev-tag" }, { text: r.body }];
      },
      rowClass: function (r) { return "ev-" + r.kind; }
    });
    slot.replaceChildren(evPager.node);
    evChips().forEach(function (b) {
      b.addEventListener("click", function () {
        evFilter = b.getAttribute("data-ev-filter") || "all";
        evChips().forEach(function (c) {
          c.setAttribute("aria-pressed", c === b ? "true" : "false");
        });
        renderedEvents = "";
        renderEvents(evRows);
        while (evPager.state().hasPrev) { evPager.press("prev"); }
      });
    });
    return evPager;
  }

  function renderEvents(rows) {
    evRows = rows;
    var key = evFilter + "#" + D.eventsKey(rows);
    if (key === renderedEvents) { return; }
    if (!evPager && !evStart()) { return; }
    renderedEvents = key;
    var shown = [];
    for (var i = rows.length - 1; i >= 0; i--) {
      var row = rows[i];
      var k = D.kindOf(row);
      if (!evShows(k, evFilter)) { continue; }
      var t = clock(row.at);
      var tag = evTag(k);
      shown.push({ kind: k, time: t, tag: tag, body: row.text,
        text: (t ? t + " " : "") + tag + ": " + row.text });
    }
    $("events").hidden = shown.length === 0;
    $("events-empty").hidden = rows.length > 0;
    var none = $("events-none");
    setText(none, rows.length && !shown.length ? EV_NONE[evFilter] || "" : "");
    none.hidden = !none.textContent;
    evPager.set(shown);
  }

  /* The registry entry; getHost is read on the first paint, when web/app.js
     has run (it is the last script). */
  function panel(getHost) {
    return {
      name: NAME,
      order: ORDER,
      paint: function (s) { bind(getHost()); renderEvents(s.recent_events || []); }
    };
  }

  return { name: NAME, order: ORDER, panel: panel };
}));
