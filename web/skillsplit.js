/* AshLight dashboard: damage by skill on the Build card (MATH-SKILL-SPLIT,
   decision 0004). UMD: CommonJS for node --test (app/test/skillsplit.test.js),
   window.ALSkillSplit for the page. The core reads Path of Building's own
   per-skill DPS (the FullDPSSkill entries every saved build carries) and
   its ailment DPS, and sends them in GET /api/build as `skill_split`
   (server/al/theorycraft/skillsplit.py); this file only lists them,
   compactly. No live region (the page keeps its 12), no timers, no
   network. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALSkillSplit = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var MAX_ROWS = 6;

  function str(v) { return typeof v === "string" ? v : ""; }
  function isNum(v) { return typeof v === "number" && isFinite(v); }

  function fmt(n) {
    var r = n >= 100 ? Math.round(n) : Math.round(n * 10) / 10;
    return r.toLocaleString("en-US");
  }

  function pct(share) {
    var p = Math.round(share * 100);
    return p < 1 ? "under 1%" : p + "%";
  }

  /* doc: the GET /api/build answer (or null) -> {show, rows, more, ailments}. */
  function view(doc) {
    var s = doc && doc.loaded && doc.skill_split && typeof doc.skill_split === "object"
      ? doc.skill_split : null;
    var none = { show: false, rows: [], more: "", ailments: "" };
    if (!s) { return none; }
    var all = (Array.isArray(s.skills) ? s.skills : []).filter(function (r) {
      return r && str(r.name) && isNum(r.dps) && r.dps > 0 && isNum(r.share);
    });
    var rows = all.slice(0, MAX_ROWS).map(function (r) {
      var name = isNum(r.count) && r.count !== 1 ? r.count + " x " + r.name : r.name;
      var part = str(r.part) ? " (" + r.part + ")" : "";
      return { name: name + part, text: fmt(r.dps) + " DPS, " + pct(r.share) };
    });
    var left = all.length - rows.length;
    var more = left > 0 ? left + (left === 1 ? " more skill" : " more skills") +
      " in Path of Building." : "";
    var ok = (Array.isArray(s.ailments) ? s.ailments : []).filter(function (a) {
      return a && str(a.label) && isNum(a.dps) && a.dps > 0;
    });
    var dot = [], total = null, impale = null;
    ok.forEach(function (a) {
      if (a.id === "TotalDotDPS") { total = a.dps; } else if (a.id === "ImpaleDPS") {
        impale = a.dps;
      } else { dot.push(a.label + " " + fmt(a.dps)); }
    });
    var said = [];
    if (dot.length) { said.push("Damage over time, per second: " + dot.join(", ") + "."); }
    if (total !== null) {
      said.push((dot.length ? "All together: " : "Damage over time, per second: ") +
        fmt(total) + ".");
    }
    if (impale !== null) { said.push("Impale: " + fmt(impale) + " per second."); }
    var ailments = said.join(" ");
    if (!rows.length && !ailments) { return none; }
    return { show: true, rows: rows, more: more, ailments: ailments };
  }

  function el(doc, tag, cls, text) {
    var e = doc.createElement(tag);
    if (cls) { e.className = cls; }
    if (text !== undefined && text !== null) { e.textContent = text; }
    return e;
  }

  var lastSig = null;

  function paint(doc, buildDoc) {
    var wrap = doc.getElementById("split-wrap");
    if (!wrap) { return; }
    var v = view(buildDoc);
    var sig = JSON.stringify(v);
    if (sig === lastSig) { return; }
    lastSig = sig;
    wrap.hidden = !v.show;
    var list = doc.getElementById("split-list");
    list.replaceChildren();
    list.hidden = !v.rows.length;
    v.rows.forEach(function (r) {
      var row = el(doc, "div", "kv-row");
      row.appendChild(el(doc, "dt", null, r.name));
      row.appendChild(el(doc, "dd", "mono", r.text));
      list.appendChild(row);
    });
    var more = doc.getElementById("split-more");
    more.textContent = v.more;
    more.hidden = !v.more;
    var ail = doc.getElementById("split-ailments");
    ail.textContent = v.ailments;
    ail.hidden = !v.ailments;
  }

  return { view: view, paint: paint, MAX_ROWS: MAX_ROWS };
}));
