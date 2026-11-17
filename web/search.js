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
  var FALLBACK = "Can't copy here. The text is selected: press Ctrl+C.";
  var FALLBACK_SAID = "can't copy here, the text is selected, press Ctrl+C";

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

  /* Select a text block's words so the player can press Ctrl+C. */
  function selectText(doc, node) {
    var sel = doc.getSelection ? doc.getSelection() : null;
    if (!sel || !doc.createRange) { return; }
    var range = doc.createRange();
    range.selectNodeContents(node);
    sel.removeAllRanges();
    sel.addRange(range);
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
      /* UX-B5-CARDS: a wrapping text block, not a one-line input, so a
         long string (the waystone one runs to about 250 characters) is
         read whole at 320 px; only the Copy button takes focus */
      var code = doc.createElement("p");
      code.className = "search-text";
      code.textContent = r.text;
      li.appendChild(code);
      var btn = doc.createElement("button");
      btn.type = "button";
      btn.className = "secondary";
      btn.textContent = "Copy";
      btn.setAttribute("aria-label", "Copy " + r.label + " search string");
      var said = doc.createElement("span");
      said.className = "muted search-said";
      /* UX-B5-CARDS: no live region (the page keeps its 12, audit 0004
         U16). The word beside the button is for the eye; the focused
         button's own name gains the outcome, which a screen reader may
         read on the click that caused it (best effort; never at any other
         time). Only the last clicked row says anything. */
      var name = "Copy " + r.label + " search string";
      var tell = function (text, state) {
        Array.prototype.forEach.call(list.querySelectorAll(".search-row"), function (row) {
          var s = row.querySelector(".search-said"), b = row.querySelector("button");
          if (s) { s.textContent = ""; }
          if (b && b.dataset.name) { b.setAttribute("aria-label", b.dataset.name); }
        });
        said.textContent = text;
        btn.setAttribute("aria-label", name + " (" + state + ")");
      };
      btn.dataset.name = name;
      btn.addEventListener("click", function () {
        copy(r.text, nav, function () { tell(COPIED, "copied"); },
          function () { selectText(doc, code); tell(FALLBACK, FALLBACK_SAID); });
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
