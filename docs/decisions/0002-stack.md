# 0002 - Stack: Python stdlib core + browser dashboard + Electron overlay shell

Date: 2026-11-16. Inputs: `docs/research/0007-overlay-tech.md`,
`docs/research/0008-dashboard-tech.md`, `docs/research/0006-existing-tools.md`,
and the sibling trees' conventions (the operator's other game companions use a
Python stdlib local server on 127.0.0.1 plus an Electron dashboard and a
transparent click-through Electron overlay).

## Decision

- **Core (`server/`)**: Python 3.11+ standard library only. Client.txt tailer
  -> parser -> in-process event bus -> state store -> HTTP server on
  `127.0.0.1:8960` with Server-Sent Events. No third-party Python packages at
  runtime. Tests: `pytest` is the one allowed test dependency (dev only,
  never imported by `server/` or `tools/`); anything else a test uses is
  optional and guarded by ImportError (AUDIT-HYGIENE H3, 2026-11-17).
- **Dashboard (`web/`)**: static HTML / CSS / vanilla JS served by the core,
  no framework, no CDN, styled only with the fleet kit design tokens
  (`ops/fleet_kit/tokens.css`). Opens in any browser or an Edge `--app`
  window on the second screen.
- **Overlay (`app/`)**: Electron, exact pin `45.3.3`. One frameless,
  transparent, always-on-top, click-through (`setIgnoreMouseEvents(true)`),
  non-focusable window; toggled by an Electron `globalShortcut`. It renders
  the same SSE feed and draws nothing when nothing changes.
- Amended 2026-11-21 (REL-RUNTIME-SCRIPTS, plan units F-047, DEP-06):
  the stack note above describes a checkout (system Python 3.11+ from
  PATH, Electron from `npm ci`). An installed copy runs the hash-pinned
  private embeddable CPython and the unmodified Electron zip of decision
  0063 (installed runtimes). The scripts find either through
  `scripts/al_env.ps1` only (Get-AlPython, Get-AlPythonCmd, Get-AlPaths,
  Get-AlElectron: `<python> -m <module>` in a checkout,
  `<python> <payload>\boot.py <module>` in an install) and the client
  through `app/client/home.js` pythonCmd(); no script holds its own Python
  lookup (`tests/test_al_env.py`).

## Alternatives

- Node built-in http for the core (the dashboard research's pick): one runtime
  for overlay and server. Rejected for now: the core would then need Node for
  every user, and the fleet tooling, tests and lane gates are Python; the
  Python core runs and is tested with zero installs.
- Tauri 2 (WebView2) overlay: smaller footprint on paper (published idle-RAM
  figures conflict, 42 to 142 MB), but click-through and transparency on
  WebView2 are less documented and it adds a Rust toolchain. Second choice;
  re-measure in ROADMAP row OVL-BUDGET.
- WPF / WinUI 3 / Avalonia: WPF AllowsTransparency has a known render cost and
  WinUI transparency is limited; a second UI stack beside the web dashboard.
- Python Qt (PySide6) overlay: large wheel, LGPL packaging care, no shared UI
  code with the dashboard.
- Native Win32 / Rust (winit + wgpu): best footprint, highest build cost; kept
  as the fallback if the Electron overlay misses its budgets.

## Why

- Electron's click-through (`setIgnoreMouseEvents`), always-on-top levels and
  non-focusable windows are documented and proven by the two most-used PoE
  overlays (Awakened PoE Trade, Exiled Exchange 2).
- One HTML / CSS / JS UI for both surfaces; the overlay is optional - the core
  and dashboard work without Node or Electron installed.
- Matches the operator's sibling conventions (same shape, same gates).

## Budgets (tested in `tests/test_budgets.py` and the overlay smoke test)

- Core idle: under 1 percent of one core averaged over 10 s; RSS under 60 MB;
  tail of a 1,000-line burst parsed in under 50 ms.
- Overlay: idle CPU under 1 percent of one core, RAM (all Electron processes)
  under 250 MB, no frames rendered while no event arrives, hardware
  acceleration off (`app.disableHardwareAcceleration()`) so it never contends
  for the game's GPU queue.
- Game FPS: FPS before / after with the overlay idle and active, loss
  under 1 percent (ROADMAP row OVL-FPS). Method per decision 0006: no
  PresentMon / ETW tracing of the game; the in-game FPS display read by the
  human, or system-wide counters only.

## API token (API-TOKEN-HDR, 2026-11-16)

Every `/api/*` and `/events` request carries the per-start token
(`ops/runtime/token`) in one of three forms, checked in this order, the
first one given wins, constant-time compare (`server/al/http.py`
`_token_ok`):

1. header `X-AL-Token: <token>` (dashboard fetch, run.ps1, keepalive);
2. header `Authorization: Bearer <token>` (any standard HTTP client);
3. query `?token=<token>` - kept because EventSource (the SSE feed of the
   dashboard and the overlay) cannot set request headers.

The ROADMAP row assumed only `?token=` worked; X-AL-Token was already
accepted. Bearer was added because it does not weaken the floor: the Host
and Origin checks run before the token check for every form; a cross-origin
page cannot send either header (no CORS preflight is ever granted - OPTIONS
is refused, no `Access-Control-Allow-Headers`); browsers never attach a
Bearer header on their own, and a 401 carries no `WWW-Authenticate`, so no
credential prompt or cached Basic credentials come into play. The query
form never reaches a log (the request logger drops the query string) and
the dashboard keeps its token in the URL fragment, which is never sent.
Tests: `tests/test_api_token_hdr.py`, `tests/test_http_security.py`.
Alternatives: query only (rejected: needlessly puts the token in URLs for
fetch calls); header only (impossible: EventSource). Reverses if: a browser
starts attaching Authorization to cross-origin requests without preflight,
or the SSE feed moves to fetch streaming (then drop `?token=`).

## Reverses if

The Electron overlay misses the RAM or FPS budget on the operator's machine
(then Tauri 2, then native), or the core needs a library the stdlib cannot
replace.

## Measured 2026-11-16

First overlay smoke (app/ at Electron 45.3.3, `app.disableHardwareAcceleration()`,
core running with replayed fixture data, overlay connected to the SSE feed and
idle). Sampled with `Get-Process electron` (all processes summed) 6 s after
launch, over a 10 s window:

- Processes: 4 electron.exe.
- Working set, summed: 248.8 MB (shared pages counted once per process, so
  this overstates the real total); private bytes, summed: 121.2 MB.
  Budget 250 MB: inside, with no margin on the summed working set.
- CPU: 0.000 percent of one core over the 10 s idle window (0.44 CPU-s total
  including start-up). Budget 1 percent: met.
- Environment note: under the agent harness the Chromium GPU-process sandbox
  failed to launch (error_code=18, then "GPU process isn't usable"), so the
  measured run added `--disable-gpu-sandbox` on the command line. The shipped
  app sets no such switch; re-measure from a normal desktop launch
  (ROADMAP OVL-BUDGET), and add a dedicated RAM trim pass if the summed
  working set stays near 250 MB (done: UX-OVL-RAM, below).

## Measured 2026-11-16 (OVL-BUDGET, game running)

Live run on the operator's machine, PoE2 open at CHARACTER SELECT (a light
scene; GPU already at 99-100 percent per nvidia-smi because the menu renders
uncapped). Overlay started detached exactly as scripts\run.ps1 does
(scripts\al_detach.ps1, WMI). Idle: the feed was live but no events arrived.

- Start-up: the shipped build exited at once ("GPU process launch failed:
  error_code=18" six times, then "GPU process isn't usable. Goodbye.") also
  when started detached by WMI, so this is not only an agent-session effect.
  Fix: `app.commandLine.appendSwitch("in-process-gpu")` in app/main.js
  (acceleration stays off; the software compositor runs in the browser
  process; renderer sandbox unchanged). The overlay then starts and stays up.
- Processes: 3 electron.exe (was 4; no separate GPU process).
- Working set, summed: 201.7 to 204.4 MB over 60 s; private bytes, summed:
  107.4 to 110.2 MB. Budget 250 MB: met (about 46 MB margin).
- CPU: 0.000 CPU-s over a 60.9 s window = 0.000 percent of one core.
  Budget 1 percent: met.
- Overlay's own GPU 3D-engine utilisation (its own pids): 0.000 percent in
  all 12 samples.

Game FPS proxy (decision 0006: system-wide counters only, 5 s samples):

- Total 3D-engine utilisation, overlay off: mean 52.5 percent (12 samples,
  range 49.6 to 66.1); overlay on and idle: mean 53.3 percent (12 samples,
  range 50.8 to 55.7). Difference +0.8 points, inside the off-run spread.
- nvidia-smi GPU utilisation 99-100 percent in both runs.
- Limitation: a utilisation proxy at a saturated GPU cannot show an FPS
  loss; it shows only that the overlay adds no measurable GPU work.
  STILL NEEDED: an in-map run (same map, overlay off vs on idle vs on
  updating), reading the game's own FPS display, Windowed Fullscreen.

## Measured 2026-11-17 (TEST-OVL, automated smoke)

`AL_OVERLAY_SMOKE=1 python -m pytest tests/test_overlay_smoke.py` (isolated
profile, no core, overlay idle): 2 electron.exe processes, peak summed
working set 142.6 MB, idle CPU 0.000 percent of one core over 7 s, rc 0.
Whole-core idle (tailer + HTTP + 2 SSE streams, tests/test_budgets.py):
0.000 percent of one core over 3 s. In-map FPS (OVL-FPS) still needs the
operator's play session.

## Measured 2026-11-17 (UX-OVL-RAM, RAM trim)

Real overlay from app/ against a test core on a spare port in the block
(own runtime and sidecar dirs, scratch Client.txt fed by
`tools/synth_client.py`); per-process working set and private bytes read
with `GetProcessMemoryInfo` over the started overlay's own process tree
every 2 s: 60 s idle, then 30 s with 150 log events (one SSE push each,
5 per second).

- Before: 3 processes (browser, renderer, network-service utility).
  Working set summed 245.4 to 248.0 MB idle, up to 252.2 MB in the burst
  (over the 250 MB budget); private 107.9 to 113.1 MB. The utility
  process alone: 67 MB working set, 12 MB private (mostly shared
  electron.exe image pages counted again).
- Change: `app.commandLine.appendSwitch("enable-features",
  "NetworkServiceInProcess2")` in app/main.js (the feature name carries
  the "2"; the unsuffixed name is ignored, measured). The network
  service, used only for the 127.0.0.1 SSE feed, runs in the browser
  process; the renderer sandbox, acceleration off and in-process GPU are
  unchanged.
- After: 2 processes. Working set summed 179.1 to 181.4 MB idle, up to
  185.7 MB in the burst; private 95.9 to 102.0 MB. Headroom 64 MB at the
  186 MB burst peak (26 percent of 250; 69 MB idle); target of 20
  percent met.
- Tried and dropped (no gain beyond 3 MB run-to-run noise):
  `--js-flags` (max-semi-space-size=1, max-old-space-size=64, jitless,
  lite-mode), `--disable-software-rasterizer`, `--disable-features` for
  spare renderer, Translate, MediaRouter, BackForwardCache,
  OptimizationHints, and background networking / component update. The
  renderer page was already lean: three small scripts, system fonts, no
  images, and only the latest snapshot kept (no event history).
- Smoke test: `tests/test_overlay_smoke.py` now samples the started
  overlay's process tree (the old profile match missed the browser
  process) and asserts at most 2 processes and a summed working set
  under 215 MB (about 15 percent over the 186 MB peak); this budget's
  250 MB stays the decision's ceiling. Live smoke: 2 processes, peak
  181.3 MB.
- Reverses if: the in-process network service crashes the overlay, or
  Electron drops the feature (then the utility process comes back and
  the smoke test fails on the process count).

## Test plugins (Q-16, 2026-11-18)

Clarified (ruling Q-16; research 0049 R3, R7 and its 2026-11-19 addendum,
verdict "XDIST: cleared"; TEST-SUITE-RUNNER):

- `pytest` stays the one test dependency. An optional dev-only test plugin
  may speed the suite: `pytest-xdist` (3.8.0, with `execnet` 2.1.2), pinned
  exactly with `--hash` lines in `requirements-dev.txt`, installed by hand.
  No AshLight script runs pip; `setup.ps1` and `build.ps1` never install
  it. `server/`, `tools/` and app code never import it (`tools/suite_run.py`
  only asks `importlib.util.find_spec` whether it is present).
- `tools/suite_run.py` is the one whole-suite command, always started under
  the kit suite gate (`python ops/fleet_kit/fleet_suite_gate.py run --owner
  <id> -- python tools/suite_run.py`; `suite_run.py argv --owner <id>`
  prints it) and refused without the gate's `FLEET_SUITE_SLOT`. Phase 1 runs
  every test except `timing` on 4 workers with `--dist loadgroup` when xdist
  is importable, serially otherwise (the serial path stays the default on a
  machine without the plugin); phase 2 runs the `timing` tests alone,
  serially, after phase 1. The exit code is the worst phase's; children run
  at below-normal priority. Callers pass no flag.
- Alternatives: stdlib file shards (4 pytest processes, largest-first; the
  plan if xdist had been rejected, more code for the same pins); the loop's
  `-n 8 --dist loadfile` (two gate slots share the box, 4 leaves room and
  loadgroup keeps the calc and fixed-port groups together); serial only
  (237 s and more, past lane eligibility).
- Reverses if: the diagnosed runs show xdist caused flakes or lost workers,
  or the operator rules tests must be stdlib-only.
