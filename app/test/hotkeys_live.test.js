"use strict";
/* HOTKEYS-LIVE (decision 0058): the client re-registers on a config
   change, falls back from a taken key and writes ops/runtime/hotkeys.json. */
const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const os = require("os");
const path = require("path");
const Hotkey = require("../hotkey.js");
const Part = require("../parts/20-hotkeys.js");

/* A fake globalShortcut: taken keys belong to another program. */
function fakeGs(taken) {
  const held = new Map();
  const calls = [];
  return {
    held: held,
    calls: calls,
    register(k, fn) {
      calls.push(["register", k]);
      if ((taken || []).includes(k) || held.has(k)) { return false; }
      held.set(k, fn);
      return true;
    },
    unregister(k) { calls.push(["unregister", k]); held.delete(k); },
    unregisterAll() { throw new Error("never unregisterAll"); }
  };
}

function makeCtx(over) {
  const logged = [];
  let cfg = {};
  let user = true;
  const ctx = Object.assign({
    log: (m) => logged.push(m),
    runtimeDir: "rt",
    env: {},
    readConfig: () => cfg,
    defaults: { toggle: "Alt+Shift+A", eval: "Alt+Shift+E" },
    keys: { toggle: "Alt+Shift+A", eval: "Alt+Shift+E" },
    actions: { toggle: () => "t", onEval: () => "e" },
    getGate: () => ({ userWants: () => user })
  }, over || {});
  return { ctx: ctx, logged: logged, setCfg: (c) => { cfg = c; },
           setUser: (u) => { user = u; } };
}

function partWith(gs) {
  const written = [];
  const part = Part.createPart(() => gs, (dir, doc) => written.push([dir, doc]));
  return { part: part, written: written };
}

test("a config change swaps the registration with no restart", () => {
  const gs = fakeGs();
  const { part, written } = partWith(gs);
  const t = makeCtx();
  part.ready(t.ctx);
  assert.deepStrictEqual([...gs.held.keys()].sort(), ["Alt+Shift+A", "Alt+Shift+E"]);
  assert.strictEqual(gs.held.get("Alt+Shift+E"), t.ctx.actions.onEval);
  assert.strictEqual(written.length, 1);

  t.setCfg({ eval_hotkey: "ctrl+shift+k" });
  gs.calls.length = 0;
  part.configChanged(t.ctx);
  // only the changed key moved; the toggle key was not touched
  assert.deepStrictEqual(gs.calls, [["unregister", "Alt+Shift+E"], ["register", "Ctrl+Shift+K"]]);
  assert.deepStrictEqual([...gs.held.keys()].sort(), ["Alt+Shift+A", "Ctrl+Shift+K"]);
  assert.strictEqual(gs.held.get("Ctrl+Shift+K"), t.ctx.actions.onEval);
  const doc = written[written.length - 1][1];
  assert.deepStrictEqual(doc.keys.eval,
    { want: "Ctrl+Shift+K", bound: "Ctrl+Shift+K", registered: true, fallback: false });

  // an unchanged config re-registers nothing
  gs.calls.length = 0;
  part.configChanged(t.ctx);
  assert.deepStrictEqual(gs.calls, []);

  // the env wins over the config, as in main.js
  t.ctx.env = { AL_OVERLAY_TOGGLE: "Alt+Shift+F7" };
  gs.calls.length = 0;
  part.configChanged(t.ctx);
  assert.deepStrictEqual(gs.calls, [["unregister", "Alt+Shift+A"], ["register", "Alt+Shift+F7"]]);
});

test("a refused config key falls back to the default, logged once", () => {
  const gs = fakeGs();
  const { part } = partWith(gs);
  const t = makeCtx();
  part.ready(t.ctx);
  t.setCfg({ eval_hotkey: "Ctrl+C" });
  part.configChanged(t.ctx);
  part.configChanged(t.ctx);
  assert.ok(gs.held.has("Alt+Shift+E"));
  assert.strictEqual(t.logged.filter((m) => /refused/.test(m)).length, 1);
});

test("a taken key yields a reported alternate", () => {
  const gs = fakeGs(["Alt+Shift+E"]);
  const { part, written } = partWith(gs);
  const t = makeCtx();
  part.ready(t.ctx);
  const ev = written[0][1].keys.eval;
  assert.deepStrictEqual(ev, { want: "Alt+Shift+E", bound: "Ctrl+Shift+F9",
                               registered: true, fallback: true });
  assert.strictEqual(Hotkey.safeAccelerator(ev.bound), ev.bound);
  assert.ok(!Hotkey.GAME_KEYS.has(ev.bound));
  assert.deepStrictEqual(t.logged, ["item check shortcut Alt+Shift+E is taken; using Ctrl+Shift+F9"]);

  // every key taken: the old sentence, nothing bound
  const all = Hotkey.FALLBACKS.toggle.concat(Hotkey.FALLBACKS.eval);
  const gs2 = fakeGs(all);
  const p2 = partWith(gs2);
  const t2 = makeCtx();
  p2.part.ready(t2.ctx);
  assert.deepStrictEqual(t2.logged, ["toggle shortcut not available: Alt+Shift+A",
                                     "item check shortcut not available: Alt+Shift+E"]);
  assert.deepStrictEqual(p2.written[0][1].keys.toggle,
    { want: "Alt+Shift+A", bound: null, registered: false, fallback: false });
  assert.strictEqual(gs2.held.size, 0);
});

test("a key wanted by both never binds twice; the fallback avoids the other", () => {
  const gs = fakeGs();
  const reg = Part.createRegistry(gs, () => {});
  reg.register("toggle", "Ctrl+Shift+F9", () => {});
  const r = reg.register("eval", "Alt+Shift+E", () => {});
  assert.strictEqual(r.bound, "Alt+Shift+E");
  const gs2 = fakeGs(["Alt+Shift+E"]);
  const reg2 = Part.createRegistry(gs2, () => {});
  reg2.register("toggle", "Ctrl+Shift+F9", () => {});
  const r2 = reg2.register("eval", "Alt+Shift+E", () => {});
  assert.strictEqual(r2.bound, "Alt+Shift+F9");
  // the toggle's key was tried once (by the toggle), never by the eval fallback
  assert.strictEqual(gs2.calls.filter((c) => c[1] === "Ctrl+Shift+F9").length, 1);
});

test("never more than 2 registered keys", () => {
  const gs = fakeGs();
  const reg = Part.createRegistry(gs, () => {});
  reg.register("toggle", "Alt+Shift+A", () => {});
  reg.register("eval", "Alt+Shift+E", () => {});
  assert.throws(() => reg.register("third", "Alt+Shift+F8", () => {}), /unknown shortcut/);
  for (const k of ["Ctrl+Shift+K", "Ctrl+Shift+L", "Alt+Shift+F7"]) {
    reg.register("eval", k, () => {});
    reg.register("toggle", k.replace("Shift", "Alt"), () => {});
    assert.ok(gs.held.size <= 2, String(gs.held.size));
    assert.ok(reg.count() <= 2);
  }
  assert.deepStrictEqual(Object.keys(reg.state()).sort(), ["eval", "toggle"]);
});

test("toggled writes the player's overlay choice", () => {
  const gs = fakeGs();
  const { part, written } = partWith(gs);
  const t = makeCtx();
  part.toggled(t.ctx); // before ready: nothing to write
  assert.strictEqual(written.length, 0);
  part.ready(t.ctx);
  assert.strictEqual(written[0][1].overlay.user_on, true);
  t.setUser(false);
  part.toggled(t.ctx);
  assert.strictEqual(written[1][1].overlay.user_on, false);
  assert.strictEqual(written[1][0], "rt");
});

test("the file shape: atomic, ASCII, LF, the documented keys", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "al-hotkeys-"));
  try {
    const gs = fakeGs(["Alt+Shift+A"]);
    const t = makeCtx({ runtimeDir: path.join(dir, "runtime") });
    const part = Part.createPart(() => gs);
    part.ready(t.ctx);
    const file = path.join(dir, "runtime", Part.FILE_NAME);
    const raw = fs.readFileSync(file);
    assert.ok(raw.every((b) => b < 128), "ASCII");
    const text = raw.toString("ascii");
    assert.ok(!text.includes("\r"), "LF");
    assert.ok(text.endsWith("\n"));
    assert.ok(!fs.existsSync(file + ".tmp"), "tmp renamed");
    const doc = JSON.parse(text);
    assert.deepStrictEqual(Object.keys(doc).sort(), ["keys", "overlay", "updated"]);
    assert.ok(!Number.isNaN(Date.parse(doc.updated)));
    assert.match(doc.updated, /^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z$/);
    assert.deepStrictEqual(Object.keys(doc.keys).sort(), ["eval", "toggle"]);
    for (const n of ["eval", "toggle"]) {
      assert.deepStrictEqual(Object.keys(doc.keys[n]).sort(),
        ["bound", "fallback", "registered", "want"]);
    }
    assert.deepStrictEqual(doc.keys.toggle,
      { want: "Alt+Shift+A", bound: "Ctrl+Shift+F10", registered: true, fallback: true });
    assert.deepStrictEqual(doc.overlay, { user_on: true });
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("the part never reads the clipboard and never calls unregisterAll", () => {
  const src = fs.readFileSync(path.join(__dirname, "..", "parts", "20-hotkeys.js"), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "");
  assert.ok(!/clipboard/.test(src));
  assert.ok(!/unregisterAll/.test(src));
  assert.ok(/ctx\.actions|acts\.onEval/.test(src));
});
