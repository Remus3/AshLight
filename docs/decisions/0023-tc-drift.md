# 0023 - TC-DRIFT: unattended PoB-PoE2 release check and pin trial

Date: 2026-11-17. Row: ROADMAP TC-DRIFT. Input: research 0017, decisions
0004 (item 3), 0018 (pin), 0022 (bridge). Ruled by the build lane itself
(FLEET item 1).

## Decision

1. `tools/tc_drift.py` (stdlib) owns the drift check. The al_loop tick calls
   `tc_drift.loop_check` once per tick; it is silent unless a check is due
   (at most one every 24 h, 3 h after a network error, and never before
   GitHub's `X-RateLimit-Reset` / `Retry-After`). The check is one read-only
   GET of `api.github.com/repos/<repo>/releases/latest` (the `releases`
   endpoint, not `tags`: research 0017) with the truthful AshLight
   User-Agent, no cookie, no token. State: gitignored
   `ops/runtime/tc_drift.json`.
2. A newer release tag launches ONE detached, windowless `tc_drift.py trial
   --tag <tag>` (relaunched only if it dies, at most 3 times per tag). The
   trial resolves the tag's commit, downloads the commit archive twice (sha
   and size must agree, as 0018 requires for a pin), writes a candidate pin
   file under the sidecar `Build\tc-drift\`, runs the opt-in setup step on
   it and then `tests/test_tc_bridge.py` and `tests/test_tc_delta.py` with
   `AL_TC_PINS_FILE` pointing at the candidate. Verdict: green (all passed,
   live tests ran), red, untested (live tests skipped: no luajit.exe on the
   host) or error.
3. The pin moves only through `tc_drift.py apply`, which refuses without a
   green trial and writes `config/tc_pins.json` (ASCII, LF) for one commit.
   The commit itself is made by a lane / operator session, not by the
   detached trial: the loop's tick line reads "trial green, pin move ready
   (tools/tc_drift.py apply)".
4. `paths.tc_pins_file()` honours `AL_TC_PINS_FILE` (set only by the trial
   subprocess) so the bridge resolves the candidate checkout; with the
   variable unset nothing changes.
5. A new live bridge test, `test_live_reload_does_not_leak_state` (load A,
   load B, reload A: A's outputs unchanged), is part of every trial, as
   research 0017 asks for the "Restore headless global cache cleanup"
   change before the pin moves.
6. A pin that stays gets a dated HOLD line in decision 0004 (`tc_drift.py
   note` prints it).

## Alternatives

- Auto-commit the pin from the detached trial: a commit outside the loop's
  gates / verifier / merge lock, racing lanes on main. Rejected; the trial
  only prepares a validated candidate.
- Poll `tags`: the repo carries PoE1-era v2.4x tags (research 0017).
  Rejected.
- Run the trial inside the tick: a 390 MB download twice and a LuaJIT run
  break the tick's 60 s target. Rejected; detached process.
- Authenticated GitHub API calls: would need a stored token. Not needed at
  one call a day. Rejected.

## Why

The ROADMAP ZERO-CLICK line wants the new tag spotted and the tests run
unattended; this does both with one daily GET and keeps the pin move behind
a green trial and an ordinary gated commit, as decision 0004 item 3 says.

## Reverses if

- GitHub rate limits or terms bar an unauthenticated daily release read.
- PoB-PoE2 stops publishing GitHub releases (then watch tags with a v0.x
  filter) or ships an official headless API (decision 0004).
- The loop gains a safe auto-commit path for data-only pin moves.
