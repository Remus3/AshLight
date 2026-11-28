// RUN-BUDGET-TESTS-DASH (B14, research 0048): measure the dashboard's paint
// cost in headless Chrome over the DevTools protocol. Driven by
// tests/test_dash_perf.py against a synthetic test core on a temp runtime;
// not a node --test file on its own.
//
//   node dash_perf.mjs <chrome.exe> <profile dir> <dashboard url> <test log> <pushes.json>
//
// <test log> is the test's own temp Client.txt (never the game's); this
// script appends each text block of <pushes.json> to it, one every
// PUSH_GAP_MS, so the core pushes one state frame per block.
// Prints one JSON line {"live", "elements", "idle_ms_per_s", "idle_pushes",
// "push_task_ms", "pushes", "task_ms_per_push", "heap_bytes", "issues"}.
// Node's global WebSocket (Node 22+) is the only client; no npm package.
import { spawn } from "node:child_process";
import { appendFileSync, readFileSync, rmSync } from "node:fs";
import path from "node:path";

const [chromePath, profile, url, logPath, pushesPath] = process.argv.slice(2);
const blocks = JSON.parse(readFileSync(pushesPath, "utf8"));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// GP-09 (decision 0080): on a CI runner (AL_CI=1) the waits widen 3x.
const CI = process.env.AL_CI === "1";
const IDLE_MS = 5000;     // the idle window (B14: task time per idle second)
const PUSH_GAP_MS = 600;  // above the feed's 4 frames a second (B8)
const SETTLE_MS = 1500;   // after the page is live, before any window
// TEST-CDP-OS-PORT: the OS picks the DevTools port (--remote-debugging-port=0,
// read back from this profile's DevToolsActivePort, as play_fit.mjs does).
// A random port of a range shared with dash_console.mjs let two drivers of a
// parallel suite pick one port; the second browser could not bind it and
// its driver attached to the first driver's page.
const portFile = path.join(profile, "DevToolsActivePort");
try { rmSync(portFile, { force: true }); } catch { /* none yet */ }
const chrome = spawn(chromePath, ["--headless=new", "--disable-gpu", "--in-process-gpu",
  "--no-first-run", "--no-default-browser-check", "--disable-extensions",
  "--remote-debugging-port=0", `--user-data-dir=${profile}`, "about:blank"],
  { stdio: "ignore" });
let chromeExit = null;
// a clean 0 exit may be a hand-off to a running browser: keep polling then
chrome.on("exit", (code, signal) => { if (signal || code) { chromeExit = signal || code; } });
const killer = setTimeout(() => { chrome.kill(); process.exit(3); }, CI ? 180000 : 60000);

// the OS-chosen port of this driver's own browser (never another one's).
// TEST-CDP-ENDPOINT-CI-WAIT (decision 0080): the DevTools endpoint poll
// widens 3x under AL_CI only (a cold runner's first Chrome launch outran
// the fixed bound, TEST-A11Y-NEWEST-DEVTOOLS) and stops at once if Chrome
// has failed; locally it stays 100 x 100 ms, as before the row (the
// port is now read from DevToolsActivePort first, TEST-CDP-OS-PORT).
const ENDPOINT_POLLS = CI ? 300 : 100;
let port = 0;
let targets = null;
for (let i = 0; i < ENDPOINT_POLLS && !targets && chromeExit === null; i++) {
  if (!port) {
    try {
      const first = readFileSync(portFile, "utf8").split(/\r?\n/)[0].trim();
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
  chrome.kill();
  console.log(JSON.stringify({ error: "no DevTools endpoint" + (chromeExit === null
    ? ` after ${ENDPOINT_POLLS} polls` : ` (browser exited: ${chromeExit})`) }));
  process.exit(2);
}
const page = targets.find((t) => t.type === "page" &&
  String(t.webSocketDebuggerUrl).startsWith(`ws://127.0.0.1:${port}/`));
if (!page) { chrome.kill(); console.log(JSON.stringify({ error: "no page target" })); process.exit(2); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let seq = 0;
const pending = new Map();
const issues = [];
ws.addEventListener("message", (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  const p = m.params || {};
  if (m.method === "Runtime.consoleAPICalled" && (p.type === "error" || p.type === "assert")) {
    issues.push(["console." + p.type, p.args.map((a) => a.value ?? a.description).join(" ")]);
  } else if (m.method === "Runtime.exceptionThrown") {
    const d = p.exceptionDetails || {};
    issues.push(["exception", (d.exception && d.exception.description) || d.text || ""]);
  }
});
const send = (method, params = {}) => new Promise((r) => {
  const i = ++seq; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params }));
});
const value = async (expression) => {
  const r = await send("Runtime.evaluate", { expression, returnByValue: true });
  return r.result && r.result.result ? r.result.result.value : undefined;
};
// TaskDuration (seconds of main-thread task time) and JSHeapUsedSize.
const metrics = async () => {
  const r = await send("Performance.getMetrics");
  const out = {};
  for (const m of (r.result && r.result.metrics) || []) { out[m.name] = m.value; }
  return out;
};

await send("Page.enable");
await send("Runtime.enable");
await send("Performance.enable", { timeDomain: "timeTicks" });
// Count the page's own state frames: wrap EventSource so every instance the
// dashboard makes also bumps a counter on each "state" message.
await send("Page.addScriptToEvaluateOnNewDocument", { source:
  "(function () { var O = window.EventSource; window.__alPushes = 0;" +
  " function W(u, o) { var e = new O(u, o);" +
  "  e.addEventListener('state', function () { window.__alPushes++; }); return e; }" +
  " W.prototype = O.prototype; W.CONNECTING = 0; W.OPEN = 1; W.CLOSED = 2;" +
  " window.EventSource = W; })();" });
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url });

// the page is live once the bar status word leaves pending / failed
let live = false;
for (let i = 0; i < (CI ? 240 : 80) && !live; i++) {
  await sleep(100);
  live = !!(await value(
    "!!document.getElementById('build-title') && /^(running|done|idle|blocked)$/.test((document.getElementById('reading') || {getAttribute(){return ''}}).getAttribute('data-state') || '')"));
}
if (!live) {
  console.log(JSON.stringify({ live, issues }));
  clearTimeout(killer); ws.close(); chrome.kill(); process.exit(0);
}
await sleep(SETTLE_MS);

// Elements: the whole document as the player sees it on load.
const elements = await value("document.getElementsByTagName('*').length");

// Idle: no log line, the page's own timers only.
let p0 = await value("window.__alPushes");
let m0 = await metrics();
let t0 = Date.now();
await sleep(IDLE_MS);
let m1 = await metrics();
let p1 = await value("window.__alPushes");
const idleS = (Date.now() - t0) / 1000;
const idleMsPerS = ((m1.TaskDuration - m0.TaskDuration) * 1000) / idleS;
const idlePushes = p1 - p0;

// Pushes: one log block every PUSH_GAP_MS, then one gap for the last frame.
p0 = await value("window.__alPushes");
m0 = await metrics();
for (const b of blocks) {
  appendFileSync(logPath, b);
  await sleep(PUSH_GAP_MS);
}
await sleep(PUSH_GAP_MS);
m1 = await metrics();
p1 = await value("window.__alPushes");
const pushes = p1 - p0;
const pushTaskMs = (m1.TaskDuration - m0.TaskDuration) * 1000;

// Heap after a full collection: what the page keeps, not what it churns.
await send("HeapProfiler.enable");
await send("HeapProfiler.collectGarbage");
const heap = (await metrics()).JSHeapUsedSize;

console.log(JSON.stringify({
  live, elements, idle_ms_per_s: idleMsPerS, idle_pushes: idlePushes,
  push_task_ms: pushTaskMs, pushes, task_ms_per_push: pushes ? pushTaskMs / pushes : null,
  heap_bytes: heap, issues,
}));
clearTimeout(killer);
ws.close();
chrome.kill();
