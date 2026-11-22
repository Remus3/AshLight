/* AshLight dashboard panel: the overlay layout editor (OVL-POS), moved out
   of web/app.js by TEST-WEB-PANELS-B (finding F-135; research 0047 R4 (c)).
   Saved to config/local.json by the core (POST /api/overlay-layout); the
   overlay follows the file. The first read (GET /api/overlay-layout) runs
   from connect() through the host's onConnect, as before the move.

   The block moved verbatim: option, fillLayout, readLayoutForm, saveLayout
   and loadLayout, plus the "layout" entry's wire. The restart-overlay
   button (wireRestartOverlay) stays in web/app.js: its note is cleared by
   render() on every state push, which no panel phase reaches. What the
   panel shares with the page ($, api, onConnect) is reached through
   window.ALApp.host, which app.js sets before start().

   Changes only: no clipboard, no new timer, no new request.

   UMD like web/fmt.js: CommonJS for node --test (app/test/panels.test.js)
   exports {name, order, panel}; in the page the file registers itself with
   window.ALApp (web/registry.js) as "layout", order 200: the name and order
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

  var NAME = "layout";
  var ORDER = 200; // app.js gave "layout" 200 before the move

  /* the page's shared helpers (window.ALApp.host, set by web/app.js) */
  var $, api, onConnect;
  var D = null; // web/status.js: pure view helpers
  var bound = false;

  function bind(host) {
    if (bound) { return; }
    if (!host || typeof host.$ !== "function") {
      throw new TypeError("layout: no page host (web/app.js sets ALApp.host)");
    }
    $ = host.$; api = host.api; onConnect = host.onConnect;
    D = window.ALDash;
    bound = true;
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

  function wire() {
    $("layout-form").addEventListener("change", saveLayout);
    $("layout-form").addEventListener("submit", function (e) { e.preventDefault(); });
    ["layout-scale", "layout-opacity"].forEach(function (id) {
      $(id).addEventListener("input", function () {
        $(id + "-out").textContent = Math.round(parseFloat($(id).value) * 100) + "%";
      });
    });
    onConnect(loadLayout);
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
