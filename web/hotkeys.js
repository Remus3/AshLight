/* AshLight dashboard: the keys the page names (OVL-KEYS-WEB, F-026;
   decision 0058 HOTKEYS-LIVE). UMD like web/settingsio.js: CommonJS for
   node --test (app/test/hotkeys_view.test.js), window.ALHotkeys in the
   page.

   The core publishes the effective keys (snap.hotkeys, server/al/
   hotkeys.py view: eval and toggle, each {key, want, registered,
   fallback}, plus overlay_on). No page text names a key that is not
   bound:
   - paint(doc, snap) writes the bound key into every element with
     data-hotkey="eval" | "toggle". A key the client did not register
     (or no word from the client yet) leaves the element's own words
     ("the item check key"), so a placeholder never reads as a key. A
     fallback shows the alternate the client bound, and the change field
     says which key was taken.
   - wire(doc, env) saves the two change-key fields (#hotkey-eval,
     #hotkey-toggle) on change: POST /api/hotkeys {name, key}; the core
     refuses a game key or the other shortcut's key with a sentence,
     shown as it is. The desktop client re-registers by itself
     (ZERO-CLICK); the field is optional. env: {fetch, token}.
   - the Play line "Overlay off. Press <key> to show it." (at most one
     52-character row) shows only while snap.hotkeys.overlay_on is false
     (the player turned the overlay off). Play's seven regions stay as
     they are in the page (tests/test_a11y.py); the line is one node this
     file adds at the end of region C ("Right now"), hidden otherwise.

   No timers, no clipboard. The answer to a save is said in the overlay
   group's one polite region, #layout-status (the page keeps at most 9
   live regions, so this file adds none); a field's note (a taken key)
   sits beside it in its aria-describedby span. Nothing is sent to the
   game: the core and the client register keys; this page only asks. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALHotkeys = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var NAMES = ["eval", "toggle"];
  var PATH = "/api/hotkeys";
  var FIELD = { eval: "hotkey-eval", toggle: "hotkey-toggle" };
  var SAID = { eval: "hotkey-eval-said", toggle: "hotkey-toggle-said" };
  var STATUS = "layout-status";   // the overlay group's polite region
  var PLAY_REGION = "play-c";
  var PLAY_LINE = "overlay-off-line";
  var FAILED = "Nothing changed. Try again.";
  var OFFLINE = "Can't reach AshLight - is it running?";
  var OFF_NO_KEY = "Overlay off. Turn it on from the tray icon.";

  function isObj(v) { return v !== null && typeof v === "object" && !Array.isArray(v); }
  function str(v) { return typeof v === "string" ? v : ""; }

  function entry(snap, name) {
    var hk = isObj(snap) && isObj(snap.hotkeys) ? snap.hotkeys : null;
    return hk && isObj(hk[name]) ? hk[name] : null;
  }

  /* The key the page may name for `name`: the bound key while the client
     registered it, else "" (nothing is bound, so nothing is named). */
  function shown(snap, name) {
    var e = entry(snap, name);
    return e && e.registered === true ? str(e.key) : "";
  }

  /* The key the player asked for (config, else the built-in default). */
  function wanted(snap, name) {
    var e = entry(snap, name);
    return e ? str(e.want) : "";
  }

  /* The sentence under a change field: a fallback names the taken key
     and the alternate; a key that could not be bound says so. */
  function fieldNote(snap, name) {
    var e = entry(snap, name);
    if (!e) { return ""; }
    var want = str(e.want);
    var key = str(e.key);
    if (e.registered === true && e.fallback === true && key && want && key !== want) {
      return "Another program holds " + want + ", so AshLight uses " + key + " instead.";
    }
    if (e.registered === false) {
      return want ? "Another program holds " + want + ", so this key is off. Type another key."
        : "This key is off. Type another key.";
    }
    return "";
  }

  /* The Play line while the player switched the overlay off, else "". */
  function playLine(snap) {
    var hk = isObj(snap) && isObj(snap.hotkeys) ? snap.hotkeys : null;
    if (!hk || hk.overlay_on !== false) { return ""; }
    var key = shown(snap, "toggle");
    return key ? "Overlay off. Press " + key + " to show it." : OFF_NO_KEY;
  }

  function paintPlayLine(doc, text) {
    var line = doc.getElementById(PLAY_LINE);
    if (!text) {
      if (line) { line.hidden = true; }
      return;
    }
    if (!line) {
      var region = doc.getElementById(PLAY_REGION);
      if (!region) { return; }
      line = doc.createElement("p");
      line.id = PLAY_LINE;
      line.className = "muted overlay-off";
      region.appendChild(line);
    }
    if (line.textContent !== text) { line.textContent = text; }
    line.hidden = false;
  }

  /* Each [data-hotkey] element keeps its own words as the placeholder
     (read once, kept in data-hotkey-words) and shows the bound key in
     their place. */
  function paintSpans(doc, snap) {
    var nodes = typeof doc.querySelectorAll === "function"
      ? doc.querySelectorAll("[data-hotkey]") : [];
    Array.prototype.forEach.call(nodes, function (node) {
      var name = node.getAttribute("data-hotkey");
      if (NAMES.indexOf(name) < 0) { return; }
      var words = node.getAttribute("data-hotkey-words");
      if (words === null) {
        words = node.textContent;
        node.setAttribute("data-hotkey-words", words);
      }
      var text = shown(snap, name) || words;
      if (node.textContent !== text) { node.textContent = text; }
    });
  }

  var dirty = { eval: false, toggle: false };
  var last = null;   // the last painted snapshot

  function paintFields(doc, snap) {
    NAMES.forEach(function (name) {
      var input = doc.getElementById(FIELD[name]);
      if (!input) { return; }
      var want = wanted(snap, name);
      /* never under the player's fingers */
      if (want && !dirty[name] && input !== doc.activeElement && input.value !== want) {
        input.value = want;
      }
      var said = doc.getElementById(SAID[name]);
      if (!said) { return; }
      var note = fieldNote(snap, name);
      if (said.textContent !== note) { said.textContent = note; }
    });
  }

  function paint(doc, snap) {
    if (!doc) { return; }
    last = snap;
    paintSpans(doc, snap);
    paintFields(doc, snap);
    paintPlayLine(doc, playLine(snap));
  }

  /* The answer to one save, from the core's reply. */
  function answer(name, status, body) {
    if (status === 200 && isObj(body) && isObj(body.hotkeys)) {
      var want = wanted(body, name);
      return want ? "Saved. The AshLight app switches to " + want + " by itself." : "Saved.";
    }
    if (status === 400 && isObj(body) && typeof body.error === "string" && body.error) {
      return body.error + " Nothing changed.";
    }
    return FAILED;
  }

  /* One save. env: {fetch, token, tell(text), done(view)}. Returns a
     promise; never throws. */
  function save(name, key, env) {
    env.tell("");
    return env.fetch(PATH, {
      method: "POST",
      headers: { "X-AL-Token": env.token, "Content-Type": "application/json" },
      body: JSON.stringify({ name: name, key: key }),
      cache: "no-store"
    }).then(function (r) {
      return r.json().then(function (b) { return b; }, function () { return null; })
        .then(function (b) {
          env.tell(answer(name, r.status, b));
          if (r.ok && isObj(b) && isObj(b.hotkeys) && env.done) { env.done(b.hotkeys); }
        });
    }).catch(function () { env.tell(OFFLINE); });
  }

  function wire(doc, env) {
    if (!doc || !env) { return; }
    var status = doc.getElementById(STATUS);
    var answered = false;   // the status region holds a key answer now
    var e = {
      fetch: env.fetch, token: env.token,
      tell: function (text) {
        if (!status) { return; }
        if (text || answered) { status.textContent = text; }
        answered = !!text;
      },
      done: function (view) {
        last = { hotkeys: view };
        paint(doc, last);
      }
    };
    NAMES.forEach(function (name) {
      var input = doc.getElementById(FIELD[name]);
      if (!input) { return; }
      input.addEventListener("input", function () {
        dirty[name] = true;
        if (answered) { e.tell(""); }
      });
      input.addEventListener("change", function () {
        var key = str(input.value).trim();
        dirty[name] = false;
        if (!key) { input.value = wanted(last, name); return; }  // an emptied field asks nothing
        save(name, key, e);
      });
    });
  }

  return { paint: paint, wire: wire, save: save, shown: shown, wanted: wanted,
    fieldNote: fieldNote, playLine: playLine, answer: answer, PATH: PATH,
    FAILED: FAILED, OFFLINE: OFFLINE, OFF_NO_KEY: OFF_NO_KEY,
    _reset: function () { dirty = { eval: false, toggle: false }; last = null; } };
}));
