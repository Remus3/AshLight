/* AshLight overlay: placement math (ROADMAP OVL-POS). Pure: no Electron,
   no DOM, no timers. UMD like format.js; main.js requires it.

   Coordinates are Electron DIPs (device-independent pixels). Each display
   carries its own scaleFactor (per-monitor DPI); a window's DIP size is
   multiplied by that factor on the monitor it sits on, so the HUD has the
   same physical size relative to the UI scale on every monitor. The user
   scale multiplies the base HUD size and the page zoom together.

   Displays are addressed by a stable index: sorted left to right, then top
   to bottom (Electron's display ids can change across restarts). A stored
   index whose monitor is gone falls back to the primary display. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALShared = Object.assign(root.ALShared || {}, api);
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var CORNERS = ["top-left", "top-center", "top-right",
                 "bottom-left", "bottom-center", "bottom-right"];
  var DEFAULT = { display: "primary", corner: "top-right", scale: 1.0,
                  opacity: 0.9, margin: 16 };
  /* Floors from design 0001 (DS-OPACITY, DS-SCALE): opacity under 0.9 drops
     overlay text under 4.5:1 over a white scene; scale under 0.95 renders
     13px text under 12px. Old saved layouts clamp to them on load. */
  var LIMITS = { scale: [0.95, 2.0], opacity: [0.9, 1.0], margin: [0, 400] };
  /* Base HUD window at scale 1, in DIPs: the status box plus room for one
     trade card below it. The window is transparent and click-through, so
     the unused part costs nothing. */
  var BASE = { width: 280, height: 176 };

  function clamp(v, lo, hi) { return Math.min(hi, Math.max(lo, v)); }

  function num(v, key) {
    if (typeof v !== "number" || !isFinite(v)) { return DEFAULT[key]; }
    return clamp(v, LIMITS[key][0], LIMITS[key][1]);
  }

  /* Mirror of server/al/layout.py normalize(strict=False): never throws. */
  function normalize(layout) {
    var l = (layout && typeof layout === "object") ? layout : {};
    var display = l.display;
    if (display !== "primary" && !(Number.isInteger(display) && display >= 0 && display < 16)) {
      display = DEFAULT.display;
    }
    return {
      display: display,
      corner: CORNERS.indexOf(l.corner) >= 0 ? l.corner : DEFAULT.corner,
      scale: num(l.scale, "scale"),
      opacity: num(l.opacity, "opacity"),
      margin: Math.round(num(l.margin, "margin"))
    };
  }

  /* Displays in index order: left to right, then top to bottom. */
  function orderDisplays(displays) {
    return (displays || []).slice().sort(function (a, b) {
      return (a.bounds.x - b.bounds.x) || (a.bounds.y - b.bounds.y);
    });
  }

  function pickDisplay(layout, displays, primaryId) {
    var list = orderDisplays(displays);
    if (!list.length) { return null; }
    var primary = list.filter(function (d) { return d.id === primaryId; })[0] || list[0];
    if (layout.display === "primary") { return primary; }
    return list[layout.display] || primary;
  }

  /* Window bounds {x, y, width, height} in integer DIPs, kept fully inside
     the chosen display's work area (taskbar excluded). */
  function computeBounds(layout, displays, primaryId, base) {
    var l = normalize(layout);
    var b = base || BASE;
    var d = pickDisplay(l, displays, primaryId);
    var area = d ? d.workArea : { x: 0, y: 0, width: b.width, height: b.height };
    var w = Math.min(Math.round(b.width * l.scale), area.width);
    var h = Math.min(Math.round(b.height * l.scale), area.height);
    var m = Math.min(l.margin, Math.floor((area.width - w) / 2),
                     Math.floor((area.height - h) / 2));
    m = Math.max(0, m);
    var parts = l.corner.split("-");
    var x;
    if (parts[1] === "left") {
      x = area.x + m;
    } else if (parts[1] === "right") {
      x = area.x + area.width - w - m;
    } else {
      x = area.x + Math.floor((area.width - w) / 2);
    }
    var y = parts[0] === "top" ? area.y + m : area.y + area.height - h - m;
    return { x: Math.round(x), y: Math.round(y), width: w, height: h,
             displayId: d ? d.id : null, scaleFactor: d ? (d.scaleFactor || 1) : 1 };
  }

  /* The list main.js writes to ops/runtime/displays.json for the dashboard. */
  function describeDisplays(displays, primaryId) {
    return orderDisplays(displays).map(function (d, i) {
      return { index: i, primary: d.id === primaryId,
               label: (d.label || ("Display " + (i + 1))).slice(0, 80),
               width: d.bounds.width, height: d.bounds.height,
               scale_factor: d.scaleFactor || 1 };
    });
  }

  /* Bottom corners stack the HUD at the bottom of its window. */
  function anchor(layout) {
    return normalize(layout).corner.indexOf("bottom") === 0 ? "bottom" : "top";
  }

  return { CORNERS: CORNERS, LAYOUT_DEFAULT: DEFAULT, LAYOUT_LIMITS: LIMITS, BASE: BASE,
           normalizeLayout: normalize, orderDisplays: orderDisplays,
           pickDisplay: pickDisplay, computeBounds: computeBounds,
           describeDisplays: describeDisplays, anchor: anchor };
}));
