/* AshLight dashboard: pure view helpers (UI-REVIEW-2, design 0003). UMD:
   CommonJS for node --test (app/test/dashboard.test.js), window.ALDash for
   the page. No DOM, no timers, no network. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALDash = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function pill(state, glyph, word) { return { state: state, glyph: glyph, word: word }; }

  var IDLE_WORD = "quiet for 20 min - game closed or AFK?";

  /* TEST-LIVE-EXIT: the time the zone, act and map clocks count to. While
     the log is idle they stop at its last line instead of running on. */
  function clockUntil(tailer, now) {
    if (tailer && tailer.idle && typeof tailer.last_line_at === "number") {
      return Math.min(now, tailer.last_line_at);
    }
    return now;
  }

  /* The connection pill. event: "notoken" | "open" | "error". everLive:
     the feed was live at least once on this page. A failure before that
     says what to do; one after it is a reconnect. */
  function linkView(event, everLive) {
    if (event === "notoken") {
      return pill("failed", "[x]", "open AshLight from the link it showed at start");
    }
    if (event === "open") { return pill("done", "[+]", "live"); }
    return everLive ? pill("pending", "[ ]", "reconnecting")
                    : pill("failed", "[x]", "can't reach AshLight - restart it");
  }

  /* The Client.txt pill. While the feed is down the page cannot know, so
     it says so instead of repeating the last (possibly stale) state. */
  function readingView(tailer, live) {
    if (!live || !tailer) { return pill("pending", "[ ]", "Client.txt status unknown"); }
    /* TEST-LIVE-EXIT (decision 0029): no line for 20 minutes - the game
       may be closed, or the player is away. Never "closed": a guess. */
    if (tailer.consented && tailer.idle) { return pill("blocked", "[#]", IDLE_WORD); }
    if (tailer.reading) { return pill("running", "[>]", "reading Client.txt"); }
    if (tailer.consented) {
      return pill("blocked", "[#]", tailer.path ? "waiting for Client.txt"
                                                : "Client.txt not found - start the game once");
    }
    return pill("idle", "[-]", "not reading Client.txt");
  }

  function kindOf(row) {
    if (row.trade) { return "trade"; }
    switch (row.type) {
      case "whisper_in": return "from";
      case "whisper_out": return "to";
      case "death": return "death";
      case "level_up": return "level";
      case "scene_changed": case "area_entered": case "area_generated": return "zone";
      case "trade_accepted": case "trade_cancelled": return "trade";
      case "tailer_started": case "tailer_reset": case "session_connect": return "log";
      case "afk_changed": case "dnd_changed": return "status";
      case "player_joined_area": case "player_left_area": return "party";
      case "hint": return "tip";
      default: return "info";
    }
  }

  /* UX-PERF: a cheap identity for the recent list (it is capped at 30
     rows and only ever appends at the end, dropping the oldest), so the
     page skips rebuilding the rows when a push did not change it. */
  function eventsKey(rows) {
    var list = rows || [];
    var first = list[0];
    var last = list[list.length - 1];
    function one(r) { return r ? r.at + "|" + r.type + "|" + r.text : ""; }
    return list.length + "#" + one(first) + "#" + one(last);
  }

  function emptyText(consented) {
    return consented
      ? "Nothing yet. Zones, level-ups, deaths and whispers show up here as you play."
      : "Nothing yet. Allow reading Client.txt above, then zones, level-ups, deaths and whispers show up here.";
  }

  /* UX-U9 (design 0001 rule 9: empty states say what will appear and
     when): the line under the session timer. AFK / DND when set; before
     the Client.txt opt-in the "--:--" timer says when it starts. */
  function sessionSub(afk, dnd, consented) {
    var flags = [];
    if (afk) { flags.push("AFK"); }
    if (dnd) { flags.push("DND"); }
    if (flags.length) { return flags.join(" / "); }
    return consented ? "\u00a0" : "Starts when you allow reading Client.txt";
  }

  /* UX-FIRSTRUN (design 0001 rule 7, honest): before the Client.txt
     opt-in nothing has been counted, so the deaths tile shows no number
     (the overlay shows none either) and the line says when counting
     starts. */
  function countsView(deaths, levelUps, consented) {
    if (!consented) { return { deaths: "-", levelups: "Counts once reading starts" }; }
    var n = Number(levelUps) || 0;
    return { deaths: String(Number(deaths) || 0),
             levelups: n + (n === 1 ? " level-up" : " level-ups") };
  }

  /* The core sends each open card's sentence (state.py trade_card_text);
     an older core without it gets a plain, honest line. */
  function tradeLine(t) {
    if (t && typeof t.text === "string" && t.text) {
      return { what: t.text, where: typeof t.where === "string" ? t.where : "" };
    }
    var who = (t && t.from) ? String(t.from) : "Unknown player";
    var item = (t && t.item) ? String(t.item) : "an item";
    return { what: who + " wants " + item + " - trade request", where: "" };
  }

  function cornerLabel(c) {
    var s = String(c || "").replace("-", " ");
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  /* TC-SNAP-UI: the game-data credit line from GET /api/version. The core
     sends data_credit only while the snapshot cache exists (decision 0009);
     no credit means no line, never a placeholder. */
  function dataCreditText(doc) {
    var c = doc && doc.data_credit;
    return (c && typeof c.credit === "string") ? c.credit : "";
  }

  return { linkView: linkView, readingView: readingView, kindOf: kindOf,
           IDLE_WORD: IDLE_WORD, clockUntil: clockUntil,
           emptyText: emptyText, eventsKey: eventsKey, sessionSub: sessionSub, countsView: countsView, tradeLine: tradeLine, cornerLabel: cornerLabel,
           dataCreditText: dataCreditText };
}));
