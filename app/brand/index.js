"use strict";
/* BRAND-ICON (docs/design/0005-brand-mark.md): the one place the Electron
   side finds AshLight's icon files. The files are rendered from
   assets/brand/*.svg by tools/make_icons.py and tracked at stable paths:
     app/assets/icon.ico      shortcut / window icon (16..256)
     app/assets/tray-16.png   tray, 100 percent scale
     app/assets/tray-32.png   tray, 200 percent scale
     app/assets/icon-256.png  large window / about icon
   Node built-ins only; the Electron nativeImage module is passed in so
   this file loads under plain node for tests. */
const fs = require("fs");
const path = require("path");

const ASSETS = path.join(__dirname, "..", "assets");
const ICO = path.join(ASSETS, "icon.ico");
const TRAY_16 = path.join(ASSETS, "tray-16.png");
const TRAY_32 = path.join(ASSETS, "tray-32.png");
const ICON_256 = path.join(ASSETS, "icon-256.png");

/* A nativeImage for the tray and window: 16 px at scale 1, 32 px at 2. */
function trayImage(nativeImage) {
  const img = nativeImage.createEmpty();
  img.addRepresentation({ scaleFactor: 1, buffer: fs.readFileSync(TRAY_16) });
  img.addRepresentation({ scaleFactor: 2, buffer: fs.readFileSync(TRAY_32) });
  return img;
}

module.exports = { ASSETS, ICO, TRAY_16, TRAY_32, ICON_256, trayImage };
