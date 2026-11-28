// PLAY-TD-22C-A11Y-CDP (TD-22, F-121): the in-browser accessibility pass.
// One headless Chrome, one page; tests/test_a11y_render.py puts a play
// state under the page (tests/play_states.py: one fixture state, then the
// long-string fixture) and this driver measures what the accessibility
// commitments of plan 03 section 9 need, on the rendered page, in dark and
// light, on all four tabs:
//   - the accessibility tree (Accessibility.getFullAXTree): focusable nodes
//     and their names, heading levels, landmark roles;
//   - a real Tab walk (Input.dispatchKeyEvent Tab to this page only) with
//     the focus ring box of every stop and the first ancestor that clips it;
//   - target sizes, text colour pairs, live regions;
//   - the forced-colours tab cue (Emulation.setEmulatedMedia);
//   - 320 px reflow and the four WCAG 1.4.12 text-spacing overrides.
// It only measures: every verdict is made in Python. Not a node --test file.
//
//   node a11y.mjs <chrome.exe> <profile dir>
//
// Reads one JSON command per stdin line and answers one JSON line each:
//   {"cmd": "load", "url"}
//   {"cmd": "audit", "theme": "dark"|"light", "tabs": [ids], "size": [w, h]}
//   {"cmd": "forced", "theme", "size": [w, h]}
//   {"cmd": "reflow", "theme", "tabs": [ids], "size": [w, h]}
//   {"cmd": "spacing", "sizes": [[w, h], ...]}
//   {"cmd": "plant"}     a clipped ring, an unnamed button, a 3:1 text pair
//   {"cmd": "quit"}
// Node's global WebSocket (Node 22+) is the only client; no npm package.
// The page is a loopback test core; nothing is sent to the game, no
// clipboard or screen is read and nothing is captured.
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { createInterface } from "node:readline";

const [chromePath, profile] = process.argv.slice(2);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// decision 0080: on a CI runner (AL_CI=1) the page-live wait gets one
// bounded retry at 3x, the DevTools endpoint wait and the watchdog 3x;
// locally all stay as they are.
const CI = process.env.AL_CI === "1";
const MAX_STOPS = 300;
const out = (o) => process.stdout.write(JSON.stringify(o) + "\n");
// TEST-CDP-OS-PORT: the OS picks the DevTools port (--remote-debugging-port=0,
// read back from this profile's DevToolsActivePort, as play_fit.mjs does).
// A random port of a range shared with play_fit.mjs let two drivers of a
// parallel suite pick one port; the second browser could not bind it and
// its driver attached to the first driver's page.
const portFile = path.join(profile, "DevToolsActivePort");
try { fs.rmSync(portFile, { force: true }); } catch { /* none yet */ }
const chrome = spawn(chromePath, ["--headless=new", "--disable-gpu", "--in-process-gpu",
  "--no-first-run", "--no-default-browser-check", "--disable-extensions",
  "--hide-scrollbars", "--force-device-scale-factor=1",
  "--remote-debugging-port=0", `--user-data-dir=${profile}`, "about:blank"],
  { stdio: "ignore" });
let chromeExit = null;
// a clean 0 exit may be a hand-off to a running browser: keep polling then
chrome.on("exit", (code, signal) => { if (signal || code) { chromeExit = signal || code; } });
const quit = (code) => { try { chrome.kill(); } catch { /* gone */ } process.exit(code); };
const killer = setTimeout(() => { out({ error: `watchdog: ${CI ? 540 : 180} s` }); quit(3); },
  CI ? 540000 : 180000);

// TEST-A11Y-NEWEST-DEVTOOLS: this is the first browser start of a CI run
// (test_a11y_render sorts near the top); on a cold runner the first
// Chrome launch took longer than the fixed 15 s poll (runs 46074274403
// and 46079475413 attempt 1, about 35 s into the suite). The poll widens
// 3x under AL_CI only, and stops at once if Chrome has failed.
const ENDPOINT_POLLS = CI ? 450 : 150;
// the OS-chosen port of this driver's own browser (never another one's)
let port = 0;
let targets = null;
for (let i = 0; i < ENDPOINT_POLLS && !targets && chromeExit === null; i++) {
  if (!port) {
    try {
      const first = fs.readFileSync(portFile, "utf8").split(/\r?\n/)[0].trim();
      if (/^\d{1,5}$/.test(first) && Number(first) > 0) { port = Number(first); }
    } catch { /* not written yet */ }
  }
  if (port) {
    try { targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); }
    catch { targets = null; }
  }
  if (!targets) { await sleep(100); }
}
if (!targets) {
  out({ error: "no DevTools endpoint" + (chromeExit === null
    ? ` after ${ENDPOINT_POLLS} polls` : ` (browser exited: ${chromeExit})`) });
  quit(2);
}
const page = targets.find((t) => t.type === "page" &&
  String(t.webSocketDebuggerUrl).startsWith(`ws://127.0.0.1:${port}/`));
if (!page) { out({ error: "no page target" }); quit(2); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
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
  if (r.error) { throw new Error(r.error.message || "evaluate failed"); }
  if (r.result && r.result.exceptionDetails) {
    const d = r.result.exceptionDetails;
    throw new Error((d.exception && d.exception.description) || d.text || "evaluate failed");
  }
  return r.result && r.result.result ? r.result.result.value : undefined;
};
const call = (fn, arg) => evaluate(`(${fn.toString()})(${JSON.stringify(arg === undefined ? null : arg)})`);
const frames = () => evaluate(
  "new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => r(true))))");

await send("Page.enable");
await send("Runtime.enable");
await send("DOM.enable");
await send("Accessibility.enable");
// headless pages have no window focus; without this :focus-visible and the
// Tab walk would not behave as in a focused window
await send("Emulation.setFocusEmulationEnabled", { enabled: true });

async function media(forced) {
  await send("Emulation.setEmulatedMedia", { features: [
    { name: "prefers-color-scheme", value: "dark" },
    { name: "forced-colors", value: forced ? "active" : "none" },
    { name: "prefers-reduced-motion", value: "reduce" }] });
}
await media(false);

async function resize(w, h) {
  await send("Emulation.setDeviceMetricsOverride",
    { width: w, height: h, deviceScaleFactor: 1, mobile: false });
  await frames();
}

async function load(url) {
  // live once the feed is up and the first state has painted
  for (const tries of CI ? [100, 300] : [100]) {
    await send("Page.navigate", { url: "about:blank" });
    await send("Page.navigate", { url });
    for (let i = 0; i < tries; i++) {
      await sleep(100);
      let ok = false;
      try {
        ok = await evaluate("!!document.getElementById('panel-play') && " +
          "/^(running|done|idle|blocked)$/.test((document.getElementById('reading') || {getAttribute(){return ''}}).getAttribute('data-state') || '')");
      } catch { ok = false; }
      if (ok) { await sleep(300); return true; }
    }
  }
  return false;
}

// -- in-page helpers (each runs in the page; returns plain data) ------------

// Theme, tab and folds: data-theme on the root (light is reached this way,
// plan note), the tab shown through its own button, every fold opened.
function prepare(args) {
  const doc = document;
  doc.documentElement.setAttribute("data-theme", args.theme);
  const tab = doc.getElementById("tab-" + args.tab);
  if (tab && tab.getAttribute("aria-selected") !== "true") { tab.click(); }
  const panel = doc.getElementById("panel-" + args.tab);
  for (const d of doc.querySelectorAll("details")) {
    if (!d.open && (!panel || panel.contains(d) || !d.closest("[role=tabpanel]"))) {
      d.open = true;
    }
  }
  if (doc.activeElement && doc.activeElement !== doc.body) { doc.activeElement.blur(); }
  window.scrollTo(0, 0);
  return { selected: tab ? tab.getAttribute("aria-selected") : null,
    shown: panel ? !panel.hidden : false };
}

// The common page measurements: targets, text pairs, live regions and the
// focusable controls the walk must reach. Installs window.__a11y (label,
// stop) for the Tab walk.
function inspect(args) {
  const doc = document;
  const de = doc.documentElement;
  const label = (el) => el.tagName.toLowerCase() + (el.id ? "#" + el.id : "") +
    (el.classList.length ? "." + Array.from(el.classList).slice(0, 2).join(".") : "");
  const rendered = (el) => el.getClientRects().length > 0 &&
    getComputedStyle(el).visibility !== "hidden";
  const visuallyHidden = (el) => {
    for (let p = el; p && p.nodeType === 1; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (/inset\(50%/.test(cs.clipPath) || cs.clip === "rect(0px, 0px, 0px, 0px)") { return true; }
      const r = p.getBoundingClientRect();
      if (cs.overflow !== "visible" && (r.width <= 1 || r.height <= 1)) { return true; }
    }
    return false;
  };
  const scopeOf = (el) => {
    const p = el.closest("[role=tabpanel]");
    if (p) { return p.id; }
    if (el.closest("header")) { return "header"; }
    if (el.closest("footer")) { return "footer"; }
    return "page";
  };
  const FOCUSABLE = "a[href], button, input:not([type=hidden]), select, textarea, summary, " +
    "[tabindex]";
  const tabbable = (el) => {
    if (el.disabled || !rendered(el) || el.closest("[inert]")) { return false; }
    const ti = el.getAttribute("tabindex");
    if (ti !== null && parseInt(ti, 10) < 0) { return false; }
    if (el.tagName === "SUMMARY" && !(el.parentElement && el.parentElement.tagName === "DETAILS" &&
      el.parentElement.firstElementChild === el)) { return false; }
    if (el.tagName === "INPUT" && el.type === "radio" && !el.checked) {
      const g = el.name && doc.querySelector(`input[type=radio][name="${CSS.escape(el.name)}"]:checked`);
      if (g) { return false; }
    }
    for (let p = el.parentElement; p; p = p.parentElement) {
      if (p.tagName === "DETAILS" && !p.open && !(el.tagName === "SUMMARY" && el.parentElement === p)) {
        return false;
      }
    }
    return true;
  };

  // 2.5.8: target sizes of every rendered focusable control
  const controls = [];
  for (const el of doc.querySelectorAll(FOCUSABLE)) {
    if (!tabbable(el)) { continue; }
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    const inline = el.tagName === "A" && cs.display === "inline" &&
      !!el.parentElement && /\S/.test((el.parentElement.textContent || "")
        .replace(el.textContent || "", ""));
    controls.push({ el: label(el), scope: scopeOf(el), w: Math.round(r.width * 10) / 10,
      h: Math.round(r.height * 10) / 10, inline, role: el.getAttribute("role") || "" });
  }

  // 1.4.3: every rendered element that holds its own text, against the
  // backdrop composed from its ancestors (canvas pixels, so any colour
  // syntax the page uses resolves)
  const cv = doc.createElement("canvas");
  cv.width = cv.height = 1;
  const ctx = cv.getContext("2d", { willReadFrequently: true });
  const cache = new Map();
  const rgba = (s) => {
    if (cache.has(s)) { return cache.get(s); }
    ctx.clearRect(0, 0, 1, 1);
    ctx.fillStyle = "rgba(0, 0, 0, 0)";
    ctx.fillStyle = s;
    ctx.fillRect(0, 0, 1, 1);
    const d = ctx.getImageData(0, 0, 1, 1).data;
    const v = [d[0], d[1], d[2], d[3] / 255];
    cache.set(s, v);
    return v;
  };
  const over = (top, under) => {
    const a = top[3];
    return [0, 1, 2].map((i) => top[i] * a + under[i] * (1 - a)).concat([1]);
  };
  const lum = (c) => {
    const f = (v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
  };
  const backdrop = (el) => {
    const layers = [];
    for (let p = el; p && p.nodeType === 1; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (cs.backgroundImage && cs.backgroundImage !== "none" && !/url\(/.test(cs.backgroundImage)) {
        return null;  // a gradient: no single backdrop
      }
      const c = rgba(cs.backgroundColor);
      if (c[3] > 0) { layers.push(c); }
      if (c[3] >= 1) { break; }
    }
    let bg = [255, 255, 255, 1];
    for (let i = layers.length - 1; i >= 0; i--) { bg = over(layers[i], bg); }
    return bg;
  };
  const inactive = (el) => !!el.closest("button:disabled, [aria-disabled=true], input:disabled, " +
    "select:disabled, textarea:disabled, fieldset:disabled");
  const pairs = [];
  let measured = 0;
  for (const el of doc.querySelectorAll("body *")) {
    const own = Array.from(el.childNodes).filter((n) => n.nodeType === 3)
      .map((n) => n.nodeValue).join("").trim();
    if (!own || !rendered(el) || visuallyHidden(el) || inactive(el)) { continue; }
    if (["SCRIPT", "STYLE", "OPTION", "TITLE", "NOSCRIPT"].includes(el.tagName)) { continue; }
    const cs = getComputedStyle(el);
    if (parseFloat(cs.opacity) === 0) { continue; }
    const bg = backdrop(el);
    if (!bg) { continue; }
    const fg = over(rgba(cs.color), bg);
    const l1 = lum(fg), l2 = lum(bg);
    const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    const px = parseFloat(cs.fontSize);
    const weight = parseInt(cs.fontWeight, 10) || 400;
    measured += 1;
    if (ratio < 4.6) {
      pairs.push({ el: label(el), scope: scopeOf(el), ratio: Math.round(ratio * 100) / 100,
        px, weight, large: px >= 24 || (px >= 18.66 && weight >= 700),
        fg: fg.slice(0, 3), bg: bg.slice(0, 3), text: own.slice(0, 40) });
    }
  }

  // 4.1.3: live regions in the DOM (shown or not) and those on Play
  const LIVE = new Set(["status", "log", "alert", "marquee", "timer"]);
  const isLive = (el) => {
    const v = el.getAttribute("aria-live");
    return (v !== null && v !== "off") || LIVE.has(el.getAttribute("role") || "");
  };
  const live = [];
  for (const el of doc.querySelectorAll("body *")) {
    if (isLive(el)) {
      live.push({ el: label(el), id: el.id, scope: scopeOf(el), rendered: rendered(el),
        polite: el.getAttribute("aria-live") || "", role: el.getAttribute("role") || "" });
    }
  }

  // the controls a full Tab cycle must reach (roving tab rows show one)
  window.__a11y = { n: 0, ids: new WeakMap() };
  // GATE-FIX-37: every Tab keydown the page has handled, so the walk reads
  // the focus only after its own key was handled (one listener per page)
  if (typeof window.__a11yKeys !== "number") {
    window.__a11yKeys = 0;
    window.addEventListener("keydown", (e) => { if (e.key === "Tab") { window.__a11yKeys++; } },
      true);
  }
  const reach = [];
  for (const el of doc.querySelectorAll(FOCUSABLE)) {
    if (!tabbable(el)) { continue; }
    const ti = el.getAttribute("tabindex");
    if (el.getAttribute("role") === "tab" && ti === "-1") { continue; }
    reach.push(label(el));
  }
  return { vw: window.innerWidth, vh: window.innerHeight, theme: de.getAttribute("data-theme"),
    controls, pairs, measured, live, reach };
}

// One Tab stop: the focused element, its ring and the first ancestor that
// clips the ring's outer box.
function stop() {
  const doc = document;
  const el = doc.activeElement;
  if (!el || el === doc.body || el === doc.documentElement) { return { none: true }; }
  const A = window.__a11y;
  if (!A.ids.has(el)) { A.ids.set(el, ++A.n); }
  const label = (n) => n.tagName.toLowerCase() + (n.id ? "#" + n.id : "") +
    (n.classList.length ? "." + Array.from(n.classList).slice(0, 2).join(".") : "");
  const cs = getComputedStyle(el);
  const r = el.getBoundingClientRect();
  const width = cs.outlineStyle === "none" ? 0 : parseFloat(cs.outlineWidth) || 0;
  const offset = parseFloat(cs.outlineOffset) || 0;
  const grow = width > 0 ? offset + width : 0;
  const ring = { left: r.left - grow, top: r.top - grow, right: r.right + grow,
    bottom: r.bottom + grow };
  let clip = null;
  for (let p = el.parentElement; p && p !== doc.documentElement; p = p.parentElement) {
    const ps = getComputedStyle(p);
    if (ps.overflowX === "visible" && ps.overflowY === "visible" && ps.contain.indexOf("paint") < 0) {
      continue;
    }
    const pr = p.getBoundingClientRect();
    const box = { left: pr.left + (parseFloat(ps.borderLeftWidth) || 0),
      top: pr.top + (parseFloat(ps.borderTopWidth) || 0),
      right: pr.right - (parseFloat(ps.borderRightWidth) || 0),
      bottom: pr.bottom - (parseFloat(ps.borderBottomWidth) || 0) };
    const cut = Math.max(box.left - ring.left, ring.right - box.right,
      box.top - ring.top, ring.bottom - box.bottom);
    if (cut > 0.5) { clip = { el: label(p), px: Math.round(cut * 10) / 10 }; break; }
  }
  const scope = el.closest("[role=tabpanel]") ? el.closest("[role=tabpanel]").id :
    (el.closest("header") ? "header" : (el.closest("footer") ? "footer" : "page"));
  return { id: A.ids.get(el), el: label(el), scope, style: cs.outlineStyle, width, offset,
    color: cs.outlineColor, w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10,
    ring: { left: Math.round(ring.left), top: Math.round(ring.top),
      right: Math.round(ring.right), bottom: Math.round(ring.bottom) },
    clip, visible: r.width > 0 && r.height > 0, focusVisible: el.matches(":focus-visible") };
}

async function tabKey() {
  const ev = { key: "Tab", code: "Tab", windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9 };
  await send("Input.dispatchKeyEvent", Object.assign({ type: "keyDown" }, ev));
  await send("Input.dispatchKeyEvent", Object.assign({ type: "keyUp" }, ev));
}

// GATE-FIX-37: resolves once the page has handled `want` Tab keydowns (then
// one frame, so the focus move is done), or false after the bound. A gated
// whole suite showed walks that skipped controls and came round early: a
// read that ran before its Tab was handled sampled the cycle out of step.
function keysHandled(args) {
  return new Promise((resolve) => {
    const t0 = Date.now();
    const poll = () => {
      if (window.__a11yKeys >= args.want) { requestAnimationFrame(() => resolve(true)); return; }
      if (Date.now() - t0 > args.ms) { resolve(false); return; }
      setTimeout(poll, 5);
    };
    poll();
  });
}

// A full Tab cycle: Tab until the first stop comes round again. Each stop
// is read only after the page handled that Tab; `unsynced` counts Tabs the
// page had not handled within the bound, `lost` reads with no focus after
// the first stop (a control re-rendered under the focus).
async function walk() {
  const stops = [];
  let first = null;
  let wrapped = false;
  let unsynced = 0;
  let lost = 0;
  let want = await evaluate("window.__a11yKeys");
  for (let i = 0; i < MAX_STOPS; i++) {
    await tabKey();
    want += 1;
    if (!(await call(keysHandled, { want, ms: CI ? 6000 : 2000 }))) { unsynced++; }
    const s = await call(stop);
    if (s.none) { if (first !== null) { lost++; } continue; }
    if (first === null) { first = s.id; } else if (s.id === first) { wrapped = true; break; }
    stops.push(s);
  }
  return { stops, wrapped, unsynced, lost };
}

// The accessibility tree: unnamed focusable nodes, the heading levels in
// tree order and the landmark roles, of what is rendered now.
const LANDMARKS = new Set(["banner", "main", "contentinfo", "navigation", "complementary",
  "search", "form", "region"]);
const prop = (n, name) => {
  const p = (n.properties || []).find((x) => x.name === name);
  return p && p.value ? p.value.value : undefined;
};
async function nodeInfo(backendNodeId) {
  const none = { el: "?", tabindex: null, text: 0 };
  try {
    const o = await send("DOM.resolveNode", { backendNodeId });
    const id = o.result && o.result.object && o.result.object.objectId;
    if (!id) { return none; }
    const r = await send("Runtime.callFunctionOn", { objectId: id, returnByValue: true,
      functionDeclaration: "function () { var e = this.nodeType === 1 ? this : this.parentElement;" +
        " if (!e) { return null; } return { el: e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') +" +
        " (e.classList.length ? '.' + Array.from(e.classList).slice(0, 2).join('.') : ''), " +
        " tabindex: e.getAttribute('tabindex'), text: (e.textContent || '').trim().length }; }" });
    return (r.result && r.result.result && r.result.result.value) || none;
  } catch { return none; }
}
async function axTree() {
  const r = await send("Accessibility.getFullAXTree", {});
  const nodes = (r.result && r.result.nodes) || [];
  const unnamed = [];
  const headings = [];
  const landmarks = {};
  for (const n of nodes) {
    if (n.ignored) { continue; }
    const role = n.role ? n.role.value : "";
    const name = n.name ? String(n.name.value || "").trim() : "";
    if (role === "heading") { headings.push({ level: prop(n, "level") || 0, name: name.slice(0, 40) }); }
    if (LANDMARKS.has(role)) { landmarks[role] = (landmarks[role] || 0) + 1; }
    if (prop(n, "focusable") && !name && role !== "RootWebArea" && role !== "WebArea") {
      const info = n.backendDOMNodeId ? await nodeInfo(n.backendDOMNodeId) :
        { el: "?", tabindex: null, text: 0 };
      unnamed.push(Object.assign({ role }, info));
    }
  }
  return { count: nodes.length, unnamed, headings, landmarks };
}

// Forced colours: the bottom border of the selected tab and of the others.
function tabCue() {
  const out = [];
  for (const t of document.querySelectorAll("[role=tab]")) {
    const cs = getComputedStyle(t);
    out.push({ id: t.id, selected: t.getAttribute("aria-selected") === "true",
      color: cs.borderBottomColor, width: parseFloat(cs.borderBottomWidth) || 0,
      style: cs.borderBottomStyle, weight: parseInt(cs.fontWeight, 10) || 400,
      forced: matchMedia("(forced-colors: active)").matches });
  }
  return out;
}

function docBox() {
  const de = document.documentElement;
  return { sw: de.scrollWidth, cw: de.clientWidth, sh: de.scrollHeight, ch: de.clientHeight };
}

// WCAG 1.4.12: line height 1.5, paragraph spacing 2em, letter spacing
// 0.12em, word spacing 0.16em, as a user style sheet would set them. The
// page's CSP refuses an inline <style>, so the sheet goes in through the
// DevTools CSS domain (an inspector sheet; the page's CSP stays as it is).
const SPACING_CSS = "* { line-height: 1.5 !important; letter-spacing: 0.12em !important;" +
  " word-spacing: 0.16em !important; } p { margin-bottom: 2em !important; }";
async function overrideSpacing() {
  const tree = await send("Page.getFrameTree");
  const frameId = tree.result.frameTree.frame.id;
  await send("CSS.enable");
  const sheet = await send("CSS.createStyleSheet", { frameId });
  const styleSheetId = sheet.result && sheet.result.styleSheetId;
  if (!styleSheetId) { throw new Error("no inspector style sheet"); }
  await send("CSS.setStyleSheetText", { styleSheetId, text: SPACING_CSS });
  await frames();
  return true;
}

// Every element under the Play panel: no clipping on either axis, and only
// the page scrolls.
function spacingIssues() {
  const doc = document;
  const play = doc.getElementById("panel-play");
  const label = (el) => el.tagName.toLowerCase() + (el.id ? "#" + el.id : "") +
    (el.classList.length ? "." + Array.from(el.classList).slice(0, 2).join(".") : "");
  const rendered = (el) => el.getClientRects().length > 0 &&
    getComputedStyle(el).visibility !== "hidden";
  const visuallyHidden = (el) => {
    for (let p = el; p && p.nodeType === 1; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (/inset\(50%/.test(cs.clipPath) || cs.clip === "rect(0px, 0px, 0px, 0px)") { return true; }
    }
    return false;
  };
  const FORM = new Set(["INPUT", "SELECT", "TEXTAREA", "OPTION", "OPTGROUP"]);
  const block = [], inline = [], scrollers = [];
  let checked = 0;
  for (const el of play ? play.querySelectorAll("*") : []) {
    if (FORM.has(el.tagName) || !rendered(el) || visuallyHidden(el)) { continue; }
    const sh = el.scrollHeight, ch = el.clientHeight, sw = el.scrollWidth, cw = el.clientWidth;
    if (ch === 0 && cw === 0) { continue; }
    checked += 1;
    if (ch > 0 && sh > ch + 1) { block.push({ el: label(el), sh, ch }); }
    if (cw > 0 && sw > cw + 1) { inline.push({ el: label(el), sw, cw }); }
    const cs = getComputedStyle(el);
    if ((/auto|scroll/.test(cs.overflowY) && sh > ch + 1) ||
      (/auto|scroll/.test(cs.overflowX) && sw > cw + 1)) {
      scrollers.push({ el: label(el), sh, ch, sw, cw });
    }
  }
  const de = doc.documentElement;
  return { attr: de.getAttribute("data-text-spacing") || "", checked,
    block: block.slice(0, 40), inline: inline.slice(0, 40), scrollers: scrollers.slice(0, 40),
    doc: { sw: de.scrollWidth, cw: de.clientWidth, sh: de.scrollHeight, ch: de.clientHeight } };
}

// The three planted defects, at the top of the Play panel (the test proves
// each one is caught; the next state loads a fresh page).
function plant() {
  // built through the DOM and CSSOM: the page's CSP refuses style attributes
  const doc = document;
  const play = doc.getElementById("panel-play");
  const make = (tag, id, css, text) => {
    const el = doc.createElement(tag);
    el.id = id;
    el.style.cssText = css;
    if (text) { el.textContent = text; }
    return el;
  };
  const host = make("div", "a11y-plant", "", "");
  const clip = make("div", "plant-clip", "overflow:hidden;width:96px;height:40px", "");
  const ring = make("button", "plant-ring", "display:block;margin:0;width:96px;height:40px;" +
    "outline-offset:2px", "Planted");
  ring.type = "button";
  clip.appendChild(ring);
  const unnamed = make("button", "plant-unnamed", "width:32px;height:32px;padding:0", "");
  unnamed.type = "button";
  const pair = make("p", "plant-pair", "color:#959595;background:#ffffff;font-size:16px;" +
    "font-weight:400;margin:0", "Planted low contrast");
  host.append(clip, unnamed, pair);
  play.insertBefore(host, play.firstChild);
  return true;
}

// -- commands -----------------------------------------------------------------

async function audit(cmd) {
  await resize(cmd.size[0], cmd.size[1]);
  const tabs = {};
  for (const tab of cmd.tabs) {
    const prep = await call(prepare, { theme: cmd.theme, tab });
    await frames();
    const page = await call(inspect, {});
    const ax = await axTree();
    const w = await walk();
    tabs[tab] = Object.assign({ prep, ax, walk: w }, page);
  }
  await call(prepare, { theme: cmd.theme, tab: "play" });
  return { theme: cmd.theme, size: cmd.size, tabs };
}

async function run(cmd) {
  if (cmd.cmd === "load") { return { live: await load(cmd.url) }; }
  if (cmd.cmd === "audit") { return audit(cmd); }
  if (cmd.cmd === "forced") {
    await resize(cmd.size[0], cmd.size[1]);
    await media(true);
    await call(prepare, { theme: cmd.theme, tab: "play" });
    await frames();
    const cue = await call(tabCue);
    await media(false);
    await frames();
    return { theme: cmd.theme, tabs: cue };
  }
  if (cmd.cmd === "reflow") {
    await resize(cmd.size[0], cmd.size[1]);
    const tabs = {};
    for (const tab of cmd.tabs) {
      const prep = await call(prepare, { theme: cmd.theme, tab });
      await frames();
      tabs[tab] = Object.assign({ prep }, await call(docBox));
    }
    await call(prepare, { theme: cmd.theme, tab: "play" });
    return { theme: cmd.theme, size: cmd.size, tabs };
  }
  if (cmd.cmd === "spacing") {
    const sizes = {};
    await call(prepare, { theme: "dark", tab: "play" });
    const before = {};
    for (const [w, h] of cmd.sizes) {
      await resize(w, h);
      before[`${w}x${h}`] = await call(spacingIssues);
    }
    await overrideSpacing();
    for (const [w, h] of cmd.sizes) {
      await resize(w, h);
      // the probe reacts through a ResizeObserver (an event): a few frames
      for (let i = 0; i < 20; i++) {
        await frames();
        if (await evaluate("document.documentElement.getAttribute('data-text-spacing') === 'user'")) {
          break;
        }
      }
      await frames();
      sizes[`${w}x${h}`] = await call(spacingIssues);
    }
    return { before, sizes };
  }
  if (cmd.cmd === "plant") { return { planted: await call(plant) }; }
  return { error: `unknown command ${cmd.cmd}` };
}

const rl = createInterface({ input: process.stdin });
out({ ready: true });
for await (const line of rl) {
  if (!line.trim()) { continue; }
  let cmd;
  try { cmd = JSON.parse(line); } catch (e) { out({ error: "bad json: " + e.message }); continue; }
  if (cmd.cmd === "quit") { break; }
  try { out(await run(cmd)); } catch (e) { out({ error: String((e && e.stack) || e) }); }
}
clearTimeout(killer);
ws.close();
quit(0);
