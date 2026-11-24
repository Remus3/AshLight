/* AshLight dashboard panel: the shared page plumbing of the cards, moved
   out of web/app.js by TEST-WEB-PANELS-C2 (finding F-135; research 0047
   R4 (c)): el, linkOut and setLine, the card pages of the grid cards
   (PLAY-TD-19C-BUILD-GRID) and the pagers of the Build card's rows
   (textPager, linkPager, sizeClass), plus the "build" entry that wires the
   Build and items cards' pages and their first empty paint.

   The blocks moved verbatim. These helpers are what the other panels
   share, so this file adds them to window.ALApp.host when it loads
   (before web/app.js, which merges its own members into the same
   object); a panel reads them on its first paint or wire, as before. What
   the helpers use of the page ($) is read from the host when they run.

   No clipboard, no timer, no request, no live region.

   UMD like web/fmt.js: CommonJS for node --test (app/test/panels.test.js)
   exports {name, order, panel, parts}; in the page the file adds
   parts().host to the host and registers itself with window.ALApp (web/registry.js) as
   "build", order 10: the name and order app.js gave this entry before the
   move, so the wire order of today's page is kept. The core links this
   file at the panels marker of index.html (TEST-WEB-ASSEMBLE). */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    var getHost = function () { return root.ALApp.host; };
    var host = root.ALApp.host = root.ALApp.host || {};
    var parts = api.parts(getHost);
    Object.keys(parts.host).forEach(function (k) { host[k] = parts.host[k]; });
    root.ALApp.register(api.panel(getHost, parts));
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var NAME = "build";
  var ORDER = 10; // app.js gave "build" 10 before the move

  /* The helpers, each reading the page's $ from the host when it runs. */
  function parts(getHost) {
    function $(id) {
      var host = getHost();
      if (!host || typeof host.$ !== "function") {
        throw new TypeError("build: no page host (web/app.js sets ALApp.host)");
      }
      return host.$(id);
    }

    function el(tag, cls, text) {
      var e = document.createElement(tag);
      if (cls) { e.className = cls; }
      if (text !== undefined && text !== null) { e.textContent = text; }
      return e;
    }

    function linkOut(l, name) {
      var a = el("a", "out", l.label);
      a.href = l.href;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      // DATA-PRICE-NINJA-LINK: a link to a category page names itself (aria)
      a.setAttribute("aria-label", l.aria || name + " on " + l.label + " (opens in a new tab)");
      return a;
    }

    /* ---- PLAY-TD-19C-BUILD-GRID: card pages (plan 03 section 4). A grid
       card (.grid-card) shows one .card-page at a time: its home page, or
       the page a button with data-card-open names. The Back button in the
       card head returns home and gives focus back to the button that opened
       the page. A page changes only on a press, or when the card's home
       changes (a build loads or goes); then a focus inside the page that is
       hidden moves to the card's heading, never out of the card. */
    function cardHomeName(box) { return box.getAttribute("data-home") || "main"; }

    function cardShown(box) { return box.getAttribute("data-shown") || cardHomeName(box); }

    function cardHeading(box) { return box.querySelector("h2"); }

    function showCardPage(box, name, focusTo) {
      var home = cardHomeName(box);
      var active = document.activeElement;
      var lost = false;
      var cur = null;
      Array.prototype.forEach.call(box.querySelectorAll(".card-page"), function (pg) {
        var on = pg.getAttribute("data-page") === name;
        if (!on && !pg.hidden && pg.contains(active)) { lost = true; }
        pg.hidden = !on;
        if (on) { cur = pg; }
      });
      box.setAttribute("data-shown", name);
      var label = name === home || !cur ? "" : cur.getAttribute("data-label") || "";
      setLine(box.querySelector("[data-card-sub]"), label);
      var back = box.querySelector("[data-card-back]");
      back.hidden = name === home;
      back.setAttribute("aria-label", "Back to the first page of " + cardHeading(box).textContent);
      if (focusTo && !focusTo.hidden) {
        focusTo.focus();
      } else if (lost) {
        cardHeading(box).focus();
      }
    }

    function cardHome(box) { showCardPage(box, cardHomeName(box), null); }

    /* a new home page: the card follows only when it showed its old home */
    function setCardHome(box, name) {
      var atHome = cardShown(box) === cardHomeName(box);
      box.setAttribute("data-home", name);
      if (atHome) { cardHome(box); }
    }

    var cardOpener = {};

    function wireCard(box) {
      // the heading takes focus when a page it held goes (server/al/diag.py
      // names the Prices heading by its exact markup, so the page sets this)
      if (!cardHeading(box).hasAttribute("tabindex")) { cardHeading(box).setAttribute("tabindex", "-1"); }
      Array.prototype.forEach.call(box.querySelectorAll("[data-card-open]"), function (b) {
        b.addEventListener("click", function () {
          cardOpener[box.id] = b;
          showCardPage(box, b.getAttribute("data-card-open"), box.querySelector("[data-card-back]"));
        });
      });
      box.querySelector("[data-card-back]").addEventListener("click", function () {
        var o = cardOpener[box.id];
        showCardPage(box, cardHomeName(box), o && !o.hidden && !o.disabled ? o : cardHeading(box));
      });
      cardHome(box);
    }

    /* the pagers of the Build card's rows: web/pager.js through web/search.js
       (textPager; app.js reaches the regions and their helpers only through
       the three hook calls, app/test/regions.test.js), and rowPager for rows
       with a link. They page again when a resize changes the size class. */
    var buildPagers = {};

    function sizeClass() {
      return window.ALSearch ? window.ALSearch.sizeClass(document) : "full";
    }

    function textPager(slotId, label, rows) {
      var pg = buildPagers[slotId];
      if (!pg) {
        pg = window.ALSearch.textPager(document, { rows: rows, label: label, sizeClass: sizeClass });
        buildPagers[slotId] = pg;
        $(slotId).replaceChildren(pg.node);
        return pg;
      }
      pg.set(rows);
      return pg;
    }

    /* opts.full(row), when given, is the row's whole text (title and the
       Full text page) while opts.text(row) stays the one-line list row
       (PLAY-TD-19E-ITEM-TEXT: a gear row's raw item text) */
    function linkPager(slotId, label, size, opts) {
      var pg = buildPagers[slotId];
      if (!pg) {
        var full = typeof opts.full === "function" ? opts.full : null;
        var po = {
          label: label, size: size, sizeClass: sizeClass, text: full || opts.text,
          parts: full ? function (r) { return [{ text: opts.text(r) }]; } : undefined,
          rowClass: opts.rowClass,
          controls: function (d, r) { return r.link ? [linkOut(r.link, r.linkName)] : []; }
        };
        // ITEM-INFO-UI: opts.parts(row), when given, builds the list row
        // (an item name button and the rest of the line)
        if (typeof opts.parts === "function") { po.parts = opts.parts; }
        pg = window.ALSearch.rowPager(document, po);
        buildPagers[slotId] = pg;
        $(slotId).replaceChildren(pg.node);
      }
      pg.set(opts.rows);
      return pg;
    }

    /* a resize: every pager whose size class changed pages again */
    function relayoutPagers() {
      if (window.ALSearch) { window.ALSearch.relayout(); }
    }

    function setLine(node, text) {
      node.textContent = text;
      if (text) { node.setAttribute("title", text); } else { node.removeAttribute("title"); }
    }

    return {
      host: {
        el: el, linkOut: linkOut, setLine: setLine, linkPager: linkPager, textPager: textPager,
        cardShown: cardShown, cardHome: cardHome, setCardHome: setCardHome,
        showCardPage: showCardPage, cardHeading: cardHeading, cardOpener: cardOpener,
        sizeClass: sizeClass
      },
      // the "build" entry's own steps
      wireCard: wireCard, relayoutPagers: relayoutPagers
    };
  }

  /* The registry entry. TEST-WEB-PANELS-A: the loaded build's paint and
     listeners are the "loaded-build" panel (web/panels/build.js, order 9);
     this entry keeps the Build and items cards' page plumbing and their
     first empty paint. getHost is read on the first wire, when web/app.js
     has run (it is the last script); p is the parts() the host holds, so
     the entry and the host share one cardOpener and one set of pagers. */
  function panel(getHost, p) {
    return {
      name: NAME,
      order: ORDER,
      wire: function () {
        var host = getHost();
        if (!host || typeof host.$ !== "function") {
          throw new TypeError("build: no page host (web/app.js sets ALApp.host)");
        }
        var pp = p || parts(getHost);
        ["buildbox", "healthbox", "searchbox", "evalbox", "pricesbox", "weightsbox"].forEach(function (id) {
          pp.wireCard(host.$(id));
        });
        window.addEventListener("resize", pp.relayoutPagers);
        if (window.ALSearch) { window.ALSearch.paint(document, null, navigator); }
        if (window.ALHealth) { window.ALHealth.paint(document, null, navigator); }
      }
    };
  }

  return { name: NAME, order: ORDER, panel: panel, parts: parts };
}));
