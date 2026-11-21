// OVL-CONTRAST-PIXELS (F-144, TD-05): the overlay contrast and width
// budgets measured on a rendered page, not only by arithmetic. Driven by
// tests/test_overlay_pixels.py; every verdict is made in Python, this file
// only measures. Not a node --test file.
//
//   node overlay_pixels.mjs <browser exe> <profile dir> <spec.json>
//
// It opens ONE page: this repository's app/overlay/index.html as a file URL
// (no core, no port, no token: the page renders its offline state and opens
// no connection) in a headless browser, at the overlay window size 280 x 176
// and each device pixel ratio the spec names. Per CSS variant (the page's
// own overlay.css, or a fixture copy swapped in through a constructed
// stylesheet) it:
//   - sets the plate alpha knob --al-plate-a to the spec's alpha (0.80, the
//     floor);
//   - writes the spec's worst-case fixture lines into the real DOM (HUD
//     line 2 through the page's own ALShared.hudLine2) and reads each row's
//     rendered width, clientWidth and scrollWidth, and those of its parts;
//   - paints, in an in-page canvas at the same device pixel ratio, the
//     backdrop (white, or a 2 px white / black checker), the element's own
//     computed plate colour, its computed text-shadow halo and its text in
//     its computed font and colour, as one layer composited with the page
//     opacity, then reads the canvas pixels and reports the mean luminance
//     of the brightest 3 percent of the glyph box against the brightest
//     plate pixel away from the text (the far plate).
// Limit (adjudicator ruling 2026-11-21): the contrast half is canvas text
// with the real computed styles and the real font rasteriser, not the
// composited DOM; no page image is taken (the one image path stays
// app/test/cdp/capture.mjs), nothing reads the screen, the game or a window.
// Exit 0 prints {"ok": true, "runs": [...]}; 2 = refused (bad argument);
// 3 = browser failure; 4 = watchdog. Node's global WebSocket only.
import { spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";

import { BROWSER_FLAGS, LOOPBACK, checkProfile, isOverlayUrl, overlayUrl } from "./capture.mjs";

const CI = process.env.AL_CI === "1";
const say = (o) => process.stdout.write(JSON.stringify(o) + "\n");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const WIN = Object.freeze({ width: 280, height: 176 });
const BACKDROPS = Object.freeze(["white", "checker"]);
const MAX_CSS = 256 * 1024;

class Refused extends Error {}
const refuse = (why) => { throw new Refused(why); };

/** The checked spec: {dprs, alpha, variants: [{name, css}], line2, cards,
    zone, secondary}. */
export function readSpec(file) {
  let doc;
  try { doc = JSON.parse(fs.readFileSync(file, "utf8")); } catch { refuse("the spec is not JSON"); }
  if (!doc || typeof doc !== "object") { refuse("the spec is not an object"); }
  const dprs = doc.dprs;
  if (!Array.isArray(dprs) || !dprs.length
      || !dprs.every((d) => typeof d === "number" && d >= 1 && d <= 3)) {
    refuse("dprs is a list of numbers from 1 to 3");
  }
  const alpha = String(doc.alpha);
  if (!/^(0\.[0-9]{1,3}|1(\.0+)?)$/.test(alpha)) { refuse("alpha is a number from 0 to 1"); }
  const variants = (doc.variants || []).map((v) => {
    if (!v || typeof v.name !== "string" || !/^[a-z0-9_]{1,32}$/.test(v.name)) {
      refuse("a variant needs a plain name");
    }
    let css = null;
    if (v.css_file) {
      let st;
      try { st = fs.statSync(v.css_file); } catch { st = null; }
      if (!st) { refuse("a variant css file is missing"); }
      if (!st.isFile() || st.size > MAX_CSS) { refuse("a variant css file is missing or too big"); }
      css = fs.readFileSync(v.css_file, "utf8");
    }
    return { name: v.name, css };
  });
  if (!variants.length) { refuse("no variant"); }
  const ids = /^[A-Za-z][A-Za-z0-9]{0,31}$/;
  for (const c of doc.cards || []) {
    if (!c || !ids.test(c.id) || typeof c.text !== "string") { refuse("a card line needs an id and text"); }
  }
  for (const s of doc.secondary || []) {
    if (!ids.test(s.id) || typeof s.text !== "string") { refuse("a secondary probe needs an id and text"); }
  }
  return { dprs, alpha, variants, line2: doc.line2 || [], cards: doc.cards || [],
    zone: doc.zone || null, secondary: doc.secondary || [] };
}

// ---------------------------------------------------------- in-page code
// Runs inside the overlay page (Runtime.evaluate). Plain ES5-ish so it reads
// the same as the page's own scripts. Returns {widths, contrast}.
function pageMeasure(job) {
  var S = window.ALShared;
  var byId = function (id) { return document.getElementById(id); };
  var widths = [];
  function measureRow(name, row) {
    var range = document.createRange();
    range.selectNodeContents(row);
    var parts = [];
    var kids = row.querySelectorAll("span, p");
    for (var i = 0; i < kids.length; i++) {
      var k = kids[i];
      if (!k.textContent || getComputedStyle(k).display === "none") { continue; }
      parts.push({ id: k.id || k.className, text: k.textContent,
        client: k.clientWidth, scroll: k.scrollWidth });
    }
    var r = row.getBoundingClientRect();
    widths.push({ name: name, text: row.textContent.replace(/\s+/g, " ").trim(),
      width: range.getBoundingClientRect().width, box: r.width,
      client: row.clientWidth, scroll: row.scrollWidth, parts: parts });
  }
  // HUD line 2 through the page's own rule
  var nums = document.querySelector(".row.nums");
  for (var a = 0; a < job.line2.length; a++) {
    var c = job.line2[a];
    var l2 = S.hudLine2(c.inp);
    byId("level").textContent = l2.level;
    byId("deaths").textContent = l2.deaths;
    byId("sep").textContent = "";
    byId("status").textContent = l2.status;
    measureRow(c.name, nums);
    widths[widths.length - 1].line2 = l2;
  }
  if (job.zone) {
    byId("zone").textContent = job.zone.text;
    byId("timer").textContent = job.zone.timer;
    measureRow("zone", document.querySelector(".row.zone"));
  }
  byId("trade").hidden = false;
  byId("evalCard").hidden = false;
  for (var b = 0; b < job.cards.length; b++) {
    var card = job.cards[b];
    var el = byId(card.id);
    el.textContent = card.text;
    var row = el.classList.contains("row") ? el : el.closest(".row");
    measureRow(card.id, row);
  }

  // ---- contrast: canvas proxy with the element's computed styles
  function lum(r, g, b) {
    var f = function (v) { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  }
  function splitTop(text) {
    var out = [], depth = 0, cur = "";
    for (var i = 0; i < text.length; i++) {
      var ch = text[i];
      if (ch === "(") { depth++; } else if (ch === ")") { depth--; }
      if (ch === "," && depth === 0) { out.push(cur.trim()); cur = ""; } else { cur += ch; }
    }
    if (cur.trim()) { out.push(cur.trim()); }
    return out;
  }
  function shadows(cs) {
    if (!cs.textShadow || cs.textShadow === "none") { return []; }
    return splitTop(cs.textShadow).map(function (s) {
      var m = /(rgba?\([^)]*\)|#[0-9a-f]+|[a-z]+)/i.exec(s);
      var color = m ? m[1] : "#000";
      var nums = (m ? s.replace(m[1], "") : s).match(/-?[\d.]+px/g) || [];
      var v = nums.map(parseFloat);
      return { color: color, x: v[0] || 0, y: v[1] || 0, blur: v[2] || 0 };
    });
  }
  function opacityOf(el) {
    var o = 1;
    for (var n = el; n && n.nodeType === 1; n = n.parentElement) {
      o *= parseFloat(getComputedStyle(n).opacity);
    }
    return o;
  }
  function probe(sec, backdrop, dpr) {
    var el = byId(sec.id);
    el.textContent = sec.text;
    var cs = getComputedStyle(el);
    var plateEl = el.closest(".trade, .evalcard, .hud");
    var plate = getComputedStyle(plateEl).backgroundColor;
    var font = [cs.fontStyle, cs.fontWeight, cs.fontSize, cs.fontFamily].join(" ");
    var opacity = opacityOf(el);
    var halo = shadows(cs);
    var pad = 12;
    var probeCtx = document.createElement("canvas").getContext("2d");
    probeCtx.font = font;
    if (cs.letterSpacing && cs.letterSpacing !== "normal") { probeCtx.letterSpacing = cs.letterSpacing; }
    var m = probeCtx.measureText(sec.text);
    var asc = m.actualBoundingBoxAscent, desc = m.actualBoundingBoxDescent;
    var w = Math.ceil(m.width) + 2 * pad, h = Math.ceil(asc + desc) + 2 * pad;
    var W = Math.round(w * dpr), H = Math.round(h * dpr);
    function canvas() {
      var cv = document.createElement("canvas");
      cv.width = W; cv.height = H;
      var ctx = cv.getContext("2d");
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      return { cv: cv, ctx: ctx };
    }
    var main = canvas();
    var g = main.ctx;
    // full-canvas fills in device pixels, so no edge column is half covered
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.fillStyle = "#ffffff";
    g.fillRect(0, 0, W, H);
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (backdrop === "checker") {
      g.fillStyle = "#000000";
      for (var y = 0; y < h; y += 2) {
        for (var x = ((y / 2) % 2) * 2; x < w; x += 4) { g.fillRect(x, y, 2, 2); }
      }
    }
    var layer = canvas();
    var t = layer.ctx;
    t.setTransform(1, 0, 0, 1, 0, 0);
    t.fillStyle = plate;
    t.fillRect(0, 0, W, H);
    t.setTransform(dpr, 0, 0, dpr, 0, 0);
    t.font = font;
    if (cs.letterSpacing && cs.letterSpacing !== "normal") { t.letterSpacing = cs.letterSpacing; }
    t.textBaseline = "alphabetic";
    var bx = pad, by = pad + asc;
    var off = w + 64;
    // CSS paints the first shadow on top: draw them last to first, shadow only
    for (var s = halo.length - 1; s >= 0; s--) {
      var sh = halo[s];
      t.save();
      t.fillStyle = "#000000";
      t.shadowColor = sh.color;
      t.shadowBlur = sh.blur * dpr;
      t.shadowOffsetX = (sh.x + off) * dpr;
      t.shadowOffsetY = sh.y * dpr;
      t.fillText(sec.text, bx - off, by);
      t.restore();
    }
    t.fillStyle = cs.color;
    t.fillText(sec.text, bx, by);
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.globalAlpha = opacity;
    g.drawImage(layer.cv, 0, 0);
    g.globalAlpha = 1;
    var data = g.getImageData(0, 0, W, H).data;
    var at = function (px, py) {
      var i = (py * W + px) * 4;
      return lum(data[i], data[i + 1], data[i + 2]);
    };
    var x0 = Math.floor(pad * dpr), x1 = Math.ceil((pad + m.width) * dpr);
    var y0 = Math.floor(pad * dpr), y1 = Math.ceil((pad + asc + desc) * dpr);
    var glyph = [];
    for (var gy = y0; gy < y1; gy++) {
      for (var gx = x0; gx < x1; gx++) { glyph.push(at(gx, gy)); }
    }
    glyph.sort(function (p, q) { return q - p; });
    var n = Math.max(1, Math.ceil(glyph.length * 0.03));
    var core = 0;
    for (var k = 0; k < n; k++) { core += glyph[k]; }
    core /= n;
    // the far plate: the band above the text, clear of the halo's reach
    var band = Math.max(1, Math.floor((pad - 6) * dpr));
    var far = 0;
    for (var py2 = 0; py2 < band; py2++) {
      for (var px2 = 0; px2 < W; px2++) { far = Math.max(far, at(px2, py2)); }
    }
    return { id: sec.id, backdrop: backdrop, dpr: dpr, text: sec.text, color: cs.color,
      plate: plate, font: font, opacity: opacity, halo: cs.textShadow,
      core_lum: core, far_lum: far, core_px: n, glyph_px: glyph.length,
      ratio: (core + 0.05) / (far + 0.05) };
  }
  var contrast = [];
  for (var p = 0; p < job.secondary.length; p++) {
    for (var q = 0; q < job.backdrops.length; q++) {
      contrast.push(probe(job.secondary[p], job.backdrops[q], job.dpr));
    }
  }
  return { widths: widths, contrast: contrast,
    plate_a: getComputedStyle(document.documentElement).getPropertyValue("--al-plate-a").trim() };
}

// ---------------------------------------------------------------- browser

function get(port, p) {
  return new Promise((resolve, reject) => {
    const req = http.get({ host: LOOPBACK, port, path: p, timeout: 5000, agent: false }, (res) => {
      const chunks = [];
      res.on("data", (c) => chunks.push(c));
      res.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    });
    req.on("timeout", () => req.destroy(new Error("timed out")));
    req.on("error", reject);
  });
}

async function devtoolsPort(profile, child) {
  const file = path.join(profile, "DevToolsActivePort");
  for (let i = 0; i < 300; i++) {
    if (child.exitCode !== null) { throw new Error("the browser exited at start"); }
    try {
      const first = fs.readFileSync(file, "utf8").split(/\r?\n/)[0].trim();
      if (/^\d{1,5}$/.test(first) && Number(first) > 0) { return Number(first); }
    } catch { /* not written yet */ }
    await sleep(100);
  }
  throw new Error("no DevToolsActivePort file");
}

let browserChild = null;

async function run(browser, profile, spec) {
  try { os.setPriority(process.pid, os.constants.priority.PRIORITY_BELOW_NORMAL); } catch { /* best effort */ }
  const child = spawn(browser, [...BROWSER_FLAGS, `--user-data-dir=${profile}`, "about:blank"],
    { stdio: "ignore", windowsHide: true });
  browserChild = child;
  let ws = null;
  try {
    const dport = await devtoolsPort(profile, child);
    const list = JSON.parse(await get(dport, "/json/list"));
    const page = list.find((t) => t.type === "page");
    if (!page || !String(page.webSocketDebuggerUrl).startsWith(`ws://${LOOPBACK}:${dport}/`)) {
      throw new Error("no loopback page target");
    }
    ws = new WebSocket(page.webSocketDebuggerUrl);
    await new Promise((r, j) => { ws.addEventListener("open", r); ws.addEventListener("error", j); });
    let seq = 0;
    const pending = new Map();
    ws.addEventListener("message", (e) => {
      const m = JSON.parse(e.data);
      if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
    });
    const send = (method, params = {}) => new Promise((r) => {
      const i = ++seq; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params }));
    });
    const evaluate = async (expression) => {
      const r = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
      if (r.result && r.result.exceptionDetails) {
        const d = r.result.exceptionDetails;
        throw new Error(`page error: ${(d.exception && d.exception.description) || d.text}`);
      }
      return r.result && r.result.result ? r.result.result.value : undefined;
    };
    await send("Page.enable");
    const href = overlayUrl();
    const runs = [];
    for (const variant of spec.variants) {
      for (const dpr of spec.dprs) {
        await send("Emulation.setDeviceMetricsOverride",
          { width: WIN.width, height: WIN.height, deviceScaleFactor: dpr, mobile: false });
        await send("Page.navigate", { url: href });
        let ready = false;
        for (let i = 0; i < (CI ? 450 : 150) && !ready; i++) {
          await sleep(100);
          ready = (await evaluate(
            "document.readyState === 'complete' && !!(window.ALShared && window.ALShared.hudLine2)")) === true;
        }
        if (!ready) { throw new Error("the overlay page never finished loading"); }
        const where = await evaluate("location.href");
        if (!isOverlayUrl(where)) { throw new Error("the browser left the overlay page"); }
        if (variant.css !== null) {
          // the fixture copy replaces the page's own sheet (a constructed
          // sheet: no markup, the page CSP stays as it is)
          await evaluate(`(function () {
            var link = document.querySelector('link[rel="stylesheet"]');
            link.disabled = true;
            var s = new CSSStyleSheet();
            s.replaceSync(${JSON.stringify(variant.css)});
            document.adoptedStyleSheets = [s];
            return true;
          })()`);
        }
        await evaluate(`document.documentElement.style.setProperty("--al-plate-a", ${JSON.stringify(spec.alpha)})`);
        const job = { line2: spec.line2, cards: spec.cards, zone: spec.zone,
          secondary: spec.secondary, backdrops: BACKDROPS, dpr };
        const got = await evaluate(`(${pageMeasure.toString()})(${JSON.stringify(job)})`);
        runs.push({ variant: variant.name, dpr, ...got });
      }
    }
    return { ok: true, browser: path.basename(browser), window: WIN, alpha: spec.alpha, runs };
  } finally {
    try { if (ws) { ws.close(); } } catch { /* closing */ }
    child.kill();
  }
}

export async function main(argv) {
  let browser;
  let profile;
  let spec;
  try {
    if (argv.length !== 3) { refuse("usage: overlay_pixels.mjs <browser> <profile dir> <spec.json>"); }
    [browser, profile] = argv;
    let st;
    try { st = fs.statSync(browser); } catch { st = null; }
    if (!st || !st.isFile()) { refuse("the browser executable was not found"); }
    profile = checkProfile(profile);
    spec = readSpec(argv[2]);
  } catch (e) {
    if (e instanceof Refused || (e && e.constructor && e.constructor.name === "Refused")) {
      say({ refused: e.message }); return 2;
    }
    throw e;
  }
  const watchdog = setTimeout(() => {
    say({ error: "watchdog" });
    if (browserChild) { browserChild.kill(); }
    process.exit(4);
  }, CI ? 360000 : 120000);
  try {
    say(await run(browser, profile, spec));
    return 0;
  } catch (e) {
    say({ error: String(e && e.message || e) });
    return 3;
  } finally {
    clearTimeout(watchdog);
  }
}

process.exitCode = await main(process.argv.slice(2));
