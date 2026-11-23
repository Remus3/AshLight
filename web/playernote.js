/* AshLight dashboard: the player's own zone note (PLAY-F-186B-PLAYER-NOTES-UI,
   finding F-186, decision 0074).

   One labelled box and a Save button on the zone guide page of the Run tab's
   Acts card. The box shows the note of the zone being played (snap.area_id)
   for the character being played (snap.character), read from the
   snapshot's player_note; Save posts the box's text to POST
   /api/player-note?area=<the shown zone> as text/plain (UTF-8), so the note
   lands on the zone the box shows even when the player moved on while
   typing. An empty box removes the note. The core caps the note at 200
   characters and refuses rather than cuts; the box carries maxlength 200
   too. The character is always the one being played (the core decides), so
   a Save after a character switch is refused here and the box is filled
   again for the new character.

   While the player is typing (the box differs from what was last filled)
   a new snapshot never replaces the box; the zone it names stays the shown
   zone until the next Save or until the box is back to what was filled.

   Play gains no control (design 0001 principle 5): the box is on Run only,
   and the note shows on Play by itself (the guide's 'Your note' row). No
   timer, no clipboard, no live region: the answer line #pn-said is named by
   the box and the button (aria-describedby). Text only through textContent
   and value.

   Registers {name: playernote, order: 265} with the panel registry
   (window.ALApp, web/registry.js): a Run card part, not a Play region, and
   web/regions.js takes no new script tag after slots.js
   (app/test/regions.test.js). The token and the snapshot come from the page
   host (window.ALApp.host, set by web/app.js before start()); the host's
   api() sends JSON only and the route takes text/plain, so the Save is its
   own fetch. UMD like web/tabs.js: CommonJS for node --test
   (app/test/playernote.test.js), window.ALPlayerNote in the page. */
(function (root, factory) {
  "use strict";
  var api = factory(root);
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALPlayerNote = api;
    if (root.ALApp && typeof root.ALApp.register === "function") {
      root.ALApp.register(api.panel(root));
    }
  }
}(typeof self !== "undefined" ? self : this, function (root) {
  "use strict";

  var MAX = 200;  /* server/al/playernotes.py MAX_NOTE */
  var AREA = /^[A-Za-z0-9_]{1,64}$/;  /* playernotes.AREA_RE */
  var SAVED = "Saved. It shows in the zone guide when you enter this zone.";
  var REMOVED = "Note removed.";
  var NO_ZONE = "Enter a zone first, then write your note.";
  var CHAR_CHANGED = "Your character changed, so the box now shows their note. " +
    "Type your note again and save.";
  var FAILED = "Your note wasn't saved. Try again.";
  var OFFLINE = "Can't reach AshLight - is it running?";

  function str(v) { return typeof v === "string" ? v : ""; }

  /* snap -> {area, character, text}: the zone and character being played
     ("" when unknown) and the note the snapshot carries for them. */
  function model(snap) {
    var s = snap && typeof snap === "object" ? snap : {};
    var area = str(s.area_id);
    var character = str(s.character);
    var n = s.player_note;
    var text = n && typeof n === "object" && str(n.area_id) === area ? str(n.text) : "";
    if (!AREA.test(area) || !character) { return { area: "", character: "", text: "" }; }
    return { area: area, character: character, text: text };
  }

  /* The URL a Save posts to for a zone. */
  function saveUrl(area) { return "/api/player-note?area=" + encodeURIComponent(area); }

  /* The answer line for a reply: status, parsed body (or null), the sent
     text. */
  function answer(status, body, text) {
    if (status === 200) { return text.trim() ? SAVED : REMOVED; }
    if (body && typeof body.error === "string" && body.error) { return body.error; }
    return FAILED;
  }

  var st = { doc: null, env: null, shown: null, filled: "", busy: false };

  function node(id) { return st.doc && st.doc.getElementById(id); }

  function setText(n, text) { if (n && n.textContent !== text) { n.textContent = text; } }

  function dirty() {
    var box = node("pn-text");
    return !!(box && st.shown && box.value !== st.filled);
  }

  /* Fill the box from the snapshot unless the player is typing (a
     character switch while typing is caught by save()). */
  function paint(doc, snap) {
    if (doc) { st.doc = doc; }
    var wrap = node("pn"), box = node("pn-text");
    if (!wrap || !box) { return; }
    var m = model(snap);
    if (dirty()) { return; }
    var same = st.shown && st.shown.area === m.area && st.shown.character === m.character;
    if (!same) { setText(node("pn-said"), ""); }
    st.shown = m.area ? m : null;
    wrap.hidden = !st.shown;
    if (box.value !== m.text) { box.value = m.text; }
    st.filled = m.text;
  }

  /* One Save. Returns a promise; never throws. */
  function save() {
    var box = node("pn-text"), btn = node("pn-save"), said = node("pn-said");
    if (!box || st.busy) { return Promise.resolve(); }
    var shown = st.shown;
    if (!shown) { setText(said, NO_ZONE); return Promise.resolve(); }
    var now = model(st.env.getSnap ? st.env.getSnap() : null);
    if (now.character !== shown.character) {
      st.shown = null;
      st.filled = "";
      box.value = "";
      paint(null, st.env.getSnap ? st.env.getSnap() : null);
      setText(said, CHAR_CHANGED);
      return Promise.resolve();
    }
    var text = box.value.slice(0, MAX);
    st.busy = true;
    if (btn) { btn.disabled = true; }
    setText(said, "");
    function done(line) {
      st.busy = false;
      if (btn) { btn.disabled = false; }
      setText(said, line);
    }
    return Promise.resolve().then(function () {
      return st.env.fetch(saveUrl(shown.area), {
        method: "POST",
        headers: { "X-AL-Token": st.env.token, "Content-Type": "text/plain; charset=utf-8" },
        body: text,
        cache: "no-store"
      });
    }).then(function (r) {
      return r.json().then(function (b) { return b; }, function () { return null; })
        .then(function (b) {
          if (r.status === 200) {
            var kept = b && b.note && typeof b.note === "object" ? str(b.note.text) : "";
            st.filled = kept;
            if (box.value === text) { box.value = kept; }
          }
          done(answer(r.status, b, text));
        });
    }).catch(function () { done(OFFLINE); });
  }

  /* ctx: {getSnap, token} from the page host (panel()); tests pass fetch
     too. */
  function wire(doc, ctx) {
    ctx = ctx || {};
    var host = root && root.ALApp && root.ALApp.host ? root.ALApp.host : {};
    st.doc = doc;
    st.env = {
      fetch: ctx.fetch || function (url, opts) { return root.fetch(url, opts); },
      token: ctx.token || host.token || "",
      getSnap: ctx.getSnap || function () { return null; }
    };
    st.shown = null;
    st.filled = "";
    st.busy = false;
    var btn = node("pn-save");
    if (btn) { btn.addEventListener("click", function () { save(); }); }
    paint(doc, st.env.getSnap());
  }

  var NAME = "playernote";
  var ORDER = 265;  /* after the settings transfer's wire (260) */

  /* The registry entry; the page's host is read at wire time. */
  function panel(page) {
    function host() { return page && page.ALApp && page.ALApp.host ? page.ALApp.host : {}; }
    return { name: NAME, order: ORDER,
      wire: function () {
        var h = host();
        wire(page.document, { getSnap: h.getSnap, token: h.token });
      },
      paint: function (snap) { paint(page.document, snap); } };
  }

  return { panel: panel, NAME: NAME, ORDER: ORDER, model: model, saveUrl: saveUrl, answer: answer, wire: wire,
    paint: paint, save: save, MAX: MAX, SAVED: SAVED, REMOVED: REMOVED, NO_ZONE: NO_ZONE,
    CHAR_CHANGED: CHAR_CHANGED, FAILED: FAILED, OFFLINE: OFFLINE };
}));
