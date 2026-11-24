/* AshLight dashboard panel: the 'Restart overlay' row and the 'Start with
   Windows' row beside it in Settings > Appearance and tools, moved out of
   web/app.js by TEST-WEB-PANELS-C2 (finding F-135; research 0047 R4 (c)).

   DESKTOP-CLIENT (decision 0041): inside the desktop client the page gets
   one action, window.alClient.restartOverlay (app/client/preload.js); in
   a browser there is none and the button stays hidden.
   REL-AUTOSTART-SETTINGS: the 'Start with Windows' row (web/autostart.js;
   the client's three autostart actions).

   The block moved verbatim: restartSaid and wireRestartOverlay, plus the
   "restart-overlay" entry's wire. MERGE-SEAMS F5: the restart note clears
   on the next state push; the panel hands that step to app.js's render()
   through host.onPush, which runs it on every push before the
   same-version return. What the panel shares with the page ($, setText,
   the snapshot) is reached through window.ALApp.host, which app.js sets
   before start().

   The click only: no clipboard, no timer, no request.

   UMD like web/fmt.js: CommonJS for node --test (app/test/panels.test.js)
   exports {name, order, panel}; in the page the file registers itself with
   window.ALApp (web/registry.js) as "restart-overlay", order 240: the name
   and order app.js gave this entry before the move, so the wire order of
   today's page is kept. The core links this file at the panels marker of
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

  var NAME = "restart-overlay";
  var ORDER = 240; // app.js gave "restart-overlay" 240 before the move

  /* the page's shared helpers (window.ALApp.host, set by web/app.js) */
  var $, setText, getSnap;
  var bound = false;

  function bind(host) {
    if (bound) { return; }
    if (!host || typeof host.$ !== "function") {
      throw new TypeError("restart-overlay: no page host (web/app.js sets ALApp.host)");
    }
    $ = host.$; setText = host.setText; getSnap = host.getSnap;
    bound = true;
  }

  var restartSaid = false; // the restart note shows until the next state push
  function wireRestartOverlay() {
    var c = window.alClient;
    if (!c || typeof c.restartOverlay !== "function") { return; }
    $("restart-overlay-row").hidden = false;
    $("restart-overlay").addEventListener("click", function () {
      var snap = getSnap();
      c.restartOverlay();
      restartSaid = true;
      setText($("restart-overlay-said"), snap && snap.game_idle
        ? "Restarting the overlay. It stays hidden while the game looks closed."
        : "Restarting the overlay.");
    });
  }

  /* MERGE-SEAMS F5: run by app.js's render() on every state push */
  function onPush() {
    if (restartSaid) { restartSaid = false; setText($("restart-overlay-said"), ""); }
  }

  function wire(host) {
    host.onPush(onPush);
    wireRestartOverlay();
    if (window.ALAutostart) { window.ALAutostart.wire(document, window.alClient); }
  }

  /* The registry entry; getHost is read on the first wire, when web/app.js
     has run (it is the last script). */
  function panel(getHost) {
    return {
      name: NAME,
      order: ORDER,
      wire: function () { var h = getHost(); bind(h); wire(h); }
    };
  }

  return { name: NAME, order: ORDER, panel: panel };
}));
