"""WATCH-CORE (AUTO-05, F-030; decision 0069): the upstream watcher frame in
tools/upstream_watch.py. Hermetic: sources are files in a tmp folder whose
check delegates to a callable in ctx, the transport is a fake callable and
every state file lives under tmp_path. No socket is ever opened."""

import json
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import upstream_watch as uw  # noqa: E402

from server.al import NAME, webfetch  # noqa: E402

NOW = 1_800_000_000.0  # a fixed clock
HOUR = 3600.0
META = "https://api.github.com/repos/someone/some-tool/releases/latest"


class FakeTransport:
    def __init__(self, replies=None):
        self.calls = []
        self.replies = list(replies or [])

    def __call__(self, method, url, headers, body=None):
        self.calls.append((method, url, dict(headers)))
        if self.replies:
            return self.replies.pop(0)
        return 200, {}, b"{}"


def _root(tmp_path, web_data=True):
    root = tmp_path / "root"
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "local.json").write_text(
        json.dumps({"web_data": web_data}), encoding="utf-8")
    return root


def _src(folder, stem, name, **fields):
    """Write tools/watch_sources-style module <stem>.py whose check calls
    ctx['impl'][name] (or returns [] when ctx has none for it)."""
    folder.mkdir(parents=True, exist_ok=True)
    extra = "".join(f"    {k!r}: {v!r},\n" for k, v in fields.items())
    (folder / f"{stem}.py").write_text(textwrap.dedent("""\
        def check(state, now, fetch, ctx):
            ctx.setdefault("ran", []).append({name!r})
            impl = ctx.get("impl", {{}}).get({name!r})
            return impl(state, now, fetch, ctx) if impl else []


        SOURCE = {{
            "name": {name!r},
            "check": check,
        """).format(name=name) + extra + "}\n", encoding="utf-8")


def _net(folder, stem, name, **fields):
    fields.setdefault("hosts", ["api.github.com"])
    fields.setdefault("cadence_s", 24 * HOUR)
    _src(folder, stem, name, **fields)


def _state(root):
    return uw.load_state(root)["sources"]


def test_registry_discovers_sources_in_name_order(tmp_path):
    d = tmp_path / "sources"
    _src(d, "b_second", "omega")
    _src(d, "a_first", "zeta", home="both")
    _src(d, "_private", "hidden")
    _src(d, "c_dup", "omega")                       # a name used twice
    _src(d, "d_badhome", "badhome", home="phone")   # a contract break
    (d / "e_broken.py").write_text("SOURCE = {\n", encoding="utf-8")
    (d / "f_nocheck.py").write_text("SOURCE = {'name': 'nocheck'}\n", encoding="utf-8")
    errors = []
    found = uw.discover(d, errors)
    assert [s["name"] for s in found] == ["zeta", "omega"]   # file-name order
    zeta = found[0]
    assert zeta["home"] == "both" and zeta["local"] is True
    assert zeta["needs_web_data"] is True and zeta["cadence_s"] == 0
    assert sorted(stem for stem, _why in errors) == ["c_dup", "d_badhome", "e_broken", "f_nocheck"]
    # the tick names each skipped file in one line and still runs the rest
    root = _root(tmp_path)
    ctx = {}
    lines = uw.run_due(root, NOW, fetch=FakeTransport(), directory=d, ctx=ctx)
    assert sum("skipped" in ln for ln in lines) == 4
    assert ctx["ran"] == ["zeta", "omega"]
    # the real folder holds only valid sources
    errs = []
    uw.discover(None, errs)
    assert errs == []


def test_one_due_network_source_per_tick_oldest_first(tmp_path):
    d = tmp_path / "sources"
    for stem, name in (("a", "net-a"), ("b", "net-b"), ("c", "net-c"), ("d", "net-d")):
        _net(d, stem, name)
    root = _root(tmp_path)
    st = {"sources": {
        "net-a": {"last_run": uw.loop_base.iso(NOW - 30 * HOUR)},
        "net-b": {"last_run": uw.loop_base.iso(NOW - 50 * HOUR)},
        "net-d": {"last_run": uw.loop_base.iso(NOW - 1 * HOUR)},   # not due
    }}
    uw.save_state(root, st)
    t = FakeTransport()
    order = []
    for i in range(4):
        ctx = {}
        uw.run_due(root, NOW + i, fetch=t, directory=d, ctx=ctx)
        assert len(ctx.get("ran", [])) <= 1
        order += ctx.get("ran", [])
    # never run first, then the oldest last_run; net-d is not due yet
    assert order == ["net-c", "net-b", "net-a"]

    # at most 2 requests per run, each through the gate with the AshLight UA
    def greedy(state, now, fetch, ctx):
        fetch(META)
        fetch(META, etag='"v1"')
        fetch(META)
        return []
    d2 = tmp_path / "s2"
    _net(d2, "a", "greedy")
    t2 = FakeTransport()
    lines = uw.run_due(root, NOW, fetch=t2, directory=d2, ctx={"impl": {"greedy": greedy}})
    assert len(t2.calls) == uw.MAX_REQUESTS
    assert all(c[2]["User-Agent"].startswith(NAME + "/") for c in t2.calls)
    assert all("Cookie" not in c[2] for c in t2.calls)
    assert t2.calls[1][2]["If-None-Match"] == '"v1"'
    rec = _state(root)["greedy"]
    assert rec["fails"] == 1 and rec["last_ok"] is None
    assert any("greedy: failed" in ln for ln in lines)


def test_local_sources_all_run_each_tick(tmp_path):
    d = tmp_path / "sources"
    _src(d, "a", "loc-a")
    _src(d, "b", "loc-b")
    _src(d, "c", "loc-hourly", cadence_s=HOUR)
    _net(d, "d", "net-x")
    _src(d, "e", "ci-only", home="ci")
    root = _root(tmp_path)
    t = FakeTransport()
    refused = []

    def tries(state, now, fetch, ctx):
        with pytest.raises(webfetch.UrlNotAllowed):
            fetch(META)
        refused.append(1)
        return []

    runs = []
    for i in range(3):
        ctx = {"impl": {"loc-a": tries}}
        uw.run_due(root, NOW + i * 60, fetch=t, directory=d, ctx=ctx)
        runs.append(sorted(ctx["ran"]))
    assert runs[0] == ["loc-a", "loc-b", "loc-hourly", "net-x"]
    assert runs[1] == ["loc-a", "loc-b"] == runs[2]   # hourly and the network one wait
    assert len(refused) == 3 and t.calls == []        # a local source makes no request
    uw.run_due(root, NOW + HOUR, fetch=t, directory=d, ctx=(ctx := {}))
    assert sorted(ctx["ran"]) == ["loc-a", "loc-b", "loc-hourly"]
    assert "ci-only" not in _state(root)              # home ci never runs on the loop


def test_web_data_off_means_zero_requests_and_idle_state(tmp_path):
    d = tmp_path / "sources"
    _net(d, "a", "gated")
    _net(d, "b", "settled", needs_web_data=False, cadence_s=0)
    _src(d, "c", "local")
    root = _root(tmp_path, web_data=False)
    t = FakeTransport()

    def reads(state, now, fetch, ctx):
        fetch(META)
        return [{"kind": "release", "key": "v1", "tokens": {}}]

    impl = {"gated": reads, "settled": reads}
    ctx = {"impl": impl}
    lines = uw.run_due(root, NOW, fetch=t, directory=d, ctx=ctx)
    assert t.calls == []                               # 0 requests on the transport
    assert "gated" not in ctx["ran"]                   # a gated source is not even called
    assert sorted(ctx["ran"]) == ["local", "settled"]
    recs = _state(root)
    assert recs["gated"]["idle"] == uw.IDLE_OFF == "idle: web data off"
    assert recs["settled"]["idle"] == uw.IDLE_OFF      # its fetch raised WebDataOff
    for name in ("gated", "settled"):
        assert recs[name]["fails"] == 0 and recs[name]["last_ok"] is None
    assert uw.pending(root) == []
    assert sum("idle: web data off" in ln for ln in lines) == 2
    # the idle line is printed once, not every tick
    again = uw.run_due(root, NOW + 60, fetch=t, directory=d, ctx={"impl": impl})
    assert not any("idle" in ln for ln in again) and t.calls == []
    # the setting is read at call time: on, the same sources read and queue
    _root(tmp_path, web_data=True)
    uw.run_due(root, NOW + 120, fetch=t, directory=d, ctx={"impl": impl})
    assert len(t.calls) == 2
    assert all(c[1] == META and c[2]["User-Agent"].startswith(NAME + "/") for c in t.calls)
    recs = _state(root)
    assert recs["gated"]["idle"] is None and recs["settled"]["idle"] is None
    assert recs["gated"]["last_ok"] and recs["settled"]["last_ok"]
    assert len(uw.pending(root)) == 2


def test_finding_is_queued_once_per_key_for_all_time(tmp_path):
    d = tmp_path / "sources"
    _src(d, "a", "loc")
    root = _root(tmp_path)
    keys = ["k1"]

    def finds(state, now, fetch, ctx):
        out = [{"kind": "bump", "key": k, "tokens": {"tag": k}} for k in keys]
        out.append({"kind": "Bad Kind", "key": "x", "tokens": {}})
        out.append({"kind": "bump", "key": "y", "tokens": {"tag": 3}})
        return out

    ctx = {"impl": {"loc": finds}}
    lines = uw.run_due(root, NOW, directory=d, ctx=ctx)
    got = uw.pending(root)
    assert [(f["source"], f["kind"], f["key"], f["tokens"]) for f in got] == [
        ("loc", "bump", "k1", {"tag": "k1"})]
    assert got[0]["found"] == uw.loop_base.iso(NOW)
    assert sum("finding dropped" in ln for ln in lines) == 2
    uw.run_due(root, NOW + 60, directory=d, ctx=ctx)
    assert len(uw.pending(root)) == 1                 # the same upstream state files nothing
    uw.set_pending(root, [])                          # filed and cleared by the commit path
    keys.append("k2")
    uw.run_due(root, NOW + 120, directory=d, ctx=ctx)
    assert [f["key"] for f in uw.pending(root)] == ["k2"]   # k1 never comes back
    assert _state(root)["loc"]["seen"] == ["k1", "k2"]
    # a source cannot spoof another source's name in a finding
    keys[:] = ["k3"]

    def spoof(state, now, fetch, ctx):
        return [{"source": "other", "kind": "bump", "key": "k3", "tokens": {}}]
    uw.run_due(root, NOW + 180, directory=d, ctx={"impl": {"loc": spoof}})
    assert uw.pending(root)[-1]["source"] == "loc"


def test_failed_source_counts_fails_and_keeps_last_ok(tmp_path):
    d = tmp_path / "sources"
    _net(d, "a", "net", cadence_s=0)
    root = _root(tmp_path)
    mode = {"v": "ok"}

    def flaky(state, now, fetch, ctx):
        state["data"] = {"version": mode["v"]}
        state["etag"] = "e-" + mode["v"]
        if mode["v"] == "net":
            raise webfetch.FetchError("connection reset")
        if mode["v"] == "shape":
            raise KeyError("tag_name")
        fetch(META)
        return []

    ctx = {"impl": {"net": flaky}}
    t = FakeTransport()
    uw.run_due(root, NOW, fetch=t, directory=d, ctx=ctx)
    rec = _state(root)["net"]
    assert rec["fails"] == 0 and rec["last_ok"] == uw.loop_base.iso(NOW)
    assert rec["data"] == {"version": "ok"} and rec["etag"] == "e-ok"
    mode["v"] = "net"
    lines = uw.run_due(root, NOW + 60, fetch=t, directory=d, ctx=ctx)
    rec = _state(root)["net"]
    assert rec["fails"] == 1 and rec["cause"] == "network"
    assert rec["last_ok"] == uw.loop_base.iso(NOW)            # kept
    assert rec["last_run"] == uw.loop_base.iso(NOW + 60)
    assert rec["data"] == {"version": "ok"} and rec["etag"] == "e-ok"   # a failed run keeps both
    assert any("failed (network, 1 in a row)" in ln for ln in lines)
    mode["v"] = "shape"
    uw.run_due(root, NOW + 120, fetch=t, directory=d, ctx=ctx)
    rec = _state(root)["net"]
    assert rec["fails"] == 2 and rec["cause"] == "shape"
    mode["v"] = "ok"
    t429 = FakeTransport([(429, {"Retry-After": "120"}, b"")])
    uw.run_due(root, NOW + 180, fetch=t429, directory=d, ctx=ctx)
    rec = _state(root)["net"]
    assert rec["fails"] == 3 and rec["cause"] == "rate-limit"
    assert rec["last_ok"] == uw.loop_base.iso(NOW)
    uw.run_due(root, NOW + 240, fetch=t, directory=d, ctx=ctx)
    rec = _state(root)["net"]
    assert rec["fails"] == 0 and rec["cause"] is None
    assert rec["last_ok"] == uw.loop_base.iso(NOW + 240)


def test_halted_run_reads_and_queues(tmp_path):
    d = tmp_path / "sources"
    _net(d, "a", "net")
    _src(d, "b", "loc")
    root = _root(tmp_path)
    t = FakeTransport()

    def reads(state, now, fetch, ctx):
        fetch(META)
        return [{"kind": "release", "key": "v2", "tokens": {"tag": "v2"}}]

    seen_ctx = []

    def local(state, now, fetch, ctx):
        seen_ctx.append(ctx)
        return [{"kind": "note", "key": "n1", "tokens": {}}]

    ctx = {"impl": {"net": reads, "loc": local}, "live": False}
    lines = uw.run_due(root, NOW, halted=True, fetch=t, directory=d, ctx=ctx)
    assert len(t.calls) == 1                                  # it still reads
    assert sorted(f["key"] for f in uw.pending(root)) == ["n1", "v2"]   # and queues
    assert any("HALT" in ln and "nothing filed" in ln for ln in lines)
    assert seen_ctx == [ctx] and seen_ctx[0] is ctx           # ctx goes over unchanged
    assert not (root / "docs").exists()                        # nothing filed by the frame
    # the CLI run reads under HALT too
    (root / uw.HALT_REL).parent.mkdir(parents=True, exist_ok=True)
    (root / uw.HALT_REL).write_text("", encoding="utf-8")
    out = []

    class W:
        def write(self, s):
            out.append(s)
    _src(d, "c", "loc2")
    rc = uw.main(["run"], root=root, out=W(), fetch=t, directory=d)
    assert rc == 0 and out and _state(root)["loc2"]["last_ok"]
    out.clear()
    assert uw.main(["status"], root=root, out=W(), directory=d) == 0
    text = "".join(out)
    assert "pending findings: 2" in text and "net (loop, network): ok" in text


def test_request_dive_writes_the_request_file(tmp_path):
    root = _root(tmp_path)
    urls = ["https://api.github.com/repos/someone/some-tool/releases/latest"]
    doc = uw.request_dive(root, "repoe-fork 1.0 schema", urls, now=NOW)
    path = root / "ops" / "runtime" / "watch" / "dive_request.json"
    assert json.loads(path.read_text(encoding="utf-8")) == doc
    assert doc == {"topic": "repoe-fork 1.0 schema", "urls": urls, "at": uw.loop_base.iso(NOW)}
    assert path.read_bytes().isascii() and b"\r" not in path.read_bytes()
    path.unlink()
    for bad in (["https://www.pathofexile.com/forum/view-forum/patch-notes"],
                ["https://poe2db.tw/us/"], ["http://example.com/"]):
        with pytest.raises(webfetch.UrlNotAllowed):
            uw.request_dive(root, "t", bad, now=NOW)
        assert not path.exists()
    with pytest.raises(ValueError):
        uw.request_dive(root, " ", urls, now=NOW)
    with pytest.raises(ValueError):
        uw.request_dive(root, "t", [], now=NOW)


def test_dated_window_shortens_the_cadence(tmp_path):
    d = tmp_path / "sources"
    day = uw._dt.datetime.fromtimestamp(NOW).date()
    _net(d, "a", "net", cadence_s=24 * HOUR,
         window={"from": day.isoformat(), "to": day.isoformat(), "cadence_s": HOUR})
    src = uw.discover(d)[0]
    assert uw.cadence_at(src, NOW) == HOUR
    assert uw.cadence_at(src, NOW + 3 * 24 * HOUR) == 24 * HOUR
    with pytest.raises(uw.SourceInvalid):
        uw.normalize({"name": "x", "check": len, "window": {"from": "2026-12-05", "to": "2026-12-01",
                                                             "cadence_s": 1}})


def test_state_files_survive_damage_and_stay_under_runtime(tmp_path):
    root = _root(tmp_path)
    for rel in (uw.STATE_REL, uw.PENDING_REL, uw.DIVE_REL):
        assert rel.parts[:3] == ("ops", "runtime", "watch")   # never ops/loop/control
    (root / uw.STATE_REL).parent.mkdir(parents=True)
    (root / uw.STATE_REL).write_text("{not json", encoding="utf-8")
    (root / uw.PENDING_REL).write_text('{"findings": "x"}', encoding="utf-8")
    assert uw.load_state(root) == {"sources": {}}
    assert uw.pending(root) == []
    uw.save_state(root, {"sources": {"a": uw._entry()}})
    assert set(uw.load_state(root)["sources"]["a"]) == {
        "last_run", "last_ok", "fails", "etag", "seen", "idle", "cause", "data"}
    assert uw.web_data_on is uw.watch_gate.web_data_on
