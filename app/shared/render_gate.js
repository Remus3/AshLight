/* AshLight overlay: the "should we repaint?" gate. The HUD repaints only
   when one of its visible strings changes; everything else (other state
   fields, heartbeats, duplicate pushes) costs no frame. UMD like format.js. */
(function (root, factory) {
  "use strict";
  var fmt = (typeof module === "object" && module.exports)
    ? require("./format.js")
    : root.ALShared;
  var api = factory(fmt);
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALShared = Object.assign(root.ALShared || {}, api);
  }
}(typeof self !== "undefined" ? self : this, function (fmt) {
  "use strict";

  /* F-131: the one status vocabulary. The overlay loads app/shared only,
     so this is a copy of server/al/data/status_words.json (without
     _README); tests/test_status_words.py and app/test/statuswords.test.js
     fail when it differs. Edit the JSON, then paste
     `python -m server.al.statuswords` here and in web/status.js. */
  /* STATUS_WORDS BEGIN: copy of server/al/data/status_words.json */
  var STATUS_WORDS = {
    "schema": 1,
    "overlay_beside_max": 15,
    "overlay_alone_max": 27,
    "states": {
      "reading": {
        "rank": 0,
        "kit": "running",
        "glyph": "[>]",
        "bar": "reading Client.txt",
        "overlay": "",
        "overlay_alone": false,
        "check_row": "reading",
        "check": "Reading Client.txt.",
        "next": "",
        "fault": false
      },
      "live": {
        "rank": 0,
        "kit": "done",
        "glyph": "[+]",
        "bar": "live",
        "overlay": "",
        "overlay_alone": false,
        "check_row": null,
        "check": null,
        "next": "",
        "fault": false
      },
      "unknown": {
        "rank": 0,
        "kit": "pending",
        "glyph": "[ ]",
        "bar": "Client.txt status unknown",
        "overlay": null,
        "overlay_alone": false,
        "check_row": null,
        "check": null,
        "next": "",
        "fault": false
      },
      "link_wait": {
        "rank": 1,
        "kit": "pending",
        "glyph": "[ ]",
        "bar": "connecting",
        "overlay": "connecting",
        "overlay_alone": false,
        "check_row": null,
        "check": null,
        "next": "",
        "fault": false
      },
      "link_retry": {
        "rank": 2,
        "kit": "pending",
        "glyph": "[ ]",
        "bar": "reconnecting",
        "overlay": "offline",
        "overlay_alone": false,
        "check_row": null,
        "check": null,
        "next": "",
        "fault": false
      },
      "off": {
        "rank": 3,
        "kit": "idle",
        "glyph": "[-]",
        "bar": "not reading Client.txt",
        "overlay": "not reading - see dashboard",
        "overlay_alone": true,
        "check_row": "consent",
        "check": "Not given yet. Allow it on the Play tab.",
        "next": "Press \"Allow reading Client.txt\" on the Play tab.",
        "fault": false
      },
      "waiting": {
        "rank": 4,
        "kit": "blocked",
        "glyph": "[#]",
        "bar": "waiting for Client.txt",
        "overlay": "waiting for log",
        "overlay_alone": false,
        "check_row": null,
        "check": null,
        "next": "",
        "fault": false
      },
      "idle": {
        "rank": 4,
        "kit": "blocked",
        "glyph": "[#]",
        "bar": "log quiet, still reading - game closed or AFK?",
        "overlay": "log quiet",
        "overlay_alone": false,
        "check_row": "last_line",
        "check": "The game may be closed, or you are AFK.",
        "next": "",
        "fault": false
      },
      "missing": {
        "rank": 4,
        "kit": "blocked",
        "glyph": "[#]",
        "bar": "Client.txt not found - start the game once",
        "overlay": "no Client.txt",
        "overlay_alone": false,
        "check_row": "log",
        "check": "Not found yet.",
        "next": "Start Path of Exile 2 once so it writes Client.txt. AshLight finds it by itself.",
        "fault": true
      },
      "unreadable": {
        "rank": 4,
        "kit": "blocked",
        "glyph": "[#]",
        "bar": "can't read Client.txt",
        "overlay": "can't read log",
        "overlay_alone": false,
        "check_row": "reading",
        "check": "Client.txt is there but can't be read. AshLight keeps trying.",
        "next": "Close any program that has Client.txt open, or check that you can open the file yourself.",
        "fault": true
      },
      "path_missing": {
        "rank": 4,
        "kit": "blocked",
        "glyph": "[#]",
        "bar": null,
        "overlay": null,
        "overlay_alone": false,
        "check_row": "log",
        "check": "The Client.txt path in your settings is missing.",
        "next": "Correct \"client_log\" in config\\local.json, or remove it so AshLight finds Client.txt by itself. Starting the game once may also create it.",
        "fault": true
      },
      "stalled": {
        "rank": 5,
        "kit": "blocked",
        "glyph": "[#]",
        "bar": null,
        "overlay": null,
        "overlay_alone": false,
        "check_row": "reading",
        "check": "Not reading Client.txt.",
        "next": "Run scripts\\run.ps1 to start AshLight's parts again.",
        "fault": true
      },
      "link_down": {
        "rank": 6,
        "kit": "failed",
        "glyph": "[x]",
        "bar": "can't reach AshLight - restart it",
        "overlay": "offline",
        "overlay_alone": false,
        "check_row": null,
        "check": null,
        "next": "Start AshLight again from its Start Menu shortcut.",
        "fault": false
      },
      "link_token": {
        "rank": 7,
        "kit": "failed",
        "glyph": "[x]",
        "bar": "open AshLight from the link it showed at start",
        "overlay": null,
        "overlay_alone": false,
        "check_row": null,
        "check": null,
        "next": "Use the AshLight window, or open the link AshLight showed at start.",
        "fault": false
      }
    }
  };
  /* STATUS_WORDS END */

  var W = STATUS_WORDS.states;

  /* TEST-LIVE-EXIT: the HUD status word for an idle log (<= 15 chars). */
  var IDLE_WORD = W.idle.overlay;

  var FIELDS = ["zone", "timer", "level", "deaths", "sep", "away", "under", "campaign", "guide",
                "log", "status", "trades",
                "tradeFrom", "tradeItem", "tradeWhere", "tradeMore", "anchor",
                "evalHead", "evalItem", "evalLine", "evalVerdict", "hudShown"];

  /* OVL-PARTS-PAGE (F-118, plan 03 section 5.1): the player's parts
     switches from snap.overlay_layout (server/al/layout.py PARTS). A
     missing layout or part is on; only an explicit false turns a part
     off. A failure word (offline, not reading, no Client.txt, log quiet)
     is not a part and always shows. */
  function partOn(snap, name) {
    var l = snap && snap.overlay_layout;
    var p = l && l.parts;
    return !(p && typeof p === "object" && p[name] === false);
  }

  /* quiet_town: the zone line (zone and its timer) drops out in town and
     in a hideout. */
  function quietHere(snap) {
    var l = snap && snap.overlay_layout;
    return !!(l && l.quiet_town === true && (snap.in_town === true || snap.in_hideout === true));
  }


  /* TC-EVAL-UI: the item check card shows from the hotkey press until the
     core's expires_at (server/al/text/overlaycard.py EVAL_CARD_S), then
     leaves by itself. While it shows it takes the one card slot (design
     0001 section 10: at most one card), so the trade card waits; trades stay on the dashboard. */
  /* PRICE-1-UI (decision 0016): a core that sends "card" has already
     chosen the one card (item check, price check, or both from one press);
     it shows until its expires_at. An older core without the field keeps
     the item check path. */
  /* ZONE-CARD-ITEM-GATE (OVL-ZONE-CARD review D-1): the parts switch each
     card kind follows. The zone moment card (overlayview CARD_HOLDERS
     "moment") has its own part; every other card the core sends (item
     check, price, both, waystone, sample) is a press card: parts.item.
     OVL-KEY-HINT: the key hint card follows parts.hint. */
  var CARD_PART = { zone: "moment", hint: "hint" };

  function cardPart(c) {
    var k = (c && c.kind) ? String(c.kind) : "";
    return Object.prototype.hasOwnProperty.call(CARD_PART, k) ? CARD_PART[k] : "item";
  }

  /* An open trade request the page's trade card shows (parts.trade on). */
  function tradeShown(snap) {
    return partOn(snap, "trade") && !!(snap.trade_requests && snap.trade_requests.length);
  }

  /* OVL-KEY-HINT: the empty slot's key hint ("Alt+Shift+E: check an
     item", overlayview CARD_HOLDERS "hint") is line 1 only, muted
     (overlay.css data-verdict="hint"), with no expiry while the core
     sends it. Holder order: press card, trade, moment, hint: an open
     trade card always outranks it, so it never shows over one. */
  function hintText(c) {
    return { head: fmt.clip(c.head, 34), line2: "", line3: "", verdict: "hint" };
  }

  function slotPart(snap) {
    if (!snap) { return null; }
    if (Object.prototype.hasOwnProperty.call(snap, "card")) {
      var c = snap.card;
      var part = cardPart(c);
      if (!c || !c.head || !partOn(snap, part)) { return null; }
      if (part === "hint") {
        return tradeShown(snap) ? null : { expires: null, text: hintText(c), part: part };
      }
      return { expires: c.expires_at, text: fmt.cardText(c), part: part };
    }
    var ev = snap.eval;
    if (!ev || !ev.text || !ev.text.head || !partOn(snap, "item")) { return null; }
    var e = fmt.evalCard(ev);
    return { expires: ev.expires_at,
             text: { head: e.head, line2: e.item, line3: e.line, verdict: e.verdict } };
  }

  function freshSlot(snap, nowS) {
    var p = slotPart(snap);
    if (p && p.part === "hint") { return p; }
    return (p && typeof p.expires === "number" && nowS < p.expires) ? p : null;
  }

  function withEval(model, snap, nowS) {
    var p = freshSlot(snap, nowS);
    var card = p ? p.text : { head: "", line2: "", line3: "", verdict: "" };
    model.evalHead = card.head;
    model.evalItem = card.line2;
    model.evalLine = card.line3;
    model.evalVerdict = card.verdict;
    /* UX-REVIEW F1: while the card holds the slot, open trade requests
       still show as a count in the status slot, never invisible. */
    var n = (snap && snap.trade_requests) ? snap.trade_requests.length : 0;
    model.trades = (card.head && partOn(snap, "status")) ? fmt.tradeCount(n) : "";
    if (card.head) {
      model.tradeFrom = model.tradeItem = model.tradeWhere = model.tradeMore = "";
    }
    return model;
  }

  /* Milliseconds until the card in the slot leaves, or null. */
  function msUntilEvalExpires(snap, nowS) {
    var p = freshSlot(snap, nowS);
    /* the key hint has no expiry: the next push takes it away */
    if (!p || typeof p.expires !== "number") { return null; }
    return Math.max(250, Math.ceil((p.expires - nowS) * 1000));
  }

  /* OVL-LINE2-GUIDE (plan 03 sections 5.2 and 5.4, S5-FOLLOWUP a): the
     guide entry's short from the core (snap.overlay.guide_short, at most
     GUIDE_MAX characters, already "" outside a guided campaign zone), only
     under the opt-in zone guide setting Always and never in a town or the
     hideout. The overlay never reads the guide's long `line`. */
  var GUIDE_MAX = 34;

  function guideShort(snap) {
    var l = snap && snap.overlay_layout;
    var o = snap && snap.overlay;
    if (!l || l.zone_guide !== "always" || !o || typeof o !== "object") { return ""; }
    if (snap.in_town === true || snap.in_hideout === true) { return ""; }
    return typeof o.guide_short === "string" ? o.guide_short : "";
  }

  /* A death or a level-up keeps the guide line quiet until calm_at (the
     core's event time + 20 s), so "Lv 74  3 deaths" shows the moment. */
  function calmAt(snap) {
    var c = snap.overlay.calm_at;
    return (typeof c === "number" && isFinite(c)) ? c : null;
  }

  /* The guide line due at nowS, or "". */
  function guideText(snap, nowS) {
    var s = guideShort(snap);
    if (!s) { return ""; }
    var calm = calmAt(snap);
    if (calm !== null && !(nowS >= calm)) { return ""; }
    return fmt.clip(s, GUIDE_MAX);
  }

  /* Milliseconds until a quiet guide line is due again, or null: the one
     extra wake-up the page folds into its single timer. */
  function msUntilGuideDue(snap, nowS) {
    if (!guideShort(snap)) { return null; }
    var calm = calmAt(snap);
    if (calm === null || !(nowS < calm)) { return null; }
    return Math.max(250, Math.ceil((calm - nowS) * 1000));
  }

  function hudModel(snap, nowS, status) {
    var m = withEval(baseModel(snap, nowS, status), snap, nowS);
    /* OVL-LINE2-GUIDE: under Always the zone card comes first, then the
       guide line (plan 03 section 5.4): while a moment card holds the slot
       (the zone card's line 1 already says the short) line 2 does not
       repeat it. */
    var slot = freshSlot(snap, nowS);
    /* Not enumerable, like hudShown: a visible string the page and the
       render gate read by name (FIELDS), kept out of a dump of the model
       so the model's shape stays as it was with the guide line off. */
    Object.defineProperty(m, "guide", {
      value: (snap && !(slot && slot.part === "moment")) ? guideText(snap, nowS) : "",
      enumerable: false, writable: true, configurable: true
    });
    /* OVL-LINE2-RULE: line 2 is picked last, once the trade count (rank 2)
       is known; it only ever empties level / deaths, never adds text. */
    var l2 = hudLine2(m);
    m.level = l2.level;
    m.deaths = l2.deaths;
    m.guide = l2.guide || "";
    m.sep = (m.level && m.deaths) ? "|" : "";
    /* OVL-PARTS-PAGE: the HUD plate shows only while one of its lines has
       something; with every part off and no failure word it is absent.
       Not enumerable: a boolean for the page, not a visible string, so a
       dump of the model's strings stays as it was. */
    Object.defineProperty(m, "hudShown", {
      value: !!(m.zone || m.timer || m.level || m.deaths || m.guide || statusText(m)),
      enumerable: false, writable: true, configurable: true
    });
    return m;
  }

  function anchorOf(snap) {
    var c = snap && snap.overlay_layout && snap.overlay_layout.corner;
    return (typeof c === "string" && c.indexOf("bottom") === 0) ? "bottom" : "top";
  }

  /* Seconds on the row-1 timer at server time nowS, or null.
     TEST-LIVE-EXIT (decision 0029): an idle log stops the timer at its
     last line (the game may be closed).
     UTIL-MAPRUN-OVL (adjudicator 2026-11-17, option B): while the player is
     inside an open map the timer is the time in that map (runs.py time_s,
     kept across hideout trips), moved on from the snapshot's clock;
     elsewhere it is the time in this zone instance. Same "12m" text, no
     new line or word (design 0001 7.2 and 10). */
  function timerSeconds(snap, nowS) {
    if (!snap) { return null; }
    var tl = snap.tailer;
    var idle = !!(tl && tl.consented && tl.idle);
    var until = (idle && typeof tl.last_line_at === "number")
      ? Math.min(nowS, tl.last_line_at) : nowS;
    var cur = snap.maps && snap.maps.current;
    /* Design review F1: an idle log pauses the map (inside turns false) while
       the player still stands in it; keep its frozen map time then. */
    var here = cur && (cur.inside === true ||
      (idle && !snap.in_hideout && cur.name && cur.name === snap.zone));
    if (here && typeof cur.time_s === "number" && isFinite(cur.time_s) &&
        typeof snap.now === "number" && isFinite(until)) {
      /* a clock skew never runs the timer backwards */
      return cur.time_s + Math.max(0, until - snap.now);
    }
    return snap.zone_entered_at ? until - snap.zone_entered_at : null;
  }

  /* The visible HUD strings for a state snapshot.
     nowS: the server clock in seconds (client clock minus offset). */
  function baseModel(snap, nowS, status) {
    if (!snap) {
      /* DS-HUD-EMPTY: before the first snapshot the HUD reads "AshLight"
         and the status word; no lone separator. */
      return { zone: "AshLight", timer: "", level: "", deaths: "", sep: "", away: "", under: "",
               campaign: "", log: "", status: status || W.link_wait.overlay,
               tradeFrom: "", tradeItem: "", tradeWhere: "", tradeMore: "", anchor: "top" };
    }
    var showTrade = partOn(snap, "trade");
    var open = showTrade ? (snap.trade_requests || []) : [];
    var card = fmt.tradeCard(open.length ? open[open.length - 1] : null);
    /* UI-REVIEW-2 (design 0001 7.2): say when Client.txt is not being read.
       Not opted in: no numbers at all (they would be made up). Opted in but
       the file is missing or quiet: keep what is known and say so. A core
       without the tailer field counts as reading. */
    var tl = snap.tailer;
    var idle = !!(tl && tl.consented && tl.idle);
    var elapsed = timerSeconds(snap, nowS);
    if (tl && !tl.consented) {
      return { zone: partOn(snap, "zone") ? "AshLight" : "", timer: "", level: "", deaths: "", sep: "", away: "", under: "",
               campaign: "", log: W.off.overlay, status: status || "live",
               tradeFrom: card.from, tradeItem: card.item, tradeWhere: card.where,
               tradeMore: open.length > 1 ? "+" + (open.length - 1) + " more" : "",
               anchor: anchorOf(snap) };
    }
    /* OVL-PARTS-PAGE: a part that is off yields "" for its fields; the
       separator shows only between a shown level and shown deaths. */
    var quiet = quietHere(snap);
    var words = partOn(snap, "status");
    var level = partOn(snap, "level") ? fmt.levelText(snap.level) : "";
    var deaths = partOn(snap, "deaths") ? fmt.deathsText(snap.deaths) : "";
    return {
      tradeFrom: card.from,
      tradeItem: card.item,
      tradeWhere: card.where,
      tradeMore: open.length > 1 ? "+" + (open.length - 1) + " more" : "",
      anchor: anchorOf(snap),
      zone: (partOn(snap, "zone") && !quiet) ? fmt.zoneText(snap.zone, snap.in_hideout) : "",
      timer: (snap.zone && partOn(snap, "timer") && !quiet) ? fmt.minutes(elapsed) : "",
      level: level,
      deaths: deaths,
      sep: (level && deaths) ? "|" : "",
      /* DS-HUD-AFK: the log's AFK / DND state (design 0001 7.2). */
      away: !words ? "" : (snap.afk ? "AFK" : (snap.dnd ? "DND" : "")),
      /* UTIL-UNDERLEVEL: the core's word ("4 lv under", <= 15 chars),
         only while the player is the set gap under the zone level. */
      under: words ? underWord(snap) : "",
      /* UTIL-CAMPAIGN-CHECKS: the core's campaign hint word, last in the
         slot so it never hides AFK / DND or the under-level word. */
      campaign: words ? campaignWord(snap) : "",
      /* UX-COPY: a known file that is quiet is not missing. Telegraphic so
         it fits after "Lv 100 | 99 deaths" in the 258 px plate (design
         review F1: "waiting for Client.txt" clipped). RUN-UNREADABLE-WORD:
         a file that is there but can't be read is named first, the same
         state as the bar (web/status.js readingState). */
      log: (tl && tl.unreadable) ? W.unreadable.overlay
        : idle ? IDLE_WORD
        : ((tl && !tl.reading) ? (tl.path ? W.waiting.overlay : W.missing.overlay) : ""),
      status: status || "live"
    };
  }

  /* The word in the HUD status slot: a connection problem first, then the
     Client.txt state, then the open trade count while a card hides the
     trade card, then the under-level word, then AFK / DND, then the
     campaign hint word, else nothing. OVL-PARTS-PAGE: rank 1 (connection
     and Client.txt words) shows whatever parts.status says; the model
     already holds "" for the lower ranks when the status part is off. */
  function statusWord(model) {
    if (model.status !== "live") { return model.status || ""; }
    return highWord(model) || model.campaign || "";
  }

  /* Ranks 1 to 4: the words the guide line yields to at once. */
  function highWord(model) {
    if (model.status !== "live") { return model.status || ""; }
    return model.log || model.trades || model.under || model.away || "";
  }

  function statusText(model) {
    return hudLine2(model).status;
  }

  /* OVL-LINE2-RULE (plan 03 sections 5.1 and 5.2, TD-17): HUD line 2 shows
     one thing, by one order, first match:
       1 the connection / Client.txt word (alone before any data: the model
         holds no level then), 2 "N trades" while a card covers an open
         trade, 3 the under-level word, 4 AFK / DND, 5 the zone-guide line
         (OVL-LINE2-GUIDE: model.guide, set by hudModel only while it is
         due; alone on the line, it replaces level and deaths and yields at
         once to ranks 1 to 4), 6 the campaign hint word, 7 level and
         deaths alone.
     Width rule (the 258 px plate, 236 px inside): the level text and the
     status word are at most LINE2_MAX characters together, else the deaths
     text drops (and the level text too if still over); a word over
     WORD_BESIDE_MAX stands alone, clipped to
     WORD_ALONE_MAX. Pure: model inputs in, {level, deaths, status} out,
     plus guide only when rank 5 fires. */
  var LINE2_MAX = 26;
  var WORD_BESIDE_MAX = 20;
  var WORD_ALONE_MAX = STATUS_WORDS.overlay_alone_max;

  function hudLine2(inp) {
    var m = inp || {};
    if (m.guide && !highWord(m) && m.status === "live") {
      return { level: "", deaths: "", status: "", guide: fmt.clip(m.guide, GUIDE_MAX) };
    }
    var word = statusWord(m);
    var level = m.level || "";
    var deaths = m.deaths || "";
    if (word.length > WORD_BESIDE_MAX) {
      return { level: "", deaths: "", status: fmt.clip(word, WORD_ALONE_MAX) };
    }
    if (word && fmt.line2Length(level, deaths, word) > LINE2_MAX) { deaths = ""; }
    /* design review L2-1: a level text and word still over the rule with
       the deaths text gone ("Lv unknown" + a 20-character word) leave the
       word alone, so the line never passes the plate. */
    if (word && fmt.line2Length(level, "", word) > LINE2_MAX) { level = ""; }
    return { level: level, deaths: deaths, status: word };
  }

  function underWord(snap) {
    var u = snap && snap.underlevel;
    var w = u && typeof u.word === "string" ? u.word : "";
    return w.length <= 15 ? w : "";
  }

  /* UTIL-CAMPAIGN-CHECKS: the core's campaign hint word ("Cold res 32%",
     <= 15 chars) in the same status slot, after the under-level word. */
  function campaignWord(snap) {
    var c = snap && snap.campaign;
    var w = c && typeof c.word === "string" ? c.word : "";
    return w.length <= 15 ? w : "";
  }

  function shouldRender(prev, next) {
    if (!prev) { return true; }
    for (var i = 0; i < FIELDS.length; i++) {
      if (prev[FIELDS[i]] !== next[FIELDS[i]]) { return true; }
    }
    return false;
  }

  /* Field names whose text changed (the page touches only those nodes). */
  function changedFields(prev, next) {
    var out = [];
    for (var i = 0; i < FIELDS.length; i++) {
      if (!prev || prev[FIELDS[i]] !== next[FIELDS[i]]) { out.push(FIELDS[i]); }
    }
    return out;
  }

  /* Decision 0029 amendment (DESKTOP-CLIENT): may the overlay show? Not
     while a live core reports the 0029 idle "game may be closed" state
     (snapshot game_idle; Client.txt staleness only, no process or window
     check). Offline or no state yet: shown, so the HUD can say so. The
     next fresh log line clears game_idle and the overlay comes back. */
  function overlayWanted(snap, status) {
    if (status !== "live" || !snap) { return true; }
    if (typeof snap.game_idle === "boolean") { return !snap.game_idle; }
    var tl = snap.tailer;
    return !(tl && tl.consented && tl.idle);
  }

  return { FIELDS: FIELDS, hudModel: hudModel, msUntilEvalExpires: msUntilEvalExpires,
           msUntilGuideDue: msUntilGuideDue, GUIDE_MAX: GUIDE_MAX,
           timerSeconds: timerSeconds, overlayWanted: overlayWanted,
           shouldRender: shouldRender,
           changedFields: changedFields, statusText: statusText, IDLE_WORD: IDLE_WORD,
           hudLine2: hudLine2, LINE2_MAX: LINE2_MAX, WORD_BESIDE_MAX: WORD_BESIDE_MAX,
           WORD_ALONE_MAX: WORD_ALONE_MAX,
           STATUS_WORDS: STATUS_WORDS };
}));
