/* AshLight dashboard. Vanilla JS, no framework, no CDN, no inline script.
   The per-start token arrives in the URL fragment (#token=...), is kept in
   sessionStorage and sent as X-AL-Token (fetch) or ?token= (EventSource,
   which cannot set headers). Every text from the log goes in via
   textContent, never innerHTML. */
(function () {
  "use strict";

  var D = window.ALDash; // web/status.js: pure view helpers
  var F = window.ALFmt; // web/fmt.js: pad, duration, clock
  var A = window.ALApp; // web/registry.js: the panel loops of render, tick, start
  var KEY = "al.token";
  var token = readToken();
  var snap = null;
  var offset = 0; // client clock minus server clock, seconds
  var renderedVersion = -1;
  // UTIL-MULTICHAR: the character the player picked ("" = the one playing)
  var charPick = "";
  var es = null;
  var ticker = null;
  var linkLive = false; // the state feed is live right now
  var everLive = false; // ... and was live at least once on this page
  var linkEvent = null; // the feed's last event, for the one bar word

  function $(id) { return document.getElementById(id); }

  function readToken() {
    var t = "";
    var m = /(?:^|[#&])token=([0-9a-fA-F]+)/.exec(location.hash || "");
    if (m) {
      t = m[1];
      try { sessionStorage.setItem(KEY, t); } catch (e) { /* storage off */ }
      try { history.replaceState(null, "", location.pathname); } catch (e) { /* ignore */ }
    } else {
      try { t = sessionStorage.getItem(KEY) || ""; } catch (e) { t = ""; }
    }
    return t;
  }

  var clock = F.clock;

  /* UX-A11Y: write only a changed string. The pills sit in polite live
     regions and are re-set on every state push; rewriting the same words
     would let a screen reader say them again each time. */
  function setText(node, text) {
    if (node.textContent !== text) { node.textContent = text; }
  }

  function setPill(el, state, glyph, word) {
    if (el.getAttribute("data-state") !== state) { el.setAttribute("data-state", state); }
    setText(el.querySelector(".glyph"), glyph);
    setText(el.querySelector(".word"), word);
  }

  function serverNow() { return Date.now() / 1000 - offset; }

  /* While the feed is down the timers stop, so a stale page never looks
     like it is still counting (UI-REVIEW-2). TEST-WEB-REGISTRY: the
     panels' ticks run in their order (web/registry.js); one that throws no
     longer stops the timers after it. */
  function tick() {
    if (!snap || document.hidden || !linkLive) { return; }
    var now = serverNow();
    // TEST-LIVE-EXIT: an idle log stops the zone and act clocks at its
    // last line (the game may be closed; decision 0029).
    var until = D.clockUntil(snap.tailer, now);
    A.tick(snap, now, until);
    // TD-09 region hook: every registered Play region's tick (web/regions.js)
    if (window.ALRegions) { window.ALRegions.tick(document, snap, now); }
  }

  /* UX-PERF: most state pushes (timers, trades, HUD fields) leave the
     recent list as it was; rebuild its rows only when the list changed.
     PLAY-TD-20B-RUN-CARDS: Run > Recent is a grid card, the twin of Play's
     feed: every recent event newest first in one-line rows that page at 8
     (6 compact) through web/pager.js (ALSearch.rowPager; the whole text in
     title and on the Full text page). A row is the local time, a muted tag
     (From / To for whispers, no edge; Death in the bad state colour) and
     the core's sentence. The chips All, Deaths and Trades (aria-pressed)
     filter the rows; a chip press starts the list at its first page. */
  var renderedEvents = "";
  var evRows = [];
  var evFilter = "all";
  var evPager = null;
  var EV_SIZE = { full: 8, compact: 6 };
  var EV_NONE = { death: "No deaths among your recent events.",
    trade: "No trades among your recent events." };

  function evTag(kind) { return kind.charAt(0).toUpperCase() + kind.slice(1); }

  function evShows(kind, filter) {
    return filter === "all" || kind === filter;
  }

  function evChips() {
    return Array.prototype.slice.call(document.querySelectorAll("[data-ev-filter]"));
  }

  function evStart() {
    var slot = $("events");
    if (!slot || !window.ALSearch) { return null; }
    var S = window.ALSearch;
    evPager = S.rowPager(document, {
      label: "recent events",
      size: EV_SIZE,
      sizeClass: function () { return S.sizeClass(document); },
      text: function (r) { return r.text; },
      parts: function (r) {
        return [{ text: r.time ? r.time + " " : "", cls: "ev-time" },
          { text: r.tag + " ", cls: "ev-tag" }, { text: r.body }];
      },
      rowClass: function (r) { return "ev-" + r.kind; }
    });
    slot.replaceChildren(evPager.node);
    evChips().forEach(function (b) {
      b.addEventListener("click", function () {
        evFilter = b.getAttribute("data-ev-filter") || "all";
        evChips().forEach(function (c) {
          c.setAttribute("aria-pressed", c === b ? "true" : "false");
        });
        renderedEvents = "";
        renderEvents(evRows);
        while (evPager.state().hasPrev) { evPager.press("prev"); }
      });
    });
    return evPager;
  }

  function renderEvents(rows) {
    evRows = rows;
    var key = evFilter + "#" + D.eventsKey(rows);
    if (key === renderedEvents) { return; }
    if (!evPager && !evStart()) { return; }
    renderedEvents = key;
    var shown = [];
    for (var i = rows.length - 1; i >= 0; i--) {
      var row = rows[i];
      var k = D.kindOf(row);
      if (!evShows(k, evFilter)) { continue; }
      var t = clock(row.at);
      var tag = evTag(k);
      shown.push({ kind: k, time: t, tag: tag, body: row.text,
        text: (t ? t + " " : "") + tag + ": " + row.text });
    }
    $("events").hidden = shown.length === 0;
    $("events-empty").hidden = rows.length > 0;
    var none = $("events-none");
    setText(none, rows.length && !shown.length ? EV_NONE[evFilter] || "" : "");
    none.hidden = !none.textContent;
    evPager.set(shown);
  }

  /* DESKTOP-CLIENT (decision 0041): inside the desktop client the page
     gets one action, window.alClient.restartOverlay (app/client/preload.js);
     in a browser there is none and the button stays hidden. */
  var restartSaid = false; // the restart note shows until the next state push
  function wireRestartOverlay() {
    var c = window.alClient;
    if (!c || typeof c.restartOverlay !== "function") { return; }
    $("restart-overlay-row").hidden = false;
    $("restart-overlay").addEventListener("click", function () {
      c.restartOverlay();
      restartSaid = true;
      setText($("restart-overlay-said"), snap && snap.game_idle
        ? "Restarting the overlay. It stays hidden while the game looks closed."
        : "Restarting the overlay.");
    });
  }

  /* ---- TC-VIEW: the loaded build lives in web/panels/build.js
     (TEST-WEB-PANELS-A). This file keeps what it shares with the other
     cards (el, linkOut, the card pages, the pagers, setLine) and hands it
     over through A.host (set before the panel registrations below). */
  var T = window.ALTc; // web/tc.js: pure view helpers

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
    a.setAttribute("aria-label", name + " on " + l.label + " (opens in a new tab)");
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
      pg = window.ALSearch.rowPager(document, {
        label: label, size: size, sizeClass: sizeClass, text: full || opts.text,
        parts: full ? function (r) { return [{ text: opts.text(r) }]; } : undefined,
        rowClass: opts.rowClass,
        controls: function (d, r) { return r.link ? [linkOut(r.link, r.linkName)] : []; }
      });
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

  /* UTIL-FILTER (decision 0031): on the player's click, fetch the snippet
     and hand it to the browser as a download; the player picks where it
     goes. AshLight writes no file itself. */
  function downloadFilter() {
    var said = $("filter-said");
    /* UX-B5-CARDS: no live region (the page keeps its 12); the focused
       button's name carries the answer; most screen readers read it on
       this click (best effort, audit 0004 U22) */
    var btn = $("filter-download");
    var tell = function (text) {
      setLine(said, text);
      setLine($("filter-merge-said"), "");  /* one outcome line for the page */
      btn.setAttribute("aria-label", text ? "Download ashlight.filter (" + text + ")"
        : "Download ashlight.filter");
    };
    tell("");
    fetch("/api/filter", { headers: { "X-AL-Token": token }, cache: "no-store" })
      .then(function (r) {
        if (!r.ok) {
          tell("Can't make the filter. Try again.");
          return null;
        }
        return r.text();
      }).then(function (text) {
        if (text === null) { return; }
        var url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
        var a = document.createElement("a");
        a.href = url;
        a.download = "ashlight.filter";
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
        tell(text.indexOf("\nShow\n") >= 0
          ? "Sent to your browser's downloads. Move it to the game's filter folder."
          : "Sent to your browser's downloads, but your build has no gear bases, so it " +
            "highlights nothing yet.");
      }).catch(function () {
        tell("Can't reach AshLight - is it running?");
      });
  }

  /* UTIL-FILTER-MERGE (decision 0033): picking a file is the player's act;
     the merged copy goes to the browser's downloads. No live region (the
     page keeps its 12): as for downloadFilter, the focused input's name
     carries the answer (best effort, audit 0004 U22). */
  function mergeFilter() {
    var input = $("filter-merge-file");
    var file = input.files && input.files[0];
    window.ALFilterMerge.run(file, {
      fetch: function (url, opts) { return fetch(url, opts); },
      token: token,
      tell: function (text) {
        setLine($("filter-merge-said"), text);
        if (text) { setLine($("filter-said"), ""); }
        if (text) {
          input.setAttribute("aria-label", "Your loot filter file (" + text + ")");
        } else {
          input.removeAttribute("aria-label");
        }
      },
      save: function (blob, name) {
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = name;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
      }
    }).then(function () { input.value = ""; });  /* the same file can be picked again */
  }

  /* ---- TC-EVAL-UI: the last item check (from the hotkey press). */
  // PLAY-LEGACY-OUT-2: a new check showing Play is the news hook of
  // web/regions.js now (UI-GLANCE ZERO-CLICK); this only fills the card
  var evalShown = null;

  /* PLAY-TD-19D-ITEMS-GRID: the Last item card's rows, one line each,
     paged with a Full text twin: the check's own rows, then the price
     rows (web/app.js renderPrice), then price and points and the upgrade
     search (UX-NEWEST N2: the price words sit together). */
  var EVAL_ROWS = { full: 6, compact: 4 };
  var evalRows = { check: [], price: [], after: [] };

  function paintEvalRows() {
    linkPager("eval-rows", "the item check", EVAL_ROWS, {
      rows: evalRows.check.concat(evalRows.price, evalRows.after),
      text: function (r) { return r.text; }
    });
  }

  function textRow(s) { return { text: s }; }

  function renderEval(ev) {
    var key = ev ? ev.id : null;
    if (key === evalShown) { return; }
    evalShown = key;
    var v = T.evalView(ev, clock);
    $("eval-empty").hidden = !!v;
    $("eval-body").hidden = !v;
    var check = [];
    if (v) {
      var w = $("eval-word");
      w.textContent = v.word;
      w.setAttribute("data-verdict", v.verdict);
      setLine($("eval-item"), v.item);
      $("eval-sentence").textContent = v.sentence;
      $("eval-calc").textContent = v.calc;
      $("eval-calc").hidden = !v.calc;
      if (v.sentence) { check.push(textRow(v.sentence)); }
      if (v.calc) { check.push(textRow(v.calc)); }
      v.notes.forEach(function (n) { check.push(textRow(n)); });
      if (v.rewards) { check.push(textRow(v.rewards)); }
      v.comparisons.forEach(function (c) {
        var slot = c.slot || "Slot";
        // the headline already says the best slot's sentence and calc line;
        // MATH-COMPARE: the other slot's own sentence and Path of Building line
        if (c.slot !== ev.slot && c.sentence) { check.push(textRow(slot + ": " + c.sentence)); }
        if (c.slot !== ev.slot && c.calc) { check.push(textRow(slot + ": " + c.calc)); }
        if (c.stats && c.stats.length) {
          // CL-3: the points in brackets, never run on from the mod text
          c.stats.forEach(function (s) { check.push(textRow(T.statRowText(slot, s))); });
        } else {
          check.push(textRow(slot + ": no stat differences."));
        }
      });
      if (v.unweighted) { check.push(textRow(v.unweighted)); }
      // MATH-POTENTIAL-UI: the core's worst / now / best roll scores
      if (v.rolls) { check.push(textRow(v.rolls)); }
    }
    // TC-CARD-PARTS-WEB: the card parts' notes, read with the verdict
    var notes = document.createDocumentFragment();
    (v ? v.notes : []).forEach(function (n) { notes.appendChild(el("li", "", n)); });
    $("eval-notes").replaceChildren(notes);
    $("eval-notes").hidden = !(v && v.notes.length);
    // UTIL-WAYSTONE-REWARD: the core's reward totals for a waystone
    $("eval-rewards").hidden = !(v && v.rewards);
    $("eval-rewards").textContent = v ? v.rewards : "";
    setLine($("eval-when"), v ? v.when : "");
    var after = [];
    // MATH-VALUE-UI: the item's Note price against its points, from the
    // rates the core already has; nothing when the item has no note price
    var val = v && ev ? P.valueView(ev.value) : null;
    // UX-REGRESSION-SWEEP: with no verdict (no build) there is no points
    // figure to set against the price; the asking price still shows
    if (val && !ev.ok) { val = Object.assign({}, val, { per: "" }); }
    if (val) {
      ["sentence", "per", "stale", "credit"].forEach(function (f) {
        if (val[f]) { after.push(textRow(val[f])); }
      });
    }
    // TC-UPGRADE (decision 0017): the player's click opens the upgrade
    // search in their browser; AshLight never opens or fetches it
    var up = v && ev ? P.upgradeView(ev.upgrade) : null;
    if (up) {
      after.push({ text: up.sentence, link: { href: up.href, label: "Trade site" },
        linkName: up.text.replace(/^Search the official trade site for /, "") });
    }
    evalRows.check = check;
    evalRows.after = after;
    paintEvalRows();
  }

  /* ---- DATA-NINJA-UI / PRICE-1-UI (decision 0016): the one web-data
     opt-in, poe.ninja currency values and the last price check. Rates are
     polled from the local core every few minutes (the core itself asks
     poe.ninja at most once an hour); no refresh button. */
  var P = window.ALPrices; // web/prices.js: pure view helpers
  var RATES_POLL_MS = 5 * 60 * 1000;
  var ratesDoc = null;
  var ratesAgain = null;
  var priceShown = null;

  /* TEST-WEB-PANELS-B: the web data switch, the contact field and the
     league picker live in web/panels/webdata.js. On its wire that panel
     fills this link with fill(doc), saved(doc) and state() (on, busy, doc),
     so the rates below follow the switch without owning it. */
  var webLink = {};

  function webState() {
    return typeof webLink.state === "function" ? webLink.state() : { on: false, busy: false, doc: null };
  }

  function webDataSaved(doc) {
    if (typeof webLink.saved === "function") { webLink.saved(doc); }
  }

  /* PLAY-TD-19D-ITEMS-GRID (F-056): the Prices card is one list that
     pages: your checked items first (web/pricewatch.js rows), then the
     currency values (top 6), then the week's movers (3) worded as a
     trend. All of it is the cached poe.ninja book; nothing new is asked. */
  var PRICE_ROWS = { full: 7, compact: 4 };
  var rateRows = [];
  var trendRows = [];

  function paintPricesList() {
    var watch = window.ALPriceWatch ? window.ALPriceWatch.rows(snap ? snap.price_watch : null) : [];
    linkPager("prices-list", "prices", PRICE_ROWS, {
      rows: watch.concat(rateRows, trendRows).map(textRow),
      text: function (r) { return r.text; }
    });
  }

  function renderRates() {
    var v = P.ratesView(ratesDoc, webState().doc);
    setPill($("rates-pill"), v.pill.state, v.pill.glyph, v.pill.word);
    // PLAY-TD-21A-SETTINGS-RAIL: the same state beside the web data switch
    setPill($("book-state"), v.pill.state, v.pill.glyph, v.pill.word);
    $("rates-credit").textContent = v.credit;
    $("rates-unit").textContent = v.rows.length
      ? ", in " + v.primary + (v.leagueLine ? ", " + v.leagueLine : "") : "";
    $("rates-credit-line").setAttribute("title", $("rates-credit-line").textContent);
    $("rates-attrib").textContent = v.attribution;
    rateRows = v.rows.map(function (r) {
      return r.name + ": " + r.value + (r.per ? " (" + r.per + ")" : "");
    });
    renderMovers();
  }

  /* UTIL-MOVERS: the week's biggest moves from the same /api/rates doc */
  function renderMovers() {
    trendRows = P.trendRows(ratesDoc);
    paintPricesList();
  }

  function loadRates() {
    if (ratesAgain) { clearTimeout(ratesAgain); ratesAgain = null; }
    api("GET", "/api/rates").then(function (doc) {
      ratesDoc = doc;
      var web = webState();
      if (typeof doc.web_data === "boolean" && !web.busy && doc.web_data !== web.on &&
          typeof webLink.fill === "function") {
        webLink.fill({ web_data: doc.web_data });
      }
      renderRates();
      renderPrice(snap ? snap.price : null, true);
      // a refresh the core just started finishes in a few seconds
      if (doc.refreshing) { ratesAgain = setTimeout(loadRates, 3000); }
    }).catch(function () {
      setPill($("rates-pill"), "failed", "[x]", "can't load currency values - is AshLight running?");
      setPill($("book-state"), "failed", "[x]", "can't load currency values - is AshLight running?");
    });
  }

  function pollRates() {
    if (!document.hidden && linkLive) { loadRates(); }
  }

  function renderPrice(pr, force) {
    var v = P.priceView(pr, ratesDoc, clock);
    var key = v ? v.key : "";
    if (key === priceShown && !force) { return; }
    priceShown = key;
    $("price-body").hidden = !v;
    var rows = [];
    if (v) {
      setPill($("price-badge"), v.badge.state, v.badge.glyph, v.badge.word);
      $("price-sentence").textContent = v.sentence;
      if (v.sentence) { rows.push(textRow(v.sentence)); }
      // PRICE-TRADE-LINK (decision 0017): the player's click opens the trade
      // search in their browser; AshLight never opens or fetches it
      if (v.link) {
        rows.push({ text: v.link.text, link: { href: v.link.href, label: "Trade site" },
          linkName: v.item || "this item" });
      }
      v.rows.forEach(function (r) {
        rows.push(textRow(r.text + (r.about ? " (" + r.about + ")" : "")));
      });
    }
    evalRows.price = rows;
    paintEvalRows();
  }

  /* ---- TEST-WEB-REGISTRY (F-135): the dashboard panels. Each paint, tick
     and wire that render(), tick() and start() called in one sequence is
     one registered entry; the explicit order keeps today's paint order and
     so the order of the live-region announcements. render() calls
     paint(s, c) (the state push and the picked character's view), tick()
     calls tick(snap, now, until), start() calls wire(). A throwing panel
     is caught and said once on the console; the panels after it still
     run. A new card registers its own entry; no shared function changes. */
  /* TEST-WEB-PANELS-A: what a panel file in web/panels/ reaches of this
     page. Set here, before start(), and read by a panel on its first
     paint or wire (web/panels/build.js). The snapshot is a getter: snap
     changes on every push.
     TEST-WEB-PANELS-B: the settings-side panels (web/panels/layout.js,
     weights.js, webdata.js, gfx.js) also get sizeClass, the rates helpers
     (getRatesDoc, renderRates, renderPrice, loadRates), the web data link
     (webLink, above) and onConnect(fn): a panel's first read, run by
     connect() in wire order, only while the page has its token. */
  A.host = {
    $: $, api: api, token: token, getSnap: function () { return snap; },
    serverNow: serverNow, el: el, linkOut: linkOut, setLine: setLine,
    linkPager: linkPager, textPager: textPager, cardShown: cardShown,
    cardHome: cardHome, setCardHome: setCardHome, showCardPage: showCardPage,
    cardHeading: cardHeading, cardOpener: cardOpener, webDataSaved: webDataSaved,
    sizeClass: sizeClass, getRatesDoc: function () { return ratesDoc; },
    renderRates: renderRates, renderPrice: renderPrice, loadRates: loadRates,
    webLink: webLink, onConnect: onConnect
  };
  A.register({
    name: "build",
    order: 10,
    // TEST-WEB-PANELS-A: the loaded build's paint and listeners are the
    // "loaded-build" panel (web/panels/build.js, order 9); this entry keeps
    // the Build and items cards' page plumbing and their first empty paint
    wire: function () {
      ["buildbox", "healthbox", "searchbox", "evalbox", "pricesbox", "weightsbox"].forEach(function (id) {
        wireCard($(id));
      });
      window.addEventListener("resize", relayoutPagers);
      if (window.ALSearch) { window.ALSearch.paint(document, null, navigator); }
      if (window.ALHealth) { window.ALHealth.paint(document, null, navigator); }
    }
  });
  A.register({
    name: "eval",
    order: 20,
    paint: function (s) { renderEval(s.eval || null); }
  });
  A.register({
    name: "price",
    order: 40,
    paint: function (s) { renderPrice(s.price || null, false); }
  });
  A.register({
    name: "chars",
    order: 50,
    paint: function (s) {
      if (window.ALChars) { window.ALChars.paint(document, s, charPick); }
    },
    wire: function () {
      if (window.ALChars) {
        window.ALChars.wire(document, function (name) {
          charPick = name;
          if (snap) { renderedVersion = -1; render(snap); }
        });
      }
    }
  });
  A.register({
    name: "pace",
    order: 60,
    // UTIL-PACE: the core's pace sentence in the Act times card, shown once
    // there is one (the picked character's, UTIL-MULTICHAR)
    paint: function (s, c) {
      var paceText = (c.pace && c.pace.text) || "";
      setText($("pace"), paceText);
      $("pace").hidden = !paceText;
    }
  });
  A.register({
    name: "consent",
    order: 70,
    // the opt-in is region C's setup card (web/setupcard.js); the opt-out,
    // the log path and the reading state are in Settings, Reading and web
    // data (PLAY-TD-21A-SETTINGS-RAIL), where the bar status word leads
    paint: function (s) {
      var tl = s.tailer || {};
      var rv = readingView(tl);
      setText($("reading-state"), rv.state);
      setText($("reading-path"), rv.path);
      if ($("reading-path").getAttribute("title") !== rv.path) {
        $("reading-path").setAttribute("title", rv.path);
      }
      $("reading-path").hidden = !rv.path;
      if (window.ALLogPath) { window.ALLogPath.paint(document, s); } // SEC-LOG-PATH-FIELD
      $("consent-no").hidden = !rv.stop;
      $("events-empty").textContent = D.emptyText(!!tl.consented);
      paintLedger(tl);
    },
    wire: function () {
      $("consent-no").addEventListener("click", stopReading);
      if (window.ALLogPath) { window.ALLogPath.wire(document, api, render); }
      $("ledger-allow").addEventListener("click", toggleLedger);
    }
  });
  A.register({
    name: "reading",
    order: 80,
    paint: function () { showReading(); }
  });
  A.register({
    name: "events",
    order: 90,
    paint: function (s) { renderEvents(s.recent_events || []); }
  });
  A.register({
    name: "acts",
    order: 110,
    paint: function (s, c) {
      if (window.ALActs) { window.ALActs.paint(document, c.acts || null, D.clockUntil(s.tailer, serverNow()), true); }
    },
    // HUD-ACT: the open act split counts up with the zone timer.
    tick: function (s, now, until) {
      if (window.ALActs) { window.ALActs.paint(document, s.acts, until, false); }
    }
  });
  A.register({
    name: "runs",
    order: 120,
    paint: function (s) {
      if (window.ALRuns) { window.ALRuns.paint(document, s, serverNow(), true); }
    },
    // UTIL-MAPS: the open map's time counts up while the player is in it.
    tick: function (s, now) {
      if (window.ALRuns) { window.ALRuns.paint(document, s, now, false); }
    }
  });
  A.register({
    name: "summary",
    order: 130,
    // UTIL-SESSION-SUMMARY: the last play stretch's card, by itself
    paint: function (s) {
      if (window.ALSummary) { window.ALSummary.paint(document, s); }
    }
  });
  A.register({
    name: "zonenote",
    order: 140,
    // PLAY-LEGACY-OUT-2: the zone note is region C's (town mode) and the old
    // Zone tip box is gone, so this panel paints nothing. It stays only
    // while app/test/registry.test.js pins today's panel list; the package
    // that widens to that test deletes this entry.
    paint: function () {}
  });
  A.register({
    name: "history",
    order: 150,
    // UTIL-UNDERLEVEL / UTIL-RUN-HISTORY: the core's sentences, by themselves
    paint: function (s, c) {
      if (window.ALHistory) { window.ALHistory.paint(document, c); }
    },
    // UTIL-RUN-HISTORY: the player's clicks
    wire: function () {
      if (window.ALHistory) { window.ALHistory.wire(document, api); }
    }
  });
  A.register({
    name: "pricewatch",
    order: 160,
    // UTIL-PRICE-WATCH: moved prices of the items the player checked, on
    // top of the Prices card list (PLAY-TD-19D-ITEMS-GRID)
    paint: function (s) {
      if (window.ALPriceWatch && window.ALPriceWatch.paint(document, s)) { paintPricesList(); }
    },
    wire: function () {
      if (window.ALPriceWatch) { window.ALPriceWatch.wire(document, api); }
    }
  });
  A.register({
    name: "hints",
    order: 170,
    // NEWBIE-HINTS: the tip itself is a region N notice (PLAY-LEGACY-OUT-2);
    // this keeps only the Settings click "Show new-character tips again".
    // The empty tick stays only while app/test/registry.test.js pins the
    // tick order; the package that widens to that test deletes it.
    tick: function () {},
    wire: function () {
      if (window.ALHints) { window.ALHints.wire(document, api); }
    }
  });
  A.register({
    name: "checks",
    order: 180,
    // DIAG-SELF / LANG-GUARD: the core's checks and language notice
    paint: function (s) {
      if (window.ALChecks) { window.ALChecks.paint(document, s); }
    },
    wire: function () {
      if (window.ALChecks) {
        var store = null;
        try { store = window.localStorage; } catch (e) { store = null; }
        // RUN-REPORT-ROUTE: api builds the report on the click (GET /api/report)
        window.ALChecks.wire(document, function () { return snap; }, navigator, store, api);
      }
    }
  });
  A.register({
    name: "zoneguide",
    order: 190,
    paint: function (s) {
      if (window.ALZoneGuide) { window.ALZoneGuide.paint(document, s); }
    }
  });
  // the tools and settings that only wire the player's clicks.
  // TEST-WEB-PANELS-B: "layout" (200), "weights" (220), "gfx" (230) and
  // "webdata" (250) register from their web/panels/ files with the same
  // names and orders, so the page keeps today's wire order.
  A.register({
    name: "filter",
    order: 210,
    wire: function () {
      $("filter-download").addEventListener("click", downloadFilter);
      $("filter-merge-file").addEventListener("change", mergeFilter);
    }
  });
  A.register({
    name: "restart-overlay",
    order: 240,
    wire: function () { wireRestartOverlay(); }
  });
  A.register({
    name: "settingsio",
    order: 260,
    // UX-SETTINGS-IO: the player's clicks
    wire: function () {
      // OVL-KEYS-WEB: the two change-key fields, saved on change (POST /api/hotkeys)
      if (window.ALHotkeys) {
        window.ALHotkeys.wire(document, { fetch: function (url, opts) { return fetch(url, opts); },
          token: token });
      }
      // OVL-PARTS-WEB: the 'Overlay shows' group, saved on change (POST
      // /api/overlay-layout); its first read runs on connect, beside the layout's
      if (window.ALOverlayParts) {
        window.ALOverlayParts.wire(document, api);
        onConnect(function () { window.ALOverlayParts.load(document, api); });
      }
      if (!window.ALSettingsIO) { return; }
      window.ALSettingsIO.wire(document, {
        fetch: function (url, opts) { return fetch(url, opts); },
        token: token,
        save: function (blob, name) {
          var url = URL.createObjectURL(blob);
          var a = document.createElement("a");
          a.href = url;
          a.download = name;
          document.body.appendChild(a);
          a.click();
          a.remove();
          setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
        }
      });
    }
  });

  /* UTIL-MULTICHAR: level, pace, deaths, act times and run history of the
     picked character (the one playing unless the player picks); the
     playing one's numbers when the view cannot be made. */
  function charView(s) {
    if (!window.ALChars) { return s; }
    try { return window.ALChars.view(s, charPick); } catch (e) { return s; }
  }

  function render(s) {
    snap = s;
    // MERGE-SEAMS F5: the restart-overlay note clears on the next state push
    if (restartSaid) { restartSaid = false; setText($("restart-overlay-said"), ""); }
    // decision 0029 amendment: say why the overlay is hidden (no live region)
    $("overlay-idle-note").hidden = s.game_idle !== true;
    offset = Date.now() / 1000 - s.now;
    if (s.version === renderedVersion) { tick(); return; }
    renderedVersion = s.version;
    // OVL-KEYS-WEB: every named key is the bound one; the change fields and
    // the Play line while the overlay is off (web/hotkeys.js)
    if (window.ALHotkeys) { window.ALHotkeys.paint(document, s); }
    A.render(s, charView(s));
    // TD-09 region hook: every registered Play region paints after the panels
    if (window.ALRegions) { window.ALRegions.paint(document, s, serverNow()); }
    tick();
  }

  function showPill(id, p) { setPill($(id), p.state, p.glyph, p.word); }

  /* PLAY-TD-09C-BAR: the one bar status word, the worse of the
     Client.txt reading state and the feed state (MERGE-SEAMS F2) */
  function showReading() {
    showPill("reading", D.barStatus(snap ? snap.tailer : null, linkEvent, everLive));
  }

  function setLink(event) {
    linkEvent = event;
    linkLive = event === "open";
    if (linkLive) { everLive = true; }
    showReading();
  }

  function api(method, path, body) {
    var opts = { method: method, headers: { "X-AL-Token": token }, cache: "no-store" };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    return fetch(path, opts).then(function (r) {
      if (!r.ok) { throw new Error("HTTP " + r.status); }
      return r.json();
    });
  }

  /* "Stop reading Client.txt": the opt-out click. The failure line is not
     a live region; the button points at it (aria-describedby). */
  function stopReading() {
    var said = $("consent-said");
    said.textContent = "";
    api("POST", "/api/consent", { consent: false }).then(function (res) {
      render(res.state);
    }).catch(function (e) {
      said.textContent = "Your choice was not saved. Try again.";
      console.warn("consent failed: " + e.message);
    });
  }

  /* READING-VIEW:begin (app/test/rail.test.js runs this function alone;
     keep it self-contained ES5)
     PLAY-TD-21A-SETTINGS-RAIL: the Reading and web data section's first
     rows from the snapshot's tailer block: the reading state in plain
     words, the log file AshLight uses ("" for none) and whether "Stop
     reading Client.txt" shows (only while the player has allowed it). */
  function readingView(tl) {
    tl = tl || {};
    var path = typeof tl.path === "string" ? tl.path.trim() : "";
    var state;
    if (tl.consented !== true) {
      state = "AshLight is not reading Client.txt. The setup card on Play asks first.";
    } else if (tl.reading === true) {
      state = "AshLight is reading Client.txt.";
    } else {
      state = "Allowed, but AshLight is not reading Client.txt now. Checks says why.";
    }
    return { state: state, path: path ? "Log file: " + path : "", stop: tl.consented === true };
  }
  /* READING-VIEW:end */

  /* LEDGER-VIEW:begin (app/test/dashboard.test.js runs this function alone;
     keep it self-contained ES5)
     RUN-LEDGER-CONSENT (decision 0071): the log record's consent line from
     the snapshot's tailer block. Shown only while Client.txt is read; the
     record is on only when the core says ledger === true (the Client.txt
     opt-in alone never turns it on). `send` is what the button posts. */
  function ledgerView(tl) {
    tl = tl || {};
    var shown = tl.consented === true;
    var on = shown && tl.ledger === true;
    var what = " AshLight counts the kinds of log lines it reads and keeps " +
      "their shapes on this computer. Names, chat and item words are blanked " +
      "out. Nothing is sent.";
    if (on) {
      return { shown: true, on: true, send: false, button: "Stop the log record",
               text: "Log record: on." + what + " Stopping it deletes the file." };
    }
    return { shown: shown, on: false, send: true, button: "Allow the log record",
             text: "Log record: off. When on," + what };
  }
  /* LEDGER-VIEW:end */

  var ledgerSend = true;

  function paintLedger(tl) {
    var v = ledgerView(tl);
    ledgerSend = v.send;
    $("ledger-line").hidden = !v.shown;
    setText($("ledger-text"), v.text);
    setText($("ledger-allow"), v.button);
  }

  /* The log record's own Allow / Stop click (decision 0071): posts only the
     ledger flag; the failure line is not a live region. */
  function toggleLedger() {
    var said = $("ledger-said");
    said.textContent = "";
    api("POST", "/api/consent", { ledger: ledgerSend }).then(function (res) {
      render(res.state);
    }).catch(function (e) {
      said.textContent = "Your choice was not saved. Try again.";
      console.warn("ledger consent failed: " + e.message);
    });
  }

  /* BUILD-STAMP:begin (app/test/about.test.js runs this function alone and
     holds it to app/about.js versionLine; keep it self-contained ES5)
     RUN-BUILD-STAMP-UI (F-027, decision 0082 part 2): the version line
     from the core's build string '<x.y.z>[+<12 hex>][.dev]':
     "Version 0.1.0, build 0123456789ab", ", dev" while hot reload is on;
     "" for anything else. */
  function versionText(doc) {
    var raw = doc && (typeof doc.build === "string" ? doc.build : doc.version);
    if (typeof raw !== "string" || raw.length > 100) { return ""; }
    var plus = raw.indexOf("+");
    var ver = plus < 0 ? raw : raw.slice(0, plus);
    if (!/^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$/.test(ver)) { return ""; }
    var meta = plus < 0 ? [] : raw.slice(plus + 1).split(".");
    var commit = "";
    var dev = false;
    for (var i = 0; i < meta.length; i++) {
      if (meta[i] === "dev" && !dev) { dev = true; continue; }
      if (/^[0-9a-f]{12}$/.test(meta[i]) && !commit && !dev) { commit = meta[i]; continue; }
      return "";
    }
    return "Version " + ver + (commit ? ", build " + commit : "") + (dev ? ", dev" : "");
  }
  /* BUILD-STAMP:end */

  /* TC-SNAP-UI: the full game-data credits in Settings > About and data
     (PLAY-TD-21B-SETTINGS-ABOUT moved them out of the footer), read on
     every connect, so a snapshot made by the build shows up without a
     click. RUN-BUILD-STAMP-UI: the same read fills the footer's version
     line and the About and data version, so a core restart on a new build
     shows it. */
  function loadDataCredit() {
    api("GET", "/api/version").then(function (doc) {
      var text = D.dataCreditText(doc);
      var p = $("data-credit");
      p.textContent = text;
      p.hidden = !text;
      $("credits").hidden = !text; // the About and data group around it
      var ver = versionText(doc);
      if (ver) {
        $("build-line").textContent = ver;
        $("build-line").hidden = false;
        $("about-version").textContent = ver;
      }
    }).catch(function () { /* keep the last line; the next connect retries */ });
  }

  /* TEST-WEB-PANELS-B: a panel's first read (host.onConnect), kept in the
     order the panels wired and run by connect() where it read them itself */
  var connectReads = [];

  function onConnect(fn) {
    if (typeof fn === "function") { connectReads.push(fn); }
  }

  function connect() {
    if (!token) {
      setLink("notoken");
      return;
    }
    // TEST-WEB-PANELS-B: the overlay layout, the stat weights and the web
    // data setting, read by their panels (onConnect, in wire order)
    connectReads.forEach(function (fn) { fn(); });
    loadRates();
    loadDataCredit();
    api("GET", "/api/state").then(render).catch(function () {
      if (!linkLive) { setLink("error"); }
    });
    if (es) { es.close(); }
    es = new EventSource("/events?token=" + encodeURIComponent(token));
    es.addEventListener("open", function () { setLink("open"); tick(); });
    es.addEventListener("error", function () { setLink("error"); });
    es.addEventListener("state", function (m) {
      try { render(JSON.parse(m.data)); } catch (e) { /* ignore a bad frame */ }
    });
    /* HOT-RELOAD (decision 0042): a dashboard file changed on disk (source
       checkout only); load the new page. The token stays in sessionStorage. */
    es.addEventListener("reload", function (m) {
      var d = null;
      try { d = JSON.parse(m.data); } catch (e) { d = null; }
      if (d && d.target === "web") { location.reload(); }
    });
  }

  function start() {
    document.addEventListener("visibilitychange", tick);
    // TEST-WEB-REGISTRY: every panel's wire, in its order (web/registry.js)
    A.start();
    // RUN-VERDICTS-UI: the 'Tried in game' card (one read, then clicks only)
    if (window.ALVerdicts) { window.ALVerdicts.wire(document, api); }
    // PLAY-TD-21A-SETTINGS-RAIL: the Settings rail, the bar status word's
    // jump and the data-jump buttons; before the first push, so a failing
    // check shows the Checks section (web/rail.js)
    if (window.ALRail) {
      window.ALRail.start(document, { tabs: window.ALTabs || null,
        observe: typeof window.ResizeObserver === "function" ? window.ResizeObserver : null });
    }
    // TD-09 region hook: wire every registered Play region before the first push
    if (window.ALRegions) {
      window.ALRegions.start(document, {
        api: api,
        getSnap: function () { return snap; },
        serverNow: serverNow,
        tabs: window.ALTabs || null
      });
    }
    setInterval(pollRates, RATES_POLL_MS);
    // The two timers advance once a second; nothing else moves.
    ticker = setInterval(tick, 1000);
    connect();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
}());
