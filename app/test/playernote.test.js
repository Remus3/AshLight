/* PLAY-F-186B-PLAYER-NOTES-UI (finding F-186, decision 0074): the zone note
   box on the Run tab's zone guide page (web/playernote.js) and the export
   option of the settings backup (web/settingsio.js). Save posts the box's
   text as text/plain for the shown zone; the box is capped at 200
   characters; the backup holds notes only while the option is ticked. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const P = web.load("playernote.js");
const S = web.load("settingsio.js");
const SRC = web.source("playernote.js");
const CODE = SRC.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
const HTML = web.source("index.html");
const fs = require("node:fs");
const path = require("node:path");
const REPO = path.resolve(__dirname, "..", "..");
const SHEET = fs.readFileSync(path.join(REPO, "docs", "design", "copy", "playernotes.md"), "utf8")
  .split(/\s+/).join(" ");
const STORE = fs.readFileSync(path.join(REPO, "server", "al", "playernotes.py"), "utf8");

function el(id) {
  return {
    id, hidden: false, disabled: false, value: "", checked: false, textContent: "",
    attrs: {}, listeners: {}, focus() {},
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
    removeAttribute(k) { delete this.attrs[k]; },
    addEventListener(t, f) { this.listeners[t] = f; }
  };
}

function fakeDoc() {
  const nodes = {};
  ["pn", "pn-text", "pn-save", "pn-said"].forEach((id) => { nodes[id] = el(id); });
  nodes.pn.hidden = true;
  return { nodes, getElementById: (id) => nodes[id] || null };
}

function snapOf(area, character, note) {
  return { area_id: area, character: character,
    player_note: note ? { area_id: area, text: note, at: 1 } : null };
}

function fakeFetch(status, body) {
  const calls = [];
  const fn = (url, opts) => {
    calls.push({ url, opts });
    return Promise.resolve({ status, ok: status === 200,
      json: () => (body === undefined ? Promise.reject(new Error("no body")) : Promise.resolve(body)) });
  };
  fn.calls = calls;
  return fn;
}

function setup(snap, fetch) {
  const doc = fakeDoc();
  let cur = snap;
  P.wire(doc, { fetch, token: "t0k", getSnap: () => cur });
  return { doc, n: doc.nodes, setSnap(s) { cur = s; P.paint(doc, s); } };
}

test("the box shows the note of the zone and character being played", () => {
  const { n, setSnap } = setup(snapOf("G1_2", "Ash", "exit north"), fakeFetch(200, {}));
  assert.equal(n.pn.hidden, false);
  assert.equal(n["pn-text"].value, "exit north");
  setSnap(snapOf("G1_3", "Ash", null));
  assert.equal(n["pn-text"].value, "");
  setSnap({ area_id: "", character: "Ash", player_note: null });
  assert.equal(n.pn.hidden, true);
  setSnap({ area_id: "G1_3", character: "", player_note: null });
  assert.equal(n.pn.hidden, true);
  // a note for another zone is never shown for this one
  assert.equal(P.model({ area_id: "G1_3", character: "Ash",
    player_note: { area_id: "G1_2", text: "x" } }).text, "");
});

test("Save posts the box as text/plain for the shown zone and character", async () => {
  const fetch = fakeFetch(200, { note: { area_id: "G1_2", text: "take the left path", at: 2 } });
  const { n, setSnap } = setup(snapOf("G1_2", "Ash", null), fetch);
  n["pn-text"].value = "take   the left path";
  // the player moves on while typing: the box keeps the zone it showed
  setSnap(snapOf("G1_3", "Ash", null));
  assert.equal(n["pn-text"].value, "take   the left path");
  await P.save();
  assert.equal(fetch.calls.length, 1);
  const c = fetch.calls[0];
  assert.equal(c.url, "/api/player-note?area=G1_2");
  assert.equal(c.opts.method, "POST");
  assert.equal(c.opts.headers["X-AL-Token"], "t0k");
  assert.equal(c.opts.headers["Content-Type"], "text/plain; charset=utf-8");
  assert.equal(c.opts.body, "take   the left path");
  assert.equal(n["pn-said"].textContent, P.SAVED);
  // PN-A: the focused Save button carries the answer too (no live region)
  assert.equal(n["pn-save"].getAttribute("aria-description"), P.SAVED);
  assert.equal(n["pn-save"].getAttribute("title"), P.SAVED);
  assert.equal(n["pn-text"].value, "take the left path");  // the stored form
  assert.equal(n["pn-save"].disabled, false);
  // the next push moves the box to the zone being played
  setSnap(snapOf("G1_3", "Ash", null));
  assert.equal(n["pn-text"].value, "");
});

test("an empty Save removes the note; a refusal shows the core's sentence", async () => {
  let fetch = fakeFetch(200, { note: null });
  let s = setup(snapOf("G1_2", "Ash", "old"), fetch);
  s.n["pn-text"].value = "";
  await P.save();
  assert.equal(fetch.calls[0].opts.body, "");
  assert.equal(s.n["pn-said"].textContent, P.REMOVED);
  fetch = fakeFetch(400, { error: "Your note is over 200 characters. Shorten it and save again." });
  s = setup(snapOf("G1_2", "Ash", null), fetch);
  s.n["pn-text"].value = "x";
  await P.save();
  assert.equal(s.n["pn-said"].textContent,
    "Your note is over 200 characters. Shorten it and save again.");
  assert.equal(s.n["pn-text"].value, "x");  // a refused note stays in the box
  fetch = fakeFetch(500, undefined);
  s = setup(snapOf("G1_2", "Ash", null), fetch);
  s.n["pn-text"].value = "x";
  await P.save();
  assert.equal(s.n["pn-said"].textContent, P.FAILED);
  s = setup(snapOf("G1_2", "Ash", null), () => Promise.reject(new Error("down")));
  s.n["pn-text"].value = "x";
  await P.save();
  assert.equal(s.n["pn-said"].textContent, P.OFFLINE);
});

test("a Save after a character switch is refused and the box refilled", async () => {
  const fetch = fakeFetch(200, { note: null });
  const s = setup(snapOf("G1_2", "Ash", null), fetch);
  s.n["pn-text"].value = "typed for Ash";
  s.setSnap(snapOf("G1_2", "Bel", "Bel's note"));
  assert.equal(s.n["pn-text"].value, "typed for Ash");  // never replaced while typing
  await P.save();
  assert.equal(fetch.calls.length, 0);
  assert.equal(s.n["pn-said"].textContent, P.CHAR_CHANGED);
  assert.equal(s.n["pn-text"].value, "Bel's note");
});

test("the box is capped at 200 characters and Save sends at most 200", async () => {
  assert.equal(P.MAX, 200);
  const box = /<textarea id="pn-text"[^>]*>/.exec(HTML);
  assert.ok(box, "the note box");
  assert.match(box[0], /maxlength="200"/);
  assert.match(box[0], /aria-describedby="pn-help pn-said"/);
  assert.match(HTML, /<label id="pn-label" for="pn-text">Your note for this zone<\/label>/);
  assert.match(HTML, /<button id="pn-save" type="button"[^>]*>Save note<\/button>/);
  const fetch = fakeFetch(400, { error: "x" });
  const s = setup(snapOf("G1_2", "Ash", null), fetch);
  s.n["pn-text"].value = "y".repeat(250);
  await P.save();
  assert.equal(fetch.calls[0].opts.body.length, 200);
});

test("the box sits on the zone guide page of the Acts card, never on Play", () => {
  const guide = HTML.indexOf('data-page="guide"');
  const box = HTML.indexOf('id="pn-text"');
  const acts = HTML.indexOf('id="actsbox"');
  const after = HTML.indexOf("</section>", acts);
  assert.ok(acts >= 0 && guide > acts && box > guide && box < after);
  const play = HTML.indexOf('id="play"');
  if (play >= 0) {
    assert.ok(!HTML.slice(play, HTML.indexOf("</section>", play)).includes("pn-text"));
  }
  assert.match(HTML, /<script src="\/web\/playernote\.js" defer><\/script>/);
  assert.equal(P.NAME, "playernote");
});

test("playernote.js sets no timer, no clipboard, no live region, no markup", () => {
  for (const bad of ["setInterval", "setTimeout", "requestAnimationFrame", "clipboard",
    "innerHTML", "outerHTML", "insertAdjacentHTML", "aria-live", "notify("]) {
    assert.ok(!CODE.includes(bad), bad);
  }
  assert.doesNotMatch(SRC, /[^\x0a\x20-\x7e]/, "ASCII and LF");
});

test("the panel entry wires the page with the host's token and snapshot", async () => {
  const doc = fakeDoc();
  const fetchCalls = [];
  const page = {
    document: doc,
    ALApp: { host: { token: "h0st", getSnap: () => snapOf("G2_1", "Ash", "hi") } },
    fetch: (url, opts) => { fetchCalls.push({ url, opts }); return Promise.reject(new Error("x")); }
  };
  const entry = P.panel(page);
  assert.equal(entry.name, "playernote");
  assert.equal(typeof entry.order, "number");
  entry.wire();
  assert.equal(doc.nodes["pn-text"].value, "hi");
  entry.paint(snapOf("G2_1", "Ash", "hi again"));
  assert.equal(doc.nodes["pn-text"].value, "hi again");
});

/* -- the settings backup option (web/settingsio.js) ------------------------- */

function blobOf(text) { return { text: () => Promise.resolve(text) }; }

function exportEnv(ticked, text) {
  const calls = [];
  const out = { said: [], saved: [] };
  out.env = {
    token: "t0k",
    notes: () => ticked,
    fetch: (url, opts) => {
      calls.push({ url, opts });
      return Promise.resolve({ ok: true, status: 200, blob: () => Promise.resolve(blobOf(text)) });
    },
    save: (blob, name) => out.saved.push(name),
    tell: (t) => out.said.push(t)
  };
  out.calls = calls;
  return out;
}

test("the export holds notes only while the option is ticked", async () => {
  assert.equal(S.exportUrl(false), "/api/settings-export");
  assert.equal(S.exportUrl(true), "/api/settings-export?notes=1");
  assert.equal(S.exportUrl("1"), "/api/settings-export");
  let x = exportEnv(false, "{}");
  await S.runExport(x.env);
  assert.equal(x.calls[0].url, "/api/settings-export");
  assert.equal(x.said[x.said.length - 1], S.SAVED);
  x = exportEnv(true, JSON.stringify({ notes: [] }));
  await S.runExport(x.env);
  assert.equal(x.calls[0].url, "/api/settings-export?notes=1");
  assert.equal(x.said[x.said.length - 1], S.SAVED_NOTES);
  x = exportEnv(true, JSON.stringify({ notes: [], notes_left_out: 3 }));
  await S.runExport(x.env);
  assert.equal(x.said[x.said.length - 1], S.SAVED_NOTES +
    " 3 older notes didn't fit in the backup and stayed only on this computer.");
  // an env without the option (older callers) never asks for notes
  x = exportEnv(true, "{}");
  delete x.env.notes;
  await S.runExport(x.env);
  assert.equal(x.calls[0].url, "/api/settings-export");
});

test("the option box is in Appearance and tools, off by default, and labelled", () => {
  const box = /<input id="settings-notes"[^>]*>/.exec(HTML);
  assert.ok(box, "the option box");
  assert.match(box[0], /type="checkbox"/);
  assert.doesNotMatch(box[0], /checked/);
  assert.match(HTML, /<label class="check" for="settings-notes">/);
  const tools = HTML.indexOf('id="toolsbox"');
  const at = HTML.indexOf('id="settings-notes"');
  assert.ok(tools >= 0 && at > HTML.indexOf('id="settingsbox"') && at > tools);
});

test("the wire reads the option box at each export", async () => {
  const nodes = { "settings-export": el("settings-export"),
    "settings-import-file": el("settings-import-file"), "settings-said": el("settings-said"),
    "settings-notes": el("settings-notes") };
  const doc = { activeElement: null, getElementById: (id) => nodes[id] || null };
  const urls = [];
  S.wire(doc, { token: "t", save: () => {},
    fetch: (url) => { urls.push(url); return Promise.resolve({ ok: false, status: 500 }); } });
  await nodes["settings-export"].listeners.click();
  nodes["settings-notes"].checked = true;
  await nodes["settings-export"].listeners.click();
  assert.deepEqual(urls, ["/api/settings-export", "/api/settings-export?notes=1"]);
});

test("an import names the notes it added and the ones it kept", () => {
  const base = { applied: [], ignored: [], weights_applied: false };
  assert.equal(S.importedText(base), "No settings in that file were changed.");
  assert.equal(S.importedText(Object.assign({ notes_added: 2, notes_kept: 0, notes_full: 0 }, base)),
    "No settings in that file were changed. Added 2 zone notes.");
  assert.equal(S.importedText(Object.assign({ notes_added: 1, notes_kept: 1, notes_full: 0 }, base)),
    "No settings in that file were changed. Added 1 zone note. Kept 1 note you already " +
    "had here for the same zone; the backup's version wasn't used.");
  assert.equal(S.importedText(Object.assign({ notes_added: 0, notes_kept: 0, notes_full: 2 }, base)),
    "No settings in that file were changed. Left out 2 notes: AshLight keeps notes for at most " +
    "300 zones and 12 characters of yours.");
  assert.equal(S.importedText(Object.assign({ notes_added: 0, notes_kept: 0, notes_full: 0 }, base)),
    "No settings in that file were changed. Your zone notes were already here.");
  assert.equal(S.notesText(Object.assign({ notes_added: 1, notes_failed: true }, base)),
    " Added 1 zone note. Some notes weren't saved. Import the backup again.");
});

test("the notes bound sentence quotes the store's own bounds", () => {
  const zones = Number(/^MAX_ZONES = (\d+)/m.exec(STORE)[1]);
  const chars = Number(/^MAX_CHARACTERS = (\d+)/m.exec(STORE)[1]);
  assert.equal(S.MAX_ZONES, zones);
  assert.equal(S.MAX_CHARACTERS, chars);
  assert.equal(S.notesText({ notes_added: 0, notes_kept: 0, notes_full: 1 }),
    " Left out 1 note: AshLight keeps notes for at most " + zones + " zones and " +
    chars + " characters of yours.");
});

test("the copy sheet holds every dashboard string of the notes", () => {
  const help = /<p id="pn-help"[^>]*>([\s\S]*?)<\/p>/.exec(HTML)[1].split(/\s+/).join(" ").trim();
  const optHelp = /<p id="settings-notes-help"[^>]*>([\s\S]*?)<\/p>/.exec(HTML)[1]
    .split(/\s+/).join(" ").trim();
  const strings = [P.SAVED, P.REMOVED, P.NO_ZONE, P.CHAR_CHANGED, P.FAILED, S.SAVED_NOTES,
    help, optHelp,
    S.leftOutText(2).trim().replace(/^2 /, "<n> "),
    S.notesText({ notes_added: 2 }).trim().replace(/ 2 /, " <n> "),
    S.notesText({ notes_added: 0, notes_kept: 2 }).trim().replace(/ 2 /, " <n> "),
    S.notesText({ notes_added: 0, notes_full: 2 }).trim().replace(/ 2 /, " <n> "),
    "Some notes weren't saved. Import the backup again.",
    S.notesText({ notes_added: 0 }).trim()];
  strings.forEach((t) => assert.ok(SHEET.includes(t), t));
});
