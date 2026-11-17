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

import re

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
