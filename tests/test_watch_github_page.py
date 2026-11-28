"""REVIEW-GH (decision 0088): the 'github-page' watcher source. Every read is
an injected gh runner over fixtures in tmp_path; no request, no gh, no
process (a scratch git repo only for the filing tests)."""

import datetime as _dt
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import upstream_watch as uw  # noqa: E402
import watch_file  # noqa: E402
import watch_gate  # noqa: E402
import watch_rows  # noqa: E402
from watch_sources import ci_issues, dependabot, github_page  # noqa: E402,F401

from server.al import webfetch  # noqa: E402

DAY = 24 * 3600
WEEK = 7 * DAY
NOW = _dt.datetime(2026, 11, 27, 12, 0).timestamp()
REMOTE = "https://github.com/someone/thing.git"
P_REPO = "repos/someone/thing"
P_REL = "repos/someone/thing/releases?per_page=10"
P_README = "repos/someone/thing/commits?path=README.md&per_page=1"
P_COMM = "repos/someone/thing/community/profile"
API = "https://api.github.com/repos/someone/thing"
ALL_FILES = {"readme": {"url": "x"}, "license": {"url": "x"}, "contributing": {"url": "x"},
             "code_of_conduct": {"url": "x"}, "issue_template": {"url": "x"},
             "pull_request_template": {"url": "x"}}


def _root(tmp_path, web_data=True, roadmap="# Roadmap\n"):
    root = tmp_path / "root"
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "local.json").write_text(json.dumps({"web_data": web_data}),
                                                encoding="ascii")
    (root / "ROADMAP.md").write_bytes(roadmap.encode("ascii"))
    return root


class Gh:
    """Records every gh argv; answers the four page reads from fixtures."""

    def __init__(self, code=0):
        self.calls, self.code = [], code
        self.meta = {"description": "A companion", "topics": ["a", "b"],
                     "homepage": "https://example.org/", "has_discussions": False}
        self.releases = [{"tag_name": "v0.2.0", "draft": True},
                         {"tag_name": "v0.1.0", "draft": False}]
        self.readme = "a" * 40
        self.files = dict(ALL_FILES)
        self.health = 100

    def __call__(self, argv, cwd):
        self.calls.append(list(argv))
        body = {P_REPO: self.meta, P_REL: self.releases,
                P_README: [{"sha": self.readme}],
                P_COMM: {"health_percentage": self.health, "files": self.files}}[argv[-1]]
        return self.code, json.dumps(body)


def _check(root, gh, now=NOW, state=None):
    ctx = {"root": root, "remote_url": REMOTE, "gh": gh}
    return github_page.check(state if state is not None else {}, now, None, ctx)


def _render(f, today="2026-11-27"):
    return watch_rows.render(watch_rows.load(ROOT), f["kind"], f["tokens"], today)


# ---------------------------------------------------------------- the row

def test_first_run_files_one_open_review_row(tmp_path):
    gh = Gh()
    found = _check(_root(tmp_path), gh)
    assert [(f["kind"], f["key"]) for f in found] == [("ghreview", "review:20261127")]
    t = found[0]["tokens"]
    assert t["why"] == "first" and t["readme"] == "a" * 12 and t["release"] == "v0.1.0"
    assert (t["homepage"], t["desc"], t["topics"], t["missing"]) == ("set", "set", "2", "none")
    rid, text = _render(found[0])
    assert rid == "REVIEW-GH-20261127"
    assert text.startswith(f"- [ ] {rid} (review) ")
    assert "BLOCKED" not in text and text.isascii() and len(text) <= 700
    for word in ("ACCEPT:", "ZERO-CLICK:", "SOURCE: watch github-page", "README.md",
                 "docs/guide/", "SECURITY.md", "CONTRIBUTING.md", "design-reviewer",
                 "UI/UX", "visual", "readability", "comprehension", "ease of use",
                 "ease of setup", "Quick start", "docs/reviews/github/2026-11-27.md"):
        assert word in text, word
    for argv in gh.calls:  # the AshLight User-Agent rides every read
        ua = argv[argv.index("-H", argv.index("-H") + 1) + 1]
        assert ua == "User-Agent: " + webfetch.user_agent("dev: watcher github-page")
    assert [a[-1] for a in gh.calls] == [P_REPO, P_REL, P_README, P_COMM]


def test_template_tokens_refuse_upstream_text():
    table = watch_rows.load(ROOT)
    good = dict(table["ghreview"]["sample"])
    assert watch_rows.render(table, "ghreview", good, "2026-11-27")[0] == "REVIEW-GH-20261127"
    for name, bad in (("release", "release notes here"), ("readme", "A" * 12),
                      ("why", "weekly-blocked"), ("missing", "Contributing"),
                      ("homepage", "https://x")):
        rid, why = watch_rows.render(table, "ghreview", dict(good, **{name: bad}), "2026-11-27")
        assert rid is None, (name, why)
    rid, _ = watch_rows.render(table, "ghreview", {"why": "first"}, "2026-11-27")
    assert rid is None


def test_odd_values_fold_to_fixed_words(tmp_path):
    gh = Gh()
    gh.meta = {"description": "  ", "homepage": None, "topics": "x"}
    gh.releases = [{"tag_name": "nightly build", "draft": False}]
    gh.readme = "not-a-sha"
    gh.files = {"readme": None}
    gh.health = True
    t = _check(_root(tmp_path), gh)[0]["tokens"]
    assert (t["release"], t["readme"], t["homepage"], t["desc"], t["topics"]) == \
        ("other", "other", "empty", "empty", "0")
    assert t["missing"] == "readme.license.contributing.conduct.issues.pr"
    assert t["why"] == "homepage-community"
    assert _render(_check(_root(tmp_path), gh)[0])[0] == "REVIEW-GH-20261127"
    gh.releases = []
    assert _check(_root(tmp_path), gh)[0]["tokens"]["release"] == "none"


# ---------------------------------------------------------------- cadence and drift

def _frame(root, gh, now, entry):
    src = uw.normalize(github_page)
    q = []
    uw._run_one(root, src, entry, now, None, {"root": root, "remote_url": REMOTE, "gh": gh}, q)
    return q


def test_cadence_is_seven_days_in_the_network_group(tmp_path):
    src = uw.normalize(github_page)
    assert uw.is_network(src) and src["home"] == "loop" and src["cadence_s"] == WEEK
    entry = uw._entry()
    assert uw._due(src, entry, NOW)
    _frame(_root(tmp_path), Gh(), NOW, entry)
    assert not uw._due(src, entry, NOW + WEEK - 60)
    assert uw._due(src, entry, NOW + WEEK)


def test_weekly_row_when_nothing_moved_and_no_row_is_open(tmp_path):
    root, gh, entry = _root(tmp_path), Gh(), uw._entry()
    q1 = _frame(root, gh, NOW, entry)
    q2 = _frame(root, gh, NOW + WEEK, entry)
    assert [f["tokens"]["why"] for f in q1 + q2] == ["first", "weekly"]
    assert [f["key"] for f in q2] == ["review:20261204"]


def test_open_review_row_holds_a_quiet_week(tmp_path):
    root = _root(tmp_path, roadmap="# Roadmap\n\n- [ ] REVIEW-GH-20261127 (review) Old one.\n")
    gh, entry = Gh(), uw._entry()
    assert len(_frame(root, gh, NOW, entry)) == 1
    assert _frame(root, gh, NOW + WEEK, entry) == []
    assert "still open" in entry["data"]["skipped"]
    (root / "docs" / "roadmap" / "done").mkdir(parents=True)
    (root / "docs" / "roadmap" / "done" / "REVIEW-GH-20261127.md").write_bytes(
        b" -- done 2026-12-01 (reviewed)\n")
    q3 = _frame(root, gh, NOW + 2 * WEEK, entry)
    assert [f["tokens"]["why"] for f in q3] == ["weekly"]


@pytest.mark.parametrize("change, why", [
    (lambda g: setattr(g, "readme", "b" * 40), "readme"),
    (lambda g: g.releases.insert(0, {"tag_name": "v0.3.0", "draft": False}), "release"),
    (lambda g: g.meta.update(homepage=""), "homepage"),
    (lambda g: g.files.update(contributing=None), "community"),
])
def test_drift_files_a_row_even_while_one_is_open(tmp_path, change, why):
    root = _root(tmp_path, roadmap="# Roadmap\n\n- [ ] REVIEW-GH-20261120 (review) Old one.\n")
    gh, entry = Gh(), uw._entry()
    _frame(root, gh, NOW, entry)
    change(gh)
    q = _frame(root, gh, NOW + WEEK, entry)
    assert [f["tokens"]["why"] for f in q] == [why]
    assert entry["data"]["filed"]["day"] == "20261204"


def test_persistent_gap_does_not_pile_rows_on_an_open_one(tmp_path):
    root = _root(tmp_path, roadmap="# Roadmap\n\n- [ ] REVIEW-GH-20261120 (review) Old one.\n")
    gh, entry = Gh(), uw._entry()
    gh.meta["homepage"] = ""
    assert [f["tokens"]["why"] for f in _frame(root, gh, NOW, entry)] == ["homepage"]
    assert _frame(root, gh, NOW + WEEK, entry) == []


def test_failed_read_keeps_the_filed_baseline(tmp_path):
    root, gh, entry = _root(tmp_path), Gh(), uw._entry()
    _frame(root, gh, NOW, entry)
    before = dict(entry["data"]["filed"])
    assert _frame(root, Gh(code=1), NOW + WEEK, entry) == []
    assert entry["fails"] == 1 and entry["cause"] == "status"
    assert entry["data"]["filed"] == before


# ---------------------------------------------------------------- gates

def test_web_data_off_makes_no_request(tmp_path):
    root = _root(tmp_path, web_data=False)
    gh = Gh()
    with pytest.raises(watch_gate.WebDataOff):
        _check(root, gh)
    assert gh.calls == []
    d = tmp_path / "sources"
    d.mkdir()
    shutil.copyfile(ROOT / "tools" / "watch_sources" / "github_page.py", d / "github_page.py")
    lines = uw.run_due(root, NOW, directory=d, ctx={"root": root, "remote_url": REMOTE, "gh": gh})
    assert gh.calls == [] and any(uw.IDLE_OFF in ln for ln in lines)
    assert uw.load_state(root)["sources"]["github-page"]["idle"] == uw.IDLE_OFF


def test_frame_runs_it_with_web_data_on_and_queues_once(tmp_path):
    root, gh = _root(tmp_path), Gh()
    d = tmp_path / "sources"
    d.mkdir()
    shutil.copyfile(ROOT / "tools" / "watch_sources" / "github_page.py", d / "github_page.py")
    ctx = {"root": root, "remote_url": REMOTE, "gh": gh}
    uw.run_due(root, NOW, directory=d, ctx=ctx)
    uw.run_due(root, NOW + DAY, directory=d, ctx=ctx)  # not due: no read
    assert len(gh.calls) == 4
    assert [f["key"] for f in uw.pending(root)] == ["review:20261127"]


def test_halted_run_still_reads_and_queues_but_files_nothing(tmp_path):
    root, gh = _root(tmp_path), Gh()
    d = tmp_path / "sources"
    d.mkdir()
    shutil.copyfile(ROOT / "tools" / "watch_sources" / "github_page.py", d / "github_page.py")
    lines = uw.run_due(root, NOW, halted=True, directory=d,
                       ctx={"root": root, "remote_url": REMOTE, "gh": gh})
    assert any("HALT" in ln for ln in lines) and len(uw.pending(root)) == 1
    out = watch_file.file_pending(root, NOW, _git, Budget(), halted=True)
    assert out and "HALT" in out[0] and len(uw.pending(root)) == 1


def test_no_live_root_no_runner_or_no_remote_starts_nothing(tmp_path):
    root = _root(tmp_path)
    assert github_page.check({}, NOW, None, {}) == []  # a lane: not live, no root
    assert github_page.check({}, NOW, None, {"root": root, "remote_url": REMOTE}) == []
    gh = Gh()
    ctx = {"root": root, "remote_url": "https://example.invalid/a/b.git", "gh": gh}
    assert github_page.check({}, NOW, None, ctx) == [] and gh.calls == []


def test_only_the_four_metadata_paths_pass_the_gate(tmp_path, monkeypatch):
    for tail in ("", github_page.RELEASES_TAIL, github_page.README_TAIL,
                 github_page.COMMUNITY_TAIL):
        assert watch_gate.check_url(github_page.SOURCE, API + tail).hostname == "api.github.com"
    for bad in ("/readme", "/readme/docs", "/contents/README.md", "/community/profile/x",
                "/community", "/community/code_of_conduct", "/traffic/views",
                "https://www.pathofexile.com/api/x", "https://raw.githubusercontent.com/a/b"):
        url = bad if bad.startswith("https://") else API + bad
        with pytest.raises(webfetch.UrlNotAllowed):
            watch_gate.check_url(github_page.SOURCE, url)
    monkeypatch.setattr(github_page, "API", "https://www.pathofexile.com/repos/")
    gh = Gh()
    with pytest.raises(webfetch.UrlNotAllowed):
        _check(_root(tmp_path), gh)
    assert gh.calls == []


def test_bad_gh_output_is_a_named_cause(tmp_path):
    def junk(argv, cwd):
        return 0, "[]" if argv[-1] == P_REPO else "{}"
    with pytest.raises(uw.SourceError) as e:
        _check(_root(tmp_path), junk)
    assert e.value.cause == "shape"


# ---------------------------------------------------------------- filing

def _env():
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    return env


def _git(args, cwd, input=None):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                          env=_env(), timeout=60)


class Budget:
    cap = 100

    def readable(self):
        return True

    def used(self):
        return 10


def _repo(tmp_path, earlier=0):
    repo = tmp_path / "repo"
    (repo / "ops" / "loop" / "watch_rows").mkdir(parents=True)
    (repo / "ROADMAP.md").write_bytes(b"# Roadmap\n\n- [ ] OLD-ROW (data) An old row.\n")
    (repo / ".gitignore").write_bytes(b"ops/runtime/\n")
    src = ROOT / "ops" / "loop" / "watch_rows" / "github-page.json"
    (repo / "ops" / "loop" / "watch_rows" / "github-page.json").write_bytes(src.read_bytes())
    steps = [["init", "-q", "-b", "main"], ["config", "user.name", "Operator"],
             ["config", "user.email", "operator@example.com"],
             ["config", "commit.gpgsign", "false"], ["config", "core.autocrlf", "false"],
             ["add", "-A"], ["commit", "-q", "-m", "base"]]
    for args in steps:
        r = _git(args, repo)
        assert r.returncode == 0, (args, r.stderr)
    new = repo / "docs" / "roadmap" / "new"
    new.mkdir(parents=True, exist_ok=True)
    for i in range(earlier):
        rid = f"EARLY-{i}"
        (new / f"{rid}.md").write_bytes(f"- [ ] {rid} (data) Filed earlier.\n".encode())
        for args in (["add", "--", f"docs/roadmap/new/{rid}.md"],
                     ["commit", "-q", "-m", f"chore(roadmap): file {rid} (watch dependabot)"]):
            r = _git(args, repo)
            assert r.returncode == 0, (args, r.stderr)
    return repo


def _queue(tmp_path, repo):
    found = _check(_root(tmp_path), Gh())
    uw.set_pending(repo, [dict(f, source="github-page", found="2026-11-27T10:00:00+00:00")
                          for f in found])


def test_row_is_filed_as_one_commit(tmp_path):
    repo = _repo(tmp_path)
    _queue(tmp_path, repo)
    now = time.time()
    lines = watch_file.file_pending(repo, now, _git, Budget())
    day = _dt.datetime.fromtimestamp(now).strftime("%Y%m%d")
    names = sorted(p.name for p in (repo / "docs" / "roadmap" / "new").glob("*.md"))
    assert names == [f"REVIEW-GH-{day}.md"], lines
    assert uw.pending(repo) == []
    subject = _git(["log", "-1", "--format=%s"], repo).stdout.strip()
    assert subject == f"chore(roadmap): file REVIEW-GH-{day} (watch github-page)"


def test_three_a_day_cap_holds_the_row(tmp_path):
    repo = _repo(tmp_path, earlier=3)
    _queue(tmp_path, repo)
    lines = watch_file.file_pending(repo, time.time(), _git, Budget())
    assert not list((repo / "docs" / "roadmap" / "new").glob("REVIEW-GH-*.md"))
    assert len(uw.pending(repo)) == 1 and any("filed today" in ln for ln in lines)


def test_halt_file_files_nothing(tmp_path):
    repo = _repo(tmp_path)
    _queue(tmp_path, repo)
    halt = repo / "ops" / "loop" / "control" / "HALT"
    halt.parent.mkdir(parents=True)
    halt.write_bytes(b"halt\n")
    lines = watch_file.file_pending(repo, time.time(), _git, Budget())
    assert lines and "HALT" in lines[0] and len(uw.pending(repo)) == 1
    assert not list((repo / "docs" / "roadmap" / "new").glob("REVIEW-GH-*.md"))
