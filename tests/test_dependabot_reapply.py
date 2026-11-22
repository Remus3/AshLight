"""GP-14, PUB-DEPBOT-ACTIONS and PUB-DEPBOT-NPM: tools/dependabot_reapply.py
lists open Dependabot pull requests, closes one that touches the vendored
identity-guard copy with one line, leaves a bump open with one report line
while its apply seam is empty, re-applies a github-actions bump as one
operator commit, pushed and closed, re-applies an npm lockfile bump through
the pin procedure (regenerated without scripts, signatures audited, the 3-day
age rule) and treats an electron bump as a signal only (npm is a recording
fake). git, gh, the clock and the gate runner are injected: the
GP-14 cases use recording fakes; the actions cases use real git in tmp_path
with a local bare remote (no network) and a recording gh. Fixture names are
made up."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import dependabot_reapply as dr  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "dependabot" / "pr_guard.json"
ACTIONS_FIXTURE = ROOT / "tests" / "fixtures" / "dependabot" / "pr_actions.json"
REMOTE = "https://github.com/example-owner/example-repo.git\n"
REPO = "example-owner/example-repo"


class FakeGit:
    def __init__(self, remote=REMOTE):
        self.remote = remote
        self.calls = []

    def __call__(self, args):
        self.calls.append(list(args))
        if list(args) == ["remote", "get-url", "origin"]:
            if self.remote is None:
                return 2, ""
            return 0, self.remote
        return 1, ""


class FakeGh:
    def __init__(self, prs=None, list_rc=0, close_rc=0):
        self.prs = prs if prs is not None else json.loads(
            FIXTURE.read_text(encoding="utf-8"))
        self.list_rc = list_rc
        self.close_rc = close_rc
        self.calls = []

    def __call__(self, args):
        args = list(args)
        self.calls.append(args)
        if args[:2] == ["pr", "list"]:
            return self.list_rc, json.dumps(self.prs)
        if args[:2] == ["pr", "close"]:
            return self.close_rc, ""
        return 1, ""

    def closes(self):
        return [c for c in self.calls if c[:2] == ["pr", "close"]]


def _empty_actions(ctx, pr):
    return None


def _empty_npm(ctx, pr):
    return None


EMPTY = {"actions": _empty_actions, "npm": _empty_npm}


def make(git=None, gh=None, seams=None):
    lines = []
    deps = dict(root=ROOT, git=git or FakeGit(), gh=gh or FakeGh(),
                clock=lambda: 1795000000.0, say=lines.append)
    if seams is not None:
        deps["seams"] = seams
    return deps, lines


def test_fixture_is_ascii_and_made_up():
    raw = FIXTURE.read_bytes()
    raw.decode("ascii")
    assert b"\r" not in raw
    data = json.loads(raw)
    assert [p["number"] for p in data] == [41, 42, 43, 44]


def test_repo_comes_from_the_origin_remote():
    for url in ("https://github.com/example-owner/example-repo.git",
                "https://github.com/example-owner/example-repo",
                "git" + "@" + "github.com:example-owner/example-repo.git",
                "ssh://git" + "@" + "github.com/example-owner/example-repo.git"):
        assert dr.repo_from_url(url) == REPO
    assert dr.repo_from_url("https://example.invalid/a/b.git") is None
    assert dr.repo_from_url("") is None


def test_kind_dispatch_from_paths():
    prs = {p["number"]: p for p in json.loads(FIXTURE.read_text(encoding="utf-8"))}
    assert dr.kind(prs[41]) == "guard"
    assert dr.kind(prs[42]) == "actions"
    assert dr.kind(prs[43]) == "npm"
    assert dr.kind(prs[44]) == "other"
    assert dr.kind({"number": 1, "files": []}) == "other"


def test_list_reads_dependabot_prs_of_the_origin_repo():
    deps, lines = make()
    assert dr.main(["list"], **deps) == 0
    call = deps["gh"].calls[0]
    assert call[:2] == ["pr", "list"]
    assert call[call.index("--repo") + 1] == REPO
    assert call[call.index("--author") + 1] == "app/dependabot"
    assert call[call.index("--state") + 1] == "open"
    assert call[call.index("--json") + 1] == "number,title,headRefOid,files"
    assert lines[0].startswith("#41 guard:")
    assert lines[-1] == "open: 4"
    assert not deps["gh"].closes()


def test_run_closes_guard_pr_and_leaves_unapplied_bumps_open():
    deps, lines = make(seams=EMPTY)
    assert dr.main(["run"], **deps) == 0
    gh = deps["gh"]
    closes = gh.closes()
    assert closes == [["pr", "close", "41", "--repo", REPO, "--comment",
                       "This file is vendored; the change is reported upstream."]]
    assert "#41: closed, vendored guard file (upstream: #41)" in lines
    assert "#42: left open, needs PUB-DEPBOT-ACTIONS" in lines
    assert "#43: left open, needs PUB-DEPBOT-NPM" in lines
    assert "#44: left open, needs review (mixed or unknown paths)" in lines
    assert "upstream: #41" in lines
    assert lines[-1] == "left open: 3"
    assert lines[0].startswith("dependabot_reapply run 2026-")
    # exactly one report line per pull request
    for n in (41, 42, 43, 44):
        assert sum(1 for x in lines if x.startswith("#%d:" % n)) == 1


def test_nothing_is_ever_merged_and_no_commit_is_made():
    deps, _lines = make(seams=EMPTY)
    dr.main(["run"], **deps)
    assert not any("merge" in c for c in deps["gh"].calls)
    assert deps["git"].calls == [["remote", "get-url", "origin"]]


def test_filled_seam_is_called_and_its_line_reported():
    seen = []

    def fake_actions(ctx, pr):
        seen.append(pr["number"])
        return "applied locally as abc1234"

    deps, lines = make(seams={"actions": fake_actions, "npm": _empty_npm})
    assert dr.main(["run"], **deps) == 0
    assert seen == [42]
    assert "#42: applied locally as abc1234" in lines
    assert "#43: left open, needs PUB-DEPBOT-NPM" in lines


def test_default_seams_actions_and_npm_filled():
    r = dr.Reapply(root=ROOT, git=FakeGit(), gh=FakeGh(), say=lambda _l: None,
                   npm=lambda _a: (1, ""))
    assert r.seams["actions"] is dr.apply_actions
    assert r.seams["npm"] is dr.apply_npm
    # an untitled pull request is left open by the npm seam too
    assert dr.apply_npm(r, {"number": 2}) == \
        "left open, needs review (title names no bump)"
    r.left_open.clear()
    # an untitled pull request is left open by the filled seam, never applied
    assert dr.apply_actions(r, {"number": 1}) == \
        "left open, needs review (title names no bump)"
    assert r.left_open == [1]


def test_default_git_takes_the_kit_lock_for_commit_and_push_only():
    for verb in ("commit", "push"):
        argv = dr.git_argv([verb, "x"], ROOT)
        assert argv[1].replace("\\", "/").endswith("ops/fleet_kit/fleet_gitlock.py")
        assert argv[2:4] == ["run", "--owner"]
        assert argv[5:] == ["--", "git", verb, "x"]
    assert dr.git_argv(["rev-parse", "HEAD"], ROOT) == ["git", "rev-parse", "HEAD"]


def test_close_command_closes_guard_pr_only():
    deps, lines = make()
    assert dr.main(["close", "41"], **deps) == 0
    assert len(deps["gh"].closes()) == 1
    deps, lines = make()
    assert dr.main(["close", "42"], **deps) == 1
    assert not deps["gh"].closes()
    deps, lines = make()
    assert dr.main(["close", "99"], **deps) == 1
    assert "#99: not an open Dependabot pull request" in lines
    assert not deps["gh"].closes()


def test_apply_command_dispatches_one_pr():
    deps, lines = make(seams=EMPTY)
    assert dr.main(["apply", "43"], **deps) == 0
    assert lines == ["#43: left open, needs PUB-DEPBOT-NPM"]
    assert not deps["gh"].closes()


def test_no_origin_is_a_noop_that_exits_zero():
    for cmd in (["run"], ["list"], ["close", "41"], ["apply", "42"]):
        deps, lines = make(git=FakeGit(remote=None))
        assert dr.main(cmd, **deps) == 0
        assert deps["gh"].calls == []
        assert lines == ["dependabot_reapply: no origin remote, nothing to do"]


def test_gh_failures_exit_one_and_leave_prs_open():
    deps, lines = make(gh=FakeGh(list_rc=4))
    assert dr.main(["run"], **deps) == 1
    assert not deps["gh"].closes()
    deps, lines = make(gh=FakeGh(close_rc=1), seams=EMPTY)
    assert dr.main(["run"], **deps) == 1
    assert "#41: gh pr close failed (rc 1), left open" in lines
    assert "upstream: #41" not in lines


def test_usage_error_exits_two():
    deps, _lines = make()
    assert dr.main(["bogus"], **deps) == 2
    assert dr.main(["close", "x"], **deps) == 2


# ------------------------------------------------- actions bump (real git)

OPERATOR = ("Op Erator", "op@example.com")
OLD_SHA = "a" * 40
NEW_SHA = "b" * 40
OTHER_SHA = "c" * 40
# Synthetic needles only; the test never spells a real one.
NEEDLES = ["Zorblax Quux", "acct-0000-fake"]
CI_YML = (
    "name: ci\n"
    "jobs:\n"
    "  test:\n"
    "    steps:\n"
    "      - uses: example-org/checkout-thing@%s # v2.0.0\n"
    "      - uses: example-org/setup-thing@%s # v1.0.0\n"
    "  lint:\n"
    "    steps:\n"
    "      - uses: example-org/setup-thing@%s # v1.0.0\n"
    % (OTHER_SHA, OLD_SHA, OLD_SHA))
GREEN = [("python tools/suite_run.py", True, "rc=0"),
         ("npm test --prefix app", True, "rc=0")]


def _git_sh():
    git = shutil.which("git")
    if not git:
        return None
    if shutil.which("sh"):
        return git
    try:
        exec_path = subprocess.run([git, "--exec-path"], capture_output=True,
                                   text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    if not exec_path:
        return None
    base = Path(exec_path).parents[2]
    for cand in (base / "bin" / "sh.exe", base / "usr" / "bin" / "sh.exe"):
        if cand.is_file():
            return git
    return None


needs_git = pytest.mark.skipif(_git_sh() is None,
                               reason="git or its sh is not available")


class Repo:
    """A work repo with copies of .githooks and the hook tools at the same
    relative paths (the harness of tests/test_pre_push_hook.py), the
    operator identity in this repo only, and a local bare repo as origin.
    Called with git args it is the injected git: real git, hooks on."""

    def __init__(self, tmp_path):
        tmp_path.mkdir(parents=True, exist_ok=True)
        self.work = tmp_path / "work"
        self.bare = tmp_path / "origin.git"
        nohooks = tmp_path / "nohooks"
        nohooks.mkdir()
        gcfg = tmp_path / "empty.gitconfig"
        gcfg.write_text("", encoding="ascii")
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("GIT_", "AL_LEAK_NEEDLES", "AL_ALLOW_PUSH"))}
        env.update(GIT_CONFIG_GLOBAL=str(gcfg), GIT_CONFIG_NOSYSTEM="1",
                   GIT_TERMINAL_PROMPT="0")
        env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
        self.env = env
        self.calls = []
        self.run(tmp_path, "init", "-q", "--bare", "-b", "main", str(self.bare))
        self.work.mkdir()
        self.run(self.work, "init", "-q", "-b", "main")
        hooks = self.work / ".githooks"
        shutil.copytree(ROOT / ".githooks", hooks)
        for h in hooks.iterdir():
            h.chmod(0o755)
        # same hook files as tests/test_pre_push_hook.py HOOK_FILES (a test
        # there fails when the two lists differ), plus the subject checker
        for rel in ("ops/fleet_kit/fleet_identity.py", "tools/leak_sweep.py",
                    "tools/push_guard.py", "tools/release.py",
                    "tools/rel_publish.py", "tools/rel_build.py",
                    "tools/rel_version.py", "tools/rel_readback.py",
                    "server/al/paths.py", "tools/commit_subject.py"):
            dst = self.work / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, dst)
        for k, v in (("core.hooksPath", str(hooks)), ("commit.gpgsign", "false"),
                     ("user.name", OPERATOR[0]), ("user.email", OPERATOR[1])):
            self.run(self.work, "config", k, v)
        self.run(self.work, "config", "--add", "fleet.operatorIdent",
                 "%s <%s>" % OPERATOR)
        self.run(self.work, "remote", "add", "origin", str(self.bare))
        # the hooks run the copies from the work tree; they are never committed
        (self.work / ".git" / "info" / "exclude").write_text(
            "/.githooks/\n/ops/\n/tools/\n/config/\n", encoding="ascii", newline="\n")
        cfg = self.work / "config" / "leak_needles.json"
        cfg.parent.mkdir()
        cfg.write_text('{"needles": ["%s", "%s"]}\n' % tuple(NEEDLES),
                       encoding="ascii", newline="\n")
        self.ci = self.work / ".github" / "workflows" / "ci.yml"
        self.ci.parent.mkdir(parents=True)
        self.ci.write_bytes(CI_YML.encode("ascii"))
        off = "core.hooksPath=%s" % nohooks
        self.run(self.work, "-c", off, "add", "-A")
        self.run(self.work, "-c", off, "commit", "-q", "-m", "chore: first commit")
        self.run(self.work, "-c", off, "push", "-q", "origin", "main")

    def run(self, cwd, *args, check=True):
        r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                           text=True, env=self.env, timeout=180)
        if check and r.returncode != 0:
            raise AssertionError("git %s rc=%d: %s" % (args, r.returncode, r.stderr))
        return r

    def __call__(self, args):
        args = list(args)
        self.calls.append(args)
        if args == ["remote", "get-url", "origin"]:
            # origin is a local bare repo; the tool reads the repository name
            # from a github.com URL, so this one call answers a made-up one
            return 0, REMOTE
        r = self.run(self.work, *args, check=False)
        return r.returncode, r.stdout

    def out(self, *args, cwd=None):
        return self.run(cwd or self.work, *args).stdout.strip()

    def verbs(self, *names):
        return [c for c in self.calls if c[:1] and c[0] in names]


class RecordingGh:
    """gh as a recording fake: pr list answers the fixture, api answers the
    tag's commit, pr close records the comment. No network."""

    def __init__(self, sha=NEW_SHA):
        self.prs = json.loads(ACTIONS_FIXTURE.read_text(encoding="utf-8"))
        self.sha = sha
        self.calls = []

    def __call__(self, args):
        args = list(args)
        self.calls.append(args)
        if args[:2] == ["pr", "list"]:
            return 0, json.dumps(self.prs)
        if args[:1] == ["api"]:
            return 0, self.sha + "\n"
        if args[:2] == ["pr", "close"]:
            return 0, ""
        return 1, ""

    def closes(self):
        return [c for c in self.calls if c[:2] == ["pr", "close"]]


class Gates:
    """The injected gate runner: records the workflow file it was run on."""

    def __init__(self, rows=GREEN):
        self.rows = rows
        self.seen = []

    def __call__(self, root):
        self.seen.append((Path(root) / ".github" / "workflows" / "ci.yml").read_bytes())
        return list(self.rows)


def _run(repo, argv, gh, gates):
    lines = []
    rc = dr.main(argv, root=repo.work, git=repo, gh=gh,
                 clock=lambda: 1795000000.0, say=lines.append, gates=gates)
    return rc, lines


def test_actions_fixture_is_ascii_and_made_up():
    raw = ACTIONS_FIXTURE.read_bytes()
    raw.decode("ascii")
    assert b"\r" not in raw
    data = json.loads(raw)
    assert [p["number"] for p in data] == [52]
    assert dr.kind(data[0]) == "actions"
    assert dr.parse_bump(data[0]["title"]) == ("example-org/setup-thing", "1.0.0", "1.1.0")


def test_parse_bump_and_rewrite_uses():
    assert dr.parse_bump("build(deps): bump example-org/x from v4 to v5") == \
        ("example-org/x", "4", "5")
    assert dr.parse_bump("Bump example-org/x/sub from 1.2 to 1.3 in /.github/workflows") \
        == ("example-org/x/sub", "1.2", "1.3")
    assert dr.parse_bump("Bump made-up-lib from 3.2.1 to 3.2.2 in /app") is None
    assert dr.parse_bump("Update stuff") is None
    text, n = dr.rewrite_uses(CI_YML, "example-org/setup-thing", NEW_SHA, "1.1.0")
    assert n == 2
    assert text.count("- uses: example-org/setup-thing@%s # v1.1.0\n" % NEW_SHA) == 2
    assert "example-org/checkout-thing@%s # v2.0.0" % OTHER_SHA in text
    assert OLD_SHA not in text


@needs_git
def test_actions_bump_is_one_operator_commit_pushed_and_closed(tmp_path):
    repo = Repo(tmp_path)
    base = repo.out("rev-parse", "HEAD")
    gh, gates = RecordingGh(), Gates()
    rc, lines = _run(repo, ["run"], gh, gates)
    assert rc == 0, lines
    head = repo.out("rev-parse", "HEAD")
    # exactly one local commit, author and committer the operator, no trailer
    assert repo.out("rev-list", "--count", "%s..HEAD" % base) == "1"
    assert repo.out("log", "-1", "--format=%an <%ae>") == "%s <%s>" % OPERATOR
    assert repo.out("log", "-1", "--format=%cn <%ce>") == "%s <%s>" % OPERATOR
    assert repo.out("log", "-1", "--format=%B") == \
        "deps(actions): bump example-org/setup-thing from v1.0.0 to v1.1.0"
    assert repo.out("log", "-1", "--format=%(trailers)") == ""
    assert repo.out("diff", "--name-only", "%s..HEAD" % base) == ".github/workflows/ci.yml"
    ci = repo.ci.read_text(encoding="ascii")
    assert ci.count("- uses: example-org/setup-thing@%s # v1.1.0\n" % NEW_SHA) == 2
    assert OLD_SHA not in ci
    assert "example-org/checkout-thing@%s # v2.0.0" % OTHER_SHA in ci
    # the gates ran once, on the rewritten file, before the commit
    assert len(gates.seen) == 1 and NEW_SHA.encode() in gates.seen[0]
    # one commit of the named path, one push to main through the guarded hook
    commits = repo.verbs("commit")
    assert len(commits) == 1 and commits[0][-2:] == ["--", ".github/workflows/ci.yml"]
    assert repo.verbs("push") == [["push", "origin", "main"]]
    assert repo.out("rev-parse", "main", cwd=repo.bare) == head
    # the tag's commit re-read, then exactly one close comment naming the commit
    assert [c for c in gh.calls if c[:1] == ["api"]] == \
        [["api", "repos/example-org/setup-thing/commits/v1.1.0", "--jq", ".sha"]]
    assert gh.closes() == [["pr", "close", "52", "--repo", REPO, "--comment",
                            "Applied locally as %s." % head]]
    assert not any("merge" in c for c in gh.calls)
    assert "#52: applied locally as %s, pushed, closed" % head in lines
    assert lines[-1] == "left open: 0"
    assert repo.out("status", "--porcelain") == ""


@needs_git
def test_red_gate_leaves_the_pull_request_open(tmp_path):
    repo = Repo(tmp_path)
    base = repo.out("rev-parse", "HEAD")
    gh = RecordingGh()
    red = Gates(rows=[GREEN[0], ("npm test --prefix app", False, "rc=1 1 failed")])
    rc, lines = _run(repo, ["run"], gh, red)
    assert rc == 0, lines
    # nothing committed, nothing pushed, nothing closed, the file restored
    assert repo.out("rev-parse", "HEAD") == base
    assert repo.out("rev-parse", "main", cwd=repo.bare) == base
    assert repo.ci.read_bytes() == CI_YML.encode("ascii")
    assert repo.out("status", "--porcelain") == ""
    assert repo.verbs("commit", "push") == []
    assert gh.closes() == []
    # one report line for the pull request
    assert [x for x in lines if x.startswith("#52:")] == \
        ["#52: left open, gate red: npm test --prefix app (rc=1 1 failed)"]
    assert lines[-1] == "left open: 1"


@needs_git
def test_refused_push_leaves_the_pull_request_open_and_exits_one(tmp_path):
    repo = Repo(tmp_path)
    repo.run(repo.work, "remote", "set-url", "origin", str(tmp_path / "missing.git"))
    gh = RecordingGh()
    rc, lines = _run(repo, ["apply", "52"], gh, Gates())
    assert rc == 1
    assert gh.closes() == []
    assert len(lines) == 1
    assert lines[0].startswith("#52: left open, committed ") and "push refused" in lines[0]


@needs_git
def test_dirty_or_already_pinned_workflow_is_left_open(tmp_path):
    repo = Repo(tmp_path / "dirty")
    repo.ci.write_bytes(CI_YML.encode("ascii") + b"# local edit\n")
    gh = RecordingGh()
    rc, lines = _run(repo, ["apply", "52"], gh, Gates())
    assert rc == 0
    assert lines == ["#52: left open, local edits in the workflow files"]
    assert [c for c in gh.calls if c[:1] == ["api"]] == []
    # a workflow already pinned to the tag's commit and comment: no change
    repo = Repo(tmp_path / "pinned")
    pinned = CI_YML.replace("%s # v1.0.0" % OLD_SHA, "%s # v1.1.0" % NEW_SHA)
    repo.ci.write_bytes(pinned.encode("ascii"))
    repo.run(repo.work, "commit", "-q", "-a", "-m",
             "chore: pin")
    gates = Gates()
    rc, lines = _run(repo, ["apply", "52"], RecordingGh(), gates)
    assert rc == 0
    assert lines == ["#52: left open, example-org/setup-thing v1.1.0 is already pinned"]
    assert gates.seen == [] and repo.verbs("commit", "push") == []


# ----------------------------------------------------- npm bump (real git)

NPM_FIXTURE = ROOT / "tests" / "fixtures" / "dependabot" / "pr_npm.json"
NOW = 1795000000.0
PKG_JSON = (
    '{\n  "name": "made-up-app",\n  "version": "0.1.0",\n'
    '  "private": true,\n  "dependencies": {\n    "electron": "45.3.3"\n  }\n}\n')


def _lock(lib, electron="45.3.3"):
    return json.dumps({
        "name": "made-up-app", "version": "0.1.0", "lockfileVersion": 3,
        "requires": True,
        "packages": {
            "": {"name": "made-up-app", "version": "0.1.0",
                 "dependencies": {"electron": electron}},
            "node_modules/electron": {"version": electron,
                                      "dependencies": {"made-up-lib": "^3.2.0"}},
            "node_modules/made-up-lib": {"version": lib},
        }}, indent=2) + "\n"


def _iso(epoch):
    import time as _t
    return _t.strftime("%Y-%m-%dT%H:%M:%S.000Z", _t.gmtime(epoch))


class FakeNpm:
    """npm as a recording fake: view answers publish times, install
    re-writes the lockfile the way npm normalises it (here: the same JSON
    dumped again), audit signatures answers audit_rc. No network."""

    def __init__(self, lock_file, published, audit_rc=0):
        self.lock_file = lock_file
        self.published = published
        self.audit_rc = audit_rc
        self.calls = []

    def __call__(self, args):
        args = list(args)
        self.calls.append(args)
        if args[:1] == ["view"]:
            return 0, json.dumps({"3.2.1": _iso(NOW - 90 * 86400),
                                  "3.2.2": _iso(self.published)})
        if args[:1] == ["install"]:
            data = json.loads(self.lock_file.read_text(encoding="utf-8"))
            self.lock_file.write_text(json.dumps(data, indent=2) + "\n",
                                      encoding="utf-8", newline="\n")
            return 0, ""
        if args[:2] == ["audit", "signatures"]:
            return self.audit_rc, ""
        return 1, ""


class NpmRepo(Repo):
    """Repo plus app/package.json and its lockfile on main, and a Dependabot
    head commit on origin that bumps made-up-lib in the lockfile only."""

    def __init__(self, tmp_path):
        super().__init__(tmp_path)
        off = "core.hooksPath=%s" % (tmp_path / "nohooks")
        app = self.work / "app"
        app.mkdir()
        (app / "package.json").write_bytes(PKG_JSON.encode("ascii"))
        self.lock = app / "package-lock.json"
        self.lock.write_bytes(_lock("3.2.1").encode("ascii"))
        self.run(self.work, "-c", off, "add", "app")
        self.run(self.work, "-c", off, "commit", "-q", "-m", "chore: app")
        self.run(self.work, "-c", off, "push", "-q", "origin", "main")
        branch = "dependabot/npm/made-up-lib"
        self.run(self.work, "checkout", "-q", "-b", branch)
        self.lock.write_bytes(_lock("3.2.2").encode("ascii"))
        self.run(self.work, "-c", off, "commit", "-q", "-a", "-m", "deps: bump")
        self.head_sha = self.out("rev-parse", "HEAD")
        self.run(self.work, "-c", off, "push", "-q", "origin", branch)
        self.run(self.work, "checkout", "-q", "main")
        self.run(self.work, "branch", "-q", "-D", branch)
        self.calls = []


def _npm_gh(head_sha, numbers):
    gh = RecordingGh()
    prs = json.loads(NPM_FIXTURE.read_text(encoding="utf-8"))
    for p in prs:
        if p["number"] == 61:
            p["headRefOid"] = head_sha
    gh.prs = [p for p in prs if p["number"] in numbers]
    return gh


def _run_npm(repo, argv, gh, npm, gates):
    lines = []
    rc = dr.main(argv, root=repo.work, git=repo, gh=gh, npm=npm,
                 clock=lambda: NOW, say=lines.append, gates=gates)
    return rc, lines


VIEW = ["view", "made-up-lib", "time", "--json", "--prefix", "app"]


def test_npm_fixture_is_ascii_and_made_up():
    raw = NPM_FIXTURE.read_bytes()
    raw.decode("ascii")
    assert b"\r" not in raw
    data = json.loads(raw)
    assert [p["number"] for p in data] == [61, 62]
    assert [dr.kind(p) for p in data] == ["npm", "npm"]
    assert dr.parse_npm_bump(data[0]["title"]) == ("made-up-lib", "3.2.1", "3.2.2")
    assert dr.parse_npm_bump(data[1]["title"]) == ("electron", "45.3.3", "45.3.4")
    assert dr.parse_npm_bump("build(deps): bump @made-up/scoped from 1.0.0 to 1.0.1") \
        == ("@made-up/scoped", "1.0.0", "1.0.1")
    assert dr.parse_npm_bump("Bump the npm_and_yarn group across 1 directory") is None


@needs_git
def test_npm_bump_regenerates_lockfile_and_closes(tmp_path):
    repo = NpmRepo(tmp_path / "ok")
    base = repo.out("rev-parse", "HEAD")
    gh = _npm_gh(repo.head_sha, [61])
    npm = FakeNpm(repo.lock, published=NOW - 5 * 86400)
    gates = Gates()
    rc, lines = _run_npm(repo, ["run"], gh, npm, gates)
    assert rc == 0, lines
    head = repo.out("rev-parse", "HEAD")
    # the pin procedure, in order: age, regenerate without scripts, audit
    assert npm.calls == [
        VIEW,
        ["install", "--prefix", "app", "--package-lock-only", "--ignore-scripts"],
        ["audit", "signatures", "--prefix", "app"]]
    assert len(gates.seen) == 1
    # one operator commit of the lockfile only, pushed and closed
    assert repo.out("rev-list", "--count", "%s..HEAD" % base) == "1"
    assert repo.out("log", "-1", "--format=%an <%ae>") == "%s <%s>" % OPERATOR
    assert repo.out("log", "-1", "--format=%cn <%ce>") == "%s <%s>" % OPERATOR
    assert repo.out("log", "-1", "--format=%B") == \
        "deps(npm): bump made-up-lib from 3.2.1 to 3.2.2"
    assert repo.out("log", "-1", "--format=%(trailers)") == ""
    assert repo.out("diff", "--name-only", "%s..HEAD" % base) == "app/package-lock.json"
    locked = json.loads(repo.lock.read_text(encoding="utf-8"))["packages"]
    assert locked["node_modules/made-up-lib"]["version"] == "3.2.2"
    assert locked["node_modules/electron"]["version"] == "45.3.3"
    assert repo.verbs("push") == [["push", "origin", "main"]]
    assert repo.out("rev-parse", "main", cwd=repo.bare) == head
    assert gh.closes() == [["pr", "close", "61", "--repo", REPO, "--comment",
                            "Applied locally as %s." % head]]
    assert not any("merge" in c for c in gh.calls)
    assert "#61: applied locally as %s, pushed, closed" % head in lines
    assert lines[-1] == "left open: 0"
    assert repo.out("status", "--porcelain") == ""
    # a failed signature audit restores the lockfile and commits nothing
    repo2 = NpmRepo(tmp_path / "audit")
    base2 = repo2.out("rev-parse", "HEAD")
    before = repo2.lock.read_bytes()
    npm2 = FakeNpm(repo2.lock, published=NOW - 5 * 86400, audit_rc=1)
    gh2 = _npm_gh(repo2.head_sha, [61])
    rc, lines = _run_npm(repo2, ["apply", "61"], gh2, npm2, Gates())
    assert rc == 1
    assert lines == ["#61: left open, npm audit signatures failed (rc 1)"]
    assert repo2.lock.read_bytes() == before
    assert repo2.out("rev-parse", "HEAD") == base2
    assert repo2.verbs("commit", "push") == [] and gh2.closes() == []


@needs_git
def test_npm_bump_younger_than_three_days_waits(tmp_path):
    repo = NpmRepo(tmp_path)
    base = repo.out("rev-parse", "HEAD")
    before = repo.lock.read_bytes()
    gh = _npm_gh(repo.head_sha, [61])
    published = NOW - 3 * 86400 + 60
    npm = FakeNpm(repo.lock, published=published)
    gates = Gates()
    rc, lines = _run_npm(repo, ["run"], gh, npm, gates)
    assert rc == 0, lines
    # only the age read ran; nothing fetched, regenerated, gated or committed
    assert npm.calls == [VIEW]
    assert gates.seen == []
    assert repo.lock.read_bytes() == before
    assert repo.out("rev-parse", "HEAD") == base
    assert repo.verbs("commit", "push", "fetch") == []
    assert gh.closes() == []
    assert [x for x in lines if x.startswith("#61:")] == [
        "#61: left open, made-up-lib 3.2.2 is under 3 days old (published %s), waits"
        % _iso(published)]
    assert lines[-1] == "left open: 1"


def test_electron_bump_is_a_signal_only(tmp_path):
    prs = json.loads(NPM_FIXTURE.read_text(encoding="utf-8"))
    electron = [p for p in prs if p["number"] == 62]
    npm_calls = []

    def npm(args):
        npm_calls.append(list(args))
        return 1, ""

    # with the Electron bump procedure's files present: closed with one line
    for rel in dr.ELECTRON_PROCEDURE_FILES:
        assert (ROOT / rel).is_file(), rel
    gh, git, lines = FakeGh(prs=electron), FakeGit(), []
    rc = dr.main(["run"], root=ROOT, git=git, gh=gh, npm=npm,
                 clock=lambda: NOW, say=lines.append, gates=Gates())
    assert rc == 0, lines
    assert gh.closes() == [["pr", "close", "62", "--repo", REPO, "--comment",
                            dr.ELECTRON_COMMENT]]
    assert "Electron bump procedure" in dr.ELECTRON_COMMENT
    assert ("#62: closed, electron 45.3.4 moves only through the Electron bump "
            "procedure (decision 0070)") in lines
    # no commit, no npm call, no git call past the origin read
    assert git.calls == [["remote", "get-url", "origin"]]
    assert npm_calls == []
    assert lines[-1] == "left open: 0"
    # before the procedure exists (a root without its files): left open
    gh, git, lines = FakeGh(prs=electron), FakeGit(), []
    rc = dr.main(["apply", "62"], root=tmp_path, git=git, gh=gh, npm=npm,
                 clock=lambda: NOW, say=lines.append, gates=Gates())
    assert rc == 0
    assert gh.closes() == []
    assert lines == ["#62: left open, electron 45.3.4 waits for the Electron "
                     "bump procedure (decision 0070)"]
    assert git.calls == [["remote", "get-url", "origin"]] and npm_calls == []


def test_grouped_single_dependency_title():
    g = "chore(deps): bump electron from 45.3.3 to 45.3.4 in /app in the npm-all group"
    assert dr.parse_npm_bump(g) == ("electron", "45.3.3", "45.3.4")
    assert dr.parse_npm_bump("Bump made-up-lib from 1.0.0 to 1.0.1 in /app in the npm-all group")         == ("made-up-lib", "1.0.0", "1.0.1")
    assert dr.parse_bump("Bump example-org/x from v4 to v5 in /.github/workflows "
                         "in the actions-all group") == ("example-org/x", "4", "5")
    assert dr.parse_npm_bump("Bump a from 1.0.0 to 1.0.1 in /app in the x group extra") is None


def test_multi_dependency_group_title_is_needs_review():
    class Ctx:
        left_open = []
        seam_rc = 0
    title = "chore(deps): bump the npm-all group across 1 directory with 3 updates"
    assert dr.parse_npm_bump(title) is None
    out = dr.apply_npm(Ctx(), {"number": 7, "title": title, "files": []})
    assert out.startswith("left open, needs review (group title names several bumps")
    assert Ctx.left_open == [7]
