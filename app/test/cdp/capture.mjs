// TEST-CAPTURE-HELPER (F-147, AUTO-15): the one image-capture path of the
// repo. It renders AshLight's OWN page, served by a DEMO core on 127.0.0.1,
// inside a headless browser, and saves that page as a PNG. Never the screen,
// never a window, never the game, never a game image (CLAUDE.md game ToS
// floor). The static floor scan (tests/test_floor_static.py) bans every
// other protocol image call, browser grab and OS screen grab in the tree;
// this file holds its one allow entry.
//
//   node capture.mjs <browser exe> <profile dir> <page url> <out.png>
//        [--width=1440] [--height=900] [--scheme=dark|light] [--wait-ms=800]
//        [--tab=play|build|run|settings]
//   node capture.mjs <browser exe> <profile dir> <overlay file url> <out.png>
//        --core=<demo core url> [--width=..] [--height=..] [--scheme=..]
//   node capture.mjs --plan <browser exe> <profile dir> <page url> <out.png>
//
// <page url> is http://127.0.0.1:<port>/<page>#token=<token>. --tab shows
// that dashboard tab (web/tabs.js ALTabs.show, AshLight's own page code)
// before the capture and checks it is the selected tab.
// TEST-SHOTS-TABS: the one other page is the file URL of
// app/overlay/index.html under this repository's app folder (no query, no
// fragment); it needs --core=<demo core url>, which passes every check
// below in place of the page url, and takes no --tab. Any other file URL or
// target is refused. The overlay page gets no port or token (it renders its
// own waiting state and opens no connection); --scheme picks a plain dark or
// light ground behind its transparent body.
// Before any browser starts, every check below must pass, in this order:
//   1. no network: the url is plain http to exactly 127.0.0.1 with an
//      explicit port that is not the core port or the dev port (both read
//      from server/al/ports.py; unreadable = refused), no user info, not an
//      /api/ or /events path, a token in the fragment; the out path ends in
//      .png inside an existing folder; the profile folder is new or empty
//      (an in-use profile would hand the page to a visible browser).
//   2. loopback only, no proxy: GET /api/hello proves the listener holds the
//      token and bound that port (decision 0054) before the token is sent;
//      /api/health names AshLight and the same port.
//   3. the demo marker: /api/state names the log the core tails; its path
//      text must hold no game folder part (checked before any stat), the
//      file must be Client.txt, and its folder must hold AshLight's demo
//      marker ashlight-demo.json with "ashlight_demo": 1 (decision 0049).
// A refusal prints {"refused": "<why>"} and exits 2 with no file written and
// no browser started. --plan runs every check and prints the browser command
// it would run, starting nothing. The browser runs headless (no window),
// software rendered, at below-normal priority, its DevTools port chosen by
// the OS (--remote-debugging-port=0, read back from DevToolsActivePort). The
// page is checked again (same origin, an HTML document, the demo marker
// still holds) right before the capture call. Exit 0 prints {"ok": true,
// "out", "bytes", "width", "height"}; 3 = browser failure; 4 = watchdog.
// Node's own http client and global WebSocket only; no npm package.
import { spawn } from "node:child_process";
import { createHmac, randomBytes } from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const ROOT = path.resolve(HERE, "..", "..", "..");
export const LOOPBACK = "127.0.0.1";
export const MARKER = "ashlight-demo.json";
export const MARKER_MAX_BYTES = 64 * 1024;
export const LOG_NAME = "Client.txt";
const GAME_PARTS = ["steamapps", "path of exile 2"];
export const TABS = Object.freeze(["play", "build", "run", "settings"]);
// the plain ground behind the transparent overlay page, per --scheme
const GROUND = Object.freeze({ dark: { r: 30, g: 32, b: 36, a: 1 },
  light: { r: 226, g: 228, b: 232, a: 1 } });
const MAX_ANSWER = 4 * 1024 * 1024;
const CI = process.env.AL_CI === "1";
// one loopback GET (core or DevTools); decision 0080 widens it 3x in CI,
// where a cold headless browser can take over 5 s to list its targets
const GET_MS = CI ? 15000 : 5000;

// The browser command: headless only, no window, no GPU, no extension, no
// first-run UI, an OS-chosen DevTools port. Frozen: no option changes it.
export const BROWSER_FLAGS = Object.freeze([
  "--headless=new", "--disable-gpu", "--in-process-gpu", "--no-first-run",
  "--no-default-browser-check", "--disable-extensions", "--disable-sync",
  "--hide-scrollbars", "--mute-audio", "--remote-debugging-port=0",
]);

let browserChild = null; // the one browser this run started, killed on any exit

export class Refused extends Error {}
const refuse = (why) => { throw new Refused(why); };

// --------------------------------------------------------------- 1. offline

/** {al, dev}: the core port and the dev port from server/al/ports.py. */
export function readPorts(root = ROOT) {
  let text;
  try { text = fs.readFileSync(path.join(root, "server", "al", "ports.py"), "utf8"); }
  catch { refuse("server/al/ports.py is unreadable; the live ports are unknown"); }
  const one = (name) => {
    const m = new RegExp(`^${name}\\s*=\\s*(\\d+)\\b`, "m").exec(text);
    if (!m) { refuse(`server/al/ports.py names no ${name}`); }
    return Number(m[1]);
  };
  return { al: one("AL_PORT"), dev: one("AL_DEV_PORT") };
}

/** {port, token, origin, href} of a page url, or Refused. No network. */
export function checkUrl(raw, livePorts) {
  if (typeof raw !== "string" || !raw.startsWith(`http://${LOOPBACK}:`)) {
    refuse(`the page must be http://${LOOPBACK}:<port>/...; got ${String(raw).slice(0, 80)}`);
  }
  let u;
  try { u = new URL(raw); } catch { refuse("the page url does not parse"); }
  if (u.protocol !== "http:" || u.hostname !== LOOPBACK) { refuse(`only ${LOOPBACK} is allowed`); }
  if (u.username || u.password) { refuse("the page url carries user info"); }
  const m = /^http:\/\/127\.0\.0\.1:(\d{1,5})(?:[/?#]|$)/.exec(raw);
  const port = m ? Number(m[1]) : NaN;
  if (!m || String(port) !== u.port || port < 1 || port > 65535) {
    refuse("the page url needs an explicit port");
  }
  if (port === livePorts.al || port === livePorts.dev) {
    refuse(`port ${port} is a live AshLight core; only a demo core is captured`);
  }
  if (u.pathname.startsWith("/api/") || u.pathname === "/events") {
    refuse("an API path is not a page");
  }
  const tm = /(?:^#|&)token=([0-9A-Za-z_-]+)(?:&|$)/.exec(u.hash);
  if (!tm) { refuse("the page url carries no #token="); }
  return { port, token: tm[1], origin: `http://${LOOPBACK}:${port}`, href: u.href };
}

/** The file URL of app/overlay/index.html under root's app folder. */
export function overlayUrl(root = ROOT) {
  return pathToFileURL(path.join(root, "app", "overlay", "index.html")).href;
}

/** True when raw is exactly the overlay page's file URL (no query or
    fragment; case ignored on Windows). Text only, no stat. */
export function isOverlayUrl(raw, root = ROOT) {
  if (typeof raw !== "string" || !raw.startsWith("file:")) { return false; }
  let u;
  try { u = new URL(raw); } catch { return false; }
  if (u.search || u.hash || u.username || u.password) { return false; }
  const want = new URL(overlayUrl(root));
  if (u.host !== want.host) { return false; }
  let a;
  let b;
  try { a = decodeURIComponent(u.pathname); b = decodeURIComponent(want.pathname); }
  catch { return false; }
  return process.platform === "win32" ? a.toLowerCase() === b.toLowerCase() : a === b;
}

/** {target, page}: target is the checked demo core (the url check of the
    page, or of --core for the overlay page); page is {href, overlay}. */
export function checkTarget(opts, livePorts, root = ROOT) {
  if (typeof opts.url === "string" && opts.url.startsWith("file:")) {
    if (!isOverlayUrl(opts.url, root)) {
      refuse("the only file page is app/overlay/index.html of this repository");
    }
    if (!opts.core) { refuse("the overlay page needs --core=<demo core url>"); }
    if (opts.tab) { refuse("--tab is for the dashboard page, not the overlay page"); }
    return { target: checkUrl(opts.core, livePorts),
      page: { href: overlayUrl(root), overlay: true } };
  }
  if (opts.core) { refuse("--core goes only with the overlay page"); }
  const target = checkUrl(opts.url, livePorts);
  return { target, page: { href: target.href, overlay: false } };
}

/** The resolved out path, or Refused: a .png in an existing folder. */
export function checkOut(out) {
  if (typeof out !== "string" || !out.toLowerCase().endsWith(".png")) {
    refuse("the out path must end in .png");
  }
  const abs = path.resolve(out);
  let st;
  try { st = fs.statSync(path.dirname(abs)); } catch { st = null; }
  if (!st || !st.isDirectory()) { refuse("the out folder does not exist"); }
  if (fs.existsSync(abs) && !fs.statSync(abs).isFile()) { refuse("the out path is not a file"); }
  return abs;
}

/** The resolved profile folder, or Refused: missing or empty. */
export function checkProfile(dir) {
  if (typeof dir !== "string" || !dir) { refuse("a profile folder is needed"); }
  const abs = path.resolve(dir);
  if (fs.existsSync(abs)) {
    if (!fs.statSync(abs).isDirectory() || fs.readdirSync(abs).length) {
      refuse("the profile folder must be new or empty");
    }
  }
  return abs;
}

/** The first path part naming a game folder, else null. Text only. */
export function gamePathPart(text) {
  for (const part of String(text).split(/[\\/]+/)) {
    if (GAME_PARTS.includes(part.trim().toLowerCase())) { return part; }
  }
  return null;
}

// --------------------------------------------------------------- 2. network

/** GET 127.0.0.1:port path -> {status, body}. Node's http client: no proxy. */
function get(port, p, headers = {}) {
  return new Promise((resolve, reject) => {
    const req = http.get({ host: LOOPBACK, port, path: p, headers, timeout: GET_MS,
      agent: false }, (res) => {
      const chunks = [];
      let n = 0;
      res.on("data", (c) => {
        n += c.length;
        if (n > MAX_ANSWER) { req.destroy(new Error("answer too large")); return; }
        chunks.push(c);
      });
      res.on("end", () => resolve({ status: res.statusCode,
        body: Buffer.concat(chunks).toString("utf8") }));
    });
    req.on("timeout", () => req.destroy(new Error("timed out")));
    req.on("error", reject);
  });
}

async function getJson(port, p, headers) {
  let r;
  try { r = await get(port, p, headers); }
  catch (e) { refuse(`no AshLight core answers on port ${port} (${e.message})`); }
  if (r.status !== 200) { refuse(`${p} answered ${r.status}; not an AshLight core page`); }
  try { return JSON.parse(r.body); } catch { refuse(`${p} is not JSON`); }
}

const mac = (token, text) => createHmac("sha256", Buffer.from(token, "ascii"))
  .update(Buffer.from(text, "ascii")).digest("hex");

/** Decision 0054: the listener proves the token and its port first. */
async function hello(port, token) {
  const nonce = randomBytes(16).toString("hex");
  const doc = await getJson(port, "/api/hello", {
    "X-AL-Hello-Nonce": nonce, "X-AL-Hello-Proof": mac(token, "client" + nonce) });
  if (!doc || doc.port !== port || typeof doc.proof !== "string"
      || doc.proof !== mac(token, "server" + nonce + String(port))) {
    refuse("the listener failed the hello proof; not the core of this token");
  }
}

/** The demo log path once every demo check holds, else Refused. */
export async function checkDemoCore(target) {
  const { port, token } = target;
  await hello(port, token);
  const auth = { "X-AL-Token": token };
  const health = await getJson(port, "/api/health", auth);
  if (!health || health.name !== "AshLight" || health.port !== port) {
    refuse("the listener is not an AshLight core on this port");
  }
  const state = await getJson(port, "/api/state", auth);
  const log = state && state.tailer && state.tailer.path;
  if (typeof log !== "string" || !log) { refuse("the core names no log; not a demo core"); }
  // the text check runs first: a game folder is never stat'ed
  const part = gamePathPart(log);
  if (part !== null) { refuse(`the core reads a game folder log (${part}); not a demo core`); }
  if (path.basename(log).toLowerCase() !== LOG_NAME.toLowerCase()) {
    refuse("the core's log is not a Client.txt; not a demo core");
  }
  const marker = path.join(path.dirname(path.resolve(log)), MARKER);
  let doc = null;
  try {
    const st = fs.lstatSync(marker);
    if (st.isFile() && st.size <= MARKER_MAX_BYTES) {
      doc = JSON.parse(fs.readFileSync(marker, "utf8"));
    }
  } catch { doc = null; }
  if (!doc || typeof doc !== "object" || Array.isArray(doc) || doc.ashlight_demo !== 1) {
    refuse(`the core's log folder holds no demo marker ${MARKER}; not a demo core`);
  }
  return log;
}

// --------------------------------------------------------------- 3. capture

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function parseArgs(argv) {
  const opts = { width: 1440, height: 900, scheme: "dark", waitMs: 800, plan: false,
    tab: null, core: null };
  const pos = [];
  for (const a of argv) {
    const m = /^--(width|height|scheme|wait-ms|tab|core)=(.*)$/.exec(a);
    if (a === "--plan") { opts.plan = true; }
    else if (m) {
      if (m[1] === "scheme") {
        if (!["dark", "light"].includes(m[2])) { refuse("--scheme is dark or light"); }
        opts.scheme = m[2];
      } else if (m[1] === "tab") {
        if (!TABS.includes(m[2])) { refuse(`--tab is one of ${TABS.join(", ")}`); }
        opts.tab = m[2];
      } else if (m[1] === "core") {
        if (!m[2]) { refuse("--core needs a demo core url"); }
        opts.core = m[2];
      } else {
        const n = Number(m[2]);
        const [lo, hi] = m[1] === "wait-ms" ? [0, 10000] : [200, 4000];
        if (!Number.isInteger(n) || n < lo || n > hi) { refuse(`--${m[1]} out of range`); }
        opts[m[1] === "wait-ms" ? "waitMs" : m[1]] = n;
      }
    } else if (a.startsWith("--")) { refuse(`unknown option ${a}`); }
    else { pos.push(a); }
  }
  if (pos.length !== 4) { refuse("usage: capture.mjs [--plan] <browser> <profile dir> <page url> <out.png>"); }
  [opts.browser, opts.profile, opts.url, opts.out] = pos;
  return opts;
}

function below(pid) {
  try { os.setPriority(pid, os.constants.priority.PRIORITY_BELOW_NORMAL); } catch { /* best effort */ }
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

async function capture(opts, target) {
  const want = opts.page; // {href, overlay}: the checked page to open
  below(process.pid); // the browser inherits below-normal from this process
  const args = [...BROWSER_FLAGS, `--user-data-dir=${opts.profile}`, "about:blank"];
  const child = spawn(opts.browser, args, { stdio: "ignore", windowsHide: true });
  browserChild = child;
  below(child.pid);
  let ws = null;
  try {
    const dport = await devtoolsPort(opts.profile, child);
    const list = JSON.parse((await get(dport, "/json/list")).body);
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
      const r = await send("Runtime.evaluate", { expression, returnByValue: true });
      return r.result && r.result.result ? r.result.result.value : undefined;
    };
    await send("Page.enable");
    await send("Emulation.setDeviceMetricsOverride",
      { width: opts.width, height: opts.height, deviceScaleFactor: 1, mobile: false });
    await send("Emulation.setEmulatedMedia",
      { features: [{ name: "prefers-color-scheme", value: opts.scheme }] });
    if (want.overlay) {
      await send("Emulation.setDefaultBackgroundColorOverride", { color: GROUND[opts.scheme] });
    }
    await send("Page.navigate", { url: want.href });
    let ready = false;
    for (let i = 0; i < (CI ? 450 : 150) && !ready; i++) {
      await sleep(100);
      ready = (await evaluate("document.readyState")) === "complete";
    }
    if (!ready) { throw new Error("the page never finished loading"); }
    const tabShown = opts.tab ? `(function () {
        var b = document.getElementById("tab-" + ${JSON.stringify(opts.tab)});
        return !!b && b.getAttribute("aria-selected") === "true";
      })()` : "true";
    if (opts.tab) {
      // the tab comes from the frozen TABS list; AshLight's own tab code shows it
      await evaluate(`window.ALTabs && window.ALTabs.show(document, ${JSON.stringify(opts.tab)}, false)`);
      if ((await evaluate(tabShown)) !== true) {
        throw new Error(`the ${opts.tab} tab could not be shown`);
      }
    }
    await sleep(opts.waitMs);
    // the page is still AshLight's own page (the demo core page, or the
    // overlay file page) and the demo core still holds
    const where = await evaluate(
      "({o: location.origin, h: location.href, t: document.contentType})");
    const home = !!where && (want.overlay ? isOverlayUrl(where.h) : where.o === target.origin);
    if (!home || where.t !== "text/html") {
      refuse("the browser left AshLight's page; nothing captured");
    }
    if ((await evaluate(tabShown)) !== true) {
      throw new Error(`the ${opts.tab} tab is no longer shown`);
    }
    await checkDemoCore(target);
    // the one capture call of the repo: AshLight's own page, demo core, headless
    const shot = await send("Page.captureScreenshot", { format: "png", fromSurface: true });
    const data = shot.result && shot.result.data;
    if (typeof data !== "string" || !data) { throw new Error("the browser returned no image"); }
    const png = Buffer.from(data, "base64");
    if (png.length < 24 || png.toString("latin1", 1, 4) !== "PNG") { throw new Error("not a PNG"); }
    fs.writeFileSync(opts.outAbs, png);
    return { ok: true, out: opts.outAbs, bytes: png.length,
      width: png.readUInt32BE(16), height: png.readUInt32BE(20) };
  } finally {
    try { if (ws) { ws.close(); } } catch { /* closing */ }
    child.kill();
  }
}

export async function main(argv) {
  const say = (o) => process.stdout.write(JSON.stringify(o) + "\n");
  let opts;
  let target;
  let page;
  try {
    opts = parseArgs(argv);
    ({ target, page } = checkTarget(opts, readPorts()));
    opts.outAbs = checkOut(opts.out);
    opts.profile = checkProfile(opts.profile);
    let st;
    try { st = fs.statSync(opts.browser); } catch { st = null; }
    if (!st || !st.isFile()) { refuse("the browser executable was not found"); }
    await checkDemoCore(target);
  } catch (e) {
    if (e instanceof Refused) { say({ refused: e.message }); return 2; }
    throw e;
  }
  if (opts.plan) {
    say({ plan: { browser: opts.browser,
      args: [...BROWSER_FLAGS, `--user-data-dir=${opts.profile}`, "about:blank"],
      url: page.overlay ? page.href : target.origin, core: target.origin,
      tab: opts.tab, out: opts.outAbs } });
    return 0;
  }
  const watchdog = setTimeout(() => {
    say({ error: "watchdog" });
    if (browserChild) { browserChild.kill(); }
    process.exit(4);
  },
    CI ? 180000 : 60000);
  try {
    opts.page = page;
    say(await capture(opts, target));
    return 0;
  } catch (e) {
    if (e instanceof Refused) { say({ refused: e.message }); return 2; }
    say({ error: String(e && e.message || e) });
    return 3;
  } finally {
    clearTimeout(watchdog);
  }
}

const self = path.resolve(fileURLToPath(import.meta.url));
const run = process.argv[1] ? path.resolve(process.argv[1]) : "";
if (self.toLowerCase() === run.toLowerCase()) {
  process.exitCode = await main(process.argv.slice(2));
}
