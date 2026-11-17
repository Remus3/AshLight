/* AshLight dashboard: build search strings (UTIL-SEARCHSTR, decision 0030).
   UMD: CommonJS for node --test (app/test/search.test.js), window.ALSearch
   for the page. The core builds every string from the loaded build
   (server/al/theorycraft/searchstr.py) and sends them in GET /api/build as
   `search_strings`; this file lists them, each with a Copy button. The
   clipboard is written only inside that button's click handler (decision
   0014); nothing is copied by itself and nothing is sent to the game. No
   timers, no network. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALSearch = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var COPIED = "Copied - paste it into the search box in game";
  var FALLBACK = "Can't copy here. Select the text and press Ctrl+C.";

  function str(v) { return typeof v === "string" ? v : ""; }

  /* doc: the GET /api/build answer (or null) -> rows, [] when none. */
  function view(doc) {
    var list = doc && doc.loaded && Array.isArray(doc.search_strings) ? doc.search_strings : [];
    return list.filter(function (s) { return s && str(s.text); }).map(function (s) {
      var dropped = typeof s.dropped === "number" && s.dropped > 0 ? s.dropped : 0;
      return {
        id: str(s.id), label: str(s.label) || "Search string", why: str(s.why),
        text: s.text,
        note: dropped ? "Shortened to fit the search box: " + dropped +
          (dropped === 1 ? " term" : " terms") + " left out." : ""
      };
    });
  }

  /* Write `text` to the clipboard; called only from a click handler. */
  function copy(text, nav, done, fail) {
    if (nav && nav.clipboard && nav.clipboard.writeText) {
      nav.clipboard.writeText(text).then(done, fail);
    } else {
      fail();
    }
  }

  function paint(doc, buildDoc, nav) {
    var box = doc.getElementById("searchbox");
    if (!box) { return; }
    var rows = view(buildDoc);
    box.hidden = !rows.length;
    var list = doc.getElementById("search-list");
    list.replaceChildren();
    rows.forEach(function (r) {
      var li = doc.createElement("li");
      li.className = "search-row";
      var h = doc.createElement("h3");
      h.className = "sub-h";
      h.textContent = r.label;
      li.appendChild(h);
      if (r.why) {
        var p = doc.createElement("p");
        p.className = "muted";
        p.textContent = r.why;
        li.appendChild(p);
      }
      var code = doc.createElement("input");
      code.type = "text";
      code.readOnly = true;
      code.className = "search-text mono";
      code.value = r.text;
      code.setAttribute("aria-label", r.label + " search string");
      li.appendChild(code);
      var btn = doc.createElement("button");
      btn.type = "button";
      btn.className = "secondary";
      btn.textContent = "Copy";
      btn.setAttribute("aria-label", "Copy " + r.label + " search string");
      var said = doc.createElement("span");
      said.className = "muted search-said";
      btn.addEventListener("click", function () {
        copy(r.text, nav, function () { said.textContent = COPIED; },
          function () { code.focus(); code.select(); said.textContent = FALLBACK; });
      });
      li.appendChild(btn);
      li.appendChild(said);
      if (r.note) {
        var n = doc.createElement("p");
        n.className = "muted";
        n.textContent = r.note;
        li.appendChild(n);
      }
      list.appendChild(li);
    });
  }

  return { view: view, paint: paint, copy: copy, COPIED: COPIED, FALLBACK: FALLBACK };
}));
