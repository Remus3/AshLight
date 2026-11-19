"""OVL-CLIENT-ZOOM (F-145): zoom keys in the desktop client window.

Static part (always runs): the zoom part exists, hooks only the client
window, and main.js still hands the client window to the parts seam with no
menu (the reason the default zoom accelerators were gone).

Live part (opt-in: AL_ZOOM_PROBE=1, Windows, Electron installed in app/ or
the main checkout's app/): runs app/test/electron/zoom_probe.js, which opens
a hidden window of its own, sends Ctrl+= / Ctrl+wheel / Ctrl+0 to that
window's own webContents and reads the zoom factor back.
"""

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
PART = APP / "parts" / "30-zoom.js"
ZOOM = APP / "client" / "zoom.js"
PROBE = APP / "test" / "electron" / "zoom_probe.js"


def _code(js):
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return re.sub(r"(^|[^:])//[^\n]*", r"\1", js)


def test_zoom_part_hooks_the_client_window_only():
    code = _code(PART.read_text(encoding="utf-8"))
    assert "module.exports = { clientWindow }" in code
    assert '"before-input-event"' in code and '"zoom-changed"' in code
    for banned in ("overlayWindow", "getOverlay", "globalShortcut", "sendInputEvent",
                   "clipboard"):
        assert banned not in code, banned


def test_zoom_levels_reach_two_and_start_at_one():
    code = _code(ZOOM.read_text(encoding="utf-8"))
    m = re.search(r"const LEVELS = \[([^\]]*)\]", code)
    assert m, "LEVELS missing"
    levels = [float(x) for x in m.group(1).split(",")]
    assert levels == sorted(levels)
    assert levels[-1] == 2.0 and 1.0 in levels
    assert levels[levels.index(1.0) + 1] == 1.1


def test_client_window_reaches_the_parts_seam_without_a_menu():
    main = _code((APP / "main.js").read_text(encoding="utf-8"))
    assert 'onWindow: (w, s) => runParts("clientWindow", w, s)' in main
    win = _code((APP / "client" / "window.js").read_text(encoding="utf-8"))
    assert "win.setMenu(null)" in win
    assert "opts.onWindow(win, clientSession())" in win


def _electron():
    exe = APP / "node_modules" / "electron" / "dist" / "electron.exe"
    if exe.is_file():
        return exe
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip()
    if common:
        exe = (ROOT / common).resolve().parent / "app" / "node_modules" / "electron" \
            / "dist" / "electron.exe"
        if exe.is_file():
            return exe
    return None


@pytest.mark.skipif(os.environ.get("AL_ZOOM_PROBE") != "1" or os.name != "nt",
                    reason="live zoom probe is opt-in (AL_ZOOM_PROBE=1, Windows)")
def test_live_zoom_probe(tmp_path):
    exe = _electron()
    if exe is None:
        pytest.skip("Electron not installed (npm ci --prefix app)")
    env = dict(os.environ)
    env.pop("ELECTRON_RUN_AS_NODE", None)
    out = subprocess.run([str(exe), str(PROBE), str(tmp_path)], capture_output=True,
                         text=True, timeout=90, env=env).stdout
    line = next((ln for ln in out.splitlines() if ln.startswith("ZOOMPROBE ")), None)
    assert line, out
    r = json.loads(line[len("ZOOMPROBE "):])
    assert "error" not in r, r
    assert r["start"] == pytest.approx(1.0)
    assert r["afterOneIn"] == pytest.approx(1.1)
    assert r["afterManyIn"] == pytest.approx(2.0)
    assert r["afterReset"] == pytest.approx(1.0)
    assert r["afterWheel"] != pytest.approx(1.0), "Ctrl+wheel did not zoom"
    assert r["afterRestart"] == pytest.approx(r["beforeRestart"])
    saved = json.loads((tmp_path / "client_zoom.json").read_text(encoding="ascii"))
    assert saved["zoom"] == pytest.approx(r["beforeRestart"])
