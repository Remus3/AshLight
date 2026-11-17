/* AshLight dashboard: the per-character selector (UTIL-MULTICHAR, decision
   0038). UMD: CommonJS for node --test (app/test/chars.test.js),
   window.ALChars for the page. The core keys level, deaths, pace, act times
   and run history by the character name the player's own Client.txt
   reports (`characters`, `run_history.by_character`); the page shows the
   character being played by default, and this file only swaps in another
   character's numbers when the player picks one. Not a live region; no
   timers, no network. Names stay on this computer. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALChars = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var MAX = 12;
  var PLAYING = " (playing now)";
  var NOT_PLAYING = " (not playing)";
  var HISTORY_ONLY = " (history only)";

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

  /* Fill the selector; hidden while there is one character or none. */
  function paint(doc, snap, picked) {
    var box = doc.getElementById("char-pick-box");
    var sel = doc.getElementById("char-pick");
    if (!box || !sel) { return; }
    var list = names(snap);
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

  /* onPick(name or "") on the player's change. */
  function wire(doc, onPick) {
    var sel = doc.getElementById("char-pick");
    if (!sel) { return; }
    sel.addEventListener("change", function () { onPick(sel.value || ""); });
  }

  return { names: names, view: view, paint: paint, wire: wire, MAX: MAX, PLAYING: PLAYING,
    NOT_PLAYING: NOT_PLAYING, HISTORY_ONLY: HISTORY_ONLY };
}));
