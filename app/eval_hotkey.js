"use strict";
/* TC-EVAL-UI: the item check hotkey (main process only).

   Decision 0003 / CLAUDE.md ToS floor: the clipboard is read ONCE per
   manual press of this AshLight hotkey - never by a watcher, a timer or at
   start - and AshLight never sends Ctrl+C or any other input to the game.
   The player copies the item in game themselves, then presses the hotkey.
   The text goes to the local core's POST /api/eval; the verdict comes back
   through the state feed (dashboard and overlay card). Pure apart from the
   injected readText / post, so node --test covers it without Electron.
   TC-PRESS-BUILD (ruling Q-02): the same single read may hold a build the
   player copied in Path of Building (code, character JSON or share link);
   the core loads it and shows "Build loaded". No second read, no retry. */

// TC-PRESS-BUILD: the build size (a PoB code is about 5-60 KB); an item
// text is far smaller. A JSON over this still goes through the paste box.
const MAX_ITEM_CHARS = 256 * 1024;
// the core's POST /api/eval body cap (server/al/http.py MAX_EVAL_BODY)
const MAX_BODY_BYTES = 256 * 1024;
// AUDIT-HOTKEY-REPEAT (audit 2026-11-17): a held global shortcut re-fires
// with Windows keyboard auto-repeat (first repeat after 250-1000 ms, then
// about every 30 ms). Every event within this gap of the PREVIOUS event
// (sliding, ignored ones included) is the same manual press, so a held key
// reads the clipboard exactly once. Longer than the 1000 ms maximum delay.
const REPEAT_GAP_MS = 1200;

/* deps: { readText(): string, post(path, body): Promise, log(msg),
   now(): ms (optional, default Date.now) }.
   Returns the press handler. Creating it reads nothing. */
function createEvalHotkey(deps) {
  let busy = false;
  let lastEvent = null;
  const now = typeof deps.now === "function" ? deps.now : Date.now;
  return function onPress() {
    const t = now();
    const repeat = lastEvent !== null && t - lastEvent < REPEAT_GAP_MS;
    lastEvent = t;
    if (repeat) { return Promise.resolve(false); } // auto-repeat of a held key
    if (busy) { return Promise.resolve(false); } // one request in flight
    busy = true;
    let text = "";
    try {
      text = String(deps.readText() || "");
    } catch (e) {
      text = "";
    }
    text = fitText(text);
    return Promise.resolve()
      .then(() => deps.post("/api/eval", { item: text }))
      .then(() => true, (e) => {
        deps.log("item check not sent: " + (e && e.message ? e.message : e));
        return false;
      })
      .then((ok) => { busy = false; return ok; });
  };
}

/* The text clipped to MAX_ITEM_CHARS, then until its JSON body fits the
   core's byte cap (escapes and non-ASCII take more bytes than characters),
   so an over-long clipboard still gets a card instead of an HTTP 413. Each
   pass cuts at least the overflow, so it ends. */
function fitText(text) {
  let out = text.length > MAX_ITEM_CHARS ? text.slice(0, MAX_ITEM_CHARS) : text;
  let over = Buffer.byteLength(JSON.stringify({ item: out }), "utf8") - MAX_BODY_BYTES;
  while (over > 0 && out.length > 0) {
    out = out.slice(0, Math.max(0, out.length - over));
    over = Buffer.byteLength(JSON.stringify({ item: out }), "utf8") - MAX_BODY_BYTES;
  }
  return out;
}

/* A JSON POST to the local core with the per-start token (Node http). */
function makePost(http, port, getToken) {
  return function post(path, body) {
    return new Promise((resolve, reject) => {
      const data = Buffer.from(JSON.stringify(body), "utf8");
      const req = http.request({
        host: "127.0.0.1", port: port, path: path, method: "POST", timeout: 5000,
        headers: { "Content-Type": "application/json", "Content-Length": data.length,
                   "X-AL-Token": getToken() }
      }, (res) => {
        res.resume();
        res.on("end", () => (res.statusCode === 200 ? resolve(res.statusCode)
          : reject(new Error("HTTP " + res.statusCode))));
      });
      req.on("timeout", () => req.destroy(new Error("timeout")));
      req.on("error", reject);
      req.end(data);
    });
  };
}

module.exports = { createEvalHotkey, makePost, fitText, MAX_ITEM_CHARS, MAX_BODY_BYTES,
                   REPEAT_GAP_MS };
