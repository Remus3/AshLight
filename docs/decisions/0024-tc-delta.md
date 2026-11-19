# 0024 - TC-DELTA: PoB-backed item deltas and per-mod weights

Date: 2026-11-17. Trigger: ROADMAP row TC-DELTA (decision 0004 phase 2).

Renumbered from 0022 to 0024 on 2026-11-17: 0022 collided with
0022-tc-bridge (kept, earlier commit); 0023 is taken on main and on lane
branches, so 0024 is the next number free on every branch.
Ruled by the build lane itself (CLAUDE.md FLEET item 1).

## Decision

`server/al/theorycraft/delta.py` computes, from an optional calc callable
`calc(build, swaps) -> {"dps", "ehp"}` (swaps: PoB slot name -> item text):
- the DPS and EHP change of the build with the checked item in each slot it
  fits (old, new, delta, percent), and a blended score: 0.5 x DPS percent +
  0.5 x EHP percent (`DEFAULT_BLEND`); verdict upgrade / downgrade outside
  +-1 percent (`SIDEGRADE_PCT`), else sidegrade;
- per-mod weights from PoB deltas: each stat key on the checked or the
  equipped item is probed by appending one line with every number set to 10
  to a carrier item in the slot (the equipped item, else the checked item);
  the weight is the blended percent change per point. At most 24 probes per
  slot (`MAX_PROBES`); flag mods (no number) stay uncounted.

`theorycraft.evaluate(..., calc=)` uses these in place of the hand weights
when a calc is given and answers; the result carries `calc` {source "pob" |
"weights", notice null | "off" | "failed"} and `mod_weights`. With no calc
(component off) or a calc that raises / times out / answers junk, the
TC-EVAL stat-weight result stands unchanged and the card says why: the
dashboard's Item check card shows one line ("Scored with your stat weights.
DPS and EHP need the optional Path of Building calc, which is off." or "...
did not answer ..."); with PoB the line reads the DPS and EHP change and
the overlay card's third line becomes "DPS +x%, EHP +y%".

`LastEval` reads a calc provider at run time (`Core.tc_calc`, None today),
so a build or weights change re-runs the deltas with no click (ZERO-CLICK).
The TC-UPGRADE doc gains `weights` {source "pob" | "hand", top: up to 6
positive per-mod weights of the compared stats}.

## Rulings

- R1 TC-BRIDGE has not landed, so there is no real calc yet. ACCEPT "delta
  tests on fixtures" is met with a deterministic fake calc on the TC-EVAL
  fixture build and items (`tests/test_tc_delta.py`); the core's provider
  returns None, so every card shows the "off" notice until TC-BRIDGE sets
  `Core.tc_calc`. Alternatives: (b) wait for TC-BRIDGE - rejected: the
  engine, fallback and wiring are independent of the process transport;
  (c) build the bridge here - rejected: out of row scope and this machine
  has no compiler for LuaJIT (TC-PIN). Reverses if: TC-BRIDGE needs a
  different calc contract (then delta.outputs adapts).
- R2 Output keys are the neutral "dps" / "ehp"; the bridge client maps
  PoB's own output names (e.g. a combined DPS and total EHP figure) to
  them, so PoB name drift stays in one place (TC-DRIFT). Reverses if: never
  (informational).
- R3 Blend 50/50 and a 1 percent sidegrade band are fixed constants, not in
  the weights file. Alternatives: a user-editable blend in weights.json -
  deferred: adding keys changes the weights schema and the dashboard editor
  for a choice no user has asked for. Reverses if: a user or the operator
  asks for an offence / defence lean.
- R4 Mod weights reach TC-UPGRADE as data on the upgrade doc only; the
  trade URL stays base + rarity because stat filters need permitted trade
  stat ids (TC-UPGRADE-STATS, decision 0017). Reverses if: TC-UPGRADE-STATS
  finds a source (then the top weights become weighted stat filters).
- R5 Probes are not cached across presses: one press costs 1 + per slot
  (1 + 1 + probed keys) calc calls. Reverses if: the real bridge makes a
  press feel slow (then cache per build revision, slot and carrier).
  REVERSED 2026-11-17 (MATH-WEIGHTS): probes are cached per build XML,
  slot, carrier and blend (theorycraft/pobweights.py, in memory, LRU 64),
  taken before the real bridge was measured, because each probe is one full
  PoB calculation; the cache also lets a calc outage score with this
  build's PoB weights (calc.source "pob_cached"). Values stay PoB's own.
- R6 (2026-11-17, AUDIT-TC-WIRE) R1's provider is now real:
  theorycraft/calcwire.py maps PoB outputs (R2) and the core enables it
  only with local config "tc_calc": true and the component installed.
  Alternatives: always on when installed - rejected: the opt-in already
  exists for setup and a slow first press should be a choice. Reverses if:
  the operator rules the calc on whenever installed.

- R7 (2026-11-17, MATH-PERF) Budget on the real bridge (decision 0028):
  first item check within 60 s (measured 12.4 s), warm check 30 s (3.6
  to 5.5 s), repeat check 10 s (1.3 s), bridge cold start 30 s (1.2 s),
  build load / reload 5 s (0.4 / 0.3 s), luajit.exe peak working set
  768 MB (511 MB with the bridge.lua GC ceiling). Enforced by
  tests/test_math_perf.py and tests/test_math_e2e_live.py. Reverses if:
  a re-measure after a pin move or on the target machine says otherwise.

## Reverses if

See R1-R5, R7 and the 2026-11-19 amendment.

## Amendment 2026-11-19 (TC-PRESS-STAGED-LIVE, F-059)

Decision: the item check is published in stages. The press answers at
once with the stat-weight card (evaluate.stages() stage "weights": no calc
call; this build's cached PoB weights score it when every slot has some);
POST /api/eval returns that first stage. Path of Building's DPS / EHP
change (stage "pob") and then its per-mod rows (stage "mods") follow from
one daemon worker per core (theorycraft/live.py LastEval), each an update
of the same card that keeps the press time (state.set_eval keep_time; the
card id moves, its `at` does not), so the overlay does not show the card
again. While a stage is pending the card part cardparts/stage.py adds the
dashboard note "Path of Building numbers are coming."; the last stage
drops it. One press in flight: a press generation counter, bumped by
every press, every re-score (rerun) and Core.close(), cancels the older
press's pending stages at the next stage boundary (its generator is
closed, so no further calc call) and a stale stage is never published.
A calc error still ends on the weights card with the "failed" /
"implausible" notice (the stages() contract); an unexpected error in a
later stage republishes the last card without the pending note. Core.close()
stops the worker and joins it. A LastEval built without `staged` (tests,
direct callers) runs every stage inline and publishes the last one, as
before.

Alternatives: (a) one synchronous press, as before - rejected: a first
press on the real bridge took 12.4 s (R7) before the card showed anything;
(b) a worker per press - rejected: two presses would race the one shared
calc process and could publish out of order; (c) cancelling inside a
stage (between probes) - not done: stage "mods" is all-or-nothing in
evaluate.py, so cancellation waits for the stage boundary.

Why: the key press must answer within budget B15 (first card under 0.5 s)
with what is already known, and fill in by itself (ZERO-CLICK: same one
press; the card fills in by itself).

Reverses if: the staged updates make the overlay card flicker or re-show
in play, a stage boundary is too coarse to cancel a stale press in time,
or the calc gets fast enough that the first press is under budget whole.
