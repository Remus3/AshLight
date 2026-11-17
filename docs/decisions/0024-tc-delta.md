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

## Reverses if

See R1-R5.
