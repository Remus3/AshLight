/* AshLight dashboard panel: the stat weights editor (the Item scoring card),
   moved out of web/app.js by TEST-WEB-PANELS-B (finding F-135; research
   0047 R4 (c)). Saves on change (PUT /api/weights); the first read (GET
   /api/weights) runs from connect() through the host's onConnect, as
   before the move.

   The block moved verbatim: the weights state, weightLabel, pointsText,
   changedRows, bandLine, weightPager, showWeightPage, fillWeights,
   resetWeights, fillBand, loadWeights and saveWeights, plus the "weights"
   entry's wire. The edits: the page's snap is read through the host's
   getSnap(), and textRow is this file's own one-line copy. What the panel
   shares with the page ($, api, el, setLine, the pagers, the card pages) is
   reached through window.ALApp.host, which app.js sets before start().

   Changes and clicks only: no clipboard, no new timer, no new request.
   SAVE-FAIL-SAY (design finding WD-3): a failed save or reset is also said
   in the page's one shared polite line, the header's #tab-news, through
   ALTabs.say (failed() below; design 0001 N6), but only while the card's
   own polite #weights-status is not shown (the card folded, its tab
   hidden): a shown status line speaks for itself, so the words are never
   said twice (review W1).

   UMD like web/fmt.js: CommonJS for node --test (app/test/panels.test.js)
   exports {name, order, panel}; in the page the file registers itself with
   window.ALApp (web/registry.js) as "weights", order 220: the name and order
   app.js gave this entry before the move, so the wire order of today's
   page is kept. The core links this file at the panels marker of
   index.html (TEST-WEB-ASSEMBLE). */
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

  var NAME = "weights";
  var ORDER = 220; // app.js gave "weights" 220 before the move

  /* the page's shared helpers (window.ALApp.host, set by web/app.js) */
  var $, api, getSnap, el, setLine, linkPager, sizeClass, showCardPage, cardHeading;
  var onConnect;
  var T = null; // web/tc.js: pure view helpers
  var P = null; // web/prices.js: pure view helpers
  var bound = false;

  function bind(host) {
    if (bound) { return; }
    if (!host || typeof host.$ !== "function") {
      throw new TypeError("weights: no page host (web/app.js sets ALApp.host)");
    }
    $ = host.$; api = host.api; getSnap = host.getSnap; el = host.el;
    setLine = host.setLine; linkPager = host.linkPager; sizeClass = host.sizeClass;
    showCardPage = host.showCardPage; cardHeading = host.cardHeading;
    onConnect = host.onConnect;
    T = window.ALTc;
    P = window.ALPrices;
    bound = true;
  }

  function textRow(s) { return { text: s }; }

  /* True while the player can see the status line: it exists, it is laid
     out (offsetParent is null under any display: none, a hidden tab panel
     included) and no folded card or hidden element holds it. */
  function statusShown(node) {
    if (!node || node.offsetParent === null) { return false; }
    return !(typeof node.closest === "function" &&
      node.closest("[data-collapsed=\"true\"], [hidden]"));
  }

  /* A failed save or reset: the card's status line (itself a polite
     region), and the same words in the header's polite #tab-news
     (ALTabs.say) only while that line is not shown, so they are said once;
     a page without tabs says only the status line. */
  function failed(text) {
    var line = $("weights-status");
    if (line) { line.textContent = text; }
    if (statusShown(line)) { return; }
    var t = window.ALTabs;
    if (t && typeof t.say === "function") { t.say(document, text); }
  }

  /* Stat weights editor: saves on change (PUT /api/weights). */
  var weightsBusy = false;
  var weightsAgain = false; // a change arrived while a save was in flight

  /* PLAY-TD-19D-ITEMS-GRID: the Item scoring card. Its first page lists
     only the weights changed from the defaults (the core's `changed`);
     the Stat weights page shows every weight, 10 a page (8 compact): all
     rows stay in the form and a page only hides the others, so focus, a
     value being typed and every save keep working across pages. */
  /* rows of 24 px (a 24 px number box) plus the card's count and status
     lines fit 8 a page in the full class and 5 in the compact one (cards
     322 and 256 px tall at s = 1; TC-WEIGHTS-DELTA-UI gave the count line
     one row) */
  var WEIGHT_PAGE = { full: 8, compact: 5 };
  var CHANGED_ROWS = { full: 6, compact: 4 };
  var weightsDoc = null;
  var weightsPageAt = 0;
  var weightsBar = null;
  var focusAfter = null; // the stat whose row Reset was pressed

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
      return inputs[i].getAttribute("data-key") === r.key &&
        inputs[i].getAttribute("data-mark") === rowMark(r);
    });
    fillBand(doc);
    var changed = changedRows(doc);
    linkPager("weights-changed", "changed weights", CHANGED_ROWS, {
      rows: (changed.length ? changed : ["Every weight is at its default."]).map(textRow),
      text: function (r) { return r.text; }
    });
    setLine($("weights-band-line"), bandLine(doc));
    setLine($("weights-count"), T.changedCount(doc));
    if (same) {
      rows.forEach(function (r, i) {
        if (inputs[i] !== document.activeElement) { inputs[i].value = String(r.weight); }
      });
      return;
    }
    var focusKey = focusAfter || (document.activeElement && document.activeElement.getAttribute
      ? document.activeElement.getAttribute("data-key") : null);
    focusAfter = null;
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
      inp.setAttribute("data-mark", rowMark(r));
      inp.setAttribute("inputmode", "decimal");
      li.appendChild(lab);
      if (r.changed) {
        // TC-WEIGHTS-DELTA-UI: a changed row says so in words, with the
        // default beside, and gets its own Reset
        li.className = "weights-changed-row";
        var mark = el("span", "weights-default muted", defaultText(r));
        mark.id = id + "-def";
        inp.setAttribute("aria-describedby", mark.id);
        li.appendChild(mark);
      }
      li.appendChild(inp);
      if (r.changed) { li.appendChild(rowReset(r)); }
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

  /* What a row's mark says: changed or not, and its default. A changed
     mark rebuilds the row; a new value alone does not. */
  function rowMark(r) {
    return r.changed ? "c" + (r.def === null ? "" : String(r.def)) : "";
  }

  function defaultText(r) {
    return r.def === null ? "added" : "default " + P.num(r.def);
  }

  /* One row's Reset: a changed default goes back to its default, an added
     stat goes away; saved as one PUT with every other row as typed. */
  function rowReset(r) {
    var b = el("button", "secondary btn-24 weights-row-reset", "Reset");
    b.type = "button";
    b.setAttribute("aria-label", r.def === null
      ? "Reset " + r.label + ": remove this added stat"
      : "Reset " + r.label + " to the default, " + pointsText(r.def));
    b.addEventListener("click", function () { resetOne(r.key); });
    return b;
  }

  function formRows() {
    var rows = [];
    Array.prototype.forEach.call($("weights-list").querySelectorAll("input[data-key]"),
      function (inp) { rows.push({ key: inp.getAttribute("data-key"), value: inp.value }); });
    return rows;
  }

  function resetOne(key) {
    var defs = weightsDoc && weightsDoc.defaults;
    if (!defs || weightsBusy) { return; }
    weightsBusy = true;
    $("weights-status").textContent = "Saving...";
    var rows = T.resetRow(formRows(), defs, key);
    api("PUT", "/api/weights", T.weightsDoc(rows, $("weights-abs").value, $("weights-pct").value))
      .then(function (doc) {
        focusAfter = key;
        fillWeights(doc);
        focusAfter = null;
        $("weights-status").textContent = "Back to the default.";
      }).catch(function () {
        failed("Not reset. Try again.");
      }).then(function () {
        weightsBusy = false;
        if (weightsAgain) { weightsAgain = false; saveWeights(); }
      });
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
        failed("Not reset. Try again.");
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
    var rows = formRows();
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
        $("weights-status").textContent = getSnap() && getSnap().eval
          ? "Saved. The last item was checked again." : "Saved.";
      }).catch(function () {
        failed("Not saved. Check that each value is a number, then try again.");
      }).then(function () {
        weightsBusy = false;
        if (weightsAgain) { weightsAgain = false; saveWeights(); }
      });
  }

  function wire() {
    $("weights-form").addEventListener("change", saveWeights);
    $("weights-form").addEventListener("submit", function (e) { e.preventDefault(); });
    $("weights-reset").addEventListener("click", resetWeights);
    window.addEventListener("resize", showWeightPage);
    onConnect(loadWeights);
  }

  /* The registry entry; getHost is read on the first wire, when web/app.js
     has run (it is the last script). */
  function panel(getHost) {
    return {
      name: NAME,
      order: ORDER,
      wire: function () { bind(getHost()); wire(); }
    };
  }

  return { name: NAME, order: ORDER, panel: panel };
}));
