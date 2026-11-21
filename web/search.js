/* AshLight dashboard: build search strings (UTIL-SEARCHSTR, decision 0030).
   UMD: CommonJS for node --test (app/test/search.test.js), window.ALSearch
   for the page. The core builds every string from the loaded build
   (server/al/theorycraft/searchstr.py) and sends them in GET /api/build as
   `search_strings`; this file lists them, each with a Copy button. The
   clipboard is written only inside that button's click handler (decision
   0014); nothing is copied by itself and nothing is sent to the game. No
   timers, no network.

   PLAY-TD-19C-BUILD-GRID (TD-19, plan 03 section 4): the Search strings
   card is a fixed card of the Build and items grid, so its list pages
   instead of growing. rowPager() is the pager of a list whose rows carry
   controls (Copy, a link): the same page arithmetic, Full text page and
   class names as web/pager.js (window.ALPager, read when a pager is made,
   since pager.js loads after this file), but each list row may end in
   controls, so a row is 24 px (the 24 px target) instead of 22. The
   Health and next card (web/health.js) and the Build card's gear and gems
   pages (web/app.js) use it too. A page changes only on a press of Prev,
   Next or Full text / List; a data change keeps the page. */
(function (root, factory) {
  "use strict";
  if (typeof module === "object" && module.exports) {
    module.exports = factory(function () { return require("./pager.js"); });
  } else {
    root.ALSearch = factory(function () { return root.ALPager || null; });
  }
}(typeof self !== "undefined" ? self : this, function (pagerLib) {
  "use strict";

  var COPIED = "Copied - paste it into the search box in game";
  var FALLBACK = "Can't copy here. The text is selected: press Ctrl+C.";
  var FALLBACK_SAID = "can't copy here, the text is selected, press Ctrl+C";
  var EMPTY = "No build yet. Load one on the Build card.";
  var NONE = "No search strings for this build.";
  // control rows are 24 px: 7 rows + the pager row under the intro line
  // fill the 10-row block (8 + 28 + 22 = 218 of 220; compact 5: 170 of 176)
  var SIZE = { full: 7, compact: 5 };
  var CTL_PX = 24;
  var ROW_PX = 22;

  function str(v) { return typeof v === "string" ? v : ""; }
  function isFn(v) { return typeof v === "function"; }

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

  /* The page's size class from the token block (--al-size-class on the
     root): "compact" or "full" (the flow class pages like full). */
  function sizeClass(doc) {
    try {
      var w = doc && doc.defaultView;
      var v = w && isFn(w.getComputedStyle)
        ? String(w.getComputedStyle(doc.documentElement).getPropertyValue("--al-size-class")).trim()
        : "";
      return v === "compact" ? "compact" : "full";
    } catch (e) {
      return "full";
    }
  }

  function el(doc, tag, cls, text) {
    var n = doc.createElement(tag);
    if (cls) { n.className = cls; }
    if (text !== undefined && text !== null) { n.textContent = text; }
    return n;
  }

  function clear(n) {
    if (isFn(n.replaceChildren)) { n.replaceChildren(); return; }
    while (n.firstChild) { n.removeChild(n.firstChild); }
  }

  /* A Copy button for one row. The clipboard is written only inside its
     click handler. The outcome is the button's own word and name (no live
     region, audit 0004 U16); only the last clicked button in `group` says
     anything. `sel` is the node selected when the clipboard refuses. */
  function copyButton(doc, text, name, sel, group, nav) {
    var btn = el(doc, "button", "secondary btn-24", "Copy");
    btn.type = "button";
    btn.setAttribute("aria-label", name);
    btn.setAttribute("data-copy", name);
    var tell = function (word, said, state) {
      var others = group && isFn(group.querySelectorAll) ? group.querySelectorAll("[data-copy]") : [];
      Array.prototype.forEach.call(others, function (b) {
        b.textContent = "Copy";
        b.setAttribute("aria-label", b.getAttribute("data-copy"));
        b.removeAttribute("title");
      });
      btn.textContent = word;
      btn.setAttribute("title", said);
      btn.setAttribute("aria-label", name + " (" + state + ")");
    };
    btn.addEventListener("click", function () {
      copy(text, nav, function () { tell("Copied", COPIED, "copied"); }, function () {
        var row = btn.parentNode;
        var target = sel || (row && isFn(row.querySelector) ? row.querySelector(".al-row-txt") : null);
        if (target) { selectText(doc, target); }
        tell("Press Ctrl+C", FALLBACK, FALLBACK_SAID);
      });
    });
    return btn;
  }

  var live = []; // every rowPager made, for relayout()

  /* A pager for a list whose rows may carry controls. opts: rows, label
     (the list's name for the button labels), text(row) -> the row's whole
     text (title and Full text page), parts(row) -> [{text, cls}] shown in
     the list row (default: the whole text), controls(doc, row, list) ->
     nodes after the row text (list page only), rowClass(row) -> extra
     class, empty (the one row shown for no rows), size {full, compact}
     (rows a page), sizeClass (a function or a string, as web/pager.js).
     Returns {node, list, bar, prev, next, toggle, set, press, state,
     render}. */
  function rowPager(doc, opts) {
    var P = pagerLib();
    var o = opts || {};
    var CLS = P.CLS;
    var textOf = isFn(o.text) ? o.text : function (r) { return String(r == null ? "" : r); };
    var name = typeof o.label === "string" && o.label ? o.label : "list";
    var sizes = o.size && o.size.full ? o.size : P.LIST_ROWS;
    var rows = Array.isArray(o.rows) ? o.rows.slice() : [];
    var mode = "list";
    var index = { list: 0, text: 0 };
    var lastClass = null;

    var node = el(doc, "div", CLS.host);
    var list = el(doc, "ul", CLS.list);
    var bar = el(doc, "div", CLS.bar);
    var count = el(doc, "span", CLS.count);
    var mk = function (t) { var b = el(doc, "button", CLS.button, t); b.setAttribute("type", "button"); return b; };
    var prev = mk("Prev");
    var next = mk("Next");
    var toggle = mk("Full text");
    prev.setAttribute("aria-label", "Previous page of " + name);
    next.setAttribute("aria-label", "Next page of " + name);
    bar.appendChild(count);
    bar.appendChild(prev);
    bar.appendChild(next);
    bar.appendChild(toggle);
    node.appendChild(list);
    node.appendChild(bar);

    function klass() {
      var v = isFn(o.sizeClass) ? o.sizeClass() : o.sizeClass;
      return v === "compact" ? "compact" : "full";
    }

    /* Full text entries that fit the list block of this pager: up to the
       pager.js figures, fewer (or shorter) when the block is smaller. */
    function textShape(k) {
      var t = P.TEXT[k];
      var px = sizes[k] * (isFn(o.controls) ? CTL_PX : ROW_PX);
      var entries = Math.min(t.entries, Math.floor(px / (t.lines * ROW_PX)));
      if (entries >= 1) { return { entries: entries, lines: t.lines, cols: t.cols }; }
      return { entries: 1, lines: Math.max(1, Math.floor(px / ROW_PX)), cols: t.cols };
    }

    function size() {
      var k = klass();
      return mode === "text" ? textShape(k).entries : sizes[k];
    }

    function state() {
      var p = P.page(rows, size(), index[mode]);
      index[mode] = p.index;
      p.mode = mode;
      p.sizeClass = klass();
      return p;
    }

    function setEnd(b, on) {
      if (on) { b.removeAttribute("aria-disabled"); } else { b.setAttribute("aria-disabled", "true"); }
    }

    function listRow(r) {
      var t = String(textOf(r) == null ? "" : textOf(r));
      var extra = isFn(o.rowClass) ? str(o.rowClass(r)) : "";
      var ctl = isFn(o.controls) ? (o.controls(doc, r, list) || []) : [];
      var li = el(doc, "li", null);
      var span = li;
      if (ctl.length || isFn(o.parts)) {
        span = el(doc, "span", null);
        li.appendChild(span);
      }
      P.rowRule(span, t);
      if (isFn(o.parts)) {
        clear(span);
        (o.parts(r) || []).forEach(function (part) {
          span.appendChild(el(doc, "span", part.cls || null, str(part.text)));
        });
      }
      if (span !== li) { li.className = "al-row-ctl"; }
      if (extra) { li.className = (li.className ? li.className + " " : "") + extra; }
      ctl.forEach(function (c) { li.appendChild(c); });
      return li;
    }

    function render() {
      var p = state();
      var k = p.sizeClass;
      lastClass = k;
      clear(list);
      list.className = mode === "text" ? CLS.list + " " + CLS.text : CLS.list;
      var empty = isFn(o.empty) ? o.empty() : o.empty;
      if (!rows.length && empty) {
        list.appendChild(P.rowRule(el(doc, "li", null), str(empty)));
      }
      p.items.forEach(function (r) {
        if (mode === "text") {
          var t = String(textOf(r) == null ? "" : textOf(r));
          var shape = textShape(k);
          var li = el(doc, "li", CLS.entry);
          li.setAttribute("title", t);
          P.wrap(t, shape.cols, shape.lines).forEach(function (line) {
            li.appendChild(el(doc, "span", CLS.line, line));
          });
          list.appendChild(li);
        } else {
          list.appendChild(listRow(r));
        }
      });
      count.textContent = p.label;
      prev.hidden = next.hidden = p.pages < 2;
      setEnd(prev, p.hasPrev);
      setEnd(next, p.hasNext);
      toggle.hidden = !rows.length;
      toggle.textContent = mode === "text" ? "List" : "Full text";
      toggle.setAttribute("aria-label", (mode === "text" ? "Show the list of " : "Show the full text of ") + name);
      return p;
    }

    function press(which) {
      var p = state();
      if (which === "prev" && p.hasPrev) {
        index[mode] = p.index - 1;
      } else if (which === "next" && p.hasNext) {
        index[mode] = p.index + 1;
      } else if (which === "toggle") {
        var first = p.from ? p.from - 1 : 0; // keep the first shown row in view
        mode = mode === "text" ? "list" : "text";
        index[mode] = Math.floor(first / size());
      } else {
        return p;
      }
      return render();
    }

    [[prev, "prev"], [next, "next"], [toggle, "toggle"]].forEach(function (pair) {
      pair[0].addEventListener("click", function () { press(pair[1]); });
    });

    function set(newRows) {
      rows = Array.isArray(newRows) ? newRows.slice() : [];
      return render();
    }

    /* the size class changed (a window resize): page again */
    function relayout() {
      if (lastClass !== klass()) { render(); }
    }

    render();
    var api = { node: node, list: list, bar: bar, count: count, prev: prev, next: next,
      toggle: toggle, set: set, press: press, state: state, render: render, relayout: relayout };
    live.push(api);
    return api;
  }

  /* web/pager.js's own pager for a list of plain text rows (web/app.js
     reaches the pager only through this file); it pages again on
     relayout() like a rowPager. */
  function textPager(doc, opts) {
    var pg = pagerLib().build(doc, opts);
    var lastClass = null;
    var klass = function () {
      var v = opts && (isFn(opts.sizeClass) ? opts.sizeClass() : opts.sizeClass);
      return v === "compact" ? "compact" : "full";
    };
    lastClass = klass();
    live.push({ relayout: function () {
      if (lastClass !== klass()) { lastClass = klass(); pg.render(); }
    } });
    return pg;
  }

  /* Re-page every rowPager whose size class changed. */
  function relayout() {
    live.forEach(function (p) { p.relayout(); });
  }

  /* The whole text of one search string row (title and Full text). */
  function rowText(r) {
    return r.label + ": " + r.text + (r.note ? " " + r.note : "");
  }

  var card = { doc: null, pager: null, loaded: false };

  function paint(doc, buildDoc, nav) {
    var box = doc.getElementById("searchbox");
    var slot = doc.getElementById("search-list");
    if (!box || !slot) { return; }
    box.hidden = false;
    var rows = view(buildDoc);
    if (card.doc !== doc || !card.pager) {
      card.doc = doc;
      card.pager = rowPager(doc, {
        label: "search strings", size: SIZE,
        sizeClass: function () { return sizeClass(doc); },
        text: rowText,
        empty: function () { return card.loaded ? NONE : EMPTY; },
        parts: function (r) {
          return [{ text: r.label + ": ", cls: "al-row-lbl" }, { text: r.text, cls: "al-row-txt" }];
        },
        /* UX-B5-CARDS: only the Copy button takes focus; its name gains the
           outcome, which a screen reader may read on the click that caused
           it (best effort; never at any other time) */
        controls: function (d, r, list) {
          var name = "Copy " + r.label + " search string";
          return [copyButton(d, r.text, name, null, list, nav)];
        }
      });
      slot.replaceChildren(card.pager.node);
    }
    card.loaded = !!(buildDoc && buildDoc.loaded);
    card.pager.set(rows);
  }

  return { view: view, paint: paint, copy: copy, copyButton: copyButton, rowPager: rowPager,
    textPager: textPager,
    relayout: relayout, sizeClass: sizeClass, selectText: selectText, SIZE: SIZE,
    COPIED: COPIED, FALLBACK: FALLBACK, EMPTY: EMPTY, NONE: NONE };
}));
