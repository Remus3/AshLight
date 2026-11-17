"""TEST-OVL: the overlay smoke test named by CLAUDE.md and decision 0002.

Static part (always runs): app/main.js and the overlay page keep the window
flags and the render rules the FPS / RAM budgets rest on.

Live part (opt-in: AL_OVERLAY_SMOKE=1, Windows, Electron installed in app/ or
in the main checkout's app/): starts the real overlay with an isolated
profile (AL_SIDECAR_ROOT in tmp, so a running overlay's single-instance lock
is not hit) and AL_OVERLAY_SMOKE_S, samples every Electron process of that
profile, and asserts the decision 0002 budgets: summed working set under
250 MB, idle CPU under 1 percent of one core, a clean exit. Opt-in because it
puts a (transparent, click-through) window on the screen for a few seconds;
the armed loop's suites never set it.
"""

import json
import os
import re
import subprocess
import time
from pathlib import Path

import pytest

import fleet_test_guard

ROOT = Path(__file__).resolve().parents[1]
MAIN_JS = (ROOT / "app" / "main.js").read_text(encoding="utf-8")
OVL_JS = (ROOT / "app" / "overlay" / "overlay.js").read_text(encoding="utf-8")
OVL_CSS = (ROOT / "app" / "overlay" / "overlay.css").read_text(encoding="utf-8")
RAM_BUDGET = 250 * 1024 * 1024
CPU_BUDGET = 0.01  # share of one core, idle
SMOKE_S = 14
IDLE_FROM_S, IDLE_TO_S = 5, 12


def _code(js):
    """JS with // and /* */ comments removed (rules apply to code only)."""
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return re.sub(r"(^|[^:])//[^\n]*", r"\1", js)


def test_window_flags_behind_the_budgets():
    code = _code(MAIN_JS)
    for needle in ("app.disableHardwareAcceleration()", 'appendSwitch("in-process-gpu")',
                   "transparent: true", "alwaysOnTop: true", "focusable: false",
                   "skipTaskbar: true", "frame: false", "setIgnoreMouseEvents(true)",
                   "requestSingleInstanceLock()"):
        assert needle in code, needle


def test_overlay_sends_no_input_and_reads_no_clipboard_on_its_own():
    """ToS floor: nothing is ever sent to the game; no clipboard watcher."""
    code = _code(MAIN_JS) + _code(OVL_JS)
    for banned in ("sendInputEvent", "robotjs", "nut-js", "keyTap", "SendInput",
                   "clipboard.readText", "setInterval("):
        if banned == "clipboard.readText":
            # the one read lives in the hotkey handler module, not here
            assert banned not in _code(OVL_JS), banned
            continue
        assert banned not in code, banned


def test_overlay_page_renders_only_on_change():
    code = _code(OVL_JS)
    assert "requestAnimationFrame" not in code and "setInterval" not in code
    assert code.count("setTimeout(") <= 1  # the one card-expiry timer
    assert "animation: none !important" in OVL_CSS
    assert "transition: none !important" in OVL_CSS


def _electron():
    for base in (ROOT, Path(os.environ.get("AL_MAIN_CHECKOUT", "")) if
                 os.environ.get("AL_MAIN_CHECKOUT") else None):
        if base is None:
            continue
        exe = base / "app" / "node_modules" / "electron" / "dist" / "electron.exe"
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


def _sample(profile):
    """[(pid, working_set, cpu_100ns)] of the Electron processes whose
    command line names this profile dir (Chromium passes it to children)."""
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='electron.exe'\" | "
          "Select-Object ProcessId,WorkingSetSize,KernelModeTime,UserModeTime,CommandLine"
          " | ConvertTo-Json -Compress")
    out = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps],
                         capture_output=True, text=True, timeout=60).stdout.strip()
    rows = json.loads(out) if out else []
    rows = rows if isinstance(rows, list) else [rows]
    key = str(profile).lower()
    return [(r["ProcessId"], int(r["WorkingSetSize"]),
             int(r["KernelModeTime"]) + int(r["UserModeTime"]))
            for r in rows if key in (r.get("CommandLine") or "").lower()]


@pytest.mark.slow
@pytest.mark.skipif(os.environ.get("AL_OVERLAY_SMOKE") != "1" or os.name != "nt",
                    reason="live overlay smoke is opt-in (AL_OVERLAY_SMOKE=1, Windows)")
def test_live_overlay_smoke_within_budget(tmp_path):
    exe = _electron()
    if exe is None:
        pytest.skip("Electron not installed (npm ci --prefix app)")
    side = tmp_path / "sidecar"
    env = dict(os.environ, AL_SIDECAR_ROOT=str(side), AL_OVERLAY_SMOKE_S=str(SMOKE_S),
               AL_OVERLAY_TOGGLE="Alt+Shift+F9", AL_EVAL_HOTKEY="Alt+Shift+F10")
    env.pop("ELECTRON_RUN_AS_NODE", None)
    proc = subprocess.Popen([str(exe), str(ROOT / "app")], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    profile = side / "Cache" / "overlay-profile"
    try:
        t0 = time.monotonic()
        peak, first, last = 0, None, None
        while time.monotonic() - t0 < IDLE_TO_S:
            rows = _sample(profile)
            el = time.monotonic() - t0
            if rows:
                peak = max(peak, sum(r[1] for r in rows))
                cpu = sum(r[2] for r in rows)
                if el >= IDLE_FROM_S and first is None:
                    first = (el, cpu, {r[0] for r in rows})
                if first is not None:
                    last = (el, cpu, {r[0] for r in rows})
            assert proc.poll() is None, f"overlay exited early rc={proc.returncode}"
            time.sleep(0.5)
        rc = proc.wait(timeout=SMOKE_S + 20)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert first and last and last[0] > first[0], "no Electron process seen"
    assert rc == 0
    assert peak < RAM_BUDGET, f"summed working set {peak / 2**20:.1f} MB"
    share = (last[1] - first[1]) / 1e7 / (last[0] - first[0])
    print(f"overlay smoke: {len(last[2])} processes, peak summed working set "
          f"{peak / 2**20:.1f} MB, idle CPU {share * 100:.3f} percent of one core")
    assert share < CPU_BUDGET * fleet_test_guard.load_factor(), f"{share * 100:.2f} percent"
