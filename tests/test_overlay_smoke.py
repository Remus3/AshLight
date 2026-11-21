"""TEST-OVL: the overlay smoke test named by CLAUDE.md and decision 0002.

Static part (always runs): app/main.js and the overlay page keep the window
flags and the render rules the FPS / RAM budgets rest on.

Live part (opt-in: AL_OVERLAY_SMOKE=1, Windows, Electron installed in app/ or
in the main checkout's app/): starts the real overlay with an isolated
profile (AL_SIDECAR_ROOT in tmp, so a running overlay's single-instance lock
is not hit) and AL_OVERLAY_SMOKE_S, samples every Electron process in the
started overlay's own process tree, and asserts the decision 0002 budgets:
at most 2 processes, summed working set under 215 MB (UX-OVL-RAM: the
decision's 250 MB, tightened to about 15 percent over the 186 MB peak
measured with the core's SSE feed bursting), idle CPU under 1 percent of
one core, a clean exit. Opt-in because it
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
RAM_BUDGET = 215 * 1024 * 1024  # decision 0002: 250 MB; measured peak 186 MB
MAX_PROCS = 2  # browser + renderer (no GPU or network utility process)
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
                   "requestSingleInstanceLock()",
                   'appendSwitch("enable-features", "NetworkServiceInProcess2")'):
        assert needle in code, needle


def _overlay_sources():
    """Every overlay source the Electron app loads (app/ minus tests and
    node_modules): .js, .html."""
    app = ROOT / "app"
    out = {}
    for p in sorted(app.rglob("*")):
        rel = p.relative_to(app).as_posix()
        if (p.suffix in (".js", ".html") and p.is_file()
                and not rel.startswith(("node_modules/", "test/"))):
            out[rel] = p.read_text(encoding="utf-8")
    return out


# OVL-SHELL-GUARDS (decision 0061): debugging switches and process starts
# by bare name, banned in app/ next to the P4-6 list.
DEBUG_NAMES = (r"remote-debugging-(port|pipe|address)", r"--inspect", r"\binspect-brk\b",
               r"\bNODE_OPTIONS\b", r"enableNodeCliInspectArguments")
SPAWN_NAMES = (r"(?<![\w.$])(spawn|spawnSync|execFile|execFileSync|execSync|exec|fork)\s*\(",)


def test_p4_6_ram_budget_static_guard():
    """AREA-AUDIT P4-6: the UX-OVL-RAM budget (at most 2 processes: browser +
    one renderer) is measured only by the opt-in live smoke below; this
    always-on guard fails on the code changes that would add a process: a
    second window or view, a worker, a child / utility process, a webview or
    iframe, a second enable-features switch (it would replace
    NetworkServiceInProcess2), or the in-process switches set after ready.
    OVL-SHELL-GUARDS (decision 0061): the same one ban list also holds the
    debugging switch names (only app/guards.js, the one detector, may name
    them) and the bare spawn names (only client/launcher.js runs a
    process)."""
    src = _overlay_sources()
    assert "main.js" in src and "overlay/index.html" in src
    code = {k: (_code(v) if k.endswith(".js") else re.sub(r"<!--.*?-->", "", v, flags=re.S))
            for k, v in src.items()}
    windows = {k: len(re.findall(r"\bnew\s+BrowserWindow\s*\(", c)) for k, c in code.items()}
    windows = {k: n for k, n in windows.items() if n}
    # one overlay window (one renderer process). DESKTOP-CLIENT (decision
    # 0041): the companion window lives in client/window.js and is built
    # only in client mode (--client), never at the overlay-only start the
    # live smoke below measures.
    assert windows == {"main.js": 1, "client/window.js": 1}, windows
    banned = (r"child_process", r"\butilityProcess\b", r"\bnew\s+(Shared)?Worker\s*\(",
              r"\bBrowserView\b", r"\bWebContentsView\b", r"webviewTag\s*:\s*true",
              r"<\s*webview\b", r"<\s*iframe\b", r"\bwindow\.open\s*\(",
              r"serviceWorker\.register", r"nodeIntegrationInWorker\s*:\s*true",
              r"\bprocess\.fork\b") + DEBUG_NAMES + SPAWN_NAMES
    for name, c in code.items():
        for pat in banned:
            if pat in ((r"child_process",) + SPAWN_NAMES) and name == "client/launcher.js":
                continue  # DESKTOP-CLIENT: runs the repo's run.ps1 / stop.ps1 only
            if pat in DEBUG_NAMES and name == "guards.js":
                continue  # OVL-SHELL-GUARDS: the one place that detects them
            assert not re.search(pat, c), (name, pat)
    # the guards part loads before every window-creating part: first, or second
    # after the crash-guard part (05, which creates no window or webContents)
    parts = sorted(k for k in code if k.startswith("parts/"))
    assert parts and parts[0] in ("parts/10-guards.js", "parts/05-crashguard.js"), parts
    if parts[0] == "parts/05-crashguard.js":
        assert parts[1] == "parts/10-guards.js", parts
        assert not re.search(r"new\s+(BrowserWindow|BrowserView|WebContentsView)|webContents\.create",
                             code["parts/05-crashguard.js"])
    main = code["main.js"]
    # the companion window module loads lazily, inside openClient() only
    assert 'require("./client/window.js")' not in main.split("function openClient")[0]
    # popups stay denied (a popup is a new window and renderer)
    assert 'setWindowOpenHandler(() => ({ action: "deny" }))' in main
    assert len(re.findall(r'appendSwitch\(\s*"enable-features"', main)) == 1
    assert "disable-features" not in main
    ready = main.index("app.whenReady()")
    for switch in ('appendSwitch("in-process-gpu")',
                   'appendSwitch("enable-features", "NetworkServiceInProcess2")',
                   "app.disableHardwareAcceleration()"):
        assert main.index(switch) < ready, switch
    assert MAX_PROCS == 2 and RAM_BUDGET == 215 * 1024 * 1024


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


def _sample(root):
    """[(pid, working_set, cpu_100ns)] of the Electron processes in the tree
    under the started overlay's pid (the browser process's command line
    does not name the profile, so a profile match would miss it)."""
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='electron.exe'\" | "
          "Select-Object ProcessId,ParentProcessId,WorkingSetSize,KernelModeTime,UserModeTime"
          " | ConvertTo-Json -Compress")
    out = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps],
                         capture_output=True, text=True, timeout=60).stdout.strip()
    rows = json.loads(out) if out else []
    rows = rows if isinstance(rows, list) else [rows]
    want, grew = {root}, True
    while grew:
        grew = False
        for r in rows:
            if r["ParentProcessId"] in want and r["ProcessId"] not in want:
                want.add(r["ProcessId"])
                grew = True
    return [(r["ProcessId"], int(r["WorkingSetSize"]),
             int(r["KernelModeTime"]) + int(r["UserModeTime"]))
            for r in rows if r["ProcessId"] in want]


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
    env.pop("NODE_OPTIONS", None)  # decision 0061: the shell quits on it
    proc = subprocess.Popen([str(exe), str(ROOT / "app")], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        t0 = time.monotonic()
        peak, procs, first, last = 0, 0, None, None
        while time.monotonic() - t0 < IDLE_TO_S:
            rows = _sample(proc.pid)
            el = time.monotonic() - t0
            if rows:
                peak = max(peak, sum(r[1] for r in rows))
                procs = max(procs, len(rows))
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
    assert procs <= MAX_PROCS, f"{procs} Electron processes"
    assert peak < RAM_BUDGET, f"summed working set {peak / 2**20:.1f} MB"
    share = (last[1] - first[1]) / 1e7 / (last[0] - first[0])
    print(f"overlay smoke: {len(last[2])} processes, peak summed working set "
          f"{peak / 2**20:.1f} MB, idle CPU {share * 100:.3f} percent of one core")
    assert share < CPU_BUDGET * fleet_test_guard.load_factor(), f"{share * 100:.2f} percent"
