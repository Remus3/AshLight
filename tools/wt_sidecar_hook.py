"""WT-SIDECAR: Claude Code WorktreeCreate / WorktreeRemove hook (decision 0012).

Puts Agent-tool isolation worktrees under the AL sidecar Worktree folder
(server/al/paths.py worktree_dir(); AL_SIDECAR_ROOT overrides; without a
sidecar the resolver's in-repo default) instead of the repo's
.claude/worktrees/. Stdlib only. NOT wired into .claude/settings.json:
activation is an operator act (snippet in decision 0012).

Assumed hook contract (Claude Code hooks docs; no offline copy in the repo):
- stdin: JSON with hook_event_name, session_id, cwd, and for WorktreeCreate
  "name" (the worktree slug), for WorktreeRemove "worktree_path".
- WorktreeCreate: create the worktree, print its ABSOLUTE path as the only
  stdout line, exit 0; any non-zero exit fails the creation (stderr shown).
- WorktreeRemove: remove it; the result is informational.

Branch: worktree-<name>, from HEAD of the repo at "cwd" (reused when it
already exists). A re-run for an existing registered worktree at the same
path prints the path again (idempotent).
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.al import paths  # noqa: E402

SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True,
                          text=True, timeout=120)


def slug(name):
    s = SAFE.sub("-", str(name or "")).strip(".-")[:64]
    if not s:
        raise ValueError("empty worktree name")
    return s


def _registered(cwd):
    r = _git(cwd, "worktree", "list", "--porcelain")
    out = set()
    for line in r.stdout.splitlines():
        if line.startswith("worktree "):
            out.add(str(Path(line[9:]).resolve()).lower())
    return out


def create(payload, environ=None):
    cwd = Path(payload.get("cwd") or ".").resolve()
    name = slug(payload.get("name"))
    top = _git(cwd, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        raise RuntimeError("not a git repository: " + top.stderr.strip())
    base = paths.worktree_dir(environ)
    target = (base / name).resolve()
    if target.exists():
        if str(target).lower() in _registered(cwd):
            return target
        raise RuntimeError(f"path exists and is not a worktree: {target}")
    base.mkdir(parents=True, exist_ok=True)
    branch = "worktree-" + name
    has = _git(cwd, "rev-parse", "--verify", "--quiet", "refs/heads/" + branch)
    if has.returncode == 0:
        r = _git(cwd, "worktree", "add", str(target), branch)
    else:
        r = _git(cwd, "worktree", "add", "-b", branch, str(target), "HEAD")
    if r.returncode != 0:
        raise RuntimeError("git worktree add failed: " + r.stderr.strip())
    return target


def remove(payload, environ=None):
    wt = payload.get("worktree_path")
    if not wt:
        raise ValueError("worktree_path missing")
    target = Path(wt).resolve()
    base = paths.worktree_dir(environ).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        # Not ours (e.g. made before the hook): leave it to the harness default.
        return None
    cwd = Path(payload.get("cwd") or target).resolve()
    if not cwd.exists():
        cwd = target
    # No --force: a dirty worktree is refused, never cleaned.
    r = _git(cwd, "worktree", "remove", str(target))
    if r.returncode != 0:
        raise RuntimeError("git worktree remove failed: " + r.stderr.strip())
    return target


def main(argv=None, stdin=None, stdout=None, environ=None):
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    try:
        payload = json.loads(stdin.read() or "{}")
        event = payload.get("hook_event_name", "WorktreeCreate")
        if event == "WorktreeCreate":
            stdout.write(str(create(payload, environ)) + "\n")
        elif event == "WorktreeRemove":
            remove(payload, environ)
        else:
            raise ValueError("unsupported hook event: " + str(event))
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
        sys.stderr.write("wt_sidecar_hook: " + str(exc) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
