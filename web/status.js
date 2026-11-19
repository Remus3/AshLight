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

  /* F-131: the one status vocabulary. The page serves web/ only, so this
     is a copy of server/al/data/status_words.json (without _README);
     tests/test_status_words.py and app/test/statuswords.test.js fail when
     it differs. Edit the JSON, then paste `python -m server.al.statuswords`
     here and in app/shared/render_gate.js. */
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
        "bar": "log quiet - game closed or AFK?",
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

  function statePill(id) { var s = W[id]; return pill(s.kit, s.glyph, s.bar); }

  var IDLE_WORD = W.idle.bar;

  /* TEST-LIVE-EXIT: the time the zone, act and map clocks count to. While
     the log is idle they stop at its last line instead of running on. */
  function clockUntil(tailer, now) {
    if (tailer && tailer.idle && typeof tailer.last_line_at === "number") {
      return Math.min(now, tailer.last_line_at);
    }
    return now;
  }

  /* The feed state id. event: "notoken" | "open" | "error" | "connecting"
     (or none yet). everLive: the feed was live at least once on this
     page. A failure before that says what to do; one after it is a
     reconnect. */
  function linkState(event, everLive) {
    if (event === "notoken") { return "link_token"; }
    if (event === "open") { return "live"; }
    if (event === "connecting" || event == null) { return "link_wait"; }
    return everLive ? "link_retry" : "link_down";
  }

  /* The Client.txt state id (server/al/statuswords.py reading_state is
     the same rule). While the feed is down the page cannot know, so it
     says so instead of repeating the last (possibly stale) state.
     TEST-LIVE-EXIT (decision 0029): no line for 20 minutes - the game may
     be closed, or the player is away. Never "closed": a guess. */
  function readingState(tailer, live) {
    if (!live || !tailer) { return "unknown"; }
    if (tailer.consented && tailer.idle) { return "idle"; }
    if (tailer.reading) { return "reading"; }
    if (tailer.consented) { return tailer.path ? "waiting" : "missing"; }
    return "off";
  }

  /* The connection pill. */
  function linkView(event, everLive) { return statePill(linkState(event, everLive)); }

  /* The Client.txt pill. */
  function readingView(tailer, live) { return statePill(readingState(tailer, live)); }

  /* The one bar status word: the worse of the reading and the feed state
     (table rank; a tie goes to the reading state). link and everLive as
     for linkView. {state, glyph, word, id, next}. */
  function barStatus(tailer, link, everLive) {
    var feed = linkState(link, everLive);
    var read = readingState(tailer, feed === "live");
    var id = W[feed].rank > W[read].rank ? feed : read;
    var p = statePill(id);
    p.id = id;
    p.next = W[id].next;
    return p;
  }

  /* The strip's zone sub line next step: the player's one act for the
     bar state, or "" when there is none (then the strip shows its own
     sub line). */
  function zoneNext(tailer, link, everLive) {
    return barStatus(tailer, link, everLive).next;
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
           linkState: linkState, readingState: readingState,
           barStatus: barStatus, zoneNext: zoneNext, STATUS_WORDS: STATUS_WORDS,
           IDLE_WORD: IDLE_WORD, clockUntil: clockUntil,
           emptyText: emptyText, eventsKey: eventsKey, sessionSub: sessionSub, countsView: countsView, tradeLine: tradeLine, cornerLabel: cornerLabel,
           dataCreditText: dataCreditText };
}));
