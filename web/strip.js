/* AshLight dashboard: region G, the strip (PLAY-TD-10-STRIP; plan 03 TD-10,
   section 3.4 and section 7; findings F-087 and F-159).

   Four cells in one row (track 100 px at s = 1): Zone, Level, Deaths,
   Session. Each cell is three fixed line boxes: the label (20 px, muted),
   the value (36 px box: the zone name at 28 px / 700 with its timer at
   20 px / 600 right-aligned, or a number / timer at 32 px / 700) and one
   sub line (20 px). Under the cockpit (the flow class) the Zone cell takes
   a full row and the other three share the next one.

   The words come composed from the core: the sub lines, the zone name and
   the fresh flag are snap.play.strip (server/al/playview.py strip_view;
   "frozen <time>" is already in the zone sub line while the log is idle,
   decision 0029). The numbers are the playing character's (snap.level,
   snap.deaths); the character picker and the pace line are not in G.
   Under-levelled, the level sub line is the overlay's word "N lv under"
   with the [?] glyph.

   The bar: #bar-char gets the character name and class (muted, full text
   in title). The one status word #reading is painted by web/app.js
   through ALDash.barStatus (PLAY-TD-09C-BAR); web/strip.css makes it
   neutral while ok and keeps colour only for blocked or failed (F-159);
   it stays visible on every tab (ToS floor reading indicator).

   Stale look (F-087): body[data-fresh=no] while the log is idle
   (play.strip.fresh false) or the feed is down (the bar word's kit state
   is pending or failed: with a live feed barStatus never says either);
   a MutationObserver on the bar word (an event, not a timer) follows the
   feed between pushes. A cell with no value gets data-empty. The words
   stay, so colour never works alone.

   Timers tick once a second from the region tick (web/app.js stops it
   while the feed is down). No timer of its own, no network, no
   clipboard, no live region, never ALTabs.notify (the legacy path keeps
   that until PLAY-LEGACY-OUT).

   Registers {name: strip, region: g, retires: [g-tiles]} with
   web/regions.js. UMD like web/tabs.js: CommonJS for node --test
   (app/test/strip.test.js), window.ALStrip in the page. */
(function (root, factory) {
  "use strict";
  var common = typeof module === "object" && module.exports;
  var dash = common ? require("./status.js") : root.ALDash;
  var fmt = common ? require("./fmt.js") : root.ALFmt;
  var api = factory(dash, fmt);
  if (common) {
    module.exports = api;
  } else {
    root.ALStrip = api;
    if (root.ALRegions && typeof root.ALRegions.register === "function") {
      root.ALRegions.register(api.spec);
    }
  }
}(typeof self !== "undefined" ? self : this, function (D, F) {
  "use strict";

  var NAME = "strip";
  var REGION = "g";
  var RETIRES = ["g-tiles"];
  var NO_ZONE = "No zone yet";
  var DASH = "-";
  var NO_TIME = "--:--";
  var UNDER_GLYPH = "[?]";
  // the bar word's kit states that only a down feed shows (web/status.js)
  var FEED_DOWN = { pending: true, failed: true };
  var CELLS = [
    { key: "zone", label: "Zone" },
    { key: "level", label: "Level", sr: "unknown" },
    { key: "deaths", label: "Deaths", sr: "not counted yet" },
    { key: "session", label: "Session" }
  ];

  function isObj(v) { return v !== null && typeof v === "object" && !Array.isArray(v); }
  function isNum(v) { return typeof v === "number" && isFinite(v); }
  function str(v) { return typeof v === "string" ? v : ""; }

  /* Seconds -> "m:ss" or "h:mm:ss" (web/fmt.js); "--:--" when not a
     number (a numeric string or a boolean too). */
  function duration(s) { return isNum(s) ? F.duration(s) : NO_TIME; }

  /* The time the clocks count to: the last log line while idle. */
  function until(tailer, now) {
    if (D && typeof D.clockUntil === "function") { return D.clockUntil(tailer, now); }
    return now;
  }

  /* The zone and session timers at `now` (server seconds). */
  function timers(snap, now) {
    var s = isObj(snap) ? snap : {};
    var tl = isObj(s.tailer) ? s.tailer : null;
    var t = until(tl, now);
    var zone = isNum(s.zone_entered_at) && isNum(t) ? duration(t - s.zone_entered_at) : NO_TIME;
    var session = tl && tl.consented === true && isNum(s.session_started_at) && isNum(t)
      ? duration(t - s.session_started_at) : NO_TIME;
    return { zone: zone, session: session };
  }

  /* The bar's character line: "Name (Class)", or "" while unknown. */
  function charLine(snap) {
    var s = isObj(snap) ? snap : {};
    var name = str(s.character);
    if (!name) { return ""; }
    var cls = str(s["class"]);
    return cls ? name + " (" + cls + ")" : name;
  }

  /* snap, now -> what G shows. Every value is a string; empty marks a cell
     with no value (shown as a muted dash or "No zone yet"). */
  function model(snap, now) {
    var s = isObj(snap) ? snap : {};
    var play = isObj(s.play) ? s.play : {};
    var g = isObj(play.strip) ? play.strip : {};
    var tl = isObj(s.tailer) ? s.tailer : {};
    var consented = tl.consented === true;
    var under = isObj(s.underlevel) ? str(s.underlevel.word) : "";
    var levelSub = str(g.level_sub);
    var t = timers(s, now);
    var zone = str(g.zone) || str(s.zone);
    return {
      zone: zone,
      zoneTime: zone ? t.zone : NO_TIME,
      zoneSub: str(g.sub),
      level: isNum(s.level) ? String(s.level) : "",
      levelSub: levelSub,
      under: !!under && levelSub === under,
      deaths: consented ? String(isNum(s.deaths) ? s.deaths : 0) : "",
      deathsSub: str(g.deaths_sub),
      session: consented ? t.session : "",
      sessionSub: str(g.session_sub),
      fresh: g.fresh !== false,
      character: charLine(s)
    };
  }

  var WORD_CAP = 20; // G5: region G, its visually hidden heading included

  function words(text) {
    return str(text).split(/\s+/).filter(function (w) { return /[A-Za-z0-9]/.test(w); }).length;
  }

  /* The words G shows for a model (labels, values, an empty cell's
     screen-reader words, sub lines) plus `extra` (the region heading). */
  function wordCount(m, extra) {
    var n = (extra || 0) + CELLS.length;
    n += words(m.zone || NO_ZONE) + words(m.zoneTime) + words(m.zoneSub);
    CELLS.forEach(function (c) {
      if (c.sr && !m[c.key]) { n += words(c.sr); }
    });
    n += words(m.level) + words(m.levelSub) + words(m.deaths) + words(m.deathsSub);
    n += words(m.session) + words(m.sessionSub);
    return n;
  }

  /* The last guard of the G5 cap (the core composes under it, without the
     heading): drop optional parts in a fixed order until G fits - the
     area level of the zone sub line, the session sub line, the deaths sub
     line, then the zone sub line's leading parts (its tags, "frozen
     <time>" among them, go last). Returns the model. */
  function fitWords(m, extra) {
    function over() { return wordCount(m, extra) > WORD_CAP; }
    if (!over()) { return m; }
    var parts = m.zoneSub ? m.zoneSub.split(" - ") : [];
    var kept = parts.filter(function (p) { return p.indexOf("area level") !== 0; });
    if (kept.length !== parts.length) { m.zoneSub = kept.join(" - "); }
    if (over()) { m.sessionSub = ""; }
    if (over()) { m.deathsSub = ""; }
    while (over() && kept.length > 0) {
      kept.shift();
      m.zoneSub = kept.join(" - ");
    }
    return m;
  }

  /* Is the feed live? Read from the bar word's kit state: pending or
     failed only show while the feed is down (or before it first opens). */
  function feedLive(doc) {
    var n = doc && typeof doc.getElementById === "function" ? doc.getElementById("reading") : null;
    if (!n || typeof n.getAttribute !== "function") { return true; }
    return !FEED_DOWN[n.getAttribute("data-state")];
  }

  function slotOf(doc) {
    if (!doc || typeof doc.querySelector !== "function") { return null; }
    return doc.querySelector('#play-g [data-slot="g"]');
  }

  function el(doc, tag, cls) {
    var n = doc.createElement(tag);
    if (cls) { n.className = cls; }
    return n;
  }

  function setText(n, text) { if (n && n.textContent !== text) { n.textContent = text; } }
  function setAttr(n, k, v) { if (n && n.getAttribute(k) !== v) { n.setAttribute(k, v); } }
  function dropAttr(n, k) {
    if (n && n.getAttribute(k) !== null && typeof n.removeAttribute === "function") {
      n.removeAttribute(k);
    }
  }

  // the region's nodes, made once by wire() (or the first paint)
  var nodes = null;
  var watcher = null;
  var last = { snap: null, now: null };

  function build(doc) {
    if (nodes && nodes.doc === doc) { return nodes; }
    var slot = slotOf(doc);
    if (!slot || typeof doc.createElement !== "function") { return null; }
    // the slot is the strip itself and each cell holds its rows straight
    // (PLAY-FIT-G5-TOTALS: no wrapper elements)
    var root = slot;
    if ((" " + root.className + " ").indexOf(" st ") < 0) {
      root.className = root.className ? root.className + " st" : "st";
    }
    var out = { doc: doc, root: root, cells: {} };
    CELLS.forEach(function (c) {
      var cell = el(doc, "div", "st-cell st-" + c.key);
      cell.setAttribute("data-cell", c.key);
      var label = el(doc, "p", "st-label row-title muted");
      label.textContent = c.label;
      var value = el(doc, "p", c.key === "zone" ? "st-value st-name row-glance one-line"
        : "st-value st-num row-hero");
      // the value text sits straight in its line box (no inline child, so
      // the glyphs never add scroll height); the screen-reader words of an
      // empty cell are a sibling, visually hidden
      var shown = value;
      var said = null;
      if (c.sr) {
        said = el(doc, "span", "st-said");
        said.textContent = c.sr;
        said.hidden = true;
      }
      var time = null;
      if (c.key === "zone") {
        time = el(doc, "p", "st-time row-title");
      }
      var sub = el(doc, "p", "st-sub row-title muted one-line");
      cell.appendChild(label);
      cell.appendChild(value);
      if (said) { cell.appendChild(said); }
      if (time) { cell.appendChild(time); }
      cell.appendChild(sub);
      root.appendChild(cell);
      out.cells[c.key] = { cell: cell, value: value, shown: shown, said: said, time: time,
                           sub: sub };
    });
    nodes = out;
    return nodes;
  }

  /* One cell: value text (shown, and for a screen reader the same text or
     the cell's "no value" words), data-empty, the sub line. */
  function paintCell(c, text, empty, sub) {
    var shown = empty ? c.emptyText : text;
    setText(c.shown, shown);
    if (c.said) {
      // the dash is hidden from screen readers; they hear the words
      if (empty) { setAttr(c.shown, "aria-hidden", "true"); } else { dropAttr(c.shown, "aria-hidden"); }
      c.said.hidden = !empty;
    } else {
      dropAttr(c.shown, "aria-hidden");
    }
    setAttr(c.value, "title", empty ? "" : text);
    if (empty) { setAttr(c.cell, "data-empty", "yes"); } else { dropAttr(c.cell, "data-empty"); }
    setText(c.sub, sub);
    setAttr(c.sub, "title", sub);
  }

  function setFresh(doc, fresh) {
    var body = doc && doc.body;
    if (body && typeof body.setAttribute === "function") {
      setAttr(body, "data-fresh", fresh ? "yes" : "no");
    }
  }

  function paintTimers(n, m) {
    var z = n.cells.zone;
    setText(z.time, m.zoneTime);
    if (m.zoneTime === NO_TIME) { setAttr(z.time, "data-empty", "yes"); } else { dropAttr(z.time, "data-empty"); }
    var s = n.cells.session;
    var empty = !m.session || m.session === NO_TIME;
    s.emptyText = NO_TIME;
    setText(s.shown, empty ? NO_TIME : m.session);
    if (empty) { setAttr(s.cell, "data-empty", "yes"); } else { dropAttr(s.cell, "data-empty"); }
  }

  /* Paint G and the bar's character line from one snapshot (each state
     push). Idempotent: a node is touched only when it changes. */
  function paint(doc, snap, now) {
    last.snap = snap;
    last.now = now;
    var n = build(doc);
    var head = doc && typeof doc.getElementById === "function" ? doc.getElementById("play-g-h") : null;
    var m = fitWords(model(snap, now), head ? words(head.textContent) : 0);
    setFresh(doc, m.fresh && feedLive(doc));
    var bc = doc && typeof doc.getElementById === "function" ? doc.getElementById("bar-char") : null;
    if (bc) {
      setText(bc, m.character);
      setAttr(bc, "title", m.character);
    }
    if (!n) { return m; }
    var c = n.cells;
    c.zone.emptyText = NO_ZONE;
    paintCell(c.zone, m.zone, !m.zone, m.zoneSub);
    c.level.emptyText = DASH;
    paintCell(c.level, m.level, !m.level, m.under ? UNDER_GLYPH + " " + m.levelSub : m.levelSub);
    setAttr(c.level.sub, "data-tone", m.under ? "warn" : "neutral");
    c.deaths.emptyText = DASH;
    paintCell(c.deaths, m.deaths, !m.deaths, m.deathsSub);
    c.session.emptyText = NO_TIME;
    paintCell(c.session, m.session, !m.session || m.session === NO_TIME, m.sessionSub);
    paintTimers(n, m);
    return m;
  }

  /* Once a second: the two timers and the fresh flag. */
  function tick(doc, snap, now) {
    last.snap = snap;
    last.now = now;
    var n = build(doc);
    var m = model(snap, now);
    setFresh(doc, m.fresh && feedLive(doc));
    if (n) { paintTimers(n, m); }
    return m;
  }

  /* Follow the feed between pushes: the bar word's state changes when the
     feed drops or comes back (web/app.js setLink). */
  function watch(doc) {
    var Obs = typeof MutationObserver === "function" ? MutationObserver : null;
    var pill = doc && typeof doc.getElementById === "function" ? doc.getElementById("reading") : null;
    if (!Obs || !pill || watcher) { return false; }
    watcher = new Obs(function () {
      var m = model(last.snap, last.now);
      setFresh(doc, m.fresh && feedLive(doc));
    });
    watcher.observe(pill, { attributes: true, attributeFilter: ["data-state"] });
    return true;
  }

  function wire(doc) {
    build(doc);
    setFresh(doc, feedLive(doc) && model(null, null).fresh);
    watch(doc);
  }

  /* Tests only: forget the nodes made for an earlier document. */
  function reset() {
    nodes = null;
    if (watcher && typeof watcher.disconnect === "function") { watcher.disconnect(); }
    watcher = null;
    last = { snap: null, now: null };
  }

  var spec = {
    name: NAME,
    region: REGION,
    retires: RETIRES.slice(),
    wire: wire,
    paint: function (doc, snap, now) { paint(doc, snap, now); },
    tick: function (doc, snap, now) { tick(doc, snap, now); }
  };

  return {
    NAME: NAME, REGION: REGION, RETIRES: RETIRES, CELLS: CELLS, UNDER_GLYPH: UNDER_GLYPH,
    NO_ZONE: NO_ZONE, NO_TIME: NO_TIME,
    WORD_CAP: WORD_CAP, wordCount: wordCount, fitWords: fitWords,
    duration: duration, timers: timers, charLine: charLine, model: model, feedLive: feedLive,
    paint: paint, tick: tick, wire: wire, watch: watch, reset: reset, spec: spec
  };
}));
