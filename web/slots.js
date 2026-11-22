/* AshLight dashboard and overlay: slot tables (TD-02, docs/plan/03-target-design
   sections 3.2, 3.4, 3.5, 3.8, 5.1, 5.2 and 5.3). Pure functions decide what
   every fixed slot shows on each state push; the player presses nothing.
   No DOM access, no timers, no network, no clipboard: every function takes
   plain values and returns plain values, so app/test/slots.test.js proves
   the tables (glance budgets G3 and the table half of G11) with no page.
   UMD like web/tabs.js: CommonJS for node --test, window.ALSlots in the
   page (the script tag lands with PLAY-TD-09A-REGION-HOOK; the overlay
   step TD-17 consumes hudLine2 and cardHolder).

   Exports:
   - trackSet(sizeClass, s): the region tracks of 3.2 (full) and 3.8
     (compact), times the scale step s; null for the flow class.
   - contextMode(state, mapOk): the one mode of region C, first match.
   - feedRows(trades, events): the 5 feed slots, open trades first.
   - noticePick(queue, sizeClass): the one notice of region N and "+N more".
   - buildLine(state): the 4 states of region B.
   - keptChecks(items, build, sizeClass): the best checks of region U.
   - layout(view, sizeClass): each region's content height against its
     track (the line-box arithmetic of 3.4), and the column sums.
   - hudLine2(input): overlay HUD line 2, one order, first match (5.1, 5.2).
   - cardHolder(input): the overlay card slot holder, first match (5.3). */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALSlots = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function isNum(v) { return typeof v === "number" && isFinite(v); }
  function isObj(v) { return v !== null && typeof v === "object"; }
  function str(v) { return typeof v === "string" ? v : ""; }

  /* ---- Tracks (3.2, 3.8), px at s = 1 ---------------------------------- */

  var REGIONS = ["g", "c", "t", "n", "b", "i", "u"];
  var LEFT = ["g", "c", "t", "n"];
  var RIGHT = ["g", "b", "i", "u"];
  var BORDER = 2;   // the region's 1 px border, counted twice
  var GAP = 8;      // between regions
  var CHROME = 108; // bar 52 + main padding 12 + 12 + footer 32

  var CLASSES = {
    full: {
      tracks: { g: 100, c: 228, t: 204, n: 96, b: 68, i: 360, u: 100 },
      pad: { g: 4, c: 12, t: 6, n: 8, b: 8, i: 12, u: 8 },
      rows: { c: 7, t: 5, n: 2, u: 3 },
      grid: 652, setupPromise: true, hiddenNoticeKinds: []
    },
    compact: {
      tracks: { g: 100, c: 212, t: 204, n: 52, b: 68, i: 348, u: 52 },
      pad: { g: 4, c: 12, t: 6, n: 8, b: 8, i: 12, u: 4 },
      rows: { c: 6, t: 5, n: 0, u: 1 },
      grid: 592, setupPromise: false, hiddenNoticeKinds: [6, 7]
    }
  };
  var SIZE_CLASSES = ["full", "compact"];
  var SCALES = [1, 1.25, 1.5, 2];

  function copy(o) {
    var out = {};
    Object.keys(o).forEach(function (k) { out[k] = o[k]; });
    return out;
  }

  /* The track table of one size class. s: the scale step (1, 1.25, 1.5 or
     2; default 1); tracks, gaps, padding and chrome scale with it, the 2 px
     of border do not. Under the compact cockpit (the flow class) Play is
     one scrolling column with no tracks: null. */
  function trackSet(sizeClass, s) {
    var c = CLASSES[sizeClass];
    if (!c) { return null; }
    var k = SCALES.indexOf(s) >= 0 ? s : 1;
    var tracks = {};
    var pad = {};
    REGIONS.forEach(function (r) {
      tracks[r] = c.tracks[r] * k;
      pad[r] = c.pad[r] * k;
    });
    return {
      sizeClass: sizeClass, scale: k, tracks: tracks, pad: pad,
      border: BORDER, gap: GAP * k, chrome: CHROME * k, grid: c.grid * k,
      left: LEFT.slice(), right: RIGHT.slice(), rows: copy(c.rows),
      setupPromise: c.setupPromise, hiddenNoticeKinds: c.hiddenNoticeKinds.slice()
    };
  }

  /* ---- Region C: context mode (3.4, 3.5) ------------------------------ */

  var MODES = ["setup", "error", "idle", "map", "town", "guide", "none"];

  function isTownArea(areaId) {
    return /_town/i.test(str(areaId));
  }

  /* The one mode of region C, first match:
     1 setup  - the core answers and the player has not opted in yet.
     2 error  - AshLight is not answering (no state, or state.offline set
                by the page while the core is lost), or Client.txt is
                missing: opted in, not reading, and either no path was
                found (the overlay's "no Client.txt") or the tailer's last
                reset was "missing" (the file went away). Opted in, not
                reading, with a path: waiting for the first line, so none.
     3 idle   - game_idle (decision 0029).
     4 map    - only while mapOk: in a map, or in the hideout after a map
                this session.
     5 town   - a campaign town (area id "_town"), or the hideout (before
                any map; while mapOk is false the hideout is always town).
     6 guide  - a campaign zone with a guide entry (zone_guide kind
                "campaign").
     7 none   - anything else: no zone yet, an unknown or unguided area,
                and every map zone while mapOk is false.
     mapOk: the second argument when it is a boolean, else
     state.play.map_ok === true; false until PLAY-MAP-MODE-ON. */
  function contextMode(state, mapOk) {
    if (!isObj(state) || state.offline === true) { return "error"; }
    var ok = typeof mapOk === "boolean" ? mapOk
      : !!(isObj(state.play) && state.play.map_ok === true);
    var tl = isObj(state.tailer) ? state.tailer : null;
    if (tl && tl.consented === false) { return "setup"; }
    if (tl && tl.consented === true && tl.reading === false &&
        (!tl.path || tl.last_reset === "missing")) {
      return "error";
    }
    if (state.game_idle === true) { return "idle"; }
    var maps = isObj(state.maps) ? state.maps : {};
    var cur = isObj(maps.current) ? maps.current : null;
    var hideout = state.in_hideout === true;
    var mapped = isNum(maps.count) && maps.count > 0;
    if (ok && ((cur && cur.inside === true) || (hideout && mapped))) { return "map"; }
    if (isTownArea(state.area_id) || hideout) { return "town"; }
    if (isObj(state.zone_guide) && state.zone_guide.kind === "campaign") { return "guide"; }
    return "none";
  }

  /* Line boxes of each mode at s = 1 (3.4): a title, body rows (each its
     own box: body 22, meta 20, control 32, button 36) and a facts row.
     The tallest content of each mode, so a mode can never outgrow C. */
  var CONTEXT_ROWS = {
    setup: { title: 26, body: [22, 20, 36, 22, 22, 22], facts: 20, factsCompact: false },
    error: { title: 26, body: [22, 22, 22, 22, 22, 36], facts: 0, factsCompact: true },
    idle: { title: 26, body: [22, 22, 22, 22, 22, 22], facts: 20, factsCompact: true },
    map: { title: 26, body: [22, 22, 22, 22, 22], facts: 20, factsCompact: true },
    town: { title: 26, body: [32, 22, 22, 22, 22], facts: 20, factsCompact: true },
    guide: { title: 26, body: [22, 22, 22, 22, 22, 22, 22], facts: 20, factsCompact: true },
    none: { title: 26, body: [22], facts: 0, factsCompact: true }
  };

  /* ---- Region T: feed (3.4, 3.5) -------------------------------------- */

  var FEED_SLOTS = 5;
  var EVENT_ORDER = ["death", "level", "zone"];

  /* The 5 feed slots. trades: the open trade requests as the core keeps
     them (oldest first, each with `at`); events: {death, level, zone},
     each the latest one or null. Open trades come first, newest on top
     (all 5 server slots); the free slots take the latest death, level-up
     and zone change, in that order, at most 3. A trade is never evicted
     by an event. Trades past 5 (never sent by the core) are counted in
     `over`, not dropped silently; whatever leaves stays in Run > Recent. */
  function feedRows(trades, events) {
    var list = Array.isArray(trades) ? trades.filter(isObj) : [];
    var order = list.map(function (t, i) { return { t: t, i: i }; });
    order.sort(function (a, b) {
      var ta = isNum(a.t.at) ? a.t.at : -Infinity;
      var tb = isNum(b.t.at) ? b.t.at : -Infinity;
      if (ta !== tb) { return tb - ta; }
      return b.i - a.i; // same time: the later arrival is newer
    });
    var rows = order.slice(0, FEED_SLOTS).map(function (o) {
      return { kind: "trade", item: o.t };
    });
    var ev = isObj(events) ? events : {};
    for (var k = 0; k < EVENT_ORDER.length && rows.length < FEED_SLOTS; k++) {
      var e = ev[EVENT_ORDER[k]];
      if (isObj(e)) { rows.push({ kind: EVENT_ORDER[k], item: e }); }
    }
    var open = Math.min(list.length, FEED_SLOTS);
    return {
      head: open ? "Trades " + open : "Recent",
      dismissAll: open >= 2,
      trades: open,
      over: Math.max(0, list.length - FEED_SLOTS),
      rows: rows
    };
  }

  /* ---- Region N: notice (3.4, 3.5, 3.8) ------------------------------- */

  /* Kinds, first match: 1 a part is broken but reading works; 2 a build
     question that needs an answer; 3 the game-language notice; 4 "Setup: N
     steps left"; 5 data notes; 6 new-character tip; 7 key reminder; 8 empty. */
  var NOTICE_KINDS = [1, 2, 3, 4, 5, 6, 7, 8];
  var NOTICE_EMPTY = { label: "Notices", text: "none" };
  var KEY_REMINDER_PRESSES = 3;

  /* The one notice to show. queue: entries {kind: 1-7, ...} in arrival
     order; the lowest kind wins, arrival order breaks a tie. The compact
     class shows the head row only and never kinds 6 and 7. A key reminder
     with `presses` of 3 or more is retired. `more` is the "+N more" text
     count of the other entries that this class could show; each also
     lives in Settings (Checks) or on its own card. */
  function noticePick(queue, sizeClass) {
    var c = CLASSES[sizeClass] || CLASSES.full;
    var list = (Array.isArray(queue) ? queue : []).filter(function (q) {
      if (!isObj(q) || !isNum(q.kind) || q.kind < 1 || q.kind > 7 || q.kind % 1) {
        return false;
      }
      if (c.hiddenNoticeKinds.indexOf(q.kind) >= 0) { return false; }
      return !(q.kind === 7 && isNum(q.presses) && q.presses >= KEY_REMINDER_PRESSES);
    });
    var best = null;
    list.forEach(function (q) {
      if (!best || q.kind < best.kind) { best = q; }
    });
    if (!best) {
      return { kind: 8, notice: null, more: 0, bodyRows: 0,
               label: NOTICE_EMPTY.label, text: NOTICE_EMPTY.text };
    }
    return { kind: best.kind, notice: best, more: list.length - 1,
             bodyRows: c.rows.n, label: "", text: "" };
  }

  /* ---- Region B: build line (3.4) -------------------------------------- */

  var BUILD_STATES = {
    fits: { glyph: "[+]", word: "Build fits", tone: "neutral" },
    old: { glyph: "[?]", word: "Old build", tone: "warn" },
    wrong_class: { glyph: "[?]", word: "Wrong class", tone: "warn" },
    none: { glyph: "[ ]", word: "No build", tone: "idle" }
  };
  var BUILD_ORDER = ["fits", "old", "wrong_class", "none"];

  /* The state of region B from the snapshot's build (build_info) and
     build_alert (decision 0045). The build alert is a state of this
     region, never a card in a queue. "Old build" is AshLight's word (the
     kit word stale is not used). "Paste a build" shows only with no build. */
  function buildLine(state) {
    var s = isObj(state) ? state : {};
    var build = isObj(s.build) ? s.build : null;
    var alert = isObj(s.build_alert) ? s.build_alert : null;
    var key = "fits";
    if (!build || build.loaded !== true || (alert && alert.kind === "missing")) {
      key = "none";
    } else if (alert && alert.kind === "class") {
      key = "wrong_class";
    } else if (alert && alert.kind === "level") {
      key = "old";
    }
    var w = BUILD_STATES[key];
    return { state: key, glyph: w.glyph, word: w.word, tone: w.tone,
             canPaste: key === "none" };
  }

  /* ---- Region U: kept checks (3.4, 3.8) -------------------------------- */

  /* The best items checked this session against the CURRENT build, best
     first: 3 in the full class, 1 in the compact class. items: the core's
     re-scored checks (decision 0045, memory only), each with a numeric
     score_delta and `at`; an item with no number is left out. With no
     loaded build there is nothing to rank against: no rows (U shows its
     one muted empty line). A tie goes to the newer check. A check with a
     zero or negative gain still ranks (best first): U is a review list
     and each row carries its own verdict word, so a downgrade reads as
     one. */
  function keptChecks(items, build, sizeClass) {
    var c = CLASSES[sizeClass] || CLASSES.full;
    if (!isObj(build) || build.loaded !== true) { return []; }
    var list = (Array.isArray(items) ? items : []).filter(function (x) {
      return isObj(x) && isNum(x.score_delta);
    }).map(function (x, i) { return { x: x, i: i }; });
    list.sort(function (a, b) {
      if (a.x.score_delta !== b.x.score_delta) { return b.x.score_delta - a.x.score_delta; }
      var ta = isNum(a.x.at) ? a.x.at : -Infinity;
      var tb = isNum(b.x.at) ? b.x.at : -Infinity;
      if (ta !== tb) { return tb - ta; }
      return b.i - a.i;
    });
    return list.slice(0, c.rows.u).map(function (o) { return o.x; });
  }

  /* ---- Region I: item card kinds (3.4) -------------------------------- */

  /* teach: the empty card, 3 rows that teach the press. Every other kind
     uses the reserved card (head, sentence, compare, price, links,
     actions), so nothing moves while a staged check fills. */
  var ITEM_KINDS = ["teach", "staged", "verdict", "waystone", "error"];
  /* Line boxes of the card at s = 1: head 32, gap 4, sentence 2 rows 44,
     gap 8, compare label 20 + 5 rows of 22, gap 8, price row 26, links 28,
     gap 8, actions 28. A waystone puts its reward totals in compare rows
     1-2; an error card ("Not an item") keeps the reserved rows empty. */
  var ITEM_RESERVED = [32, 4, 44, 8, 20, 22, 22, 22, 22, 22, 8, 26, 28, 8, 28];
  var ITEM_BOXES = {
    teach: [22, 22, 22], staged: ITEM_RESERVED, verdict: ITEM_RESERVED,
    waystone: ITEM_RESERVED, error: ITEM_RESERVED
  };

  /* ---- Content heights (3.4, 3.7, 3.8), px at s = 1 ------------------- */

  function sum(list) { return list.reduce(function (a, b) { return a + b; }, 0); }

  function contextPx(mode, c) {
    var m = CONTEXT_ROWS[mode] || CONTEXT_ROWS.none;
    var facts = (c.setupPromise || m.factsCompact) ? m.facts : 0;
    return m.title + sum(m.body.slice(0, c.rows.c)) + facts;
  }

  /* view: {mode, feed: feedRows(), notice: noticePick(), kept: keptChecks(),
     item: one of ITEM_KINDS}. Returns null for an unknown class, else
     {regions: {g..u: {content, track, slack, rows}}, left, right, grid}
     where left and right are the summed column tracks. */
  function layout(view, sizeClass) {
    var c = CLASSES[sizeClass];
    if (!c) { return null; }
    var v = isObj(view) ? view : {};
    var feed = isObj(v.feed) ? v.feed : feedRows([], {});
    var notice = isObj(v.notice) ? v.notice : noticePick([], sizeClass);
    var kept = Array.isArray(v.kept) ? v.kept : [];
    var item = ITEM_KINDS.indexOf(v.item) >= 0 ? v.item : "teach";
    var inner = {
      g: 26 + 36 + 26,
      c: contextPx(v.mode, c),
      /* head 26 + one 32 px row per painted row (one muted line when
         empty); the CSS still reserves all 5 slots, so the box never moves */
      t: 26 + Math.max(1, feed.rows.length) * 32,
      n: 32 + notice.bodyRows * 22,
      b: 26 + 22,
      i: sum(ITEM_BOXES[item]),
      u: 20 + Math.max(1, kept.length) * 20
    };
    var rows = { c: Math.min((CONTEXT_ROWS[v.mode] || CONTEXT_ROWS.none).body.length, c.rows.c),
                 t: feed.rows.length, n: notice.bodyRows, u: kept.length };
    var regions = {};
    REGIONS.forEach(function (r) {
      var content = BORDER + 2 * c.pad[r] + inner[r];
      regions[r] = { content: content, track: c.tracks[r],
                     slack: c.tracks[r] - content, rows: rows[r] };
    });
    function column(list) {
      return sum(list.map(function (r) { return c.tracks[r]; })) + GAP * (list.length - 1);
    }
    return { regions: regions, left: column(LEFT), right: column(RIGHT), grid: c.grid };
  }

  /* ---- Overlay HUD line 2 (5.1, 5.2) ---------------------------------- */

  var LINE2_CHARS = 26;  // level text + status word
  var WORD_ALONE = 20;   // a status word over this stands alone
  var WORD_MAX = 27;     // "not reading - see dashboard"
  var CALM_S = 20;       // a death or level-up puts level and deaths back
  var GUIDE_CHARS = 34;
  var LOG_WORDS = ["AshLight offline", "no Client.txt", "waiting for log",
                   "not reading - see dashboard"];

  function levelText(level) {
    return isNum(level) ? "Lv " + level : "Lv unknown";
  }

  function deathsText(deaths) {
    var n = isNum(deaths) ? deaths : 0;
    return n === 1 ? "1 death" : n + " deaths";
  }

  /* "1 trade" in the singular, as the overlay's format.tradeCount says
     today; 5.2 shows the plural form "2 trades". */
  function tradesText(n) {
    return n === 1 ? "1 trade" : n + " trades";
  }

  function word(w) {
    var t = str(w);
    return t.length <= WORD_MAX ? t : "";
  }

  /* Overlay HUD line 2, one order, first match:
     1 the connection or log word (input.log); before any data
       (input.data false) it stands alone. The caller owns the word list
       (LOG_WORDS are the words of 5.2); this function only enforces the
       27-character limit, so a new state word needs no change here;
     2 "N trades" while another card covers an open trade card
       (input.coveredTrades);
     3 the under-level word (input.under, "3 lv under");
     4 "AFK" / "DND" (input.away);
     5 the zone-guide line, alone, replacing the level text: only when
       input.zoneGuide is "always" (an opt-in), input.guideShort is a
       non-empty `short` of at most 34 characters, and no death or level-up
       came in the last 20 s (input.bumpAt, input.now);
     6 a campaign hint word (input.campaign, "Boss: cold");
     7 level and deaths alone.
     Width rule: the level text ("Lv 74  3 deaths") and the status word are
     at most 26 characters together; over that the deaths text drops; a
     word over 20 characters stands alone (at most 27; a longer word is
     never shown). Returns {rank, level, deaths, status, guide}; an empty
     field is not shown. */
  function hudLine2(input) {
    var s = isObj(input) ? input : {};
    var out = { rank: 7, level: "", deaths: "", status: "", guide: "" };
    var log = word(s.log);
    var data = s.data !== false;
    if (!data) {
      /* no numbers before the first state: they would be made up */
      out.rank = log ? 1 : 7;
      out.status = log;
      return out;
    }
    var covered = isNum(s.coveredTrades) && s.coveredTrades > 0 ? s.coveredTrades : 0;
    var picks = [
      [1, log],
      [2, covered ? tradesText(covered) : ""],
      [3, word(s.under)],
      [4, word(s.away)]
    ];
    var rank = 0;
    var status = "";
    for (var i = 0; i < picks.length && !status; i++) {
      if (picks[i][1]) { rank = picks[i][0]; status = picks[i][1]; }
    }
    if (!status) {
      var short = str(s.guideShort);
      var calm = !isNum(s.bumpAt) || !isNum(s.now) || s.now - s.bumpAt >= CALM_S;
      if (s.zoneGuide === "always" && short && short.length <= GUIDE_CHARS && calm) {
        out.rank = 5;
        out.guide = short;
        return out;
      }
      var hint = word(s.campaign);
      if (hint) { rank = 6; status = hint; }
    }
    out.rank = rank || 7;
    out.status = status;
    if (status.length > WORD_ALONE) { return out; }
    var lv = levelText(s.level);
    var dt = deathsText(s.deaths);
    out.level = lv;
    if (!status || (lv + "  " + dt).length + status.length <= LINE2_CHARS) {
      out.deaths = dt;
    }
    return out;
  }

  /* The characters of line 2 as the width rule counts them (the gap before
     the status word is a 10 px gap, not a character). */
  function line2Chars(line) {
    var l = isObj(line) ? line : {};
    if (l.guide) { return l.guide.length; }
    var left = l.level ? (l.deaths ? l.level + "  " + l.deaths : l.level) : "";
    return left.length + str(l.status).length;
  }

  /* ---- Overlay card slot (5.3) ---------------------------------------- */

  var HOLDERS = ["press", "trade", "moment", "hint", "none"];
  var MOMENT_S = 12;
  var CARD_CHARS = 26; // CARD-LINE-LIMIT-FLIP (state.CARD_LINE)
  var HINT_TAIL = ": check an item";
  var HINT_HEAD = "Check: "; // the short form, overlayview HINT_SHORT
  var KEY_NAME_MAX = CARD_CHARS - HINT_HEAD.length; // 19
  var STATUS_CARD_WORDS = ["Build loaded", "Not an item", "Copy the item first"];
  var CARD_EDGE_PX = 62; // the card's near edge, whatever line 2 shows

  /* The one card slot, first match:
     1 press  - input.press {at, expiresAt} while now < expiresAt (an answer
                or status card; the newest press wins, the core sends one);
     2 trade  - the newest open trade request (input.trades, oldest first,
                each with `at`), with "+N" for the others;
     3 moment - input.moment {kind: "zone" | "act", at}: 12 s, only into a
                free slot, never waiting and never interrupting: it is
                dropped when a press card held the slot at its arrival or
                came after it; an open trade holds the slot first. Trades
                that closed are no longer in input.trades, so the caller
                that notes the moment sets moment.dropped once a trade card
                held the slot at its arrival or took it later; a dropped
                moment never shows;
     4 hint   - input.hint {due, key}: "<key>: check an item" while due,
                "Check: <key>" when that is over the 26-character line
                (overlayview _hint_head); a key name over 19 characters
                fits neither, so no hint then (never a cut key);
     5 none   - the card plate is absent.
     Returns {holder, rank, card, more, line1}. */
  function cardHolder(input) {
    var s = isObj(input) ? input : {};
    var now = isNum(s.now) ? s.now : 0;
    var press = isObj(s.press) && isNum(s.press.expiresAt) ? s.press : null;
    if (press && now < press.expiresAt && (!isNum(press.at) || press.at <= now)) {
      return { holder: "press", rank: 1, card: press, more: 0, line1: "" };
    }
    var feed = feedRows(s.trades, null);
    if (feed.rows.length) {
      var open = (Array.isArray(s.trades) ? s.trades.filter(isObj) : []).length;
      return { holder: "trade", rank: 2, card: feed.rows[0].item, more: open - 1,
               line1: "" };
    }
    var m = isObj(s.moment) ? s.moment : null;
    if (m && (m.kind === "zone" || m.kind === "act") && isNum(m.at) &&
        m.dropped !== true && now >= m.at && now < m.at + MOMENT_S) {
      var pAt = press && isNum(press.at) ? press.at : -Infinity;
      var busy = press && pAt <= now && (pAt > m.at || press.expiresAt > m.at);
      if (!busy) {
        return { holder: "moment", rank: 3, card: m, more: 0, line1: "" };
      }
    }
    var h = isObj(s.hint) ? s.hint : null;
    var key = h ? str(h.key) : "";
    if (h && h.due === true && key && key.length <= KEY_NAME_MAX) {
      var line1 = (key + HINT_TAIL).length <= CARD_CHARS ? key + HINT_TAIL : HINT_HEAD + key;
      return { holder: "hint", rank: 4, card: h, more: 0, line1: line1 };
    }
    return { holder: "none", rank: 5, card: null, more: 0, line1: "" };
  }

  return {
    REGIONS: REGIONS, LEFT: LEFT, RIGHT: RIGHT, SIZE_CLASSES: SIZE_CLASSES,
    SCALES: SCALES, MODES: MODES, FEED_SLOTS: FEED_SLOTS, NOTICE_KINDS: NOTICE_KINDS,
    BUILD_ORDER: BUILD_ORDER, ITEM_KINDS: ITEM_KINDS, HOLDERS: HOLDERS,
    LOG_WORDS: LOG_WORDS, STATUS_CARD_WORDS: STATUS_CARD_WORDS,
    LINE2_CHARS: LINE2_CHARS, WORD_ALONE: WORD_ALONE, WORD_MAX: WORD_MAX,
    CALM_S: CALM_S, GUIDE_CHARS: GUIDE_CHARS, MOMENT_S: MOMENT_S,
    CARD_CHARS: CARD_CHARS, KEY_NAME_MAX: KEY_NAME_MAX, CARD_EDGE_PX: CARD_EDGE_PX,
    trackSet: trackSet, contextMode: contextMode, feedRows: feedRows,
    noticePick: noticePick, buildLine: buildLine, keptChecks: keptChecks,
    layout: layout, hudLine2: hudLine2, line2Chars: line2Chars,
    cardHolder: cardHolder
  };
}));
