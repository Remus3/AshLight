/* AshLight dashboard: the live zone guide (ZONE-GUIDE, decision 0043).
   UMD: CommonJS for node --test (app/test/zoneguide.test.js),
   window.ALZoneGuide for the page. The core picks the guide for the zone
   the player is in and sends it in the snapshot's `zone_guide` part
   (server/al/zoneguide.py); this file only lays it out in the element
   with id "zone-guide" and repaints when it changes. No clicks, no
   timers, no network. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALZoneGuide = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var KIND = { spirit: "Spirit", resist: "Resistance", passive: "Passive points",
               life: "Life", mana: "Mana", gem: "Gem", charm: "Charm slot",
               flask: "Flask", item: "Item", skill: "Skill", other: "Bonus" };

  function str(v) { return typeof v === "string" ? v : ""; }

  /* The rows to show, as [{cls, label, text, more}] in order; [] for none.
     The first rows (zone, goal, first bonus, level lean, waypoint, next
     zone) always show; rows with more: true fold under "More for this
     zone" so the guide stays short on the Play tab. */
  function rows(g) {
    if (!g || typeof g !== "object" || !str(g.zone)) { return []; }
    var out = [];
    var more = false;
    function add(cls, label, text) {
      if (str(text)) { out.push({ cls: cls, label: label, text: text, more: more }); }
    }
    var bonus = (Array.isArray(g.optional) ? g.optional : []).filter(function (o) {
      return o && str(o.text);
    });
    function addBonus(o) {
      add("zg-bonus zg-" + (KIND[o.kind] ? o.kind : "other"), "Bonus: ", o.text);
    }
    add("zg-title", "", str(g.act) ? g.act + ": " + g.zone : g.zone);
    add("zg-objective", "Goal: ", g.objective);
    if (bonus.length) { addBonus(bonus[0]); }
    if (g.advice && str(g.advice.text)) {
      add("zg-advice zg-" + str(g.advice.mode), "", g.advice.text);
    }
    add("zg-waypoint", "", g.waypoint);
    add("zg-next", "Next zone: ", g.next);
    more = true;
    bonus.slice(1).forEach(addBonus);
    add("zg-layout", "Layout: ", g.layout);
    var q = g.quest;
    if (q && typeof q === "object") {
      var steps = Array.isArray(q.steps) ? q.steps : [];
      if (steps.length && str(q.act)) {
        add("zg-quest", "", q.act + " main path: " + (q.steps_done || 0) + " of " +
            steps.length + " zones passed.");
      }
      add("zg-quest", "", q.bonus_text);
      (Array.isArray(q.missed) ? q.missed : []).forEach(function (m) {
        if (m) { add("zg-missed", "", m.text); }
      });
    }
    add("zg-source muted", "", g.source);
    return out;
  }

  var lastKey = null;

  var MORE = "More for this zone";
  var wasOpen = false;

  /* One node holding the rows: the short part, then a closed <details>
     with the rest (its open state kept across repaints). */
  function build(doc, list) {
    var node = doc.createElement("div");
    node.className = "zone-guide-body";
    var fold = null;
    list.forEach(function (r) {
      var p = doc.createElement("p");
      p.className = r.cls;
      if (r.label) {
        var b = doc.createElement("strong");
        b.textContent = r.label;
        p.appendChild(b);
      }
      p.appendChild(doc.createTextNode(r.text));
      if (r.more) {
        if (!fold) {
          fold = doc.createElement("details");
          fold.className = "zg-more";
          fold.open = wasOpen;
          fold.addEventListener("toggle", function () { wasOpen = fold.open; });
          var s = doc.createElement("summary");
          s.textContent = MORE;
          fold.appendChild(s);
          node.appendChild(fold);
        }
        fold.appendChild(p);
      } else {
        node.appendChild(p);
      }
    });
    return node;
  }

  /* Fill the Play tab slot through ALTabs when the page has it, else the
     #zone-guide element directly. */
  function paint(doc, snap) {
    var list = rows(snap && snap.zone_guide);
    var key = JSON.stringify(list);
    if (key === lastKey) { return; }
    var node = build(doc, list);
    var tabs = typeof self !== "undefined" ? self.ALTabs : null;
    if (tabs && typeof tabs.fill === "function") {
      lastKey = key;
      tabs.fill(doc, "zone-guide", list.length ? node : null);
      return;
    }
    var box = doc.getElementById("zone-guide");
    if (!box) { return; }
    lastKey = key;
    while (box.firstChild) { box.removeChild(box.firstChild); }
    box.appendChild(node);
    box.hidden = list.length === 0;
  }

  return { rows: rows, build: build, paint: paint, KIND: KIND, MORE: MORE };
}));
