"""AUTO-09 (ELECTRON-WATCH, F-130; W8 of docs/plan/06; decision 0070): the
'electron' and 'npm-audit' watcher sources. Every read is an injected
transport or runner over fixtures in tmp_path: no request, no npm."""

import datetime as _dt
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import upstream_watch as uw  # noqa: E402
import watch_file  # noqa: E402
import watch_rows  # noqa: E402
from watch_sources import electron, npm_audit  # noqa: E402

DAY = 24 * 3600
NOW = _dt.datetime(2026, 11, 20, 12, 0).timestamp()
TODAY = "2026-11-20"
PIN = "45.3.3"
NPMRC = ("ignore-scripts=true\n"
         "user-agent=AshLight/0.1.0 npm/{npm-version} node/{node-version}\n")


def _day(offset_days):
    return (_dt.date(2026, 11, 20) + _dt.timedelta(days=offset_days)).isoformat()


def _root(tmp_path, web_data=True, pin=PIN, eol="2027-04-27", npmrc=True, lock=True):
    root = tmp_path / "root"
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "app").mkdir(parents=True, exist_ok=True)
    (root / "config" / "local.json").write_text(
        json.dumps({"web_data": web_data}), encoding="ascii")
    (root / "app" / "package.json").write_text(
        json.dumps({"name": "ashlight-overlay", "devDependencies": {"electron": pin}}),
        encoding="ascii")
    if eol is not None:
        (root / "config" / "electron_pin.json").write_text(
            json.dumps({"schema": 1, "version": pin, "eol": eol}), encoding="ascii")
    if npmrc:
        (root / "app" / ".npmrc").write_text(NPMRC, encoding="ascii")
    if lock:
        (root / "app" / "package-lock.json").write_text(
            json.dumps({"lockfileVersion": 3, "packages": {}}), encoding="ascii")
    return root


def _tags(head="45.3.3", latest=None):
    tags = {"45-x-y": head, "latest": latest or head, "44-x-y": "44.9.1"}
    return tags


def _schedule(next_stable=None, pin_eol="2027-04-27"):
    rows = [{"version": "45.0.0", "stableDate": "2026-08-25", "endOfLife": pin_eol,
             "status": "stable"}]
    if next_stable:
        rows.append({"version": "46.0.0", "stableDate": next_stable,
                     "endOfLife": "2027-06-22", "status": "stable"})
    return rows


class Fetch:
    """The frame-style fetch(url, etag=None) -> (status, headers, body)."""

    def __init__(self, tags, schedule):
        self.docs = {electron.DIST_TAGS_URL: tags, electron.SCHEDULE_URL: schedule}
        self.calls = []

    def __call__(self, url, etag=None):
        self.calls.append(url)
        return 200, {}, json.dumps(self.docs[url]).encode("utf-8")


class Transport:
    """webfetch's transport fetch(method, url, headers, body) for the frame."""

    def __init__(self, tags, schedule):
        self.inner = Fetch(tags, schedule)
        self.calls = []

    def __call__(self, method, url, headers, body=None):
        self.calls.append((method, url, dict(headers)))
        status, hdrs, data = self.inner(url)
        return status, hdrs, data


class Runner:
    def __init__(self, report):
        self.report = report
        self.calls = []

    def __call__(self, argv, cwd):
        self.calls.append((list(argv), Path(cwd)))
        return 1, json.dumps(self.report)


def _sources(folder, stems):
    """A sources folder holding copies of the named real source files."""
    folder.mkdir(parents=True)
    for stem in stems:
        shutil.copyfile(ROOT / "tools" / "watch_sources" / f"{stem}.py", folder / f"{stem}.py")
    return folder


def _run(state, now, fetch, root):
    """One check with the frame's state threading (data kept after a good run)."""
    view = json.loads(json.dumps(state))
    found = electron.check(view, now, fetch, {"root": root})
    state["data"] = view.get("data", {})
    return found


def _render(finding):
    table = watch_rows.load(ROOT)
    return watch_rows.render(table, finding["kind"], finding["tokens"], TODAY)


AUDIT_ELECTRON = {
    "auditReportVersion": 2,
    "vulnerabilities": {
        "electron": {
            "name": "electron", "severity": "high", "isDirect": True,
            "via": [{"source": 1101234, "name": "electron", "dependency": "electron",
                     "title": "Heap overflow in a renderer", "severity": "high",
                     "url": "https://github.com/advisories/GHSA-xxxx-yyyy-zzzz",
                     "range": "<45.3.4"},
                    {"source": 1101300, "name": "electron", "dependency": "electron",
                     "title": "Use after free", "severity": "critical",
                     "url": "https://github.com/advisories/GHSA-aaaa-bbbb-cccc",
                     "range": "<45.3.4"}],
            "effects": [], "range": "<45.3.4", "nodes": ["node_modules/electron"],
            "fixAvailable": True},
        "@electron/get": {
            "name": "@electron/get", "severity": "moderate", "isDirect": False,
            "via": ["got"], "effects": ["electron"], "range": "*",
            "nodes": ["node_modules/@electron/get"], "fixAvailable": True},
    },
    "metadata": {"vulnerabilities": {"high": 1, "critical": 1, "total": 2}},
}


# ------------------------------------------------------------------ bump

def test_line_head_4_days_old_yields_one_bump_and_2_days_none(tmp_path):
    root = _root(tmp_path)
    fetch = Fetch(_tags(head="45.3.4"), _schedule())
    state = {}
    assert _run(state, NOW, fetch, root) == []  # first seen now
    assert len(fetch.calls) == 2  # the two public JSON files, nothing else
    assert state["data"]["heads"] == {"45.3.4": NOW}
    assert _run(state, NOW + 2 * DAY, fetch, root) == []  # 2 days: too young
    found = _run(state, NOW + 4 * DAY, fetch, root)
    assert [(f["kind"], f["key"]) for f in found] == [("electronbump", "45.3.4")]
    assert found[0]["tokens"] == {"MAJ": "45", "MIN": "3", "PAT": "4",
                                  "version": "45.3.4", "pin": PIN}
    rid, text = _render(found[0])
    assert rid == "ELECTRON-45-3-4"
    assert text.startswith("- [ ] ELECTRON-45-3-4 (data) Electron 45.3.4 ")
    assert "BLOCKED" not in text and "(priority)" not in text
    assert text.endswith(f"SOURCE: watch electron 45.3.4, filed {TODAY}.")
    # once only, and nothing for a head on the pin or on another line
    assert _run(state, NOW + 5 * DAY, fetch, root) == []
    quiet = Fetch(_tags(head=PIN, latest="46.0.1"), _schedule())
    assert _run({}, NOW, quiet, root) == [] and _run({}, NOW + 9 * DAY, quiet, root) == []
    # the frame: HALT reads and records, queues once, files nothing
    transport = Transport(_tags(head="45.3.4"), _schedule())
    d = _sources(tmp_path / "only", ('electron',))
    srcs = uw.discover(d)
    assert [s["name"] for s in srcs] == ["electron"] and uw.is_network(srcs[0])
    ctx = {"root": root}
    uw.run_due(root, NOW, halted=True, fetch=transport, directory=d, ctx=ctx)
    lines = uw.run_due(root, NOW + 4 * DAY, halted=True, fetch=transport, directory=d,
                       ctx=ctx)
    assert any("HALT: 1 finding(s) queued, nothing filed" in ln for ln in lines)
    assert [(f["source"], f["kind"], f["key"]) for f in uw.pending(root)] == [
        ("electron", "electronbump", "45.3.4")]
    assert len(transport.calls) == 4
    for _method, _url, headers in transport.calls:
        assert "electron watch" in headers["User-Agent"]
        assert "Cookie" not in headers
    git_calls = []
    out = watch_file.file_pending(root, NOW + 4 * DAY, lambda *a, **k: git_calls.append(a),
                                  None, halted=True)
    assert git_calls == [] and not (root / "docs" / "roadmap").exists()
    assert len(uw.pending(root)) == 1, out


def test_second_bump_inside_7_days_waits(tmp_path):
    root = _root(tmp_path)
    state = {}
    _run(state, NOW, Fetch(_tags(head="45.3.4"), _schedule()), root)
    first = _run(state, NOW + 3 * DAY, Fetch(_tags(head="45.3.4"), _schedule()), root)
    assert [f["key"] for f in first] == ["45.3.4"]
    fetch = Fetch(_tags(head="45.3.5"), _schedule())
    assert _run(state, NOW + 4 * DAY, fetch, root) == []  # seen
    assert _run(state, NOW + 7 * DAY, fetch, root) == []  # 3 days old, but 4 days since
    assert _run(state, NOW + 9 * DAY, fetch, root) == []  # 6 days since the bump
    second = _run(state, NOW + 10 * DAY, fetch, root)  # 7 days since the bump
    assert [f["key"] for f in second] == ["45.3.5"]
    assert second[0]["tokens"]["pin"] == PIN
    assert _render(second[0])[0] == "ELECTRON-45-3-5"


# ------------------------------------------------------------------ npm audit

def test_audit_fixture_naming_electron_is_a_priority_row(tmp_path):
    root = _root(tmp_path)
    runner = Runner(AUDIT_ELECTRON)

    def fetch(url, etag=None):
        raise AssertionError(f"npm-audit never uses the frame fetch: {url}")

    found = npm_audit.check({}, NOW, fetch, {"root": root, "npm_audit": runner})
    assert runner.calls == [(["audit", "--package-lock-only", "--json", "--prefix", "app"],
                             root)]
    # electron carries its own advisories; @electron/get is only a chain
    assert [(f["kind"], f["tokens"]) for f in found] == [
        ("npmaudit", {"PKG": "ELECTRON", "package": "electron", "severity": "critical"})]
    assert found[0]["key"] == "electron:1101234,1101300"
    rid, text = _render(found[0])
    assert rid == f"NPM-AUDIT-ELECTRON-{TODAY.replace('-', '')}"
    assert text.startswith(f"- [ ] {rid} (data) (priority) npm audit reports a critical ")
    assert "BLOCKED" not in text
    table = watch_rows.load(ROOT)
    assert table["npmaudit"]["priority"] is True and table["npmaudit"]["lane"] == "data"
    # through the frame at once (one tick), queued as a finding
    d = _sources(tmp_path / "only", ('npm_audit',))
    lines = uw.run_due(root, NOW, directory=d, ctx={"root": root, "npm_audit": runner})
    assert any("1 new finding(s) queued" in ln for ln in lines)
    assert [f["kind"] for f in uw.pending(root)] == ["npmaudit"]
    # a scoped package name maps to a valid id and word
    assert npm_audit.pkg_id("@electron/get") == "ELECTRON-GET"
    assert npm_audit.pkg_word("@electron/get") == "electron.get"
    # no AshLight user-agent in app/.npmrc (F-037) or no lockfile: idle, npm not run
    for kw in ({"npmrc": False}, {"lock": False}):
        idle_root = _root(tmp_path / "idle" / next(iter(kw)), **kw)
        idle = Runner(AUDIT_ELECTRON)
        assert npm_audit.check({}, NOW, fetch, {"root": idle_root, "npm_audit": idle}) == []
        assert idle.calls == []
    # a clean audit makes no finding
    clean = Runner({"auditReportVersion": 2, "vulnerabilities": {}, "metadata": {}})
    assert npm_audit.check({}, NOW, fetch, {"root": root, "npm_audit": clean}) == []


# ------------------------------------------------------------------ major

def test_next_major_15_days_old_yields_the_major_row_once(tmp_path):
    root = _root(tmp_path)
    tags = _tags(head=PIN, latest="46.0.1")
    state = {}
    # 13 days old: not yet
    assert _run(state, NOW, Fetch(tags, _schedule(next_stable=_day(-13))), root) == []
    # a tentative date with no 46 release in the registry: not yet
    assert _run(state, NOW, Fetch(_tags(head=PIN), _schedule(next_stable=_day(-15))),
                root) == []
    found = _run(state, NOW, Fetch(tags, _schedule(next_stable=_day(-15))), root)
    assert [(f["kind"], f["key"]) for f in found] == [("electronmajor", "major-46")]
    assert found[0]["tokens"] == {"MAJ": "46", "PINMAJ": "45", "eol": "2027-04-27"}
    rid, text = _render(found[0])
    assert rid == "ELECTRON-MAJOR-46"
    assert "(review)" in text and "BLOCKED: session." in text
    assert text.index("BLOCKED:") < text.index("SOURCE:")
    # once per major through the frame: the key is queued for all time
    d = _sources(tmp_path / "only", ('electron',))
    transport = Transport(tags, _schedule(next_stable=_day(-15)))
    for i in range(3):
        uw.run_due(root, NOW + i * DAY, fetch=transport, directory=d, ctx={"root": root})
    majors = [f for f in uw.pending(root) if f["kind"] == "electronmajor"]
    assert [f["key"] for f in majors] == ["major-46"]
    # one major at a time: a pin on 45 with 47 out still asks for 46 only
    far = _run({}, NOW, Fetch(_tags(head=PIN, latest="47.0.2"),
                              _schedule(next_stable=_day(-60))), root)
    assert [f["key"] for f in far] == ["major-46"]


def test_inside_30_days_of_eol_yields_the_major_row_once(tmp_path):
    eol = _day(29)
    root = _root(tmp_path, eol=eol)
    tags = _tags(head=PIN)
    found = _run({}, NOW, Fetch(tags, _schedule(pin_eol=eol)), root)
    assert [(f["kind"], f["key"]) for f in found] == [("electronmajor", "major-46")]
    assert found[0]["tokens"] == {"MAJ": "46", "PINMAJ": "45", "eol": eol}
    assert _render(found[0])[0] == "ELECTRON-MAJOR-46"
    # 31 days out: idle; no config/electron_pin.json: the end-of-life rule is idle
    far = _root(tmp_path / "far", eol=_day(31))
    assert _run({}, NOW, Fetch(tags, _schedule()), far) == []
    none = _root(tmp_path / "none", eol=None)
    assert _run({}, NOW, Fetch(tags, _schedule(pin_eol=_day(5))), none) == []
    # once through the frame
    d = _sources(tmp_path / "only", ('electron',))
    transport = Transport(tags, _schedule(pin_eol=eol))
    for i in range(3):
        uw.run_due(root, NOW + i * DAY, fetch=transport, directory=d, ctx={"root": root})
    assert [f["key"] for f in uw.pending(root)] == ["major-46"]


# ------------------------------------------------------------------ web data off

def test_web_data_off_makes_zero_requests_and_starts_no_npm(tmp_path):
    root = _root(tmp_path, web_data=False)
    transport = Transport(_tags(head="45.3.4"), _schedule(next_stable=_day(-20)))
    runner = Runner(AUDIT_ELECTRON)
    ctx = {"root": root, "npm_audit": runner}
    d = _sources(tmp_path / "both", ('electron', 'npm_audit'))
    for i in range(5):
        lines = uw.run_due(root, NOW + i * DAY, fetch=transport, directory=d, ctx=ctx)
        if i == 0:
            assert sum(uw.IDLE_OFF in ln for ln in lines) == 2
    assert transport.calls == [] and runner.calls == []
    assert uw.pending(root) == []
    recs = uw.load_state(root)["sources"]
    assert recs["electron"]["idle"] == uw.IDLE_OFF
    assert recs["npm-audit"]["idle"] == uw.IDLE_OFF
    # a direct call while off starts no npm either
    with pytest.raises(uw.webfetch.WebDataOff):
        npm_audit.check({}, NOW, None, ctx)
    assert runner.calls == []
    # the registry: both are gated network sources with exact listed URLs
    srcs = {s["name"]: s for s in uw.discover(d)}
    for name in ("electron", "npm-audit"):
        assert srcs[name]["needs_web_data"] is True and uw.is_network(srcs[name])
        assert srcs[name]["cadence_s"] == DAY
    for url in electron.SOURCE["urls"]:
        uw.watch_gate.check_url(electron.SOURCE, url)
    assert electron.SOURCE["urls"] == [
        "https://registry.npmjs.org/-/package/electron/dist-tags",
        "https://releases.electronjs.org/schedule.json"]
    # no tree, not live: nothing is read, no runner, no request

    def boom(*a, **k):
        raise AssertionError("no read without a tree")

    assert electron.check({}, NOW, boom, {}) == []
    assert npm_audit.check({}, NOW, boom, {}) == []
    # web data on but not live and no injected runner: the subprocess never starts
    on = _root(tmp_path / "on")
    assert npm_audit.check({}, NOW, boom, {"root": on}) == []
