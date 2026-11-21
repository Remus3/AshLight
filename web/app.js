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
     recent list as it was; rebuild its rows only when the list changed. */
  var renderedEvents = "";

  function renderEvents(rows) {
    var key = D.eventsKey(rows);
    if (key === renderedEvents) { return; }
    renderedEvents = key;
    var list = $("events");
    var frag = document.createDocumentFragment();
    for (var i = rows.length - 1; i >= 0; i--) {
      var row = rows[i];
      var li = document.createElement("li");
      var k = D.kindOf(row);
      if (row.whisper) { li.className = "whisper"; }
      if (row.trade) { li.className += " trade"; }
      if (row.type === "death") { li.className = "death"; }
      var t = document.createElement("span");
      t.className = "time mono";
      t.textContent = clock(row.at);
      var kd = document.createElement("span");
      kd.className = "kind";
      kd.textContent = k;
      var tx = document.createElement("span");
      tx.className = "text";
      tx.textContent = row.text;
      li.appendChild(t);
      li.appendChild(kd);
      li.appendChild(tx);
      frag.appendChild(li);
    }
    list.replaceChildren(frag);
    $("events-empty").hidden = rows.length > 0;
  }

  /* OVL-POS: overlay layout editor. Saved to config/local.json by the core;
     the overlay follows the file. */
  var layoutBusy = false;

  function option(value, text) {
    var o = document.createElement("option");
    o.value = value;
    o.textContent = text;
    return o;
  }

  function fillLayout(doc) {
    var l = doc.layout;
    var corner = $("layout-corner");
    if (!corner.options.length) {
      doc.corners.forEach(function (c) { corner.appendChild(option(c, D.cornerLabel(c))); });
    }
    var disp = $("layout-display");
    disp.replaceChildren(option("primary", "Primary"));
    (doc.displays || []).forEach(function (d) {
      disp.appendChild(option(String(d.index), "Monitor " + (d.index + 1) +
        (d.primary ? " (primary)" : "") +
        (d.width ? " - " + d.width + "x" + d.height : "") +
        (d.scale_factor && d.scale_factor !== 1
          ? " @" + Math.round(d.scale_factor * 100) + "%" : "")));
    });
    var known = (doc.displays || []).some(function (d) { return d.index === l.display; });
    if (l.display !== "primary" && !known) {
      disp.appendChild(option(String(l.display),
        "Monitor " + (l.display + 1) + " (not connected - primary used)"));
    }
    disp.value = String(l.display);
    corner.value = l.corner;
    $("layout-scale").value = String(l.scale);
    $("layout-opacity").value = String(l.opacity);
    $("layout-margin").value = String(l.margin);
    $("layout-scale-out").textContent = Math.round(l.scale * 100) + "%";
    $("layout-opacity-out").textContent = Math.round(l.opacity * 100) + "%";
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

  function readLayoutForm() {
    var d = $("layout-display").value;
    return {
      display: d === "primary" ? "primary" : parseInt(d, 10),
      corner: $("layout-corner").value,
      scale: parseFloat($("layout-scale").value),
      opacity: parseFloat($("layout-opacity").value),
      margin: parseInt($("layout-margin").value, 10) || 0
    };
  }

  function saveLayout() {
    if (layoutBusy) { return; }
    layoutBusy = true;
    $("layout-status").textContent = "Saving...";
    api("POST", "/api/overlay-layout", readLayoutForm()).then(function (doc) {
      fillLayout(doc);
      $("layout-status").textContent = "Saved. The overlay moves within a second.";
    }).catch(function (e) {
      $("layout-status").textContent = "Not saved. Try again.";
      console.warn("layout save failed: " + e.message);
    }).then(function () { layoutBusy = false; });
  }

  function loadLayout() {
    api("GET", "/api/overlay-layout").then(fillLayout).catch(function () {
      $("layout-status").textContent = "Can't load the overlay settings. Is AshLight running?";
    });
  }

  /* ---- TC-VIEW: the loaded build. It follows the core: the state carries
     a build revision, and a new one fetches GET /api/build (no refresh
     button). Text from the build goes in via textContent only. */
  var T = window.ALTc; // web/tc.js: pure view helpers
  var buildRev = null;
  var calcRev = null; // MATH-SKILL-SPLIT / MATH-DEF-BREAKDOWN: PoB calc outputs ready
  var buildDoc = null;
  var pobEvalId = null; // MATH-NEXT-LOOK: the last PoB-scored item check
  var lastPaste = "";

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

  function loadBuild() {
    api("GET", "/api/build").then(function (doc) {
      buildDoc = doc;
      renderBuild();
      // UTIL-SEARCHSTR: copy happens only on the player's Copy click
      if (window.ALSearch) { window.ALSearch.paint(document, doc, navigator); }
      // MATH-BUILD-HEALTH / MATH-NEXT-LOOK: PoB numbers; Copy on a click only
      if (window.ALHealth) { window.ALHealth.paint(document, doc, navigator); }
      // MATH-SKILL-SPLIT: PoB's per-skill DPS on the Build card's Damage page
      if (window.ALSkillSplit) { window.ALSkillSplit.paint(document, doc); }
      var noSplit = $("split-wrap").hidden;
      $("split-open").hidden = noSplit;
      if (noSplit && cardShown($("buildbox")) === "split") { cardHome($("buildbox")); }
    }).catch(function () {
      setLine($("build-status"), "Can't load the build. Is AshLight running?");
    });
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

  function linkPager(slotId, label, size, opts) {
    var pg = buildPagers[slotId];
    if (!pg) {
      pg = window.ALSearch.rowPager(document, {
        label: label, size: size, sizeClass: sizeClass, text: opts.text,
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

  /* BUILD-LIVE (decision 0045): where the build came from and how old it is */
  var SOURCE_WORDS = { paste: "Pasted", press: "Loaded with the item key",
    ggg_api: "Loaded from your account" };

  function sourceLine(doc) {
    var word = SOURCE_WORDS[doc && doc.source] || "Loaded";
    var at = doc && typeof doc.loaded_at === "number" ? doc.loaded_at : null;
    if (at === null) { return word + "."; }
    var s = Math.max(0, serverNow() - at);
    var age = s < 60 ? "just now" : s < 3600 ? Math.floor(s / 60) + " min ago"
      : s < 172800 ? Math.floor(s / 3600) + " h ago" : Math.floor(s / 86400) + " days ago";
    return word + ", " + age + ".";
  }

  function renderBuildYou() {
    if (!buildDoc) { return; }
    var v = T.buildView(buildDoc, snap);
    if (!v.loaded) { return; }
    setLine($("build-level"), v.levelLine);
    setLine($("build-you"), v.you);
    $("build-you").hidden = !v.you;
    setLine($("build-source"), sourceLine(buildDoc));
  }

  var KEY_STATS_SHOWN = 6; // plan 03 section 4: key stats (6)

  function renderBuild() {
    var v = T.buildView(buildDoc, snap);
    $("build-view").hidden = !v.loaded;
    $("build-empty").hidden = v.loaded;
    $("build-paste-label").textContent = v.loaded ? "Paste another build" : "Paste a build";
    setCardHome($("buildbox"), v.loaded ? "main" : "paste");
    if (!v.loaded) {
      $("build-empty").textContent = v.empty;
      return;
    }
    setLine($("build-name"), v.title);
    renderBuildYou();
    var dl = document.createDocumentFragment();
    v.stats.slice(0, KEY_STATS_SHOWN).forEach(function (s) {
      var row = el("div", "");
      row.appendChild(el("dt", "", s.label));
      row.appendChild(el("dd", "mono", s.value));
      dl.appendChild(row);
    });
    $("build-stats").replaceChildren(dl);
    $("build-stats-empty").hidden = v.stats.length > 0;
    setLine($("build-copy-status"), "");
    $("build-copy").setAttribute("aria-label", "Copy the build code for Path of Building");

    // the Health and next card's gear, gems and notes pages: rows through
    // the pagers (one line each; the Full text page holds the whole text)
    linkPager("build-gear", "gear", { full: 9, compact: 7 }, {
      rows: v.gear.length ? v.gear.map(function (g) {
        return { text: g.slot + ": " + g.name + (g.base ? ", " + g.base : "") +
          (g.rarity ? " (" + g.rarity + ")" : ""),
          link: g.links[0] || null, linkName: g.name };
      }) : [{ text: "No gear in this build." }],
      text: function (r) { return r.text; }
    });
    var gems = [];
    v.skills.forEach(function (g) {
      var head = g.label + (g.main ? " (main skill)" : "") + (g.enabled ? "" : " (off)");
      g.gems.forEach(function (m) {
        gems.push({ text: head + ": " + m.name + (m.detail ? " (" + m.detail + ")" : ""),
          off: !g.enabled || !m.enabled, link: m.links[0] || null, linkName: m.name });
      });
      if (!g.gems.length) { gems.push({ text: head, off: !g.enabled }); }
    });
    linkPager("build-skills", "skills and gems", { full: 8, compact: 6 }, {
      rows: gems.length ? gems : [{ text: "No skills in this build." }],
      text: function (r) { return r.text; },
      rowClass: function (r) { return r.off ? "off" : ""; }
    });
    var tree = $("build-tree");
    tree.replaceChildren();
    if (v.tree) {
      var line = el("span", "one-line", v.tree.line + ".");
      line.setAttribute("title", v.tree.line + ".");
      tree.appendChild(line);
      if (v.tree.url) {
        var a = el("a", "out", "Open the tree");
        a.href = v.tree.url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.setAttribute("aria-label", "Open the passive tree (opens in a new tab)");
        tree.appendChild(a);
      }
    } else {
      tree.textContent = "No passive tree in this build.";
    }
    var notes = v.notes ? v.notes.split(/\r?\n/).map(function (x) { return x.trim(); })
      .filter(function (x) { return x; }) : [];
    textPager("build-notes", "build notes", notes.length ? notes : ["No notes in this build."]);
    var mine = buildDoc && buildDoc.character;
    var chars = (buildDoc && Array.isArray(buildDoc.characters_with_builds)
      ? buildDoc.characters_with_builds : []).filter(function (n) { return typeof n === "string" && n; })
      .map(function (n) { return n === mine ? n + " (this character)" : n; });
    textPager("build-chars", "characters with a build", chars.length ? chars
      : ["No character has a saved build yet."]);
    $("build-code-out").value = v.code;
    renderBuildFile();
  }

  /* TC-BUILDFILE (decision 0034): what the .build download holds and what
     was left out; ready as soon as a build is loaded (no click). */
  function renderBuildFile() {
    var f = T.buildFileView(buildDoc);
    tellBuildFile("");  /* a new build: the last click's answer is stale */
    $("buildfile-save").disabled = !f.ready;
    setLine($("buildfile-summary"), f.ready ? f.summary
      : "The build file isn't available for this build.");
    /* each left-out note on its own wrapping row: the whole text shows */
    var notes = $("buildfile-notes");
    notes.replaceChildren();
    f.notes.forEach(function (s) { notes.appendChild(el("li", "", s)); });
    notes.hidden = !f.notes.length;
  }

  /* TC-BUILDFILE: on the player's click, fetch the .build text and hand it
     to the browser as a download; the player picks where it goes. AshLight
     writes no file itself. No live region (the page keeps its 12): as for
     downloadFilter, the focused button's name carries the answer. */
  function tellBuildFile(text) {
    setLine($("buildfile-said"), text);
    $("buildfile-save").setAttribute("aria-label", text ? "Save .build file (" + text + ")"
      : "Save .build file");
  }

  function saveBuildFile() {
    var tell = tellBuildFile;
    tell("");
    var name = T.buildFileView(buildDoc).filename || "ashlight.build";
    fetch("/api/buildfile", { headers: { "X-AL-Token": token }, cache: "no-store" })
      .then(function (r) {
        if (!r.ok) {
          tell(r.status === 404 ? "Paste a build first." : "Can't make the file. Try again.");
          return null;
        }
        return r.text();
      }).then(function (text) {
        if (text === null) { return; }
        var url = URL.createObjectURL(new Blob([text], { type: "application/json" }));
        var a = document.createElement("a");
        a.href = url;
        a.download = name;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
        tell("Saved to your browser's downloads. Move it to the game's planner folder " +
          "in your Documents.");
      }).catch(function () {
        tell("Can't reach AshLight - is it running?");
      });
  }

  /* A token POST that resolves to { status, body } on any HTTP answer
     (the paste box words every status); rejects only when unreachable. */
  function postJson(path, body) {
    var opts = { method: "POST", cache: "no-store",
                 headers: { "X-AL-Token": token, "Content-Type": "application/json" },
                 body: JSON.stringify(body) };
    return fetch(path, opts).then(function (r) {
      return r.json().catch(function () { return null; }).then(function (b) {
        return { status: r.status, body: b };
      });
    });
  }

  /* The paste box's answer: the status line, a loaded build, and the
     TC-LINK-RECOVER offer when the core refused a link for web data. */
  function showPaste(res, body, code) {
    setLine($("build-status"), res.text);
    linkRecover = res.offer ? T.linkRecover(code, postJson) : null;
    $("link-recover").hidden = !linkRecover;
    $("link-offer-row").hidden = false;
    $("link-confirm").hidden = true;
    $("paste-form").hidden = false;
    if (res.ok) {
      $("build-paste").value = "";
      buildDoc = body;
      renderBuild();
    } else {
      lastPaste = ""; // the same text may be pasted again after a fix
    }
  }

  function pasteBuild() {
    var text = $("build-paste").value.trim();
    if (!text || text === lastPaste) { return; }
    lastPaste = text;
    linkRecover = null;
    $("link-recover").hidden = true;
    setLine($("build-status"), "Loading the build...");
    postJson("/api/build-code", { code: text }).then(function (r) {
      showPaste(T.pasteResult(r.status, r.body), r.body, text);
    }).catch(function () {
      lastPaste = "";
      setLine($("build-status"), "Not loaded. Can't reach AshLight - is it running?");
    });
  }

  /* TC-LINK-RECOVER (F-117, decision 0013): first click shows the full
     opt-in sentence and posts nothing; only the confirm click saves the
     opt-in and loads the same link once. */
  var linkRecover = null;

  function linkOffer() {
    var shown = linkRecover ? linkRecover.open() : null;
    if (!shown) { return; }
    $("link-sentence").textContent = shown.sentence;
    $("link-offer-row").hidden = true;
    $("link-confirm").hidden = false;
    $("paste-form").hidden = true; /* the sentence takes the paste box's place */
    $("link-yes").focus();
  }

  function linkCancel() {
    if (!linkRecover) { return; }
    linkRecover.cancel();
    $("link-confirm").hidden = true;
    $("paste-form").hidden = false;
    $("link-offer-row").hidden = false;
    $("link-offer").focus();
  }

  function linkConfirm() {
    var rec = linkRecover;
    var going = rec ? rec.confirm() : null;
    if (!going) { return; }
    $("link-yes").disabled = true;
    setLine($("build-status"), "Turning on web data, then loading the link...");
    going.then(function (out) {
      $("link-yes").disabled = false;
      if (out.web) { webDataSaved(out.web); }
      if (rec !== linkRecover) { return; } // a new paste took the box meanwhile
      if (!out.saved) {
        setLine($("build-status"), out.result.text);
        $("link-yes").focus(); // re-enabled; the panel stays for another try
        return;
      }
      showPaste(out.result, out.body, "");
      // the buttons are gone; stay in this card (the paste box, or the
      // heading once the loaded build took the card's first page)
      if (cardShown($("buildbox")) === "paste") { $("build-paste").focus(); } else {
        cardHeading($("buildbox")).focus();
      }
    });
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

  /* Copy code: the clipboard is written only in this click. No live region
     (PLAY-TD-19C-BUILD-GRID: the page-wide cap is 6); the answer is plain
     text beside the button and the button's own name. When the clipboard
     refuses, the card's code page shows the code selected for Ctrl+C. */
  function copyBuild() {
    var code = buildDoc && buildDoc.code;
    if (!code) { return; }
    var out = $("build-code-out");
    var btn = $("build-copy");
    var done = function () {
      setLine($("build-copy-status"), "Copied - paste it into Path of Building");
      btn.setAttribute("aria-label", "Copy the build code for Path of Building (copied)");
    };
    var fallback = function () {
      setLine($("build-copy-status"), "");
      cardOpener.buildbox = btn;
      showCardPage($("buildbox"), "code", out);
      out.select();
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(code).then(done, fallback);
    } else {
      fallback();
    }
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
          c.stats.forEach(function (s) { check.push(textRow(slot + ": " + s.text + " " + s.points)); });
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

  /* Stat weights editor: saves on change (PUT /api/weights). */
  var weightsBusy = false;
  var weightsAgain = false; // a change arrived while a save was in flight

  /* PLAY-TD-19D-ITEMS-GRID: the Item scoring card. Its first page lists
     only the weights changed from the defaults (the core's `changed`);
     the Stat weights page shows every weight, 10 a page (8 compact): all
     rows stay in the form and a page only hides the others, so focus, a
     value being typed and every save keep working across pages. */
  /* rows of 24 px (a 24 px number box) plus the card's status line fit 9
     a page in the full class and 6 in the compact one (cards 322 and 256
     px tall at s = 1) */
  var WEIGHT_PAGE = { full: 9, compact: 6 };
  var CHANGED_ROWS = { full: 6, compact: 4 };
  var weightsDoc = null;
  var weightsPageAt = 0;
  var weightsBar = null;

  function weightLabel(k) { return String(k).replace(/#/g, "N"); }

  function pointsText(v) {
    var n = P.num(v);
    return n === "1" ? "1 point" : n + " points";
  }

  function changedRows(doc) {
    var ch = (doc && doc.changed) || {};
    var defs = (doc && doc.defaults) || {};
    var dw = defs.weights || {};
    var rows = Object.keys(ch.weights || {}).sort(function (a, b) {
      var x = a.toLowerCase(), y = b.toLowerCase();
      return x < y ? -1 : (x > y ? 1 : 0);
    }).map(function (k) {
      var v = ch.weights[k];
      var d = dw[k];
      if (v === null) { return weightLabel(k) + ": removed (default " + pointsText(d) + ")"; }
      return weightLabel(k) + ": " + pointsText(v) +
        (typeof d === "number" ? " (default " + pointsText(d) + ")" : " (added)");
    });
    var sg = ch.sidegrade || {};
    var dsg = defs.sidegrade || {};
    if (typeof sg.abs === "number") {
      rows.push("Sidegrade range: " + pointsText(sg.abs) + " (default " + pointsText(dsg.abs) + ")");
    }
    if (typeof sg.pct === "number") {
      rows.push("Sidegrade range: " + P.num(sg.pct) + "% of your item's score (default " +
        P.num(dsg.pct) + "%)");
    }
    return rows;
  }

  function bandLine(doc) {
    var sg = (doc && doc.sidegrade) || {};
    if (typeof sg.abs !== "number" || typeof sg.pct !== "number") { return ""; }
    return "About the same within " + pointsText(sg.abs) + " or " + P.num(sg.pct) +
      "% of your item's score.";
  }

  function weightPager() {
    if (weightsBar) { return weightsBar; }
    var count = el("span", "al-pager-count");
    var mk = function (text, label, step) {
      var b = el("button", "al-pager-btn", text);
      b.type = "button";
      b.setAttribute("aria-label", label);
      b.addEventListener("click", function () {
        if (b.getAttribute("aria-disabled") === "true") { return; }
        weightsPageAt += step;
        showWeightPage();
      });
      return b;
    };
    weightsBar = { count: count, prev: mk("Prev", "Previous page of stat weights", -1),
      next: mk("Next", "Next page of stat weights", 1) };
    $("weights-pager").replaceChildren(count, weightsBar.prev, weightsBar.next);
    return weightsBar;
  }

  /* One page of the weight rows; it changes on a press, a new stat list
     or a size class change, never by itself. */
  function showWeightPage() {
    var items = $("weights-list").querySelectorAll("li");
    var size = WEIGHT_PAGE[sizeClass() === "compact" ? "compact" : "full"];
    var pages = Math.max(1, Math.ceil(items.length / size));
    weightsPageAt = Math.min(Math.max(0, weightsPageAt), pages - 1);
    var from = weightsPageAt * size;
    Array.prototype.forEach.call(items, function (li, i) {
      li.hidden = i < from || i >= from + size;
    });
    var bar = weightPager();
    bar.count.textContent = pages > 1
      ? (from + 1) + "-" + Math.min(items.length, from + size) + " of " + items.length : "";
    bar.prev.hidden = bar.next.hidden = pages < 2;
    [[bar.prev, weightsPageAt > 0], [bar.next, weightsPageAt < pages - 1]].forEach(function (p) {
      if (p[1]) { p[0].removeAttribute("aria-disabled"); } else { p[0].setAttribute("aria-disabled", "true"); }
    });
  }

  /* Update the rows in place when the stat list is the same, so focus and
     a value being typed survive a save; rebuild only when stats were added
     or removed, then put focus back on the same stat (on its page). */
  function fillWeights(doc) {
    weightsDoc = doc;
    var rows = T.weightRows(doc);
    var inputs = $("weights-list").querySelectorAll("input[data-key]");
    var same = inputs.length === rows.length && rows.every(function (r, i) {
      return inputs[i].getAttribute("data-key") === r.key;
    });
    fillBand(doc);
    var changed = changedRows(doc);
    linkPager("weights-changed", "changed weights", CHANGED_ROWS, {
      rows: (changed.length ? changed : ["Every weight is at its default."]).map(textRow),
      text: function (r) { return r.text; }
    });
    setLine($("weights-band-line"), bandLine(doc));
    if (same) {
      rows.forEach(function (r, i) {
        if (inputs[i] !== document.activeElement) { inputs[i].value = String(r.weight); }
      });
      return;
    }
    var focusKey = document.activeElement && document.activeElement.getAttribute
      ? document.activeElement.getAttribute("data-key") : null;
    var frag = document.createDocumentFragment();
    rows.forEach(function (r, i) {
      var li = el("li");
      var id = "w-" + i;
      var lab = el("label", "", r.label);
      lab.htmlFor = id;
      lab.setAttribute("title", r.label);
      var inp = el("input");
      inp.type = "number";
      inp.step = "any";
      inp.id = id;
      inp.value = String(r.weight);
      inp.setAttribute("data-key", r.key);
      inp.setAttribute("inputmode", "decimal");
      li.appendChild(lab);
      li.appendChild(inp);
      frag.appendChild(li);
    });
    $("weights-list").replaceChildren(frag);
    var all = $("weights-list").querySelectorAll("input[data-key]");
    var back = focusKey ? Array.prototype.find.call(all, function (inp) {
      return inp.getAttribute("data-key") === focusKey;
    }) : null;
    if (back) {
      weightsPageAt = Math.floor(Array.prototype.indexOf.call(all, back) /
        WEIGHT_PAGE[sizeClass() === "compact" ? "compact" : "full"]);
    }
    showWeightPage();
    if (back) { back.focus(); }
  }

  /* Reset (the card's Reset page, one confirm click): the defaults the
     core sent with the weights, saved as one PUT. */
  function resetWeights() {
    var defs = weightsDoc && weightsDoc.defaults;
    if (!defs || weightsBusy) { return; }
    weightsBusy = true;
    $("weights-status").textContent = "Saving...";
    api("PUT", "/api/weights", { weights: defs.weights, sidegrade: defs.sidegrade })
      .then(function (doc) {
        fillWeights(doc);
        $("weights-status").textContent = "Back to the defaults.";
        showCardPage($("weightsbox"), "main", cardHeading($("weightsbox")));
      }).catch(function () {
        $("weights-status").textContent = "Not reset. Try again.";
      }).then(function () { weightsBusy = false; });
  }

  function fillBand(doc) {
    var sg = (doc && doc.sidegrade) || {};
    [["weights-abs", sg.abs], ["weights-pct", sg.pct]].forEach(function (p) {
      if ($(p[0]) !== document.activeElement) {
        $(p[0]).value = p[1] === undefined ? "" : String(p[1]);
      }
    });
  }

  function loadWeights() {
    api("GET", "/api/weights").then(fillWeights).catch(function () {
      $("weights-status").textContent = "Can't load the weights. Is AshLight running?";
    });
  }

  function saveWeights(e) {
    if (weightsBusy) { weightsAgain = true; return; }
    var rows = [];
    Array.prototype.forEach.call($("weights-list").querySelectorAll("input[data-key]"),
      function (inp) { rows.push({ key: inp.getAttribute("data-key"), value: inp.value }); });
    var nk = $("weights-new-key").value.trim();
    var nv = $("weights-new-value").value;
    var numOk = nv !== "" && isFinite(parseFloat(nv));
    var adding = !!nk && numOk;
    var target = e && e.target;
    if ((nk || nv !== "") && !adding &&
        (target === $("weights-new-key") || target === $("weights-new-value"))) {
      // half a new row: wait for the other field, save nothing yet
      $("weights-status").textContent = nk ? "Add the points to add this stat."
                                           : "Add the stat name to add these points.";
      return;
    }
    if (adding) { rows.push({ key: nk, value: nv }); }
    weightsBusy = true;
    $("weights-status").textContent = "Saving...";
    api("PUT", "/api/weights", T.weightsDoc(rows, $("weights-abs").value, $("weights-pct").value))
      .then(function (doc) {
        fillWeights(doc);
        if (adding) {
          $("weights-new-key").value = "";
          $("weights-new-value").value = "";
        }
        $("weights-status").textContent = snap && snap.eval
          ? "Saved. The last item was checked again." : "Saved.";
      }).catch(function () {
        $("weights-status").textContent = "Not saved. Check that each value is a number, then try again.";
      }).then(function () {
        weightsBusy = false;
        if (weightsAgain) { weightsAgain = false; saveWeights(); }
      });
  }

  /* ---- DATA-NINJA-UI / PRICE-1-UI (decision 0016): the one web-data
     opt-in, poe.ninja currency values and the last price check. Rates are
     polled from the local core every few minutes (the core itself asks
     poe.ninja at most once an hour); no refresh button. */
  var P = window.ALPrices; // web/prices.js: pure view helpers
  var RATES_POLL_MS = 5 * 60 * 1000;
  var ratesDoc = null;
  var webOn = false;
  var webBusy = false;
  var ratesAgain = null;
  var priceShown = null;

  function fillWebData(doc) {
    var v = P.webDataView(doc);
    webOn = v.on;
    $("webdata-on").checked = v.on;
    return v;
  }

  function loadWebData() {
    api("GET", "/api/web-data").then(function (doc) {
      $("webdata-status").textContent = fillWebData(doc).status;
      renderPrice(snap ? snap.price : null, true);
    }).catch(function () {
      $("webdata-status").textContent = "Can't load the web data setting. Is AshLight running?";
    });
  }

  /* After a saved web-data choice (the Settings switch or the
     TC-LINK-RECOVER confirm): the switch, its status and the prices. */
  function webDataSaved(doc) {
    fillWebData(doc);
    $("webdata-status").textContent = P.savedText(webOn);
    renderPrice(snap ? snap.price : null, true);
    loadRates();
  }

  function saveWebData() {
    if (webBusy) { return; }
    var want = $("webdata-on").checked;
    webBusy = true;
    $("webdata-status").textContent = "Saving...";
    api("POST", "/api/web-data", { enabled: want }).then(function (doc) {
      webDataSaved(doc);
    }).catch(function () {
      $("webdata-on").checked = webOn; // back to what is really saved
      $("webdata-status").textContent = "Not saved. Try again.";
    }).then(function () { webBusy = false; });
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
    var v = P.ratesView(ratesDoc);
    setPill($("rates-pill"), v.pill.state, v.pill.glyph, v.pill.word);
    $("rates-credit").textContent = v.credit;
    $("rates-unit").textContent = v.rows.length
      ? ", in " + v.primary + (v.league ? ", league " + v.league : "") : "";
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
      if (typeof doc.web_data === "boolean" && !webBusy && doc.web_data !== webOn) {
        fillWebData({ web_data: doc.web_data });
      }
      renderRates();
      renderPrice(snap ? snap.price : null, true);
      // a refresh the core just started finishes in a few seconds
      if (doc.refreshing) { ratesAgain = setTimeout(loadRates, 3000); }
    }).catch(function () {
      setPill($("rates-pill"), "failed", "[x]", "can't load currency values - is AshLight running?");
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

  /* ---- GFX-ADVISOR: read on the first open of the panel (a click on the
     dashboard, so the game is not focused then); kept for the session. */
  var gfxLoaded = false;

  function renderGfx(doc) {
    var v = T.gfxView(doc);
    var hw = document.createDocumentFragment();
    v.hardware.forEach(function (h) {
      var row = el("div", "kv-row");
      row.appendChild(el("dt", "", h.label));
      row.appendChild(el("dd", "", h.value));
      hw.appendChild(row);
    });
    $("gfx-hw").replaceChildren(hw);
    $("gfx-tier").textContent = v.ok ? v.tierText : v.error;
    var warn = document.createDocumentFragment();
    v.warnings.forEach(function (w) { warn.appendChild(el("li", "", w)); });
    $("gfx-warn").replaceChildren(warn);
    var list = document.createDocumentFragment();
    v.settings.forEach(function (s) {
      var li = el("li");
      var line = el("p", "gfx-line");
      line.appendChild(el("span", "gfx-name", s.setting));
      line.appendChild(el("strong", "gfx-value", s.value));
      li.appendChild(line);
      li.appendChild(el("p", "muted gfx-why", s.why.charAt(0).toUpperCase() + s.why.slice(1) + "."));
      list.appendChild(li);
    });
    $("gfx-list").replaceChildren(list);
    $("gfx-body").hidden = false;
  }

  function openGfx() {
    if (!$("gfx").open || gfxLoaded) { return; }
    gfxLoaded = true;
    $("gfx-status").textContent = "Checking this computer's hardware...";
    api("GET", "/api/gfx").then(function (doc) {
      renderGfx(doc);
      $("gfx-status").textContent = "";
    }).catch(function () {
      gfxLoaded = false;
      $("gfx-status").textContent = "Can't check right now. Is AshLight running? Close and open this panel to try again.";
    });
  }

  /* ---- TEST-WEB-REGISTRY (F-135): the dashboard panels. Each paint, tick
     and wire that render(), tick() and start() called in one sequence is
     one registered entry; the explicit order keeps today's paint order and
     so the order of the live-region announcements. render() calls
     paint(s, c) (the state push and the picked character's view), tick()
     calls tick(snap, now, until), start() calls wire(). A throwing panel
     is caught and said once on the console; the panels after it still
     run. A new card registers its own entry; no shared function changes. */
  A.register({
    name: "build",
    order: 10,
    paint: function (s) {
      // MATH-NEXT-LOOK: a new PoB-scored item check may add PoB stat weights
      // for a slot, so the build view is read again (no click)
      var pobEval = s.eval && s.eval.calc && s.eval.calc.source === "pob" ? s.eval.id : null;
      var newWeights = pobEval !== null && pobEval !== pobEvalId;
      if (pobEval !== null) { pobEvalId = pobEval; }
      var newCalc = !!(s.build && s.build.calc_rev && s.build.calc_rev !== calcRev);
      if (s.build) { calcRev = s.build.calc_rev || null; }
      if (s.build && s.build.rev !== buildRev) {
        buildRev = s.build.rev;
        loadBuild();
      } else if (newCalc && buildDoc) {
        loadBuild();
      } else if (newWeights && buildDoc) {
        loadBuild();
      } else {
        renderBuildYou();
      }
    },
    wire: function () {
      $("build-paste").addEventListener("paste", function () { setTimeout(pasteBuild, 0); });
      $("build-paste").addEventListener("change", pasteBuild);
      $("link-offer").addEventListener("click", linkOffer);
      $("link-yes").addEventListener("click", linkConfirm);
      $("link-no").addEventListener("click", linkCancel);
      $("build-copy").addEventListener("click", copyBuild);
      $("buildfile-save").addEventListener("click", saveBuildFile);
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
    // the opt-in is region C's setup card (web/setupcard.js); the footer
    // keeps the opt-out until PLAY-TD-21A-SETTINGS-RAIL moves it
    paint: function (s) {
      var tl = s.tailer || {};
      $("consent-no").hidden = !tl.consented;
      $("events-empty").textContent = D.emptyText(!!tl.consented);
      paintLedger(tl);
    },
    wire: function () {
      $("consent-no").addEventListener("click", stopReading);
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
  // the tools and settings that only wire the player's clicks
  A.register({
    name: "layout",
    order: 200,
    wire: function () {
      $("layout-form").addEventListener("change", saveLayout);
      $("layout-form").addEventListener("submit", function (e) { e.preventDefault(); });
      ["layout-scale", "layout-opacity"].forEach(function (id) {
        $(id).addEventListener("input", function () {
          $(id + "-out").textContent = Math.round(parseFloat($(id).value) * 100) + "%";
        });
      });
    }
  });
  A.register({
    name: "filter",
    order: 210,
    wire: function () {
      $("filter-download").addEventListener("click", downloadFilter);
      $("filter-merge-file").addEventListener("change", mergeFilter);
    }
  });
  A.register({
    name: "weights",
    order: 220,
    wire: function () {
      $("weights-form").addEventListener("change", saveWeights);
      $("weights-form").addEventListener("submit", function (e) { e.preventDefault(); });
      $("weights-reset").addEventListener("click", resetWeights);
      window.addEventListener("resize", showWeightPage);
    }
  });
  A.register({
    name: "gfx",
    order: 230,
    wire: function () { $("gfx").addEventListener("toggle", openGfx); }
  });
  A.register({
    name: "restart-overlay",
    order: 240,
    wire: function () { wireRestartOverlay(); }
  });
  A.register({
    name: "webdata",
    order: 250,
    wire: function () {
      // TC-LINK-RECOVER: Settings shows the one opt-in sentence the confirm shows
      $("webdata-sentence").textContent = T.WEB_DATA_OPT_IN;
      $("webdata-form").addEventListener("change", saveWebData);
      $("webdata-form").addEventListener("submit", function (e) { e.preventDefault(); });
    }
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

  /* TC-SNAP-UI: the game-data credit in the footer, read on every connect,
     so a snapshot made by the build shows up without a click.
     RUN-BUILD-STAMP-UI: the same read fills the footer's version line and
     the Settings About fold, so a core restart on a new build shows it. */
  function loadDataCredit() {
    api("GET", "/api/version").then(function (doc) {
      var text = D.dataCreditText(doc);
      var p = $("data-credit");
      p.textContent = text;
      p.hidden = !text;
      $("credits").hidden = !text; // UI-GLANCE: the footer fold around it
      var ver = versionText(doc);
      if (ver) {
        $("build-line").textContent = ver;
        $("build-line").hidden = false;
        $("about-version").textContent = ver;
      }
    }).catch(function () { /* keep the last line; the next connect retries */ });
  }

  function connect() {
    if (!token) {
      setLink("notoken");
      return;
    }
    loadLayout();
    loadWeights();
    loadWebData();
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
