/* DESKTOP-CLIENT: the main process loads this page with #failed when the
   core did not answer in time; the page then shows the failure line
   (kind=installed: the installed-copy line, UX-FAILED-PAGE-KIND).
   RUN-START-REASON-CLIENT (F-091): when the core left its one-line reason
   (start-error.json, read by app/client/window.js), it arrives as the
   "reason" query value and is shown as text in place of the general line.
   Only printable ASCII up to 300 characters is shown. */
(function () {
  "use strict";
  var MAX = 300;
  if (location.hash !== "#failed") { return; }
  document.getElementById("starting").hidden = true;
  var reason = "";
  var kind = "";
  try {
    var q = new URLSearchParams(location.search);
    reason = q.get("reason") || "";
    kind = q.get("kind") || "";
  } catch (e) { reason = ""; kind = ""; }
  reason = reason.trim();
  if (reason && reason.length <= MAX && /^[\x20-\x7e]+$/.test(reason)) {
    document.getElementById("reason-line").textContent = reason;
    document.getElementById("reason").hidden = false;
  } else {
    // UX-FAILED-PAGE-KIND: an installed copy runs on its own Python, so it
    // gets the repair line; anything else keeps the checkout line
    document.getElementById(kind === "installed" ? "failed-installed" : "failed").hidden = false;
  }
}());
