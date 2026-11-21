"""AUTO-19 (CI-WATCH, decision 0076): tools/watch_ci.py and
.github/workflows/watch.yml. Every network behaviour runs on an injected
transport; no test makes a real request."""

import io
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import watch_ci  # noqa: E402
import watch_gate  # noqa: E402
from server.al import VERSION  # noqa: E402

WORKFLOW = ROOT / ".github" / "workflows" / "watch.yml"
CI = ROOT / ".github" / "workflows" / "ci.yml"
PIN = json.loads((ROOT / "config" / "tc_pins.json").read_text(encoding="ascii"))["pob2"]
REPO = "owner/proj"
API = "https://api.github.com/repos/" + REPO
LATEST = f"https://api.github.com/repos/{PIN['repo']}/releases/latest"
NOW = 1795300000.0


def env(**over):
    e = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": REPO,
         "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
         "GITHUB_TOKEN": "t0ken"}
    e.update(over)
    return e


def issue(number, key=None, login=watch_ci.BOT_LOGIN, body=None):
    return {"number": number, "user": {"login": login},
            "body": body if body is not None else watch_ci.body_for(key)}


class FakeGitHub:
    """A transport: fixed GET answers by URL plus a stateful issue list."""

    def __init__(self, routes=None, issues=None, label=True):
        self.routes = dict(routes or {})
        self.issues = list(issues or [])
        self.label = label
        self.calls = []

    def __call__(self, method, url, headers, body=None):
        self.calls.append((method, url, dict(headers), body))
        if url in self.routes:
            status, doc = self.routes[url]
            return status, {}, json.dumps(doc).encode("utf-8")
        if url == API + "/labels/" + watch_ci.LABEL and method == "GET":
            return (200 if self.label else 404), {}, b"{}"
        if url == API + "/labels" and method == "POST":
            self.label = True
            return 201, {}, b"{}"
        if url.startswith(API + "/issues?") and method == "GET":
            open_ = [i for i in self.issues if i.get("state", "open") == "open"]
            return 200, {}, json.dumps(open_).encode("utf-8")
        if url == API + "/issues" and method == "POST":
            doc = json.loads(body.decode("utf-8"))
            n = 1000 + len(self.issues)
            self.issues.append({"number": n, "user": {"login": watch_ci.BOT_LOGIN},
                                "body": doc["body"], "labels": doc["labels"],
                                "title": doc["title"], "state": "open"})
            return 201, {}, json.dumps({"number": n}).encode("utf-8")
        m = re.fullmatch(re.escape(API) + r"/issues/(\d+)", url)
        if m and method == "PATCH":
            for i in self.issues:
                if i["number"] == int(m.group(1)):
                    i["state"] = json.loads(body.decode("utf-8"))["state"]
            return 200, {}, b"{}"
        raise AssertionError(f"unexpected request {method} {url}")

    def posted(self):
        return [json.loads(b.decode("utf-8")) for (m, u, _h, b) in self.calls
                if m == "POST" and u == API + "/issues"]

    def closed(self):
        return [int(u.rsplit("/", 1)[1]) for (m, u, _h, _b) in self.calls if m == "PATCH"]


def run(fake, *args, environ=None):
    out = io.StringIO()
    code = watch_ci.main(list(args), environ=environ or env(), transport=fake, out=out, now=NOW)
    return code, out.getvalue()


def test_issue_body_is_exactly_the_key_line():
    fake = FakeGitHub({LATEST: (200, {"tag_name": "v99.0.0"})}, label=False)
    code, text = run(fake, "--sources", "pob-release")
    assert code == 0, text
    posted = fake.posted()
    assert len(posted) == 1
    assert posted[0]["body"] == "AL-WATCH key=pob-release:v99.0.0 v=1"
    assert "\n" not in posted[0]["body"]
    assert posted[0]["labels"] == ["al-watch"]
    assert fake.label  # the label was made once
    # A second run with the issue open opens nothing new.
    fake.calls.clear()
    code, _ = run(fake, "--sources", "pob-release")
    assert code == 0 and fake.posted() == [] and fake.closed() == []
    # The tick-side reading: only the exact line from the bot account is a key.
    assert watch_ci.key_of(issue(1, "pob-release:v99.0.0")) == "pob-release:v99.0.0"
    for bad in ("AL-WATCH key=pob-release:v99.0.0 v=1\nmore",
                "AL-WATCH key=pob-release:v99.0.0 v=1 ",
                " AL-WATCH key=pob-release:v99.0.0 v=1",
                "AL-WATCH key=pob-release:v99 0 v=1",
                "AL-WATCH key=Pob:v1 v=1",
                "AL-WATCH key=pob-release:v99.0.0 v=2"):
        assert watch_ci.key_of(issue(2, body=bad)) is None, bad
    assert watch_ci.key_of(issue(3, "pob-release:v99.0.0", login="someone")) is None
    assert watch_ci.make_key("npm-audit", "has space:1") is None
    assert watch_ci.make_key("npm-audit", "x" * 201) is None


def test_gone_finding_closes_its_issue():
    pin = PIN["tag"]
    issues = [issue(5, "pob-release:v98.0.0"),
              issue(6, "pob-release:v97.0.0", login="someone"),     # forged
              issue(7, body="AL-WATCH key=pob-release:v96.0.0 v=1 extra"),
              issue(8, "electron:99.1.2"),                          # not run now
              issue(9, "pob-release:v98.0.0")]                      # duplicate
    fake = FakeGitHub({LATEST: (500, {})}, issues=issues)
    code, text = run(fake, "--sources", "pob-release")
    # A failed read is not "gone": its issues stay; only the duplicate goes.
    assert code == 1 and "::warning::" in text
    assert fake.closed() == [9]
    fake.calls.clear()
    fake.routes[LATEST] = (200, {"tag_name": pin})
    code, text = run(fake, "--sources", "pob-release")
    assert code == 0, text
    assert fake.closed() == [5]
    assert fake.posted() == []
    state = {i["number"]: i.get("state", "open") for i in fake.issues}
    assert state == {5: "closed", 6: "open", 7: "open", 8: "open", 9: "closed"}


def test_workflow_holds_no_ggg_host_and_no_poe_ninja_host():
    text = WORKFLOW.read_text(encoding="ascii").lower()
    for host in watch_gate.GGG_DOMAINS + ("poe.ninja", "poe2db", "pathofexile"):
        assert host not in text, host
    src = (TOOLS / "watch_ci.py").read_text(encoding="ascii").lower()
    for host in watch_gate.GGG_DOMAINS + ("poe.ninja",):
        assert not re.search(r"://[a-z0-9.-]*" + re.escape(host), src), host
    # The fetch a source gets refuses those hosts before any request.
    fake = FakeGitHub()
    srcmap = {"name": "repoe-fork", "urls": []}
    fetch = watch_ci.source_fetch(srcmap, env(), fake)
    for url in ("https://www.pathofexile.com/developer/docs/data",
                "https://poe.ninja/api/data/economyleagues",
                "https://raw.githubusercontent.com/repoe-fork/poe2/master/data.json",
                "https://api.github.com/repos/repoe-fork/poe2/contents/x.json"):
        with pytest.raises(watch_gate.UrlNotAllowed):
            fetch(url)
    assert fake.calls == []
    # The scope sentence of decision 0076 stands on one line.
    dec = (ROOT / "docs" / "decisions" / "0076-ci-issue-protocol.md").read_text(encoding="ascii")
    assert sum("not a web_data path" in ln for ln in dec.splitlines()) == 1


def test_workflow_permissions_and_pinned_actions():
    raw = WORKFLOW.read_bytes()
    raw.decode("ascii")
    assert b"\r" not in raw
    text = raw.decode("ascii")
    m = re.search(r"(?m)^permissions:[ \t]*\n((?:[ \t]+.*\n?)*)", text)
    body = sorted(ln.strip() for ln in m.group(1).split("\n") if ln.strip())
    assert body == ["contents: read", "issues: write"]
    assert len(re.findall(r"(?m)^\s*permissions:", text)) == 1
    ci_pins = dict(re.findall(r"uses:\s*([\w.-]+/[\w./-]+@[0-9a-f]{40}) # (v\S+)",
                              CI.read_text(encoding="ascii")))
    uses = [ln.split("uses:", 1)[1].strip() for ln in text.split("\n")
            if re.match(r"^\s*(?:-\s+)?uses:", ln)]
    assert uses
    for ref in uses:
        assert re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40} # v\d+(?:\.\d+)*", ref), ref
        action, tag = ref.split(" # ")
        assert ci_pins.get(action) == tag, ref  # same pin as ci.yml
    assert "persist-credentials: false" in text
    assert "secrets." not in text
    assert re.search(r"(?m)^  workflow_dispatch:\s*$", text)
    cron = re.search(r'cron:\s*"(\d+) (\d+) \* \* \*"', text)
    assert cron and cron.group(1) != "0"  # once a day, off the hour
    assert re.search(r"(?m)^\s*runs-on:\s*(windows|ubuntu)-[0-9a-z.]+\s*$", text)
    runs = re.findall(r"(?m)^\s*(?:-\s+)?run:\s*(.*)$", text)
    assert runs == ["python tools/watch_ci.py --sources "
                    "pob-release,repoe-fork,ggg-tree,electron,npm-audit"]
    for word in ("git commit", "git push", "pull_request", "pull-requests"):
        assert word not in text


def test_ci_user_agent_names_ashlight_version_and_issues_page():
    e = env(GITHUB_REPOSITORY="someone/thing")
    ua = watch_ci.user_agent(e, "electron")
    assert ua.startswith(f"AshLight/{VERSION} ")
    assert "ci watcher electron" in ua
    assert ua.endswith("(contact: https://github.com/someone/thing/issues)")
    api = "https://api.github.com/repos/someone/thing"
    fake = FakeGitHub({LATEST: (200, {"tag_name": PIN["tag"]}),
                       api + "/labels/al-watch": (200, {})})
    fake.routes[api + "/issues?labels=al-watch&state=open&per_page=100&page=1"] = (200, [])
    code, text = watch_ci.main(["--sources", "pob-release"], environ=e, transport=fake,
                               out=io.StringIO(), now=NOW), None
    assert code == 0
    assert fake.calls
    for _m, url, headers, _b in fake.calls:
        assert headers["User-Agent"].startswith(f"AshLight/{VERSION} "), url
        assert "(contact: https://github.com/someone/thing/issues)" in headers["User-Agent"]
        assert "Cookie" not in headers
    # The job token goes only to api.github.com, never to a registry host.
    src = {"name": "electron",
           "urls": ["https://registry.npmjs.org/-/package/electron/dist-tags"]}
    fake2 = FakeGitHub({src["urls"][0]: (200, {"latest": "1.0.0"})})
    watch_ci.source_fetch(src, e, fake2)(src["urls"][0])
    assert "Authorization" not in fake2.calls[0][2]
    with pytest.raises(watch_ci.Refused):
        watch_ci.user_agent(env(GITHUB_SERVER_URL="https://ghe.example"))


def test_ci_entry_refuses_to_run_off_a_github_runner():
    for e in ({}, env(GITHUB_ACTIONS="false"), env(GITHUB_ACTIONS="1"),
              {k: v for k, v in env().items() if k != "GITHUB_ACTIONS"}):
        fake = FakeGitHub({LATEST: (200, {"tag_name": "v99.0.0"})})
        out = io.StringIO()
        assert watch_ci.main(["--sources", "pob-release"], environ=e, transport=fake,
                             out=out, now=NOW) == watch_ci.EXIT_REFUSED
        assert "runs only on a GitHub runner" in out.getvalue()
        assert fake.calls == []
    # On a runner: a source that never runs in CI, or an unknown name, is refused
    # before any request.
    for name in ("ggg-docs", "launch", "nope"):
        fake = FakeGitHub()
        code, text = run(fake, "--sources", name)
        assert code == watch_ci.EXIT_REFUSED and fake.calls == [], text


def test_versioned_source_finds_a_version_off_the_baseline():
    url = "https://api.github.com/repos/repoe-fork/poe2/commits"
    base = watch_ci.BASELINE["repoe-fork"]["live_version"]

    def commits(title):
        return [{"sha": "a" * 40, "commit": {"message": title,
                                             "committer": {"date": "2026-11-20T00:00:00Z"}}}]
    fake = FakeGitHub({url: (200, commits(f"Export {base}"))})
    code, _ = run(fake, "--sources", "repoe-fork")
    assert code == 0 and fake.posted() == []
    fake.routes[url] = (200, commits("Export 9.9.9.9"))
    code, _ = run(fake, "--sources", "repoe-fork")
    assert code == 0
    assert [p["body"] for p in fake.posted()] == ["AL-WATCH key=repoe-fork:9.9.9.9 v=1"]


def test_electron_bump_age_counts_from_the_release_date():
    from watch_sources import electron as el
    pin = el.pin_of(ROOT)
    maj, mnr, pat = el.vtuple(pin)
    head = f"{maj}.{mnr}.{pat + 1}"
    tags = {"latest": head, f"{maj}-x-y": head}
    sched = [{"version": f"{maj}.0.0", "stableDate": "2026-01-01", "endOfLife": "2099-01-01"}]
    rel = f"https://api.github.com/repos/electron/electron/releases/tags/v{head}"
    routes = {el.DIST_TAGS_URL: (200, tags), el.SCHEDULE_URL: (200, sched)}
    fake = FakeGitHub(dict(routes, **{rel: (200, {"published_at": "2026-11-20T00:00:00Z"})}))
    out = io.StringIO()
    src = next(s for s in watch_ci.upstream_watch.discover() if s["name"] == "electron")
    ok, keys, _line = watch_ci.run_source(src, env(), fake, NOW, ROOT)
    assert ok and f"electron:{head}" not in keys  # 1 day old: not ripe
    fake = FakeGitHub(dict(routes, **{rel: (200, {"published_at": "2026-11-01T00:00:00Z"})}))
    ok, keys, _line = watch_ci.run_source(src, env(), fake, NOW, ROOT)
    assert ok and f"electron:{head}" in keys, out.getvalue()
