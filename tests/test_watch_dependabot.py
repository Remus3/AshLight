"""AUTO-20 (DEPBOT-WATCH): the 'dependabot' watcher source. Every read is an
injected gh runner over fixtures in tmp_path; no request, no gh, no process
(a scratch git repo only for the soft budget gate test)."""

import datetime as _dt
import json
import os
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
from watch_sources import dependabot  # noqa: E402

from server.al import webfetch  # noqa: E402

DAY = 24 * 3600
NOW = _dt.datetime(2026, 11, 27, 12, 0, tzinfo=_dt.timezone.utc).timestamp()
REMOTE = "https://github.com/someone/thing.git"
ALERTS = "repos/someone/thing/dependabot/alerts?state=open&per_page=100"
PULLS = "repos/someone/thing/pulls?state=open&per_page=100"


def _root(tmp_path, web_data=True, names=("electron", "@electron/get")):
    root = tmp_path / "root"
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "app").mkdir(parents=True, exist_ok=True)
    (root / "config" / "local.json").write_text(json.dumps({"web_data": web_data}),
                                                encoding="ascii")
    pkgs = {"": {"name": "ashlight-overlay"}}
    pkgs.update({f"node_modules/{n}": {"version": "1.0.0"} for n in names})
    (root / "app" / "package-lock.json").write_text(
        json.dumps({"lockfileVersion": 3, "packages": pkgs}), encoding="ascii")
    return root


def _alert(name="electron", ghsa="GHSA-8f24-v5vv-gm5j", severity="high", state="open"):
    return {"number": 3, "state": state,
            "dependency": {"package": {"ecosystem": "npm", "name": name},
                           "manifest_path": "app/package-lock.json"},
            "security_advisory": {"ghsa_id": ghsa, "severity": severity}}


def _pr(n=17, login="dependabot[bot]", kind="Bot", title="Bump debug from 4.3.4 to 4.3.5 in /app",
        age_days=3):
    made = _dt.datetime.fromtimestamp(NOW - age_days * DAY, _dt.timezone.utc)
    return {"number": n, "state": "open", "title": title, "draft": False,
            "user": {"login": login, "type": kind},
            "created_at": made.strftime("%Y-%m-%dT%H:%M:%SZ")}


class Gh:
    """Records every gh argv; answers ALERTS and PULLS from fixtures."""

    def __init__(self, alerts=(), pulls=(), code=0):
        self.calls, self.alerts, self.pulls, self.code = [], list(alerts), list(pulls), code

    def __call__(self, argv, cwd):
        self.calls.append(list(argv))
        path = argv[-1]
        body = {ALERTS: self.alerts, PULLS: self.pulls}[path]
        return self.code, json.dumps(body)


def _check(root, gh, now=NOW, state=None):
    ctx = {"root": root, "remote_url": REMOTE, "gh": gh}
    return dependabot.check(state if state is not None else {}, now, None, ctx)


def _render(f, today="2026-11-27"):
    return watch_rows.render(watch_rows.load(ROOT), f["kind"], f["tokens"], today)


# ---------------------------------------------------------------- alerts

def test_recorded_alert_yields_one_priority_row(tmp_path):
    gh = Gh(alerts=[_alert()])
    found = _check(_root(tmp_path), gh)
    assert [f["kind"] for f in found] == ["depbotalert"]
    rid, text = _render(found[0])
    assert rid == "DEPBOT-ELECTRON-GHSA-8F24-V5VV-GM5J"
    assert text.startswith(f"- [ ] {rid} (data) (priority) Dependabot alert ")
    assert "BLOCKED" not in text and text.isascii()
    for argv in gh.calls:  # the AshLight User-Agent rides every read
        ua = argv[argv.index("-H", argv.index("-H") + 1) + 1]
        assert ua == "User-Agent: " + webfetch.user_agent("dev: watcher dependabot")


def test_lower_case_advisory_id_is_upper_cased_and_validated(tmp_path):
    good = _alert(ghsa="ghsa-8f24-v5vv-gm5j", severity="medium")
    bad = _alert(name="@electron/get", ghsa="GHSA-not-an-id")
    found = _check(_root(tmp_path), Gh(alerts=[good, bad]))
    assert len(found) == 1
    assert found[0]["tokens"]["GHSA"] == "GHSA-8F24-V5VV-GM5J"
    assert found[0]["tokens"]["severity"] == "moderate"
    assert found[0]["key"] == "alert:electron:GHSA-8F24-V5VV-GM5J"


def test_package_not_in_the_lockfile_files_nothing(tmp_path):
    alerts = [_alert(name="left-pad"), _alert(name="actions/checkout"),
              _alert(state="dismissed")]
    assert _check(_root(tmp_path), Gh(alerts=alerts)) == []


def test_scoped_package_renders_a_valid_row(tmp_path):
    found = _check(_root(tmp_path), Gh(alerts=[_alert(name="@electron/get")]))
    rid, text = _render(found[0])
    assert rid == "DEPBOT-ELECTRON-GET-GHSA-8F24-V5VV-GM5J" and "electron.get" in text


# ---------------------------------------------------------------- pull requests

def test_open_dependabot_pull_request_yields_one_depbot_pr_row(tmp_path):
    found = _check(_root(tmp_path), Gh(pulls=[_pr()]))
    assert [(f["kind"], f["key"]) for f in found] == [("depbotpr", "pr:17")]
    rid, text = _render(found[0])
    assert rid == "DEPBOT-PR-17"
    assert "dependabot_reapply.py apply 17" in text and "BLOCKED: session" in text


def test_fresh_pull_request_waits_for_the_daily_worker(tmp_path):
    assert _check(_root(tmp_path), Gh(pulls=[_pr(age_days=1)])) == []


def test_no_pr_row_while_an_advisory_row_names_the_package(tmp_path):
    pr = _pr(title="Bump electron from 39.2.3 to 39.2.4 in /app")
    found = _check(_root(tmp_path), Gh(alerts=[_alert()], pulls=[pr, _pr(n=18)]))
    assert [f["key"] for f in found] == ["alert:electron:GHSA-8F24-V5VV-GM5J", "pr:18"]


def test_pull_request_from_another_author_yields_nothing(tmp_path):
    pulls = [_pr(login="someone"), _pr(login="dependabot[bot]", kind="User"),
             _pr(login="dependabot-preview[bot]")]
    assert _check(_root(tmp_path), Gh(pulls=pulls)) == []


# ---------------------------------------------------------------- frame and gates

def test_frame_dedupes_a_finding_across_runs(tmp_path):
    root = _root(tmp_path)
    gh = Gh(alerts=[_alert()], pulls=[_pr()])
    src = uw.normalize(dependabot)
    entry = uw._entry()
    q1, q2 = [], []
    uw._run_one(root, src, entry, NOW, None, {"root": root, "remote_url": REMOTE, "gh": gh}, q1)
    uw._run_one(root, src, entry, NOW + DAY, None,
                {"root": root, "remote_url": REMOTE, "gh": gh}, q2)
    assert sorted(f["key"] for f in q1) == ["alert:electron:GHSA-8F24-V5VV-GM5J", "pr:17"]
    assert q2 == [] and len(gh.calls) == 4


def test_web_data_off_makes_no_request(tmp_path):
    root = _root(tmp_path, web_data=False)
    gh = Gh(alerts=[_alert()])
    with pytest.raises(watch_gate.WebDataOff):
        _check(root, gh)
    assert gh.calls == []
    src = uw.normalize(dependabot)
    assert uw.is_network(src) and src["home"] == "loop" and src["cadence_s"] == DAY


def test_no_runner_or_no_github_remote_starts_nothing(tmp_path):
    root = _root(tmp_path)
    assert dependabot.check({}, NOW, None, {"root": root, "remote_url": REMOTE}) == []
    gh = Gh(alerts=[_alert()])
    ctx = {"root": root, "remote_url": "https://example.invalid/a/b.git", "gh": gh}
    assert dependabot.check({}, NOW, None, ctx) == [] and gh.calls == []
    assert dependabot.check({}, NOW, None, {}) == []


def test_refused_hosts_and_sub_paths_never_reach_gh(tmp_path, monkeypatch):
    repo = "https://api.github.com/repos/someone/thing"
    for tail in (dependabot.ALERTS_TAIL, dependabot.PULLS_TAIL):
        assert watch_gate.check_url(dependabot.SOURCE, repo + tail).hostname == "api.github.com"
    for bad in (repo + "/pulls/1", repo + "/pulls/1/merge", repo + "/dependabot/alerts/1",
                repo + "/dependabot/secrets", "https://www.pathofexile.com/api/x",
                "https://poe.ninja/api/data/x", "https://example.com/pulls"):
        with pytest.raises(webfetch.UrlNotAllowed):
            watch_gate.check_url(dependabot.SOURCE, bad)
    monkeypatch.setattr(dependabot, "API", "https://www.pathofexile.com/repos/")
    gh = Gh(alerts=[_alert()])
    with pytest.raises(webfetch.UrlNotAllowed):
        _check(_root(tmp_path), gh)
    assert gh.calls == []


def test_gh_failure_or_bad_output_is_a_named_cause(tmp_path):
    with pytest.raises(uw.SourceError) as e:
        _check(_root(tmp_path), Gh(code=1))
    assert e.value.cause == "status"

    def junk(argv, cwd):
        return 0, "not json"
    with pytest.raises(uw.SourceError) as e:
        _check(_root(tmp_path), junk)
    assert e.value.cause == "shape"


def test_no_workflow_is_added_for_the_dependabot_read():
    """The dev-loop source does the read; no CI job holds the alert scope."""
    wf = ROOT / ".github" / "workflows"
    assert not (wf / "watch-dependabot.yml").exists()
    for path in wf.glob("*.yml"):
        assert "vulnerability-alerts" not in path.read_text(encoding="utf-8"), path.name


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
        return 90  # over the 60 percent soft gate


def test_soft_budget_gate_does_not_hold_the_row(tmp_path):
    repo = tmp_path / "repo"
    (repo / "ops" / "loop" / "watch_rows").mkdir(parents=True)
    (repo / "ROADMAP.md").write_bytes(b"# Roadmap\n\n- [ ] OLD-ROW (data) An old row.\n")
    (repo / ".gitignore").write_bytes(b"ops/runtime/\n")
    src = ROOT / "ops" / "loop" / "watch_rows" / "dependabot.json"
    (repo / "ops" / "loop" / "watch_rows" / "dependabot.json").write_bytes(src.read_bytes())
    for args in (["init", "-q", "-b", "main"], ["config", "user.name", "Operator"],
                 ["config", "user.email", "operator@example.com"],
                 ["config", "commit.gpgsign", "false"], ["config", "core.autocrlf", "false"],
                 ["add", "-A"], ["commit", "-q", "-m", "base"]):
        r = _git(args, repo)
        assert r.returncode == 0, (args, r.stderr)
    root = _root(tmp_path)
    found = _check(root, Gh(alerts=[_alert()], pulls=[_pr()]))
    uw.set_pending(repo, [dict(f, source="dependabot", found="2026-11-27T10:00:00+00:00")
                          for f in found])
    assert watch_file.soft_gate_open(Budget()) is False
    lines = watch_file.file_pending(repo, time.time(), _git, Budget())
    new = sorted(p.name for p in (repo / "docs" / "roadmap" / "new").glob("*.md"))
    assert new == ["DEPBOT-ELECTRON-GHSA-8F24-V5VV-GM5J.md"], lines
    assert [f["key"] for f in uw.pending(repo)] == ["pr:17"]  # held by the soft gate
