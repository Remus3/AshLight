"""TEST-OVL: the overlay smoke test named by CLAUDE.md and decision 0002.

Static part (always runs): app/main.js and the overlay page keep the window
flags and the render rules the FPS / RAM budgets rest on.

Live part (opt-in: AL_OVERLAY_SMOKE=1, Windows, Electron installed in app/ or
in the main checkout's app/), in two shapes (RUN-BUDGET-TESTS-LIVE, research
0048 B10 / B11). Each starts the real Electron app with an isolated profile
(AL_SIDECAR_ROOT in tmp, so a running client's single-instance lock is not
hit) and AL_OVERLAY_SMOKE_S, samples every Electron process in the started
app's own process tree and checks a clean exit.
- Overlay alone (B10): at most 2 processes, summed working set under 215 MB
  (UX-OVL-RAM: the decision's 250 MB, tightened to about 15 percent over the
  186 MB peak measured with the core's SSE feed bursting), summed private
  bytes under B10's 120 MB, idle CPU under 1 percent of one core.
- Client with the companion (B11): --client against a test core this test
  starts on a leased port (AL_HOME in tmp holds its token, so the live
  token, config and core are never read); the companion shows that core's
  dashboard; at most 3 processes and a summed working set under B11's
  300 MB. The client log must show the dashboard and no run.ps1 start.
Opt-in because it puts AshLight's own (transparent, click-through) overlay
and its companion window on the screen for a few seconds; the armed loop's
suites never set it.
"""

import json
import os
import re
import subprocess
import time
from pathlib import Path

import pytest

import fleet_test_guard
from server.al import budgetlog

ROOT = Path(__file__).resolve().parents[1]
MAIN_JS = (ROOT / "app" / "main.js").read_text(encoding="utf-8")
OVL_JS = (ROOT / "app" / "overlay" / "overlay.js").read_text(encoding="utf-8")
OVL_CSS = (ROOT / "app" / "overlay" / "overlay.css").read_text(encoding="utf-8")
RAM_BUDGET = 215 * 1024 * 1024  # decision 0002: 250 MB; measured peak 186 MB
MAX_PROCS = 2  # browser + renderer (no GPU or network utility process)
CPU_BUDGET = 0.01  # share of one core, idle
SMOKE_S = 14
IDLE_FROM_S, IDLE_TO_S = 5, 12
B10 = budgetlog.BUDGETS["B10"]  # client, companion closed (research 0048)
B11 = budgetlog.BUDGETS["B11"]  # client, companion open
MB = 1024 * 1024
LIVE_SMOKE = pytest.mark.skipif(os.environ.get("AL_OVERLAY_SMOKE") != "1" or os.name != "nt",
                                reason="live overlay smoke is opt-in (AL_OVERLAY_SMOKE=1, Windows)")


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
    """[(pid, working_set, cpu_100ns, private)] of the Electron processes in
    the tree under the started app's pid (the browser process's command
    line does not name the profile, so a profile match would miss it)."""
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='electron.exe'\" | "
          "Select-Object ProcessId,ParentProcessId,WorkingSetSize,KernelModeTime,UserModeTime,"
          "PrivatePageCount | ConvertTo-Json -Compress")
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
             int(r["KernelModeTime"]) + int(r["UserModeTime"]),
             int(r.get("PrivatePageCount") or 0))
            for r in rows if r["ProcessId"] in want]


def _smoke_env(side, **extra):
    env = dict(os.environ, AL_SIDECAR_ROOT=str(side), AL_OVERLAY_SMOKE_S=str(SMOKE_S),
               AL_OVERLAY_TOGGLE="Alt+Shift+F9", AL_EVAL_HOTKEY="Alt+Shift+F10", **extra)
    env.pop("ELECTRON_RUN_AS_NODE", None)
    env.pop("NODE_OPTIONS", None)  # decision 0061: the shell quits on it
    env.pop("AL_DEV", None)
    return env


def _run_smoke(exe, args, env):
    """Start Electron with args, sample its tree until IDLE_TO_S, wait for its
    own SMOKE_S quit. {"rc", "procs", "peak", "peak_private", "share",
    "seen"}: the peak process count, summed working set and summed private
    bytes, and the CPU share of one core between IDLE_FROM_S and the last
    sample."""
    proc = subprocess.Popen([str(exe), *args], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        t0 = time.monotonic()
        peak, peak_priv, procs, first, last = 0, 0, 0, None, None
        while time.monotonic() - t0 < IDLE_TO_S:
            rows = _sample(proc.pid)
            el = time.monotonic() - t0
            if rows:
                peak = max(peak, sum(r[1] for r in rows))
                peak_priv = max(peak_priv, sum(r[3] for r in rows))
                procs = max(procs, len(rows))
                cpu = sum(r[2] for r in rows)
                if el >= IDLE_FROM_S and first is None:
                    first = (el, cpu, {r[0] for r in rows})
                if first is not None:
                    last = (el, cpu, {r[0] for r in rows})
            assert proc.poll() is None, f"Electron exited early rc={proc.returncode}"
            time.sleep(0.5)
        rc = proc.wait(timeout=SMOKE_S + 20)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert first and last and last[0] > first[0], "no Electron process seen"
    share = (last[1] - first[1]) / 1e7 / (last[0] - first[0])
    return {"rc": rc, "procs": procs, "peak": peak, "peak_private": peak_priv,
            "share": share, "seen": len(last[2])}


def test_live_shapes_use_the_budget_log_limits():
    """The two live shapes read B10 / B11 from server/al/budgetlog.py, the
    one table the budget log checker uses (no second copy to drift)."""
    assert MAX_PROCS == B10["processes"] == 2 and B11["processes"] == 3
    assert B10["private_mb"] == 120.0 and B11["ws_mb"] == 300.0
    assert RAM_BUDGET < 250 * MB  # decision 0002's overlay ceiling


@pytest.mark.slow
@LIVE_SMOKE
def test_live_overlay_smoke_within_budget(tmp_path):
    """Shape 1, overlay alone (B10 process count and private bytes; the
    decision 0002 working set; idle CPU)."""
    exe = _electron()
    if exe is None:
        pytest.skip("Electron not installed (npm ci --prefix app)")
    got = _run_smoke(exe, [str(ROOT / "app")], _smoke_env(tmp_path / "sidecar"))
    print(f"overlay smoke: {got['seen']} processes, peak summed working set "
          f"{got['peak'] / MB:.1f} MB, private {got['peak_private'] / MB:.1f} MB, "
          f"idle CPU {got['share'] * 100:.3f} percent of one core")
    assert got["rc"] == 0
    assert got["procs"] <= MAX_PROCS, f"{got['procs']} Electron processes"
    assert got["peak"] < RAM_BUDGET, f"summed working set {got['peak'] / MB:.1f} MB"
    assert got["peak_private"] < B10["private_mb"] * MB, (
        f"summed private {got['peak_private'] / MB:.1f} MB")
    assert got["share"] < CPU_BUDGET * fleet_test_guard.load_factor(), (
        f"{got['share'] * 100:.2f} percent")


@pytest.fixture
def test_core(tmp_path):
    """A real core and HTTP server on a leased test port with a tmp runtime,
    an empty log and a tmp AL_HOME whose data/token is this core's token."""
    import secrets
    import threading

    from server.al import hello
    from server.al.core import Core
    from server.al.http import serve
    from tc_live_util import lease_port

    rt = tmp_path / "rt"
    rt.mkdir()
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    home = tmp_path / "home"
    (home / "data").mkdir(parents=True)
    token = secrets.token_hex(24)
    (home / "data" / "token").write_text(token, encoding="ascii")
    (home / "data" / "local.json").write_text("{}", encoding="ascii")
    core = Core(runtime=rt, log_path=str(log), tail=False, config_path=rt / "local.json")
    port, release = lease_port()
    server = serve(core, token, port=port, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    try:
        # the client starts run.ps1 only when the core does not answer the
        # hello check: prove it does before the client starts
        assert hello.verify(port, token), "the test core did not answer the hello check"
        yield {"port": port, "home": home}
    finally:
        server.stop()
        release()
        core.close()


@pytest.mark.slow
@LIVE_SMOKE
def test_live_client_smoke_within_budget(tmp_path, test_core):
    """Shape 2, the client with the companion window open (B11): overlay
    window, companion window on the test core's dashboard, tray."""
    exe = _electron()
    if exe is None:
        pytest.skip("Electron not installed (npm ci --prefix app)")
    side = tmp_path / "sidecar"
    env = _smoke_env(side, AL_HOME=str(test_core["home"]), AL_PORT=str(test_core["port"]))
    got = _run_smoke(exe, [str(ROOT / "app"), "--client"], env)
    print(f"client smoke: {got['seen']} processes, peak summed working set "
          f"{got['peak'] / MB:.1f} MB, private {got['peak_private'] / MB:.1f} MB")
    logs = "".join(p.read_text(encoding="utf-8", errors="replace")
                   for p in sorted((side / "Logs").glob("overlay*.log")))
    assert "run.ps1 started" not in logs, "the client tried to start a core"
    assert "client: dashboard shown" in logs, "the companion never showed the dashboard"
    assert got["rc"] == 0
    assert got["procs"] <= B11["processes"], f"{got['procs']} Electron processes"
    assert got["peak"] < B11["ws_mb"] * MB, f"summed working set {got['peak'] / MB:.1f} MB"
