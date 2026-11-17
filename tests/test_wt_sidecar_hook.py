"""WT-SIDECAR (decision 0012): the WorktreeCreate hook puts worktrees under
the AL sidecar Worktree folder. Runs on a tmp git repo with AL_SIDECAR_ROOT
pointed at tmp_path; never touches this repo's worktrees."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from server.al import paths

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "tools" / "wt_sidecar_hook.py"

pytestmark = pytest.mark.git


def _git(cwd, *args):
    r = subprocess.run(["git", "-c", "core.hooksPath=", "-c", "user.name=t",
                        "-c", "user.email=t@example.com", "-C", str(cwd), *args],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    (r / "a.txt").write_text("a\n", encoding="ascii")
    _git(r, "add", "a.txt")
    _git(r, "commit", "-q", "-m", "init")
    return r


def _hook(payload, tmp_path):
    env = dict(os.environ)
    env[paths.SIDECAR_ENV] = str(tmp_path / "AL")
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=120, env=env)


def test_create_puts_worktree_under_sidecar(repo, tmp_path):
    p = {"hook_event_name": "WorktreeCreate", "session_id": "s", "cwd": str(repo),
         "name": "agent-abc123"}
    r = _hook(p, tmp_path)
    assert r.returncode == 0, r.stderr
    lines = r.stdout.splitlines()
    assert len(lines) == 1
    wt = Path(lines[0])
    assert wt.is_absolute()
    assert wt == (tmp_path / "AL" / "Worktree" / "agent-abc123").resolve()
    assert (wt / "a.txt").is_file()
    listed = _git(repo, "worktree", "list", "--porcelain")
    assert str(wt).replace("\\", "/").lower() in listed.replace("\\", "/").lower()
    assert _git(wt, "rev-parse", "--abbrev-ref", "HEAD").strip() == "worktree-agent-abc123"
    assert not (repo / ".claude" / "worktrees").exists()
    # idempotent: same name again prints the same path
    r2 = _hook(p, tmp_path)
    assert r2.returncode == 0, r2.stderr
    assert Path(r2.stdout.strip()) == wt
    # remove
    r3 = _hook({"hook_event_name": "WorktreeRemove", "cwd": str(repo),
                "worktree_path": str(wt)}, tmp_path)
    assert r3.returncode == 0, r3.stderr
    assert not wt.exists()


def test_name_is_sanitised_and_stays_inside_sidecar(repo, tmp_path):
    r = _hook({"hook_event_name": "WorktreeCreate", "cwd": str(repo),
               "name": "../../evil name"}, tmp_path)
    assert r.returncode == 0, r.stderr
    wt = Path(r.stdout.strip())
    wt.relative_to((tmp_path / "AL" / "Worktree").resolve())
    assert wt.name == "evil-name"


def test_failures_exit_nonzero(repo, tmp_path):
    assert _hook({"hook_event_name": "WorktreeCreate", "cwd": str(repo), "name": ""},
                 tmp_path).returncode == 1
    plain = tmp_path / "plain"
    plain.mkdir()
    r = _hook({"hook_event_name": "WorktreeCreate", "cwd": str(plain), "name": "x"}, tmp_path)
    assert r.returncode == 1 and "wt_sidecar_hook" in r.stderr
    # an existing non-worktree dir at the target is refused, never reused
    (tmp_path / "AL" / "Worktree" / "busy").mkdir(parents=True)
    r = _hook({"hook_event_name": "WorktreeCreate", "cwd": str(repo), "name": "busy"}, tmp_path)
    assert r.returncode == 1


def test_remove_ignores_paths_outside_sidecar(repo, tmp_path):
    r = _hook({"hook_event_name": "WorktreeRemove", "cwd": str(repo),
               "worktree_path": str(repo)}, tmp_path)
    assert r.returncode == 0, r.stderr
    assert repo.exists()


def test_worktree_dir_resolves_under_sidecar(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.SIDECAR_ENV, str(tmp_path / "AL"))
    assert paths.worktree_dir() == (tmp_path / "AL" / "Worktree").resolve()
    monkeypatch.delenv(paths.SIDECAR_ENV)
    assert paths.worktree_dir() == paths.sidecar_root() / "Worktree"
