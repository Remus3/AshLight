# AshLight ROADMAP

Open work only, as lane rows the loop (`tools/al_loop.py`) can dispatch.
Format: `- [ ] ID (lane) title. ACCEPT: ...`; `(priority)` jumps the queue.
Done rows are flipped to `[x]` by the merge and pruned at /done.

## Lane: build

- [ ] LIVE-1 (build) (priority) PARTIAL 2026-11-16: first live log verified
  (research 0002 section 7): prefix, SCENE, area generation, instance
  connect, level-up, global / trade chat VERIFIED; "(unknown)" and "Act <N>"
  scenes and the empty-character config were WRONG and are fixed; fixture
  tests/fixtures/client_live_shapes.txt. REMAINS: death, whispers and trade
  templates (then replace the HUD-WHISPER fixture whispers with anonymised
  real-shaped ones), party / guild chat, AFK / DND, joined / left, Trade
  accepted, hideout scene names. ACCEPT: every event type seen live has a
  fixture and a passing test. Needs the operator to play past the whisper
  level, die once, and receive one trade whisper.
- [ ] OVL-BUDGET (build) PARTIAL 2026-11-16 (decision 0002 "Measured
  2026-11-16 (OVL-BUDGET, game running)"): idle with the game open at
  character select 3 processes, about 204 MB working set, 0.000 percent CPU,
  0 GPU - within budget, after the in-process-gpu start fix. REMAINS: the
  ACTIVE measurement (overlay updating during play, in a map). ACCEPT: within
  budget or a ruling on Tauri / native.
- [ ] OVL-FPS (build) PARTIAL 2026-11-16. Method per decision 0006 (no
  PresentMon / ETW of the game). Character-select proxy: system-wide GPU 3D
  utilisation off 52.5 vs on 53.3 percent, inside noise, GPU saturated.
  REMAINS: in-map run read from the game's own FPS display, overlay off vs
  idle vs updating, Windowed Fullscreen. ACCEPT: average FPS loss under 1
  percent, 1 percent lows unchanged within noise; numbers in decision 0002.
- [x] OVL-TRADE-CANCEL (build) Decide whether ": Trade cancelled." (new
  event trade_cancelled) should clear or mark an open trade card (design
  review 2026-11-16). ACCEPT: behaviour decided and tested. DONE
  2026-11-17: decision 0019 - accepted / cancelled drop one open card (by
  counterparty name if a line carries one, else the oldest); with
  UX-REVIEW F1 (HUD status slot says "1 trade" / "N trades" while a card
  holds the slot) and F6 (dashboard polite "New trade request from <name>."
  only when the set of ids grows). ZERO-CLICK: the card clears itself.
- [ ] HUD-ACT (build) Leveling helpers: act / zone level table from an
  attributed build-time data snapshot (license checked first, research 0005);
  zone timer splits per act. ACCEPT: split table on the dashboard.
- [x] PRICE-1-COPY (build) Design review of PRICE-1-WIRE (reviews.log
  2026-11-17, S3 x3) on price.card_of: F1 any error text containing
  "league" maps to "no league" (match only trade.search_url's exact
  "league required"; others -> free-text error); F2 `off` covers both web
  data off and contact not set but the card says "Web data is off" (carry
  the reason, add a state.py PRICE_TEXT entry for contact not set, design
  review); F3 every skipped doc maps to "not an item" incl. build_query's
  "item has no base type" (map only reason "not an item"). ACCEPT: tests
  per mapping; design-reviewer pass. ZERO-CLICK: code row.
- [x] PRICE-TRADE-LINK (build) Decision 0017: remove every reachable app
  HTTP path to trade2 (/data/stats, /data/leagues, /search, /fetch); keep
  build_query offline, producing
  https://www.pathofexile.com/trade2/search/poe2/<league>?q=<json>; price
  card status "link" with `url` (0016 Fork 1 amended); dashboard shows a
  click-through link, overlay "Trade link ready"; the core never opens it;
  league from config, else Standard, nothing fetched; prices from poe.ninja
  only. After PRICE-1-COPY merges (both edit price.py). ACCEPT: tests that
  no trade host is in the webfetch allowlist and no code path reaches a
  trade2 request; URL round-trip test; design-reviewer pass.
  ZERO-CLICK: the item-check press builds the link with the price card; the
  user clicks it only if they want the trade site.
  DONE 2026-11-17: trade network code deleted, webfetch refuses trade URLs,
  offline search_link (research 0016), card status "link" (0016 amendment).

## Lane: data

- [x] DATA-TREE-IDS (data) DONE 2026-11-17: PoB2 spec node ids and GGG
  export skill ids are the SAME id space (research 0015: PoB2 PassiveSpec /
  PassiveTree / passivetree_ggg source, plus all 4914 PoB2 0_5 tree ids
  found in the GGG export with matching names). resolve() stays 1:1;
  TreeData.id_match guards it (build view drops named_nodes when under
  half the spec ids exist, adds tree_match). Tests:
  tests/test_tc_tree_ids.py. ZERO-CLICK: code row, no user step.

## Lane: review

- [ ] UX-REVIEW (review) Glanceability review of dashboard and overlay
  (contrast, type scale, motion, phone width) against research 0008.
  ACCEPT: findings fixed or filed.
- [x] RES-POLICY (review) Re-read GGG's developer docs and ToU each patch
  cycle; update research 0001 and the CLAUDE.md floor if anything changed.
  Done 2026-11-17: policy unchanged; 3 floor wording proposals in research
  0001 for MAIN / operator.

## Theorycraft and item optimization (decision 0004, research 0010)

Phase 1 is stdlib-only file interop with Path of Building PoE2; phase 2
adds the optional pinned LuaJIT + PoB calc subprocess. Rows run in order.
Every row carries the minimal-interaction constraint (CLAUDE.md, decision
0004): no click the app can safely make for the user, state updates itself,
and the row's own dev / test steps run unattended. ZERO-CLICK states how.

- [ ] TC-CODE-REAL (review) Confirm the codec on a real PoB2 v0.23.1 export
  (framing, root element, PlayerStat names) once a PoB2 install or an
  operator-supplied code is available; add it as a fixture only if its
  owner allows. After TC-CODE. ACCEPT: decode + parse + byte-exact round
  trip of the real code. ZERO-CLICK: a test that skips when the fixture is
  absent.
- [ ] TC-SNAP-UI (build) Show snapshot.ATTRIBUTION (decision 0009) in the
  dashboard footer / About and the overlay About wherever snapshot data is
  used; expose it via an API field. After TC-SNAP. ACCEPT: text visible,
  design-reviewer pass. ZERO-CLICK: shown automatically when the cache
  exists.
- [ ] TC-UPGRADE (build) Upgrade search as a link builder (decision
  0017): from the local weights build a trade2 search URL offline
  (https://www.pathofexile.com/trade2/search/poe2/<league>?q=<json>) that
  the user opens in their own browser; the app makes no trade2 request, no
  POESESSID; prices shown come from poe.ninja only. Until TC-UPGRADE-STATS
  lands the link carries name, base and rarity only; weighted mod filters
  are BLOCKED on TC-UPGRADE-STATS. After PRICE-TRADE-LINK, TC-EVAL.
  ACCEPT: URL-builder tests; shares PRICE-TRADE-LINK's builder, not
  duplicated; no trade host in the webfetch allowlist.
  ZERO-CLICK: the same hotkey press that evaluates the item builds the
  link; the user clicks it only to open the trade site.
- [ ] TC-UPGRADE-STATS (review) Find a permitted source for trade stat ids
  (mod filters for TC-UPGRADE links): GGG API Reference / Data Exports
  check first (decision 0017), then attributed build-time snapshots with a
  license check per decision 0009; never the trade2 /data/stats endpoint
  from the app. ACCEPT: source and license recorded in docs/research and a
  decision, or a dated "no permitted source" note.
  ZERO-CLICK: research row; if a source is found, the build-time fetch runs
  in setup.ps1 unattended.
- [x] TC-PIN (build) Phase 2 setup: tracked pin file (PoB-PoE2 tag, commit,
  archive sha256; LuaJIT version, sha256; no absolute paths); setup.ps1
  step fetches the PoB source archive to the sidecar Cache and builds or
  accepts LuaJIT into Build, hash-verified, off by default; THIRD-PARTY
  notices with PoB's MIT and component notices. ACCEPT: hash mismatch
  refuses; re-run is a no-op; test_sidecar_paths covers the new paths.
  ZERO-CLICK: one opt-in toggle; setup.ps1 does the rest unattended.
  DONE 2026-11-17 (decision 0018): config/tc_pins.json pins PoB-PoE2
  v0.23.1 (7d6f530c) and LuaJIT 2.1.1794386141 (63c8f1a9), both archive
  SHA-256 verified over two downloads; tools/tc_pin.py + setup.ps1 -TcCalc
  (or tc_calc: true); THIRD-PARTY.md; tests/test_tc_pin.py. LuaJIT is built
  only when MSVC / MinGW is on PATH, else "source-only" (this machine has
  neither: TC-BRIDGE needs a compiler or a later pinned binary).
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

## Design and UX audit (operator order 2026-11-16)

Uses the design-reviewer agent (.claude/agents/design-reviewer.md) and the
design docs in docs/design/, both made by a separate agent.

- [ ] DESIGN-GATE (review) Make the design-reviewer pass a standing step for
  every row that touches web/ or app/ (review lane after build). After
  DESIGN-AUDIT. ACCEPT: lane prompt or loop rule names the step; one row
  reviewed through it. ZERO-CLICK: runs in the loop, no manual trigger.
  Partly done: the lane prompt names the step (DS-REVIEW-HOOK); "one row
  reviewed through it" waits for LOOP-ARM (the loop is not armed).

Rows filed by the first audit (docs/design/0002-first-audit.md; S1 = worst).
Run after DESIGN-AUDIT, ahead of DESIGN-GATE.

## Ops

- [ ] LOOP-ARM (build) Arm the lane loop as a scheduled task (every 15 min,
  IgnoreNew, hidden) after one supervised dry-run tick and one real tick on a
  trivial row. ACCEPT: task read back; first tick's progress file done.
- [ ] WT-SIDECAR (build) Harness Agent-tool worktree isolation creates
  worktrees under the repo's .claude/worktrees/, but the Sidecar rule puts
  them under the AL sidecar Worktree folder. Finding: .claude/worktrees/ IS
  gitignored (.gitignore line 37), so nothing leaks into commits; the
  violation is placement only. Fix: a WorktreeCreate hook in
  .claude/settings.json that creates the worktree at
  server/al/paths.py's Worktree path (kit fleet_lanes.worktree_path), or
  harness config pointing worktrees at the sidecar; whichever the harness
  supports. Also note: the isolation hook blocks a worktree agent from
  merging into main, so the main checkout merges its branches (ff-only via
  fleet_gitlock). ACCEPT: a fresh isolated agent's worktree resolves under
  the sidecar Worktree dir; tests/test_sidecar_paths.py still green.
  ZERO-CLICK: the hook fires on every isolated spawn; no manual move.
  PARTIAL 2026-11-17: hook ready; activation = operator act. Decision
  0012: tools/wt_sidecar_hook.py (WorktreeCreate + WorktreeRemove) makes
  the worktree at server/al/paths.py worktree_dir()/<name>, tested on a
  tmp repo (tests/test_wt_sidecar_hook.py). Operator adds to
  .claude/settings.json "hooks": "WorktreeCreate" and "WorktreeRemove",
  each [{"hooks": [{"type": "command", "command": "python
  \"$CLAUDE_PROJECT_DIR/tools/wt_sidecar_hook.py\""}]}], then checks one
  isolated spawn lands under the sidecar Worktree dir.
- [x] LEAK-WT (build) The commit hook's leak sweep reports DEGRADED in agent
  worktrees: config/local.json and config/leak_needles.json are gitignored
  and absent there. Fix: tools/leak_sweep.py resolves the main checkout via
  `git rev-parse --git-common-dir` and reads its needle config when the
  worktree has none, so the sweep runs ARMED in worktrees. ACCEPT: a commit
  in a linked worktree prints ARMED with the main checkout's needle count; a
  test on a tmp repo + linked worktree covers it. ZERO-CLICK: the hook finds
  the config itself on every worktree commit; no copy step.
  Done 2026-11-17: resolve_config() in tools/leak_sweep.py (worktree
  config wins, else main checkout); run line names config=<source>;
  tests/test_leak_sweep.py tmp repo + linked worktree.
- [x] PUB-NAME (review) Manual poe2wiki check that "Ashlight" is not a GGG
  proper noun (decision 0001). Done 2026-11-17: 0 hits on both wikis
  (research 0009).
- [ ] OPERATOR: create the GitHub remote when the operator wants to publish
  (then lift the pre-push refusal in the same change, CI workflow with the
  kit's fleet_identity_guard.yml as a required check).
