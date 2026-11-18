"""FLOOR-STATIC-SCAN: a static ToS floor scan of AshLight's own code.

CLAUDE.md game ToS floor (decision 0003, research 0001, research 0026): no
input to the game, no game memory, no injection / DirectX hooks / packets,
the screen and the clipboard read only once per manual press of an AshLight
hotkey. tests/test_overlay_smoke.py checks two overlay files for a few words;
this test greps every authored text file under server/, tools/, scripts/,
app/ and web/ (node_modules and caches skipped) for:

- input APIs (SendInput, SendKeys, keybd_event, mouse_event, Electron
  sendInputEvent, robotjs, nut-js, pyautogui, pynput, ...),
- memory / injection APIs (ReadProcessMemory, WriteProcessMemory,
  VirtualAllocEx, CreateRemoteThread, SetWindowsHookEx, PROCESS_VM_*),
- screen capture (CopyFromScreen, ImageGrab, BitBlt, desktopCapturer,
  capturePage, PrintWindow, mss),
- DXGI / Direct3D hooks and present tracing (dxgi, d3d11, Present hooks,
  PresentMon, MinHook, Detours; decision 0006),
- packet capture (WinDivert, pcap),
- clipboard READS anywhere except the one item-check hotkey handler
  (clipboard writes on a player's click are allowed, decision 0014).

A hit fails unless an ALLOW entry names the file, the pattern, how many hits
are expected, an anchor that must sit on or just above each hit, and a
non-empty reason. A stale ALLOW entry (no longer hit) also fails, so the list
cannot rot. The scan is raw text on purpose: comments and strings count, so
a planted call cannot hide behind a language the scanner does not parse; a
harmless mention gets an allow entry with its reason instead.
"""

import re
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ("server", "tools", "scripts", "app", "web")
SKIP_DIRS = {"node_modules", "__pycache__", ".pytest_cache", "dist", "out"}
TEXT_EXT = {".py", ".pyw", ".js", ".mjs", ".cjs", ".ts", ".ps1", ".psm1",
            ".psd1", ".cmd", ".bat", ".lua", ".html", ".htm", ".css",
            ".json", ".ahk", ".vbs", ".sh", ".c", ".cpp", ".h", ".cs"}

# (id, compiled regex). Case-insensitive unless the word is too common.
_I = re.IGNORECASE
BANNED = [
    # input to the game
    ("SendInput", re.compile(r"\bSendInput\b", _I)),
    ("SendKeys", re.compile(r"\bSendKeys\b|\bSendWait\b", _I)),
    ("keybd_event", re.compile(r"\bkeybd_event\b", _I)),
    ("mouse_event", re.compile(r"\bmouse_event\b", _I)),
    ("sendInputEvent", re.compile(r"\bsendInputEvent\b", _I)),
    ("robotjs", re.compile(r"\brobotjs\b", _I)),
    ("nut-js", re.compile(r"nut-js|@nut-tree", _I)),
    ("keyTap", re.compile(r"\bkeyTap\b|\bmouseClick\b", _I)),
    ("pyautogui", re.compile(r"\bpyautogui\b|\bpynput\b|\bpydirectinput\b", _I)),
    ("window-message input", re.compile(r"\bWM_(KEYDOWN|KEYUP|CHAR|LBUTTONDOWN|RBUTTONDOWN)\b")),
    # game memory / injection
    ("ReadProcessMemory", re.compile(r"\b(Nt|Zw)?ReadProcessMemory\b|\bNtReadVirtualMemory\b", _I)),
    ("WriteProcessMemory", re.compile(r"\b(Nt|Zw)?WriteProcessMemory\b|\bNtWriteVirtualMemory\b", _I)),
    ("VirtualAllocEx", re.compile(r"\bVirtualAllocEx\b|\bVirtualProtectEx\b", _I)),
    ("CreateRemoteThread", re.compile(r"\bCreateRemoteThread(Ex)?\b|\bQueueUserAPC\b", _I)),
    ("SetWindowsHookEx", re.compile(r"\bSetWindowsHookEx[AW]?\b", _I)),
    ("PROCESS_VM access", re.compile(r"\bPROCESS_VM_(READ|WRITE|OPERATION)\b|\bPROCESS_ALL_ACCESS\b", _I)),
    # screen capture
    ("CopyFromScreen", re.compile(r"\bCopyFromScreen\b", _I)),
    ("ImageGrab", re.compile(r"\bImageGrab\b|\bpyscreenshot\b", _I)),
    ("BitBlt", re.compile(r"\bBitBlt\b|\bPrintWindow\b|\bGetDIBits\b", _I)),
    ("desktopCapturer", re.compile(r"\bdesktopCapturer\b|\bgetDisplayMedia\b", _I)),
    ("capturePage", re.compile(r"\bcapturePage\b", _I)),
    ("mss", re.compile(r"^\s*(import mss|from mss\b)", re.MULTILINE)),
    # DXGI / Direct3D hooks, present tracing (decision 0006)
    ("DXGI", re.compile(r"\bI?DXGI\w*|\bdxgi\.dll\b|\bd3d1[12]\w*\b|\bd3d9\b", _I)),
    ("Present hook", re.compile(r"\bPresentMon\b|\bMinHook\b|\bDetours\b|\bDetourAttach\b", _I)),
    # packets
    ("packet capture", re.compile(r"\bWinDivert\b|\bn?pcap\b|\bscapy\b", _I)),
    # clipboard reads (writes on a click are fine, decision 0014)
    ("clipboard read", re.compile(
        r"clipboard\s*\.\s*read\w*\s*\("                 # Electron / navigator
        r"|\bGetClipboardData\b|\bOpenClipboard\b"       # Win32
        r"|\bGet-Clipboard\b|Clipboard\]::Get\w*"        # PowerShell / .NET
        r"|\bclipboard_get\b|\bpyperclip\b|\bwin32clipboard\b"  # Python
        r"|\bexecCommand\s*\(\s*['\"]paste['\"]", _I)),
]

# Every allowed hit: (relpath, banned id, count, anchor, reason).
# anchor: a substring that must appear on the hit line or within the 3 lines
# above it, so the allowance stays pinned to the place it was reasoned about.
ALLOW = [
    ("app/main.js", "clipboard read", 1,
     "EvalKey.createEvalHotkey({",
     "The one clipboard read: readText handed to the item-check hotkey "
     "handler (eval_hotkey.js), called once per manual press, never at "
     "start, by a timer or a watcher (decision 0003)."),
    ("scripts/brand_render.js", "capturePage", 1,
     "offscreen page only, never the screen",
     "BRAND-ICON build tool: captures its own offscreen window holding "
     "AshLight's brand SVG to write the icon PNGs; never the screen, never "
     "the game, never at run time (docs/design/0005-brand-mark.md)."),
    ("app/test/eval.test.js", "SendInput", 1, "for (const word of [",
     "A banned-word list: the node test asserts eval_hotkey.js never "
     "contains sendInput; the word is the check, not a call."),
    ("app/test/eval.test.js", "keyTap", 1, "for (const word of [",
     "Same banned-word list as above: asserts eval_hotkey.js never "
     "contains keyTap; the word is the check, not a call."),
]

MAX_BYTES = 4 * 1024 * 1024
ANCHOR_LINES = 3


def _files(root):
    for top in SCAN_DIRS:
        base = root / top
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            rel = p.relative_to(root)
            if any(part in SKIP_DIRS for part in rel.parts):
                continue
            try:
                ok = (p.is_file() and p.suffix.lower() in TEXT_EXT
                      and p.stat().st_size <= MAX_BYTES)
            except OSError:  # a file another test removed mid-walk
                continue
            if ok:
                yield p, rel.as_posix()


def scan(root):
    """All hits under root: list of (relpath, banned id, line no, line)."""
    hits = []
    for path, rel in _files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:  # a file another test removed mid-walk
            continue
        for bid, rx in BANNED:
            for m in rx.finditer(text):
                lno = text.count("\n", 0, m.start()) + 1
                hits.append((rel, bid, lno, text.splitlines()[lno - 1].strip()))
    return hits


def violations(root, allow=ALLOW):
    """Hits not covered by an allow entry, plus allow entries that broke
    (wrong count, anchor missing, stale). Empty list = floor holds."""
    hits = scan(root)
    out = []
    by_key = {}
    for h in hits:
        by_key.setdefault((h[0], h[1]), []).append(h)
    allowed = {(a[0], a[1]): a for a in allow}
    for key, hs in sorted(by_key.items()):
        entry = allowed.get(key)
        if entry is None:
            out.extend(f"{r}:{n}: {b}: {line[:120]}" for r, b, n, line in hs)
            continue
        _, _, count, anchor, _ = entry
        if count is not None and len(hs) != count:
            out.append(f"{key[0]}: {key[1]}: {len(hs)} hits, allow-list says {count}: "
                       + "; ".join(f"line {n}" for _, _, n, _ in hs))
        if anchor:
            lines = (root / key[0]).read_text(encoding="utf-8", errors="replace").splitlines()
            for _, _, n, _ in hs:
                window = lines[max(0, n - 1 - ANCHOR_LINES):n]
                if not any(anchor in w for w in window):
                    out.append(f"{key[0]}:{n}: {key[1]}: outside its allowed place "
                               f"(anchor {anchor!r} not on or just above it)")
    for key in allowed:
        if key not in by_key:
            out.append(f"stale allow entry {key}: no hit left, remove it")
    return out


def test_allow_entries_name_a_reason():
    seen = set()
    for rel, bid, count, anchor, reason in ALLOW:
        assert bid in {b for b, _ in BANNED}, bid
        assert isinstance(reason, str) and len(reason.split()) >= 5, (rel, bid)
        assert reason.isascii()
        assert count is None or count >= 1
        assert (rel, bid) not in seen, (rel, bid)
        seen.add((rel, bid))


def test_floor_holds_on_the_tree():
    found = violations(ROOT)
    assert not found, "ToS floor scan:\n" + "\n".join(found)


def test_scan_covers_the_shipped_code():
    rels = {rel for _, rel in _files(ROOT)}
    for must in ("app/main.js", "app/eval_hotkey.js", "app/preload.js",
                 "server/al/http.py", "server/al/core.py", "scripts/run.ps1",
                 "web/app.js"):
        assert must in rels, must
    assert not any("node_modules" in r for r in rels)


@pytest.fixture(scope="module")
def tree_copy(tmp_path_factory):
    dst = tmp_path_factory.mktemp("floor")
    for top in SCAN_DIRS:
        if (ROOT / top).is_dir():
            shutil.copytree(ROOT / top, dst / top,
                            ignore=shutil.ignore_patterns(*SKIP_DIRS))
    assert not violations(dst), "the clean copy must pass"
    return dst


PLANTS = [
    ("server/al/pfloor_plant.py", "ctypes.windll.user32.SendInput(1, ptr, size)\n"),
    ("tools/pfloor_plant.ps1", "[System.Windows.Forms.SendKeys]::SendWait('^c')\n"),
    ("server/al/pfloor_plant.py", "user32.keybd_event(0x11, 0, 0, 0)\n"),
    ("server/al/pfloor_plant.py", "user32.mouse_event(2, 0, 0, 0, 0)\n"),
    ("app/pfloor_plant.js", "win.webContents.sendInputEvent({ type: 'keyDown' });\n"),
    ("app/pfloor_plant.js", "const robot = require('robotjs'); robot.keyTap('c');\n"),
    ("app/pfloor_plant.js", "const { keyboard } = require('@nut-tree/nut-js');\n"),
    ("tools/pfloor_plant.py", "import pyautogui\npyautogui.press('c')\n"),
    ("server/al/pfloor_plant.py", "k.ReadProcessMemory(h, addr, buf, n, None)\n"),
    ("server/al/pfloor_plant.py", "k.WriteProcessMemory(h, addr, buf, n, None)\n"),
    ("server/al/pfloor_plant.py", "k.VirtualAllocEx(h, 0, n, 0x3000, 0x40)\n"),
    ("server/al/pfloor_plant.py", "k.CreateRemoteThread(h, None, 0, f, a, 0, None)\n"),
    ("server/al/pfloor_plant.py", "OPEN = PROCESS_VM_READ | 0x400\n"),
    ("scripts/pfloor_plant.ps1", "$g.CopyFromScreen(0, 0, 0, 0, $size)\n"),
    ("tools/pfloor_plant.py", "from PIL import ImageGrab\nImageGrab.grab()\n"),
    ("server/al/pfloor_plant.py", "gdi32.BitBlt(dst, 0, 0, w, h, src, 0, 0, 0xCC0020)\n"),
    ("app/pfloor_plant.js", "const { desktopCapturer } = require('electron');\n"),
    ("app/pfloor_plant.js", "win.webContents.capturePage().then(save);\n"),
    ("tools/pfloor_plant.py", "import mss\n"),
    ("server/al/pfloor_plant.py", "dxgi = ctypes.WinDLL('dxgi.dll')\n"),
    ("server/al/pfloor_plant.py", "hook(IDXGISwapChain_Present, mine)\n"),
    ("tools/pfloor_plant.ps1", "& PresentMon.exe --process_name game.exe\n"),
    ("server/al/pfloor_plant.py", "import pydivert  # WinDivert\n"),
    ("app/pfloor_plant.js", "setInterval(() => clipboard.readText(), 500);\n"),
    ("web/pfloor_plant.js", "navigator.clipboard.readText().then(show);\n"),
    ("server/al/pfloor_plant.py", "user32.OpenClipboard(0); user32.GetClipboardData(13)\n"),
    ("scripts/pfloor_plant.ps1", "$t = Get-Clipboard -Raw\n"),
    ("tools/pfloor_plant.py", "import pyperclip\npyperclip.paste()\n"),
    ("tools/pfloor_plant.py", "root.clipboard_get()\n"),
]


@pytest.mark.parametrize("rel,code", PLANTS, ids=[p[1].strip()[:40] for p in PLANTS])
def test_planted_call_fails_the_scan(tree_copy, rel, code):
    target = tree_copy / rel
    assert not target.exists()
    target.write_text(code, encoding="ascii", newline="\n")
    try:
        found = violations(tree_copy)
    finally:
        target.unlink()
    assert any(rel in f for f in found), found


def test_second_clipboard_read_in_main_js_fails(tree_copy):
    """The allowed read is pinned to the hotkey handler: a second read in the
    same file (outside the handler) fails on count and on anchor."""
    main = tree_copy / "app" / "main.js"
    original = main.read_bytes()
    try:
        main.write_bytes(original + b"\napp.on('ready', () => clipboard.readText());\n")
        found = violations(tree_copy)
    finally:
        main.write_bytes(original)
    assert any("allow-list says 1" in f for f in found), found
    assert any("outside its allowed place" in f for f in found), found


def test_moved_clipboard_read_fails(tree_copy):
    """Same count, wrong place: the anchor check catches a read moved out of
    the hotkey handler."""
    main = tree_copy / "app" / "main.js"
    original = main.read_bytes()
    text = original.decode("utf-8")
    moved = text.replace("readText: () => clipboard.readText(),",
                         "readText: () => cached,", 1)
    assert moved != text
    moved = moved.replace("app.on(\"will-quit\"",
                          "const cached = clipboard.readText();\napp.on(\"will-quit\"", 1)
    try:
        main.write_bytes(moved.encode("utf-8"))
        found = violations(tree_copy)
    finally:
        main.write_bytes(original)
    assert any("outside its allowed place" in f for f in found), found


def test_stale_allow_entry_fails(tree_copy):
    extra = ALLOW + [("server/al/core.py", "SendInput", 1, "", "a stale test entry "
                      "that matches nothing")]
    assert any("stale allow entry" in f for f in violations(tree_copy, extra))
