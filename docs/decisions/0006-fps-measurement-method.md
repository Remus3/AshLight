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

## Reverses if

GGG's tool policy or an official GGG statement explicitly permits ETW /
PresentMon-style tracing alongside the game (source and access date added to
research 0001), or the operator rules in their own words that the allowlist
includes OS performance telemetry.
