"""LOOP-CI-ISSUES (CI-WATCH tick half, F-150; decisions 0076 item 6, 0069):
the ci-issues watch source. Hermetic: the source file is copied into a tmp
folder and run through the tools/upstream_watch.py frame with a fake
transport and fixture replies; every state file lives under tmp_path. No
socket is opened, no real GitHub issue is read or touched."""

import datetime as dt
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import upstream_watch as uw  # noqa: E402
import watch_rows  # noqa: E402
from loop_base import ROW_RX  # noqa: E402

SRC_FILE = ROOT / "tools" / "watch_sources" / "ci_issues.py"
NOW = dt.datetime(2026, 11, 20, 12, 0).timestamp()
HOUR = 3600.0
DAY = 24 * HOUR
REMOTE = "https://github.com/someone/ashlight-test.git"
API = "https://api.github.com/repos/someone/ashlight-test"
WF = API + "/actions/workflows/watch.yml"
RUNS = WF + "/runs?status=success&per_page=1"
ISSUES = API + "/issues?labels=al-watch&state=open&per_page=100"
BOT = "github-actions[bot]"


def _gh(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _issue(n, body, login=BOT, pr=False):
    doc = {"number": n, "user": {"login": login}, "body": body,
           "labels": [{"name": "al-watch"}], "title": "al-watch: x"}
    if pr:
        doc["pull_request"] = {"url": "x"}
    return doc


class Transport:
    """Fixture replies by exact URL; records every request."""

    def __init__(self, replies):
        self.replies = dict(replies)
        self.calls = []

    def __call__(self, method, url, headers, body=None):
        self.calls.append(url)
        if url not in self.replies:
            return 404, {}, b"{}"
        reply = self.replies[url]
        reply = reply() if callable(reply) else reply
        return 200, {}, json.dumps(reply).encode("utf-8")


def _setup(tmp_path, web_data=True):
    src_dir = tmp_path / "sources"
    src_dir.mkdir(parents=True)
    shutil.copy(SRC_FILE, src_dir / SRC_FILE.name)
    root = tmp_path / "root"
    (root / "config").mkdir(parents=True)
    (root / "config" / "local.json").write_text(json.dumps({"web_data": web_data}),
                                                encoding="utf-8")
    return root, src_dir


def _ctx(root, t, sources=()):
    return {"root": str(root), "remote_url": REMOTE, "transport": t,
            "watch_sources": list(sources)}


def _healthy(now, issues):
    return {WF: {"state": "active"},
            RUNS: {"total_count": 1, "workflow_runs": [{"created_at": _gh(now - 5 * HOUR)}]},
            ISSUES: issues}


def _render(finding):
    table = watch_rows.load(ROOT)
    return watch_rows.render(table, finding["kind"], finding["tokens"], "2026-11-20")


def test_one_valid_key_and_one_forged_issue_file_exactly_one_row(tmp_path):
    root, src_dir = _setup(tmp_path)
    issues = [
        _issue(1, "AL-WATCH key=pob-release:v0.24.0 v=1"),
        _issue(2, "AL-WATCH key=electron:39.2.0 v=1", login="someone-else"),
        _issue(3, "AL-WATCH key=electron:39.2.1 v=1", pr=True),
        _issue(4, "AL-WATCH key=pob-release:v0.24.0 v=1"),  # duplicate key
    ]
    t = Transport(_healthy(NOW, issues))
    ctx = _ctx(root, t)
    uw.run_due(root, NOW, fetch=t, directory=src_dir, ctx=ctx)
    assert t.calls == [WF, RUNS] and uw.pending(root) == []
    uw.run_due(root, NOW + 3 * HOUR, fetch=t, directory=src_dir, ctx=ctx)
    assert t.calls[2:] == [ISSUES]
    found = uw.pending(root)
    assert len(found) == 1
    f = found[0]
    assert (f["source"], f["kind"], f["key"]) == ("ci-issues", "cikey", "pob-release:v0.24.0")
    row_id, text = _render(f)
    assert row_id == "CI-WATCH-POB-RELEASE-V0-24-0"
    m = ROW_RX.match(text)
    assert m and m.group(2) == row_id and text.count("\n") <= 1
    # the next issue read (6 h later) queues nothing again; 3 h later no read
    uw.run_due(root, NOW + 6 * HOUR, fetch=t, directory=src_dir, ctx=ctx)
    assert t.calls[3:] == []
    uw.run_due(root, NOW + 9 * HOUR, fetch=t, directory=src_dir, ctx=ctx)
    assert t.calls[3:] == [ISSUES] and len(uw.pending(root)) == 1


def test_body_with_extra_text_is_ignored(tmp_path):
    root, src_dir = _setup(tmp_path)
    issues = [
        _issue(1, "AL-WATCH key=pob-release:v0.24.0 v=1 extra"),
        _issue(2, "AL-WATCH key=pob-release:v0.24.1 v=1\n"),
        _issue(3, "AL-WATCH key=pob-release:v0.24.2 v=1\nmore text"),
        _issue(4, " AL-WATCH key=pob-release:v0.24.3 v=1"),
        _issue(5, "Please read: AL-WATCH key=pob-release:v0.24.4 v=1"),
        _issue(6, "AL-WATCH key=pob-release:v0.24.5 v=2"),
        _issue(7, None),
        _issue(8, "AL-WATCH key=pob-release:BLOCKED-x v=1"),
        _issue(9, "AL-WATCH key=pob-release:a/b?c v=1"),
        _issue(10, "AL-WATCH key=pob-release:" + "x" * 70 + " v=1"),
    ]
    t = Transport(_healthy(NOW, issues))
    ctx = _ctx(root, t)
    uw.run_due(root, NOW, fetch=t, directory=src_dir, ctx=ctx)
    lines = uw.run_due(root, NOW + 3 * HOUR, fetch=t, directory=src_dir, ctx=ctx)
    assert ISSUES in t.calls
    assert uw.pending(root) == [], lines
    # a key the loop already queued for that source itself is skipped too
    st = uw.load_state(root)
    st["sources"]["pob-release"] = uw._entry({"seen": ["v0.30.0"]})
    st["sources"]["ci-issues"]["data"]["issues_at"] = None
    uw.save_state(root, st)
    t.replies[ISSUES] = [_issue(11, "AL-WATCH key=pob-release:v0.30.0 v=1")]
    uw.run_due(root, NOW + 6 * HOUR, fetch=t, directory=src_dir, ctx=ctx)
    assert t.calls[-1] == ISSUES and uw.pending(root) == []


def _fake_ci_source(calls):
    url = "https://api.github.com/repos/upstream/tool/releases/latest"

    def check(state, now, fetch, ctx):
        status, _h, body = fetch(url)
        calls.append((now, status))
        return [{"kind": "pobrelease", "key": "v9.9.9",
                 "tokens": {"VTAG": "V9-9-9", "tag": "v9.9.9", "pin": "v9.9.8",
                            "verdict": "green"}}]

    return uw.normalize({"name": "fake-ci", "home": "ci", "cadence_s": 6 * HOUR,
                         "hosts": ["api.github.com"], "check": check}), url


def test_disabled_inactivity_switches_the_tick_to_failover(tmp_path):
    root, src_dir = _setup(tmp_path)
    calls = []
    fake, fake_url = _fake_ci_source(calls)
    replies = _healthy(NOW, [_issue(1, "AL-WATCH key=pob-release:v0.24.0 v=1")])
    replies[WF] = {"state": "disabled_inactivity"}
    replies[fake_url] = {"tag_name": "v9.9.9"}
    t = Transport(replies)
    ctx = _ctx(root, t, [fake])
    uw.run_due(root, NOW, fetch=t, directory=src_dir, ctx=ctx)
    assert t.calls == [WF, RUNS] and calls == []
    data = uw.load_state(root)["sources"]["ci-issues"]["data"]
    assert data["workflow_state"] == "disabled_inactivity" and data["failover_since"]
    uw.run_due(root, NOW + 3 * HOUR, fetch=t, directory=src_dir, ctx=ctx)
    # the tick ran the ci-home source itself, through the gated fetch, and
    # no issue list was read
    assert t.calls[2:] == [fake_url] and calls == [(NOW + 3 * HOUR, 200)]
    found = uw.pending(root)
    assert [(f["source"], f["kind"], f["key"]) for f in found] == [
        ("ci-issues", "pobrelease", "fake-ci:v9.9.9")]
    assert _render(found[0])[0] == "POB-V9-9-9"
    # its own cadence holds (6 h): nothing 3 h later, again at 9 h
    uw.run_due(root, NOW + 6 * HOUR, fetch=t, directory=src_dir, ctx=ctx)
    assert t.calls[3:] == []
    uw.run_due(root, NOW + 9 * HOUR, fetch=t, directory=src_dir, ctx=ctx)
    assert t.calls[3:] == [fake_url] and len(uw.pending(root)) == 1
    # the workflow comes back active with a fresh run: issues read again
    t.replies[WF] = {"state": "active"}
    t.replies[RUNS] = {"workflow_runs": [{"created_at": _gh(NOW + 23 * HOUR)}]}
    uw.run_due(root, NOW + 24 * HOUR, fetch=t, directory=src_dir, ctx=ctx)
    assert t.calls[4:] == [WF, RUNS]
    assert "failover_since" not in uw.load_state(root)["sources"]["ci-issues"]["data"]
    uw.run_due(root, NOW + 27 * HOUR, fetch=t, directory=src_dir, ctx=ctx)
    assert t.calls[6:] == [ISSUES]


def test_48_hours_silent_also_fails_over_and_no_remote_files_nothing(tmp_path):
    root, src_dir = _setup(tmp_path)
    replies = _healthy(NOW, [])
    replies[RUNS] = {"workflow_runs": [{"created_at": _gh(NOW - 49 * HOUR)}]}
    t = Transport(replies)
    uw.run_due(root, NOW, fetch=t, directory=src_dir, ctx=_ctx(root, t))
    assert uw.load_state(root)["sources"]["ci-issues"]["data"]["failover_since"]
    # no remote (scratch root, not live): no request, nothing filed
    root2, src2 = _setup(tmp_path / "b")
    t2 = Transport(replies)
    uw.run_due(root2, NOW, fetch=t2, directory=src2,
               ctx={"root": str(root2), "transport": t2, "watch_sources": []})
    assert t2.calls == [] and uw.pending(root2) == []
    # web data off: the source is not called at all
    root3, src3 = _setup(tmp_path / "c", web_data=False)
    t3 = Transport(replies)
    uw.run_due(root3, NOW, fetch=t3, directory=src3, ctx=_ctx(root3, t3))
    assert t3.calls == []


def test_seven_days_of_failover_file_watch_broken_ci_once(tmp_path):
    root, src_dir = _setup(tmp_path)
    replies = _healthy(NOW, [])
    replies[WF] = {"state": "disabled_manually"}
    t = Transport(replies)
    ctx = _ctx(root, t)
    now = NOW
    while now <= NOW + 9 * DAY:
        uw.run_due(root, now, fetch=t, directory=src_dir, ctx=ctx)
        broken = [f for f in uw.pending(root) if f["kind"] == "watchbroken"]
        if now < NOW + 7 * DAY:
            assert broken == []
        now += 3 * HOUR
    broken = [f for f in uw.pending(root) if f["kind"] == "watchbroken"]
    assert len(broken) == 1
    assert broken[0]["tokens"] == {"NAME": "CI", "CAUSE": "workflow"}
    assert broken[0]["key"].startswith("broken:ci:")
    row_id, text = _render(broken[0])
    assert row_id == "WATCH-BROKEN-CI-20261120" and ROW_RX.match(text)
    assert ISSUES not in t.calls
    assert all(c in (WF, RUNS) for c in t.calls)
