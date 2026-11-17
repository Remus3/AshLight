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
  runtime.
- **Dashboard (`web/`)**: static HTML / CSS / vanilla JS served by the core,
  no framework, no CDN, styled only with the fleet kit design tokens
  (`ops/fleet_kit/tokens.css`). Opens in any browser or an Edge `--app`
  window on the second screen.
- **Overlay (`app/`)**: Electron, exact pin `45.3.3`. One frameless,
  transparent, always-on-top, click-through (`setIgnoreMouseEvents(true)`),
  non-focusable window; toggled by an Electron `globalShortcut`. It renders
  the same SSE feed and draws nothing when nothing changes.

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
  working set stays near 250 MB.

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
