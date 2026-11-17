# 0012 - Agent worktrees under the sidecar via a WorktreeCreate hook

Date: 2026-11-17. Trigger: ROADMAP row WT-SIDECAR (Agent-tool isolation
worktrees land in the repo's gitignored .claude/worktrees/, but the Sidecar
rule puts worktrees under the AL sidecar Worktree folder).

## Decision

- `tools/wt_sidecar_hook.py` (stdlib) handles the Claude Code
  WorktreeCreate and WorktreeRemove hook events. Create: `git worktree add`
  at `server/al/paths.py worktree_dir()/<name>` (the AL sidecar
  `Worktree\`; AL_SIDECAR_ROOT overrides; with no sidecar the resolver's
  in-repo default), branch `worktree-<name>` from HEAD (reused if it
  exists), name sanitised to `[A-Za-z0-9._-]`, prints the absolute path as
  its only stdout line, exits 1 with a stderr reason on failure. A rerun
  for an existing registered worktree prints the same path; any other
  existing dir there is refused. Remove: `git worktree remove` (no
  --force, a dirty worktree is refused) only for paths under that folder.
- Assumed contract (no offline copy of the hooks docs in the repo): stdin
  JSON with hook_event_name, cwd, and `name` (create) or `worktree_path`
  (remove); stdout path, exit 0 = success.
- NOT wired in. Activation is an operator act (harness configuration):
  add to `.claude/settings.json` under "hooks":

      "WorktreeCreate": [{"hooks": [{"type": "command",
        "command": "python \"$CLAUDE_PROJECT_DIR/tools/wt_sidecar_hook.py\""}]}],
      "WorktreeRemove": [{"hooks": [{"type": "command",
        "command": "python \"$CLAUDE_PROJECT_DIR/tools/wt_sidecar_hook.py\""}]}]

  Then spawn one isolated agent and check its cwd is under the sidecar
  `Worktree\`.

## Notes 2026-11-17 (WT-SIDECAR build lane, round 2; no Settled change)

- Contract checked against the live Claude Code hooks reference
  (code.claude.com/docs/en/hooks, read 2026-11-17): WorktreeCreate gets
  `name`, prints the absolute path as the last non-empty stdout line, any
  non-zero exit fails creation; WorktreeRemove gets `worktree_path`, exit 0
  counts as removed; neither event takes a matcher (ignored if given). The
  script already matches; no code change.
- The lane tried to wire the snippet itself (FLEET item 1, act) and the
  harness refused the write: `.claude/settings.json` is protected from
  agent edits. Activation therefore stays an operator act. Alternatives:
  a session edit (same protection), a settings.local.json (also under
  .claude/, same protection, and untracked so lanes would not get it).
- Tests: `tests/test_wt_sidecar_hook.py` now runs the exact snippet
  command end to end (fresh agent name -> path under the sidecar
  `Worktree\`, then removed), pins the snippet text in this file, and
  checks the wiring in settings.json: it skips while unwired and fails on
  a half or wrong wiring once the operator pastes it.
- Known gap (accepted): WorktreeRemove ignores paths outside the sidecar
  folder and exits 0, so a pre-hook `.claude/worktrees/` entry is left on
  disk (gitignored). Why: the hook never deletes outside its own folder.
  Reverses if: stale entries there become a problem; then remove them by
  hand once.

## Alternatives

- Leave .claude/worktrees/: gitignored, nothing leaks, but breaks the
  Sidecar placement rule.
- A harness setting for the worktree base dir: none known; if one ships,
  prefer it over the hook.
- Kit `fleet_lanes.worktree_path`: names lane worktrees by index
  (lane-<i>), not by the harness's per-agent name; reused only for the
  folder.

## Reverses if

The harness gains a worktree base-dir setting, the real hook contract
differs (then adapt the script), or the hook makes isolated spawns fail.
