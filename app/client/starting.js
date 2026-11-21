/* DESKTOP-CLIENT: the main process loads this page with #failed when the
   core did not answer in time; the page then shows the failure line.
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
  try { reason = new URLSearchParams(location.search).get("reason") || ""; } catch (e) { reason = ""; }
  reason = reason.trim();
  if (reason && reason.length <= MAX && /^[\x20-\x7e]+$/.test(reason)) {
    document.getElementById("reason-line").textContent = reason;
    document.getElementById("reason").hidden = false;
  } else {
    document.getElementById("failed").hidden = false;
  }
}());
