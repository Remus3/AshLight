# Decisions

One file per decision: `NNNN-<topic>.md` (decision, alternatives, why,
reverses if). Numbers 0047 to 0076 are reserved for the packages of
docs/plan/packages.json (docs/plan/07, Reserved decision numbers); a
package uses the number in its new_files entry. 0077 to 0087
are taken. Numbers are reserved in the plan before a wave starts.
Numbers are reserved per package in docs/plan/packages.json before a
wave starts; the wave integrator adds the index line. 0035 stays unused.

- 0087: CodeQL default setup on for python, javascript-typescript and
  actions; GitHub-managed, no workflow, not a required check.
- 0086: RUN-DATAAGE-SHARED-PARSE: the data age watch shares the zone
  table's parse; its refute-round timing gate failures stand as load.
- 0085: PLAY-TD-21C-HISTORY-MOVE: its budget gate failures are load
  flakes, no budget number moves.
- 0084: LP-B refute findings: timing-gate failures under load stand as
  unrelated to the row (no ceiling moved, no rerun plugin).
- 0083: item info popover data: local caches only, unknown fields
  omitted, no drop rates or vendor / disenchant data, PoB Source lines
  under sha256 pins (amends 0037), a "More on poe2db" link on click;
  amended 2026-11-19: Apache-2.0 kept, link only until a source permits
  app use (operator requests 2026-11-19).
- 0082: UI: item info popover, header text (sr-only h1) and version
  line, collapsible cards on Build and items and Run; amended 2026-11-19:
  collapse state in the core, buttons in the client window only
  (operator requests 2026-11-19).
- 0081: Kindler build generator: authored archetype templates scored by
  Path of Building on the Generate click, at most 12 candidates in 60 s,
  up to 6 tabs (amends 0004); amended 2026-11-19: tab move / rename /
  close, deterministic ranking, stages from levelling to maps, follow
  Play guidance (operator requests 2026-11-19).
- 0080: CI timing tolerance (AL_CI=1 in ci.yml only: timing budgets
  skip, test waits 3x, one CDP page-live retry) and the core's listen
  backlog of 128 (GP-09 ruling).
- 0079: go-public gate 6: binary blobs 500 KB, text blobs 2 MB,
  tools/blob_gate.py; no history rewrite (GP-09 ruling).
- 0078: ultraplan rulings ledger: Q-01 to Q-28, A-01 to A-03, the
  close-out LE rulings and R1 to R6 of the close-out 2, each with its
  default in force (ULTRAPLAN).
- 0077: ultraplan execution model: waves in sessions, per-wave
  integrator, loop tail, HALT removal point; 0047 to 0076 are reserved
  for packages in docs/plan/packages.json (ULTRAPLAN).
- 0075: Fixed cockpit Play, four tabs, dark by default (PLAY-TD-23-RECORDS)
- 0074: Player notes: one bounded file, a token route and the your-note row (PLAY-F-186A)
- 0076: CI issue protocol - labelled key issues, bot account only, failover to the dev loop (CI-WATCH) (docs/decisions/0076-ci-issue-protocol.md)
- 0073: Versioning and release trigger (plan 05 D4) (docs/decisions/0073-versioning-release-trigger.md)
- 0072: poe.ninja cadence tiers and the release polling gate (GO-PUBLIC-NINJA) (docs/decisions/0072-poe-ninja-cadence-and-release-gate.md)
- 0071: parse ledger: per-pattern counts and masked log shapes under their
  own consent line beside the Client.txt opt-in (RUN-METRICS-SITES).
- 0070: Electron upgrade policy - line, waiting periods, advisory fast path, end-of-life rule (ELECTRON-WATCH).
- 0069: upstream watcher frame (docs/decisions/0069-upstream-watch-frame.md): one tool, one state file, metadata-only sources behind the web-data gate, templated rows (AUTO-05).
- 0068: Electron and npm supply chain (docs/decisions/0068-electron-npm-supply-chain.md)
  (OVL-ELECTRON-SETUP).
- 0067: Observability records (docs/decisions/0067-observability-records.md): AshLight
  records only its own behaviour (counters behind /api/debug, budget log, typed
  event log, report on click); no game process, no Client.txt text, nothing
  uploaded (RUN-METRICS-CORE).
- 0066: Uninstall consent (plan 05 D6) (docs/decisions/0066-uninstall-consent.md)
  (DEP-10).
- 0065: Update policy (plan 05 D5, ruling Q-21; amends 0013 and the 0018
  item 6 wording) (docs/decisions/0065-update-policy.md) (DEP-16).
- 0064: Release artifact and tool (plan 05 D3, ruling Q-22)
  (docs/decisions/0064-release-artifact.md) (DEP-08).
- 0063: Installed-copy runtimes and launch (plan 05 D2, ruling Q-20; amends
  0002, 0010, 0041 point 8; holds the licence record for fetching CPython
  and Electron) (docs/decisions/0063-installed-runtimes.md)
  (REL-RUNTIME-PINS).
- 0062: Changelog (plan 05 D7) (docs/decisions/0062-changelog.md)
  (DEP-04).
- 0061: Electron shell guards (docs/decisions/0061-electron-shell-guards.md)
  (OVL-SHELL-GUARDS).
- 0060: wave gate policy - named-file subset per package, one whole suite
  per merge batch (Q-17).
- 0059: installed-mode home and layout (plan 05 D1, ruling Q-19)
  (DEP-05).
- 0058: hotkeys: effective keys, rebind in the app, self-healing
  fallback (OVL-KEYS-CLIENT).
- 0057: keep-or-vendor levelling rules: own table, hot reloaded, used
  only with no build (TC-CAMPAIGN-KEEP).
- 0056: plug-in folder for ticks, Checks rows and routes (RUN-SEAMS).
- 0055: loop and wave contract - BLOCKED reasons, tag-then-read claim,
  folder hold, shared merge lock, the six checks (WAVE-INTERPLAY).
- 0054: core hello handshake: clients prove the core before they send
  the token (SEC-HELLO-CORE).
- 0053: main-process parts seam (app/parts/) (OVL-MAIN-PARTS).
- 0052: worn-gear baseline: parsed mod lines in a bounded per-character
  file (TC-WORN-STORE).
- 0051: private runtime files: an explicit ACL on the runtime dir and
  local config (SEC-ACL-APPLY).
- 0050: research dive sources - no free web tools, one host allow-list,
  GGG only at the API Reference and Data Exports pages (DIVE-FLOOR).
- 0049: Demo mode: an isolated AshLight instance on a fixture folder
  (SEC-DEMO-CORE).
- 0048: AshLight's own GGG OAuth public client: scope, ports, token
  handling (TC-OAUTH-REG).
- 0047: licence and NOTICE: Apache-2.0, holder The AshLight authors
  (GP-03).
- 0046: go public: guarded push, private first, public on gates
  (GP-02).
- 0045: per-character build, stale-build alert and upgrade notices
  (BUILD-LIVE).
- 0044: daily GGG developer docs watch, registration reopen alert
  (GGG-DOCS-WATCH).
- 0043: live zone guide and quest tracker (ZONE-GUIDE).
- 0042: hot reload of data files, web assets, overlay page and core
  code (HOT-RELOAD).
- 0041: desktop client (companion window, tray, overlay only inside the
  client) (DESKTOP-CLIENT).
- 0040: self checks and the non-English client notice
  (DIAG-SELF, LANG-GUARD).
- 0039: waystone reward totals and campaign checks
  (UTIL-WAYSTONE-REWARD, UTIL-CAMPAIGN-CHECKS).
- 0038: per-character run history, pace, act splits and deaths
  (UTIL-MULTICHAR).
- 0037: Trade stat ids from the repoe-fork snapshot (TC-UPGRADE-STATS).
- 0036: Run history and price watch files; settings export / import
  (UTIL-RUN-HISTORY, UTIL-PRICE-WATCH, UX-SETTINGS-IO).
- 0035: intentionally unused. It was reserved by a lane draft that never
  merged; do not reuse it (AREA-AUDIT P5-7, 2026-11-17).
- 0034: The game's `.build` file as a download only (TC-BUILDFILE,
  AUDIT-BUILDFILE).
- 0033: Loot filter merge into the player's own filter
  (UTIL-FILTER-MERGE).
- 0032: Swap compare on the card, PoB sanity guard, filter value tiers.
- 0031: Loot filter snippet as a download only (UTIL-FILTER).
- 0030: Player helpers: waystone check, search strings, zone notes.
- 0029: Game exit detection (TEST-LIVE-EXIT): Client.txt staleness only.
- 0028: Theorycraft on real data: end-to-end proof, calc budgets, PoB
  drift guard.
- 0027: TC-LIVE: pinned portable C toolchain for the LuaJIT build.
- 0026: Price book: unique and stackable poe.ninja prices, movers,
  league rollover.
- 0025: TC-DRIFT: unattended PoB-PoE2 release check and pin trial.
- 0024: TC-DELTA: PoB-backed item deltas and per-mod weights.
- 0023: HUD-ACT-RESUME: act splits rebuild from Client.txt at core
  start.
- 0022: TC-BRIDGE: own stdio JSON bridge to the pinned PoB-PoE2
  checkout.
- 0021: TC-CODE-REAL: real PoB2 export check, fixture sources,
  round-trip scope.
- 0020: HUD-ACT: act splits from the log, zone levels from repoe-fork
  world_areas.
- 0019: A finished trade closes one open trade card (OVL-TRADE-CANCEL).
- 0018: TC-PIN: pinned PoB-PoE2 and LuaJIT, license check, opt-in setup.
- 0017: No app calls to trade2; trade-search link only; floor wording
  (PRICE-1, TC-UPGRADE, RES-POLICY).
- 0016: Price check result contract, overlay card slot, rates panel
  (PRICE-1-UI, DATA-NINJA-UI); amended 2026-11-23: card key ninja_url, a
  poe.ninja category page link the player opens; the app requests nothing;
  amended 2026-11-23 (DATA-CONTACT-DEFAULT): issues page as default
  contact, the contact field an optional override (label and note only).
- 0015: Price check per press and the User-Agent contact (PRICE-1,
  UA-CONTACT); amended 2026-11-23 (DATA-CONTACT-DEFAULT): the project's
  issues page is the default contact once public, a typed contact
  overrides it.
- 0014: Build view, item check UI and graphics advisor (TC-VIEW,
  TC-EVAL-UI, GFX-ADVISOR).
- 0013: Web data: one opt-in, one fetch path (DATA-NINJA, TC-URL,
  PRICE-1).
- 0012: Agent worktrees under the sidecar via a WorktreeCreate hook.
- 0011: Core autostart at logon: opt-in current-user scheduled task.
- 0010: Process registry: one of each, stop all of ours, nothing else.
- 0009: DATA-LICENSE: game-data sources, what is bundled vs fetched.
- 0008: Live resume: bounded backward scan of Client.txt.
- 0007: TC-CODE: PoB2 share-code codec, build model, paste API.
- 0006: Game FPS measurement method (OVL-FPS): no ETW present tracing.
- 0005: Core keepalive: detached stdlib supervisor.
- 0004: Scope: theorycraft and item optimization; PoB2 interop path.
- 0003: What AshLight reads, and when.
- 0002: Stack: Python stdlib core + browser dashboard + Electron overlay
  shell.
- 0001: Name: AshLight (code AL).
