/* AshLight dashboard. Vanilla JS, no framework, no CDN, no inline script.
   The per-start token arrives in the URL fragment (#token=...), is kept in
   sessionStorage and sent as X-AL-Token (fetch) or ?token= (EventSource,
   which cannot set headers). Every text from the log goes in via
   textContent, never innerHTML. */
(function () {
  "use strict";

  var D = window.ALDash; // web/status.js: pure view helpers
  var KEY = "al.token";
  var token = readToken();
  var snap = null;
  var offset = 0; // client clock minus server clock, seconds
  var renderedVersion = -1;
  var es = null;
  var ticker = null;
  var linkLive = false; // the state feed is live right now
  var everLive = false; // ... and was live at least once on this page

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

  function pad(n) { return n < 10 ? "0" + n : String(n); }

  function duration(s) {
    if (s === null || s === undefined || !isFinite(s)) { return "--:--"; }
    s = Math.max(0, Math.floor(s));
    var h = Math.floor(s / 3600);
    var m = Math.floor((s % 3600) / 60);
    var sec = s % 60;
    return h > 0 ? h + ":" + pad(m) + ":" + pad(sec) : m + ":" + pad(sec);
  }

  function clock(ts) {
    var d = new Date(ts * 1000);
    return pad(d.getHours()) + ":" + pad(d.getMinutes());
  }

  function setPill(el, state, glyph, word) {
    el.setAttribute("data-state", state);
    el.querySelector(".glyph").textContent = glyph;
    el.querySelector(".word").textContent = word;
  }

  function serverNow() { return Date.now() / 1000 - offset; }

  /* While the feed is down the timers stop, so a stale page never looks
     like it is still counting (UI-REVIEW-2). */
  function tick() {
    if (!snap || document.hidden || !linkLive) { return; }
    var now = serverNow();
    $("zone-time").textContent = snap.zone_entered_at ? duration(now - snap.zone_entered_at) : "--:--";
    // Before the Client.txt opt-in there is no play session to time.
    $("session").textContent = snap.tailer && snap.tailer.consented
      ? duration(now - snap.session_started_at) : "--:--";
    // HUD-ACT: the open act split counts up with the zone timer.
    if (window.ALActs) { window.ALActs.paint(document, snap.acts, now, false); }
    // UTIL-MAPS: the open map's time counts up while the player is in it.
    if (window.ALRuns) { window.ALRuns.paint(document, snap, now, false); }
  }

  function renderEvents(rows) {
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

  var renderedTrades = "";
  var TR = window.ALTrades; // web/trades.js: pure trade list helpers
  var shownTradeIds = null; // null until the first paint (F6)

  function renderTrades(rows) {
    var ids = TR.tradeIds(rows);
    var key = JSON.stringify(ids);
    if (key === renderedTrades) { return; }
    renderedTrades = key;
    var prevIds = shownTradeIds;
    shownTradeIds = ids;
    var frag = document.createDocumentFragment();
    for (var i = rows.length - 1; i >= 0; i--) {
      var t = rows[i];
      var line = D.tradeLine(t);
      var li = document.createElement("li");
      var tm = document.createElement("span");
      tm.className = "time mono";
      tm.textContent = clock(t.at);
      var what = document.createElement("span");
      what.className = "what";
      what.textContent = line.what;
      var where = document.createElement("span");
      where.className = "where";
      where.textContent = line.where;
      var worth = P.tradeAbout(t, ratesDoc); // DATA-NINJA-UI: "about N <primary>"
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "secondary";
      btn.textContent = "Dismiss";
      btn.setAttribute("aria-label", "Dismiss trade request from " + (t.from || "unknown player"));
      btn.addEventListener("click", dismissTrade.bind(null, t.id));
      li.appendChild(tm);
      li.appendChild(what);
      li.appendChild(where);
      if (worth.text) {
        var ab = document.createElement("span");
        ab.className = "about";
        ab.textContent = worth.text;
        ab.title = worth.title;
        li.appendChild(ab);
      }
      li.appendChild(btn);
      frag.appendChild(li);
    }
    $("trade-list").replaceChildren(frag);
    $("trades").hidden = rows.length === 0;
    /* UX-REVIEW F6: a new request is said once in the polite region. */
    TR.showStatus($("trade-status"), prevIds, rows);
  }

  /* Dashboard-only: dismissing never sends anything to the game. */
  function dismissTrade(id) {
    $("trade-status").textContent = "";
    api("POST", "/api/trade-dismiss", id === null ? { all: true } : { id: id })
      .then(function (res) { render(res.state); })
      .catch(function (e) {
        $("trade-status").textContent = "Not dismissed. Try again.";
        console.warn("dismiss failed: " + e.message);
      });
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
  var buildDoc = null;
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

  function appendLinks(parent, list, name) {
    list.forEach(function (l) {
      parent.appendChild(document.createTextNode(" "));
      parent.appendChild(linkOut(l, name));
    });
  }

  function loadBuild() {
    api("GET", "/api/build").then(function (doc) {
      buildDoc = doc;
      renderBuild();
    }).catch(function () {
      $("build-status").textContent = "Can't load the build. Is AshLight running?";
    });
  }

  function renderBuildYou() {
    if (!buildDoc) { return; }
    var v = T.buildView(buildDoc, snap);
    if (v.loaded) { $("build-you").textContent = v.you; }
  }

  function renderBuild() {
    var v = T.buildView(buildDoc, snap);
    $("build-view").hidden = !v.loaded;
    $("build-empty").hidden = v.loaded;
    $("build-paste-label").textContent = v.loaded ? "Paste another build" : "Paste a build";
    if (!v.loaded) {
      $("build-empty").textContent = v.empty;
      return;
    }
    $("build-name").textContent = v.title;
    $("build-level").textContent = v.levelLine;
    $("build-you").textContent = v.you;
    var dl = document.createDocumentFragment();
    v.stats.forEach(function (s) {
      var row = el("div", "kv-row");
      row.appendChild(el("dt", "", s.label));
      row.appendChild(el("dd", "mono", s.value));
      dl.appendChild(row);
    });
    $("build-stats").replaceChildren(dl);
    $("build-stats-empty").hidden = v.stats.length > 0;

    var gear = document.createDocumentFragment();
    v.gear.forEach(function (g) {
      var li = el("li");
      var line = el("p", "gear-line");
      line.appendChild(el("span", "slot", g.slot));
      line.appendChild(el("span", "name", g.name));
      if (g.base) { line.appendChild(el("span", "muted", g.base)); }
      if (g.rarity) { line.appendChild(el("span", "tag", g.rarity)); }
      appendLinks(line, g.links, g.name);
      li.appendChild(line);
      if (g.text) {
        var d = el("details", "item-text");
        d.appendChild(el("summary", "", "Item text"));
        d.appendChild(el("pre", "", g.text));
        li.appendChild(d);
      }
      gear.appendChild(li);
    });
    if (!v.gear.length) { gear.appendChild(el("li", "muted", "No gear in this build.")); }
    $("build-gear").replaceChildren(gear);

    var sk = document.createDocumentFragment();
    v.skills.forEach(function (g) {
      var li = el("li", g.enabled ? "" : "off");
      var head = el("p", "skill-head");
      head.appendChild(el("strong", "", g.label));
      if (g.main) { head.appendChild(el("span", "tag", "main skill")); }
      if (!g.enabled) { head.appendChild(el("span", "tag", "off")); }
      if (g.slot) { head.appendChild(el("span", "muted", g.slot)); }
      li.appendChild(head);
      var gems = el("ul", "gems");
      g.gems.forEach(function (m) {
        var gi = el("li", m.enabled ? "" : "off");
        gi.appendChild(el("span", "", m.name));
        if (m.detail) { gi.appendChild(el("span", "muted", " (" + m.detail + ")")); }
        appendLinks(gi, m.links, m.name);
        gems.appendChild(gi);
      });
      li.appendChild(gems);
      sk.appendChild(li);
    });
    if (!v.skills.length) { sk.appendChild(el("li", "muted", "No skills in this build.")); }
    $("build-skills").replaceChildren(sk);

    var tree = $("build-tree");
    tree.replaceChildren();
    if (v.tree) {
      tree.appendChild(document.createTextNode(v.tree.line + ". "));
      if (v.tree.url) {
        var a = el("a", "out", "Open the tree");
        a.href = v.tree.url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        tree.appendChild(a);
      }
    } else {
      tree.textContent = "No passive tree in this build.";
    }
    $("build-notes-box").hidden = !v.notes;
    $("build-notes").textContent = v.notes;
    $("build-code-out").value = v.code;
  }

  function pasteBuild() {
    var text = $("build-paste").value.trim();
    if (!text || text === lastPaste) { return; }
    lastPaste = text;
    $("build-status").textContent = "Loading the build...";
    var opts = { method: "POST", cache: "no-store",
                 headers: { "X-AL-Token": token, "Content-Type": "application/json" },
                 body: JSON.stringify({ code: text }) };
    fetch("/api/build-code", opts).then(function (r) {
      return r.json().catch(function () { return null; }).then(function (body) {
        var res = T.pasteResult(r.status, body);
        $("build-status").textContent = res.text;
        if (res.ok) {
          $("build-paste").value = "";
          buildDoc = body;
          renderBuild();
        } else {
          lastPaste = ""; // the same text may be pasted again after a fix
        }
      });
    }).catch(function () {
      lastPaste = "";
      $("build-status").textContent = "Not loaded. Can't reach AshLight - is it running?";
    });
  }

  function copyBuild() {
    var code = buildDoc && buildDoc.code;
    if (!code) { return; }
    var out = $("build-code-out");
    var done = function () {
      $("build-copy-status").textContent =
        "Copied. In Path of Building, open Import/Export Build and paste it.";
    };
    var fallback = function () {
      out.hidden = false;
      out.focus();
      out.select();
      $("build-copy-status").textContent = "Select the code above and press Ctrl+C to copy it.";
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(code).then(done, fallback);
    } else {
      fallback();
    }
  }

  /* ---- TC-EVAL-UI: the last item check (from the hotkey press). */
  var evalShown = null;

  function renderEval(ev) {
    var key = ev ? ev.id : null;
    if (key === evalShown) { return; }
    evalShown = key;
    var v = T.evalView(ev, clock);
    $("eval-empty").hidden = !!v;
    $("eval-body").hidden = !v;
    var comps = document.createDocumentFragment();
    if (v) {
      var w = $("eval-word");
      w.textContent = v.word;
      w.setAttribute("data-verdict", v.verdict);
      $("eval-item").textContent = v.item;
      $("eval-sentence").textContent = v.sentence;
      $("eval-calc").textContent = v.calc;
      $("eval-calc").hidden = !v.calc;
      v.comparisons.forEach(function (c) {
        var box = el("div", "eval-comp");
        box.appendChild(el("h3", "sub-h", c.slot || "Slot"));
        // the headline already says the best slot's sentence
        if (c.slot !== ev.slot) { box.appendChild(el("p", "", c.sentence)); }
        if (c.stats && c.stats.length) {
          var ul = el("ul", "eval-stats");
          c.stats.forEach(function (s) {
            var li = el("li");
            li.appendChild(el("span", "stat-text", s.text));
            li.appendChild(el("span", "stat-points mono", s.points));
            ul.appendChild(li);
          });
          box.appendChild(ul);
        } else {
          box.appendChild(el("p", "muted", "No stat differences."));
        }
        comps.appendChild(box);
      });
    }
    $("eval-comps").replaceChildren(comps);
    $("eval-unweighted").hidden = !(v && v.unweighted);
    $("eval-unweighted").textContent = v ? v.unweighted : "";
    $("eval-when").textContent = v ? v.when : "";
    // TC-UPGRADE (decision 0017): the player's click opens the upgrade
    // search in their browser; AshLight never opens or fetches it
    var up = v && ev ? P.upgradeView(ev.upgrade) : null;
    $("upgradebox").hidden = !up;
    $("upgrade-sentence").textContent = up ? up.sentence : "";
    var ubox = $("upgrade-link");
    ubox.replaceChildren();
    if (up) {
      var a = el("a", "out", up.text);
      a.href = up.href;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.setAttribute("aria-label", up.label);
      ubox.appendChild(a);
    }
  }

  /* Stat weights editor: saves on change (PUT /api/weights). */
  var weightsBusy = false;
  var weightsAgain = false; // a change arrived while a save was in flight

  /* Update the rows in place when the stat list is the same, so focus and
     a value being typed survive a save; rebuild only when stats were added
     or removed, then put focus back on the same stat. */
  function fillWeights(doc) {
    var rows = T.weightRows(doc);
    var inputs = $("weights-list").querySelectorAll("input[data-key]");
    var same = inputs.length === rows.length && rows.every(function (r, i) {
      return inputs[i].getAttribute("data-key") === r.key;
    });
    fillBand(doc);
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
    if (focusKey) {
      var back = Array.prototype.find.call($("weights-list").querySelectorAll("input[data-key]"),
        function (inp) { return inp.getAttribute("data-key") === focusKey; });
      if (back) { back.focus(); }
    }
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

  function saveWebData() {
    if (webBusy) { return; }
    var want = $("webdata-on").checked;
    webBusy = true;
    $("webdata-status").textContent = "Saving...";
    api("POST", "/api/web-data", { enabled: want }).then(function (doc) {
      fillWebData(doc);
      $("webdata-status").textContent = P.savedText(webOn);
      renderPrice(snap ? snap.price : null, true);
      loadRates();
    }).catch(function () {
      $("webdata-on").checked = webOn; // back to what is really saved
      $("webdata-status").textContent = "Not saved. Try again.";
    }).then(function () { webBusy = false; });
  }

  function renderRates() {
    var v = P.ratesView(ratesDoc);
    setPill($("rates-pill"), v.pill.state, v.pill.glyph, v.pill.word);
    $("rates-unit").hidden = !v.rows.length;
    $("rates-unit").textContent = v.rows.length
      ? "In " + v.primary + (v.league ? ", league " + v.league : "") + "." : "";
    var frag = document.createDocumentFragment();
    v.rows.forEach(function (r) {
      var li = el("li");
      li.appendChild(el("span", "rate-name", r.name));
      li.appendChild(el("span", "rate-value mono", r.value));
      if (r.per) { li.appendChild(el("span", "rate-per muted", "(" + r.per + ")")); }
      frag.appendChild(li);
    });
    $("rates-list").replaceChildren(frag);
    renderMovers();
    $("rates-credit").textContent = v.credit;
    $("rates-attrib").textContent = v.attribution;
  }

  /* UTIL-MOVERS: rising and falling prices from the same /api/rates doc. */
  function moverList(id, rows) {
    var frag = document.createDocumentFragment();
    rows.forEach(function (r) {
      var li = el("li");
      li.appendChild(el("span", "rate-name", r.name));
      li.appendChild(el("span", "rate-value mono", r.change));
      if (r.value) { li.appendChild(el("span", "rate-per muted", "(" + r.value + ")")); }
      frag.appendChild(li);
    });
    $(id).replaceChildren(frag);
    $(id).hidden = !rows.length;
    $(id + "-h").hidden = !rows.length;
  }

  function renderMovers() {
    var m = P.moversView(ratesDoc);
    $("movers").hidden = !m.show;
    $("movers-empty").hidden = !m.empty;
    $("movers-empty").textContent = m.empty;
    moverList("movers-up", m.up);
    moverList("movers-down", m.down);
  }

  function loadRates() {
    if (ratesAgain) { clearTimeout(ratesAgain); ratesAgain = null; }
    api("GET", "/api/rates").then(function (doc) {
      ratesDoc = doc;
      if (typeof doc.web_data === "boolean" && !webBusy && doc.web_data !== webOn) {
        fillWebData({ web_data: doc.web_data });
      }
      renderRates();
      renderedTrades = ""; // conversions may have changed
      if (snap) { renderTrades(snap.trade_requests || []); }
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
    var key = v ? v.key : null;
    if (key === priceShown && !force) { return; }
    priceShown = key;
    $("price-empty").hidden = !!v;
    $("price-body").hidden = !v;
    $("price-empty").textContent = P.priceEmpty(webOn);
    var frag = document.createDocumentFragment();
    if (v) {
      setPill($("price-badge"), v.badge.state, v.badge.glyph, v.badge.word);
      $("price-item").textContent = v.item;
      $("price-sentence").textContent = v.sentence;
      v.rows.forEach(function (r) {
        var li = el("li");
        li.appendChild(el("span", "mono", r.text));
        if (r.about) { li.appendChild(el("span", "muted", r.about)); }
        frag.appendChild(li);
      });
    }
    $("price-list").replaceChildren(frag);
    $("price-when").textContent = v ? v.when : "";
    // PRICE-TRADE-LINK (decision 0017): the player's click opens the trade
    // search in their browser; AshLight never opens or fetches it
    var box = $("price-link");
    box.replaceChildren();
    box.hidden = !(v && v.link);
    if (v && v.link) {
      var a = el("a", "out", v.link.text);
      a.href = v.link.href;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.setAttribute("aria-label", v.link.label);
      box.appendChild(a);
    }
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

  function render(s) {
    snap = s;
    offset = Date.now() / 1000 - s.now;
    if (s.version === renderedVersion) { tick(); return; }
    renderedVersion = s.version;
    if (s.build && s.build.rev !== buildRev) {
      buildRev = s.build.rev;
      loadBuild();
    } else {
      renderBuildYou();
    }
    renderEval(s.eval || null);
    renderPrice(s.price || null, false);

    $("zone").textContent = s.zone || "No zone yet";
    $("hideout").hidden = !s.in_hideout;
    $("level").textContent = s.level === null ? "-" : String(s.level);
    $("who").textContent = s.character
      ? s.character + (s["class"] ? " (" + s["class"] + ")" : "")
      : "character unknown";
    // UTIL-PACE: the core's pace sentence, shown once there is one.
    var paceText = (s.pace && s.pace.text) || "";
    $("pace").textContent = paceText;
    $("pace").hidden = !paceText;
    $("deaths").textContent = String(s.deaths);
    $("levelups").textContent = s.level_ups + (s.level_ups === 1 ? " level-up" : " level-ups");
    $("flags").textContent = D.sessionSub(s.afk, s.dnd, !!(s.tailer && s.tailer.consented));

    var tl = s.tailer || {};
    $("consent").hidden = !!tl.consented;
    $("consent-no").hidden = !tl.consented;
    $("consent-path").textContent = tl.path || "Client.txt (not found yet - start the game once)";
    $("events-empty").textContent = D.emptyText(!!tl.consented);
    showReading();
    renderEvents(s.recent_events || []);
    renderTrades(s.trade_requests || []);
    if (window.ALActs) { window.ALActs.paint(document, s.acts || null, serverNow(), true); }
    if (window.ALRuns) { window.ALRuns.paint(document, s, serverNow(), true); }
    tick();
  }

  function showPill(id, p) { setPill($(id), p.state, p.glyph, p.word); }

  function showReading() {
    showPill("reading", D.readingView(snap ? snap.tailer : null, linkLive));
  }

  function setLink(event) {
    linkLive = event === "open";
    if (linkLive) { everLive = true; }
    showPill("link", D.linkView(event, everLive));
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

  function consent(yes) {
    var err = $("consent-error"); // a polite live region; empty hides nothing
    err.textContent = "";
    api("POST", "/api/consent", { consent: yes }).then(function (res) {
      render(res.state);
    }).catch(function (e) {
      err.textContent = "Your choice was not saved. Try again.";
      console.warn("consent failed: " + e.message);
    });
  }

  /* TC-SNAP-UI: the game-data credit in the footer, read on every connect,
     so a snapshot made by the build shows up without a click. */
  function loadDataCredit() {
    api("GET", "/api/version").then(function (doc) {
      var text = D.dataCreditText(doc);
      var p = $("data-credit");
      p.textContent = text;
      p.hidden = !text;
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
  }

  function start() {
    $("consent-yes").addEventListener("click", function () { consent(true); });
    $("consent-no").addEventListener("click", function () { consent(false); });
    document.addEventListener("visibilitychange", tick);
    $("trade-clear").addEventListener("click", function () { dismissTrade(null); });
    $("layout-form").addEventListener("change", saveLayout);
    $("layout-form").addEventListener("submit", function (e) { e.preventDefault(); });
    ["layout-scale", "layout-opacity"].forEach(function (id) {
      $(id).addEventListener("input", function () {
        $(id + "-out").textContent = Math.round(parseFloat($(id).value) * 100) + "%";
      });
    });
    $("build-paste").addEventListener("paste", function () { setTimeout(pasteBuild, 0); });
    $("build-paste").addEventListener("change", pasteBuild);
    $("build-copy").addEventListener("click", copyBuild);
    $("weights-form").addEventListener("change", saveWeights);
    $("weights-form").addEventListener("submit", function (e) { e.preventDefault(); });
    $("gfx").addEventListener("toggle", openGfx);
    $("webdata-form").addEventListener("change", saveWebData);
    $("webdata-form").addEventListener("submit", function (e) { e.preventDefault(); });
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
