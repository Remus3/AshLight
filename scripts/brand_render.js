"use strict";
/* BRAND-ICON (docs/design/0005-brand-mark.md): renders the brand SVGs to
   PNG with the pinned Electron, offscreen, software raster, scale factor 1.
   Run by tools/make_icons.py only:
     electron scripts/brand_render.js <jobs.json>
   jobs.json: {"tmp": dir, "jobs": [{"svg", "out", "size": [w, h],
   "theme": "light" | "dark"}]}. Each SVG is inlined into a data: page (so
   its own prefers-color-scheme rules apply) and captured at exactly w x h
   with a transparent ground; "tmp" holds only the throwaway profile. No
   network, no game files. */
const fs = require("fs");
const path = require("path");
const { app, BrowserWindow, nativeTheme } = require("electron");

const SPEC = JSON.parse(fs.readFileSync(process.argv[process.argv.length - 1], "utf8"));
/* Profile and caches stay in the throwaway dir (AL sidecar Temp), never in
   the user's roaming profile. */
app.setPath("userData", path.join(SPEC.tmp, "profile"));
app.disableHardwareAcceleration();
app.commandLine.appendSwitch("force-device-scale-factor", "1");
app.commandLine.appendSwitch("in-process-gpu");

function page(svgText, w, h) {
  const svg = svgText.replace(/^<\?xml[^>]*>\s*/, "");
  return "<!doctype html><html><head><meta charset=\"utf-8\">" +
    "<style>html,body{margin:0;padding:0;background:transparent;overflow:hidden}" +
    "svg{display:block;width:" + w + "px;height:" + h + "px}</style>" +
    "</head><body>" + svg + "</body></html>";
}

async function renderOne(job) {
  const [w, h] = job.size;
  nativeTheme.themeSource = job.theme === "light" ? "light" : "dark";
  const html = page(fs.readFileSync(job.svg, "utf8"), w, h);
  const win = new BrowserWindow({
    show: false, width: w, height: h, useContentSize: true, frame: false,
    transparent: true, backgroundColor: "#00000000",
    webPreferences: { offscreen: true, javascript: false, sandbox: true },
  });
  try {
    await win.loadURL("data:text/html;base64," + Buffer.from(html, "utf8").toString("base64"));
    await new Promise((r) => setTimeout(r, 300));
    /* Captures this offscreen page only, never the screen or a game. */
    const img = await win.webContents.capturePage({ x: 0, y: 0, width: w, height: h });
    const got = img.getSize();
    if (got.width !== w || got.height !== h) {
      throw new Error("capture size " + got.width + "x" + got.height + " for " + w + "x" + h);
    }
    fs.writeFileSync(job.out, img.toPNG());
  } finally {
    win.destroy();
  }
}

/* Each job closes its window; the default handler would quit right there. */
app.on("window-all-closed", () => {});

app.whenReady().then(async () => {
  let rc = 0;
  try {
    const spec = SPEC;
    let n = 0;
    for (const job of spec.jobs) {
      await renderOne(job);
      n += 1;
    }
    process.stdout.write("rendered " + n + "\n");
  } catch (err) {
    process.stderr.write("render failed: " + (err && err.message) + "\n");
    rc = 1;
  }
  app.exit(rc);
});
