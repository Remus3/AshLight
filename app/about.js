"use strict";
/* TC-SNAP-UI: the overlay About text (decision 0009). The non-affiliation
   line is always first; the game-data credit follows it only while the core
   reports snapshot data (GET /api/version "data_credit", null without the
   cache). Read once at start and once per core restart, never polled. */
const START_WAIT_MS = 1500;

const MAX_CREDIT_CHARS = 1000;

/* The credit line from a /api/version document, or "" (no line). */
function creditOf(doc) {
  const c = doc && doc.data_credit;
  if (!c || typeof c.credit !== "string") { return ""; }
  return c.credit.slice(0, MAX_CREDIT_CHARS);
}

/* The About panel credits: the disclaimer, then the credit when there is one. */
function aboutText(disclaimer, credit) {
  return credit ? disclaimer + "\n\n" + credit : disclaimer;
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
function firstCredit(getVersion, ms) {
  return new Promise((resolve) => {
    const t = setTimeout(() => resolve(""), ms);
    getVersion().then((doc) => { clearTimeout(t); resolve(creditOf(doc)); },
                      () => { clearTimeout(t); resolve(""); });
  });
}

module.exports = { creditOf, aboutText, makeGetVersion, firstCredit, MAX_CREDIT_CHARS,
                   START_WAIT_MS };
