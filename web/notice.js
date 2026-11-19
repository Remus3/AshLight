/* AshLight dashboard: region N, the notice (TD-14, PLAY-TD-14-NOTICE; plan 03
   sections 3.4, 3.5, 3.8 and 8). One fixed slot shows one notice at a time:
   a broken part, a build question, the game-language note, "Setup: N steps
   left", a data note or a new character's tip. The core composes and caps
   every entry (snap.play.notices, server/al/playview.py, already in pick
   order); web/slots.js noticePick chooses the one to show for the size
   class and counts the rest as "+N more". Each queued notice also lives in
   Settings (Checks) or on its own card, so the count is enough.

   ZERO-CLICK: notices show and leave by themselves on the state push; the
   one action of a notice is optional. No toast, no sound, no timer of its
   own, no network, no clipboard. It never calls ALTabs.notify (the legacy
   path keeps doing that until PLAY-LEGACY-OUT).

   Layout (s = 1): head row 32 px (glyph + state word 20 px / 600, the short
   title 16 px / 600, "+N more" 14 px, at most 1 action button 32 px on the
   right), then up to 2 body rows of 22 px; the compact class keeps the head
   row only and never shows kinds 6 and 7 (noticePick). One amber cue at
   most (F-159): only a warn notice is amber, its word and the 4 px edge
   that repeats it; nothing else in the row takes the status colour.

   The language note's action is Hide. It reuses the stored key of
   web/checks.js (that file is not edited): the click goes through the
   legacy "Hide this notice" button, whose handler writes the key with the
   checks.js helpers, and the hidden state is read back from
   ALChecks._state.dismissed with ALChecks.langModel. A hidden note comes
   back only after it cleared and began again (the checks.js rule).

   One polite live region: the notice box (aria-live="polite"); it is
   repainted only when its text changes, so a state push that changes
   nothing says nothing.

   UMD like web/tabs.js: CommonJS for node --test (app/test/notice.test.js),
   window.ALNotice in the page, registered with web/regions.js as
   {name: notice, region: n, retires: [n-legacy]}. */
(function (root, factory) {
  "use strict";
  var api = factory(root);
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALNotice = api;
    if (root.ALRegions && typeof root.ALRegions.register === "function") {
      root.ALRegions.register(api.spec);
    }
  }
}(typeof self !== "undefined" ? self : this, function (root) {
  "use strict";

  var KIND_LANGUAGE = 3;
  var LABEL_CAP = 12;            // plan 03 3.4: an action label is at most 12 characters
  var HIDE = "Hide";
  /* Server action labels (server/al/playview.py) -> what the click does. */
  var ACTIONS = { "Open Checks": "checks", "Settings": "settings" };
  var TONES = { "needs-operator": "warn", "failed": "bad" };
  var CLASSES = ["full", "compact"];

  function isObj(v) { return v !== null && typeof v === "object"; }
  function str(v) { return typeof v === "string" ? v : ""; }

  function slotsApi() {
    if (root && root.ALSlots) { return root.ALSlots; }
    if (typeof require === "function") {
      try { return require("./slots.js"); } catch (e) { return null; }
    }
    return null;
  }

  function checksApi() {
    if (root && root.ALChecks) { return root.ALChecks; }
    if (typeof require === "function") {
      try { return require("./checks.js"); } catch (e) { return null; }
    }
    return null;
  }

  /* True while the player hid the current game-language note (checks.js
     key: the time this note began). */
  function langHidden(snap, dismissed) {
    var lang = isObj(snap) && isObj(snap.lang) ? snap.lang : null;
    var C = checksApi();
    if (!lang || !lang.text || !C || typeof C.langModel !== "function") { return false; }
    if (dismissed === undefined || dismissed === null) { return false; }
    return C.langModel(lang, dismissed).show === false;
  }

  /* The queue of snap.play.notices, without a hidden language note. */
  function queueOf(snap, dismissed) {
    var play = isObj(snap) && isObj(snap.play) ? snap.play : null;
    var list = play && Array.isArray(play.notices) ? play.notices : [];
    var hidden = langHidden(snap, dismissed);
    return list.filter(function (n) {
      return isObj(n) && !(hidden && n.kind === KIND_LANGUAGE);
    });
  }

  /* The action of a notice: {label, does} or null. The language note's
     is Hide; another notice keeps the core's label when the page knows
     what it does, so a button is never dead. */
  function actionOf(n) {
    if (n.kind === KIND_LANGUAGE) { return { label: HIDE, does: "hide" }; }
    var label = str(n.action);
    if (!label || label.length > LABEL_CAP || !ACTIONS[label]) { return null; }
    return { label: label, does: ACTIONS[label] };
  }

  /* The pure view of region N: {empty, kind, state, tone, glyph, word,
     title, rows, action, more, sizeClass, key}. sizeClass: full or compact
     (anything else, the flow class included, reads as full: every row
     shows and wraps). */
  function model(snap, sizeClass, dismissed) {
    var cls = CLASSES.indexOf(sizeClass) >= 0 ? sizeClass : "full";
    var S = slotsApi();
    var pick = S ? S.noticePick(queueOf(snap, dismissed), cls)
      : { kind: 8, notice: null, more: 0, bodyRows: 0, label: "Notices", text: "none" };
    var m;
    if (!pick.notice) {
      m = { empty: true, kind: 8, state: "idle", tone: "", glyph: "", word: pick.label,
            title: pick.text, rows: [], action: null, more: 0, sizeClass: cls };
    } else {
      var n = pick.notice;
      var rows = (Array.isArray(n.rows) ? n.rows : []).filter(function (r) {
        return typeof r === "string" && r.length > 0;
      }).slice(0, pick.bodyRows);
      m = { empty: false, kind: pick.kind, state: str(n.state) || "idle",
            tone: TONES[n.state] || "", glyph: str(n.glyph), word: str(n.word),
            title: str(n.title), rows: rows, action: actionOf(n),
            more: pick.more > 0 ? pick.more : 0, sizeClass: cls };
    }
    m.key = JSON.stringify([m.kind, m.state, m.glyph, m.word, m.title, m.rows,
                            m.action && m.action.label, m.more, cls]);
    return m;
  }

  /* ---- DOM ---------------------------------------------------------------- */

  function el(doc, tag, cls, text) {
    var n = doc.createElement(tag);
    if (cls) { n.className = cls; }
    if (text !== undefined) { n.textContent = text; }
    return n;
  }

  function sizeClassOf(doc) {
    try {
      var view = doc.defaultView || root;
      if (view && typeof view.getComputedStyle === "function" && doc.documentElement) {
        var v = view.getComputedStyle(doc.documentElement).getPropertyValue("--al-size-class");
        return String(v || "").trim() || "flow";
      }
    } catch (e) { /* no styles: flow */ }
    return "flow";
  }

  function slotOf(doc) {
    return doc && typeof doc.querySelector === "function"
      ? doc.querySelector("[data-slot=\"n\"]") : null;
  }

  var state = { box: null, ctx: null, cls: null, snap: null };

  /* The one box in the slot: the polite live region. */
  function boxOf(doc) {
    if (state.box && state.box.parentNode) { return state.box; }
    var slot = slotOf(doc);
    if (!slot) { return null; }
    var box = el(doc, "div", "notice");
    box.setAttribute("aria-live", "polite");
    slot.appendChild(box);
    state.box = box;
    return box;
  }

  /* Draw a model into the box (only when its key changed). */
  function render(doc, box, m, onAction) {
    if (box.getAttribute("data-key") === m.key) { return false; }
    box.setAttribute("data-key", m.key);
    box.setAttribute("data-kind", String(m.kind));
    box.setAttribute("data-state", m.state);
    box.setAttribute("data-tone", m.tone);
    box.className = "notice" + (m.empty ? " notice-empty" : " edge");
    box.textContent = "";
    var head = el(doc, "div", "notice-head");
    if (m.empty) {
      head.appendChild(el(doc, "p", "notice-label row-title muted", m.word));
      head.appendChild(el(doc, "p", "notice-none row-title muted", m.title));
      box.appendChild(head);
      return true;
    }
    var word = el(doc, "p", "notice-word row-title one-line");
    if (m.glyph) {
      var g = el(doc, "span", "glyph", m.glyph);
      g.setAttribute("aria-hidden", "true");
      word.appendChild(g);
      word.appendChild(doc.createTextNode(" "));
    }
    word.appendChild(doc.createTextNode(m.word));
    head.appendChild(word);
    var title = el(doc, "p", "notice-title row-body one-line", m.title);
    title.setAttribute("title", m.title);
    head.appendChild(title);
    if (m.more > 0) {
      head.appendChild(el(doc, "p", "notice-more row-meta muted", "+" + m.more + " more"));
    }
    if (m.action) {
      var b = el(doc, "button", "notice-act btn-32 secondary", m.action.label);
      b.setAttribute("type", "button");
      b.setAttribute("data-does", m.action.does);
      b.addEventListener("click", function () { onAction(m.action.does); });
      head.appendChild(b);
    }
    box.appendChild(head);
    m.rows.forEach(function (r) {
      var p = el(doc, "p", "notice-row row-body one-line", r);
      p.setAttribute("title", r);
      box.appendChild(p);
    });
    return true;
  }

  function dismissedNow() {
    var C = checksApi();
    var d = C && isObj(C._state) ? C._state.dismissed : undefined;
    return d === undefined ? null : d;
  }

  /* The click of the notice's one action. */
  function act(doc, does) {
    var ctx = state.ctx || {};
    var tabs = ctx.tabs;
    if (does === "hide") {
      // the checks.js handler reads #langbox data-key and writes it with
      // its own helpers (stored key al.lang.dismissed)
      var legacy = doc.getElementById ? doc.getElementById("lang-dismiss") : null;
      if (legacy && typeof legacy.click === "function") {
        legacy.click();
      } else {
        var C = checksApi();
        var lang = isObj(state.snap) && isObj(state.snap.lang) ? state.snap.lang : null;
        if (C && isObj(C._state) && lang) {
          C._state.dismissed = String(lang.since == null ? "" : lang.since);
        }
      }
      paintNow(doc, state.snap);
      return;
    }
    if (!tabs || typeof tabs.show !== "function") { return; }
    if (does === "checks") {
      tabs.show(doc, "settings", false);
      var fold = doc.getElementById ? doc.getElementById("checks") : null;
      if (fold) { fold.open = true; }
      var sum = doc.getElementById ? doc.getElementById("checks-summary") : null;
      if (sum && typeof sum.focus === "function") { sum.focus(); }
    } else if (does === "settings") {
      tabs.show(doc, "settings", true);
    }
  }

  function paintNow(doc, snap) {
    var box = boxOf(doc);
    if (!box) { return; }
    state.snap = snap;
    state.cls = sizeClassOf(doc);
    var m = model(snap, state.cls, dismissedNow());
    render(doc, box, m, function (does) { act(doc, does); });
  }

  function wire(doc, ctx) {
    state.ctx = ctx || {};
    paintNow(doc, null);
  }

  function paint(doc, snap) { paintNow(doc, snap); }

  /* Once a second: repaint only when the size class changed (a window
     resize between two state pushes). */
  function tick(doc) {
    if (state.box && sizeClassOf(doc) !== state.cls) { paintNow(doc, state.snap); }
  }

  var spec = { name: "notice", region: "n", retires: ["n-legacy"],
               wire: wire, paint: paint, tick: tick };

  function reset() {
    state.box = null; state.ctx = null; state.cls = null; state.snap = null;
  }

  return { spec: spec, model: model, queueOf: queueOf, actionOf: actionOf,
           render: render, wire: wire, paint: paint, tick: tick, act: act,
           sizeClassOf: sizeClassOf, HIDE: HIDE, ACTIONS: ACTIONS,
           _state: state, _reset: reset };
}));
