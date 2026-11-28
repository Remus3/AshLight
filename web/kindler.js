/* AshLight dashboard: the Build sub-tabs (KINDLER-UI-TABS, decision 0081
   points 7 to 11). The Build and items tab holds the fixed Pasted build
   sub-tab (today's card grid) and up to 6 Kindler sub-tabs, each a Kindler
   editor: Move left / Move right, Rename (at most 32 characters), Close
   with an inline confirm (Close / Keep, focus on Keep; never
   window.confirm), a class and league picker, the tri-state toggles and
   Generate. The editor card is built here the first time a Kindler
   sub-tab shows (buildCard), so the page carries no unused markup.

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

   The plan card (KINDLER-UI-RESULT, decision 0081 points 10 and 14 to
   17) is made after the editor card the first time a shown Kindler tab
   has a result. It reads POST /api/kindler-generate "op": "plan" (never a
   Generate) and shows the top template's stages, one at a time with
   Previous stage / Next stage: skills with their support links, gem
   changes with the level (the gems snapshot's, else AshLight's planned
   one), the passives in order with the point count, the Ascendancy points
   as "after your Nth Ascendancy trial" and the per-slot item focus, as
   three card pages (Skills and gems, Passives, Item focus) in a labelled
   button group like the sub-tabs. Gem names and focus stats are buttons
   of the shared item info popover (web/iteminfo.js). No weight or score
   number is shown, so nothing has a number with the calc off. The per-tab
   "Follow Play guidance" toggle (aria-pressed, on by default, the store's
   follow flag) lets the core pick the stage from the zone, act and level
   the snapshot already publishes: the snapshot paint re-reads the plan
   when those change, the shown stage moves to it by itself and carries a
   "Now" badge with why ("This stage matches your act."); it never says a
   step was done. While Path of Building ranks the item focus ("pending")
   the plan is re-read on the page's timer, at most PLAN_MAX times.

   ACTIVE-BUILD-PICK (decision 0096): a "Use this plan for Play" chip on the plan
   card (pressed while that tab's plan is the build in use; a second click
   goes back to the pasted build) and one on the Pasted build's Build card
   (#build-use, shown only while there is a choice) post the player's click
   to POST /api/build-source; their state is the snapshot's build_source.

   UMD: CommonJS for node (tests/test_kindler_tabs_ui.py,
   tests/test_kindler_result_ui.py), window.ALKindler
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
        paint: function (snap) { api.paintLeagues(); api.follow(snap); api.useSource(snap); },
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

  /* ACTIVE-BUILD-PICK (decision 0096): the build Play uses, per
     character: the pasted build or one Kindler tab's plan. The snapshot's
     build_source says which; a "Use ... for Play" chip (aria-pressed) on the
     plan card and one on the Pasted build's Build card post the player's
     click to POST /api/build-source. */
  var SOURCE_PATH = "/api/build-source";
  var USE_WORDS = {
    use: "Use this plan for Play",
    pasted: "Use pasted build for Play",
    notSaved: "Not saved. Try again."
  };

  /* KINDLER-UI-RESULT (decision 0081 points 10 and 14 to 17): the plan
     card. Plan parts are pages of the card (design A: a card pages, never
     scrolls); no weight or other number from Path of Building is shown,
     only its order, and nothing with the calc off. */
  var PLAN_PAGES = [["skills", "Skills and gems"], ["passives", "Passives"],
                    ["items", "Item focus"]];
  var PLAN_MAX = 20; // plan re-reads while Path of Building ranks the focus
  var ORDINALS = ["first", "second", "third", "fourth", "fifth", "sixth",
                  "seventh", "eighth"];
  var FOCUS_WORDS = {
    pob: "Stats ranked by Path of Building for this build.",
    pending: "AshLight's own order for now. Path of Building is ranking these stats.",
    calc_off: "AshLight's own order (calc off). Turn the calc on in Settings, Checks.",
    failed: "AshLight's own order. Path of Building could not rank these stats.",
    no_base: "AshLight's own order. The item data is still loading.",
    no_tree: "AshLight's own order. The passive tree data is still loading."
  };
  var BY_WORDS = { zone: "your zone", act: "your act", area_level: "your area level",
                   level: "your level", nearest_level: "your level" };
  var PLAN_WORDS = {
    reading: "Reading the plan.",
    none: "No plan for this result. Press Generate to make a new one.",
    followOn: "Shows the stage that matches where you are.",
    followOff: "Pick a stage with Previous stage and Next stage.",
    follow: "Follow Play guidance",
    now: "Now",
    noSkills: "No skills planned for this stage.",
    noGems: "No gem changes at this stage.",
    noPassives: "No passives added at this stage.",
    noFocus: "No item focus for this stage.",
    noApply: "not used by this skill",
    applyCredit: "Path of Building says which links a skill uses.",
    failed: "Can't read the plan right now. AshLight tries again when something changes."
  };
  var PART_ROWS = 10; // rows a card part holds (design A card, 22 to 24 px rows)

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
               follow: t.follow !== false,
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

  /* -- the plan card: pure helpers (KINDLER-UI-RESULT) ---------------- */

  function str(v) { return typeof v === "string" ? v : ""; }
  function int(v) { return typeof v === "number" && isFinite(v) && Math.floor(v) === v ? v : null; }
  function arr(v) { return Array.isArray(v) ? v : []; }
  function obj(v) { return v && typeof v === "object" && !Array.isArray(v) ? v : null; }

  /* 2 -> "second" (an Ascendancy trial), "" outside the known words. */
  function ordinal(n) {
    return int(n) !== null && n >= 1 && n <= ORDINALS.length ? ORDINALS[n - 1] : "";
  }

  function gemOf(g) {
    g = obj(g) || {};
    return { name: str(g.name), level: int(g.level), checked: g.checked === true };
  }

  function nodeOf(n) {
    n = obj(n) || {};
    var id = int(n.id);
    var name = str(n.name);
    return name ? name : (id !== null ? "Unnamed passive" : "");
  }

  function named(g) { return !!g.name; }

  /* POST /api/kindler-generate "op": "plan" -> the card's model, every
     field checked; a field the answer lacks stays empty, never guessed.
     The per-mod weights are left out on purpose (no number shown). */
  function planView(answer) {
    var plan = obj(answer && answer.plan);
    var stages = arr(plan && plan.stages).filter(obj).map(function (st) {
      var asc = obj(st.ascendancy);
      return {
        id: str(st.id), label: str(st.label) || "Stage", trigger: obj(st.trigger) || {},
        level: int(st.level),
        skills: arr(st.skills).map(function (sk) {
          var g = gemOf(sk);
          g.supports = arr(sk && sk.supports).map(function (x) {
            var y = gemOf(x);
            y.applies = x && typeof x.applies === "boolean" ? x.applies : null;
            return y;
          }).filter(named);
          return g;
        }).filter(named),
        gems: arr(st.gems).map(function (g) {
          var x = gemOf(g);
          x.action = g && ["pick", "swap", "drop"].indexOf(g.action) >= 0 ? g.action : "";
          x.forName = str(g && g["for"]);
          return x;
        }).filter(function (g) { return g.name && g.action; }),
        passives: arr(st.passives).map(nodeOf).filter(Boolean),
        points: int(st.points), budget: int(st.budget),
        ascendancy: asc ? { trial: int(asc.trial), nodes: arr(asc.nodes).map(nodeOf).filter(Boolean) } : null,
        focus: arr(st.focus).filter(obj).map(function (f) {
          return { slot: str(f.slot), stats: arr(f.stats).map(function (x) {
            return str(obj(x) ? x.stat : x);
          }).filter(Boolean) };
        }).filter(function (f) { return f.slot && f.stats.length; })
      };
    });
    var cur = obj(answer && answer.current);
    var at = cur ? int(cur.stage) : null;
    if (at === null || at < 0 || at >= stages.length) { cur = null; }
    var focus = str(answer && answer.focus) || str(plan && plan.focus_note) || str(plan && plan.focus);
    return { plan: stages.length > 0, label: str(plan && plan.label),
             ascendancy: str(plan && plan.ascendancy),
             focus: Object.prototype.hasOwnProperty.call(FOCUS_WORDS, focus) ? focus : "",
             stages: stages, current: cur ? { stage: at, by: str(cur.by) } : null };
  }

  /* A stage trigger in words ("" for a zone: the stage label names it). */
  function triggerText(t) {
    t = obj(t) || {};
    if ((t.kind === "level" || t.kind === "area_level") && int(t.min) !== null && int(t.max) !== null) {
      return (t.kind === "level" ? "For character level " : "For area level ") + t.min + " to " + t.max;
    }
    if (t.kind === "act" && int(t.act) !== null) { return "For Act " + t.act; }
    return "";
  }

  /* One gem step as parts: {text} and {item} (a gem name, a popover
     button on the page). The level is the gems snapshot's when checked,
     else AshLight's planned level (decision 0081 point 16). */
  function gemStep(g) {
    var lvl = g.level === null ? "" : (g.checked ? ", usable from level " : ", planned for level ") + g.level;
    if (g.action === "swap" && g.forName) {
      return [{ text: "Swap " }, { item: g.forName }, { text: " for " }, { item: g.name }, { text: lvl }];
    }
    if (g.action === "drop") { return [{ text: "Drop " }, { item: g.name }]; }
    return [{ text: "Pick up " }, { item: g.name }, { text: lvl }];
  }

  /* The three values the follow resolver reads from a snapshot, or null. */
  function hereOf(snap) {
    if (!obj(snap)) { return null; }
    return { area_id: str(snap.area_id), area_level: int(snap.area_level), level: int(snap.level) };
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
      mode: "tools", here: null, plans: {}, planKeys: {}, planSeq: 0, planLeft: 0,
      stageAt: {}, page: PLAN_PAGES[0][0], bodyKey: "", part: 0, parts: 1, partAt: "",
      useSrc: null
    };
    S = s;
    try {
      var stored = ctl.store ? ctl.store.getItem(STORE_KEY) : null;
      if (stored === "kindler") { s.want = "kindler"; }
    } catch (e) { /* private window */ }
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

  /* h(doc, tag, attrs, kids): one element; attrs are attributes (class,
     id, type ...), kids strings (textContent) or elements. */
  function h(doc, tag, attrs, kids) {
    var n = doc.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "hidden") { n.hidden = !!attrs[k]; } else if (k === "class") { n.className = attrs[k]; } else { n.setAttribute(k, attrs[k]); }
    });
    if (typeof kids === "string") { n.textContent = kids; } else {
      (kids || []).forEach(function (c) { n.appendChild(c); });
    }
    return n;
  }

  /* KINDLER-UI-TABS fix round (dashboard element cap, test_dash_perf): the
     editor card is made here the first time a Kindler sub-tab shows, after
     the six card cells of #panel-build; the page holds only the sub-tab
     bar until then. Text through textContent only, no markup strings. */
  function buildCard(s) {
    var d = s.doc;
    var panel = s.$("panel-build");
    if (s.$("kindlerbox") || !panel) { return s.$("kindlerbox"); }
    var b24 = function (id, text, more) {
      var a = { id: id, type: "button", "class": "secondary btn-24" };
      Object.keys(more || {}).forEach(function (k) { a[k] = more[k]; });
      return h(d, "button", a, text);
    };
    var card = h(d, "section", { id: "kindlerbox", "class": "card kindler-card",
      "aria-labelledby": "kindler-title", hidden: true }, [
      h(d, "div", { "class": "kindler-head" }, [
        h(d, "h2", { id: "kindler-title", "class": "one-line", tabindex: "-1" }, "Kindler"),
        h(d, "span", { "class": "row-meta muted" }, "Kindler: build generator")]),
      h(d, "div", { id: "kindler-tools", "class": "kindler-row" }, [
        b24("kindler-left", "Move left"), b24("kindler-right", "Move right"),
        b24("kindler-rename", "Rename"), b24("kindler-close", "Close tab")]),
      h(d, "form", { id: "kindler-rename-form", "class": "kindler-row", hidden: true }, [
        h(d, "label", { "for": "kindler-name", "class": "row-meta" }, "Name"),
        h(d, "input", { id: "kindler-name", type: "text", maxlength: String(MAX_LABEL),
          autocomplete: "off", spellcheck: "false", "aria-describedby": "kindler-name-hint" }),
        h(d, "button", { type: "submit", "class": "secondary btn-24" }, "Save name"),
        b24("kindler-name-cancel", "Cancel"),
        h(d, "span", { id: "kindler-name-hint", "class": "row-meta muted" },
          "Up to 32 characters. Empty keeps the usual name.")]),
      h(d, "div", { id: "kindler-confirm", "class": "kindler-row", hidden: true }, [
        h(d, "p", { id: "kindler-confirm-q", "class": "row-body one-line" }),
        b24("kindler-yes", "Close", { "aria-describedby": "kindler-confirm-q" }),
        b24("kindler-keep", "Keep")]),
      h(d, "form", { id: "kindler-form", "class": "kindler-form" }, [
        h(d, "div", { "class": "kindler-row" }, [
          h(d, "label", { "for": "kindler-class", "class": "row-meta" }, "Class"),
          h(d, "select", { id: "kindler-class" }),
          h(d, "label", { "for": "kindler-league", "class": "row-meta" }, "League"),
          h(d, "input", { id: "kindler-league", type: "text", list: "kindler-leagues",
            maxlength: "64", placeholder: "Standard", autocomplete: "off", spellcheck: "false" }),
          h(d, "datalist", { id: "kindler-leagues" })]),
        h(d, "p", { "class": "row-meta muted" },
          "Not sure sets no limit. The league changes only prices and trade links."),
        h(d, "div", { id: "kindler-toggles", "class": "kindler-toggles" }),
        h(d, "div", { "class": "kindler-row" }, [
          h(d, "button", { id: "kindler-generate", type: "submit", "class": "secondary btn-28" },
            "Generate"),
          h(d, "span", { id: "kindler-status", "class": "row-meta muted" })])]),
      h(d, "p", { "class": "kindler-result row-body" }, [
        h(d, "span", { id: "kindler-stale", "class": "badge", hidden: true }, "Out of date"),
        h(d, "span", { id: "kindler-result" })]),
      h(d, "p", { id: "kindler-stale-why", "class": "row-meta muted", hidden: true })]);
    panel.appendChild(card);
    buildToggles(s);
    buildClasses(s);
    wireCard(s);
    s.leagueKey = "";
    paintLeagues();
    return card;
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
    var tab = s.sub === PASTED ? null : current(s);
    var card = tab ? buildCard(s) : s.$("kindlerbox");
    if (panel) {
      if (tab) { panel.setAttribute("data-sub", "kindler"); } else { panel.removeAttribute("data-sub"); }
    }
    if (card) { card.hidden = !tab; }
    var withPlan = !!(tab && tab.result);
    var plan = withPlan ? buildPlanCard(s) : s.$("kindler-plan");
    if (plan) { plan.hidden = !withPlan; }
    if (tab) { paintCard(s, tab); }
    if (withPlan) { paintPlan(s, tab); syncPlan(s, false); }
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
    delete s.plans[tab.id];
    delete s.planKeys[tab.id];
    delete s.stageAt[tab.id];
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

  /* -- the plan card (KINDLER-UI-RESULT) ------------------------------ */

  function itemInfo() {
    if (root && root.ALItemInfo) { return root.ALItemInfo; }
    if (typeof module === "object" && module.exports && typeof require === "function") {
      try { return require("./iteminfo.js"); } catch (e) { return null; }
    }
    return null;
  }

  function setText(n, text) { if (n && n.textContent !== text) { n.textContent = text; } }

  function shownTab(s) { return s.sub === PASTED ? null : current(s); }

  /* Made after the editor card the first time a shown Kindler tab has a
     result (dashboard element cap), like buildCard. */
  function buildPlanCard(s) {
    var d = s.doc;
    var panel = s.$("panel-build");
    if (s.$("kindler-plan") || !panel) { return s.$("kindler-plan"); }
    var b24 = function (id, text) {
      return h(d, "button", { id: id, type: "button", "class": "secondary btn-24" }, text);
    };
    var pages = PLAN_PAGES.map(function (p) {
      return h(d, "button", { id: "kindler-page-" + p[0], type: "button", "class": "subtab",
        "data-page": p[0], "data-label": p[1] }, p[1]);
    });
    var card = h(d, "section", { id: "kindler-plan", "class": "card kindler-card kindler-plan",
      "aria-labelledby": "kindler-plan-title", hidden: true }, [
      h(d, "div", { "class": "kindler-head" }, [
        h(d, "h2", { id: "kindler-plan-title", "class": "one-line" }, "Plan"),
        h(d, "span", { id: "kindler-plan-name", "class": "row-meta muted one-line" }),
        h(d, "button", { id: "kindler-use", type: "button", "class": "chip",
          "aria-pressed": "false", "data-label": USE_WORDS.use }, USE_WORDS.use)]),
      h(d, "div", { "class": "kindler-row" }, [
        h(d, "button", { id: "kindler-follow", type: "button", "class": "chip",
          "aria-pressed": "true", "data-label": PLAN_WORDS.follow,
          "aria-describedby": "kindler-follow-why" }, PLAN_WORDS.follow),
        h(d, "span", { id: "kindler-follow-why", "class": "row-meta muted" })]),
      h(d, "p", { id: "kindler-plan-empty", "class": "row-body" }),
      h(d, "div", { id: "kindler-plan-main", "class": "kindler-plan-main", hidden: true }, [
        h(d, "div", { "class": "kindler-row kindler-stage-nav" }, [
          b24("kindler-stage-prev", "Previous stage"),
          h(d, "h3", { id: "kindler-stage-name", "class": "card-h3 one-line" }),
          b24("kindler-stage-next", "Next stage")]),
        h(d, "p", { "class": "row-meta kindler-stage-why" }, [
          h(d, "span", { id: "kindler-here", "class": "badge", hidden: true }, PLAN_WORDS.now),
          h(d, "span", { id: "kindler-stage-why", "class": "muted" })]),
        h(d, "div", { id: "kindler-plan-pages", "class": "kindler-row kindler-pages",
          role: "group", "aria-label": "Plan parts" }, pages),
        h(d, "div", { id: "kindler-plan-body", "class": "kindler-plan-body" }),
        h(d, "div", { id: "kindler-parts", "class": "kindler-row kindler-parts", hidden: true }, [
          b24("kindler-part-prev", "Previous part"),
          h(d, "span", { id: "kindler-part-label", "class": "row-meta" }),
          b24("kindler-part-next", "Next part")]),
        h(d, "p", { id: "kindler-plan-credit", "class": "row-meta muted", hidden: true })])]);
    panel.appendChild(card);
    wirePlan(s);
    var info = itemInfo();
    if (info && typeof info.attach === "function") { info.attach(card, {}); }
    return card;
  }

  function wirePlan(s) {
    var $ = s.$;
    on($("kindler-follow"), "click", function () { setFollow(s); });
    on($("kindler-use"), "click", function () { useForPlay(s, "kindler"); });
    on($("kindler-stage-prev"), "click", function () { moveStage(s, -1); });
    on($("kindler-stage-next"), "click", function () { moveStage(s, 1); });
    on($("kindler-part-prev"), "click", function () { movePart(s, -1); });
    on($("kindler-part-next"), "click", function () { movePart(s, 1); });
    on($("kindler-plan-pages"), "click", function (e) {
      var b = e.target && e.target.closest ? e.target.closest("button") : e.target;
      if (b && b.getAttribute("data-page")) { showPage(s, b.getAttribute("data-page"), false); }
    });
    on($("kindler-plan-pages"), "keydown", function (e) {
      var here = e.target && e.target.getAttribute ? e.target.getAttribute("data-page") : null;
      var next = here ? step(e.key, PLAN_PAGES.map(function (p) { return p[0]; }), here) : null;
      if (next === null) { return; }
      if (e.preventDefault) { e.preventDefault(); }
      showPage(s, next, true);
    });
  }

  /* An item or gem name: the shared popover's button (decision 0082 part
     1), plain text when the popover script is not there. No gem level is
     sent: the plan's gem levels are character levels, so the popover
     shows gem level 1 rather than a guess (GEM-LEVEL-WIRE). */
  function itemNode(s, name) {
    var info = itemInfo();
    return info && typeof info.button === "function" ? info.button(s.doc, name) : el(s.doc, "span", "", name);
  }

  function addParts(s, node, parts) {
    parts.forEach(function (p) {
      if (p.item) { node.appendChild(itemNode(s, p.item)); } else if (p.text) {
        node.appendChild(el(s.doc, "span", "", p.text));
      }
    });
    return node;
  }

  /* names joined by ", ", each an item button */
  function itemList(names) {
    var parts = [];
    names.forEach(function (n, i) {
      if (i) { parts.push({ text: ", " }); }
      parts.push({ item: n });
    });
    return parts;
  }

  /* A page body is a list of rows ({head}, {para}, {li, list, cls, rows});
     parts() cuts it into card parts of at most PART_ROWS rows, so a page
     never grows or clips its card (design A); a heading never ends a part,
     and a list cut in two goes on numbered from where it stopped. */
  function head(text) { return { head: text, rows: 1 }; }
  function para(text, cls) { return { para: text, cls: cls || "row-body", rows: 1 }; }

  function parts(rows) {
    var out = [[]], used = 0;
    rows.forEach(function (r, i) {
      var last = out[out.length - 1];
      var need = r.rows + (r.head && rows[i + 1] ? rows[i + 1].rows : 0);
      if (last.length && used + need > PART_ROWS) { out.push([]); used = 0; last = out[out.length - 1]; }
      last.push(r);
      used += r.rows;
    });
    return out;
  }

  function paintRows(s, body, rows) {
    var list = null, kind = "", count = 0;
    rows.forEach(function (r) {
      if (r.li) {
        if (!list || kind !== r.list + r.cls) {
          list = el(s.doc, r.list, r.cls);
          if (r.list === "ol" && r.n > 1) { list.setAttribute("start", String(r.n)); }
          body.appendChild(list);
          kind = r.list + r.cls;
        }
        list.appendChild(r.li);
        count += 1;
        return;
      }
      list = null;
      kind = "";
      body.appendChild(r.head ? el(s.doc, "h4", "card-h3", r.head) : el(s.doc, "p", r.cls, r.para));
    });
    return count;
  }

  function bodySkills(s, st) {
    var rows = [head("Skills")];
    if (!st.skills.length) { rows.push(para(PLAN_WORDS.noSkills, "row-meta muted")); }
    st.skills.forEach(function (sk) {
      var li = addParts(s, el(s.doc, "li"), [{ item: sk.name }]);
      if (sk.supports.length) {
        var bits = [{ text: " Links: " }];
        sk.supports.forEach(function (x, i) {
          if (i) { bits.push({ text: ", " }); }
          bits.push({ item: x.name });
          if (x.applies === false) { bits.push({ text: " (" + PLAN_WORDS.noApply + ")" }); }
        });
        li.appendChild(addParts(s, el(s.doc, "span", "row-meta kindler-links"), bits));
      }
      rows.push({ li: li, list: "ul", cls: "kindler-list", rows: sk.supports.length > 2 ? 2 : 1 });
    });
    rows.push(head("Gem changes"));
    if (!st.gems.length) { rows.push(para(PLAN_WORDS.noGems, "row-meta muted")); }
    st.gems.forEach(function (g) {
      rows.push({ li: addParts(s, el(s.doc, "li"), gemStep(g)), list: "ul", cls: "kindler-list", rows: 1 });
    });
    return rows;
  }

  function nodeRows(s, names) {
    return names.map(function (n, i) {
      return { li: el(s.doc, "li", "", n), list: "ol", cls: "kindler-passives", n: i + 1, rows: 0.5 };
    });
  }

  function bodyPassives(s, st) {
    var n = st.passives.length;
    var line = n ? n + (n === 1 ? " passive" : " passives") + " to take, in this order." : PLAN_WORDS.noPassives;
    if (st.points !== null && st.budget !== null) {
      line += " " + st.points + " of " + st.budget + " points planned so far.";
    }
    var rows = [para(line)].concat(nodeRows(s, st.passives));
    if (st.ascendancy && st.ascendancy.nodes.length) {
      var nth = ordinal(st.ascendancy.trial);
      rows.push(head("Ascendancy"));
      rows.push(para(nth ? "After your " + nth + " Ascendancy trial:" : "After an Ascendancy trial:"));
      rows = rows.concat(nodeRows(s, st.ascendancy.nodes).map(function (r) {
        r.cls = "kindler-passives kindler-asc";
        return r;
      }));
    }
    return rows;
  }

  function bodyItems(s, st) {
    if (!st.focus.length) { return [para(PLAN_WORDS.noFocus, "row-meta muted")]; }
    return st.focus.map(function (f) {
      var li = el(s.doc, "li");
      li.appendChild(el(s.doc, "span", "kindler-slot", f.slot + ": "));
      return { li: addParts(s, li, itemList(f.stats)), list: "ul", cls: "kindler-list", rows: 1 };
    });
  }

  /* The shown stage: the one the Play guidance matches while follow is
     on (it moves by itself when that changes), else the player's pick. */
  function stageIndex(s, tab, pv) {
    var cur = tab.follow && pv.current ? pv.current.stage : null;
    var m = s.stageAt[tab.id];
    if (!m) {
      m = s.stageAt[tab.id] = { i: cur !== null ? cur : 0, cur: cur };
    } else if (m.cur !== cur) {
      m.cur = cur;
      if (cur !== null) { m.i = cur; }
    }
    m.i = Math.max(0, Math.min(m.i, pv.stages.length - 1));
    return m.i;
  }

  function ariaOff(n, off) {
    if (!n) { return; }
    if (off) { n.setAttribute("aria-disabled", "true"); } else { n.removeAttribute("aria-disabled"); }
  }

  function paintPlan(s, tab) {
    var $ = s.$;
    if (!$("kindler-plan") || !tab || !tab.result) { return; }
    var follow = $("kindler-follow");
    if (follow) { follow.setAttribute("aria-pressed", tab.follow ? "true" : "false"); }
    paintUse(s);
    setText($("kindler-follow-why"), tab.follow ? PLAN_WORDS.followOn : PLAN_WORDS.followOff);
    var pv = s.plans[tab.id];
    var ok = !!(pv && pv.plan);
    var main = $("kindler-plan-main"), empty = $("kindler-plan-empty");
    if (main) { main.hidden = !ok; }
    if (empty) {
      empty.hidden = ok;
      setText(empty, ok ? "" : (pv ? (pv.failed ? PLAN_WORDS.failed : PLAN_WORDS.none) : PLAN_WORDS.reading));
    }
    var nameLine = ok ? pv.label + (pv.ascendancy ? ", " + pv.ascendancy : "") : "";
    setText($("kindler-plan-name"), nameLine);
    if ($("kindler-plan-name")) { $("kindler-plan-name").setAttribute("title", nameLine); }
    if (!ok) { return; }
    var n = pv.stages.length;
    var i = stageIndex(s, tab, pv);
    var st = pv.stages[i];
    var stageLine = "Stage " + (i + 1) + " of " + n + ": " + st.label;
    setText($("kindler-stage-name"), stageLine);
    if ($("kindler-stage-name")) { $("kindler-stage-name").setAttribute("title", stageLine); }
    ariaOff($("kindler-stage-prev"), i <= 0);
    ariaOff($("kindler-stage-next"), i >= n - 1);
    var now = tab.follow && pv.current !== null && pv.current.stage === i;
    var badge = $("kindler-here");
    if (badge) { badge.hidden = !now; }
    var why = triggerText(st.trigger);
    why = why ? why + "." : "";
    if (now) {
      why = (why ? why + " " : "") + "This stage matches " + (BY_WORDS[pv.current.by] || "where you are") + ".";
    }
    setText($("kindler-stage-why"), why);
    PLAN_PAGES.forEach(function (p) {
      var b = $("kindler-page-" + p[0]);
      if (!b) { return; }
      if (p[0] === s.page) { b.setAttribute("aria-current", "true"); } else { b.removeAttribute("aria-current"); }
      b.setAttribute("tabindex", p[0] === s.page ? "0" : "-1");
    });
    var credit = $("kindler-plan-credit");
    var unused = st.skills.some(function (sk) {
      return sk.supports.some(function (x) { return x.applies === false; });
    });
    var said = s.page === "items" ? FOCUS_WORDS[pv.focus] || ""
      : s.page === "skills" && unused ? PLAN_WORDS.applyCredit : "";
    if (credit) { credit.hidden = !said; setText(credit, said); }
    var where = tab.id + "|" + i + "|" + s.page;
    if (s.partAt !== where) { s.partAt = where; s.part = 0; }
    var key = JSON.stringify([tab.id, i, s.page, s.part, st]);
    var body = $("kindler-plan-body");
    if (!body || key === s.bodyKey) { return; }
    s.bodyKey = key;
    while (body.firstChild) { body.removeChild(body.firstChild); }
    var cut = parts(s.page === "passives" ? bodyPassives(s, st)
      : s.page === "items" ? bodyItems(s, st) : bodySkills(s, st));
    s.parts = cut.length;
    s.part = Math.max(0, Math.min(s.part, cut.length - 1));
    paintRows(s, body, cut[s.part]);
    var nav = $("kindler-parts");
    if (nav) { nav.hidden = cut.length < 2; }
    setText($("kindler-part-label"), cut.length < 2 ? "" : "Part " + (s.part + 1) + " of " + cut.length);
    ariaOff($("kindler-part-prev"), s.part <= 0);
    ariaOff($("kindler-part-next"), s.part >= cut.length - 1);
    var info = itemInfo();
    if (info && typeof info.sync === "function") { info.sync(); }
  }

  /* Read the shown tab's plan (never a Generate) when its result, its
     follow flag or the Play guidance it follows changed. The page reads
     it once it holds a snapshot (the guidance); while Path of Building
     ranks the item focus it re-reads on the page's timer, at most
     PLAN_MAX times. */
  function syncPlan(s, force) {
    var tab = shownTab(s);
    if (!tab || !tab.result || !s.here) { return; }
    var r = tab.result, w = s.here;
    var key = [tab.id, r.template, r.at, r.key, tab.follow, w.area_id, w.area_level, w.level].join("|");
    if (!force && s.planKeys[tab.id] === key) { return; }
    if (!force) { s.planLeft = PLAN_MAX; }
    s.planKeys[tab.id] = key;
    var id = tab.id;
    var seq = ++s.planSeq;
    s.ctl.request("POST", GEN, { id: id, op: "plan" }).then(function (res) {
      if (seq !== s.planSeq) { return; }
      if (!res || res.status !== 200 || !res.body) {
        s.plans[id] = { plan: false, failed: true };
        var t0 = shownTab(s);
        if (t0 && t0.id === id) { paintPlan(s, t0); }
        return;
      }
      s.plans[id] = planView(res.body);
      var t = shownTab(s);
      if (t && t.id === id) { paintPlan(s, t); }
      if (res.body.focus === "pending" && s.planLeft > 0) {
        s.planLeft -= 1;
        s.ctl.later(function () { if (s.planKeys[id] === key) { syncPlan(s, true); } }, POLL_MS);
      }
    }, function () {
      if (seq !== s.planSeq) { return; }
      if (s.planKeys[id] === key) { s.planKeys[id] = ""; } // tried again on the next change
      s.plans[id] = { plan: false, failed: true };
      var t1 = shownTab(s);
      if (t1 && t1.id === id) { paintPlan(s, t1); }
    });
  }

  /* ACTIVE-BUILD-PICK: the two chips from the snapshot's build_source. The
     plan chip is pressed while the shown tab's plan is in use, the Pasted
     build chip while the pasted build is; the Pasted build chip shows only
     when there is a choice (a Kindler plan in use or one to use). */
  function sourceOf(snap) {
    var v = obj(snap) ? obj(snap.build_source) : null;
    return v ? { use: v.use === "kindler" ? "kindler" : "pasted", tab: str(v.tab),
      offer: obj(v.offer) } : null;
  }

  function paintUse(s) {
    var src = s.useSrc;
    var $ = s.$;
    var tab = shownTab(s);
    var plan = $("kindler-use");
    if (plan) {
      var mine = !!(src && tab && src.use === "kindler" && src.tab === tab.id);
      plan.setAttribute("aria-pressed", mine ? "true" : "false");
      plan.hidden = !src;
    }
    var pasted = $("build-use");
    if (pasted) {
      pasted.setAttribute("aria-pressed", src && src.use === "pasted" ? "true" : "false");
      pasted.hidden = !(src && (src.use === "kindler" || src.offer));
    }
  }

  function useSource(s, snap) {
    var src = sourceOf(snap);
    if (!src) { return; }
    s.useSrc = src;
    paintUse(s);
  }

  /* One click: "kindler" uses the shown tab's plan (a second click on the
     pressed chip goes back to the pasted build); "pasted" uses the pasted
     build (nothing to do while it is already in use). */
  function useForPlay(s, which) {
    var src = s.useSrc;
    var body;
    if (which === "kindler") {
      var tab = shownTab(s);
      if (!tab) { return Promise.resolve(false); }
      body = src && src.use === "kindler" && src.tab === tab.id
        ? { use: "pasted" } : { use: "kindler", id: tab.id };
    } else {
      if (src && src.use === "pasted") { return Promise.resolve(false); }
      body = { use: "pasted" };
    }
    return s.ctl.request("POST", SOURCE_PATH, body).then(function (r) {
      if (r.status === 200 && r.body) {
        s.useSrc = sourceOf({ build_source: r.body });
        paintUse(s);
        if (r.body.saved === false && s.ctl.say) { s.ctl.say(USE_WORDS.notSaved); }
        return true;
      }
      var text = r.body && typeof r.body.error === "string" ? r.body.error : USE_WORDS.notSaved;
      if (s.ctl.say) { s.ctl.say(text); }
      return false;
    }, function () {
      if (s.ctl.say) { s.ctl.say(WORDS.noReach); }
      return false;
    });
  }

  /* The snapshot paint: the Play guidance the follow flag tracks. */
  function followPlay(s, snap) {
    var here = hereOf(snap);
    if (!here) { return; }
    s.here = here;
    syncPlan(s, false);
  }

  function setFollow(s) {
    var tab = shownTab(s);
    if (!tab) { return Promise.resolve(false); }
    return change(s, { op: "set", id: tab.id, follow: !tab.follow });
  }

  function moveStage(s, dir) {
    var tab = shownTab(s);
    var pv = tab ? s.plans[tab.id] : null;
    var m = tab ? s.stageAt[tab.id] : null;
    if (!pv || !pv.plan || !m) { return; }
    var i = m.i + dir;
    if (i < 0 || i >= pv.stages.length) { return; }
    m.i = i;
    paintPlan(s, tab);
  }

  function movePart(s, dir) {
    var tab = shownTab(s);
    var i = s.part + dir;
    if (!tab || i < 0 || i >= (s.parts || 1)) { return; }
    s.part = i;
    paintPlan(s, tab);
  }

  function showPage(s, id, key) {
    if (!PLAN_PAGES.some(function (p) { return p[0] === id; })) { return; }
    s.page = id;
    var tab = shownTab(s);
    if (tab) { paintPlan(s, tab); }
    if (key) { focus(s, "kindler-page-" + id); }
  }

  function wire(s) {
    var $ = s.$;
    on($("build-use"), "click", function () { useForPlay(s, "pasted"); });
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
  }

  /* The editor card's controls, wired once when buildCard makes them. */
  function wireCard(s) {
    var $ = s.$;
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
    PLAN_PAGES: PLAN_PAGES, FOCUS_WORDS: FOCUS_WORDS, PLAN_WORDS: PLAN_WORDS,
    planView: planView, triggerText: triggerText, gemStep: gemStep, ordinal: ordinal,
    hereOf: hereOf,
    follow: function (snap) { if (S) { followPlay(S, snap); } },
    useSource: function (snap) { if (S) { useSource(S, snap); } },
    useForPlay: function (which) { return useForPlay(S, which); },
    sourceOf: sourceOf, USE_WORDS: USE_WORDS,
    setFollow: function () { return setFollow(S); },
    stage: function (dir) { moveStage(S, dir); },
    part: function (dir) { movePart(S, dir); },
    PART_ROWS: PART_ROWS, parts: parts,
    planPage: function (id) { showPage(S, id, false); },
    state: function () { return S; }
  };
}));
