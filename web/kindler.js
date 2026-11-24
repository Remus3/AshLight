/* AshLight dashboard: the Build sub-tabs (KINDLER-UI-TABS, decision 0081
   points 7 to 11). The Build and items tab holds the fixed Pasted build
   sub-tab (today's card grid) and up to 6 Kindler sub-tabs, each a Kindler
   editor: Move left / Move right, Rename (at most 32 characters), Close
   with an inline confirm (Close / Keep, focus on Keep; never
   window.confirm), a class and league picker, the tri-state toggles and
   Generate.

   The sub-tabs are a labelled button group (role="group", aria-current
   on the shown one; adjudicator ruling 2026-11-23: no tab roles, the
   Pasted build is six grid cells, not one panel) with the keyboard model
   of web/tabs.js: Left / Right / Home / End move and show, one Tab stop.
   Nothing is dragged. The Pasted build cannot move, close or be renamed.

   State lives in the core (GET / POST /api/gen-builds, KINDLER-STORE): the
   tab list, its order and the shown Kindler tab survive a reload and an
   app exit, so the tabs come back by themselves. Whether the Pasted build
   or the Kindler editor is up is a per-viewer convenience in localStorage
   (try/catch; the page works without it), like web/tabs.js.

   Nothing generates by itself (point 4): only the Generate click posts
   /api/kindler-generate. While its run works the card re-reads that
   run's state ("op": "read", never a calc) every 3 s, at most 30 times.
   Leagues come from the web data answer the page already holds (cached
   poe.ninja names while web data is on, else Standard; point 8); no new
   request. Text goes in through textContent only; no live region (the
   page's shared polite line, ALTabs.say, says a refused change).

   UMD: CommonJS for node (tests/test_kindler_tabs_ui.py), window.ALKindler
   in the page, where it registers itself with window.ALApp
   (web/registry.js) as "kindler", order 175. */
(function (root, factory) {
  "use strict";
  var api = factory(root);
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALKindler = api;
    if (root.ALApp && typeof root.ALApp.register === "function") {
      root.ALApp.register({
        name: api.NAME,
        order: api.ORDER,
        paint: function () { api.paintLeagues(); },
        wire: function () {
          var host = root.ALApp.host;
          var store = null;
          try { store = root.localStorage; } catch (e) { store = null; }
          api.attach(document, {
            request: api.fetcher(host.token),
            store: store,
            later: function (fn, ms) { return setTimeout(fn, ms); },
            leagues: function () {
              var w = typeof host.webState === "function" ? host.webState() : null;
              return w && w.doc ? w.doc : null;
            },
            say: function (text) {
              if (root.ALTabs && typeof root.ALTabs.say === "function") {
                root.ALTabs.say(document, text);
              }
            },
            onConnect: host.onConnect
          });
        }
      });
    }
  }
}(typeof self !== "undefined" ? self : this, function (root) {
  "use strict";

  var NAME = "kindler";
  var ORDER = 175; // after Item info (165), before the panels from 180 on
  var PATH = "/api/gen-builds";
  var GEN = "/api/kindler-generate";
  var STORE_KEY = "ashlight.buildsub";
  var PASTED = "pasted";
  var MAX_LABEL = 32; // genstore.MAX_LABEL
  var POLL_MS = 3000;
  var POLL_MAX = 30; // 90 s: past the engine's 60 s budget
  var CLASSES = ["Druid", "Huntress", "Mercenary", "Monk", "Ranger", "Sorceress",
                 "Warrior", "Witch"];
  var TRI = [["yes", "Yes"], ["no", "No"], ["unsure", "Not sure"]];
  var DEFENCE = [["life", "Life"], ["energy_shield", "Energy shield"],
                 ["hybrid", "Life and shield"], ["unsure", "Not sure"]];
  var TOGGLES = [["melee", "Melee", TRI], ["spell", "Spells", TRI],
                 ["minion", "Minions", TRI], ["bow", "Bow", TRI],
                 ["crit", "Critical hits", TRI], ["defence", "Defence", DEFENCE]];
  var NOTES = {
    calc_off: "not scored (calc off). Turn the calc on in Settings, Checks",
    no_tree: "not scored. The passive tree data is still loading",
    no_score: "not scored. Path of Building could not score these"
  };
  var WORDS = {
    noReach: "Can't reach AshLight - is it running?",
    notSaved: "Not saved. Try again.",
    none: "No result yet. Pick what you want, then press Generate.",
    noMatch: "No build fits these choices. Set one to Not sure and press Generate again.",
    working: "Generating. Path of Building scores up to 12 builds, about a minute at most.",
    busy: "Another Kindler tab is generating. Press Generate again when it is done.",
    slow: "Still generating. The result shows here when it is done.",
    stale: "Your choices changed. Press Generate to update.",
    partial: " Time ran out, so this is the best of the builds scored so far."
  };

  /* -- pure helpers -------------------------------------------------- */

  /* A player label as the store keeps it: control characters removed,
     trimmed, at most MAX_LABEL characters ("" = the default label). */
  function cleanLabel(value) {
    if (typeof value !== "string") { return ""; }
    return value.replace(/[\x00-\x1f\x7f]/g, "").trim().slice(0, MAX_LABEL).trim();
  }

  /* GET / POST /api/gen-builds -> the bar's model, every field checked. */
  function view(doc) {
    var tabs = (doc && Array.isArray(doc.tabs) ? doc.tabs : []).filter(function (t) {
      return t && typeof t.id === "string" && t.id;
    }).map(function (t) {
      return { id: t.id, label: typeof t.label === "string" && t.label ? t.label : "Kindler",
               custom: t.custom_label === true,
               cls: typeof t["class"] === "string" ? t["class"] : "",
               league: typeof t.league === "string" ? t.league : "",
               toggles: t.toggles && typeof t.toggles === "object" ? t.toggles : {},
               result: t.result && typeof t.result === "object" ? t.result : null };
    });
    var ids = tabs.map(function (t) { return t.id; });
    var shown = doc && ids.indexOf(doc.shown) >= 0 ? doc.shown : (ids[0] || "");
    var max = doc && typeof doc.max === "number" ? doc.max : 6;
    var full = tabs.length >= max;
    return { tabs: tabs, shown: shown, max: max, full: full,
             fullText: full ? (doc && typeof doc.full_text === "string" && doc.full_text
               ? doc.full_text : "You can keep 6 Kindler tabs. Close one to add another.") : "" };
  }

  /* Arrow-key move in the sub-tab row: key, the row's ids (Pasted build
     first), the current id -> the next id or null (web/tabs.js step). */
  function step(key, ids, current) {
    var n = ids.length;
    if (!n) { return null; }
    var i = ids.indexOf(current);
    if (i < 0) { i = 0; }
    if (key === "ArrowRight") { return ids[(i + 1) % n]; }
    if (key === "ArrowLeft") { return ids[(i - 1 + n) % n]; }
    if (key === "Home") { return ids[0]; }
    if (key === "End") { return ids[n - 1]; }
    return null;
  }

  function num(n) {
    if (typeof n !== "number" || !isFinite(n)) { return null; }
    var r = Math.round(n);
    return (r < 0 ? "-" : "") + String(Math.abs(r)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }

  /* The card's result line: tab (a view tab) and read (the last
     /api/kindler-generate read answer for it, or null). {text, stale}. */
  function resultText(tab, read) {
    var doc = read && read.result && typeof read.result === "object" ? read.result : null;
    var r = tab ? tab.result : null;
    if (!r) {
      if (doc && doc.best === null && doc.note === "no_match") {
        return { text: WORDS.noMatch, stale: false };
      }
      return { text: WORDS.none, stale: false };
    }
    var best = doc && doc.best && doc.best.template === r.template ? doc.best : null;
    var label = best && typeof best.label === "string" && best.label ? best.label : r.template;
    var text;
    if (r.scored && num(r.dps) !== null && num(r.ehp) !== null) {
      text = label + ": " + num(r.dps) + " DPS, " + num(r.ehp) +
        " EHP. Scored by Path of Building.";
    } else {
      var why = doc && Object.prototype.hasOwnProperty.call(NOTES, doc.note)
        ? NOTES[doc.note] : "not scored";
      text = label + ": " + why + ".";
    }
    if (r.partial) { text += WORDS.partial; }
    return { text: text, stale: r.stale === true };
  }

  /* The league suggestions: the cached poe.ninja names while web data is
     on (GET /api/web-data, already read by the page), else Standard. */
  function leagueNames(web) {
    var names = web && web.web_data === true && Array.isArray(web.leagues)
      ? web.leagues.filter(function (s) { return typeof s === "string" && s; }) : [];
    return names.length ? names.slice(0, 20) : ["Standard"];
  }

  /* fetch with the token header -> {status, body} (body null when it is
     not JSON); a network failure rejects. */
  function fetcher(token) {
    return function (method, path, body) {
      var opts = { method: method, headers: { "X-AL-Token": token }, cache: "no-store" };
      if (body !== undefined) {
        opts.headers["Content-Type"] = "application/json";
        opts.body = JSON.stringify(body);
      }
      return root.fetch(path, opts).then(function (r) {
        return r.json().then(function (b) { return { status: r.status, body: b }; },
          function () { return { status: r.status, body: null }; });
      });
    };
  }

  /* -- the page ------------------------------------------------------ */

  var S = null; // the attached page

  function attach(doc, ctl) {
    var $ = function (id) { return doc.getElementById(id); };
    var s = {
      doc: doc, ctl: ctl, $: $, model: view(null), sub: PASTED, reads: {},
      chain: Promise.resolve(), poll: null, buttons: {}, leagueKey: "",
      mode: "tools"
    };
    S = s;
    try {
      var stored = ctl.store ? ctl.store.getItem(STORE_KEY) : null;
      if (stored === "kindler") { s.want = "kindler"; }
    } catch (e) { /* private window */ }
    buildToggles(s);
    buildClasses(s);
    wire(s);
    paintBar(s);
    if (typeof ctl.onConnect === "function") {
      ctl.onConnect(function () { load(s); });
    } else {
      load(s);
    }
    return s;
  }

  function el(doc, tag, cls, text) {
    var n = doc.createElement(tag);
    if (cls) { n.className = cls; }
    if (text !== undefined) { n.textContent = text; }
    return n;
  }

  function buildClasses(s) {
    var sel = s.$("kindler-class");
    if (!sel) { return; }
    var any = el(s.doc, "option", "", "Any class");
    any.value = "";
    sel.appendChild(any);
    CLASSES.forEach(function (c) {
      var o = el(s.doc, "option", "", c);
      o.value = c;
      sel.appendChild(o);
    });
  }

  function buildToggles(s) {
    var box = s.$("kindler-toggles");
    if (!box) { return; }
    TOGGLES.forEach(function (t) {
      var fs = el(s.doc, "fieldset", "kindler-toggle");
      fs.appendChild(el(s.doc, "legend", "", t[1]));
      t[2].forEach(function (v) {
        var id = "kt-" + t[0] + "-" + v[0];
        var lab = el(s.doc, "label", "kindler-choice");
        lab.setAttribute("for", id);
        var input = el(s.doc, "input");
        input.type = "radio";
        input.name = "kt-" + t[0];
        input.value = v[0];
        input.setAttribute("id", id);
        input.setAttribute("data-toggle", t[0]);
        lab.appendChild(input);
        lab.appendChild(el(s.doc, "span", "", v[1]));
        fs.appendChild(lab);
      });
      box.appendChild(fs);
    });
  }

  function current(s) {
    var m = s.model;
    for (var i = 0; i < m.tabs.length; i++) {
      if (m.tabs[i].id === m.shown) { return m.tabs[i]; }
    }
    return null;
  }

  function rowIds(s) {
    return [PASTED].concat(s.model.tabs.map(function (t) { return t.id; }));
  }

  function shownId(s) { return s.sub === PASTED || !current(s) ? PASTED : s.model.shown; }

  /* The card's status line (no live region); a refusal or failure is
     also said on the page's shared polite line (design N6). */
  var SAID = ["noReach", "notSaved", "busy", "slow"];
  function setStatus(s, text) {
    var n = s.$("kindler-status");
    if (n && n.textContent !== text) { n.textContent = text; }
    if (text && s.ctl.say && SAID.some(function (k) { return WORDS[k] === text; })) {
      s.ctl.say(text);
    }
  }

  function saveSub(s) {
    if (!s.ctl.store) { return; }
    try { s.ctl.store.setItem(STORE_KEY, s.sub === PASTED ? PASTED : "kindler"); } catch (e) { /* off */ }
  }

  function subButton(s, id, label) {
    var b = s.buttons[id];
    if (!b) {
      b = el(s.doc, "button", "subtab");
      b.type = "button";
      b.setAttribute("data-id", id);
      b.setAttribute("id", "kindler-tab-" + id);
      s.buttons[id] = b;
    }
    if (b.textContent !== label) { b.textContent = label; }
    b.setAttribute("data-label", label);
    b.setAttribute("title", label); // a clipped name keeps its full text
    return b;
  }

  /* The bar: Pasted build (fixed, in the markup), the Kindler tabs in the
     store's order, then New. aria-current and the one Tab stop follow the
     shown sub-tab. */
  function paintBar(s) {
    var bar = s.$("kindler-bar");
    var pasted = s.$("kindler-pasted");
    var add = s.$("kindler-new");
    if (!bar || !pasted || !add) { return; }
    var shown = shownId(s);
    var keep = {};
    var next = add;
    /* right to left, a node is moved only when it is out of place, so a
       focused sub-tab is not blurred by a repaint */
    s.model.tabs.slice().reverse().forEach(function (t) {
      var b = subButton(s, t.id, t.label);
      keep[t.id] = true;
      if (b.parentNode !== bar || b.nextSibling !== next) { bar.insertBefore(b, next); }
      next = b;
    });
    Object.keys(s.buttons).forEach(function (id) {
      if (!keep[id]) {
        var b = s.buttons[id];
        if (b.parentNode) { b.parentNode.removeChild(b); }
        delete s.buttons[id];
      }
    });
    [pasted].concat(s.model.tabs.map(function (t) { return s.buttons[t.id]; })).forEach(function (b) {
      var id = b === pasted ? PASTED : b.getAttribute("data-id");
      if (id === shown) { b.setAttribute("aria-current", "true"); } else { b.removeAttribute("aria-current"); }
      b.setAttribute("tabindex", id === shown ? "0" : "-1");
    });
    if (s.model.full) { add.setAttribute("aria-disabled", "true"); } else { add.removeAttribute("aria-disabled"); }
    var note = s.$("kindler-full");
    if (note && !s.model.full) { note.hidden = true; note.textContent = ""; }
    paintPanel(s);
  }

  /* Which view is up: the grid (Pasted build) or the Kindler card. */
  function paintPanel(s) {
    var panel = s.$("panel-build");
    var card = s.$("kindlerbox");
    var tab = s.sub === PASTED ? null : current(s);
    if (panel) {
      if (tab) { panel.setAttribute("data-sub", "kindler"); } else { panel.removeAttribute("data-sub"); }
    }
    if (card) { card.hidden = !tab; }
    if (tab) { paintCard(s, tab); }
  }

  function paintCard(s, tab) {
    var $ = s.$;
    var title = $("kindler-title");
    if (title && title.textContent !== tab.label) { title.textContent = tab.label; }
    if (title) { title.setAttribute("title", tab.label); }
    var ids = s.model.tabs.map(function (t) { return t.id; });
    var at = ids.indexOf(tab.id);
    var left = $("kindler-left"), right = $("kindler-right");
    if (left) {
      if (at <= 0) { left.setAttribute("aria-disabled", "true"); } else { left.removeAttribute("aria-disabled"); }
    }
    if (right) {
      if (at >= ids.length - 1) { right.setAttribute("aria-disabled", "true"); } else { right.removeAttribute("aria-disabled"); }
    }
    var cls = $("kindler-class");
    if (cls && cls.value !== tab.cls) { cls.value = CLASSES.indexOf(tab.cls) >= 0 ? tab.cls : ""; }
    var league = $("kindler-league");
    if (league && s.doc.activeElement !== league && league.value !== tab.league) { league.value = tab.league; }
    TOGGLES.forEach(function (t) {
      var v = tab.toggles[t[0]];
      t[2].forEach(function (c) {
        var input = $("kt-" + t[0] + "-" + c[0]);
        if (input) { input.checked = (v || "unsure") === c[0]; }
      });
    });
    var res = resultText(tab, s.reads[tab.id] || null);
    var line = $("kindler-result");
    if (line && line.textContent !== res.text) { line.textContent = res.text; }
    var stale = $("kindler-stale");
    if (stale) { stale.hidden = !res.stale; }
    var staleWhy = $("kindler-stale-why");
    if (staleWhy) {
      staleWhy.hidden = !res.stale;
      if (staleWhy.textContent !== WORDS.stale) { staleWhy.textContent = WORDS.stale; }
    }
    setMode(s, s.mode);
  }

  /* tools (Move, Rename, Close), rename (the name field) or confirm
     (Close <label>? Close / Keep). */
  function setMode(s, mode) {
    s.mode = mode;
    var tools = s.$("kindler-tools"), form = s.$("kindler-rename-form"), ask = s.$("kindler-confirm");
    if (tools) { tools.hidden = mode !== "tools"; }
    if (form) { form.hidden = mode !== "rename"; }
    if (ask) { ask.hidden = mode !== "confirm"; }
  }

  function focus(s, id) {
    var n = typeof id === "string" ? s.$(id) : id;
    if (n && typeof n.focus === "function") { n.focus(); }
  }

  function setModel(s, body) {
    s.model = view(body);
    if (!current(s)) { s.sub = PASTED; }
    paintBar(s);
  }

  /* One store change, in click order. Resolves true when it was kept. */
  function change(s, body) {
    var run = function () {
      return s.ctl.request("POST", PATH, body).then(function (r) {
        if (r.status === 200 && r.body) {
          setModel(s, r.body);
          if (r.body.saved === false) { setStatus(s, WORDS.notSaved); }
          return true;
        }
        var text = r.body && typeof r.body.error === "string" ? r.body.error : WORDS.notSaved;
        setStatus(s, text);
        if (s.ctl.say) { s.ctl.say(text); }
        paintBar(s); // put the controls back as the store has them
        return false;
      }, function () {
        setStatus(s, WORDS.noReach);
        paintBar(s);
        return false;
      });
    };
    s.chain = s.chain.then(run, run);
    return s.chain;
  }

  function load(s) {
    return s.ctl.request("GET", PATH).then(function (r) {
      if (r.status !== 200 || !r.body) { return; }
      s.model = view(r.body);
      if (s.want === "kindler" && current(s)) { s.sub = "kindler"; }
      s.want = "";
      paintBar(s);
      var tab = current(s);
      if (tab && s.sub !== PASTED) { readResult(s, tab.id); }
    }, function () { /* the page says the core is down elsewhere */ });
  }

  /* The tab's last result (in the engine's memory), never a calc. */
  function readResult(s, id) {
    var tab = null;
    s.model.tabs.forEach(function (t) { if (t.id === id) { tab = t; } });
    if (!tab || !tab.result || s.reads[id]) { return Promise.resolve(); }
    return s.ctl.request("POST", GEN, { id: id, op: "read" }).then(function (r) {
      if (r.status === 200 && r.body) {
        s.reads[id] = r.body;
        if (current(s) && current(s).id === id && s.sub !== PASTED) { paintCard(s, current(s)); }
      }
    }, function () { /* the store's summary stays */ });
  }

  /* Show a sub-tab: PASTED or a Kindler tab id. The shown Kindler tab is
     the store's (it survives a reload); focus only on a keyboard move. */
  function show(s, id, how) {
    if (id === PASTED) {
      s.sub = PASTED;
      saveSub(s);
      paintBar(s);
      if (how === "key") { focus(s, "kindler-pasted"); }
      return Promise.resolve();
    }
    s.sub = "kindler";
    saveSub(s);
    var was = s.model.shown;
    s.model.shown = id;
    setMode(s, "tools");
    paintBar(s);
    if (how === "key") { focus(s, s.buttons[id]); }
    readResult(s, id);
    return was === id ? Promise.resolve(true) : change(s, { op: "show", id: id });
  }

  function addTab(s) {
    var note = s.$("kindler-full");
    if (s.model.full) {
      if (note) { note.textContent = s.model.fullText; note.hidden = false; }
      if (s.ctl.say) { s.ctl.say(s.model.fullText); }
      return Promise.resolve(false);
    }
    return change(s, { op: "add" }).then(function (ok) {
      if (!ok) {
        if (s.model.full && note) { note.textContent = s.model.fullText; note.hidden = false; }
        return false;
      }
      s.sub = "kindler";
      saveSub(s);
      setMode(s, "tools");
      paintBar(s);
      focus(s, "kindler-title");
      return true;
    });
  }

  function move(s, dir, btn) {
    var tab = current(s);
    if (!tab || (btn && btn.getAttribute("aria-disabled") === "true")) { return Promise.resolve(false); }
    return change(s, { op: "move", id: tab.id, dir: dir });
  }

  function openRename(s) {
    var tab = current(s);
    if (!tab) { return; }
    var input = s.$("kindler-name");
    if (input) {
      input.value = tab.custom ? tab.label : "";
      input.setAttribute("placeholder", tab.custom ? "" : tab.label);
    }
    setMode(s, "rename");
    focus(s, input);
  }

  function closeRename(s) {
    setMode(s, "tools");
    focus(s, "kindler-rename");
  }

  function saveRename(s) {
    var tab = current(s);
    var input = s.$("kindler-name");
    if (!tab || !input) { return Promise.resolve(false); }
    var label = cleanLabel(input.value);
    return change(s, { op: "rename", id: tab.id, label: label }).then(function (ok) {
      if (ok) { closeRename(s); }
      return ok;
    });
  }

  function openConfirm(s) {
    var tab = current(s);
    if (!tab) { return; }
    var q = s.$("kindler-confirm-q");
    if (q) { q.textContent = "Close " + tab.label + "?"; }
    setMode(s, "confirm");
    focus(s, "kindler-keep");
  }

  function keep(s) {
    setMode(s, "tools");
    focus(s, "kindler-close");
  }

  function closeTab(s) {
    var tab = current(s);
    if (!tab) { return Promise.resolve(false); }
    delete s.reads[tab.id];
    return change(s, { op: "close", id: tab.id }).then(function (ok) {
      setMode(s, "tools");
      if (!ok) { return false; }
      if (current(s)) {
        s.sub = "kindler";
        paintBar(s);
        focus(s, s.buttons[s.model.shown]);
      } else {
        s.sub = PASTED;
        saveSub(s);
        paintBar(s);
        focus(s, "kindler-pasted");
      }
      return true;
    });
  }

  function setField(s, fields) {
    var tab = current(s);
    if (!tab) { return Promise.resolve(false); }
    var body = { op: "set", id: tab.id };
    Object.keys(fields).forEach(function (k) { body[k] = fields[k]; });
    return change(s, body);
  }

  function stopPoll(s) {
    s.poll = null;
  }

  function finish(s, id, body) {
    s.reads[id] = body;
    stopPoll(s);
    return s.ctl.request("GET", PATH).then(function (r) {
      if (r.status === 200 && r.body) { setModel(s, r.body); }
      setStatus(s, "");
      /* a short fixed sentence, and only while the Build tab shows (the
         full text stays on the card; nothing is said over Play) */
      var tab = current(s);
      var panel = s.$("panel-build");
      if (tab && tab.id === id && s.ctl.say && panel && !panel.hidden) {
        s.ctl.say(tab.label + ": result ready.");
      }
    }, function () { setStatus(s, WORDS.noReach); });
  }

  /* Re-read one run's state every POLL_MS, at most POLL_MAX times. */
  function pollRun(s, id, left) {
    var token = {};
    s.poll = token;
    var go = function () {
      if (s.poll !== token) { return; }
      s.ctl.request("POST", GEN, { id: id, op: "read" }).then(function (r) {
        if (s.poll !== token) { return; }
        var st = r.body && r.body.state;
        if (r.status === 200 && st === "running" && left > 1) {
          left -= 1;
          s.ctl.later(go, POLL_MS);
          return;
        }
        if (r.status === 200 && st === "running") {
          stopPoll(s);
          setStatus(s, WORDS.slow);
          return;
        }
        if (r.status === 200 && (st === "done" || st === "none")) { finish(s, id, r.body); return; }
        stopPoll(s);
        setStatus(s, r.body && typeof r.body.error === "string" ? r.body.error : WORDS.notSaved);
      }, function () {
        stopPoll(s);
        setStatus(s, WORDS.noReach);
      });
    };
    s.ctl.later(go, POLL_MS);
  }

  /* The Generate click: the only thing that starts a run (point 4). */
  function generate(s) {
    var tab = current(s);
    if (!tab) { return Promise.resolve(null); }
    var id = tab.id;
    return s.chain.then(function () {
      setStatus(s, WORDS.working);
      return s.ctl.request("POST", GEN, { id: id });
    }).then(function (r) {
      var st = r.body && r.body.state;
      if (r.status !== 200) {
        setStatus(s, r.body && typeof r.body.error === "string" ? r.body.error : WORDS.notSaved);
        return st || null;
      }
      if (st === "done") { finish(s, id, r.body); return st; }
      if (st === "started") { pollRun(s, id, POLL_MAX); return st; }
      if (st === "running") {
        var mine = s.poll !== null;
        setStatus(s, mine ? WORDS.working : WORDS.busy);
        return st;
      }
      setStatus(s, WORDS.notSaved);
      return st || null;
    }, function () {
      setStatus(s, WORDS.noReach);
      return null;
    });
  }

  function on(n, type, fn) { if (n) { n.addEventListener(type, fn); } }

  function wire(s) {
    var $ = s.$;
    on($("kindler-bar"), "click", function (e) {
      var b = e.target && e.target.closest ? e.target.closest("button") : e.target;
      if (!b) { return; }
      if (b.getAttribute("id") === "kindler-pasted") { show(s, PASTED, "click"); return; }
      if (b.getAttribute("id") === "kindler-new") { addTab(s); return; }
      var id = b.getAttribute("data-id");
      if (id) { show(s, id, "click"); }
    });
    on($("kindler-bar"), "keydown", function (e) {
      var b = e.target;
      if (!b || b.getAttribute("id") === "kindler-new") { return; }
      var here = b.getAttribute("id") === "kindler-pasted" ? PASTED : b.getAttribute("data-id");
      if (!here) { return; }
      var next = step(e.key, rowIds(s), here);
      if (next === null) { return; }
      if (e.preventDefault) { e.preventDefault(); }
      show(s, next, "key");
    });
    on($("kindler-left"), "click", function (e) { move(s, "left", e.currentTarget || $("kindler-left")); });
    on($("kindler-right"), "click", function (e) { move(s, "right", e.currentTarget || $("kindler-right")); });
    on($("kindler-rename"), "click", function () { openRename(s); });
    on($("kindler-rename-form"), "submit", function (e) {
      if (e.preventDefault) { e.preventDefault(); }
      saveRename(s);
    });
    on($("kindler-name-cancel"), "click", function () { closeRename(s); });
    on($("kindler-name"), "keydown", function (e) {
      if (e.key === "Escape") { if (e.preventDefault) { e.preventDefault(); } closeRename(s); }
    });
    on($("kindler-close"), "click", function () { openConfirm(s); });
    on($("kindler-keep"), "click", function () { keep(s); });
    on($("kindler-yes"), "click", function () { closeTab(s); });
    on($("kindler-confirm"), "keydown", function (e) {
      if (e.key === "Escape") { if (e.preventDefault) { e.preventDefault(); } keep(s); }
    });
    on($("kindler-class"), "change", function () { setField(s, { "class": $("kindler-class").value }); });
    on($("kindler-league"), "change", function () {
      setField(s, { league: $("kindler-league").value.replace(/[\x00-\x1f\x7f]/g, "").trim().slice(0, 64) });
    });
    on($("kindler-toggles"), "change", function (e) {
      var t = e.target;
      var key = t && t.getAttribute ? t.getAttribute("data-toggle") : null;
      if (!key || !t.checked) { return; }
      var tg = {};
      tg[key] = t.value;
      setField(s, { toggles: tg });
    });
    on($("kindler-form"), "submit", function (e) {
      if (e.preventDefault) { e.preventDefault(); }
      generate(s);
    });
  }

  /* The league suggestions, painted when the web data answer changes. */
  function paintLeagues() {
    var s = S;
    if (!s) { return; }
    var list = s.$("kindler-leagues");
    if (!list) { return; }
    var names = leagueNames(s.ctl.leagues ? s.ctl.leagues() : null);
    var key = names.join("\n");
    if (key === s.leagueKey) { return; }
    s.leagueKey = key;
    while (list.firstChild) { list.removeChild(list.firstChild); }
    names.forEach(function (n) {
      var o = el(s.doc, "option");
      o.value = n;
      list.appendChild(o);
    });
  }

  return {
    NAME: NAME, ORDER: ORDER, PASTED: PASTED, MAX_LABEL: MAX_LABEL, POLL_MS: POLL_MS,
    POLL_MAX: POLL_MAX, CLASSES: CLASSES.slice(), TOGGLES: TOGGLES, WORDS: WORDS,
    cleanLabel: cleanLabel, view: view, step: step, resultText: resultText,
    leagueNames: leagueNames, fetcher: fetcher, attach: attach, paintLeagues: paintLeagues,
    show: function (id, how) { return show(S, id, how); },
    addTab: function () { return addTab(S); },
    move: function (dir) { return move(S, dir, S.$(dir === "left" ? "kindler-left" : "kindler-right")); },
    openRename: function () { openRename(S); },
    saveRename: function () { return saveRename(S); },
    openConfirm: function () { openConfirm(S); },
    keep: function () { keep(S); },
    closeTab: function () { return closeTab(S); },
    setField: function (f) { return setField(S, f); },
    generate: function () { return generate(S); },
    state: function () { return S; }
  };
}));
