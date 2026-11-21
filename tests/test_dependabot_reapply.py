"""GP-14: tools/dependabot_reapply.py lists open Dependabot pull requests,
closes one that touches the vendored identity-guard copy with one line, and
leaves every other bump open with one report line while its apply seam is
empty. git, gh and the clock are recording fakes: no network, no real git.
Fixture names are made up."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import dependabot_reapply as dr  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "dependabot" / "pr_guard.json"
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
    deps, lines = make()
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
    deps, _lines = make()
    dr.main(["run"], **deps)
    assert not any("merge" in c for c in deps["gh"].calls)
    assert deps["git"].calls == [["remote", "get-url", "origin"]]


def test_filled_seam_is_called_and_its_line_reported():
    seen = []

    def fake_actions(ctx, pr):
        seen.append(pr["number"])
        return "applied locally as abc1234"

    deps, lines = make(seams={"actions": fake_actions, "npm": dr.apply_npm})
    assert dr.main(["run"], **deps) == 0
    assert seen == [42]
    assert "#42: applied locally as abc1234" in lines
    assert "#43: left open, needs PUB-DEPBOT-NPM" in lines


def test_default_seams_are_empty():
    r = dr.Reapply(root=ROOT, git=FakeGit(), gh=FakeGh(), say=lambda _l: None)
    assert r.seams["actions"] is dr.apply_actions
    assert r.seams["npm"] is dr.apply_npm
    assert dr.apply_actions(r, {"number": 1}) is None
    assert dr.apply_npm(r, {"number": 1}) is None


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
    deps, lines = make()
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
    deps, lines = make(gh=FakeGh(close_rc=1))
    assert dr.main(["run"], **deps) == 1
    assert "#41: gh pr close failed (rc 1), left open" in lines
    assert "upstream: #41" not in lines


def test_usage_error_exits_two():
    deps, _lines = make()
    assert dr.main(["bogus"], **deps) == 2
    assert dr.main(["close", "x"], **deps) == 2
