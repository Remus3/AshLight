# 0004 - Scope: theorycraft and item optimization; PoB2 interop path

Date: 2026-11-16. Trigger: operator order 2026-11-16 (scope expands to
theorycrafting builds and item optimization). Input:
`docs/research/0010-theorycraft-scope.md`. Amends decision 0002 (stack).
Forks ruled by an adjudicator agent the same day; rulings recorded below.

## Decision

1. Scope. AshLight is the live companion plus a theorycraft and
   item-optimization layer: view the build you play, evaluate an item
   against it, and search for upgrades. Crafting simulation is out of scope
   (link out to Craft of Exile). Commercial use stays out (GGG IP rule,
   research 0010 section 2).
2. Calc integration path: interoperate with Path of Building for PoE2
   (MIT), never reimplement its engine. Phased (adjudicator ruling, option
   D = C then A):
   - Phase C, file-level interop, stdlib only: decode / encode PoB2 share
     codes (URL-safe base64 of deflated XML) with `base64` + `zlib`, show
     the build (tree, gear, skills, PoB's saved stats), open it in the PoB
     GUI. Item evaluation in this phase uses stat-weight scoring.
   - Phase A, optional calc component: a separate `luajit.exe` subprocess
     runs an unmodified, pinned PoB-PoE2 SOURCE checkout through a stdio
     JSON bridge written fresh by us (no code from pob-mcp or pob2-mcp; the
     latter is GPL-3.0, ideas only). The bridge only loads build XML / JSON
     and item text and returns computed outputs (DPS, EHP, deltas). Killed on
     timeout; the core runs without it. Not ctypes on PoB's `lua51.dll`
     (in-process crash risk, fragile).
3. Stack amendment to 0002 (adjudicator ruling): "Python stdlib only" binds
   AshLight's own code. Optional external tools (LuaJIT, a PoB-PoE2 source
   checkout) are allowed only as hash-pinned, unmodified subprocesses,
   fetched at setup into the AL sidecar (`Cache\pob2\`, `Build\luajit\`,
   resolved by `server/al/paths.py`), never vendored in the tracked tree,
   never imported, off by default. A tracked pin file holds the PoB tag,
   commit and archive SHA-256 and the LuaJIT version and SHA-256 (no
   absolute paths); setup refuses on a hash mismatch; the pin moves only by
   a commit with the bridge tests green. The PoB MIT notice (and its
   third-party notices) ship in a THIRD-PARTY file.
4. Character import: GGG OAuth public client (PKCE, loopback redirect in
   the AL port block, scopes `account:profile` + `account:characters`,
   realm `poe2`) once GGG reopens registration - registering is an operator
   act. Until then: the user imports in PoB2 and pastes the share code, or
   pastes character JSON. Never POESESSID, never `character-window` or other
   undocumented endpoints (ToU 7i), never poe.ninja's internal builds /
   profile endpoints, never another app's OAuth client id.
5. Item input: the existing per-press clipboard read (decision 0003) feeds
   both price check and "evaluate against my build". No new read path.
6. Upgrade search (adjudicator ruling): allowed through trade2 weighted
   (`"type": "weight"`) stat queries, opt-in, one search per manual user
   action, through the single PRICE-1 limiter that obeys `X-Rate-Limit-*`
   and `Retry-After` dynamically, query complexity under the site's cap of
   200, truthful User-Agent, no POESESSID, no polling or auto-refresh. Mod
   weights are computed locally (stat weights in phase C, PoB deltas in
   phase A, including EHP weights, which PoB's own generator lacks).
7. Game data: build-time snapshots only, with a manifest (URL, date,
   sha256) and attribution: GGG's poe2-skilltree-export and the RePoE fork
   PoE2 export (MIT code, GGG-owned data) after DATA-LICENSE rules; poe2db
   and the PoE2 wiki (CC BY-NC-SA 3.0) link out only.
8. Name: keep AshLight (research 0010 section 6); no flag to the name
   review.
9. Minimal-interaction principle (operator order 2026-11-16): the repo and
   the app aim for as little user interaction as possible. In play, state
   progresses and updates itself with no clicks (the loaded build reloads,
   deltas recompute on change, one hotkey press yields price, verdict and,
   when opted in, the upgrade search). In build / debug, setup, snapshots,
   tests and pin checks run unattended. Every ROADMAP row carries a
   `ZERO-CLICK:` line. Bound: it never overrides the ToS floor - reads of
   clipboard / screen stay one per manual AshLight press, opt-ins stay
   explicit (Client.txt, trade requests), and no input goes to the game.
10. Game settings advisor (operator order 2026-11-16): an optional panel
    reads this machine's hardware and recommends PoE2 graphics settings,
    Windowed Fullscreen required. Recommend only: the user applies them in
    game; AshLight never reads or writes the game's config files (the read
    list in CLAUDE.md allows only Client.txt from the game install).
11. Design / UX: a design-reviewer audit pass (agent and docs/design/ made
    by a separate agent) covers the new panels; ROADMAP DESIGN-AUDIT and
    DESIGN-GATE.

## Alternatives

- Own Python calc engine (B): would chase PoB's rules every patch and drift
  from the community standard that poe.ninja also uses. Rejected.
- Phase A alone: delivers nothing until the LuaJIT toolchain works.
  Rejected in favour of C first.
- Phase C alone: no computed DPS / EHP, so no real upgrade deltas. Kept as
  phase 1 and as the fallback.
- ctypes on PoB's bundled `lua51.dll`: no extra binary, but in-process
  crashes and fragile ABI coupling. Rejected.
- Vendor PoB and LuaJIT in the repo: bloats the tree, breaks the sidecar
  rule. Rejected. Make PoB required: rejected, the core must work without it.
- Undocumented character endpoints or POESESSID for import: ToS floor.
  Rejected outright.
- Settings advisor that writes the game's config file (one-click apply):
  game file modification, ToS floor. Rejected; recommend only.
- Fully automatic upgrade search on a timer (zero clicks): polling the
  unofficial trade2 API without a user action. Rejected; the search rides
  on the item-evaluation press.

## Why

PoB2 is MIT, actively maintained (v0.23.1, 2026-07-28), already the
calculator the community trusts, and ships a headless wrapper; build codes
are plain deflated XML, readable with the stdlib. Interop keeps AshLight
small, keeps the core dependency-free, adds no contact with the game, and
puts the effort into what no existing tool does: the build next to the live
session and one-press "is this an upgrade for me".

## Pin log (TC-DRIFT, decision 0023)

One dated line per drift check that changed nothing or moved the pin;
`python tools/tc_drift.py note` prints the next line.

- 2026-11-17 HOLD: no PoB-PoE2 release after v0.23.1 (2026-07-28); latest
  v0.23.1; pin stays (tag v0.23.1, commit 7d6f530c). dev is 109 commits
  ahead (0.5.5 rune / runemastered data, HeadlessWrapper "Restore headless
  global cache cleanup", .build export) but untagged (research 0017). At
  the next tag the unattended trial runs the bridge tests, including the
  new reload-leak test, before any pin move.

## Reverses if

- PoB-PoE2 internals drift breaks the bridge at every release: pin harder
  or fall back to phase C only (then remove the stack amendment).
- PoB ships an official headless API: adopt it in place of our bridge.
- PoB's license changes away from a permissive license.
- GGG documents trade search, opens a character endpoint without OAuth, or
  changes its tool policy: re-rule items 4 and 6 (research 0001 refresh).

## Pin log (TC-DRIFT)

- 2026-11-17 HOLD (no move needed). Read back from the GitHub API
  (`repos/PathOfBuildingCommunity/PathOfBuilding-PoE2/releases/latest` and
  `/tags`): the latest PoB-PoE2 release is still v0.23.1 (published
  2026-07-28, tag commit 7d6f530c), equal to `config/tc_pins.json`; the
  newer-looking v2.49.x tags in that repo are inherited PoE1 PoB tags, not
  PoE2 releases. LuaJIT `v2.1` branch head read back as 63c8f1a9 (committed
  2026-11-11), equal to the pin. No bridge tests exist yet (TC-BRIDGE open),
  so nothing to re-run. Next check: the next PoB-PoE2 release tag `v0.*`.
