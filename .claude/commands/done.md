---
description: End-of-session ritual - gate, commit (never push, local only), paperwork, rewrite AL-NEXT-SESSION.txt carrying forward every unacted item, then print ONLY "Done ritual complete, safe to clear".
---

> **CHAT OUTPUT CONTRACT (FLEET items 2, 3, 5).** /done's ONLY chat output is the
> single line `Done ritual complete, safe to clear`, or one line
> `/done stopped: <reason>`. No banner, recap, checklist, hand-off or
> next-session prompt in chat. Everything else goes into `AL-NEXT-SESSION.txt`.

> **DISPATCH (kit v10):** the main session runs no tool for /done; it dispatches
> the whole ritual to ONE background sub-agent and relays only that agent's
> final line verbatim.

Every step is idempotent: re-running /done after a partial run finishes the
remaining steps and repeats nothing destructive.

### 0. Pre-flight

- Every session-checklist task is done or carried into the hand-off (FLEET
  item 13). Triage `moon_sync_inbox/` with `fleet_inbox.classify()`; ANSWER /
  ACK / INFORMATION / TERMINAL are recorded, never answered.

### 1. Local gate - commit only when green

- `git status -s` - identify this session's files.
- `python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python -m pytest -q`
  (`<id>` = this agent's claims owner id `<session_id>.<agent_id>`).
- `npm test --prefix app` when `app/node_modules` exists.
- `python tools/leak_sweep.py --tree` - must print no HALT.
- Run fresh this turn; never carry a sub-agent's green forward. RED: fix and
  re-run; a pre-existing unrelated red becomes the hand-off's first action.

### 2. Commit (batched, coherent; NEVER push - the repo is local only)

- Refuse to stage `config/local.json`, `config/leak_needles.json`, `.env*`,
  `*.key`, `*.pem`, anything under `ops/runtime/` or the sidecar.
- Stage named files only, never `git add -A`.
- `python ops/fleet_kit/fleet_gitlock.py run --owner <id> -- git commit ...`
- Body records adjudicated decisions (decision / alternatives / why).
- No AI / bot attribution line (FLEET-COMMON 17). Never `--amend`, never
  `--no-verify`.

### 3. Background work

- Running agents / lane runs are NOT killed; record each as in flight with its
  progress file and ETA.

### 4. Paperwork

- `ROADMAP.md`: flip finished rows, add new open rows as lanes.
- New settled decisions: `docs/decisions/` plus one CLAUDE.md "Settled" line.

### 5. Reap finished worktrees (kit v22)

    python ops/fleet_kit/fleet_done.py reap --apply

Record its summary line in the hand-off as a `NOTE:` bullet.

### 6. Hand-off - ALWAYS, never skipped

1. READ the current `AL-NEXT-SESSION.txt`.
2. Every unacted item is copied forward verbatim or tighter. Never drop one.
3. Add this session's items from ground truth.

```
AL NEXT SESSION
---------------
SESSION: <n+1>   (FLEET item 13 counter: the previous SESSION line plus one)
Next action: <the one thing "continue" should work on>
Carried forward (not acted on yet): <every unacted item>
Context: <files / live state to probe first>
Acceptance: <how the next session knows it is done>
Do NOT redo: <shipped this session that still looks open>
In flight: <lane / agent, progress file, ETA>
Status: <commits / gates / server health>
Start with: read this file, then CLAUDE.md, ROADMAP.md, git log -10.
```

Overwrite the whole file and read it back (the read-back is the recorded act).
Then `python ops/fleet_kit/fleet_done.py archive --auto`, then commit the
hand-off (and any archive file) through the git lock.

### 7. Status board (FLEET-COMMON item 18 - LOCAL ONLY)

Skip unless ops/status_board.json holds "opt_in": true or the operator asked
for the board this session (AL board is opt-out, operator order 2026-11-17).
Otherwise pipe the last printed checklist into
`python ops/fleet_kit/fleet_board.py render --final --session <n>`. A failed
render is one hand-off line, never a ritual failure.

### 8. Done marker, then ONE line

    python ops/fleet_kit/fleet_done.py mark --session <n> --status done

(on a stop: `--status failed --reason "<step>"`). Then print
`Done ritual complete, safe to clear` - or `/done stopped: <reason>`.

### Safety rails

- Never push, force-push, `--amend` or `--no-verify`. Never commit secrets.
- Never run `/clear` yourself. Never touch the game client in any step.
