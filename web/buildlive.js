/* AshLight dashboard: the build-alert slot (BUILD-LIVE, decision 0045).
   UMD: CommonJS for node --test (app/test/buildlive.test.js),
   window.ALBuildLive for the page. The core keeps one build per character
   and swaps it by itself when the player's own Client.txt names another
   character; it sends `build_alert` (the saved build looks stale: missing,
   another class, or levels behind) and `upgrades` (items checked earlier
   with the item hotkey that beat the gear now, re-scored on every build or
   weight change). The words come from the core; this file only shows and
   hides them in #build-alert. No timers, no network, no clicks. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALBuildLive = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var MAX = 10;
  var TITLE = "Your build";
  var UPGRADES_TITLE = "Upgrades from items you checked";
  var lastAlert = ""; // the alert text last painted (a new one is Play news)

  function str(v) { return typeof v === "string" ? v : ""; }

  /* What the slot shows for a snapshot: {show, alert, upgrades}. The slot
     hides when the build fits and no checked item is an upgrade now. */
  function model(snap) {
    var a = snap && snap.build_alert;
    var alert = a && str(a.text) ? { kind: str(a.kind), text: a.text } : null;
    var up = snap && snap.upgrades;
    var items = [];
    ((up && up.items) || []).forEach(function (n) {
      if (n && str(n.head) && items.length < MAX) {
        items.push({ head: n.head, line: str(n.line), fit: str(n.fit), isNew: !!n["new"] });
      }
    });
    var upgrades = items.length ? { text: str(up.text), items: items } : null;
    return { show: !!(alert || upgrades), alert: alert, upgrades: upgrades };
  }

  function el(doc, tag, id, cls) {
    var e = doc.createElement(tag);
    if (id) { e.id = id; }
    if (cls) { e.className = cls; }
    return e;
  }

  /* Builds the slot's inner parts once, in one body node. The page gives
     only the slot: with the Play tab helper (window.ALTabs, the tabs
     work) the body goes in through ALTabs.fill(doc, "build-alert", node),
     else it is appended to the slot. */
  function parts(doc, box, tabs) {
    var p = doc.getElementById("build-alert-text");
    if (p) {
      return { text: p, upTitle: doc.getElementById("build-upgrades-title"),
        upText: doc.getElementById("build-upgrades-text"),
        list: doc.getElementById("build-upgrades-list"),
        up: doc.getElementById("build-upgrades") };
    }
    var body = el(doc, "div", "build-alert-body");
    if (!doc.getElementById("build-alert-title")) {
      // the page may carry the heading; a page without it still gets one
      var h = el(doc, "h2", "build-alert-title");
      h.textContent = TITLE;
      body.appendChild(h);
    }
    p = el(doc, "p", "build-alert-text");
    var up = el(doc, "div", "build-upgrades");
    var upTitle = el(doc, "h3", "build-upgrades-title");
    upTitle.textContent = UPGRADES_TITLE;
    var upText = el(doc, "p", "build-upgrades-text", "muted");
    var list = el(doc, "ul", "build-upgrades-list", "upgrade-list");
    up.appendChild(upTitle);
    up.appendChild(upText);
    up.appendChild(list);
    body.appendChild(p);
    body.appendChild(up);
    if (tabs && typeof tabs.fill === "function") {
      tabs.fill(doc, "build-alert", body);
    } else {
      box.appendChild(body);
    }
    return { text: p, upTitle: upTitle, upText: upText, list: list, up: up };
  }

  /* `tabs`: the Play tab helper; the page passes nothing and the global
     window.ALTabs is used when it is there. */
  function paint(doc, snap, tabs) {
    var box = doc.getElementById("build-alert");
    if (!box) { return; }
    if (tabs === undefined && typeof window !== "undefined") { tabs = window.ALTabs; }
    var m = model(snap);
    box.hidden = !m.show;
    var alertText = m.alert ? m.alert.text : "";
    var fresh = alertText && alertText !== lastAlert;
    lastAlert = alertText;
    if (!m.show) { return; }
    var built = !!doc.getElementById("build-alert-text");
    var q = parts(doc, box, tabs);
    // merge fix: ALTabs.fill says "build alert" only on the first fill;
    // a later, different alert is news for Play too (tabs.js notify)
    if (fresh && built && tabs && typeof tabs.notify === "function") {
      tabs.notify(doc, "build alert");
    }
    q.text.textContent = m.alert ? m.alert.text : "";
    q.text.hidden = !m.alert;
    q.up.hidden = !m.upgrades;
    while (q.list.firstChild) { q.list.removeChild(q.list.firstChild); }
    if (!m.upgrades) { return; }
    q.upText.textContent = m.upgrades.text;
    m.upgrades.items.forEach(function (n) {
      var li = doc.createElement("li");
      var head = doc.createElement("strong");
      head.textContent = n.head;
      li.appendChild(head);
      [n.line, n.fit].forEach(function (t, i) {
        if (!t) { return; }
        var s = doc.createElement("span");
        s.className = i ? "muted small upgrade-fit" : "upgrade-line";
        s.textContent = " " + t;
        li.appendChild(s);
      });
      q.list.appendChild(li);
    });
  }

  return { model: model, paint: paint, MAX: MAX, TITLE: TITLE,
    UPGRADES_TITLE: UPGRADES_TITLE };
}));
