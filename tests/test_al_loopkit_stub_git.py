"""TEST-LOOP-STUB-GIT: the no-spawn git stand-ins the tick tests opt into
(tests/al_loopkit.py stub_git) answer like the real ones they replace."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import al_loopkit as L  # noqa: E402
from al_loopkit import al_loop  # noqa: E402

pytestmark = pytest.mark.git


def _same_classes(a_keys, b_keys):
    """Two key sequences split the states into the same equality classes."""
    n = len(a_keys)
    return all((a_keys[i] == a_keys[j]) == (b_keys[i] == b_keys[j])
               for i in range(n) for j in range(n))


def test_py_tree_key_has_tree_key_equality(tmp_path, monkeypatch):
    L.isolate_git(monkeypatch)
    root, wt = L.git_world(tmp_path)
    real, py = [], []

    def snap(cwd):
        real.append(al_loop.tree_key(cwd))
        py.append(L.py_tree_key(cwd))

    snap(root)                                       # clean main
    snap(wt)                                         # dirty lane: feature.txt
    (root / "ops").mkdir(exist_ok=True)
    (root / "ops" / "x.json").write_text("{}\n", newline="\n")
    snap(root)                                       # ignored file: same key
    (root / "feature.txt").write_text("work\n", newline="\n")
    snap(root)                                       # main now has lane content
    (root / "feature.txt").write_text("other\n", newline="\n")
    snap(root)                                       # content change: new key
    (root / "feature.txt").write_text("work\n", newline="\n")
    L.git(root, "add", "-A")
    L.git(root, "commit", "-q", "-m", "f")
    snap(root)                                       # committed clean: same as dirty
    assert all(k for k in real) and all(k for k in py)
    assert _same_classes(real, py), (real, py)
    assert real[0] == real[2] and py[0] == py[2]
    assert real[1] == real[3] == real[5] and py[1] == py[3] == py[5]


def test_py_tree_key_outside_a_repo_is_none_like_tree_key(tmp_path):
    assert al_loop.tree_key(tmp_path) is None
    assert L.py_tree_key(tmp_path) is None


def test_ignore_rules_cover_plain_dir_and_glob_lines():
    rules = ["ops/", "*.log", "build/out"]
    assert L._ignored("ops/a/b.json", rules)
    assert L._ignored("x/y.log", rules)
    assert L._ignored("build/out/z", rules)
    assert not L._ignored("opsx/a", rules)
    assert not L._ignored("src/ops.py", rules)


def test_stub_default_git_matches_real_git_outside_a_repo(tmp_path):
    for args in (["log", "-1"], ["show", "HEAD:x"]):
        real = al_loop._git(args, tmp_path)
        stub = L.stub_default_git(args, tmp_path)
        assert stub.returncode == real.returncode == 128
        assert stub.stdout == real.stdout == ""
        assert isinstance(stub, subprocess.CompletedProcess)
    # config reads the host global config outside a repo (al_loop._git drops
    # GIT_*); the stub answers as a host with core.hooksPath unset does
    args = ["config", "core.hooksPath"]
    stub, real = L.stub_default_git(args, tmp_path), al_loop._git(args, tmp_path)
    assert (stub.returncode, stub.stdout) == (1, "")
    if real.returncode != 0:
        assert (real.returncode, real.stdout) == (1, "")


def test_stub_default_git_delegates_inside_a_repo(tmp_path, monkeypatch):
    L.isolate_git(monkeypatch)
    root, _wt = L.git_world(tmp_path)
    args = ["rev-parse", "--abbrev-ref", "HEAD"]
    assert L.stub_default_git(args, root).stdout == al_loop._git(args, root).stdout


COUNT_PROBE = (
    "import subprocess, sys\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "import al_loopkit\n"
    "subprocess.run(['git', '--version'], capture_output=True)\n"
    "subprocess.run([sys.executable, '-c', 'pass'])\n"
)


@pytest.mark.parametrize("flag, want", [("1", "git spawns: 1"), ("", None)])
def test_al_git_count_prints_the_git_spawn_total_at_exit(tmp_path, flag, want):
    import os
    env = dict(os.environ, AL_GIT_COUNT=flag)
    r = subprocess.run([sys.executable, "-c", COUNT_PROBE, str(Path(__file__).resolve().parent)],
                       capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=60)
    assert r.returncode == 0, r.stderr
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith("git spawns:")]
    assert lines == ([want] if want else [])


def test_deps_uses_the_stand_ins_only_when_opted_in(tmp_path, monkeypatch):
    root = L.make_root(tmp_path)
    d = L.deps(root)
    assert d.git is al_loop._git and d.tree_key is al_loop.tree_key
    L.stub_git(monkeypatch)
    d = L.deps(root)
    assert d.git is L.stub_default_git and d.tree_key is L.py_tree_key
    d = L.deps(root, git=L.real_git)
    assert d.git is L.real_git and d.tree_key is L.py_tree_key
