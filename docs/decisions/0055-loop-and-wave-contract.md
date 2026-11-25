# 0055 - Loop and wave contract: the loop and a session never work one row

Date: 2026-11-18. Source: package AUTO-06 (wave 5) with its split half
LOOP-WAVE-HOLD; finding F-033 (WAVE-INTERPLAY) and F-078 (the six checks)
in docs/plan/02-findings.md; decision 0077 (execution model, HALT removal
point). Code: tools/loop_work.py (reason echo, dispatch re-check),
tools/loop_merge.py (folder hold, merge lock; LOOP-WAVE-HOLD). Tests:
tests/test_loop_wave.py, tests/test_loop_wave_hold.py.

## Decision

1. BLOCKED means not for the loop. A ROADMAP row (in ROADMAP.md or a
   docs/roadmap/new/ file) whose text carries the upper-case word BLOCKED
   is listed in the loop's checklist and never dispatched. Its reason is
   written after `BLOCKED:`: `session wave <n>`, `session`, `operator act`
   or `gate`. The work list echoes the text after `BLOCKED:` up to the next
   full stop, at most 60 characters (a longer one is cut and ends in
   `...`), as `BLOCKED: <reason>` on the checklist row. A bare BLOCKED with
   no reason reads `BLOCKED: operator act (see ROADMAP)`, the old fixed
   wording.
2. Hand-off bullets. A hand-off bullet is loop work only when it starts
   with `LOOP:`; BLOCKED applies to it as to a row (LOOP-HANDOFF-PREFIX,
   unchanged here).
3. Tag, then read: the claim. A session that takes an untagged row first
   commits its `BLOCKED: session` (or `session wave <n>`) tag on main, then
   reads ops/loop/control/loop_items/<ID>.json; when the loop already holds a live
   record for the row (dispatched, ran, committed or merging), the loop's
   record wins and the session drops its tag and leaves the row.
4. Dispatch re-check. Inside the tick lock, right before a row is
   dispatched (also in a dry run), the tick re-reads that row as committed
   at HEAD of the main checkout (`git show HEAD:ROADMAP.md`, plus
   `HEAD:docs/roadmap/new/<ID>.md` and the `HEAD:docs/roadmap/done/<ID>.md`
   mark, composed as tools/roadmap.py load_rows does), and then the main
   tree's rows through the tools/roadmap.py loader. A BLOCKED tag or a
   close found in either read skips the row with the log line
   `<ID>: not dispatched, <reason> (at HEAD|main tree)`; no item record is
   written, so the next work list shows it as blocked. A HEAD that cannot
   be read, or holds no such row, is no evidence: the main tree read
   decides alone.
5. Folder hold (LOOP-WAVE-HOLD). While a wave owns folders it writes
   ops/loop/control/wave_owned.json (wave, prefixes, time); a loop merge
   whose diff touches a held prefix parks as wave-hold and merges once the
   file is gone; a hold file older than 48 h is one checklist row and is
   not obeyed. The session that ends a wave flips its rows and removes the
   hold file.
6. Shared merge lock (LOOP-WAVE-HOLD). A wave's merge agent merges under
   the loop's merge lock: `python tools/loop_merge.py hold -- <command>`
   (exit 3 when the lock stays busy past --wait-s).
7. The six checks. HALT is removed only by AUTO-21 after the six checks of
   F-078 read back green (decision 0077 item 9): plan rows in ROADMAP and
   the lint green; every session row tagged; the hand-off yields 0 loop
   items; preflight green with the client running; the gate under half
   the cap; a dry-run tick lists only intended rows as would dispatch.

## Alternatives

- A lock file per row instead of the tag: rejected, a second claim channel
  next to the ROADMAP text, and a crashed session leaves a stale lock the
  loop cannot see in the row itself.
- Re-check only the working tree (no HEAD read): rejected, a session's
  committed tag is the claim (item 3), and the main checkout's working
  file may lag or lead it; reading both costs at most three `git show`
  calls per dispatched row.
- Fail closed when HEAD cannot be read: rejected, a tree without a
  readable HEAD (tests, a fresh clone mid-setup) would never dispatch;
  the main tree read still applies, which is the pre-0055 behaviour.
- A free-length reason: rejected, the checklist is read on a phone; 60
  characters keep one line.

## Why

F-033: a row worked by the loop and a session at once costs two runs and
a merge conflict. The tag is visible in the row the loop already reads, the
re-check closes the window between the work list and the launch, and the
reason echo tells the operator at a glance why a row waits.

## Reverses if

A row is worked twice in practice, or the tag traffic on ROADMAP.md causes
merge conflicts.

## Amendment 2026-11-24 (LOOP-NOCHANGE-OPEN)

Decision: a plan item whose lane exits rc 0 with a clean worktree and no
blocked marker, while its ROADMAP row (main tree, through the loader) is
still open, is recorded "refused" with the error "no change, row still
open", not "no-change": dispatchable() retries it up to MAX_ATTEMPTS and
reap_lost() then makes it gave-up, which the checklist lists. A closed,
missing or unreadable row, and any non-plan item, keeps the plain
"no-change" done state. The checklist also lists any existing "no-change"
record whose row is still open, with the state "no-change, row still open"
(loop_base.NO_CHANGE_OPEN), so records written before this amendment are
seen. The lane allow-list (tools/al_lane.py GATE_TOOLS) gains
`Bash(python tools/docs_fresh.py:*)`, which makes no request and writes
nothing (DOCS-FRESH); tools/electron_pin.py stays out, since it fetches and
writes the sidecar Cache, so an Electron bump stays a session task.

Alternatives: drop "no-change" from DONE_STATES (rejected: closed rows and
non-plan items would be listed and retried forever); a new state with its
own retry rule (rejected: refused already carries the MAX_ATTEMPTS bound and
the gave-up hand-off); grant every tool a row names (rejected: a fetch or a
write outside the worktree must stay a session act).

Why: rows DOCS-FRESH-20261121 and ELECTRON-45-4-1 were open in ROADMAP.md
but never dispatched again and never shown, because an empty run (the lane
was refused a tool) landed in a done state. A refusal must be bounded and
visible, never silent.

Reverses if: a row that is legitimately left open after a clean run (work
done elsewhere, row not yet flipped) is retried often enough to waste runs,
or the kit gains its own empty-run state.
