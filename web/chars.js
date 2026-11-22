/* AshLight dashboard: the per-character selector (UTIL-MULTICHAR, decision
   0038). UMD: CommonJS for node --test (app/test/chars.test.js),
   window.ALChars for the page. The core keys level, deaths, pace, act times
   and run history by the character name the player's own Client.txt
   reports (`characters`, `run_history.by_character`); the page shows the
   character being played by default, and this file only swaps in another
   character's numbers when the player picks one. Not a live region; no
   timers, no network. Names stay on this computer.

   PLAY-TD-20B-RUN-CARDS (plan 03 section 4): the Run grid's Characters
   card holds the picker (looking at another character is a review act)
   and one row per character: who is playing, class, level, deaths and the
   best act times from run history, paged at 8 (6 compact) under the
   picker through web/acts.js's pager. The picker moved here from the Acts
   card's pace page; web/acts.js still reads its choice (#char-pick). */
(function (root, factory) {
  "use strict";
  var common = typeof module === "object" && module.exports;
  var api = factory(function () {
    return common ? require("./acts.js") : root.ALActs;
  });
  if (common) {
    module.exports = api;
  } else {
    root.ALChars = api;
  }
}(typeof self !== "undefined" ? self : this, function (actsLib) {
  "use strict";

  var MAX = 12;
  var PLAYING = " (playing now)";
  var NOT_PLAYING = " (not playing)";
  var HISTORY_ONLY = " (history only)";
  /* rows a page under the picker: 32 + 4 + 8 x 22 + pager 24 = 236 of the
     244 px under the title at 1280x760 (compact 32 + 4 + 6 x 22 + 24 = 192
     of 204 at 1024x700) */
  var ROWS = { full: 8, compact: 6 };

  /* [{name, current}] : live characters first (the current one leads),
     then characters seen only in the saved run history; at most MAX. */
  function names(snap) {
    var out = [];
    // a Map, not {}: "constructor" / "toString" / "__proto__" are valid
    // names (AUDIT-P6-LOW P6-3)
    var seen = new Map();
    ((snap && snap.characters) || []).forEach(function (c) {
      if (c && typeof c.name === "string" && c.name && !seen.has(c.name) && out.length < MAX) {
        seen.set(c.name, true);
        out.push({ name: c.name, current: !!c.current });
      }
    });
    var by = (snap && snap.run_history && snap.run_history.by_character) || {};
    Object.keys(by).forEach(function (n) {
      if (n && !seen.has(n) && out.length < MAX) {
        seen.set(n, true);
        out.push({ name: n, current: false });
      }
    });
    return out;
  }

  function find(list, name) {
    for (var i = 0; i < list.length; i++) {
      if (list[i] && list[i].name === name) { return list[i]; }
    }
    return null;
  }

  /* The snapshot with the picked character's numbers in place of the
     current one's. picked "" / null / the current name / an unknown name
     -> the snapshot as it is. */
  function view(snap, picked) {
    if (!snap || !picked || picked === snap.character || !find(names(snap), picked)) {
      return snap;
    }
    var live = find(snap.characters || [], picked);
    var by = (snap.run_history && snap.run_history.by_character) || {};
    var hist = Object.prototype.hasOwnProperty.call(by, picked) ? by[picked] : null;
    if (!live && !hist) { return snap; }
    var out = {};
    Object.keys(snap).forEach(function (k) { out[k] = snap[k]; });
    out.character = picked;
    // the Level tile says whose numbers these are (design review S3/S4)
    out.who_note = live ? NOT_PLAYING : HISTORY_ONLY;
    out["class"] = live ? live["class"] : null;
    out.level = live ? live.level : null;
    out.deaths = live ? live.deaths : 0;
    out.level_ups = live ? live.level_ups : 0;
    out.pace = live ? live.pace : { text: "" };
    var acts = live ? live.acts : null;
    if (!acts && snap.acts) {
      acts = {};
      Object.keys(snap.acts).forEach(function (k) { acts[k] = snap.acts[k]; });
      acts.splits = [];
      acts.zones = [];
      acts.current = null;
    }
    out.acts = acts;
    // underlevel compares the zone the player is in: current character only
    out.underlevel = null;
    // UTIL-CAMPAIGN-CHECKS: the hints read the current level and zone too
    out.campaign = null;
    if (snap.run_history) {
      out.run_history = hist || null;
    }
    return out;
  }

  function own(obj, key) { return Object.prototype.hasOwnProperty.call(obj, key); }

  /* "Act 1 20:00, Act 2 15:00": a run history view's best act times. */
  function bestsText(hist) {
    return ((hist && hist.best) || []).filter(function (b) {
      return b && typeof b.best_text === "string" && b.best_text;
    }).map(function (b) {
      return (b.label || b.key || "Act") + " " + b.best_text;
    }).join(", ");
  }

  /* One row of the Characters card per character (names() order): "Sable
     (playing now): Witch, level 4, 2 deaths; best Act 1 20:00". A
     character seen only in the saved run history has its best times only. */
  function charRows(snap) {
    var s = snap || {};
    var by = (s.run_history && s.run_history.by_character) || {};
    return names(s).map(function (c) {
      var live = find(s.characters || [], c.name);
      var hist = c.current ? s.run_history : (own(by, c.name) ? by[c.name] : null);
      var facts = [];
      if (live) {
        if (live["class"]) { facts.push(live["class"]); }
        if (typeof live.level === "number") { facts.push("level " + live.level); }
        var d = typeof live.deaths === "number" ? live.deaths : 0;
        facts.push(d + (d === 1 ? " death" : " deaths"));
      }
      var best = bestsText(hist);
      var text = c.name + (c.current ? PLAYING : live ? NOT_PLAYING : HISTORY_ONLY);
      if (facts.length) { text += ": " + facts.join(", "); }
      if (best) { text += (facts.length ? "; best " : ": best ") + best; }
      return { text: text };
    });
  }

  /* Fill the selector; hidden while there is one character or none. */
  function paintPicker(doc, list, picked) {
    var box = doc.getElementById("char-pick-box");
    var sel = doc.getElementById("char-pick");
    if (!box || !sel) { return; }
    box.hidden = list.length < 2;
    var key = JSON.stringify(list);
    if (sel.getAttribute("data-key") !== key) {
      sel.setAttribute("data-key", key);
      sel.textContent = "";
      list.forEach(function (c) {
        var o = doc.createElement("option");
        o.value = c.current ? "" : c.name;
        o.textContent = c.name + (c.current ? PLAYING : "");
        sel.appendChild(o);
      });
    }
    var want = picked && find(list, picked) && !find(list, picked).current ? picked : "";
    if (sel.value !== want && doc.activeElement !== sel) { sel.value = want; }
  }

  /* The picker and the Characters card's rows (on each new snapshot). */
  function paint(doc, snap, picked) {
    var list = names(snap);
    paintPicker(doc, list, picked);
    if (!doc.getElementById("chars-rows")) { return; }
    actsLib().fill(doc, "chars-rows", "characters", charRows(snap), ROWS);
    var empty = doc.getElementById("chars-empty");
    if (empty) { empty.hidden = list.length > 0; }
  }

  /* onPick(name or "") on the player's change. */
  function wire(doc, onPick) {
    var sel = doc.getElementById("char-pick");
    if (!sel) { return; }
    sel.addEventListener("change", function () { onPick(sel.value || ""); });
  }

  return { names: names, view: view, paint: paint, wire: wire, charRows: charRows,
    bestsText: bestsText, ROWS: ROWS, MAX: MAX, PLAYING: PLAYING,
    NOT_PLAYING: NOT_PLAYING, HISTORY_ONLY: HISTORY_ONLY };
}));
