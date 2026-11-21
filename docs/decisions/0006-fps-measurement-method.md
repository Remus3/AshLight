# 0006 - Game FPS measurement method (OVL-FPS): no ETW present tracing

Date: 2026-11-16. Ruled by a distinct adjudicator agent (CLAUDE.md FLEET
item 1). Inputs: CLAUDE.md "Game ToS floor", `docs/research/0001-ggg-tool-policy.md`,
`docs/decisions/0003-read-policy.md`, `docs/decisions/0002-stack.md`,
`docs/research/0007-overlay-tech.md` (PresentMon notes).

## Decision

NOT CLEARED: OVL-FPS does not use PresentMon or any ETW DxgKrnl / DXGI /
D3D9 Present-event tracing of the game, not even as a dev-only measurement.
Cleared methods:

1. The game's own in-game FPS / performance display, read by the human,
   same scene, overlay on vs off, recorded by hand.
2. System-wide OS counters only, e.g. the TOTAL of
   `\GPU Engine(*engtype_3D)\Utilization Percentage` and
   `\Processor(_Total)\% Processor Time`, or `nvidia-smi` GPU utilisation.
   They are never filtered or keyed to the game's PID.
3. Counters for AshLight's own processes (overlay, core): RAM, CPU, GPU
   engine. This is the overlay cost decision 0002 budgets.
4. Overlay on vs off over repeated runs, recording machine, display mode and
   the counter used; every write-up says it is a proxy, not a frame-time
   measure. Nothing from the measurement ships in the product.

Decision 0002's "PresentMon before / after" reads as "FPS before / after,
method per decision 0006".

## Alternatives

- Cleared with conditions (dev-only; ETW opens no handle to the game, reads
  no memory, injects and hooks nothing). Rejected: the floor's "READ ONLY
  what GGG permits" is an allowlist that does not name OS performance
  telemetry, and Present events keyed to the game's PID observe the game's
  rendering. No adjudicator can widen the floor.
- GPU-engine counters filtered by the game's PID: rejected for the same
  reason (per-game-process telemetry).
- Skip the measurement: rejected; the budget needs evidence.

## Why

No named prohibited act is clearly triggered by ETW; the allowlist reading
makes it ambiguous. Under ambiguity the non-intrusive, reversible choice
wins: a later clearance costs nothing, a wrong assumed clearance cannot be
undone.

## Record of use (2026-11-16)

The first overlay-off baseline taken before this ruling arrived also summed
the 3D-engine counter instances of the game's PID; that column was discarded
unused. Only system-wide totals and nvidia-smi are reported in decision 0002.

Note 2026-11-18 (RUN-BUDGET-LOG-CORE, landed 2026-11-20): AshLight's own-process
counters (method 3) are a Checks-class self-diagnostic and ship: the core's
budget log (server/al/budgetlog.py) records once a minute its own working set
and CPU (own handle), luajit's (its own Popen child handle, never a pid) and the
client's figures from overlay-state.json, tagged from AshLight's own state, in
a 1 MB capped file; the game process and window are never listed or opened. The
overlay on / off FPS measurement still never ships. Rulings, recorded: B9 is
checked only on a row that carries a supervisor figure (the core opens no other
process; alternative, a pid open of the supervisor, rejected by the floor); B12
is split out only while the companion is closed (one renderer = the overlay;
alternative, attributing renderer CPU by window, needs a per-window read the
client file does not carry); B18 is checked only on rows with fresh client
figures and the calc tag off; client figures older than 150 s are dropped.
Reverses if: the floor or decision 0029 changes, or the client file gains
per-window renderer figures (then B12 also with the companion open).

## Note 2026-11-21 (OVL-CHECK, F-128, ruling Q-18): budget B19

OVL-FPS is accepted on budget B19, documented as a proxy, not a frame-time
measure: (1) no change on the game's own FPS display with the HUD on, read
by the operator (method 1) and given as one answer, same or dropped;
(2) AshLight's own CPU (core plus client) under 1 percent of one core in
the shown and updating blocks (method 3); (3) system-wide CPU totals of the
shown and updating blocks within the noise of the hidden blocks (the larger
of their spread and 2 percentage points; method 2). B19 passes only when
all three hold; a missing answer leaves it pending, a 'dropped' answer
fails it. The numbers are recorded here (the OVL-FPS row), not in decision
0002, which is unchanged.

Method: tools/ovl_check.py, developer-only, stdlib, never started by the
shipped app; nothing under server/ or app/ exists for it
(tests/test_ovl_check.py scans for that). A session arms it (a flag in the
sidecar Logs dir, 24 h) and it starts one hidden runner. The runner waits
until the core's GET /api/state shows an open map for 20 s, then plays nine
30 s blocks (hidden, shown, updating, three times) through calls the core
already has: hidden = POST /api/overlay-layout with every overlay part off,
shown = the player's parts back, updating = POST /api/overlay-sample every
10 s plus an opacity nudge of 0.02 inside the layout limits every 5 s. The
player's layout is copied first and put back at the end, on any error, and
by the next run or `restore` if the runner died. Each second it reads the
core's own CPU and working set from the token-gated GET /api/debug (the
core's own handle), the client's figures from overlay-state.json (once a
minute, so the client part is coarse) and the system-wide CPU totals
(GetSystemTimes, never per process). It writes ovl_check-<stamp>.json and a
15-line ovl_check-<stamp>.txt in the sidecar Logs dir and clears the flag.
The answer comes from one console prompt, else the 'Tried in game' card
(OVL-FPS: Worked = same, Refused = dropped, read through GET /api/verdicts
for 15 min), else `python tools/ovl_check.py answer same|dropped`.

Rulings, recorded: the tool opens no process by pid and lists no process
(alternative, the pids of server/al/procs.py, rejected: overlay_pids walks
the system process list, which the floor and the budget log decline; the
client's own figure file carries the same numbers once a minute); no screen
capture and no input (Q-18 b); the hidden block keeps the failure words
that can never be switched off (they are part of the product); the check
is blind at a saturated GPU or an FPS cap and the display mode is not
detected, so the write-up names the operator's display mode by hand.
Reverses if: the client figure file gains a per-second rate (then client
CPU per block), the operator rules a pid-keyed read of AshLight's own
processes acceptable, or the existing calls stop producing an updating
load (then the question returns to the adjudicator with the evidence).

## Reverses if

GGG's tool policy or an official GGG statement explicitly permits ETW /
PresentMon-style tracing alongside the game (source and access date added to
research 0001), or the operator rules in their own words that the allowlist
includes OS performance telemetry.
