# Overlay technology on Windows

Scope: transparent, always-on-top, click-through in-game overlay for Path of Exile 2 (Steam, Windows 10/11) that must not cost FPS. Research date 2026-11-16. Items not confirmed by a source are marked UNVERIFIED.

## Windows mechanics

- WS_EX_LAYERED: marks the window as a layered window; Windows 8 and later allow it on top-level and child windows, and it cannot be combined with class styles CS_OWNDC or CS_CLASSDC. https://learn.microsoft.com/en-us/windows/win32/winmsg/extended-window-styles (accessed 2026-11-16)
- WS_EX_TRANSPARENT: per Microsoft's wording it only means "do not paint until sibling windows beneath have painted"; it is not by itself documented as click-through, and Microsoft points to SetWindowRgn for transparency without those restrictions. https://learn.microsoft.com/en-us/windows/win32/winmsg/extended-window-styles (accessed 2026-11-16)
- Raymond Chen notes that different hit-testing functions use different rules for whether a click passes through and that WS_EX_TRANSPARENT affects some of them; a layered window may work better. https://devblogs.microsoft.com/oldnewthing/20121217-00/?p=5823 (accessed 2026-11-16)
- In practice the click-through recipe is WS_EX_LAYERED plus WS_EX_TRANSPARENT; it makes the whole window click-through, so interactive widgets on the same window stop receiving clicks. Partial click-through needs hit-test overriding or a second window. https://users.rust-lang.org/t/possible-to-create-a-full-screen-overlay-that-catches-clicks-but-does-not-come-into-focus/75567 (accessed 2026-11-16)
- WS_EX_TOPMOST: window stays above all non-topmost windows even when deactivated; set or cleared with SetWindowPos. https://learn.microsoft.com/en-us/windows/win32/winmsg/extended-window-styles (accessed 2026-11-16)
- WS_EX_TOOLWINDOW: no taskbar button and no Alt+Tab entry. https://learn.microsoft.com/en-us/windows/win32/winmsg/extended-window-styles (accessed 2026-11-16)
- WS_EX_NOACTIVATE: clicking the window does not make it the foreground window, and the system does not bring it to the foreground when another window is closed or minimized; hidden from taskbar by default. This is the focus-stealing guard for any overlay region that must accept clicks. https://learn.microsoft.com/en-us/windows/win32/winmsg/extended-window-styles (accessed 2026-11-16)
- Layered windows are hardware accelerated on WDDM systems per WPF docs, but a 2008-era Microsoft blog measured simple 2D layered content as slower on the hardware path on discrete GPUs, and Nick Kramer noted layering costs extra GDI coordination. Old and not PoE-specific; direction only. https://learn.microsoft.com/en-gb/archive/blogs/seema/layered-windows-sw-is-sometimes-faster-than-hw (accessed 2026-11-16) and https://learn.microsoft.com/it-it/archive/blogs/nickkramer/favorite-features-in-the-june-ctp (accessed 2026-11-16)

## Display modes, DWM and why exclusive fullscreen blocks overlays

- Microsoft describes Fullscreen Exclusive (FSE) as the game owning the display; overlays must then intercept the rendering process, which can cause performance regressions, instability and anti-cheat issues. In borderless windowed, DWM still composites, so a separate window can sit on top. https://devblogs.microsoft.com/directx/demystifying-full-screen-optimizations/ (accessed 2026-11-16)
- Windows 10+ Fullscreen Optimizations run a legacy exclusive-fullscreen game as an optimized borderless window; when something like Game Bar draws over it, DWM takes control back to composite it, with slight overhead. https://devblogs.microsoft.com/directx/demystifying-full-screen-optimizations/ (accessed 2026-11-16)
- Flip-model games can get Direct Flip / Independent Flip, bypassing desktop composition "in the same way that exclusive fullscreen does"; other desktop content on top makes DWM either fall back to composed mode, reverse-compose, or keep independent flip via a multi-plane overlay (MPO) hardware plane. https://learn.microsoft.com/en-us/windows/win32/direct3ddxgi/for-best-performance--use-dxgi-flip-model (accessed 2026-11-16)
- Microsoft recommends checking which mode is in use with PresentMon. https://learn.microsoft.com/en-us/windows/win32/direct3ddxgi/for-best-performance--use-dxgi-flip-model (accessed 2026-11-16)
- Overlay impact on flip mode is mostly community evidence: one Blur Busters user reported an overlay app forcing composed flip with extra latency, restored to independent flip when the overlay closed; claims about Discord and Game Bar there are speculation. MPO behaviour varies by GPU and driver. No official Microsoft statement found: UNVERIFIED, test. https://forums.blurbusters.com/viewtopic.php?p=124286 and https://forums.blurbusters.com/viewtopic.php?p=111995 (accessed 2026-11-16)
- Overwolf (commercial overlay platform) documents the same split: ow-electron captures games only in borderless fullscreen; in non-borderless fullscreen "the capture will not work correctly". https://dev.overwolf.com/ow-electron/guides/product-guidelines/app-screen-behavior/in-game-overlays (accessed 2026-11-16) Its release notes say newer builds can show an overlay over Fullscreen Exclusive games but with no mouse or keyboard interaction. https://support.overwolf.com/en/support/solutions/articles/9000199444-overwolf-release-notes (accessed 2026-11-16)

## PoE2 display modes

- GGG forum thread: the client offers three modes, "Windowed", "Fullscreen" and "Windowed Fullscreen" (the last can be called a borderless window). https://www.pathofexile.com/forum/view-thread/3659441 (accessed 2026-11-16) (from a search-result summary; the thread also reports resolution quirks)
- Whether PoE2 "Fullscreen" is true exclusive or handled by Windows Fullscreen Optimizations: UNVERIFIED. No official GGG page found; only community guides, some recommending Windowed Fullscreen for smoother Alt+Tab. https://bo3.gg/games/articles/best-pc-settings-for-path-of-exile-2 (accessed 2026-11-16)
- Design consequence (proposal): support Windowed Fullscreen as the guaranteed mode; show a one-time hint to switch when "Fullscreen" is detected (overlay visibility there is UNVERIFIED).

## DPI and multi-monitor

- Default desktop apps are DPI unaware and bitmap-stretched (blurry); declare Per-Monitor V2 (Windows 10 1703+) and handle WM_DPICHANGED using the suggested rectangle. https://learn.microsoft.com/en-us/windows/win32/hidpi/high-dpi-desktop-application-development-on-windows (accessed 2026-11-16)
- Per-Monitor V2 apps see raw pixels of each display and are never bitmap scaled, so the overlay must read the game window rect in physical pixels on the monitor the game occupies; the dashboard monitor may have a different scale factor. Same source (accessed 2026-11-16)

## Candidates

### Electron

- Current stable: 45.3.3 (Chromium 156.0.8078.100, Node 24.22.3), released 2026-11-14. https://releases.electronjs.org/ (accessed 2026-11-16)
- Click-through: win.setIgnoreMouseEvents(ignore, {forward: true}) forwards mouse-move so mouseleave still fires (macOS and Windows); on Windows forward stops working while an elevated window such as Task Manager is focused (UIPI); workaround is running elevated or UIAccess. https://www.electronjs.org/docs/latest/api/browser-window (accessed 2026-11-16)
- Always on top: setAlwaysOnTop(flag, level); levels from pop-up-menu upward sit above the taskbar; screen-saver is a listed level. Same source (accessed 2026-11-16)
- Focus: setFocusable(false) and showInactive() exist on Windows. Same source (accessed 2026-11-16)
- Transparency on Windows: transparent windows do not work with DWM disabled. https://ayakael.net/mirrors/electron/commit/c3a8ad254a4dd3b2135d24638f3526ba3819bc45 (accessed 2026-11-16) An Electron commit made window contents opaque in some cases to cut DWM GPU usage, evidence that transparency raises compositor cost. https://ayakael.net/mirrors/electron/commit/f943b8c940386f196a10cf490ad9122d83ec59f5 (accessed 2026-11-16)
- Idle footprint: published comparisons vary widely. One 2026 test: 168 MB Electron 34 single window vs 42 MB Tauri; another Windows 11 test 149 MB vs 142 MB; typical blog range 150-300 MB. Secondary sources of unknown rigor; measure our own build. https://tech-insider.org/tauri-vs-electron-desktop-app-framework-2026/ and https://betterstack.com/community/guides/scaling-nodejs/tauri-vs-electron-vs-deno-vs-electrobun/ (accessed 2026-11-16)
- GPU: a Claude Code issue reports an Electron window pegging an Intel iGPU on Windows, fixed only by disabling GPU compositing (--disable-gpu was heavier-handed). Single anecdote. https://github.com/anthropics/claude-code/issues/56805 (accessed 2026-11-16) Whether app.disableHardwareAcceleration() keeps per-pixel transparency on Windows: UNVERIFIED, test (see https://github.com/electron/electron/issues/40515 (accessed 2026-11-16)).
- Packaging: unsigned Windows apps trigger warnings; EV signing is now needed and Azure Artifact Signing is the cheapest option but limited to certain countries. https://www.electronjs.org/docs/latest/tutorial/code-signing (accessed 2026-11-16) Installer size and AV false-positive rates for Electron: UNVERIFIED (no measurement found).

### electron-overlay-window (SnosMe)

- Finds the target window by title, keeps the overlay position and size in sync with it and emits lifecycle events; Windows 7 to 10 and Linux X11; one overlay window only; target must be a top-level window; license MIT. https://github.com/SnosMe/electron-overlay-window (accessed 2026-11-16)
- That the Windows backend uses SetWinEventHook: UNVERIFIED (README fetched did not state the mechanism). Windows 11 support is not stated in the README (UNVERIFIED).
- Exiled Exchange 2 (PoE2 fork of Awakened PoE Trade) is a price-check overlay; setup changes windowTitle in config.json to "Path of Exile 2", implying title-based tracking; acknowledges libuiohook. https://github.com/Kvan7/Exiled-Exchange-2 (accessed 2026-11-16) Its license and framework were not stated on the page fetched (UNVERIFIED).
- Policy context: GGG says it does not encourage third-party tools and cannot guarantee any stays allowed; the ToS forbids modifying the client or its data, so the safe design is read-only (no injection, no memory reads, no hooks into the game process). https://www.pathofexile.com/legal/terms-of-use-and-privacy-policy (accessed 2026-11-16) and https://www.poeoverlay.com/faq (accessed 2026-11-16) (developer claim only)

### Tauri 2 (WebView2)

- Window API has setAlwaysOnTop (needs capability core:window:allow-set-always-on-top, not in the default set); setBackgroundColor on Windows ignores the alpha channel. https://v2.tauri.app/reference/javascript/api/namespacewindow/ (accessed 2026-11-16) Click-through is set_ignore_cursor_events (Rust) / setIgnoreCursorEvents (JS); its doc text was not read: UNVERIFIED details.
- Known issues: transparent windows lose shadows/borders until resized on Windows 11; shadow persists despite settings in undecorated transparent windows; resize flicker. https://github.com/tauri-apps/tauri/issues/1564 (accessed 2026-11-16) A fully click-through window also stops receiving OS drag-enter events. https://dev.to/devrayat000/building-a-transparent-drag-and-drop-shelf-for-windows-with-tauri-the-engineering-war-stories-3c8c (accessed 2026-11-16)
- WebView2 runs browser, renderer(s), GPU and utility processes, so RAM is not one small process. https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/process-model (accessed 2026-11-16)
- Binary size: docs say "very small binaries" by default and list size flags (LTO, opt-level, panic abort, strip); no number given. https://v2.tauri.app/concept/size/ (accessed 2026-11-16)

### .NET WPF, WinUI 3, Avalonia

- WPF: transparent window needs WindowStyle=None, AllowsTransparency=true, Background=Transparent (layered window, fixed at construction). https://learn.microsoft.com/en-my/archive/blogs/dwayneneed/transparent-windows-in-wpf (accessed 2026-11-16) AllowsTransparency perf cost on current .NET and GPUs: UNVERIFIED, measure (historic data: https://learn.microsoft.com/en-gb/archive/blogs/seema/layered-windows-sw-is-sometimes-faster-than-hw (accessed 2026-11-16)).
- WinUI 3: no first-class transparent XAML window; the Reactor windowing docs say XAML composition does not compose cleanly with classic WS_EX_LAYERED rendering, and a Microsoft Q&A thread reports white or framed backgrounds. https://microsoft.github.io/microsoft-ui-reactor/latest/windowing-advanced/ and https://learn.microsoft.com/en-us/answers/questions/1418063/(winui3)-semi-transparent-window-click-through-win (accessed 2026-11-16) Not recommended for the overlay.
- Avalonia: TransparencyLevelHint="Transparent" plus Background={x:Null} gives click-through in transparent areas on Windows (Background="Transparent" still captures input); Windows is the only platform with full transparency support. https://docs.avaloniaui.net/docs/how-to/window-how-to and https://docs.avaloniaui.net/docs/platform-specific-guides/windows (accessed 2026-11-16)

### Python (PySide6/Qt, tkinter)

- Qt: common recipe is Qt::FramelessWindowHint | Qt::WindowStaysOnTopHint | Qt::WindowTransparentForInput plus WA_TranslucentBackground; known bugs: translucent frameless tool window with QQuickWidget not shown on Windows (QTBUG-43854), translucency failing for native child widgets (QTBUG-105537), toggling WindowTransparentForInput can hide the window. https://forum.qt.io/post/664778 and https://bugreports.qt-project.org/browse/QTBUG-43854 (accessed 2026-11-16) Footprint: UNVERIFIED, measure.
- tkinter: attributes('-transparentcolor', c, '-topmost', 1) gives a transparent topmost window; full click-through needs ctypes WS_EX_LAYERED|WS_EX_TRANSPARENT and breaks interactive controls; partial click-through needs a two-window design. https://kaweah.freedombox.rocks/kiwix/content/stackoverflow.com_en_all_2023-11/questions/61114145/tying-to-set-non-interactable-click-through-overlay-with-tkinter (accessed 2026-11-16) Prototype only (my judgment; footprint UNVERIFIED).

### Native Win32 / Direct2D, Rust (winit + wgpu / egui)

- Native layered window (UpdateLayeredWindow) or a DirectComposition swap chain is the minimum-overhead path; cost is writing hit-testing, DPI handling and window tracking yourself (mechanics per the Microsoft pages above).
- winit: with_transparent(true), with_decorations(false), set_cursor_hittest(false) for full click-through; wgpu alpha mode and surface format on Windows must be tested (a Qt-forum report notes black backgrounds on Windows). https://docs.rs/egui-winit (accessed 2026-11-16) and https://lib.rs/crates/egui_overlay (accessed 2026-11-16) egui_overlay is a reference crate; maintenance looked light (UNVERIFIED).
- Rust gives the smallest idle RAM (UNVERIFIED, no measurement) but the dashboard UI would be rebuilt in a native toolkit if the dashboard is HTML.

## How to measure FPS impact

- PresentMon (Intel, MIT): captures CPU/GPU/display frame durations and latencies for DirectX, OpenGL, Vulkan; console app can target `--process_name`, needs Performance Log Users membership; with HAGS enabled GPU timing metrics may read high. https://github.com/GameTechDev/PresentMon (accessed 2026-11-16)
- CapFrameX: frametime capture and analysis built on PresentMon; overlay via RTSS. https://www.capframex.com/ (accessed 2026-11-16)
- Protocol (proposal, not from a source): fixed PoE2 scene, 3 runs of 120 s each for baseline, overlay hidden-but-running, overlay visible and updating; compare average FPS, 1% and 0.1% lows, and the PresentMode column (Independent Flip vs Composed Flip) from PresentMon. Fail if present mode changes or 1% low drops more than 1 percent.
- Budgets published by others for idle overlays: none found; the budgets below are proposals.

## Proposed budgets

- Idle CPU under 1 percent of one core (60 s window, game idle in hideout).
- Working set RAM under 150 MB for the whole overlay process tree (Electron needs tuning to hit this; Tauri or native should).
- Zero GPU work when idle: no requestAnimationFrame loops, CSS animations paused, repaint only on data change; 0 frames rendered when nothing changes.
- At most 10 repaints per second when active; no per-frame JS timers.
- Overlay never takes focus (NOACTIVATE or focusable false) and never changes the game's present mode.

## Recommendation

1. Electron (pinned stable 45.x): frameless transparent window, setIgnoreMouseEvents(true, {forward:true}), screen-saver always-on-top level, setFocusable(false), and a title-tracking helper in the style of electron-overlay-window (MIT; use as a dependency, never copied). Reason: documented click-through with forwarding, mature precedent in PoE tools, one HTML/JS stack shared with the dashboard. Risk: footprint and GPU idle cost; mitigate with demand-driven rendering and test disableHardwareAcceleration.
2. Tauri 2 as the lighter alternative if Electron misses the RAM or GPU budget; risk is WebView2 transparency quirks and thinner overlay precedent.
3. Native Win32 + Direct2D or Rust winit/wgpu only if both webview stacks fail the FPS test.
4. Avoid WinUI 3 and tkinter; Avalonia, WPF and Qt are viable but add a second UI stack.

What to test first: (a) PresentMode stays Independent Flip with overlay shown, on Windows 10 and 11, MPO on and off; (b) behaviour in PoE2 Fullscreen vs Windowed Fullscreen; (c) idle CPU/RAM/GPU per candidate against the budgets; (d) mixed DPI (100 percent game monitor, 150 percent second monitor); (e) elevated-window case for forwarded mouse events; (f) AV scan and SmartScreen on the unsigned installer.

## Sources

- https://learn.microsoft.com/en-us/windows/win32/winmsg/extended-window-styles
- https://devblogs.microsoft.com/oldnewthing/20121217-00/?p=5823
- https://devblogs.microsoft.com/directx/demystifying-full-screen-optimizations/
- https://learn.microsoft.com/en-us/windows/win32/direct3ddxgi/for-best-performance--use-dxgi-flip-model
- https://learn.microsoft.com/en-us/windows/win32/hidpi/high-dpi-desktop-application-development-on-windows
- https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/process-model
- https://learn.microsoft.com/en-gb/archive/blogs/seema/layered-windows-sw-is-sometimes-faster-than-hw
- https://learn.microsoft.com/en-my/archive/blogs/dwayneneed/transparent-windows-in-wpf
- https://learn.microsoft.com/it-it/archive/blogs/nickkramer/favorite-features-in-the-june-ctp
- https://learn.microsoft.com/en-us/answers/questions/1418063/(winui3)-semi-transparent-window-click-through-win
- https://microsoft.github.io/microsoft-ui-reactor/latest/windowing-advanced/
- https://www.electronjs.org/docs/latest/api/browser-window
- https://www.electronjs.org/docs/latest/tutorial/code-signing
- https://releases.electronjs.org/
- https://github.com/electron/electron/issues/40515
- https://ayakael.net/mirrors/electron/commit/c3a8ad254a4dd3b2135d24638f3526ba3819bc45
- https://ayakael.net/mirrors/electron/commit/f943b8c940386f196a10cf490ad9122d83ec59f5
- https://github.com/anthropics/claude-code/issues/56805
- https://github.com/SnosMe/electron-overlay-window
- https://github.com/Kvan7/Exiled-Exchange-2
- https://v2.tauri.app/reference/javascript/api/namespacewindow/
- https://v2.tauri.app/concept/size/
- https://github.com/tauri-apps/tauri/issues/1564
- https://dev.to/devrayat000/building-a-transparent-drag-and-drop-shelf-for-windows-with-tauri-the-engineering-war-stories-3c8c
- https://docs.avaloniaui.net/docs/how-to/window-how-to
- https://docs.avaloniaui.net/docs/platform-specific-guides/windows
- https://forum.qt.io/post/664778
- https://bugreports.qt-project.org/browse/QTBUG-43854
- https://kaweah.freedombox.rocks/kiwix/content/stackoverflow.com_en_all_2023-11/questions/61114145/tying-to-set-non-interactable-click-through-overlay-with-tkinter
- https://users.rust-lang.org/t/possible-to-create-a-full-screen-overlay-that-catches-clicks-but-does-not-come-into-focus/75567
- https://docs.rs/egui-winit
- https://lib.rs/crates/egui_overlay
- https://github.com/GameTechDev/PresentMon
- https://www.capframex.com/
- https://forums.blurbusters.com/viewtopic.php?p=124286
- https://forums.blurbusters.com/viewtopic.php?p=111995
- https://dev.overwolf.com/ow-electron/guides/product-guidelines/app-screen-behavior/in-game-overlays
- https://support.overwolf.com/en/support/solutions/articles/9000199444-overwolf-release-notes
- https://www.pathofexile.com/forum/view-thread/3659441
- https://bo3.gg/games/articles/best-pc-settings-for-path-of-exile-2
- https://www.pathofexile.com/legal/terms-of-use-and-privacy-policy
- https://www.poeoverlay.com/faq
- https://tech-insider.org/tauri-vs-electron-desktop-app-framework-2026/
- https://betterstack.com/community/guides/scaling-nodejs/tauri-vs-electron-vs-deno-vs-electrobun/
