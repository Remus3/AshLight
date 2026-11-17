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

## Ops

- [ ] LOOP-ARM (build) Arm the lane loop as a scheduled task (every 15 min,
  IgnoreNew, hidden) after one supervised dry-run tick and one real tick on a
  trivial row. ACCEPT: task read back; first tick's progress file done.
- [ ] PUB-NAME (review) Manual poe2wiki check that "Ashlight" is not a GGG
  proper noun (decision 0001).
- [ ] OPERATOR: create the GitHub remote when the operator wants to publish
  (then lift the pre-push refusal in the same change, CI workflow with the
  kit's fleet_identity_guard.yml as a required check).
