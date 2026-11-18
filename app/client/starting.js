/* DESKTOP-CLIENT: the main process loads this page with #failed when the
   core did not answer in time; the page then shows the failure line. */
(function () {
  "use strict";
  if (location.hash === "#failed") {
    document.getElementById("starting").hidden = true;
    document.getElementById("failed").hidden = false;
  }
}());
