// PLAY-TD-01B: the Play fit harness driver. One headless Chrome, one page;
// tests/test_play_fit.py swaps the play state under the page (same port,
// same token, a fresh core per state) and this driver resizes the page
// through the 5 cockpit and 2 flow sizes and measures what the glance
// budgets of plan 03 section 11 need (G1, G2, G4, G5, G6, G7, G9). It only
// measures: every verdict is made in Python. Not a node --test file.
//
//   node play_fit.mjs <chrome.exe> <profile dir>
//
// Reads one JSON command per stdin line and answers one JSON line each:
//   {"cmd": "state", "url", "name", "sizes": [[w, h], ...], "answers": [...]}
//   {"cmd": "placeholder", "sizes": [[w, h], ...]}   data-fit forced on
//                                                    every region, legacy
//                                                    groups hidden
//   {"cmd": "metrics", "rows": [{"key", "text", "px", "weight"}]}
//   {"cmd": "quit"}
// Node's global WebSocket (Node 22+) is the only client; no npm package.
// The page is a loopback test core; nothing is sent to the game.
//
// TEST-PLAYFIT-LOAD-FLAKE: the DevTools port is chosen by the OS
// (--remote-debugging-port=0, read back from the profile's
// DevToolsActivePort, as capture.mjs does). A random port of a shared range
// let two drivers of a parallel suite (this file on several workers, and
// a11y.mjs on the same range) pick one port: the second browser could not
// bind it and its driver drove the first driver's page, so a size or a
// state was measured under another driver's resize or navigation. Each
// measure also waits until the page itself reports the intended viewport,
// and a load only counts once the new document (not the last state's page
// on the same url) is live.
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { createInterface } from "node:readline";

const [chromePath, profile] = process.argv.slice(2);
const REGIONS = ["g", "c", "t", "n", "b", "i", "u"];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// GP-09 (decision 0080): on a CI runner (AL_CI=1, set only in ci.yml) the
// page-live wait gets one bounded retry at 3x and the watchdog 3x; locally
// both stay as they are.
const CI = process.env.AL_CI === "1";
const out = (o) => process.stdout.write(JSON.stringify(o) + "\n");
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
const killer = setTimeout(() => { out({ error: `watchdog: ${CI ? 900 : 300} s` }); quit(3); },
  CI ? 900000 : 300000);

// the OS-chosen port of this driver's own browser (never another one's).
// TEST-CDP-ENDPOINT-CI-WAIT (decision 0080): the poll widens 3x under
// AL_CI only and stops at once if Chrome has failed; locally 150 x 100 ms.
const ENDPOINT_POLLS = CI ? 450 : 150;
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
  if (r.result && r.result.exceptionDetails) {
    const d = r.result.exceptionDetails;
    throw new Error((d.exception && d.exception.description) || d.text || "evaluate failed");
  }
  return r.result && r.result.result ? r.result.result.value : undefined;
};
await send("Page.enable");
await send("Runtime.enable");
await send("Emulation.setEmulatedMedia", { features: [
  { name: "prefers-color-scheme", value: "dark" }, { name: "forced-colors", value: "none" },
  { name: "prefers-reduced-motion", value: "reduce" }] });

// -- in-page measurement (runs in the page; returns plain data) -------------
function measure(args) {
  const REG = args.regions;
  const doc = document;
  const de = doc.documentElement;
  const root = parseFloat(getComputedStyle(de).fontSize) || 16;
  const rendered = (el) => el.getClientRects().length > 0 &&
    getComputedStyle(el).visibility !== "hidden";
  const regionOf = (el) => {
    for (const r of REG) {
      const n = doc.getElementById("play-" + r);
      if (n && (n === el || n.contains(el))) { return r; }
    }
    return null;
  };
  const label = (el) => el.tagName.toLowerCase() + (el.id ? "#" + el.id : "") +
    (el.classList.length ? "." + Array.from(el.classList).slice(0, 2).join(".") : "");
  const words = (t) => (t || "").split(/\s+/).filter((w) => /[A-Za-z0-9]/.test(w));
  const ownText = (el) => Array.from(el.childNodes)
    .filter((n) => n.nodeType === 3).map((n) => n.nodeValue).join(" ").trim();
  const FORM = new Set(["INPUT", "SELECT", "TEXTAREA", "OPTION", "OPTGROUP"]);
  const CONTROL = "a[href], button, input:not([type=hidden]), select, textarea, summary, " +
    "[tabindex]:not([tabindex='-1'])";

  // G1: overflow on the block axis (cockpit) and nested scroll boxes (flow)
  function scrollIssues(scope) {
    const over = [];
    const scrollers = [];
    let overMax = 0;
    for (const el of scope.querySelectorAll("*")) {
      if (FORM.has(el.tagName) || !rendered(el)) { continue; }
      const sh = el.scrollHeight, ch = el.clientHeight, sw = el.scrollWidth, cw = el.clientWidth;
      if (ch > 0 && sh > ch) { overMax = Math.max(overMax, sh - ch); }
      if (ch > 0 && sh > ch + 1) {
        over.push({ region: regionOf(el), el: label(el), sh, ch });
      }
      const cs = getComputedStyle(el);
      const sx = /auto|scroll/.test(cs.overflowX), sy = /auto|scroll/.test(cs.overflowY);
      if ((sy && ch > 0 && sh > ch + 1) || (sx && cw > 0 && sw > cw + 1)) {
        scrollers.push({ region: regionOf(el), el: label(el), sh, ch, sw, cw });
      }
    }
    return { over: over.slice(0, 40), overCount: over.length, overMax,
      scrollers: scrollers.slice(0, 40), scrollerCount: scrollers.length };
  }

  // G7: (ratio, weight) of every rendered element that holds its own text
  function typeStyles(scope) {
    const seen = new Map();
    for (const el of scope.querySelectorAll("*")) {
      if (!ownText(el) || !rendered(el)) { continue; }
      const cs = getComputedStyle(el);
      const px = parseFloat(cs.fontSize);
      const weight = parseInt(cs.fontWeight, 10) || 400;
      const ratio = Math.round((px / root) * 10000) / 10000;
      const key = [regionOf(el), ratio, weight].join("|");
      if (!seen.has(key)) {
        seen.set(key, { region: regionOf(el), ratio, weight, px,
          el: label(el), text: ownText(el).slice(0, 40) });
      }
    }
    return Array.from(seen.values());
  }

  function docBox() {
    return { sh: de.scrollHeight, ch: de.clientHeight, sw: de.scrollWidth, cw: de.clientWidth };
  }

  function box(el) {
    const r = el.getBoundingClientRect();
    const sy = window.scrollY, sx = window.scrollX;
    return { top: r.top + sy, left: r.left + sx, width: r.width, height: r.height,
      bottom: r.bottom + sy };
  }

  // G2 / G4: the region box, its inner bottom and its content bottom
  function region(r) {
    const n = doc.getElementById("play-" + r);
    if (!n || !rendered(n)) { return null; }
    const b = box(n);
    const cs = getComputedStyle(n);
    const inner = b.bottom - (parseFloat(cs.borderBottomWidth) || 0) -
      (parseFloat(cs.paddingBottom) || 0);
    let content = b.top + (parseFloat(cs.borderTopWidth) || 0) + (parseFloat(cs.paddingTop) || 0);
    const sy = window.scrollY;
    for (const el of n.querySelectorAll("*")) {
      if (!rendered(el)) { continue; }
      const rr = el.getBoundingClientRect();
      if (rr.height > 0) { content = Math.max(content, rr.bottom + sy); }
    }
    const walker = doc.createTreeWalker(n, NodeFilter.SHOW_TEXT);
    const range = doc.createRange();
    for (let t = walker.nextNode(); t; t = walker.nextNode()) {
      if (!t.nodeValue.trim() || !t.parentElement || !rendered(t.parentElement)) { continue; }
      range.selectNodeContents(t);
      for (const rr of range.getClientRects()) { content = Math.max(content, rr.bottom + sy); }
    }
    const controls = [];
    for (const el of n.querySelectorAll(CONTROL)) {
      if (!rendered(el)) { continue; }
      const rr = el.getBoundingClientRect();
      controls.push({ el: label(el), w: rr.width, h: rr.height });
    }
    return { top: b.top, left: b.left, width: b.width, height: b.height, inner,
      content, words: words(n.innerText).length, controls,
      fit: n.getAttribute("data-fit") || "" };
  }

  // G9: an answer is found in its region, at its step, in the first 6 words
  function blockText(el) {
    let p = el;
    while (p && p !== doc.body) {
      const d = getComputedStyle(p).display;
      if (d !== "inline" && d !== "contents") { return p.innerText || p.textContent || ""; }
      p = p.parentElement;
    }
    return el.textContent || "";
  }
  function answer(a) {
    const scope = a.scope === "bar" ? doc.querySelector("header") :
      doc.getElementById("play-" + a.region);
    if (!scope || !rendered(scope)) { return { id: a.id, ok: false, why: "region missing" }; }
    const re = a.re ? new RegExp(a.re, a.flags || "") : null;
    const match = (t) => (re ? (t.match(re) || [null])[0] : (t.indexOf(a.text) >= 0 ? a.text : null));
    const hits = [];
    for (const el of scope.querySelectorAll("*")) {
      if (!rendered(el)) { continue; }
      if (a.kind === "first") {
        const rr = el.getBoundingClientRect();
        if (ownText(el) && rr.width > 1 && rr.height > 1) { hits.push(el); break; }
        continue;
      }
      const t = el.textContent || "";
      if (a.kind === "exact") {
        if (match(t.trim()) === t.trim() && t.trim()) { hits.push(el); }
      } else if (match(t) && !Array.from(el.children).some((c) => match(c.textContent || ""))) {
        hits.push(el);
      }
    }
    if (!hits.length) { return { id: a.id, ok: false, why: "not found" }; }
    let best = null;
    for (const el of hits) {
      const ratio = parseFloat(getComputedStyle(el).fontSize) / root;
      let pos = 0;
      if (a.kind !== "first") {
        const text = blockText(el);
        const all = words(text);
        const want = words(match(text) || match(el.textContent || "") || "");
        pos = want.length ? -1 : 0;
        for (let i = 0; i + want.length <= all.length && pos < 0; i++) {
          if (want.every((w, j) => all[i + j].indexOf(w) >= 0)) { pos = i; }
        }
        if (pos < 0) { pos = 99; }
      }
      const small = ratio < a.min - 0.001;
      const cand = { id: a.id, ok: !small && pos < 6, ratio: Math.round(ratio * 1000) / 1000,
        pos, el: label(el), why: small ? "too small" : (pos < 6 ? "" : "past word 6") };
      if (!best || (cand.ok && !best.ok) || (!best.ok && cand.ratio > best.ratio)) { best = cand; }
      if (best.ok) { break; }
    }
    return best;
  }

  function frame() {
    const bar = doc.querySelector("header");
    const foot = doc.querySelector("footer");
    const main = doc.querySelector("main");
    const play = doc.getElementById("panel-play");
    const ms = main ? getComputedStyle(main) : null;
    const cols = play ? Array.from(play.children).filter(rendered).map((el) => ({
      el: label(el), height: el.getBoundingClientRect().height, sh: el.scrollHeight })) : [];
    return { bar: bar ? bar.getBoundingClientRect().height : null,
      foot: foot ? foot.getBoundingClientRect().height : null,
      mainPad: ms ? [parseFloat(ms.paddingTop), parseFloat(ms.paddingBottom)] : null,
      play: play ? play.getBoundingClientRect().height : null, cols };
  }

  // PLAY-FEED-VERB-FIT: each feed trade row's buyer, verb (a bare text
  // node, measured through a Range) and item; a part is clipped when its
  // text is wider than its box, and the verb when its box runs into the
  // item or past the row
  function tradeRows(play) {
    const out = [];
    for (const li of play.querySelectorAll("#play-t .feed-trade")) {
      if (!rendered(li)) { continue; }
      const part = (cls) => {
        const n = li.querySelector(cls);
        if (!n || !rendered(n)) { return null; }
        const rr = n.getBoundingClientRect();
        const cs = getComputedStyle(n);
        return { text: n.textContent, title: n.getAttribute("title"),
          sw: n.scrollWidth, cw: n.clientWidth, left: rr.left, right: rr.right,
          fs: parseFloat(cs.fontSize), ellipsis: cs.textOverflow === "ellipsis" };
      };
      const item = part(".feed-item");
      const verbNode = Array.from(li.childNodes)
        .find((n) => n.nodeType === 3 && n.nodeValue.trim());
      let verb = null;
      if (verbNode) {
        const range = doc.createRange();
        range.selectNodeContents(verbNode);
        const vr = range.getBoundingClientRect();
        verb = { text: verbNode.nodeValue.trim(), left: vr.left, right: vr.right,
          width: vr.width };
      }
      const lr = li.getBoundingClientRect();
      out.push({ buyer: part(".feed-buyer"), verb, item, price: part(".feed-price"),
        right: part(".feed-right"), dismiss: part(".feed-dismiss"),
        row: { left: lr.left, right: lr.right, sw: li.scrollWidth, cw: li.clientWidth } });
    }
    return out;
  }

  function playBlock() {
    const play = doc.getElementById("panel-play");
    if (!play) { return null; }
    // G5 (design 0001 SR-COUNT ruling 2026-11-24): an element that is
    // visually hidden for screen readers (it or an ancestor clipped to
    // nothing: clip rect(0 0 0 0) or clip-path inset(50%), the .sr-only
    // pattern) is not a visible element; it is counted apart as "hidden"
    const clipped = new Map();
    const srOnly = (el) => {
      if (!el || el === play) { return false; }
      if (clipped.has(el)) { return clipped.get(el); }
      const cs = getComputedStyle(el);
      const own = cs.clipPath === "inset(50%)" || cs.clip === "rect(0px, 0px, 0px, 0px)";
      const v = own || srOnly(el.parentElement);
      clipped.set(el, v);
      return v;
    };
    let elements = 0;
    let hidden = 0;
    let srClass = 0;
    let srClassHidden = 0;
    const controls = [];
    for (const el of play.querySelectorAll("*")) {
      if (!rendered(el)) { continue; }
      if (srOnly(el)) { hidden += 1; } else { elements += 1; }
      // the guard on the clip test: every .sr-only element must read hidden
      if (el.classList.contains("sr-only")) {
        srClass += 1;
        if (srOnly(el)) { srClassHidden += 1; }
      }
      // G6 counts every control, a visually hidden one included (it is
      // still a keyboard stop)
      if (el.matches(CONTROL)) {
        const rr = el.getBoundingClientRect();
        controls.push({ region: regionOf(el), el: label(el), w: rr.width, h: rr.height });
      }
    }
    const regions = {};
    for (const r of REG) { regions[r] = region(r); }
    return { words: words(play.innerText).length, elements, hidden,
      srClass: [srClass, srClassHidden], controls,
      trades: tradeRows(play),
      type: typeStyles(play), scroll: scrollIssues(play), regions,
      answers: (args.answers || []).map(answer), frame: frame() };
  }

  const tabs = Array.from(doc.querySelectorAll("[role=tab]"));
  const playTab = tabs.find((t) => t.getAttribute("aria-controls") === "panel-play");
  const res = { vw: window.innerWidth, vh: window.innerHeight, root, panels: {} };
  if (playTab) { playTab.click(); }
  window.scrollTo(0, 0);
  res.doc = docBox();
  res.play = playBlock();
  if (args.tabs) {
    for (const t of tabs) {
      const id = t.getAttribute("aria-controls");
      const p = id && doc.getElementById(id);
      if (!p || id === "panel-play") { continue; }
      t.click();
      window.scrollTo(0, 0);
      res.panels[id] = { doc: docBox(), scroll: scrollIssues(p), type: typeStyles(p) };
    }
    if (playTab) { playTab.click(); }
  }
  return res;
}

function placeholder() {
  for (const n of document.querySelectorAll("[data-legacy]")) { n.hidden = true; }
  for (const r of ["g", "c", "t", "n", "b", "i", "u"]) {
    const n = document.getElementById("play-" + r);
    if (n) { n.setAttribute("data-fit", "yes"); }
  }
  return true;
}

function metrics(rows) {
  const host = document.createElement("div");
  host.style.cssText = "position:absolute;left:-10000px;top:0;white-space:nowrap";
  document.body.appendChild(host);
  const res = [];
  for (const r of rows) {
    const width = (extra) => {
      const s = document.createElement("span");
      s.textContent = r.text;
      s.style.cssText = `font-size:${r.px}px;font-weight:${r.weight};white-space:nowrap;` + extra;
      host.appendChild(s);
      const w = s.getBoundingClientRect().width;
      s.remove();
      return Math.round(w * 10) / 10;
    };
    res.push({ key: r.key, chars: r.text.length, px: r.px, weight: r.weight,
      width: width(""), spaced: width("letter-spacing:0.12em;word-spacing:0.16em") });
  }
  host.remove();
  return res;
}

const call = (fn, arg) => evaluate(`(${fn.toString()})(${JSON.stringify(arg)})`);

// true once the page reports the intended viewport to script and to its
// media queries (the em queries of app.css pick the size class), then two
// frames so layout runs at that size; a size never applied is answered as
// measured and the Python side names it (vw / vh of every measure)
const applied = (w, h) => evaluate(`new Promise((r) => {
  const want = matchMedia("(width: ${w}px) and (height: ${h}px)");
  let n = 0;
  const step = () => {
    if (innerWidth === ${w} && innerHeight === ${h} && want.matches) {
      requestAnimationFrame(() => requestAnimationFrame(() => r(true)));
    } else if (++n > 120) { r(false); } else { requestAnimationFrame(step); }
  };
  step();
})`);

async function resize(w, h) {
  await send("Emulation.setDeviceMetricsOverride",
    { width: w, height: h, deviceScaleFactor: 1, mobile: false });
  await applied(w, h);
}

async function load(url) {
  // live once the feed is up and the first state has painted
  for (const tries of CI ? [100, 300] : [100]) {
    // the last state's page has the same url; mark it so only a new
    // document can count as live
    try { await evaluate("window.__alFitOld = true"); } catch { /* no page */ }
    await send("Page.navigate", { url: "about:blank" });
    await send("Page.navigate", { url });
    for (let i = 0; i < tries; i++) {
      await sleep(100);
      let ok = false;
      try {
        ok = await evaluate("!window.__alFitOld && document.readyState === 'complete' && " +
          "!!document.getElementById('panel-play') && " +
          "/^(running|done|idle|blocked)$/.test((document.getElementById('reading') || {getAttribute(){return ''}}).getAttribute('data-state') || '')");
      } catch { ok = false; }
      if (ok) { await sleep(350); return true; }
    }
  }
  return false;
}

async function run(cmd) {
  if (cmd.cmd === "state") {
    const live = await load(cmd.url);
    const sizes = {};
    for (const [w, h] of cmd.sizes) {
      await resize(w, h);
      sizes[`${w}x${h}`] = await call(measure,
        { regions: REGIONS, answers: cmd.answers || [], tabs: true });
    }
    return { name: cmd.name, live, sizes };
  }
  if (cmd.cmd === "placeholder") {
    await call(placeholder, null);
    const sizes = {};
    for (const [w, h] of cmd.sizes) {
      await resize(w, h);
      sizes[`${w}x${h}`] = await call(measure, { regions: REGIONS, answers: [], tabs: false });
    }
    return { name: "placeholder", sizes };
  }
  if (cmd.cmd === "metrics") {
    await resize(1280, 760);
    return { name: "metrics", rows: await call(metrics, cmd.rows) };
  }
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
