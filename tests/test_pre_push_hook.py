"""GP-02 (docs/plan/04-go-public.md, decision 0046): the guarded pre-push hook.

Real git under tmp_path: a work repo whose core.hooksPath is a copy of
.githooks, with copies of the kit identity gate and the leak sweep at the
same relative paths, and a local bare repo as origin. No network remote is
ever used. Each case asserts the push return code and the bare repo's refs.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / ".githooks" / "pre-push"
OPERATOR = ("Op Erator", "op@example.com")
REFUSED = "pre-push: refused"

pytestmark = pytest.mark.git


def _git_sh():
    git = shutil.which("git")
    if not git:
        return None
    if shutil.which("sh"):
        return git
    try:
        exec_path = subprocess.run([git, "--exec-path"], capture_output=True, text=True,
                                   timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    if not exec_path:
        return None
    base = Path(exec_path).parents[2]
    for cand in (base / "bin" / "sh.exe", base / "usr" / "bin" / "sh.exe"):
        if cand.is_file():
            return git
    return None


if _git_sh() is None:
    pytest.skip("git or its sh is not available", allow_module_level=True)


class World:
    def __init__(self, tmp_path):
        self.tmp = tmp_path
        self.work = tmp_path / "work"
        self.bare = tmp_path / "origin.git"
        self.nohooks = tmp_path / "nohooks"
        self.nohooks.mkdir()
        gcfg = tmp_path / "empty.gitconfig"
        gcfg.write_text("", encoding="ascii")
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("GIT_", "AL_LEAK_NEEDLES", "AL_ALLOW_PUSH"))}
        env["GIT_CONFIG_GLOBAL"] = str(gcfg)
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
        self.env = env
        self.git_in(tmp_path, "init", "-q", "--bare", "-b", "main", str(self.bare))
        self.work.mkdir()
        self.git("init", "-q", "-b", "main")
        hooks = self.work / ".githooks"
        shutil.copytree(ROOT / ".githooks", hooks)
        for p in hooks.iterdir():
            p.chmod(0o755)
        for rel in ("ops/fleet_kit/fleet_identity.py", "tools/leak_sweep.py"):
            dst = self.work / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, dst)
        self.git("config", "core.hooksPath", str(hooks))
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "user.name", OPERATOR[0])
        self.git("config", "user.email", OPERATOR[1])
        self.git("config", "--add", "fleet.operatorIdent", f"{OPERATOR[0]} <{OPERATOR[1]}>")
        self.git("remote", "add", "origin", str(self.bare))
        # the hook runs the copies from the work tree; they are never committed
        (self.work / ".git" / "info" / "exclude").write_text(
            "/.githooks/\n/ops/\n/tools/\n", encoding="ascii", newline="\n")
        self.commit("README.txt", "hello\n", "first commit")

    def git_in(self, cwd, *args, env=None, check=True):
        r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                           env=env or self.env, timeout=180)
        if check and r.returncode != 0:
            raise AssertionError(f"git {args} rc={r.returncode}: {r.stderr}")
        return r

    def git(self, *args, **kw):
        return self.git_in(self.work, *args, **kw)

    def commit(self, name, text, msg, author=None):
        path = self.work / name
        path.write_text(text, encoding="ascii", newline="\n")
        self.git("-c", f"core.hooksPath={self.nohooks}", "add", "-A")
        extra = ["--author", author] if author else []
        self.git("-c", f"core.hooksPath={self.nohooks}", "commit", "-q", "-m", msg, *extra)
        return self.rev("HEAD")

    def rev(self, ref):
        return self.git("rev-parse", ref).stdout.strip()

    def push(self, *args, extra_env=None):
        env = dict(self.env, **(extra_env or {}))
        return self.git("push", "origin", *args, env=env, check=False)

    def remote_refs(self):
        out = self.git_in(self.bare, "for-each-ref", "--format=%(refname) %(objectname)").stdout
        return dict(ln.split() for ln in out.splitlines() if ln.strip())


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


@pytest.fixture
def pushed(world):
    r = world.push("main")
    assert r.returncode == 0, r.stderr
    return world


def _refused(r):
    return r.returncode != 0 and REFUSED in r.stderr


# 1 + 2
def test_clean_commit_pushes_and_fast_forwards(world):
    r = world.push("main")
    assert r.returncode == 0, r.stderr
    assert world.remote_refs() == {"refs/heads/main": world.rev("main")}
    world.commit("b.txt", "second\n", "second commit")
    r = world.push("main")
    assert r.returncode == 0, r.stderr
    assert world.remote_refs() == {"refs/heads/main": world.rev("main")}


# 3
def test_drive_rooted_path_is_refused_by_the_leak_sweep(pushed):
    before = pushed.remote_refs()
    drive = chr(ord("A") + 16) + ":" + "\\" + "\\".join(("zz", "yy", "file.txt"))
    pushed.commit("leak.txt", f"see {drive}\n", "add a note")
    r = pushed.push("main")
    assert r.returncode != 0
    assert "HALT" in r.stderr and "drive-path" in r.stderr
    assert pushed.remote_refs() == before


ALLOW = [{}, {"AL_ALLOW_PUSH": "1"}]  # 10: the old override changes nothing


# 4
@pytest.mark.parametrize("extra", ALLOW)
def test_lane_and_keep_refs_are_refused(pushed, extra):
    before = pushed.remote_refs()
    pushed.git("branch", "fleet-lanes/x")
    pushed.git("branch", "al/keep/x")
    pushed.git("update-ref", "refs/fleet-lanes/x", "HEAD")
    pushed.git("update-ref", "refs/al/keep/x", "HEAD")
    for spec in ("refs/heads/fleet-lanes/x", "refs/heads/al/keep/x",
                 "refs/fleet-lanes/x:refs/fleet-lanes/x",
                 "refs/al/keep/x:refs/al/keep/x"):
        r = pushed.push(spec, extra_env=extra)
        assert _refused(r), (spec, r.returncode, r.stderr)
    assert pushed.remote_refs() == before


# 5
@pytest.mark.parametrize("extra", ALLOW)
def test_delete_is_refused(pushed, extra):
    before = pushed.remote_refs()
    r = pushed.push(":main", extra_env=extra)
    assert _refused(r), r.stderr
    assert "deleting" in r.stderr
    assert pushed.remote_refs() == before


# 6
@pytest.mark.parametrize("extra", ALLOW)
def test_renamed_targets_are_refused(pushed, extra):
    before = pushed.remote_refs()
    pushed.commit("c.txt", "c\n", "third commit")
    for spec in ("main:other", "HEAD:main"):
        r = pushed.push(spec, extra_env=extra)
        assert _refused(r), (spec, r.stderr)
    assert pushed.remote_refs() == before


# 7
@pytest.mark.parametrize("extra", ALLOW)
def test_release_tag_pushes_once_and_never_moves(pushed, extra):
    pushed.git("tag", "v0.0.1")
    r = pushed.push("v0.0.1", extra_env=extra)
    assert r.returncode == 0, r.stderr
    tag_sha = pushed.rev("v0.0.1")
    assert pushed.remote_refs()["refs/tags/v0.0.1"] == tag_sha
    pushed.commit("d.txt", "d\n", "fourth commit")
    pushed.git("tag", "-f", "v0.0.1")
    r = pushed.push("--force", "v0.0.1", extra_env=extra)
    assert _refused(r), r.stderr
    assert pushed.remote_refs()["refs/tags/v0.0.1"] == tag_sha
    pushed.git("tag", "rc1")
    r = pushed.push("rc1", extra_env=extra)
    assert _refused(r), r.stderr
    assert "refs/tags/rc1" not in pushed.remote_refs()


# 8
@pytest.mark.parametrize("extra", ALLOW)
def test_forced_rewind_of_main_is_refused(pushed, extra):
    pushed.commit("e.txt", "e\n", "fifth commit")
    assert pushed.push("main").returncode == 0
    before = pushed.remote_refs()
    pushed.git("reset", "-q", "--hard", "HEAD~1")
    r = pushed.push("--force", "main", extra_env=extra)
    assert _refused(r), r.stderr
    assert "fast-forward" in r.stderr
    assert pushed.remote_refs() == before


# 9
@pytest.mark.parametrize("extra", ALLOW)
def test_bot_author_is_refused_by_the_identity_gate(pushed, extra):
    before = pushed.remote_refs()
    pushed.commit("f.txt", "f\n", "bump", author="dependabot[bot] <bot@example.com>")
    r = pushed.push("main", extra_env=extra)
    assert r.returncode != 0
    assert "IDENTITY" in r.stderr + r.stdout
    assert pushed.remote_refs() == before


# 11
def test_hook_text_is_ascii_lf_sh():
    data = HOOK.read_bytes()
    data.decode("ascii")
    assert b"\r" not in data
    assert data.startswith(b"#!/bin/sh\n")
    text = data.decode("ascii")
    assert "AL_ALLOW_PUSH" not in text and "PUSH REFUSED" not in text
