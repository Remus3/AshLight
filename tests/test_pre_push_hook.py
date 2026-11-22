"""GP-02 (docs/plan/04-go-public.md, decision 0046): the guarded pre-push hook.

Real git under tmp_path: a work repo whose core.hooksPath is a copy of
.githooks, with copies of the kit identity gate and the leak sweep at the
same relative paths, and a local bare repo as origin. No network remote is
ever used. Each case asserts the push return code and the bare repo's refs.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / ".githooks" / "pre-push"
# Files a hook run needs in a temp repo; the Repo fixture of
# tests/test_dependabot_reapply.py lists the same ones (checked below).
HOOK_FILES = ("ops/fleet_kit/fleet_identity.py", "tools/leak_sweep.py",
              "tools/push_guard.py", "tools/release.py", "tools/rel_publish.py",
              "tools/rel_build.py", "tools/rel_version.py", "tools/rel_readback.py",
              "server/al/paths.py")
OPERATOR = ("Op Erator", "op@example.com")
REFUSED = "pre-push: refused"
# Synthetic needles only; the hook test never spells a real one.
NEEDLES = ["Zorblax Quux", "acct-0000-fake"]

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
        self.sidecar = tmp_path / "sidecar"
        env["AL_SIDECAR_ROOT"] = str(self.sidecar)
        env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
        self.env = env
        self.git_in(tmp_path, "init", "-q", "--bare", "-b", "main", str(self.bare))
        self.work.mkdir()
        self.git("init", "-q", "-b", "main")
        hooks = self.work / ".githooks"
        shutil.copytree(ROOT / ".githooks", hooks)
        for p in hooks.iterdir():
            p.chmod(0o755)
        for rel in HOOK_FILES:
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
            "/.githooks/\n/ops/\n/tools/\n/config/\n", encoding="ascii", newline="\n")
        self.cfg = self.work / "config" / "leak_needles.json"
        self.cfg.parent.mkdir()
        self.cfg.write_text('{"needles": ["%s", "%s"]}\n' % tuple(NEEDLES), encoding="ascii",
                            newline="\n")
        self.commit("README.txt", "hello\n", "first commit")

    def stage_pass(self, version, ref="HEAD"):
        """A PASS stage report of version at ref's commit (plan 05 fixture)."""
        d = self.sidecar / "Build" / "release" / version
        d.mkdir(parents=True, exist_ok=True)
        rep = {"verdict": "PASS", "version": version,
               "commit": self.rev(ref + "^{commit}"),
               "created": "2026-01-01T00:00:00Z", "sums_sha256": "a" * 64}
        (d / "stage.json").write_text(json.dumps(rep), encoding="ascii", newline="\n")

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
        if isinstance(text, bytes):
            path.write_bytes(text)
        else:
            path.write_text(text, encoding="ascii", newline="\n")
        return self.commit_staged(msg, author)

    def commit_staged(self, msg, author=None):
        self.git("-c", f"core.hooksPath={self.nohooks}", "add", "-A")
        extra = ["--author", author] if author else []
        self.git("-c", f"core.hooksPath={self.nohooks}", "commit", "-q", "-m", msg, *extra)
        return self.rev("HEAD")

    def rev(self, ref):
        return self.git("rev-parse", ref).stdout.strip()

    def push(self, *args, extra_env=None, config=()):
        env = dict(self.env, **(extra_env or {}))
        pre = [x for c in config for x in ("-c", c)]
        return self.git(*pre, "push", "origin", *args, env=env, check=False)

    def blob(self, data):
        r = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=str(self.work),
                           input=data, capture_output=True, env=self.env, timeout=60)
        assert r.returncode == 0, r.stderr
        return r.stdout.decode("ascii").strip()

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
    pushed.stage_pass("0.0.1")
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


# --- GP-02 review regressions: each bypass the review found is refused ---

N0, N1 = NEEDLES
ZERO = "0" * 40


def _halted(r):
    return r.returncode != 0 and "HALT" in r.stderr


def _sweep_kinds(world, ref_line):
    sys.path.insert(0, str(ROOT / "tools"))
    import leak_sweep as ls
    f, _ = ls.scan_pre_push([ref_line], ls.compile_needles(NEEDLES), cwd=world.work)
    return sorted({(w, k) for w, _, k in f})


# B-TAG-BLOB
@pytest.mark.parametrize("annotated", [False, True])
def test_tag_on_a_blob_is_refused(pushed, annotated):
    before = pushed.remote_refs()
    blob = pushed.blob(f"note {N0}\n".encode("ascii"))
    for name in ("v8", "v0.8.0"):
        args = ["-a", "-m", "rel"] if annotated else []
        pushed.git("tag", *args, name, blob)
        r = pushed.push(name)
        assert _refused(r), (name, r.stderr)
    assert pushed.remote_refs() == before
    # the sweep alone also sees the blob's bytes
    assert ("blob", "needle-slot-0") in _sweep_kinds(
        pushed, f"refs/tags/v0.8.0 {blob} refs/tags/v0.8.0 {ZERO}")


# B-TAG-TREE
def test_tag_on_a_tree_is_refused(pushed):
    before = pushed.remote_refs()
    blob = pushed.blob(f"{N1}\n".encode("ascii"))
    r = subprocess.run(["git", "mktree"], cwd=str(pushed.work), capture_output=True,
                       input=f"100644 blob {blob}\t{N1}-synth.txt\n".encode("ascii"),
                       env=pushed.env, timeout=60)
    tree = r.stdout.decode("ascii").strip()
    pushed.git("tag", "v0.6.0", tree)
    r = pushed.push("v0.6.0")
    assert _refused(r) and "tree" in r.stderr, r.stderr
    assert pushed.remote_refs() == before
    kinds = _sweep_kinds(pushed, f"refs/tags/v0.6.0 {tree} refs/tags/v0.6.0 {ZERO}")
    assert ("path", "needle-slot-1") in kinds


# B-TAG-MSG
def test_annotated_tag_message_is_swept(pushed):
    before = pushed.remote_refs()
    pushed.git("tag", "-a", "v0.9.0", "-m", "release", "-m", f"thanks {N0}")
    pushed.stage_pass("0.9.0", "v0.9.0")
    r = pushed.push("v0.9.0")
    assert _halted(r) and "tag-message" in r.stderr, r.stderr
    assert pushed.remote_refs() == before


# B-TAGGER
def test_tag_object_identity_and_trailer(pushed):
    before = pushed.remote_refs()
    other = dict(pushed.env, GIT_COMMITTER_NAME="Some One",
                 GIT_COMMITTER_EMAIL="someone@example.org")
    pushed.git("tag", "-a", "v0.10.0", "-m", "rel", env=other)
    r = pushed.push("v0.10.0")
    assert _refused(r) and "non-operator-tagger" in r.stderr, r.stderr
    pushed.git("tag", "-a", "v0.11.0", "-m", "rel", "-m", "Co-Authored-By: Claude")
    r = pushed.push("v0.11.0")
    assert _refused(r) and "trailer" in r.stderr, r.stderr
    assert pushed.remote_refs() == before


# B-ADD-REMOVE
def test_needle_added_then_removed_is_refused(pushed):
    before = pushed.remote_refs()
    pushed.commit("t1.txt", f"{N0}\n", "add t1")
    (pushed.work / "t1.txt").unlink()
    pushed.commit_staged("drop t1")
    r = pushed.push("main")
    assert _halted(r), r.stderr
    assert pushed.remote_refs() == before


# B-NOPREFIX, B-DSTPREFIX
@pytest.mark.parametrize("cfg", ["diff.noprefix=true", "diff.dstPrefix=x/",
                                 "diff.mnemonicPrefix=true", "core.quotePath=false"])
def test_push_time_diff_config_does_not_blind_the_sweep(pushed, cfg):
    before = pushed.remote_refs()
    pushed.commit("t2.txt", f"see {N1}\n", "add t2")
    r = pushed.push("main", config=[cfg])
    assert _halted(r), (cfg, r.stderr)
    assert pushed.remote_refs() == before


# B-BINARY-NUL
@pytest.mark.parametrize("data", [b"\0" + N0.encode("ascii") + b"\n",
                                  b"\0\0" + N1.encode("utf-16-le"),
                                  b"\x89PNG\0" + N1.encode("utf-16-be")])
def test_needle_in_a_binary_blob_is_refused(pushed, data):
    before = pushed.remote_refs()
    pushed.commit("t4.dat", data, "add t4")
    r = pushed.push("main")
    assert _halted(r), r.stderr
    assert pushed.remote_refs() == before


# B-GITATTR
def test_minus_diff_attribute_does_not_hide_a_file(pushed):
    before = pushed.remote_refs()
    (pushed.work / ".gitattributes").write_text("t5.txt -diff\n", encoding="ascii",
                                               newline="\n")
    pushed.commit("t5.txt", f"{N0}\n", "add t5")
    r = pushed.push("main")
    assert _halted(r), r.stderr
    assert pushed.remote_refs() == before


# B-EMPTY-PATH
def test_empty_file_with_a_needle_name_is_refused(pushed):
    before = pushed.remote_refs()
    pushed.commit(f"{N1}.txt", "", "add empty")
    r = pushed.push("main")
    assert _halted(r) and "path" in r.stderr, r.stderr
    assert pushed.remote_refs() == before


# B-RENAME-PATH
def test_pure_rename_to_a_needle_name_is_refused(pushed):
    pushed.commit("clean1.txt", "clean\n", "add clean1")
    assert pushed.push("main").returncode == 0
    before = pushed.remote_refs()
    pushed.git("mv", "clean1.txt", f"{N1}.md")
    pushed.commit_staged("rename")
    r = pushed.push("main")
    assert _halted(r) and "path" in r.stderr, r.stderr
    assert pushed.remote_refs() == before


# B-CONFIG-MISSING
def test_missing_needle_config_fails_closed(pushed):
    before = pushed.remote_refs()
    pushed.cfg.unlink()
    pushed.commit("t6.txt", f"{N0}\n", "add t6")
    r = pushed.push("main")
    assert r.returncode != 0 and "FAULT" in r.stderr, r.stderr
    pushed.commit("t7.txt", "clean\n", "clean only")
    r = pushed.push("main")
    assert r.returncode != 0 and "FAULT" in r.stderr, r.stderr
    assert pushed.remote_refs() == before


# B-ENV-OVERRIDE
def test_env_needles_only_add(pushed):
    before = pushed.remote_refs()
    pushed.commit("t8.txt", f"{N0}\n", "add t8")
    r = pushed.push("main", extra_env={"AL_LEAK_NEEDLES": "nothing-xyz"})
    assert _halted(r), r.stderr
    assert pushed.remote_refs() == before


# B-TRAILER-KEYS
@pytest.mark.parametrize("trailer", [
    "Helped-by: GitHub Copilot <x@example.com>",
    "Co-authored-by: Opus <x@example.com>",
    "Assisted-by: Claude",
    "Reviewed-by: Sonnet",
    "Generated-by: ChatGPT",
    "AI-assisted: Gemini",
])
def test_ai_trailer_of_any_key_is_refused(pushed, trailer):
    before = pushed.remote_refs()
    pushed.commit("t9.txt", "t9\n", "change t9\n\n" + trailer)
    r = pushed.push("main")
    assert _refused(r) and "ai-trailer" in r.stderr, (trailer, r.stderr)
    assert pushed.remote_refs() == before


def test_human_trailer_passes(pushed):
    pushed.commit("t10.txt", "t10\n", "change t10\n\nReviewed-by: Op Erator <op@example.com>")
    r = pushed.push("main")
    assert r.returncode == 0, r.stderr


# B-NONVERSION-TAG
def test_only_semver_release_tags(pushed):
    before = pushed.remote_refs()
    for name in ("v1x", "vendor-notes", "v1", "v1.2", "v01.2.3", "v1.2.3-"):
        pushed.git("tag", name)
        r = pushed.push(name)
        assert _refused(r), (name, r.stderr)
    assert pushed.remote_refs() == before
    for name in ("v0.2.0-rc.1", "v0.2.0"):
        pushed.git("tag", name)
        pushed.stage_pass(name[1:], name)
        r = pushed.push(name)
        assert r.returncode == 0, (name, r.stderr)
        assert pushed.remote_refs()[f"refs/tags/{name}"] == pushed.rev(name)


def test_annotated_operator_tag_on_public_commit_pushes(pushed):
    pushed.git("tag", "-a", "v0.3.0", "-m", "release 0.3.0")
    pushed.stage_pass("0.3.0", "v0.3.0")
    r = pushed.push("v0.3.0")
    assert r.returncode == 0, r.stderr
    assert pushed.remote_refs()["refs/tags/v0.3.0"] == pushed.rev("v0.3.0")


# PUB-HOOK-RELEASE-CHECK
def test_tag_without_pass_stage_report_is_refused(pushed):
    before = pushed.remote_refs()
    pushed.git("tag", "v0.4.0")
    r = pushed.push("v0.4.0")
    assert r.returncode != 0 and "prepush-check: refused" in r.stderr, r.stderr
    assert pushed.remote_refs() == before
    pushed.stage_pass("0.4.0")
    d = pushed.sidecar / "Build" / "release" / "0.4.0" / "stage.json"
    rep = json.loads(d.read_text("ascii"))
    rep["verdict"] = "FAIL"
    d.write_text(json.dumps(rep), encoding="ascii", newline="\n")
    r = pushed.push("v0.4.0")
    assert r.returncode != 0 and "prepush-check: refused" in r.stderr, r.stderr
    assert pushed.remote_refs() == before
    pushed.stage_pass("0.4.0")
    r = pushed.push("v0.4.0")
    assert r.returncode == 0, r.stderr
    assert pushed.remote_refs()["refs/tags/v0.4.0"] == pushed.rev("v0.4.0")


def test_branch_push_ignores_the_stage_check(world):
    assert not (world.sidecar / "Build").exists()
    r = world.push("main")
    assert r.returncode == 0, r.stderr
    assert "prepush-check" not in r.stderr


def test_dependabot_fixture_copies_the_same_hook_files():
    text = (ROOT / "tests" / "test_dependabot_reapply.py").read_text(encoding="utf-8")
    missing = [rel for rel in HOOK_FILES if '"%s"' % rel not in text]
    assert not missing, "tests/test_dependabot_reapply.py Repo fixture lacks %s" % missing
