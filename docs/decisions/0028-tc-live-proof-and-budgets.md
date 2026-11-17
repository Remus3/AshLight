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
