/* AshLight dashboard: the pager (TD-19, PLAY-TD-19A-PAGER; docs/plan/
   03-target-design section 4). No card on Build and items or Run grows or
   scrolls: a list longer than its page pages ("1-10 of 23", Prev / Next),
   and the full text of every row is on the card's "Full text" page, one
   button in the pager row away ("Full text" / "List").

   Numbers (px at s = 1): a list row is one line of 22 px, the pager row is
   28 px. A list page holds 10 rows (8 in the compact class). A Full text
   page holds 3 entries of up to 3 wrapped lines (2 entries of up to 4
   lines in the compact class); a line is at most 47 characters (37
   compact), the widths of section 4 [D]. No composed string is over 120
   characters, so an entry never needs a fourth (fifth) line; a longer one
   ends in "..." and keeps its whole text in title.

   ZERO-CLICK: a page never advances by itself. No timer, no animation, no
   network, no clipboard, no live region. A page changes only on a press
   of Prev, Next or the switch; a data change keeps the page (clamped to
   the last one). The pressed button is never re-created or disabled, so
   focus stays on it (an end button says aria-disabled="true" and does
   nothing).

   The stylesheet rules for the class names below land with the first card
   that uses the pager (PLAY-TD-19C-BUILD-GRID owns web/app.css); this file
   sets classes, text and title only, never an inline style (CSP
   style-src 'self', and the text-spacing override must win).

   UMD like web/regions.js: CommonJS for node --test (app/test/
   pager.test.js), window.ALPager in the page; it registers itself as a
   helper (region null) with window.ALRegions when that is loaded.

   Exports:
   - LIST_ROWS {full: 10, compact: 8}; TEXT {full: {entries 3, lines 3,
     cols 47}, compact: {entries 2, lines 4, cols 37}}; ROW_PX 22,
     PAGER_PX 28; CLS (the class names).
   - page(rows, size, index): the slice of one page, index clamped:
     {items, index, pages, from, to, total, label, hasPrev, hasNext}.
     label is "1-10 of 23" (empty when one page holds every row).
   - wrap(text, cols, maxLines): word wrap to lines of at most cols
     characters, at most maxLines lines (the last one ends in "..." when
     text is cut).
   - rowRule(el, text): the one-line row rule: class CLS.row (nowrap,
     ellipsis guard), the text, and the full text in title.
   - build(doc, opts): one card's pager. opts: rows (array), text(row) ->
     the row's full text (default String), sizeClass ("full" | "compact"
     or a function giving one; anything else counts as full), label (the
     card's name, for the button labels). Returns {node, list, bar, prev,
     next, toggle, set(rows), press(which), state(), render()}. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALPager = api;
    if (root.ALRegions && typeof root.ALRegions.register === "function") {
      root.ALRegions.register({ name: "pager", region: null });
    }
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var LIST_ROWS = { full: 10, compact: 8 };
  var TEXT = {
    full: { entries: 3, lines: 3, cols: 47 },
    compact: { entries: 2, lines: 4, cols: 37 }
  };
  var ROW_PX = 22;
  var PAGER_PX = 28;
  var CLS = {
    host: "al-pager-host",
    list: "al-pager-list",
    row: "al-row1",
    text: "al-pager-full",
    entry: "al-pager-entry",
    line: "al-pager-line",
    bar: "al-pager",
    count: "al-pager-count",
    button: "al-pager-btn"
  };
  var ELLIPSIS = "...";

  function isFn(v) { return typeof v === "function"; }
  function toInt(v, dflt) {
    return typeof v === "number" && isFinite(v) ? Math.floor(v) : dflt;
  }

  /* One page of rows. size < 1 counts as 1; index is clamped to 0 ..
     pages - 1 (an empty list is one empty page). */
  function page(rows, size, index) {
    var list = Array.isArray(rows) ? rows : [];
    var n = Math.max(1, toInt(size, 1));
    var total = list.length;
    var pages = Math.max(1, Math.ceil(total / n));
    var i = Math.min(Math.max(0, toInt(index, 0)), pages - 1);
    var start = i * n;
    var items = list.slice(start, start + n);
    var from = total ? start + 1 : 0;
    var to = start + items.length;
    return {
      items: items, index: i, pages: pages, from: from, to: to, total: total,
      label: pages > 1 ? from + "-" + to + " of " + total : "",
      hasPrev: i > 0, hasNext: i < pages - 1
    };
  }

  /* Word wrap: lines of at most cols characters, at most maxLines lines.
     A word longer than a line is cut at the line end. Cut text ends in
     "..." on the last line. */
  function wrap(text, cols, maxLines) {
    var c = Math.max(4, toInt(cols, 47));
    var m = Math.max(1, toInt(maxLines, 3));
    var words = String(text == null ? "" : text).replace(/\s+/g, " ").trim().split(" ");
    var lines = [];
    var cur = "";
    words.forEach(function (w) {
      if (!w) { return; }
      while (w.length > c) {
        if (cur) { lines.push(cur); cur = ""; }
        lines.push(w.slice(0, c));
        w = w.slice(c);
      }
      if (!cur) { cur = w; } else if (cur.length + 1 + w.length <= c) { cur += " " + w; } else {
        lines.push(cur);
        cur = w;
      }
    });
    if (cur) { lines.push(cur); }
    if (lines.length > m) {
      lines = lines.slice(0, m);
      var last = lines[m - 1];
      if (last.length + ELLIPSIS.length > c) { last = last.slice(0, c - ELLIPSIS.length).replace(/\s+$/, ""); }
      lines[m - 1] = last + ELLIPSIS;
    }
    return lines;
  }

  /* The one-line row rule: nowrap with the ellipsis as the last guard (the
     class), the full text in title. */
  function rowRule(el, text) {
    var t = String(text == null ? "" : text);
    el.className = CLS.row;
    el.textContent = t;
    el.setAttribute("title", t);
    return el;
  }

  function el(doc, tag, cls) {
    var n = doc.createElement(tag);
    if (cls) { n.className = cls; }
    return n;
  }

  function clear(n) {
    while (n.firstChild) { n.removeChild(n.firstChild); }
  }

  function button(doc, text) {
    var b = el(doc, "button", CLS.button);
    b.setAttribute("type", "button");
    b.textContent = text;
    return b;
  }

  function build(doc, opts) {
    var o = opts || {};
    var textOf = isFn(o.text) ? o.text : function (r) { return String(r == null ? "" : r); };
    var name = typeof o.label === "string" && o.label ? o.label : "list";
    var rows = Array.isArray(o.rows) ? o.rows.slice() : [];
    var mode = "list"; // "list" | "text"
    var index = { list: 0, text: 0 };

    var node = el(doc, "div", CLS.host);
    var list = el(doc, "ul", CLS.list);
    var bar = el(doc, "div", CLS.bar);
    var count = el(doc, "span", CLS.count);
    var prev = button(doc, "Prev");
    var next = button(doc, "Next");
    var toggle = button(doc, "Full text");
    prev.setAttribute("aria-label", "Previous page of " + name);
    next.setAttribute("aria-label", "Next page of " + name);
    bar.appendChild(count);
    bar.appendChild(prev);
    bar.appendChild(next);
    bar.appendChild(toggle);
    node.appendChild(list);
    node.appendChild(bar);

    function sizeClass() {
      var v = isFn(o.sizeClass) ? o.sizeClass() : o.sizeClass;
      return v === "compact" ? "compact" : "full";
    }

    function size() {
      var k = sizeClass();
      return mode === "text" ? TEXT[k].entries : LIST_ROWS[k];
    }

    function state() {
      var p = page(rows, size(), index[mode]);
      index[mode] = p.index;
      p.mode = mode;
      p.sizeClass = sizeClass();
      return p;
    }

    function setEnd(b, on) {
      if (on) { b.removeAttribute("aria-disabled"); } else { b.setAttribute("aria-disabled", "true"); }
    }

    function render() {
      var p = state();
      var k = p.sizeClass;
      clear(list);
      list.className = mode === "text" ? CLS.list + " " + CLS.text : CLS.list;
      p.items.forEach(function (r) {
        var li = el(doc, "li", null);
        var t = String(textOf(r) == null ? "" : textOf(r));
        if (mode === "text") {
          li.className = CLS.entry;
          li.setAttribute("title", t);
          wrap(t, TEXT[k].cols, TEXT[k].lines).forEach(function (line) {
            var d = el(doc, "span", CLS.line);
            d.textContent = line;
            li.appendChild(d);
          });
        } else {
          rowRule(li, t);
        }
        list.appendChild(li);
      });
      count.textContent = p.label;
      prev.hidden = next.hidden = p.pages < 2;
      setEnd(prev, p.hasPrev);
      setEnd(next, p.hasNext);
      toggle.textContent = mode === "text" ? "List" : "Full text";
      toggle.setAttribute("aria-label", (mode === "text" ? "Show the list of " : "Show the full text of ") + name);
      return p;
    }

    /* The only way a page changes: a press. which: "prev" | "next" |
       "toggle". An end button does nothing. */
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

    function on(b, which) {
      if (isFn(b.addEventListener)) {
        b.addEventListener("click", function () { press(which); });
      }
    }
    on(prev, "prev");
    on(next, "next");
    on(toggle, "toggle");

    function set(newRows) {
      rows = Array.isArray(newRows) ? newRows.slice() : [];
      return render();
    }

    render();
    return {
      node: node, list: list, bar: bar, count: count, prev: prev, next: next,
      toggle: toggle, set: set, press: press, state: state, render: render
    };
  }

  return {
    LIST_ROWS: LIST_ROWS, TEXT: TEXT, ROW_PX: ROW_PX, PAGER_PX: PAGER_PX, CLS: CLS,
    page: page, wrap: wrap, rowRule: rowRule, build: build
  };
}));
