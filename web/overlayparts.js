/* AshLight dashboard: the 'Overlay shows' group of Settings, Overlay
   (OVL-PARTS-WEB; findings F-118, TD-17; plan 03 section 4, Overlay row).
   UMD: CommonJS for node --test (app/test/overlayparts.test.js),
   window.ALOverlayParts for the page.

   The player picks what the overlay shows in one place: one switch per
   overlay part (server/al/layout.py PARTS), two presets (Full: every part
   on; Cards only: the five top-line parts off, the four cards on), 'Hide
   the zone line in town and hideout' (quiet_town) and 'Zone guide on the
   overlay' (zone_guide: On entry, Always, Never). Each change saves at
   once as a partial change to POST /api/overlay-layout (the core merges
   it into the stored layout, config/local.json) and the overlay follows
   the published layout within a second. A switch or a preset sends the
   whole parts object and nothing else; the core fills a missing part as
   on, so the switches never send half a set.

   The button 'Show a sample card for 10 s' posts POST /api/overlay-sample
   once per click (a click while one is in flight is ignored); the core
   shows the card for 10 s and it leaves by itself. The sample is a press
   card, so the overlay hides it while Item check card is off; the status
   line says so.

   fill(document, doc) takes the GET /api/overlay-layout document (or its
   layout), wire(document, api) binds the controls (api is web/app.js's
   api(method, path, body) promise), load(document, api) is the first read.
   Every answer goes to #parts-status, a plain line: not a live region (the
   page keeps at most 6). No timer, no clipboard, nothing sent to the game;
   every text is set with textContent. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALOverlayParts = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var PATH = "/api/overlay-layout";
  var SAMPLE_PATH = "/api/overlay-sample";
  // server/al/layout.py PARTS, in the order the switches show
  var PARTS = ["zone", "timer", "level", "deaths", "status", "trade", "item", "moment", "hint"];
  // the top line of the overlay; the other parts are cards
  var HUD = ["zone", "timer", "level", "deaths", "status"];
  // server/al/layout.py ZONE_GUIDE; the first is the default
  var ZONE_GUIDE = ["entry", "always", "never"];
  var PRESETS = { full: {}, cards: {} };
  PARTS.forEach(function (name) {
    PRESETS.full[name] = true;
    PRESETS.cards[name] = HUD.indexOf(name) < 0;
  });
  // the controls in index.html (Settings, Overlay)
  var IDS = { quiet: "parts-quiet-town", guide: "parts-zone-guide", full: "parts-full",
              cards: "parts-cards", sample: "parts-sample", status: "parts-status" };
  var SAY = {
    saving: "Saving...",
    saved: "Saved. The overlay follows within a second.",
    failed: "Not saved. Try again.",
    load: "Can't load the overlay settings. Is AshLight running?",
    sample: "Sample card on the overlay for 10 s.",
    sampleHidden: "Sample card hidden: Item check card is off. Turn it on to see the card.",
    sampleFailed: "Sample card not shown. Try again."
  };

  function partId(name) { return "part-" + name; }

  function byId(doc, id) { return doc.getElementById(id); }

  function say(doc, text) {
    var n = byId(doc, IDS.status);
    if (n) { n.textContent = text; }
  }

  /* The switches, the town switch and the zone guide choice from a layout
     document ({layout: {...}}) or a bare layout. A part that is not false
     is on (the core's default). False when there is no layout. */
  function fill(doc, d) {
    var l = d && typeof d === "object" && d.layout && typeof d.layout === "object" ? d.layout : d;
    if (!l || typeof l !== "object") { return false; }
    var parts = l.parts && typeof l.parts === "object" ? l.parts : {};
    PARTS.forEach(function (name) {
      var box = byId(doc, partId(name));
      if (box) { box.checked = parts[name] !== false; }
    });
    var quiet = byId(doc, IDS.quiet);
    if (quiet) { quiet.checked = l.quiet_town === true; }
    var guide = byId(doc, IDS.guide);
    if (guide) {
      guide.value = ZONE_GUIDE.indexOf(l.zone_guide) >= 0 ? l.zone_guide : ZONE_GUIDE[0];
    }
    return true;
  }

  /* {part: on} for every part, as the switches show it now. */
  function readParts(doc) {
    var out = {};
    PARTS.forEach(function (name) {
      var box = byId(doc, partId(name));
      out[name] = !!(box && box.checked);
    });
    return out;
  }

  /* A copy of a preset's parts ("full" or "cards"); null for another name. */
  function presetParts(name) {
    var p = Object.prototype.hasOwnProperty.call(PRESETS, name) ? PRESETS[name] : null;
    if (!p) { return null; }
    var out = {};
    PARTS.forEach(function (n) { out[n] = p[n]; });
    return out;
  }

  // one wired page; seq makes only the newest save's answer fill the form
  var state = { api: null, seq: 0, sampleBusy: false };

  function save(doc, body) {
    state.seq += 1;
    var mine = state.seq;
    say(doc, SAY.saving);
    return state.api("POST", PATH, body).then(function (d) {
      if (mine !== state.seq) { return; }
      fill(doc, d);
      say(doc, SAY.saved);
    }).catch(function () {
      if (mine === state.seq) { say(doc, SAY.failed); }
    });
  }

  function applyPreset(doc, name) {
    var parts = presetParts(name);
    PARTS.forEach(function (n) {
      var box = byId(doc, partId(n));
      if (box) { box.checked = parts[n]; }
    });
    return save(doc, { parts: parts });
  }

  function sample(doc) {
    if (state.sampleBusy) { return null; }
    state.sampleBusy = true;
    var item = byId(doc, partId("item"));
    var shown = !item || item.checked;
    return state.api("POST", SAMPLE_PATH, {}).then(function () {
      say(doc, shown ? SAY.sample : SAY.sampleHidden);
    }).catch(function () {
      say(doc, SAY.sampleFailed);
    }).then(function () { state.sampleBusy = false; });
  }

  function on(doc, id, type, fn) {
    var n = byId(doc, id);
    if (n) { n.addEventListener(type, fn); }
  }

  /* Bind every control once; nothing is read until load(). */
  function wire(doc, api) {
    state.api = api;
    PARTS.forEach(function (name) {
      on(doc, partId(name), "change", function () { save(doc, { parts: readParts(doc) }); });
    });
    on(doc, IDS.quiet, "change", function () {
      save(doc, { quiet_town: !!byId(doc, IDS.quiet).checked });
    });
    on(doc, IDS.guide, "change", function () {
      var v = byId(doc, IDS.guide).value;
      if (ZONE_GUIDE.indexOf(v) >= 0) { save(doc, { zone_guide: v }); }
    });
    on(doc, IDS.full, "click", function () { applyPreset(doc, "full"); });
    on(doc, IDS.cards, "click", function () { applyPreset(doc, "cards"); });
    on(doc, IDS.sample, "click", function () { sample(doc); });
  }

  /* The first read (GET /api/overlay-layout), run on connect. */
  function load(doc, api) {
    return api("GET", PATH).then(function (d) {
      if (!fill(doc, d)) { say(doc, SAY.load); }
    }).catch(function () { say(doc, SAY.load); });
  }

  return { PATH: PATH, SAMPLE_PATH: SAMPLE_PATH, PARTS: PARTS, HUD: HUD,
           ZONE_GUIDE: ZONE_GUIDE, PRESETS: PRESETS, IDS: IDS, SAY: SAY,
           fill: fill, readParts: readParts, presetParts: presetParts,
           wire: wire, load: load };
}));
