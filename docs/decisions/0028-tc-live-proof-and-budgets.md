# 0028 - Theorycraft on real data: end-to-end proof, calc budgets, PoB drift guard

Date: 2026-11-17. Trigger: ROADMAP rows MATH-E2E-LIVE, MATH-PERF and
MATH-POB-DRIFT-GUARD (AREA-MATH batch 3), after TC-LIVE installed the
optional calc component and matched the PoB GUI (decision 0027).
Ruled by the build lane itself (CLAUDE.md FLEET item 1). 0027 is the
highest number on main and every branch, so this is 0028.

## Decision

1. MATH-E2E-LIVE (`tests/test_math_e2e_live.py`): a test core on a free
   port in 8961-8979, its runtime's own local.json with "tc_calc": true
   (a test core never reads config/local.json), the public reference
   build (pobb.in Nqt6FK5lIc6F, sidecar Cache\tc_bridge) posted as a PoB
   code to POST /api/build-code, then four hand-written PoE2 copy-format
   items (`tests/math_live_items.py`) to POST /api/eval. Asserted: calc
   source "pob"; the base DPS / EHP equal the PoB GUI sidebar (FullDPS
   39265, TotalEHP 32072, within 0.1 percent); verdict and delta signs
   (ring upgrade +2.7 % DPS / +3.2 % EHP; amulet sidegrade 0.0 / +0.7 %;
   bow downgrade -53 % DPS; body upgrade +10.3 % EHP); PoB per-mod weights
   present; the published card carries the same deltas; press times within
   the budget; a press whose calc process is killed again and again
   mid-request answers 200 with calc.notice "failed" (weights or cached
   PoB weights), and the next press is PoB again.
2. MATH-PERF budget (`tests/test_math_perf.py`, constants in
   `tests/tc_live_util.py` BUDGET). Measured on this machine, 2026-11-17:

   - cold start to the ready frame: 1.2 to 1.3 s (budget 30 s)
   - load_build, real level 90 build: 0.38 to 0.42 s (budget 5 s)
   - reload: 0.26 to 0.29 s, median of 30: 0.30 s (budget 5 s)
   - set_item + outputs, warm: 0.09 to 0.10 s (budget 2 s)
   - first item check incl. start: 12.4 s (budget 60 s; 22 calc calls:
     base, 2 slots x (delta + carrier + probes), each a full reload)
   - item check, bridge warm: 3.6 to 5.5 s (budget 30 s)
   - same item again (probes cached, MATH-WEIGHTS): 1.3 s (budget 10 s)
   - luajit.exe working set after 30 reloads: 497 MB, peak 511 MB
     (budget 768 MB)

3. GC ceiling in bridge.lua: each load_build leaves the previous build as
   garbage (~20 MB); with LuaJIT's default pause the Lua heap reached
   ~600 MB and the process working set ~900 MB (LuaJIT never returns the
   pages). After load_build the bridge now runs one full collect only when
   the Lua heap is over 384 MB: peak working set 511 MB, median reload
   unchanged (0.29 s vs 0.32 s).
4. MATH-POB-DRIFT-GUARD (`tests/test_tc_pob_drift_guard.py`): reads the
   installed pinned checkout for every PoB name bridge.lua relies on
   (HeadlessWrapper mainObject / SetMainObject / runCallback /
   loadBuildFromXML / promptMsg, main.modes["BUILD"] and SetMode,
   build.itemsTab / calcsTab / buildFlag, new(), ItemsTab slots / AddItem /
   PopulateSlots / UndoHandler AddUndoState, CalcsTab BuildOutput /
   mainOutput, Item NormaliseQuality / GetPrimarySlot, ItemSlot
   SetSelItemId); a meta-test fails if bridge.lua calls a PoB method the
   guard does not list. Live: the bridge drives the checkout and
   mainOutput still carries FullDPS, TotalEHP, Life, EnergyShield and all
   17 reference keys. Each failure names the file, the shape and the fix
   ("update bridge.lua before moving the pin"). It joins the TC-DRIFT
   trial (tools/tc_drift.py TRIAL_TESTS), so a candidate pin with a moved
   API shape is red, not green.

## Alternatives

- Full GC after every load (working set ~300 MB) - rejected: +0.2 s per
  load, +4 s on a first item check of 22 loads.
- Lower GC pause (setpause 100 / 120) - rejected: ~550 MB and +0.2 s per
  load; the threshold collect is cheaper and lower.
- Restore the slot's original item instead of reloading the build per
  swap (set_item is 0.1 s vs 0.3 s) - deferred: PoB's AddItem keeps every
  added item in the build, so state would grow; the press is within
  budget today. Reverses if: a press feels slow in play.
- Real game items from the operator's clipboard as fixtures - rejected:
  hand-written copies of public-build-shaped items are enough and need no
  operator act.

## Reverses if

The budgets are re-measured when the PoB pin moves (TC-DRIFT) or the
machine changes; a breach on unchanged code means PoB got slower or
heavier and decision 0024 R5 (per-swap reload) is revisited. The GC
ceiling reverses if LuaJIT or PoB changes make it cost more than it saves.
The drift guard rows change only together with bridge.lua.

## Amendment 2026-11-18 (LOOP-DRIFT-REF, F-064; with decision 0025)

- Decision: the PoB GUI reference is keyed by tag. A reference folder
  (tracked fixtures, gitignored ops/runtime/tc_bridge, the sidecar
  Cache	c_bridge) may hold `gui_expected.json` and any number of
  `gui_expected-<tag>.json`, each naming its tag in `"pob"`. The tag under
  test is the pin's (the candidate's during a drift trial; a rehearsal is
  `ref-<12 hex>`). The same tag compares the recorded numbers within 0.1
  percent, as before. Another tag takes the newest recorded reference,
  reports per-key deltas (want, got, relative delta) and fails unless that
  reference carries a session's written acceptance for the tag under test:
  `"accepted": {"<tag>": "<YYYY-MM-DD> <why>"}`. So a live trial of a new
  tag is live-green only with a reference recorded for it or a dated
  acceptance of the deltas.
- Alternatives: compare any recorded reference within 0.1 percent (a new
  PoB that changes numbers on purpose can never be live-green, or a wrong
  one is masked by a widened band); skip the comparison on a tag mismatch
  (live-green without any GUI check); a per-key tolerance table (guesses
  which outputs may move).
- Why: a pin move either proves the bridge against the GUI of the new tag
  or leaves a dated, readable record that a session read the deltas and
  accepted them.
- Reverses if: the acceptance becomes a rubber stamp in practice, PoB
  changes the sidebar outputs every release, or a scripted GUI read
  becomes possible.
- Tests: tests/test_tc_drift.py test_gui_reference_is_keyed_by_tag,
  tests/test_tc_bridge.py test_live_outputs_match_pob_gui_within_0_1_percent.

## Amendment 2026-11-22 (TC-CALC-IDLE, plan unit F-154)

- Decision: luajit leaves when it is not needed, and the GC ceiling in
  bridge.lua stays as it is (bridge.lua not edited).
  1. calcwire.Provider stamps `last_used` when __call__ makes a calc and
     at the start and end of every calc and calc.raw call, and counts the
     calls in flight. Its `reap(idle=False)`, from the core's loop tick,
     stops the calc process after IDLE_STOP_S = 1200 s without a call, or
     at once when `idle` is true, but never while a press holds it: a call
     in flight, or one that ended under PRESS_HOLD_S = 30 s ago (a press
     between two of its stages). Turning tc_calc off still stops it at
     once. A stop and the start of a call are ordered by one lock, so a
     call never meets a process being stopped under it.
  2. Core.tick_calc reads the state's game-idle flag (decision 0029
     Client.txt staleness: the log consented and stale for 20 min, the
     snapshot's `game_idle`; never a process-list check), only while a
     calc is running, and passes it to reap.
  3. The next press, re-score or build load makes a fresh calc at once
     (no RECHECK_S wait); the stat-weight card is published before any
     calc call (decision 0024 amendment 2026-11-19), so luajit starts
     behind the first staged card. A call on a calc the provider dropped
     is adopted again, so the process it starts is reaped like any other.
  4. exepin.verified caches a match with the exe's size and mtime and the
     recorded hash (the record is read every time); any change hashes the
     exe again and a mismatch is never cached. Each restart after an idle
     stop checks the exe before it runs it, now without reading it.
- Measured 2026-11-22 on this machine, reference build, 30 loads per
  run, two runs each (a scratch copy of bridge.lua for the variant):
  - GC ceiling as shipped: median reload 0.26 to 0.28 s, working set
    485 to 504 MB, peak 492 to 504 MB.
  - full collect after every load: median reload 0.49 s, working set
    275 to 281 MB, peak 281 to 286 MB.
  The full collect costs about 0.22 s per load (about 4.8 s on a first
  item check of 22 loads) for about 220 MB that the idle stop now frees
  anyway, 30 s after a press while the game is idle and after 20 min
  otherwise. The reverse clause of this decision (the ceiling costs more
  than it saves) is not met, so item 3 stands; B17 (peak 768 MB) is
  unchanged.
- Alternatives: a full collect after every probe load (measured above:
  slower presses for memory the idle stop frees); stop only on game idle
  (luajit stays at about 500 MB through a long session without presses);
  a shorter idle timer such as 5 min (a cold start of about 1.3 s plus the
  first load on more presses in normal play); reading game idle from a
  full state snapshot each tick (a snapshot every 0.5 s for one boolean);
  stamping last_used on every __call__ (the build view asks the provider
  on each read, so an open dashboard would keep luajit alive forever).
- Why: the calc holds about 500 MB that nothing uses between presses; a
  restart costs one cold start behind a card that is already shown.
- Reverses if: restarts after an idle stop make presses feel slow in play,
  game_idle misfires while the player plays, a press is ever seen cut by
  a stop, or a later measurement shows the full collect cheaper than the
  ceiling.
- Tests: tests/test_tc_wire.py test_provider_stops_after_idle_and_answers_later,
  test_idle_stop_never_fires_mid_press, test_game_idle_stops_the_calc;
  tests/test_audit_exe_path.py test_verified_is_cached_by_mtime_and_size;
  tests/test_math_perf.py test_luajit_memory_stays_under_ceiling (B17).
