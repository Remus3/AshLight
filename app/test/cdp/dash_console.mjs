// UX-REGRESSION-SWEEP: load the dashboard in headless Chrome over the
// DevTools protocol and report every console error, uncaught exception,
// failed load and CSP violation. Driven by tests/test_dash_console.py
// against a synthetic core; not a node --test file on its own.
//
//   node dash_console.mjs <chrome.exe> <profile dir> <dashboard url>
//
// Prints one JSON line {"issues": [[tag, kind, text], ...], "views": {...}}.
// Node's global WebSocket (Node 22+) is the only client; no npm package.
import { spawn } from "node:child_process";

const [chromePath, profile, url] = process.argv.slice(2);
const VIEWS = [
  { tag: "360-dark", w: 360, scheme: "dark", forced: "none" },
  { tag: "1440-light", w: 1440, scheme: "light", forced: "none" },
  { tag: "768-forced", w: 768, scheme: "dark", forced: "active" },
];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const port = 9500 + Math.floor(Math.random() * 400);
const chrome = spawn(chromePath, ["--headless=new", "--disable-gpu", "--in-process-gpu",
  "--no-first-run", "--no-default-browser-check", "--disable-extensions",
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "about:blank"],
  { stdio: "ignore" });
const killer = setTimeout(() => { chrome.kill(); process.exit(3); }, 60000);

let targets = null;
for (let i = 0; i < 100 && !targets; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); }
  catch { await sleep(100); }
}
if (!targets) { chrome.kill(); console.log(JSON.stringify({ error: "no DevTools endpoint" })); process.exit(2); }
const page = targets.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let seq = 0;
let tag = "start";
const pending = new Map();
const issues = [];
ws.addEventListener("message", (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  const p = m.params || {};
  if (m.method === "Runtime.consoleAPICalled" && (p.type === "error" || p.type === "assert")) {
    issues.push([tag, "console." + p.type, p.args.map((a) => a.value ?? a.description).join(" ")]);
  } else if (m.method === "Runtime.exceptionThrown") {
    const d = p.exceptionDetails || {};
    issues.push([tag, "exception", (d.exception && d.exception.description) || d.text || ""]);
  } else if (m.method === "Log.entryAdded" && p.entry.level === "error") {
    issues.push([tag, "log." + p.entry.source, p.entry.text + " " + (p.entry.url || "")]);
  }
});
const send = (method, params = {}) => new Promise((r) => {
  const i = ++seq; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params }));
});
await send("Page.enable");
await send("Runtime.enable");
await send("Log.enable");
// A CSP violation also reaches the console, but the event names the directive.
await send("Page.addScriptToEvaluateOnNewDocument", { source:
  "document.addEventListener('securitypolicyviolation', function (e) {" +
  " console.error('CSP violation: ' + e.violatedDirective + ' ' + e.blockedURI); });" });

// Every fold opens (the graphics fold reads the PC on open, so it stays shut),
// then the page gets a moment to paint what the folds hold.
const PROBE = `(function () {
  document.querySelectorAll("details").forEach(function (d) { if (d.id !== "gfx") d.open = true; });
  return new Promise(function (r) { setTimeout(function () {
    var de = document.documentElement;
    r({ sw: de.scrollWidth, cw: de.clientWidth,
        cards: document.querySelectorAll("main .card:not([hidden])").length });
  }, 400); });
})()`;
const views = {};
for (const v of VIEWS) {
  tag = v.tag;
  await send("Emulation.setDeviceMetricsOverride", { width: v.w, height: 900, deviceScaleFactor: 1, mobile: false });
  await send("Emulation.setEmulatedMedia", { features: [
    { name: "prefers-color-scheme", value: v.scheme }, { name: "forced-colors", value: v.forced }] });
  await send("Page.navigate", { url: "about:blank" });
  await send("Page.navigate", { url });
  // the page is live once the feed pill says so (SSE open)
  let live = false;
  for (let i = 0; i < 80 && !live; i++) {
    await sleep(100);
    const r = await send("Runtime.evaluate", { expression:
      "!!document.getElementById('build-title') && /live/.test((document.querySelector('header') || {}).textContent || '')",
      returnByValue: true });
    live = !!(r.result && r.result.result && r.result.result.value);
  }
  const r = await send("Runtime.evaluate", { expression: PROBE, returnByValue: true, awaitPromise: true });
  views[v.tag] = Object.assign({ live }, (r.result && r.result.result && r.result.result.value) || {});
}
tag = "end";
await sleep(200);
console.log(JSON.stringify({ issues, views }));
clearTimeout(killer);
ws.close();
chrome.kill();
