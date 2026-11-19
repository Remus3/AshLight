/* AshLight dashboard: region I, the item card (stub). PLAY-TD-09A-REGION-HOOK pre-links this
   file in web/index.html so PLAY-TD-16A-ITEMCARD edits only its own files; it
   registers with web/regions.js when it gets its content. Empty until then. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALItemCard = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  return {};
}));
