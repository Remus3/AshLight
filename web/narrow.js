/* AshLight dashboard: narrow side-window layout (UX-NARROW, research 0028
   section 5 item 2, ruling F). Below NARROW_PX the page stays one column,
   live play cards come first and the tool cards move into one folded group
   at the end. The nodes really move (no CSS `order`), so Tab order always
   equals what is on screen. Wider windows get the page's own order back.
   UMD: CommonJS for node --test (app/test/narrow.test.js), window.ALNarrow
   for the page. No live region, no timers, no network, no stored state. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALNarrow = api;
    if (typeof document !== "undefined") {
      document.addEventListener("DOMContentLoaded", function () { api.start(document, root); });
    }
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var NARROW_PX = 520;
  var QUERY = "(max-width: " + NARROW_PX + "px)";
  /* live play cards, in their narrow order (anything not named keeps its
     place among these, after the card it followed) */
  var LIVE = ["consent", "glance", "summarybox", "trades", "trade-status", "actsbox",
    "mapsbox", "deathsbox", "evalbox", "events"];
  /* tool cards, folded together at the end when narrow */
  var TOOLS = ["buildbox", "healthbox", "searchbox", "pricesbox", "watchbox",
    "historybox", "toolsbox"];
  var FOLD_ID = "narrow-tools";
  var FOLD_LABEL = "Build, prices, history and settings";

  /* ids: the main children's keys in page order -> {live, tools, rest}:
     the narrow order. Unknown keys stay with the live cards in page order
     (a new card is never hidden in the fold by accident). */
  function plan(ids) {
    var live = [], tools = [], rest = [];
    ids.forEach(function (id) {
      if (TOOLS.indexOf(id) >= 0) { tools.push(id); return; }
      if (LIVE.indexOf(id) >= 0) { live.push(id); return; }
      rest.push(id);
    });
    live.sort(function (a, b) { return LIVE.indexOf(a) - LIVE.indexOf(b); });
    tools.sort(function (a, b) { return TOOLS.indexOf(a) - TOOLS.indexOf(b); });
    return { live: live, rest: rest, tools: tools };
  }

  function key(node) {
    if (node.id) { return node.id; }
    if (node.classList && node.classList.contains("stats")) { return "glance"; }
    if (node.classList && node.classList.contains("events")) { return "events"; }
    return "";
  }

  function start(doc, win) {
    var main = doc.querySelector("main");
    if (!main || !win || !win.matchMedia) { return null; }
    var original = Array.prototype.slice.call(main.children);
    var fold = doc.createElement("details");
    fold.id = FOLD_ID;
    fold.className = "card narrow-tools";
    var summary = doc.createElement("summary");
    summary.textContent = FOLD_LABEL;
    fold.appendChild(summary);
    var mq = win.matchMedia(QUERY);
    var narrow = false;

    function toNarrow() {
      var byKey = {};
      var keys = [];
      original.forEach(function (n) {
        var k = key(n) || ("node" + keys.length);
        byKey[k] = n;
        keys.push(k);
      });
      var p = plan(keys);
      var active = doc.activeElement;
      p.live.concat(p.rest).forEach(function (k) { main.appendChild(byKey[k]); });
      main.appendChild(fold);
      p.tools.forEach(function (k) { fold.appendChild(byKey[k]); });
      if (active && active !== doc.activeElement && active.focus && fold.contains(active)) {
        fold.open = true;
        active.focus();
      }
    }

    function toWide() {
      var active = doc.activeElement;
      original.forEach(function (n) { main.appendChild(n); });
      if (fold.parentNode) { fold.parentNode.removeChild(fold); }
      if (active && active !== doc.activeElement && active.focus) { active.focus(); }
    }

    function apply() {
      if (mq.matches === narrow) { return; }
      narrow = mq.matches;
      if (narrow) { toNarrow(); } else { toWide(); }
    }
    if (mq.addEventListener) { mq.addEventListener("change", apply); }
    else if (mq.addListener) { mq.addListener(apply); }
    apply();
    return { apply: apply, fold: fold };
  }

  return { plan: plan, start: start, NARROW_PX: NARROW_PX, LIVE: LIVE, TOOLS: TOOLS,
    FOLD_LABEL: FOLD_LABEL };
}));
