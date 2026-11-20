"use strict";
/* TC-SNAP-UI: the overlay About text (decision 0009). The non-affiliation
   line is always first; the game-data credit follows it only while the core
   reports snapshot data (GET /api/version "data_credit", null without the
   cache). Read once at start and once per core restart, never polled.
   RUN-BUILD-STAMP-UI (F-027, decision 0082 part 2): the version line from
   the core's build string follows the disclaimer, in the About text and
   the tray tooltip: "Version 0.1.0, build 0123456789ab" (build_id split at
   "+"), ", dev" while hot reload is on. web/app.js versionText says the
   same words for the dashboard footer and the Settings About fold. */
const START_WAIT_MS = 1500;

const MAX_CREDIT_CHARS = 1000;

/* The credit line from a /api/version document, or "" (no line). */
function creditOf(doc) {
  const c = doc && doc.data_credit;
  if (!c || typeof c.credit !== "string") { return ""; }
  return c.credit.slice(0, MAX_CREDIT_CHARS);
}

const VERSION_RE = /^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$/;
const COMMIT_RE = /^[0-9a-f]{12}$/;
const MAX_BUILD_CHARS = 100;

/* The version line from a /api/version (or /api/health) document, or ""
   when it carries no well-formed version. The build string is
   '<x.y.z>[+<12 hex>][.dev]' (server/al/buildinfo.py compose); "version"
   is the fallback for a core without "build". */
function versionLine(doc) {
  const raw = doc && (typeof doc.build === "string" ? doc.build : doc.version);
  if (typeof raw !== "string" || raw.length > MAX_BUILD_CHARS) { return ""; }
  const plus = raw.indexOf("+");
  const ver = plus < 0 ? raw : raw.slice(0, plus);
  if (!VERSION_RE.test(ver)) { return ""; }
  let commit = "";
  let dev = false;
  for (const m of (plus < 0 ? [] : raw.slice(plus + 1).split("."))) {
    if (m === "dev" && !dev) { dev = true; continue; }
    if (COMMIT_RE.test(m) && !commit && !dev) { commit = m; continue; }
    return "";
  }
  return "Version " + ver + (commit ? ", build " + commit : "") + (dev ? ", dev" : "");
}

/* The About panel credits: the disclaimer, the version line when known,
   then the credit when there is one. */
function aboutText(disclaimer, credit, version) {
  const head = version ? disclaimer + "\n" + version : disclaimer;
  return credit ? head + "\n\n" + credit : head;
}

/* GET /api/version with the per-start token; resolves the parsed JSON. */
function makeGetVersion(http, port, getToken) {
  return function getVersion() {
    return new Promise((resolve, reject) => {
      const req = http.request({
        host: "127.0.0.1", port: port, path: "/api/version", method: "GET", timeout: 5000,
        headers: { "X-AL-Token": getToken() }
      }, (res) => {
        const chunks = [];
        res.on("data", (c) => chunks.push(c));
        res.on("end", () => {
          if (res.statusCode !== 200) { reject(new Error("HTTP " + res.statusCode)); return; }
          try { resolve(JSON.parse(Buffer.concat(chunks).toString("utf8"))); } catch (e) { reject(e); }
        });
      });
      req.on("timeout", () => req.destroy(new Error("timeout")));
      req.on("error", reject);
      req.end();
    });
  };
}

/* The credit at overlay start, read BEFORE the page loads so the page never
   reloads just to show it (design review TC-SNAP-UI-2). Resolves "" on any
   error or after ms, so a slow or absent core never holds the window back. */
function firstDoc(getVersion, ms) {
  return new Promise((resolve) => {
    const t = setTimeout(() => resolve(null), ms);
    getVersion().then((doc) => { clearTimeout(t); resolve(doc || null); },
                      () => { clearTimeout(t); resolve(null); });
  });
}

/* The credit alone at start (firstDoc, then creditOf). */
function firstCredit(getVersion, ms) {
  return firstDoc(getVersion, ms).then(creditOf);
}

module.exports = { creditOf, versionLine, aboutText, makeGetVersion, firstDoc, firstCredit,
                   MAX_CREDIT_CHARS, START_WAIT_MS };
