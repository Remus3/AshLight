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
  /* OVL-OVERLAY-KEYS (plan 03 section 5.4), mirror of server/al/layout.py:
     the overlay parts the player can switch off, all on by default. A
     failure word (offline, no Client.txt, not reading) is not a part and
     can never be switched off. */
  var PARTS = ["zone", "timer", "level", "deaths", "status", "trade", "item",
               "moment", "hint"];
  var ZONE_GUIDE = ["entry", "always", "never"];
  function defaultParts() {
    var out = {};
    PARTS.forEach(function (name) { out[name] = true; });
    return out;
  }
  var DEFAULT = { display: "primary", corner: "top-right", scale: 1.0,
                  opacity: 0.9, margin: 16, parts: defaultParts(),
                  quiet_town: false, zone_guide: "entry" };
  /* Floors from design 0001 (DS-OPACITY, DS-SCALE): opacity under 0.9 drops
     overlay text under 4.5:1 over a white scene; scale under 0.95 renders
     13px text under 12px. Old saved layouts clamp to them on load. */
  var LIMITS = { scale: [0.95, 2.0], opacity: [0.9, 1.0], margin: [0, 400] };
  /* Base HUD window at scale 1, in DIPs: the status box plus room for one
     trade card below it. The window is transparent and click-through, so
     the unused part costs nothing. */
  var BASE = { width: 280, height: 176 };

  /* UX-DPI: a monitor taller than 1440 physical px at a low Windows scale
     (4K at 100 percent, say) would draw the 13 px secondary line under
     2 mm tall, while the game's own UI grows with the resolution. The HUD
     then grows by itself so its text is never physically smaller than at
     1440p and 100 percent: factor = physical height / scale factor / 1440,
     which is the display's DIP height / 1440, never under 1 (1080p, 1440p and 4K at 150 percent are unchanged), at
     most 2, in 0.05 steps. Zero clicks: it follows the monitor. */
  var AUTO_REF_HEIGHT = 1440;
  var MAX_ZOOM = 2.5;

  function autoScale(display) {
    if (!display || !display.bounds) { return 1; }
    var f = display.bounds.height / AUTO_REF_HEIGHT; // DIPs: physical / scaleFactor
    if (!isFinite(f) || f <= 1) { return 1; }
    return Math.min(2, Math.round(f * 20) / 20);
  }

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
      margin: Math.round(num(l.margin, "margin")),
      parts: parts(l.parts),
      quiet_town: typeof l.quiet_town === "boolean" ? l.quiet_town : DEFAULT.quiet_town,
      zone_guide: ZONE_GUIDE.indexOf(l.zone_guide) >= 0 ? l.zone_guide : DEFAULT.zone_guide
    };
  }

  /* Every part filled in; an unknown name or a non-boolean value is
     dropped and that part keeps its default (on). A fresh object each
     call, so a caller can never change DEFAULT. */
  function parts(value) {
    var out = defaultParts();
    if (!value || typeof value !== "object" || Array.isArray(value)) { return out; }
    PARTS.forEach(function (name) {
      if (Object.prototype.hasOwnProperty.call(value, name)
          && typeof value[name] === "boolean") {
        out[name] = value[name];
      }
    });
    return out;
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
    // the user scale times autoScale, capped at 2.5 (design review F4)
    var zoom = Math.min(MAX_ZOOM, Math.round(l.scale * autoScale(d) * 100) / 100);
    var w = Math.min(Math.round(b.width * zoom), area.width);
    var h = Math.min(Math.round(b.height * zoom), area.height);
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
    return { x: Math.round(x), y: Math.round(y), width: w, height: h, zoom: zoom,
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

  /* UX-REAL-OVERLAY: the overlay opacity as page CSS (main.js insertCSS).
     BrowserWindow.setOpacity left the transparent software-composited
     window invisible on the real desktop, so the window alpha is never
     used. The value is clamped to LIMITS like every other field. */
  function opacityCss(value) {
    var v = num(value, "opacity");
    return "html { opacity: " + (Math.round(v * 100) / 100) + " !important; }";
  }

  return { CORNERS: CORNERS, LAYOUT_DEFAULT: DEFAULT, LAYOUT_LIMITS: LIMITS, BASE: BASE,
           LAYOUT_PARTS: PARTS, ZONE_GUIDE: ZONE_GUIDE,
           opacityCss: opacityCss,
           normalizeLayout: normalize, orderDisplays: orderDisplays,
           pickDisplay: pickDisplay, autoScale: autoScale, computeBounds: computeBounds,
           describeDisplays: describeDisplays, anchor: anchor };
}));
