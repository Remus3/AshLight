"use strict";
/* OVL-MAIN-PARTS (decision 0053) and HOTKEYS-LIVE (decision 0058): the
   two global shortcuts, item check and show / hide, and nothing more
   (never more than two registered keys).

   - ready: register the keys app/main.js picked and validated (Hotkey.pick:
     env, then config, then the default; ctx.keys).
   - configChanged: re-pick the same way and swap only a key that changed
     (unregister its old accelerator only, never unregisterAll); no restart.
   - a taken key falls back to the first free key of Hotkey.FALLBACKS
     (Ctrl or Alt held, never a game key); a key bound nowhere keeps the
     old log sentence ("... shortcut not available: <key>"), which
     server/al/diag.py reads.
   - ready, configChanged and toggled write ops/runtime/hotkeys.json
     atomically (tmp + rename, ASCII, LF): what is really bound and whether
     the player switched the overlay off.

   The item check handler is ctx.actions.onEval, built in main.js around
   the one clipboard read per manual press; this part never reads the
   clipboard. ToS floor: a global shortcut only listens for the player's
   own press; nothing is sent to the game. */

const fs = require("fs");
const path = require("path");
const Hotkey = require("../hotkey.js");

const FILE_NAME = "hotkeys.json";
const LABELS = { toggle: "toggle", eval: "item check" };
const NAMES = ["eval", "toggle"];
const ENV = { toggle: "AL_OVERLAY_TOGGLE", eval: "AL_EVAL_HOTKEY" };
const CONFIG = { toggle: "overlay_toggle", eval: "eval_hotkey" };

/* A small pure registry over gs (Electron's globalShortcut or a test fake)
   holding at most the two named shortcuts. */
function createRegistry(gs, log) {
  const say = typeof log === "function" ? log : () => {};
  const slots = {};

  function otherBound(name) {
    return NAMES.filter((n) => n !== name && slots[n] && slots[n].bound)
      .map((n) => slots[n].bound);
  }

  function view(s) {
    return { want: s.want, bound: s.bound, registered: s.registered, fallback: s.fallback };
  }

  /* Bind name to want, else to its first free fallback. A held key with
     the same want stays as it is; a changed want frees only the old key. */
  function register(name, want, handler) {
    if (!LABELS[name]) { throw new Error("unknown shortcut " + String(name)); }
    const old = slots[name];
    if (old && old.registered && old.want === want && old.handler === handler) {
      return view(old);
    }
    if (old && old.bound) {
      try { gs.unregister(old.bound); } catch (e) { /* already gone */ }
    }
    const avoid = otherBound(name);
    const tries = (want && !avoid.includes(want) ? [want] : [])
      .concat(Hotkey.alternates(name, want, avoid));
    let bound = null;
    for (const k of tries) {
      let ok = false;
      try { ok = gs.register(k, handler) === true; } catch (e) { ok = false; }
      if (ok) { bound = k; break; }
    }
    const s = { want: want || null, bound: bound, registered: bound !== null,
      fallback: bound !== null && bound !== want, handler: handler };
    slots[name] = s;
    if (!s.registered) {
      say(LABELS[name] + " shortcut not available: " + want);
    } else if (s.fallback) {
      say(LABELS[name] + " shortcut " + want + " is taken; using " + bound);
    }
    return view(s);
  }

  /* The keys block of hotkeys.json. */
  function state() {
    const out = {};
    for (const n of NAMES) {
      out[n] = slots[n] ? view(slots[n])
        : { want: null, bound: null, registered: false, fallback: false };
    }
    return out;
  }

  function count() { return NAMES.filter((n) => slots[n] && slots[n].registered).length; }

  return { register: register, state: state, count: count };
}

/* Register both keys (toggle first, then item check) from ctx.keys. */
function registerKeys(gs, ctx, registry) {
  const reg = registry || createRegistry(gs, ctx.log);
  const keys = ctx.keys || {};
  const acts = ctx.actions || {};
  reg.register("toggle", keys.toggle, acts.toggle);
  reg.register("eval", keys.eval, acts.onEval);
  return reg;
}

/* The keys as main.js picks them, from a fresh config read. A refused
   value is logged once per value, not on every config save. */
function repick(ctx, seen) {
  let cfg = {};
  try { cfg = (ctx.readConfig && ctx.readConfig()) || {}; } catch (e) { cfg = {}; }
  const env = ctx.env || {};
  const defs = ctx.defaults || {};
  const log = (m) => {
    if (!seen.has(m)) { seen.add(m); if (typeof ctx.log === "function") { ctx.log(m); } }
  };
  const out = {};
  for (const n of NAMES) {
    out[n] = Hotkey.pick([env[ENV[n]], cfg[CONFIG[n]]], defs[n] || Hotkey.FALLBACKS[n][0], log);
  }
  return out;
}

/* The hotkeys.json document. */
function snapshot(registry, gate, now) {
  return {
    updated: (now || new Date()).toISOString(),
    keys: registry.state(),
    overlay: { user_on: gate ? gate.userWants() === true : true }
  };
}

/* Write doc to dir/hotkeys.json: tmp then rename, ASCII and LF only. */
function writeState(dir, doc, fsi) {
  const f = fsi || fs;
  const text = JSON.stringify(doc, null, 1)
    .replace(/[^\x00-\x7f]/g, (c) => "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0")) + "\n";
  const file = path.join(dir, FILE_NAME);
  const tmp = file + ".tmp";
  f.mkdirSync(dir, { recursive: true });
  f.writeFileSync(tmp, text, { encoding: "ascii" });
  f.renameSync(tmp, file);
  return file;
}

/* The part's hooks over an injected globalShortcut and writer. */
function createPart(getGs, write) {
  let registry = null;
  const seen = new Set();

  function save(ctx) {
    if (!registry || !ctx.runtimeDir) { return; }
    const gate = typeof ctx.getGate === "function" ? ctx.getGate() : null;
    try {
      (write || writeState)(ctx.runtimeDir, snapshot(registry, gate));
    } catch (e) {
      if (typeof ctx.log === "function") { ctx.log("hotkeys.json not written: " + e.message); }
    }
  }

  return {
    ready(ctx) {
      registry = registerKeys(getGs(), ctx);
      save(ctx);
    },
    configChanged(ctx) {
      if (!registry) { return; }
      const keys = repick(ctx, seen);
      const acts = ctx.actions || {};
      registry.register("toggle", keys.toggle, acts.toggle);
      registry.register("eval", keys.eval, acts.onEval);
      save(ctx);
    },
    toggled(ctx) { save(ctx); },
    registry: () => registry
  };
}

const PART = createPart(() => require("electron").globalShortcut);

module.exports = {
  ready: PART.ready, configChanged: PART.configChanged, toggled: PART.toggled,
  registerKeys, createRegistry, createPart, repick, snapshot, writeState, FILE_NAME
};
