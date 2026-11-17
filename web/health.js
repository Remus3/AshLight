/* AshLight dashboard: build health and "look for next" (MATH-BUILD-HEALTH,
   MATH-NEXT-LOOK, decision 0004). UMD: CommonJS for node --test
   (app/test/health.test.js), window.ALHealth for the page. The core builds
   both from Path of Building's own numbers (server/al/theorycraft/
   health.py) and sends them in GET /api/build as `health` and `next_look`;
   this file only lists them. Each "look for next" row has a Copy button
   that writes its search string to the clipboard inside that click only
   (decision 0014, via ALSearch.copy). No live region (the page keeps its
   12), no timers, no network. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALHealth = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* the word shown before each warning, so severity never rests on colour */
  var SEVERITY = { high: "Fix first", medium: "Check", low: "Note" };
  var ALL_CLEAR = "No resistance, attribute or Spirit problems in Path of Building's numbers.";
  var NO_STATS = "This build has no Path of Building numbers. Open it in Path of Building, " +
    "then copy its code again.";
  // UX-B9-CARDS: name the optional calc, not "build calc"
  var NO_WEIGHTS = "More stats show here for each slot once you check items. This " +
    "needs the optional Path of Building calc, which is off by default.";
  var COPIED = "Copied - paste it into the search box in game";
  var FALLBACK = "Can't copy here. The text is selected: press Ctrl+C.";
  var FALLBACK_SAID = "can't copy here, the text is selected, press Ctrl+C";

  function str(v) { return typeof v === "string" ? v : ""; }
  function isNum(v) { return typeof v === "number" && isFinite(v); }

  function fmt(n) {
    var r = Math.round(n * 10) / 10;
    return r.toLocaleString("en-US");
  }

  /* doc: the GET /api/build answer (or null) -> the health view. */
  function view(doc) {
    var h = doc && doc.health && typeof doc.health === "object" ? doc.health : null;
    if (!doc || !doc.loaded || !h || !h.loaded) {
      return { show: false, message: "", warnings: [], values: [] };
    }
    var warnings = (Array.isArray(h.warnings) ? h.warnings : []).filter(function (w) {
      return w && str(w.text) && SEVERITY[w.severity];
    }).map(function (w) {
      return { id: str(w.id), severity: w.severity, word: SEVERITY[w.severity], text: w.text };
    });
    var values = (Array.isArray(h.values) ? h.values : []).filter(function (v) {
      return v && str(v.label) && isNum(v.value);
    }).map(function (v) {
      return { label: v.label, text: fmt(v.value) + str(v.unit) };
    });
    /* UX-U25: with no saved stats the Build card already says so (Key
       stats); this card says nothing and shows only for Look for next rows */
    if (h.has_stats === false && !warnings.length && !values.length) {
      return { show: nextView(doc).rows.length > 0, message: "", warnings: [], values: [] };
    }
    var message = str(h.message);
    if (!message && h.has_stats &&
        !warnings.some(function (w) { return w.severity !== "low"; })) {
      message = ALL_CLEAR;
    }
    if (!message && !warnings.length && !values.length) { message = NO_STATS; }
    return { show: true, message: message, warnings: warnings, values: values };
  }

  /* doc -> {rows: [{slot, line, text, note}], hint} for "look for next". */
  function nextView(doc) {
    var n = doc && doc.loaded && doc.next_look && typeof doc.next_look === "object"
      ? doc.next_look : null;
    if (!n) { return { rows: [], hint: "" }; }
    var rows = (Array.isArray(n.slots) ? n.slots : []).filter(function (r) {
      return r && str(r.slot) && str(r.line) && str(r.text);
    }).map(function (r) {
      var dropped = isNum(r.dropped) && r.dropped > 0 ? r.dropped : 0;
      return { slot: r.slot, line: r.line, text: r.text,
        note: dropped ? "Shortened to fit the search box: " + dropped +
          (dropped === 1 ? " term" : " terms") + " left out." : "" };
    });
    return { rows: rows, hint: n.pob_weights ? "" : NO_WEIGHTS };
  }

  function el(doc, tag, cls, text) {
    var e = doc.createElement(tag);
    if (cls) { e.className = cls; }
    if (text !== undefined && text !== null) { e.textContent = text; }
    return e;
  }

  function copyText(text, nav, done, fail) {
    var S = typeof window !== "undefined" ? window.ALSearch : null;
    if (S && S.copy) { S.copy(text, nav, done, fail); return; }
    if (nav && nav.clipboard && nav.clipboard.writeText) {
      nav.clipboard.writeText(text).then(done, fail);
    } else {
      fail();
    }
  }

  function selectText(doc, node) {
    var sel = doc.getSelection ? doc.getSelection() : null;
    if (!sel || !doc.createRange) { return; }
    var range = doc.createRange();
    range.selectNodeContents(node);
    sel.removeAllRanges();
    sel.addRange(range);
  }

  function paintNext(doc, buildDoc, nav) {
    var wrap = doc.getElementById("next-wrap");
    var list = doc.getElementById("next-list");
    var hint = doc.getElementById("next-hint");
    if (!wrap || !list) { return; }
    var v = nextView(buildDoc);
    list.replaceChildren();
    wrap.hidden = !v.rows.length && !v.hint;
    if (hint) { hint.textContent = v.hint; hint.hidden = !v.hint; }
    v.rows.forEach(function (r) {
      var li = el(doc, "li", "search-row");
      var p = el(doc, "p");
      p.appendChild(el(doc, "strong", null, r.slot + ": "));
      p.appendChild(doc.createTextNode(r.line));
      li.appendChild(p);
      var code = el(doc, "p", "search-text", r.text);
      li.appendChild(code);
      var name = "Copy " + r.slot + " search string";
      var btn = el(doc, "button", "secondary", "Copy");
      btn.type = "button";
      btn.setAttribute("aria-label", name);
      btn.dataset.name = name;
      var said = el(doc, "span", "muted search-said");
      var tell = function (text, state) {
        Array.prototype.forEach.call(list.querySelectorAll(".search-row"), function (row) {
          var s = row.querySelector(".search-said"), b = row.querySelector("button");
          if (s) { s.textContent = ""; }
          if (b && b.dataset.name) { b.setAttribute("aria-label", b.dataset.name); }
        });
        said.textContent = text;
        btn.setAttribute("aria-label", name + " (" + state + ")");
      };
      btn.addEventListener("click", function () {
        copyText(r.text, nav, function () { tell(COPIED, "copied"); },
          function () { selectText(doc, code); tell(FALLBACK, FALLBACK_SAID); });
      });
      li.appendChild(btn);
      li.appendChild(said);
      if (r.note) { li.appendChild(el(doc, "p", "muted", r.note)); }
      list.appendChild(li);
    });
  }

  var lastSig = null;

  function paint(doc, buildDoc, nav) {
    var box = doc.getElementById("healthbox");
    if (!box) { return; }
    var v = view(buildDoc);
    var sig = JSON.stringify([v, nextView(buildDoc)]);
    if (sig === lastSig) { return; }
    lastSig = sig;
    box.hidden = !v.show;
    var msg = doc.getElementById("health-msg");
    msg.textContent = v.message;
    msg.hidden = !v.message;
    var list = doc.getElementById("health-list");
    list.replaceChildren();
    list.hidden = !v.warnings.length;
    v.warnings.forEach(function (w) {
      var li = el(doc, "li", "health-row");
      li.dataset.severity = w.severity;
      li.appendChild(el(doc, "strong", "health-word", w.word + ": "));
      li.appendChild(doc.createTextNode(w.text));
      list.appendChild(li);
    });
    var vals = doc.getElementById("health-values");
    vals.replaceChildren();
    vals.hidden = !v.values.length;
    v.values.forEach(function (x) {
      var row = el(doc, "div", "kv-row");
      row.appendChild(el(doc, "dt", null, x.label));
      row.appendChild(el(doc, "dd", null, x.text));
      vals.appendChild(row);
    });
    paintNext(doc, buildDoc, nav);
  }

  return { view: view, nextView: nextView, paint: paint, SEVERITY: SEVERITY,
    ALL_CLEAR: ALL_CLEAR, NO_STATS: NO_STATS, NO_WEIGHTS: NO_WEIGHTS, COPIED: COPIED };
}));
