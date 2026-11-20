"""LOOP-WATCH-SETTLED (F-030, AUTO-05, CARRY-01): the GGG docs watch
(decision 0044) and the PoB-PoE2 release check (decision 0025) as registry
sources of tools/upstream_watch.py, plus tc_drift.loop_check(halted=...).

Hermetic: every root, cache and state file lives under tmp_path; the settled
reads are replaced by recording seams in ctx; the frame's transport is a
fake that records; tc_drift reads through an injected fake fetch and its
trial launch is a recorder. No socket is ever opened."""

import importlib
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import ggg_docs_watch  # noqa: E402
import tc_drift  # noqa: E402
import upstream_watch as uw  # noqa: E402
import watch_rows  # noqa: E402

ggg_docs = importlib.import_module("watch_sources.ggg_docs")
pob_release = importlib.import_module("watch_sources.pob_release")

NOW = 1_800_000_000.0
TODAY = "2026-11-20"
SETTLED = ("ggg-docs", "pob-release")


class Transport:
    """The frame's transport: records, and fails the test if ever used."""

    def __init__(self):
        self.calls = []

    def __call__(self, method, url, headers, body=None):
        self.calls.append((method, url))
        raise AssertionError(f"network request to {url}")


class Seam:
    """A recording stand-in for a settled read (docs_watch or drift)."""

    def __init__(self, line=None):
        self.calls = []
        self.line = line

    def __call__(self, root, now, halted=False):
        self.calls.append((Path(root), now, halted))
        return self.line


def _root(tmp_path, web_data=False, local=None):
    root = tmp_path / "root"
    (root / "config").mkdir(parents=True, exist_ok=True)
    cfg = {"web_data": web_data}
    cfg.update(local or {})
    (root / "config" / "local.json").write_text(json.dumps(cfg), encoding="utf-8")
    (root / "config" / "tc_pins.json").write_bytes(
        (ROOT / "config" / "tc_pins.json").read_bytes())
    return root


def _ctx(root, tmp_path, **over):
    ctx = {"root": root, "docs_watch": Seam(), "drift": Seam(),
           "docs_cache": tmp_path / "docs_cache"}
    ctx.update(over)
    return ctx


def _settled_only(sources):
    return [s for s in sources if s["name"] in SETTLED]


def _fake_release(latest="v99.0.0"):
    calls = []

    def fetch(method, url, hdrs, body=None):
        calls.append(url)
        if url.endswith("/releases/latest"):
            doc = {"tag_name": latest, "published_at": "2026-12-10T12:00:00Z",
                   "draft": False, "prerelease": False}
            return 200, {}, json.dumps(doc).encode("ascii")
        return 404, {}, b""
    fetch.calls = calls
    return fetch


def _drift_state(root, verdict="static-green", latest="v0.24.0", pinned="v0.23.1",
                 status="new", trial_tag=None):
    st = {"status": status, "latest": latest, "pinned": pinned, "checked": "x",
          "next_check": NOW + 10 * 86400}
    tr = {"tag": trial_tag or latest, "state": "done"}
    if verdict is not None:
        tr["verdict"] = verdict
    else:
        tr["state"] = "launched"
    st["trial"] = tr
    tc_drift.save_state(root, st)


def _table():
    return watch_rows.load(ROOT)


# --------------------------------------------------------------- registry

def test_settled_sources_read_with_web_data_off(tmp_path):
    sources = _settled_only(uw.discover())
    assert sorted(s["name"] for s in sources) == sorted(SETTLED)
    for src in sources:
        assert src["needs_web_data"] is False and not uw.is_network(src)
        assert src["hosts"] == [] and src["urls"] == [] and src["home"] == "loop"
    root = _root(tmp_path, web_data=False)
    ctx = _ctx(root, tmp_path)
    transport = Transport()
    lines = uw.run_due(root, NOW, fetch=transport, ctx=ctx)
    assert transport.calls == []
    assert ctx["docs_watch"].calls == [(root, NOW, False)]
    assert ctx["drift"].calls == [(root, NOW, False)]
    recs = uw.load_state(root)["sources"]
    for name in SETTLED:
        assert recs[name]["last_run"] and recs[name]["last_ok"], name
        assert recs[name]["idle"] is None and recs[name]["fails"] == 0, name
    assert not any(uw.IDLE_OFF in line and any(n in line for n in SETTLED)
                   for line in lines)
    # every tick, not throttled by the frame: each read keeps its own gate
    uw.run_due(root, NOW + 60, fetch=transport, ctx=ctx)
    assert len(ctx["docs_watch"].calls) == 2 and len(ctx["drift"].calls) == 2
    assert transport.calls == []


# --------------------------------------------------------------- HALT

def test_release_check_under_halt_never_runs_a_live_trial(tmp_path):
    root = _root(tmp_path, local={"tc_drift_live_unattended": True})
    assert tc_drift.live_opted_in(root) is True
    launched = []

    def launch(r, tag, live=False):
        launched.append((tag, live))
        return 4242

    fetch = _fake_release()
    line = tc_drift.loop_check(root, NOW, fetch=fetch, launch=launch, halted=True)
    assert launched == [("v99.0.0", False)]
    assert "v99.0.0" in line and fetch.calls  # the read and the record still happen
    assert tc_drift.load_state(root)["trial"]["state"] == "launched"

    # not HALTed: the host's opt-in still decides (unchanged behaviour)
    other = _root(tmp_path / "b", local={"tc_drift_live_unattended": True})
    tc_drift.loop_check(other, NOW, fetch=_fake_release(), launch=launch)
    assert launched[-1] == ("v99.0.0", True)

    # through the source: HALT file under the root, seam passes halted on
    third = _root(tmp_path / "c", local={"tc_drift_live_unattended": True})
    (third / pob_release.HALT_REL).parent.mkdir(parents=True)
    (third / pob_release.HALT_REL).write_text("halt\n", encoding="ascii")
    seen = []

    def drift(r, now, halted=False):
        seen.append(halted)
        return tc_drift.loop_check(r, now, fetch=_fake_release(), launch=launch,
                                   halted=halted)

    got = pob_release.check({}, NOW, None, {"root": third, "drift": drift})
    assert seen == [True] and got == []
    assert launched[-1] == ("v99.0.0", False)

    # a seam that cannot be told about HALT is not called while HALTed
    old = []
    assert pob_release.check({}, NOW, None,
                             {"root": third, "drift": lambda r, now: old.append(r)}) == []
    assert old == []


# --------------------------------------------------------------- ggg-docs

def test_reg_open_flag_yields_one_tc_oauth_reg_open_finding(tmp_path, monkeypatch):
    root = _root(tmp_path)
    flag = ggg_docs_watch.runtime_dir(root) / ggg_docs_watch.FLAG_NAME
    flag.parent.mkdir(parents=True)
    flag.write_text("open\n", encoding="ascii")
    ctx = _ctx(root, tmp_path)

    # A-01 constant off (the default): the flag is not read, no finding
    assert ggg_docs_watch.SHAPE_ALL_PAGES is False
    assert ggg_docs.check({}, NOW, None, ctx) == []
    uw.run_due(root, NOW, fetch=Transport(), ctx=ctx)
    assert [f for f in uw.pending(root) if f["source"] == "ggg-docs"] == []

    monkeypatch.setattr(ggg_docs_watch, "SHAPE_ALL_PAGES", True)
    uw.run_due(root, NOW + 60, fetch=Transport(), ctx=ctx)
    uw.run_due(root, NOW + 120, fetch=Transport(), ctx=ctx)  # queued once only
    found = [f for f in uw.pending(root) if f["source"] == "ggg-docs"]
    assert [(f["kind"], f["key"], f["tokens"]) for f in found] == [
        ("regopen", "TC-OAUTH-REG-OPEN", {})]
    row_id, text = watch_rows.render(_table(), "regopen", {}, TODAY)
    assert row_id == "TC-OAUTH-REG-OPEN"
    assert "BLOCKED: operator act" in text and "SOURCE: watch ggg-docs reg-open" in text

    flag.unlink()  # no flag, no finding
    assert ggg_docs.check({}, NOW, None, ctx) == []


def test_shape_topic_hit_yields_a_ggg_shape_finding(tmp_path):
    root = _root(tmp_path)
    cache = tmp_path / "docs_cache"
    ggg_docs_watch.save_state(cache, {"last_shape": {
        "at": "2026-11-20T10:00:00Z",
        "pages": [{"page": "data", "fields": ["id", "name"], "count": 2},
                  {"page": "reference", "fields": ["a", "b", "c"], "count": 3},
                  {"page": "index", "fields": ["x"] * 9, "count": 9}]}})
    ctx = _ctx(root, tmp_path, docs_cache=cache)
    uw.run_due(root, NOW, fetch=Transport(), ctx=ctx)
    uw.run_due(root, NOW + 60, fetch=Transport(), ctx=ctx)
    found = [f for f in uw.pending(root) if f["source"] == "ggg-docs"]
    assert len(found) == 1
    f = found[0]
    assert f["kind"] == "gggshape"
    assert f["tokens"] == {"page": "reference", "n": "3"}
    row_id, text = watch_rows.render(_table(), f["kind"], f["tokens"], TODAY)
    assert row_id == "GGG-SHAPE-20261120"
    assert "page reference changed near 3 field names" in text
    assert "BLOCKED: session" in text

    # data only, a count over 99 is capped; no shape record, no finding
    assert ggg_docs.shape_findings({"last_shape": {"at": "t2", "pages": [
        {"page": "data", "count": 150}]}})[0]["tokens"] == {"page": "data", "n": "99"}
    assert ggg_docs.shape_findings({}) == []
    assert ggg_docs.shape_findings({"last_shape": {"at": "t3", "pages": [
        {"page": "changelog", "count": 4}, {"page": "data", "count": 0}]}}) == []


# --------------------------------------------------------------- pob-release

def test_static_verdict_yields_the_pob_release_finding(tmp_path):
    root = _root(tmp_path)
    ctx = _ctx(root, tmp_path)
    _drift_state(root, verdict=None)  # trial launched, verdict not known yet
    assert pob_release.check({}, NOW, None, ctx) == []

    _drift_state(root, verdict="static-green")
    uw.run_due(root, NOW, fetch=Transport(), ctx=ctx)
    uw.run_due(root, NOW + 60, fetch=Transport(), ctx=ctx)
    found = [f for f in uw.pending(root) if f["source"] == "pob-release"]
    assert [(f["kind"], f["key"]) for f in found] == [("pobrelease", "v0.24.0")]
    tokens = found[0]["tokens"]
    assert tokens == {"VTAG": "V0-24-0", "tag": "v0.24.0", "pin": "v0.23.1",
                      "verdict": "green"}
    row_id, text = watch_rows.render(_table(), "pobrelease", tokens, TODAY)
    assert row_id == "POB-V0-24-0"
    assert "static trial green" in text and "BLOCKED: session" in text

    _drift_state(root, verdict="static-red")
    assert pob_release.check({}, NOW, None, ctx)[0]["tokens"]["verdict"] == "red"
    for verdict in ("untested", "error", "red"):
        _drift_state(root, verdict=verdict)
        assert pob_release.check({}, NOW, None, ctx) == [], verdict
    _drift_state(root, verdict="static-green", trial_tag="v0.23.9")  # older trial
    assert pob_release.check({}, NOW, None, ctx) == []
    _drift_state(root, verdict="static-green", status="current")
    assert pob_release.check({}, NOW, None, ctx) == []

    # HALT present: the read runs, no finding; it comes once HALT is gone
    _drift_state(root, verdict="static-green", latest="v0.25.0")
    halt = root / pob_release.HALT_REL
    halt.parent.mkdir(parents=True, exist_ok=True)
    halt.write_text("halt\n", encoding="ascii")
    ctx["drift"] = Seam()
    assert pob_release.check({}, NOW, None, ctx) == []
    assert ctx["drift"].calls == [(root, NOW, True)]
    halt.unlink()
    assert pob_release.check({}, NOW, None, ctx)[0]["key"] == "v0.25.0"


# --------------------------------------------------------------- seams

def test_sources_use_the_ctx_seams_not_the_network(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a settled read ran outside its seam")

    monkeypatch.setattr(ggg_docs_watch, "safe_check", boom)
    monkeypatch.setattr(ggg_docs_watch, "loop_check", boom)
    monkeypatch.setattr(ggg_docs_watch, "run", boom)
    monkeypatch.setattr(ggg_docs_watch, "cache_dir", boom)
    monkeypatch.setattr(tc_drift, "loop_check", boom)
    monkeypatch.setattr(tc_drift, "check", boom)
    monkeypatch.setattr(tc_drift, "launch_trial", boom)

    def fetch(url, etag=None):
        raise AssertionError(f"frame fetch used for {url}")

    root = _root(tmp_path)
    # no seam, not live: nothing is read or started, scratch roots stay hermetic
    for ctx in ({}, {"root": root}, {"live": False, "root": root}):
        assert ggg_docs.check({}, NOW, fetch, dict(ctx)) == []
        assert pob_release.check({}, NOW, fetch, dict(ctx)) == []

    # seams given: they are what runs, with the tick's root and clock
    ctx = _ctx(root, tmp_path)
    assert ggg_docs.check({}, NOW, fetch, ctx) == []
    assert pob_release.check({}, NOW, fetch, ctx) == []
    assert ctx["docs_watch"].calls == [(root, NOW, False)]
    assert ctx["drift"].calls == [(root, NOW, False)]

    # live with no seam: the default is the settled read itself
    docs, drift = Seam(), Seam()
    monkeypatch.setattr(ggg_docs_watch, "safe_check", docs)
    monkeypatch.setattr(tc_drift, "loop_check", drift)
    live = {"live": True, "root": root, "docs_cache": tmp_path / "docs_cache"}
    ggg_docs.check({}, NOW, fetch, dict(live))
    pob_release.check({}, NOW, fetch, dict(live))
    assert docs.calls == [(root, NOW, False)] and drift.calls == [(root, NOW, False)]

    # through the frame: the transport is never touched
    transport = Transport()
    uw.run_due(root, NOW, fetch=transport, ctx=_ctx(root, tmp_path))
    assert transport.calls == []
    assert ggg_docs.SOURCE["purpose"] == ggg_docs_watch.UA_PURPOSE
    assert pob_release.SOURCE["purpose"] == tc_drift.UA_PURPOSE


@pytest.mark.parametrize("tag,vtag", [("v0.24.0", "V0-24-0"), ("v1.10.12", "V1-10-12")])
def test_vtag_matches_the_template_pattern(tag, vtag):
    assert pob_release.vtag(tag) == vtag
    pattern = _table()["pobrelease"]["tokens"]["VTAG"]
    assert re.fullmatch(pattern, vtag)
