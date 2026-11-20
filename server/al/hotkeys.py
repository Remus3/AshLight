"""AREA-AUDIT P5-3: the AshLight hotkey rule (core side). Mirror of
app/hotkey.js; both read the case table in app/test/hotkey_cases.json.

Electron's globalShortcut takes its key from EVERY program, the game
included. So an AshLight hotkey always holds Ctrl or Alt (Shift alone only
with an F key: Shift + a letter types in the game's chat), and never a
combination the game or Windows uses (item copy Ctrl+C / Ctrl+Alt+C,
paste, stash search, chat send, Alt+F4, Alt+Tab,
Alt+Shift+Tab, Ctrl+Alt+Tab, Task Manager Ctrl+Shift+Esc, Ctrl+Alt+Delete
...). The Win key is never a modifier: Windows owns it.
"""

import json
import re
from pathlib import Path

MAX_CHARS = 40
_CHARS = re.compile(r"[A-Za-z0-9+ ]+")
_MODS = {"ctrl": "Ctrl", "control": "Ctrl", "commandorcontrol": "Ctrl", "cmdorctrl": "Ctrl",
         "alt": "Alt", "shift": "Shift"}
_ORDER = ("Ctrl", "Alt", "Shift")
_NAMED = ("Space", "Tab", "Enter", "Backspace", "Delete", "Insert", "Home", "End",
          "PageUp", "PageDown", "Up", "Down", "Left", "Right", "Escape")
_ALIAS = {"return": "Enter", "esc": "Escape"}
_F = re.compile(r"^f([1-9]|1[0-9]|2[0-4])$")
GAME_KEYS = frozenset({
    "Ctrl+C", "Ctrl+Alt+C", "Ctrl+V", "Ctrl+X", "Ctrl+A", "Ctrl+Z", "Ctrl+F",
    "Ctrl+Enter", "Ctrl+Escape", "Ctrl+Shift+Escape", "Ctrl+Alt+Delete",
    "Alt+F4", "Alt+Tab", "Alt+Enter", "Alt+Escape", "Alt+Space",
    "Alt+Shift+Tab", "Ctrl+Alt+Tab", "Alt+Shift+Escape", "Ctrl+Alt+End"})


def _key(token):
    low = token.lower()
    if len(low) == 1 and (low.isdigit() or "a" <= low <= "z"):
        return low.upper()
    m = _F.match(low)
    if m:
        return "F" + m.group(1)
    if low in _ALIAS:
        return _ALIAS[low]
    for name in _NAMED:
        if name.lower() == low:
            return name
    return None


def safe_accelerator(value):
    """The canonical accelerator ("Ctrl+Alt+K"), or None when it is not a
    safe AshLight hotkey."""
    if not isinstance(value, str) or len(value) > MAX_CHARS or not _CHARS.fullmatch(value):
        return None
    tokens = [t.strip() for t in value.split("+")]
    if len(tokens) < 2 or not all(tokens):
        return None
    key = _key(tokens[-1])
    if key is None:
        return None
    mods = set()
    for t in tokens[:-1]:
        m = _MODS.get(t.lower())
        if m is None or m in mods:
            return None
        mods.add(m)
    if not mods & {"Ctrl", "Alt"} and not (key[0] == "F" and key[1:].isdigit()):
        return None
    out = "+".join([m for m in _ORDER if m in mods] + [key])
    return None if out in GAME_KEYS else out


# -- HOTKEYS-LIVE (decision 0058, OVL-KEYS-CORE): the core side

# The short safe lists a taken key falls back to, in order (the first entry
# is the built-in default). Mirror of app/hotkey.js FALLBACKS; both equal
# app/test/hotkey_cases.json "fallbacks".
FALLBACKS = {
    "eval": ("Alt+Shift+E", "Ctrl+Shift+F9", "Alt+Shift+F9", "Ctrl+Alt+F9"),
    "toggle": ("Alt+Shift+A", "Ctrl+Shift+F10", "Alt+Shift+F10", "Ctrl+Alt+F10"),
}
NAMES = ("eval", "toggle")
# The config/local.json key of each shortcut (app/parts/20-hotkeys.js CONFIG).
CONFIG_KEYS = {"eval": "eval_hotkey", "toggle": "overlay_toggle"}
# The client's runtime file (app/parts/20-hotkeys.js FILE_NAME) and the
# most bytes the core reads of it (the client writes about 400).
FILE_NAME = "hotkeys.json"
MAX_FILE_BYTES = 8 * 1024
# The player words of each shortcut (settingsio.LABELS) and the refusal
# sentences of POST /api/hotkeys (the unsafe one is settingsio._hotkey's).
LABELS = {"eval": "item check hotkey", "toggle": "overlay hotkey"}
REFUSE_UNSAFE = ("needs Ctrl or Alt held with a key, and can't be a key "
                 "the game uses")
REFUSE_NAME = 'name must be "eval" or "toggle"'


def _flag(v):
    return v if isinstance(v, bool) else None


def _entry(raw):
    """One validated keys entry of the runtime file: {"key", "want",
    "registered", "fallback"}; a bad part reads None. "registered" is True
    only with a safe bound key, so a claimed binding the rule refuses is
    unknown, never shown."""
    raw = raw if isinstance(raw, dict) else {}
    bound = safe_accelerator(raw.get("bound"))
    registered = _flag(raw.get("registered"))
    if registered is True and bound is None:
        registered = None
    if registered is not True:
        bound = None
    fallback = _flag(raw.get("fallback")) if registered is True else None
    if registered is False:
        fallback = False
    return {"key": bound, "want": safe_accelerator(raw.get("want")),
            "registered": registered, "fallback": fallback}


def read_runtime(runtime_dir):
    """The client's ops/runtime/hotkeys.json, validated and bounded:
    {"eval": entry, "toggle": entry, "overlay_on": bool | None}, or None
    when the file is missing, too big, not JSON or not an object. Every
    key goes through safe_accelerator; bad parts read None."""
    path = Path(runtime_dir) / FILE_NAME
    try:
        with open(path, "rb") as fh:
            raw = fh.read(MAX_FILE_BYTES + 1)
    except OSError:
        return None
    if len(raw) > MAX_FILE_BYTES:
        return None
    try:
        doc = json.loads(raw.decode("ascii"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None
    if not isinstance(doc, dict):
        return None
    keys = doc.get("keys") if isinstance(doc.get("keys"), dict) else {}
    overlay = doc.get("overlay") if isinstance(doc.get("overlay"), dict) else {}
    out = {name: _entry(keys.get(name)) for name in NAMES}
    out["overlay_on"] = _flag(overlay.get("user_on"))
    return out


def wanted(cfg, name):
    """The key the player asked for: the config value made canonical,
    else the built-in default (app/hotkey.js pick, without the env)."""
    cfg = cfg if isinstance(cfg, dict) else {}
    return safe_accelerator(cfg.get(CONFIG_KEYS[name])) or FALLBACKS[name][0]


def view(cfg, runtime):
    """The published hotkeys view: {"eval": {"key", "want", "registered",
    "fallback"}, "toggle": {...}, "overlay_on"}. "key" is the bound key
    from the client's runtime file; with no file every unknown field is
    None and "want" comes from the config (or the default)."""
    runtime = runtime if isinstance(runtime, dict) else None
    out = {}
    for name in NAMES:
        known = runtime.get(name) if runtime else None
        entry = (dict(known) if isinstance(known, dict)
                 else {"key": None, "want": None, "registered": None, "fallback": None})
        if entry.get("want") is None:
            entry["want"] = wanted(cfg, name)
        out[name] = entry
    out["overlay_on"] = runtime.get("overlay_on") if runtime else None
    return out


def check_new(name, key, cfg, current=None):
    """The canonical key for POST /api/hotkeys, or raise ValueError with the
    refusal sentence: an unknown name, a key the rule refuses (a game key)
    or the other shortcut's key (wanted or bound)."""
    if name not in NAMES:
        raise ValueError(REFUSE_NAME)
    ok = safe_accelerator(key)
    if ok is None:
        raise ValueError(f"The {LABELS[name]} {REFUSE_UNSAFE}.")
    other = NAMES[1 - NAMES.index(name)]
    taken = {wanted(cfg, other)}
    cur = (current or {}).get(other) if isinstance(current, dict) else None
    if isinstance(cur, dict) and cur.get("key"):
        taken.add(cur["key"])
    if ok in taken:
        raise ValueError(f"The {LABELS[name]} can't be the same key as the "
                         f"{LABELS[other]}.")
    return ok
