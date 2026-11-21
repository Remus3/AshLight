# 0025 - TC-DRIFT: unattended PoB-PoE2 release check and pin trial

Date: 2026-11-17. Row: ROADMAP TC-DRIFT. Input: research 0017, decisions
0004 (item 3), 0018 (pin), 0022 (bridge). Ruled by the build lane itself
(FLEET item 1).

Renumbered from 0023 to 0025 on 2026-11-17 (AREA-AUDIT batch 4): 0023 is
act-splits-resume and 0024 tc-delta on main; the lane drafted it against an
older main. tests/test_audit_pass2.py fails on any duplicate number.

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

## Amendment 2026-11-17 (AREA-AUDIT P3-9, P3-8)

Ruled by the adjudicator agent (FLEET item 1): combine "static checks only
unattended" with an opt-in switch.

- Decision: the unattended TC-DRIFT trial runs download, double hash,
  extract and the static drift-guard tests only (tests/test_tc_pob_drift_guard.py
  `-k "not test_live"`: reads the candidate's Lua, runs none of it); verdict
  `static-green` / `static-red` / `untested` / `error`. Live luajit
  execution of candidate Lua needs `tc_drift.py trial --tag X --live` (a
  manual trigger) or `config/local.json` `"tc_drift_live_unattended": true`
  (a real boolean, default off; no env var enables it). `apply` requires
  `live-green` from a live trial; static-green never moves the pin. The
  trial child runs `python -I -m pytest` with a hard timeout, cwd the repo
  (never the extracted tree). Item 2's "runs the bridge tests" and item 3's
  "green" now read as above.
- P3-8: item 4 narrowed. `paths.tc_pins_file()` honours `AL_TC_PINS_FILE`
  only inside a pytest run (`pytest` in sys.modules: the trial child and
  the suite). The core and setup never import pytest, so the variable
  cannot move their trust root.
- Alternatives: (A) opt-in only, leaving unattended execution the only live
  path with no static tier; (B) a sandboxed live run, not possible without
  admin or firewall rules on stdlib Windows (false assurance); status quo,
  unreviewed upstream Lua run unattended.
- Why: no unreviewed upstream code runs by default, the static tier keeps
  early drift detection, and the opt-in keeps ZERO-CLICK for an operator
  who accepts the risk; apply's live-green gate keeps a review in front of
  the pin move. No GGG ToS surface change.
- Reverses if: PoB-PoE2 releases become signed or otherwise verifiable, a
  real OS sandbox is available without admin, or the operator rules
  unattended live trials acceptable by default.
- Tests: tests/test_tc_drift.py test_p3_9_* and test_p3_8_*.

## Amendment 2026-11-18 (AUTO-12, TC-DRIFT-TRIAL-FIX part 1, F-064)

- Decision: after setup a trial re-hashes every `pob2_files` entry from the extracted candidate checkout (read as data, never run; the checkout must carry the candidate archive's marker), moves the candidate pin's entries to the new sha256, size and commit, and records old hash, new hash and the parsed row count (decision 0037 amendment parser) in the trial state for review at apply (`apply` prints one review line per file; a file the candidate lacks keeps its old entry so the static guard reports it); candidates other than the pin and the newest (this trial's) are pruned: `<repo name>-<commit>` checkouts and `.zip` archives in the sidecar pob2 cache and `<tag>-pins.json` / `<tag>-junit.xml` in the sidecar `Build\tc-drift\`, by the Recycle Bin only (FLEET item 9), left in place when the recycle fails or no safe method exists (off Windows). Alternatives: keep the pin's old hashes in the candidate (the static guard can never end green after an upstream data change); prune by direct unlink or by newest tag number (a manual trial of an older tag would drop the candidate apply needs). Why: a trial that can end green, the reviewer sees what data changed before the pin moves, and the sidecar keeps at most two PoB-PoE2 trees. Reverses if: the guard stops reading pob2_files, a pruned candidate is needed for a rollback in practice, or the Recycle Bin call proves unreliable for large trees. Candidate Lua still runs only on the manual trigger. Tests: tests/test_tc_drift.py test_trial_rehashes_pob2_files_and_records_old_new_and_rows, test_candidates_other_than_pin_and_newest_are_pruned.

## Amendment 2026-11-18 (LOOP-WATCH-WIRE, rulings Q-12 and Q-13; cross-reference 0044)

- Decision: the tick may commit add-only row files
  (`docs/roadmap/new|done/<ID>.md`) built from tracked templates and
  validated tokens, at most 3 of each kind a local day, with the operator
  identity, only through the kit git lock, never while HALT exists; the
  release check reads in front of the HALT return and acts on nothing
  while HALTed; pin moves stay session commits. The release check is now
  the pob-release source of tools/upstream_watch.py (decision 0069), run
  from the tick's one step module tools/loop_steps/upstream_watch.py in
  front of the HALT test beside the decision 0044 docs watch; the read
  still goes through the tick's drift seam, its line is still one tick
  line, and its 24 h throttle and User-Agent are unchanged. While HALTed
  the read, the record and the static trial happen (Q-13: no live trial,
  no row file, no pin move, no commit); on the live checkout a drift seam
  without a `halted` argument is replaced for that tick by
  `tc_drift.loop_check(halted=True)`. Queued findings are filed after the
  work list by tools/watch_file.py on the first tick without HALT.
- Alternatives: edit ROADMAP.md in place (merge conflicts with waves);
  report only (rows wait for a human); keep the release check in the work
  phase (no read while HALTed, so drift is seen only after HALT goes).
- Why: an unattended commit that can only add a file cannot break a row or
  a wave merge, and a HALT-time read lets drift be seen while HALT stands
  and acted on the first tick after it goes.
- Reverses if: a tick commit ever touches a non-row path, a bad row lands,
  tokens fail validation, GitHub limits bar the daily read, or the
  operator rules unattended commits or HALT-time reads unwanted.
- Tests: tests/test_watch_wire.py.
