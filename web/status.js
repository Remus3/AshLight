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
      case "scene_changed": case "area_entered": return "zone";
      case "tailer_started": case "tailer_reset": return "log";
      case "afk_changed": case "dnd_changed": return "status";
      case "player_joined_area": case "player_left_area": return "party";
      default: return "info";
    }
  }

  function emptyText(consented) {
    return consented
      ? "Nothing yet. Zones, level-ups, deaths and whispers show up here as you play."
      : "Nothing yet. Allow reading Client.txt above, then zones, level-ups, deaths and whispers show up here.";
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

  return { linkView: linkView, readingView: readingView, kindOf: kindOf,
           emptyText: emptyText, tradeLine: tradeLine, cornerLabel: cornerLabel };
}));
