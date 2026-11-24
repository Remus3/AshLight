/* AshLight dashboard panel: Settings' change-key fields, the 'Overlay
   shows' group and the settings export / import, moved out of web/app.js
   by TEST-WEB-PANELS-C2 (finding F-135; research 0047 R4 (c)).

   UX-SETTINGS-IO: the player's clicks (web/settingsio.js does the work).
   OVL-KEYS-WEB: the two change-key fields, saved on change (POST
   /api/hotkeys, web/hotkeys.js), and the key names it paints on every new
   state: every named key is the bound one, and the Play line while the
   overlay is off. OVL-PARTS-WEB: the 'Overlay shows' group, saved on
   change (POST /api/overlay-layout); its first read runs on connect,
   beside the layout's.

   The blocks moved verbatim: the "settingsio" entry's wire and the key
   paint render() ran before the panels. What the panel shares with the
   page (api, token, onConnect) is reached through window.ALApp.host,
   which app.js sets before start().

   The same requests as before, through the modules it wires, and the
   download link's one revoke timer; no clipboard, no live region.

   UMD like web/fmt.js: CommonJS for node --test (app/test/panels.test.js)
   exports {name, order, panel, more, entries}; in the page the file
   registers two entries with window.ALApp (web/registry.js): "settingsio",
   order 260, the name and order app.js gave it before the move, and
   "hotkeys", order 0, before every other panel, where render() painted
   the keys before the panels' loop. The core links this file at the
   panels marker of index.html (TEST-WEB-ASSEMBLE). */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    api.entries(function () { return root.ALApp.host; }).forEach(function (spec) {
      root.ALApp.register(spec);
    });
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var NAME = "settingsio";
  var ORDER = 260; // app.js gave "settingsio" 260 before the move
  var MORE = [["hotkeys", 0]];

  /* the page's shared helpers (window.ALApp.host, set by web/app.js) */
  var api, token, onConnect;
  var bound = false;

  function bind(host) {
    if (bound) { return; }
    if (!host || typeof host.$ !== "function") {
      throw new TypeError("settingsio: no page host (web/app.js sets ALApp.host)");
    }
    api = host.api; token = host.token; onConnect = host.onConnect;
    bound = true;
  }

  function wire() {
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

  /* OVL-KEYS-WEB: every named key is the bound one; the change fields and
     the Play line while the overlay is off (web/hotkeys.js) */
  function paintKeys(s) {
    if (window.ALHotkeys) { window.ALHotkeys.paint(document, s); }
  }

  /* The registry entries; getHost is read on the first wire, when
     web/app.js has run (it is the last script). */
  function panel(getHost) {
    return {
      name: NAME,
      order: ORDER,
      wire: function () { bind(getHost()); wire(); }
    };
  }

  function entries(getHost) {
    return [panel(getHost), { name: "hotkeys", order: 0, paint: paintKeys }];
  }

  return { name: NAME, order: ORDER, panel: panel, more: MORE, entries: entries };
}));
