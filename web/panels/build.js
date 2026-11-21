/* AshLight dashboard panel: the loaded build (TC-VIEW), moved out of
   web/app.js by TEST-WEB-PANELS-A (finding F-135; research 0047 R4 (c)).
   It follows the core: the state carries a build revision, and a new one
   fetches GET /api/build (no refresh button). Text from the build goes in
   via textContent only.

   The block moved verbatim: loadBuild, sourceLine, renderBuildYou,
   renderBuild, renderBuildFile, tellBuildFile, saveBuildFile, postJson,
   showPaste, pasteBuild, the TC-LINK-RECOVER offer (linkOffer, linkCancel,
   linkConfirm) and copyBuild, plus the "build" panel's paint and its
   build listeners. The one edit: the page's snap is read through the
   host's getSnap(). What it shares with the other cards (el, linkOut, the
   card pages, the pagers, setLine, api, the token) stays in web/app.js and
   is reached through window.ALApp.host, which app.js sets before start().

   Clicks only, as before: the Copy code clipboard WRITE happens only in
   the player's click (decision 0014), the .build file is fetched only on
   the player's click and handed to the browser's downloads (decision
   0034); no clipboard read, no new timer, no new request.

   UMD like web/fmt.js: CommonJS for node --test (app/test/panels.test.js)
   exports {name, order, panel}; in the page the file registers itself with
   window.ALApp (web/registry.js) as "loaded-build", order 9: just before
   app.js's "build" entry (order 10, the cards' page plumbing), so the paint
   and wire order of today's page is kept. The core links this file at the
   panels marker of index.html (TEST-WEB-ASSEMBLE). */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALApp.register(api.panel(function () { return root.ALApp.host; }));
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var NAME = "loaded-build";
  var ORDER = 9; // before app.js "build" (10): today's paint and wire order

  /* the page's shared helpers (window.ALApp.host, set by web/app.js) */
  var $, api, token, getSnap, serverNow, el, linkOut, setLine, linkPager, textPager;
  var cardShown, cardHome, setCardHome, showCardPage, cardHeading, cardOpener;
  var webDataSaved;
  var T = null; // web/tc.js: pure view helpers
  var bound = false;

  function bind(host) {
    if (bound) { return; }
    if (!host || typeof host.$ !== "function") {
      throw new TypeError("loaded-build: no page host (web/app.js sets ALApp.host)");
    }
    $ = host.$; api = host.api; token = host.token; getSnap = host.getSnap;
    serverNow = host.serverNow; el = host.el; linkOut = host.linkOut;
    setLine = host.setLine; linkPager = host.linkPager; textPager = host.textPager;
    cardShown = host.cardShown; cardHome = host.cardHome; setCardHome = host.setCardHome;
    showCardPage = host.showCardPage; cardHeading = host.cardHeading;
    cardOpener = host.cardOpener; webDataSaved = host.webDataSaved;
    T = window.ALTc;
    bound = true;
  }

  var buildRev = null;
  var calcRev = null; // MATH-SKILL-SPLIT / MATH-DEF-BREAKDOWN: PoB calc outputs ready
  var buildDoc = null;
  var pobEvalId = null; // MATH-NEXT-LOOK: the last PoB-scored item check
  var lastPaste = "";

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
    var v = T.buildView(buildDoc, getSnap());
    if (!v.loaded) { return; }
    setLine($("build-level"), v.levelLine);
    setLine($("build-you"), v.you);
    $("build-you").hidden = !v.you;
    setLine($("build-source"), sourceLine(buildDoc));
  }

  var KEY_STATS_SHOWN = 6; // plan 03 section 4: key stats (6)

  function renderBuild() {
    var v = T.buildView(buildDoc, getSnap());
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

  function paint(s) {
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
  }

  function wire() {
    $("build-paste").addEventListener("paste", function () { setTimeout(pasteBuild, 0); });
    $("build-paste").addEventListener("change", pasteBuild);
    $("link-offer").addEventListener("click", linkOffer);
    $("link-yes").addEventListener("click", linkConfirm);
    $("link-no").addEventListener("click", linkCancel);
    $("build-copy").addEventListener("click", copyBuild);
    $("buildfile-save").addEventListener("click", saveBuildFile);
  }

  /* The registry entry; getHost is read on the first paint or wire, when
     web/app.js has run (it is the last script). */
  function panel(getHost) {
    return {
      name: NAME,
      order: ORDER,
      paint: function (s) { bind(getHost()); paint(s); },
      wire: function () { bind(getHost()); wire(); }
    };
  }

  return { name: NAME, order: ORDER, panel: panel };
}));
