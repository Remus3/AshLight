# AshLight ROADMAP

Open work only, as lane rows the loop (`tools/al_loop.py`) can dispatch.
Format: `- [ ] ID (lane) title. ACCEPT: ...`; `(priority)` jumps the queue.
Done rows are flipped to `[x]` by the merge and pruned at /done.

## Lane: build

- [ ] LIVE-1 (build) (priority) Run the core against the real Client.txt with
  the game running; confirm or correct every UNVERIFIED pattern in
  docs/research/0002-client-log.md; add the real (anonymized) lines as
  fixtures. ACCEPT: every event type seen live has a fixture and a passing test.
  BLOCKED (2026-11-16, adjudicated): operator physical act - PoE2 is installed
  but has never been launched (no logs/Client.txt). Unblocks when the operator
  plays once (or names the log path); then replace the HUD-WHISPER fixture
  whispers with real anonymized lines. The loop skips BLOCKED rows.
- [ ] OVL-BUDGET (build) BLOCKED with LIVE-1 (needs the game running). Measure the overlay idle and active (RSS of all
  Electron processes, CPU over 60 s) with the game running in Windowed
  Fullscreen; add the numbers to decision 0002. ACCEPT: within budget or a
  ruling on Tauri / native.
- [ ] OVL-FPS (build) BLOCKED with LIVE-1 (needs the game running). PresentMon capture: game alone vs game + overlay idle vs
  overlay updating. ACCEPT: average FPS loss under 1 percent, 1 percent lows
  unchanged within noise; numbers in decision 0002.
- [x] OVL-POS (build) Overlay layout editor on the dashboard (corner, scale,
  opacity), DPI-aware, multi-monitor; stored in config/local.json. ACCEPT:
  position survives restart; tests for the layout math.
- [ ] HUD-ACT (build) Leveling helpers: act / zone level table from an
  attributed build-time data snapshot (license checked first, research 0005);
  zone timer splits per act. ACCEPT: split table on the dashboard.
- [x] HUD-WHISPER (build) Trade whisper card on the overlay (item, price,
  stash position) with a quiet, non-flashing cue; dismissed from the
  dashboard. ACCEPT: fixture whisper renders; no input sent to the game.
- [ ] PRICE-1 (build) Price check: AshLight hotkey reads the clipboard ONCE
  (decision 0003), parses the item (research 0003), queries the trade2 API
  through one rate-limited queue that parses X-Rate-Limit headers
  dynamically; opt-in setting. ACCEPT: parser tests on fixtures; limiter
  tests; no request without the opt-in.

## Lane: data

- [ ] DATA-NINJA (data) poe.ninja PoE2 currency rates with ETag caching under
  the AL sidecar Cache, refresh at most hourly, attribution in the UI.
  ACCEPT: offline-cached rates shown; one request per hour max.
- [ ] DATA-LICENSE (data) License check for RePoE / repoe-fork PoE2 exports
  and poe2db / poe2wiki (CC BY-NC-SA) before any snapshot is bundled; record
  in docs/decisions. ACCEPT: decision file with the ruling.

## Lane: review

- [ ] UX-REVIEW (review) Glanceability review of dashboard and overlay
  (contrast, type scale, motion, phone width) against research 0008.
  ACCEPT: findings fixed or filed.
- [ ] RES-POLICY (review) Re-read GGG's developer docs and ToU each patch
  cycle; update research 0001 and the CLAUDE.md floor if anything changed.

## Theorycraft and item optimization (decision 0004, research 0010)

Phase 1 is stdlib-only file interop with Path of Building PoE2; phase 2
adds the optional pinned LuaJIT + PoB calc subprocess. Rows run in order.
Every row carries the minimal-interaction constraint (CLAUDE.md, decision
0004): no click the app can safely make for the user, state updates itself,
and the row's own dev / test steps run unattended. ZERO-CLICK states how.

- [ ] TC-CODE (build) PoB2 share-code codec in server/al: URL-safe base64 +
  zlib decode / encode (stdlib) to build XML, plus a typed build model
  (class, ascendancy, level, tree nodes, gear, skills, PoB's saved stats);
  paste-a-code API behind the token. ACCEPT: round-trip tests on fixture
  codes exported from PoB2 v0.23.1 (deflate framing confirmed); no network.
  ZERO-CLICK: a copied PoB code or share URL is taken on the AshLight
  hotkey press; the last build reloads on start.
- [ ] TC-VIEW (build) Build view on the dashboard: gear by slot, skills,
  key stats from the XML, tree summary; "copy code for PoB" export; link out
  to poe2db / wiki pages, no copied text. After TC-CODE. ACCEPT: fixture
  build renders at desktop and phone width; no GGG art bundled.
  ZERO-CLICK: the view follows the loaded build and the live character's
  level / zone from Client.txt with no refresh button.
- [ ] TC-JSON (build) Character JSON paste import (GGG reference Character
  / Item types, PoE2 fields skills, passives.specialisations, runeMods) into
  the build model. After TC-CODE. ACCEPT: fixture JSON maps to the same
  model as its PoB code; unknown fields ignored, not fatal.
  ZERO-CLICK: format (code, URL, JSON) auto-detected; no import dialog.
- [ ] TC-SNAP (data) Build-time snapshot tool: GGG poe2-skilltree-export
  plus the RePoE fork PoE2 mods / base_items / stats / stat_translations
  into the AL sidecar Cache with a manifest (URL, fetch date, sha256);
  attribution line in the UI. After DATA-LICENSE. ACCEPT: manifest written;
  no runtime fetch; tool idempotent.
  ZERO-CLICK: runs inside scripts/build.ps1, no manual step.
- [ ] TC-EVAL (build) Item evaluation phase 1: the clipboard item from the
  existing hotkey read (decision 0003, one read per press) scored by
  editable stat weights against the build's item in that slot; result on the
  dashboard and a compact overlay card. After TC-CODE, TC-SNAP. ACCEPT:
  fixture items scored; no second clipboard read; no input to the game.
  ZERO-CLICK: the one hotkey press shows price and upgrade verdict together.
- [ ] TC-UPGRADE (build) Upgrade search: weighted trade2 query ("type":
  "weight" stat group) from the local weights, complexity under 200, one
  search per user action, through the PRICE-1 limiter (X-Rate-Limit-*,
  Retry-After), opt-in, no POESESSID; prices shown with poe.ninja rates.
  After PRICE-1, TC-EVAL, DATA-NINJA. ACCEPT: query-builder tests; limiter
  shared, not duplicated; no request without the opt-in.
  ZERO-CLICK: once opted in, the same hotkey press that evaluates the item
  queues the search; results appear when the limiter allows, no extra click.
- [ ] TC-PIN (build) Phase 2 setup: tracked pin file (PoB-PoE2 tag, commit,
  archive sha256; LuaJIT version, sha256; no absolute paths); setup.ps1
  step fetches the PoB source archive to the sidecar Cache and builds or
  accepts LuaJIT into Build, hash-verified, off by default; THIRD-PARTY
  notices with PoB's MIT and component notices. ACCEPT: hash mismatch
  refuses; re-run is a no-op; test_sidecar_paths covers the new paths.
  ZERO-CLICK: one opt-in toggle; setup.ps1 does the rest unattended.
- [ ] TC-BRIDGE (build) Fresh stdio JSON bridge (our own Lua, no code from
  pob-mcp / pob2-mcp) driving the unmodified pinned PoB checkout via
  luajit.exe, plus a Python client in server/al: load build XML, set an item
  from item text, return outputs; timeout kill; core runs without it.
  After TC-PIN. ACCEPT: outputs on a fixture build match PoB GUI within 0.1
  percent; tests skip cleanly when the component is absent.
  ZERO-CLICK: the bridge starts on first need and restarts itself on a crash.
- [ ] TC-DELTA (build) PoB-backed evaluation: DPS and EHP delta of the
  clipboard item vs the equipped one, and per-mod weights from PoB deltas
  (offence and EHP) feeding TC-UPGRADE in place of hand weights. After
  TC-BRIDGE, TC-EVAL. ACCEPT: delta tests on fixtures; falls back to stat
  weights with a visible notice when the component is off.
  ZERO-CLICK: deltas recompute on item or build change, no Calculate button.
- [ ] TC-DRIFT (review) On each PoB-PoE2 release: run the bridge tests
  against the new tag, then move the pin in one commit, or hold it and
  record why. ACCEPT: pin moved or a dated hold note in decision 0004.
  ZERO-CLICK: a loop check spots the new tag and runs the tests unattended.
- [ ] TC-OAUTH-REG (review) OPERATOR act: apply to GGG for an AshLight
  public OAuth client (PKCE, loopback redirect in port block 8960-8979,
  scopes account:profile and account:characters) once GGG reopens
  registration. BLOCKED: registration closed ("currently unable to process
  new applications", research 0010).
- [ ] TC-IMPORT (build) Live character import with AshLight's own public
  client: PKCE sign-in, GET /character/poe2[/name], tokens in the OS
  credential store, refresh handled, into the build model. BLOCKED on
  TC-OAUTH-REG. ACCEPT: mocked-flow tests; no POESESSID; no undocumented
  endpoint. ZERO-CLICK: one sign-in ever; silent refresh after that.

## Game settings advisor (operator order 2026-11-16)

- [ ] GFX-ADVISOR (build) Optional dashboard panel: read this machine's
  hardware (CPU, GPU and VRAM, RAM, displays with resolution and refresh)
  through stdlib calls or Windows' own CIM query, and recommend PoE2
  graphics settings for it, Windowed Fullscreen required (decision 0002).
  RECOMMEND ONLY: the user applies them in game; AshLight never reads or
  writes the game's config files (ToS floor: no game file modification).
  ACCEPT: recommendation tests on fixture hardware profiles; no file under
  the game's folders opened; the panel says "apply in game".
  ZERO-CLICK: hardware read on first start and on change, panel ready with
  no button; nothing runs while the game is focused.

## Design and UX audit (operator order 2026-11-16)

Uses the design-reviewer agent (.claude/agents/design-reviewer.md) and the
design docs in docs/design/, both made by a separate agent.

- [x] DESIGN-AUDIT (review) Design / UX audit pass of the dashboard, overlay
  and the new theorycraft and advisor panels with the design-reviewer agent
  against docs/design/. ACCEPT: findings fixed or filed as ROADMAP rows;
  report in docs/design/. ZERO-CLICK: count the clicks each play-session
  flow needs and file a row for every one that can go. First pass done
  (ref e909dc8, docs/design/0002-first-audit.md): findings filed as the DS-*
  rows below; later passes (theorycraft and advisor panels) stay open.
- [ ] DESIGN-GATE (review) Make the design-reviewer pass a standing step for
  every row that touches web/ or app/ (review lane after build). After
  DESIGN-AUDIT. ACCEPT: lane prompt or loop rule names the step; one row
  reviewed through it. ZERO-CLICK: runs in the loop, no manual trigger.

Rows filed by the first audit (docs/design/0002-first-audit.md; S1 = worst).
Run after DESIGN-AUDIT, ahead of DESIGN-GATE.

- [ ] DS-OPACITY (build, S1) Raise the overlay opacity floor to 0.9 in
  server/al/layout.py, app/shared/layout.js and the dashboard slider; clamp
  older saved layouts; update layout tests. ACCEPT: no overlay text pair
  under 4.5:1 over a white scene at the floor (design 0001 5.2).
  ZERO-CLICK: saved layouts clamp themselves on load; no user action.
- [ ] DS-SCALE (build, S2) Raise the overlay scale floor to 0.95 in the same
  three places so 13px text never renders under 12px. ACCEPT: layout tests
  and a design 0001 O3 check. ZERO-CLICK: old layouts clamp on load.
- [ ] DS-NLM (build, S2) Rewrite summarize to the design 0001 section 9
  templates with honest defaults and no internal ids; add
  tests/test_summarize.py with one exact-output assert per template.
  ACCEPT: tests green. ZERO-CLICK: text is generated from events; nothing
  to configure.
- [ ] DS-TRADE-EXPIRE (build, S2) Trade requests expire 10 minutes after
  arrival; the dashboard states the rule; Dismiss stays. ACCEPT: expiry
  test with a fake clock. ZERO-CLICK: stale requests drop off by themselves.
- [ ] DS-HUD-AFK (build, S2) Show AFK / DND in the overlay status slot; add
  the field to the render gate and a test. ACCEPT: test green.
  ZERO-CLICK: follows the log's AFK / DND lines automatically.
- [ ] DS-HUD-EMPTY (build, S3) A sensible HUD before the first snapshot (no
  lone separator). ACCEPT: render test for the empty state.
  ZERO-CLICK: fills in by itself when the first snapshot arrives.
- [ ] DS-HUD-CLIP (build, S3) Clip the zone before adding "(HO)"; glanceable
  stash position text. ACCEPT: render test with a long zone name.
  ZERO-CLICK: purely display; no input.
- [ ] DS-REVIEW-HOOK (process) Run the design-reviewer agent on every change
  to web/, app/overlay/, app/shared/ or summarize before commit (lane prompt
  or pre-commit reminder). Folds into DESIGN-GATE. ACCEPT: rule named in the
  lane prompt or loop. ZERO-CLICK: runs in the loop, no manual trigger.
## Ops

- [ ] LOOP-ARM (build) Arm the lane loop as a scheduled task (every 15 min,
  IgnoreNew, hidden) after one supervised dry-run tick and one real tick on a
  trivial row. ACCEPT: task read back; first tick's progress file done.
- [x] CORE-DETACH (build) run.ps1 starts the core and overlay via WMI
  Win32_Process.Create (scripts/al_detach.ps1), outside the caller's tree and
  job; core.log records unhandled exceptions and native faults;
  ops/runtime/core.alive heartbeat (30 s, removed on clean exit) bounds the
  time of a silent kill. Cause of the 2026-11-16 21:57-22:12 death not
  proven: no crash event, no log line, Start-Process children survived probe
  sub-agent exits.
- [x] CORE-KEEPALIVE (build) run.ps1 starts a detached stdlib supervisor
  (server/al/keepalive.py, single-instance) that relaunches the core when its
  pid is gone with core.alive left behind, or when it hangs (heartbeat 90 s
  stale and /api/health failing); backoff 2/10/30/60/120 s, cap 5 per 15 min
  with a logged give-up. scripts/stop.ps1 writes ops/runtime/stop.request:
  the core exits cleanly and is not restarted (decision 0005). End-to-end
  test kills a real core on a tmp runtime and sees it back. Takes effect on
  the next run.ps1.
- [ ] CORE-AUTOSTART (build) Optional logon autostart of run.ps1 (scheduled
  task, hidden, opt-in recorded), filed by decision 0005 option C.
  ACCEPT: after a logon the core answers with no input. ZERO-CLICK.
- [ ] PUB-NAME (review) Manual poe2wiki check that "Ashlight" is not a GGG
  proper noun (decision 0001).
- [ ] OPERATOR: create the GitHub remote when the operator wants to publish
  (then lift the pre-push refusal in the same change, CI workflow with the
  kit's fleet_identity_guard.yml as a required check).
