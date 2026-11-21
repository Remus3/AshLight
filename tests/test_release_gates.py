"""Release publish gates (REL-PUBLISH-GATES, decision 0073): tools/rel_publish.py.

git, gh, the push, the clock, the environment and the lane locks are all
injected: FakeGit answers the handful of git reads the gates make from a
state dict and records every call, so no test touches a real remote, tag or
the operator's sidecar. Each refusal case checks that nothing changed: no
tag call, no push, no publish.json. The prepush-check CLI case runs real git
in a scratch repo under tmp_path.
"""
import copy
import datetime
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(
        "gates_test_" + name, str(ROOT / "tools" / (name + ".py")))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rp = _load("rel_publish")
VERSION = "0.4.2"
TAG = "v" + VERSION
HEAD = "a" * 40
OTHER = "b" * 40
SUMS = "c" * 64
REPO = "Example/AshLight"
OPERATOR = "Op Erator <op@example.com>"
NOW = datetime.datetime(2026, 11, 21, 12, 0, 0,
                        tzinfo=datetime.timezone.utc).timestamp()
CREATED = "2026-11-21T10:00:00Z"


class FakeGit:
    """The git reads the gates make, answered from state; every call kept."""

    def __init__(self, **over):
        self.state = {
            "url": "https://github.com/%s.git" % REPO, "head": HEAD,
            "dirty": [], "local_tags": set(), "remote": {
                "refs/heads/main": HEAD},
            "committer": ("Op Erator", "op@example.com"),
            "idents": OPERATOR, "ls_fail": False, "tag_fail": False,
        }
        self.state.update(over)
        self.calls = []

    def __call__(self, *args):
        self.calls.append(list(args))
        s = self.state
        a = list(args)
        if a[:3] == ["remote", "get-url", "origin"]:
            return (0, s["url"] + "\n", "") if s["url"] else \
                (2, "", "error: No such remote 'origin'")
        if a[:1] == ["rev-parse"] and "--git-common-dir" in a:
            return 0, "", ""
        if a[:3] == ["rev-parse", "-q", "--verify"]:
            ref = a[3]
            if ref == "HEAD^{commit}":
                return 0, s["head"] + "\n", ""
            if ref.startswith("refs/tags/"):
                name = ref[len("refs/tags/"):]
                return (0, HEAD + "\n", "") if name in s["local_tags"] \
                    else (1, "", "")
            return 1, "", ""
        if a[:1] == ["status"]:
            return 0, "".join(ln + "\n" for ln in s["dirty"]), ""
        if a[:1] == ["ls-remote"]:
            if s["ls_fail"]:
                return 128, "", "fatal: could not read"
            wanted = a[2:]
            out = "".join("%s\t%s\n" % (sha, ref)
                          for ref, sha in sorted(s["remote"].items())
                          if ref in wanted)
            return 0, out, ""
        if a[:1] == ["log"]:
            return 0, "%s\x00%s\n" % s["committer"], ""
        if a[:2] == ["config", "--local"]:
            return (0, s["idents"] + "\n", "") if s["idents"] else (1, "", "")
        if a[:1] == ["tag"]:
            if a[1] == "-d":
                s["local_tags"].discard(a[2])
                return 0, "", ""
            if s["tag_fail"]:
                return 128, "", "fatal: tag failed"
            s["local_tags"].add(a[2])
            return 0, "", ""
        raise AssertionError("unexpected git call %r" % (a,))

    def writes(self):
        """Calls that would change something (tag creates or deletes)."""
        return [c for c in self.calls if c[:1] == ["tag"]]


class FakeGh:
    def __init__(self, enabled=None):
        self.enabled = enabled
        self.calls = []

    def __call__(self, *args):
        self.calls.append(list(args))
        if self.enabled is None:
            return 127, "", "gh not installed"
        return 0, json.dumps({"enabled": self.enabled,
                              "enforced_by_owner": False}), ""


class FakePush:
    def __init__(self, rc=0):
        self.rc = rc
        self.calls = []

    def __call__(self, argv):
        self.calls.append(list(argv))
        return self.rc


def _tree(tmp_path, notes="## [%s] - 2026-11-21\n\nNotes.\n" % VERSION,
          immutable="2026-11-20"):
    root = tmp_path / "repo"
    (root / "config").mkdir(parents=True)
    (root / "docs" / "releases").mkdir(parents=True)
    (root / "config" / "public_repo.json").write_text(
        json.dumps({"repo": REPO}), encoding="ascii")
    (root / "config" / "release.json").write_text(
        json.dumps({"immutable_confirmed": immutable, "repository": ""}),
        encoding="ascii")
    if notes is not None:
        (root / "docs" / "releases" / ("%s.md" % VERSION)).write_text(
            notes, encoding="ascii")
    return root


def _stage_report(out, **over):
    rep = {"schema": 1, "version": VERSION, "commit": HEAD,
           "verdict": "PASS", "steps": [], "assets": [],
           "sums_sha256": SUMS, "created": CREATED, "sandbox": False,
           "notes": []}
    rep.update(over)
    out.mkdir(parents=True, exist_ok=True)
    (out / "stage.json").write_text(json.dumps(rep), encoding="ascii")
    return rep


class Setup:
    def __init__(self, tmp_path, git=None, gh=None, push=None, env=None,
                 locks=(), changelog=True, stage=True, go=None,
                 version=VERSION, **tree_kw):
        self.root = _tree(tmp_path, **tree_kw)
        self.out = tmp_path / "out"
        if stage is True:
            _stage_report(self.out)
        elif isinstance(stage, dict):
            _stage_report(self.out, **stage)
        # the REFUSALS table shares its fakes between parameter runs
        self.git = copy.deepcopy(git) if git else FakeGit()
        self.gh = copy.deepcopy(gh) if gh else FakeGh()
        self.push = push or FakePush()
        self.ctx = rp.make_ctx(
            version, go if go is not None else "release " + version,
            root=self.root, out=self.out, git=self.git, gh=self.gh,
            push=self.push, now=lambda: NOW,
            env={} if env is None else env,
            lane_locks=lambda ctx: list(locks), owner="sess.agent",
            changelog_current=lambda root: changelog)

    def run(self, rehearse=False):
        before = sorted(p.name for p in self.out.iterdir()) \
            if self.out.is_dir() else []
        self.result = rp.run(self.ctx, rehearse=rehearse)
        self.before = before
        return self.result

    def refused(self):
        return dict(self.result["refusals"])

    def assert_nothing_changed(self):
        assert self.git.writes() == []
        assert self.push.calls == []
        after = sorted(p.name for p in self.out.iterdir()) \
            if self.out.is_dir() else []
        assert after == self.before
        assert "publish.json" not in after
        assert self.result["tagged"] is False
        assert self.result["pushed"] is False


# --- the pass ---------------------------------------------------------------

def test_every_gate_passes_then_one_annotated_tag_and_one_push(tmp_path):
    s = Setup(tmp_path)
    res = s.run()
    assert res["refusals"] == []
    assert [r[0] for r in res["rows"]] == [n for n, _f in rp.GATES]
    tags = s.git.writes()
    assert len(tags) == 1
    call = tags[0]
    assert call[:3] == ["tag", "-a", TAG]
    assert call[3] == "-m" and "sums-sha256: %s" % SUMS in call[4]
    assert call[5] == HEAD
    assert len(s.push.calls) == 1
    argv = s.push.calls[0]
    assert argv[1].replace("\\", "/").endswith("ops/fleet_kit/fleet_gitlock.py")
    assert argv[2:6] == ["run", "--owner", "sess.agent", "--"]
    assert argv[6:] == ["git", "push", "origin", "refs/tags/" + TAG]
    for bad in ("--tags", "--all", "--mirror", "--force", "main",
                "refs/heads/main"):
        assert bad not in argv
    assert res["tagged"] and res["pushed"]
    doc = json.loads((s.out / "publish.json").read_text(encoding="ascii"))
    assert doc["tag"] == TAG and doc["commit"] == HEAD
    assert doc["sums_sha256"] == SUMS


def test_rehearse_runs_every_gate_with_no_tag_and_no_push(tmp_path):
    s = Setup(tmp_path)
    res = s.run(rehearse=True)
    assert res["refusals"] == []
    assert len(res["rows"]) == len(rp.GATES)
    s.assert_nothing_changed()
    assert res["remote_line"] == "remote: origin (%s)" % REPO


def test_gh_reading_enabled_confirms_immutable_releases(tmp_path):
    s = Setup(tmp_path, gh=FakeGh(enabled=True), immutable=None)
    res = s.run(rehearse=True)
    assert res["refusals"] == []
    assert s.gh.calls == [["api", "repos/%s/immutable-releases" % REPO]]


def test_a_failed_push_removes_the_local_tag(tmp_path):
    s = Setup(tmp_path, push=FakePush(rc=1))
    res = s.run()
    assert res["pushed"] is False and res["tagged"] is False
    assert "failed" in res["error"]
    assert TAG not in s.git.state["local_tags"]
    assert not (s.out / "publish.json").exists()


# --- every refusal changes nothing -----------------------------------------

REFUSALS = [
    ("phrase", dict(go="release 9.9.9"), "the phrase differs"),
    ("phrase", dict(go="Release %s" % VERSION), "the phrase differs"),
    ("stage", dict(stage=False), "no stage report"),
    ("stage", dict(stage={"verdict": "FAIL"}), "not PASS"),
    ("stage", dict(stage={"version": "0.4.1"}), "another version"),
    ("stage", dict(stage={"commit": OTHER}), "another commit"),
    ("stage", dict(stage={"created": "2026-11-20T11:59:00Z"}),
     "older than 24 h"),
    ("stage", dict(git=FakeGit(head=OTHER)), "HEAD is not the stage commit"),
    ("tree", dict(git=FakeGit(dirty=[" M server/al/core.py"])),
     "the tree is dirty"),
    ("notes", dict(notes="# AshLight %s\n\nSTUB: release notes not written "
                         "yet (fill).\n" % VERSION), "STUB mark"),
    ("notes", dict(notes=None), "no notes file"),
    ("notes", dict(changelog=False), "CHANGELOG.md is stale"),
    ("tag", dict(git=FakeGit(local_tags={TAG})), "exists locally"),
    ("tag", dict(git=FakeGit(remote={"refs/heads/main": HEAD,
                                     "refs/tags/" + TAG: OTHER})),
     "exists on the remote"),
    ("origin", dict(git=FakeGit(remote={"refs/heads/main": OTHER})),
     "origin/main is not HEAD"),
    ("origin", dict(git=FakeGit(ls_fail=True)), "could not be read"),
    ("remote", dict(git=FakeGit(url=None)), "no remote"),
    ("remote", dict(git=FakeGit(url="https://github.com/Someone/Else.git")),
     "does not name"),
    ("committer", dict(git=FakeGit(committer=("Bot", "bot@example.com"))),
     "not the operator identity"),
    ("committer", dict(git=FakeGit(idents="")), "not the operator identity"),
    ("immutable", dict(immutable=None), "immutable releases not confirmed"),
    ("immutable", dict(immutable=None, gh=FakeGh(enabled=False)),
     "immutable releases not confirmed"),
    ("headless", dict(env={"FLEET_PROGRESS_OWNER": "4242"}),
     "headless marker"),
]


@pytest.mark.parametrize("rehearse", [False, True])
@pytest.mark.parametrize("gate,kw,text", REFUSALS,
                         ids=["%s-%d" % (r[0], i)
                              for i, r in enumerate(REFUSALS)])
def test_each_refusal_leaves_nothing_changed(tmp_path, gate, kw, text,
                                             rehearse):
    s = Setup(tmp_path, **kw)
    s.run(rehearse=rehearse)
    refused = s.refused()
    assert gate in refused, refused
    assert text in refused[gate]
    s.assert_nothing_changed()


def test_a_lane_lock_on_this_worktree_is_a_headless_marker(tmp_path):
    root = tmp_path / "repo"
    s = Setup(tmp_path, locks=[{"lane": "build", "worktree": str(root)}])
    s.run()
    assert "headless marker" in s.refused()["headless"]
    s.assert_nothing_changed()


def test_a_lane_lock_on_another_worktree_is_not_a_marker(tmp_path):
    s = Setup(tmp_path, locks=[{"lane": "build",
                                "worktree": str(tmp_path / "lane-0")}])
    s.run(rehearse=True)
    assert "headless" not in s.refused()


def test_no_remote_is_named_among_the_refusals(tmp_path):
    s = Setup(tmp_path, git=FakeGit(url=None))
    res = s.run(rehearse=True)
    assert "no remote" in s.refused()["remote"]
    assert res["remote_line"] == "remote: none"
    assert not any(c[:1] == ["ls-remote"] for c in s.git.calls)
    s.assert_nothing_changed()


def test_with_origin_configured_the_remote_gate_passes(tmp_path):
    s = Setup(tmp_path)
    res = s.run(rehearse=True)
    rows = {n: (st, d) for n, st, d in res["rows"]}
    assert rows["remote"][0] == "pass"
    assert "no remote" not in json.dumps(res)


def test_origin_is_only_read_once(tmp_path):
    s = Setup(tmp_path)
    s.run(rehearse=True)
    reads = [c for c in s.git.calls if c[:1] == ["ls-remote"]]
    assert len(reads) == 1
    assert reads[0][:2] == ["ls-remote", "origin"]
    assert not any(c[:1] in (["push"], ["fetch"]) for c in s.git.calls)


def test_a_bad_version_is_refused_by_the_phrase_gate(tmp_path):
    s = Setup(tmp_path, version="1.2", go="release 1.2", stage=False)
    s.run(rehearse=True)
    assert "phrase" in s.refused()
    s.assert_nothing_changed()


def test_repository_reads_the_go_public_file_first(tmp_path):
    root = _tree(tmp_path)
    assert rp.repository(root) == REPO
    (root / "config" / "public_repo.json").unlink()
    assert rp.repository(root) is None
    (root / "config" / "release.json").write_text(
        json.dumps({"immutable_confirmed": None, "repository": "A/B"}),
        encoding="ascii")
    assert rp.repository(root) == "A/B"


def test_tracked_config_holds_the_placeholders():
    doc = json.loads((ROOT / "config" / "release.json").read_text(
        encoding="ascii"))
    assert doc == {"immutable_confirmed": None, "repository": ""}


def test_release_dispatcher_routes_publish_and_prepush_check():
    rel = _load("release")
    assert rel.module_path("publish").name == "rel_publish.py"
    assert rel.module_path("prepush-check").name == "rel_publish.py"


# --- prepush-check ----------------------------------------------------------

def _stage_dir(base):
    return lambda version: base / version


def _real_git(sha_ok=True):
    def git(*args):
        if args[:3] == ("rev-parse", "-q", "--verify"):
            return (0, args[3].split("^")[0] + "\n", "") if sha_ok \
                else (1, "", "")
        raise AssertionError(args)
    return git


def test_prepush_check_passes_a_branch_ref_untouched(tmp_path):
    calls = []

    def git(*args):
        calls.append(args)
        return 1, "", ""
    lines = ["refs/heads/main %s refs/heads/main %s" % (HEAD, OTHER)]
    assert rp.prepush_check(lines, _stage_dir(tmp_path), git) == []
    assert calls == []


def test_prepush_check_refuses_a_tag_with_no_stage_report(tmp_path):
    lines = ["refs/tags/%s %s refs/tags/%s %s" % (TAG, HEAD, TAG, rp.ZERO_SHA)]
    found = rp.prepush_check(lines, _stage_dir(tmp_path), _real_git())
    assert len(found) == 1 and "no stage report" in found[0]


def test_prepush_check_passes_a_tag_with_its_pass_report(tmp_path):
    _stage_report(tmp_path / VERSION)
    lines = ["refs/tags/%s %s refs/tags/%s %s" % (TAG, HEAD, TAG, rp.ZERO_SHA)]
    assert rp.prepush_check(lines, _stage_dir(tmp_path), _real_git()) == []


@pytest.mark.parametrize("over,text", [
    ({"verdict": "FAIL"}, "not PASS"),
    ({"commit": OTHER}, "another commit"),
    ({"version": "0.4.1"}, "another version"),
])
def test_prepush_check_refuses_a_tag_whose_report_does_not_match(
        tmp_path, over, text):
    _stage_report(tmp_path / VERSION, **over)
    lines = ["refs/tags/%s %s refs/tags/%s %s" % (TAG, HEAD, TAG, rp.ZERO_SHA)]
    found = rp.prepush_check(lines, _stage_dir(tmp_path), _real_git())
    assert len(found) == 1 and text in found[0]


def test_prepush_check_refuses_a_tag_delete(tmp_path):
    lines = ["(delete) %s refs/tags/%s %s" % (rp.ZERO_SHA, TAG, HEAD)]
    found = rp.prepush_check(lines, _stage_dir(tmp_path), _real_git())
    assert len(found) == 1 and "never deleted" in found[0]


def test_prepush_check_cli_with_real_git(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    base = ["git", "-c", "core.hooksPath=", "-c", "user.name=t",
            "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false"]

    def g(*args):
        return subprocess.run(base + list(args), cwd=str(repo),
                              capture_output=True, check=True).stdout
    g("init", "-q")
    (repo / "f.txt").write_text("x\n", encoding="ascii")
    g("add", "-A")
    g("commit", "-q", "-m", "chore: one")
    head = g("rev-parse", "HEAD").decode("ascii").strip()
    stage_root = tmp_path / "stages"
    env = dict(os.environ)
    cmd = [sys.executable, str(ROOT / "tools" / "release.py"),
           "prepush-check", "origin", "x", "--stage-root", str(stage_root),
           "--root", str(repo)]
    branch = "refs/heads/main %s refs/heads/main %s\n" % (head, rp.ZERO_SHA)
    tag = "refs/tags/%s %s refs/tags/%s %s\n" % (TAG, head, TAG, rp.ZERO_SHA)
    ok = subprocess.run(cmd, input=branch.encode("ascii"), env=env,
                        capture_output=True)
    assert ok.returncode == 0, ok.stderr
    bad = subprocess.run(cmd, input=tag.encode("ascii"), env=env,
                         capture_output=True)
    assert bad.returncode == 1
    assert b"no stage report" in bad.stderr
    _stage_report(stage_root / VERSION, commit=head)
    good = subprocess.run(cmd, input=tag.encode("ascii"), env=env,
                          capture_output=True)
    assert good.returncode == 0, good.stderr


# --- static guards ----------------------------------------------------------

def test_publish_never_uses_a_wide_push_flag():
    text = (ROOT / "tools" / "rel_publish.py").read_text(encoding="utf-8")
    for bad in ('"--tags"', '"--all"', '"--mirror"', '"--force"', '"fetch"'):
        assert bad not in text, bad
