"use strict";
/* AREA-AUDIT P5-3: the AshLight hotkey rule (main process only). Mirror of
   server/al/hotkeys.py; both read the case table in test/hotkey_cases.json.

   Electron's globalShortcut takes its key from EVERY program, the game
   included. So an AshLight hotkey always holds Ctrl or Alt (Shift alone
   only with an F key: Shift + a letter types in the game's chat), and
   never a combination the game or Windows uses (item copy Ctrl+C /
   Ctrl+Alt+C, paste, stash search, chat send, Alt+F4, Alt+Tab,
   Alt+Shift+Tab, Ctrl+Alt+Tab, Task Manager Ctrl+Shift+Esc, Ctrl+Alt+Delete
   ...). The Win key is never a modifier: Windows owns it.
   Pure: node --test covers it without Electron. */

const MAX_CHARS = 40;
const MODS = { ctrl: "Ctrl", control: "Ctrl", commandorcontrol: "Ctrl", cmdorctrl: "Ctrl",
  alt: "Alt", shift: "Shift" };
const ORDER = ["Ctrl", "Alt", "Shift"];
const NAMED = ["Space", "Tab", "Enter", "Backspace", "Delete", "Insert", "Home", "End",
  "PageUp", "PageDown", "Up", "Down", "Left", "Right", "Escape"];
const ALIAS = { return: "Enter", esc: "Escape" };
const GAME_KEYS = new Set(["Ctrl+C", "Ctrl+Alt+C", "Ctrl+V", "Ctrl+X", "Ctrl+A", "Ctrl+Z",
  "Ctrl+F", "Ctrl+Enter", "Ctrl+Escape", "Ctrl+Shift+Escape", "Ctrl+Alt+Delete",
  "Alt+F4", "Alt+Tab", "Alt+Enter", "Alt+Escape", "Alt+Space",
  "Alt+Shift+Tab", "Ctrl+Alt+Tab", "Alt+Shift+Escape", "Ctrl+Alt+End"]);

function keyName(token) {
  const low = token.toLowerCase();
  if (/^[a-z0-9]$/.test(low)) { return low.toUpperCase(); }
  const f = /^f([1-9]|1[0-9]|2[0-4])$/.exec(low);
  if (f) { return "F" + f[1]; }
  if (ALIAS[low]) { return ALIAS[low]; }
  for (const n of NAMED) { if (n.toLowerCase() === low) { return n; } }
  return null;
}

/* The canonical accelerator ("Ctrl+Alt+K"), or null when it is not a safe
   AshLight hotkey. */
function safeAccelerator(value) {
  if (typeof value !== "string" || value.length > MAX_CHARS || /[^A-Za-z0-9+ ]/.test(value)) {
    return null;
  }
  const tokens = value.split("+").map((t) => t.trim());
  if (tokens.length < 2 || tokens.some((t) => !t)) { return null; }
  const key = keyName(tokens[tokens.length - 1]);
  if (!key) { return null; }
  const mods = new Set();
  for (const t of tokens.slice(0, -1)) {
    const m = MODS[t.toLowerCase()];
    if (!m || mods.has(m)) { return null; }
    mods.add(m);
  }
  if (!mods.has("Ctrl") && !mods.has("Alt") && !/^F\d+$/.test(key)) { return null; }
  const out = ORDER.filter((m) => mods.has(m)).concat([key]).join("+");
  return GAME_KEYS.has(out) ? null : out;
}

/* The first safe candidate (env, then config), else the built-in default.
   A refused non-empty candidate is logged. */
function pick(candidates, fallback, log) {
  for (const c of candidates) {
    if (c === undefined || c === null || c === "") { continue; }
    const ok = safeAccelerator(c);
    if (ok) { return ok; }
    if (typeof log === "function") {
      log("hotkey " + JSON.stringify(String(c).slice(0, MAX_CHARS)) +
        " refused: it needs Ctrl or Alt and a key the game doesn't use");
    }
  }
  return fallback;
}

/* HOTKEYS-LIVE (decision 0058): the short safe lists a taken key falls
   back to, in order. Each is canonical, passes safeAccelerator and is not
   a game key; the lists share no key. The first entry is the built-in
   default. Ctrl+Alt+letter is left out: on many keyboard layouts that is
   AltGr and types a character. Mirrored in test/hotkey_cases.json
   ("fallbacks"), and in server/al/hotkeys.py from OVL-KEYS-CORE. */
const FALLBACKS = Object.freeze({
  eval: Object.freeze(["Alt+Shift+E", "Ctrl+Shift+F9", "Alt+Shift+F9", "Ctrl+Alt+F9"]),
  toggle: Object.freeze(["Alt+Shift+A", "Ctrl+Shift+F10", "Alt+Shift+F10", "Ctrl+Alt+F10"])
});

/* The fallback keys for name ("eval" or "toggle") to try after want, in
   order: want itself and any key in avoid (held by the other shortcut)
   left out. An unknown name has none. */
function alternates(name, want, avoid) {
  const list = Object.prototype.hasOwnProperty.call(FALLBACKS, name) ? FALLBACKS[name] : [];
  const skip = new Set([safeAccelerator(want)].concat(avoid || []));
  return list.filter((k) => !skip.has(k));
}

module.exports = { safeAccelerator, pick, alternates, FALLBACKS, GAME_KEYS, MAX_CHARS };
