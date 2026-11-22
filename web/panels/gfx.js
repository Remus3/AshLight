/* AshLight dashboard panel: the graphics advisor (GFX-ADVISOR), moved out of
   web/app.js by TEST-WEB-PANELS-B (finding F-135; research 0047 R4 (c)).
   GET /api/gfx is read on the player's first open of the panel (a click
   on the dashboard, so the game is not focused then; decision 0014) and
   kept for the session.

   The block moved verbatim: gfxLoaded, renderGfx and openGfx, plus the
   "gfx" entry's wire. What the panel shares with the page ($, api, el) is
   reached through window.ALApp.host, which app.js sets before start().

   The open click only: no clipboard, no new timer, no new request.

   UMD like web/fmt.js: CommonJS for node --test (app/test/panels.test.js)
   exports {name, order, panel}; in the page the file registers itself with
   window.ALApp (web/registry.js) as "gfx", order 230: the name and order
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

  var NAME = "gfx";
  var ORDER = 230; // app.js gave "gfx" 230 before the move

  /* the page's shared helpers (window.ALApp.host, set by web/app.js) */
  var $, api, el;
  var T = null; // web/tc.js: pure view helpers
  var bound = false;

  function bind(host) {
    if (bound) { return; }
    if (!host || typeof host.$ !== "function") {
      throw new TypeError("gfx: no page host (web/app.js sets ALApp.host)");
    }
    $ = host.$; api = host.api; el = host.el;
    T = window.ALTc;
    bound = true;
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

  function wire() { $("gfx").addEventListener("toggle", openGfx); }

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
