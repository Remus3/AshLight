/* AshLight dashboard: the Acts card of the Run grid (HUD-ACT; PLAY-TD-20A-
   RUN-GRID, plan 03 section 4, TD-20). UMD: CommonJS for node --test
   (app/test/acts.test.js), window.ALActs for the page. The core computes
   the splits and sends every sentence in the snapshot's `acts` part
   (server/al/acts.py); this file only formats times and writes the rows.
   No timers, no network.

   The card is a fixed cell of the Run grid: one page at a time and lists
   that page (web/pager.js rows through ALSearch.rowPager: 10 rows a page,
   8 compact; a row is one line with its full text on the Full text page).
   Home page: one row per act (act, time in the act, run total, your best
   from run history). Pages: zone levels with the game data credit line
   under them (decision 0009), the pace line and the character picker,
   the zone guide and quest tracker slot (decision 0043). A page changes
   only on a press (wireCard); web/runs.js wires its cards with the same
   helper. */
(function (root, factory) {
  "use strict";
  var common = typeof module === "object" && module.exports;
  var api = factory(common ? require("./fmt.js") : root.ALFmt, function () {
    return common ? require("./search.js") : root.ALSearch;
  }, function () {
    return !common && root.ALApp ? root.ALApp.host || null : null;
  }, function (snap, picked) {
    var C = !common ? root.ALChars : null;
    return C && typeof C.view === "function" ? C.view(snap, picked) : snap;
  });
  if (common) {
    module.exports = api;
  } else {
    root.ALActs = api;
  }
}(typeof self !== "undefined" ? self : this, function (F, searchLib, pageHost, charView) {
  "use strict";

  /* Seconds as m:ss or h:mm:ss, the same form as the zone timer
     (web/fmt.js). */
  var duration = F.duration;

  function isFn(v) { return typeof v === "function"; }

  /* One display row per split. `now` is server time (s); the open split
     counts up to it, a closed one keeps its own end. */
  function splitRows(acts, now) {
    var splits = (acts && acts.splits) || [];
    if (splits.length === 0) { return []; }
    var start = splits[0].started_at;
    return splits.map(function (s) {
      var end = s.ended_at === null || s.ended_at === undefined ? now : s.ended_at;
      var label = s.label || "Act";
      return {
        key: s.key || "",
        label: label,
        note: s.partial ? "partial" : "",
        time: duration(end - s.started_at),
        total: duration(end - start),
        current: !!s.current
      };
    });
  }

  /* UX-NEW-CARDS: a partial row says only "(partial)"; the reason is one
     sentence, read on the row's Full text page. "" when no row is
     partial. */
  function partialNote(acts) {
    var splits = (acts && acts.splits) || [];
    var any = splits.some(function (s) { return !!s.partial; });
    var t = (acts && acts.partial_text) || "";
    if (!any || !t) { return ""; }
    return t.charAt(0).toUpperCase() + t.slice(1) + ".";
  }

  /* Your best time per act key, from the run history the core sends
     (`run_history.best`, server/al/runhistory.py); {} with none. */
  function bestByKey(hist) {
    var out = {};
    ((hist && hist.best) || []).forEach(function (b) {
      if (!b || !b.key) { return; }
      var t = b.best_text || (typeof b.best_s === "number" ? duration(b.best_s) : "");
      if (t) { out[b.key] = t; }
    });
    return out;
  }

  /* The one-line list text of an act row, key facts first: "Act 2 (now):
     14:05, total 38:10, best 35:12" (time in the act, run total, your
     best). */
  function actLine(r, best) {
    var notes = [];
    if (r.current) { notes.push("now"); }
    if (r.note) { notes.push(r.note); }
    var t = r.label + (notes.length ? " (" + notes.join(", ") + ")" : "") + ": " +
      r.time + ", total " + r.total;
    var b = best && r.key ? best[r.key] : "";
    if (b) { t += ", best " + b; }
    return t;
  }

  /* The whole text of an act row (title and the Full text page): the
     list text, and for a partial row the reason sentence. */
  function actText(r, best, note) {
    var t = actLine(r, best);
    if (r.note && note) { t += ". " + note; }
    return t;
  }

  /* One display row per zone of the current act: name, level, and a note
     ("you are here", "town"). */
  function zoneRows(acts) {
    return ((acts && acts.zones) || []).map(function (z) {
      var notes = [];
      if (z.here) { notes.push("you are here"); }
      if (z.town) { notes.push("town"); }
      return { name: z.name, level: String(z.level), note: notes.join(", "),
        here: !!z.here };
    });
  }

  /* "Vastiri Outskirts: level 16 (you are here)" */
  function zoneText(z) {
    return z.name + ": level " + z.level + (z.note ? " (" + z.note + ")" : "");
  }

  /* Label of the zone level page: "Zone levels in Act 2". */
  function zonesTitle(acts) {
    return acts && acts.zones_act ? "Zone levels in " + acts.zones_act : "Zone levels";
  }

  /* The zone level page's message when there is no list to show: the
     data is missing on this computer, lacks the player's act, or the
     player is not in an act. */
  function zonesEmpty(acts) {
    if (!acts) { return ""; }
    // UX-FIRSTRUN: outside a campaign act the missing download does not
    // matter yet, so the player is not told to run a build step.
    if (!acts.levels && acts.current) { return acts.no_levels_text || ""; }
    if (!acts.levels) { return acts.no_zones_text || ""; }
    if (!acts.zones || acts.zones.length === 0) {
      // UTIL-1.0-FIXTURES: in an act the downloaded table lacks (Acts 5-6
      // before the data refresh) the core says so instead.
      return acts.act_levels_text || acts.no_zones_text || "";
    }
    return "";
  }

  /* ---- card pages (shared with web/runs.js) -----------------------------
     A grid card shows one .card-page at a time: its home page, or the page
     a button with data-card-open names; the Back button in the card head
     returns home and gives focus back to the opener. In the page the
     switch is web/app.js's own (ALApp.host.showCardPage), so every grid
     card behaves alike; without it (node tests) the same steps run here. */
  function homeOf(box) { return box.getAttribute("data-home") || "main"; }

  function setSub(node, text) {
    if (!node) { return; }
    node.textContent = text;
    if (text) { node.setAttribute("title", text); } else { node.removeAttribute("title"); }
  }

  function localShow(doc, box, name, focusTo) {
    var home = homeOf(box);
    var active = doc.activeElement;
    var lost = false;
    var cur = null;
    Array.prototype.forEach.call(box.querySelectorAll(".card-page"), function (pg) {
      var on = pg.getAttribute("data-page") === name;
      if (!on && !pg.hidden && isFn(pg.contains) && pg.contains(active)) { lost = true; }
      pg.hidden = !on;
      if (on) { cur = pg; }
    });
    box.setAttribute("data-shown", name);
    setSub(box.querySelector("[data-card-sub]"),
      name === home || !cur ? "" : cur.getAttribute("data-label") || "");
    var back = box.querySelector("[data-card-back]");
    var h = box.querySelector("h2");
    back.hidden = name === home;
    back.setAttribute("aria-label", "Back to the first page of " + (h ? h.textContent : "the card"));
    if (focusTo && !focusTo.hidden) {
      focusTo.focus();
    } else if (lost && h) {
      h.focus();
    }
  }

  /* Wire a card's page buttons once (per document); returns the box. */
  function wireCard(doc, id) {
    var box = doc.getElementById(id);
    if (!box || box.getAttribute("data-wired") === "1") { return box; }
    box.setAttribute("data-wired", "1");
    var host = pageHost();
    var show = host && isFn(host.showCardPage) ? host.showCardPage
      : function (b, name, focusTo) { localShow(doc, b, name, focusTo); };
    var h = box.querySelector("h2");
    var back = box.querySelector("[data-card-back]");
    var opener = null;
    if (h && !h.hasAttribute("tabindex")) { h.setAttribute("tabindex", "-1"); }
    Array.prototype.forEach.call(box.querySelectorAll("[data-card-open]"), function (b) {
      b.addEventListener("click", function () {
        opener = b;
        show(box, b.getAttribute("data-card-open"), back);
      });
    });
    back.addEventListener("click", function () {
      show(box, homeOf(box), opener && !opener.hidden && !opener.disabled ? opener : h);
    });
    show(box, homeOf(box), null);
    return box;
  }

  /* A page's label (the card head's sub line while the page shows). */
  function setPageLabel(box, page, text) {
    if (!box) { return; }
    var pg = box.querySelector('[data-page="' + page + '"]');
    if (!pg || pg.getAttribute("data-label") === text) { return; }
    pg.setAttribute("data-label", text);
    if (box.getAttribute("data-shown") === page) { setSub(box.querySelector("[data-card-sub]"), text); }
  }

  /* ---- pagers -------------------------------------------------------------
     One rowPager per slot and document (web/search.js over web/pager.js):
     it pages again when a resize changes the size class (ALSearch
     .relayout) and keeps its page across data changes. */
  var pagers = {};

  function pagerFor(doc, slotId, label, size) {
    var slot = doc.getElementById(slotId);
    if (!slot) { return null; }
    var have = pagers[slotId];
    if (have && have.doc === doc && have.slot === slot) { return have.pg; }
    var S = searchLib();
    var pg = S.rowPager(doc, {
      label: label,
      size: size || null,
      sizeClass: function () { return S.sizeClass(doc); },
      text: function (r) { return r.text; },
      // the list shows r.line when a row has one (key facts first); the
      // title and the Full text page keep the whole r.text
      parts: function (r) { return [{ text: r.line || r.text }]; }
    });
    slot.replaceChildren(pg.node);
    pagers[slotId] = { doc: doc, slot: slot, pg: pg, key: null };
    return pg;
  }

  /* Write rows (each {text, line?}) into a slot's pager; the slot hides
     with no rows (the card's empty sentence shows instead). Unchanged rows
     write nothing, so the 1 s tick moves only what moved. size: rows a
     page {full, compact} when a page holds more than the list (default
     web/pager.js LIST_ROWS, 10 and 8). */
  function fill(doc, slotId, label, rows, size) {
    var pg = pagerFor(doc, slotId, label, size);
    if (!pg) { return null; }
    var entry = pagers[slotId];
    var key = rows.map(function (r) { return (r.line || "") + "|" + r.text; }).join("\n");
    doc.getElementById(slotId).hidden = rows.length === 0;
    if (entry.key !== key) {
      entry.key = key;
      pg.set(rows);
    }
    return pg;
  }

  function showText(doc, id, text) {
    var n = doc.getElementById(id);
    if (!n) { return; }
    if (n.textContent !== text) { n.textContent = text; }
    n.hidden = !text;
  }

  /* The run history of the character the card shows: given (tests), or
     read from the page (the snapshot through ALChars.view, the picker's
     choice), as the Run history card reads it. */
  function historyOf(doc, given) {
    if (given !== undefined) { return given; }
    var host = pageHost();
    var snap = host && isFn(host.getSnap) ? host.getSnap() : null;
    if (!snap) { return null; }
    var pick = doc.getElementById("char-pick");
    var c = charView(snap, pick && pick.value ? pick.value : "");
    return (c && c.run_history) || null;
  }

  var lastBest = {};
  var ZONE_ROWS = { full: 9, compact: 8 };

  /* Fill the Acts card. full: every row and page (new snapshot); otherwise
     only the act rows (the 1 s tick moves the open act's times). hist:
     the run history for "your best" (read from the page when left out). */
  function paint(doc, acts, now, full, hist) {
    if (!doc.getElementById("acts-rows")) { return; }
    var rows = splitRows(acts, now);
    if (full) {
      wireCard(doc, "actsbox");
      lastBest = bestByKey(historyOf(doc, hist));
    }
    var note = partialNote(acts);
    fill(doc, "acts-rows", "act times", rows.map(function (r) {
      return { text: actText(r, lastBest, note), line: actLine(r, lastBest), current: r.current };
    }));
    if (!full) { return; }
    showText(doc, "acts-empty", rows.length ? "" : (acts && acts.empty_text) || "");

    var box = doc.getElementById("actsbox");
    setPageLabel(box, "zones", zonesTitle(acts));
    var zones = zoneRows(acts);
    // the credit takes two lines under the list (it is never cut), so a
    // full page holds 9 zones: 9 x 22 + 24 + 40 = 262 of 270 px (compact
    // 8 x 22 + 24 + 40 = 240 of 240)
    fill(doc, "zones-rows", "zone levels", zones.map(function (z) {
      return { text: zoneText(z), here: z.here };
    }), ZONE_ROWS);
    showText(doc, "zones-empty", zones.length ? "" : zonesEmpty(acts));
    // decision 0009 item 2: the credit shows whenever the zone levels do
    var src = doc.getElementById("zones-source");
    var credit = zones.length && acts && acts.source ? acts.source : "";
    showText(doc, "zones-source", credit);
    if (src) {
      if (credit) { src.setAttribute("title", credit); } else { src.removeAttribute("title"); }
    }
  }

  return { duration: duration, splitRows: splitRows, zoneRows: zoneRows,
    zonesTitle: zonesTitle, zonesEmpty: zonesEmpty, partialNote: partialNote,
    bestByKey: bestByKey, actLine: actLine, actText: actText, zoneText: zoneText,
    ZONE_ROWS: ZONE_ROWS,
    wireCard: wireCard, setPageLabel: setPageLabel, fill: fill, showText: showText,
    paint: paint };
}));
