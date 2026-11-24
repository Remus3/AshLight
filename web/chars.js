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
   card's pace page; web/acts.js still reads its choice (#char-pick).

   RUN-CHARACTER-PIN (F-157): a 'This is my character' toggle button
   (#char-pin, aria-pressed) after the picker pins the character the
   picker shows (the picked one, else the one being played): one click
   posts POST /api/character, which writes the same "character" setting a
   player could type into config/local.json; a click on the pressed pin
   frees it (""). A pinned character never switches (decision 0038). The
   picker line shows from the first character on, so the pin is there
   with one character too. The only network use of this file, and only
   on that click.

   CP-2 (RUN-CHARACTER-PIN design finding S3): a pin save that fails keeps
   its muted line (#char-pin-said, not a live region) and is also said in
   the page's one shared polite line, the header's #tab-news, through
   ALTabs.say (design 0001 N6, as SAVE-FAIL-SAY; a region of its own would
   breach the 6-region cap of tests/test_a11y.py), so it is heard while
   focus has left the button. */
(function (root, factory) {
  "use strict";
  var common = typeof module === "object" && module.exports;
  var api = factory(function () {
    return common ? require("./acts.js") : root.ALActs;
  }, function () {
    return common ? require("./tabs.js") : root.ALTabs;
  });
  if (common) {
    module.exports = api;
  } else {
    root.ALChars = api;
    /* TEST-WEB-PANELS-C2 (F-135): the Characters card registers itself
       (web/registry.js) as "chars", order 50, the name and order web/app.js
       gave it. UTIL-MULTICHAR: pick is the character the player picked
       ("" = the one playing); on its wire the card fills app.js's charLink
       with view(s), the picked character's numbers for every other panel
       (the playing one's when the view cannot be made), and a pick paints
       the last push again in full. */
    if (root.ALApp && typeof root.ALApp.register === "function") {
      var pick = "";
      root.ALApp.register({
        name: "chars",
        order: 50,
        paint: function (s) { api.paint(document, s, pick); },
        wire: function () {
          var host = root.ALApp.host;
          host.charLink.view = function (s) {
            try { return api.view(s, pick); } catch (e) { return s; }
          };
          api.wire(document, function (name) {
            pick = name;
            host.repaint();
          });
        }
      });
    }
  }
}(typeof self !== "undefined" ? self : this, function (actsLib, tabsLib) {
  "use strict";

  var MAX = 12;
  var PLAYING = " (playing now)";
  var NOT_PLAYING = " (not playing)";
  var HISTORY_ONLY = " (history only)";
  /* rows a page under the picker: 32 + 4 + 8 x 22 + pager 24 = 236 of the
     244 px under the title at 1280x760 (compact 32 + 4 + 6 x 22 + 24 = 192
     of 204 at 1024x700) */
  var ROWS = { full: 8, compact: 6 };
  var PIN_LABEL = "This is my character";
  var PIN_FAILED = "AshLight couldn't save that.";
  var PIN_PATH = "/api/character";
  /* the last painted snapshot and pick, and the click's api (wire) */
  var pinState = { snap: null, picked: "", api: null, busy: false };

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

  /* The name the pin acts on: the picked one, else the one being played. */
  function shownName(snap, picked) {
    var list = names(snap);
    var p = picked ? find(list, picked) : null;
    if (p && !p.current) { return p.name; }
    return snap && typeof snap.character === "string" && snap.character ? snap.character : "";
  }

  /* Pressed while the shown character is the pinned one. */
  function pinPressed(snap, picked) {
    return !!(snap && snap.character_pinned && snap.character &&
      shownName(snap, picked) === snap.character);
  }

  /* The pin button, made once after the picker in its line. */
  function pinButton(doc, box) {
    var b = doc.getElementById("char-pin");
    if (b) { return b; }
    b = doc.createElement("button");
    b.setAttribute("type", "button");
    b.setAttribute("id", "char-pin");
    b.className = "chip";
    b.setAttribute("data-label", PIN_LABEL);
    b.setAttribute("aria-pressed", "false");
    b.setAttribute("aria-describedby", "char-pin-said");
    b.textContent = PIN_LABEL;
    box.appendChild(b);
    var said = doc.createElement("span");
    said.setAttribute("id", "char-pin-said");
    said.className = "muted";
    box.appendChild(said);
    b.addEventListener("click", function () { pinClick(doc); });
    return b;
  }

  /* Say a line in the header's polite #tab-news (ALTabs.say); a page
     without tabs says nothing. */
  function say(doc, text) {
    var t = tabsLib();
    if (t && typeof t.say === "function") { t.say(doc, text); }
  }

  /* One click: pin the shown character, or free it when pressed. */
  function pinClick(doc) {
    var api = pinState.api;
    if (typeof api !== "function") {
      var host = typeof self !== "undefined" && self.ALApp && self.ALApp.host;
      api = host && typeof host.api === "function" ? host.api : null;
    }
    var snap = pinState.snap;
    var b = doc.getElementById("char-pin");
    var said = doc.getElementById("char-pin-said");
    if (!b || pinState.busy || !api || !snap) { return null; }
    var name = pinPressed(snap, pinState.picked) ? "" : shownName(snap, pinState.picked);
    if (!name && !snap.character_pinned) { return null; }
    pinState.busy = true;
    b.setAttribute("aria-disabled", "true");
    if (said) { said.textContent = ""; }
    var p;
    try { p = api("POST", PIN_PATH, { name: name }); } catch (e) { p = Promise.reject(e); }
    return Promise.resolve(p).then(function (res) {
      pinState.busy = false;
      b.setAttribute("aria-disabled", "false");
      var on = !!(res && res.pinned);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    }, function () {
      pinState.busy = false;
      b.setAttribute("aria-disabled", "false");
      if (said) { said.textContent = PIN_FAILED; }
      say(doc, PIN_FAILED);
    });
  }

  /* Fill the selector and the pin; hidden while there is no character. */
  function paintPicker(doc, list, picked, snap) {
    var box = doc.getElementById("char-pick-box");
    var sel = doc.getElementById("char-pick");
    if (!box || !sel) { return; }
    box.hidden = list.length < 1;
    pinState.snap = snap || null;
    pinState.picked = picked || "";
    var pin = pinButton(doc, box);
    pin.hidden = !shownName(snap, picked);
    if (!pinState.busy) {
      pin.setAttribute("aria-pressed", pinPressed(snap, picked) ? "true" : "false");
    }
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
    paintPicker(doc, list, picked, snap);
    if (!doc.getElementById("chars-rows")) { return; }
    actsLib().fill(doc, "chars-rows", "characters", charRows(snap), ROWS);
    var empty = doc.getElementById("chars-empty");
    if (empty) { empty.hidden = list.length > 0; }
  }

  /* onPick(name or "") on the player's change. api(method, path, body)
     -> promise of the JSON reply, for the pin's click (app.js api(); left
     out, the page's window.ALApp.host.api is used at the click). */
  function wire(doc, onPick, api) {
    pinState.api = typeof api === "function" ? api : null;
    var sel = doc.getElementById("char-pick");
    if (!sel) { return; }
    sel.addEventListener("change", function () { onPick(sel.value || ""); });
  }

  return { names: names, view: view, paint: paint, wire: wire, charRows: charRows,
    bestsText: bestsText, ROWS: ROWS, MAX: MAX, PLAYING: PLAYING,
    shownName: shownName, pinPressed: pinPressed, PIN_LABEL: PIN_LABEL,
    PIN_FAILED: PIN_FAILED,
    NOT_PLAYING: NOT_PLAYING, HISTORY_ONLY: HISTORY_ONLY };
}));
