"""AUTO-10 (NINJA-WATCH, W6 and the W7 flag bridge of docs/plan/06): the
'ninja-docs' and 'ninja-shape' watcher sources. Every read is an injected
transport over fixture pages in tmp_path: no request is ever made."""

import datetime as _dt
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import upstream_watch as uw  # noqa: E402
import watch_rows  # noqa: E402
from watch_sources import ninja_docs, ninja_shape  # noqa: E402

HOUR = 3600
DAY = 24 * HOUR
NOW = _dt.datetime(2026, 11, 21, 12, 0).timestamp()
TODAY = "2026-11-21"
TYPES = ["Currency", "Fragments", "Abyss", "UncutGems"]
POLICY = "Please set a User-Agent with a contact so we can reach you."


def page(types=TYPES, policy=POLICY, route="GET /poe2/api/economy/exchange/current/overview",
         spaces=" "):
    rows = "".join(f"<tr><td>{t}</td><td>{t.lower()}</td></tr>" for t in types)
    return (
        "<!doctype html><html><head><title>API Reference</title>"
        "<style>body{color:red}</style><script>var x=1;</script></head><body>"
        "<nav><a href='/docs'>Docs</a><a href='/docs/api'>API Reference</a></nav>"
        "<h1>API Reference</h1>"
        f"<p>The{spaces}API is used to run the site.</p>"
        "<h2>Routes</h2>"
        f"<pre>{route}</pre>"
        "<h2>PoE2 exchange types</h2>"
        f"<table><tr><th>Type</th><th>Id</th></tr>{rows}</table>"
        "<h2>Usage</h2>"
        f"<p>{policy}</p>"
        "<footer><p>Copyright poe.ninja</p><p>Footer links change every render</p></footer>"
        "</body></html>").encode("utf-8")


def _root(tmp_path, web_data=True, contact="someone"):
    root = tmp_path / "root"
    (root / "config").mkdir(parents=True, exist_ok=True)
    cfg = {"web_data": web_data}
    if contact is not None:
        cfg["contact"] = contact
    (root / "config" / "local.json").write_text(json.dumps(cfg), encoding="ascii")
    return root


def _ctx(tmp_path, root):
    return {"root": root, "ninja_cache": tmp_path / "cache", "ninja_logs": tmp_path / "logs"}


class Transport:
    """webfetch's transport fetch(method, url, headers, body) for the frame."""

    def __init__(self, body, status=200, headers=None):
        self.body, self.status, self.headers = body, status, headers or {}
        self.calls = []

    def __call__(self, method, url, headers, body=None):
        self.calls.append((method, url, dict(headers)))
        return self.status, dict(self.headers), self.body


def _sources(tmp_path, stems=("ninja_docs",)):
    folder = tmp_path / "sources"
    folder.mkdir(parents=True, exist_ok=True)
    for stem in stems:
        shutil.copyfile(ROOT / "tools" / "watch_sources" / f"{stem}.py", folder / f"{stem}.py")
    return folder


def _pending(root, kind):
    return [f for f in uw.pending(root) if f["kind"] == kind]


def _render(finding):
    table = watch_rows.load(ROOT)
    return watch_rows.render(table, finding["kind"], finding["tokens"], TODAY)


def _two_reads(tmp_path, first, second):
    """A baseline read of `first`, then a read of `second` 25 h later."""
    root = _root(tmp_path)
    ctx = _ctx(tmp_path, root)
    d = _sources(tmp_path)
    t = Transport(first)
    assert uw.run_due(root, NOW - 25 * HOUR, fetch=t, directory=d, ctx=ctx) == []
    assert len(t.calls) == 1
    t.body = second
    lines = uw.run_due(root, NOW, fetch=t, directory=d, ctx=ctx)
    assert len(t.calls) == 2
    return root, ctx, lines


def test_new_poe2_type_writes_a_dated_diff_and_files_ninja_docs(tmp_path):
    root, ctx, lines = _two_reads(tmp_path, page(), page(types=TYPES + ["UniqueRelics"]))
    found = _pending(root, "ninjadocs")
    assert [f["tokens"] for f in found] == [{"topic": "types", "n": "1"}]
    assert _pending(root, "ninjapolicy") == []
    assert any("1 new finding" in ln for ln in lines)
    diff = (tmp_path / "logs" / "diff-20261121.txt").read_text(encoding="utf-8")
    assert "UniqueRelics" in diff and "[types] +" in diff
    row_id, text = _render(found[0])
    assert row_id == "NINJA-DOCS-20261121"
    assert "(types, 1 lines)" in text and "UniqueRelics" not in text
    # The baseline moved on: the same page again files nothing more.
    t = Transport(page(types=TYPES + ["UniqueRelics"]))
    uw.run_due(root, NOW + 25 * HOUR, fetch=t, directory=_sources(tmp_path), ctx=ctx)
    assert len(t.calls) == 1 and len(_pending(root, "ninjadocs")) == 1


def test_policy_line_change_files_ninja_policy(tmp_path):
    root, _ctx_, _lines = _two_reads(
        tmp_path, page(), page(policy="Desktop apps must go through a backend proxy."))
    found = _pending(root, "ninjapolicy")
    assert [f["tokens"] for f in found] == [{"n": "2"}]
    assert _pending(root, "ninjadocs") == []
    row_id, text = _render(found[0])
    assert row_id == "NINJA-POLICY-20261121"
    assert "BLOCKED: session" in text and "proxy" not in text


def test_route_change_files_ninja_docs_routes():
    old = ninja_docs.normalise(page().decode())
    new = ninja_docs.normalise(page(route="GET /poe2/api/economy/v2/overview").decode())
    rows = ninja_docs.changed(old, new)
    assert ninja_docs.counts_of(rows) == {"types": 0, "routes": 2, "policy": 0}


def test_whitespace_only_change_files_nothing(tmp_path):
    root, _ctx_, lines = _two_reads(tmp_path, page(), page(spaces="  \n\t "))
    assert uw.pending(root) == [] and lines == []
    assert not (tmp_path / "logs").exists()


def test_normalise_cuts_from_the_heading_to_the_footer():
    lines = ninja_docs.normalise(page().decode())
    assert lines[0] == "# API Reference"
    assert not any("Copyright" in ln or "Footer" in ln or "var x" in ln for ln in lines)
    assert "Currency | currency" in lines
    try:
        ninja_docs.normalise("<html><body><p>Moved</p></body></html>")
    except uw.SourceError as exc:
        assert exc.cause == "shape"
    else:
        raise AssertionError("a page with no API Reference heading must be a shape error")


def test_no_contact_or_web_data_off_makes_zero_requests(tmp_path):
    for i, (web, contact) in enumerate(((False, "someone"), (True, None),
                                        (True, "  "), (False, None))):
        base = tmp_path / f"case{i}"
        root = _root(base, web_data=web, contact=contact)
        t = Transport(page())
        for k in range(3):
            uw.run_due(root, NOW + k * DAY, fetch=t, directory=_sources(base), ctx=_ctx(base, root))
        assert t.calls == [], (web, contact)
        assert uw.pending(root) == []
    # Without a root, a cache folder or the live flag the source reads nothing.
    assert ninja_docs.check({"data": {}}, NOW, None, {}) == []


def test_429_or_503_stops_the_source(tmp_path):
    for status in (429, 503):
        base = tmp_path / str(status)
        root = _root(base)
        ctx = _ctx(base, root)
        d = _sources(base)
        t = Transport(page(), status=status)
        lines = uw.run_due(root, NOW, fetch=t, directory=d, ctx=ctx)
        assert len(t.calls) == 1
        assert any("rate-limit" in ln for ln in lines)
        assert uw.load_state(root)["sources"]["ninja-docs"]["cause"] == "rate-limit"
        t.status = 200
        for k in range(1, 7):  # every 3 h retry slot of the next 6 days stays silent
            uw.run_due(root, NOW + k * DAY, fetch=t, directory=d, ctx=ctx)
        assert len(t.calls) == 1
        uw.run_due(root, NOW + 8 * DAY, fetch=t, directory=d, ctx=ctx)
        assert len(t.calls) == 2


def test_network_error_retries_after_3_hours_and_a_good_read_waits_24(tmp_path):
    root = _root(tmp_path)
    ctx = _ctx(tmp_path, root)
    d = _sources(tmp_path)
    t = Transport(page(), status=500)
    uw.run_due(root, NOW, fetch=t, directory=d, ctx=ctx)
    uw.run_due(root, NOW + 2 * HOUR, fetch=t, directory=d, ctx=ctx)
    assert len(t.calls) == 1
    t.status = 200
    uw.run_due(root, NOW + 3 * HOUR, fetch=t, directory=d, ctx=ctx)
    assert len(t.calls) == 2
    sent = t.calls[-1][2]
    assert sent["User-Agent"].startswith("AshLight/") and "docs watch" in sent["User-Agent"]
    assert "Cookie" not in sent
    for h in (6, 12, 24):
        uw.run_due(root, NOW + (3 + h) * HOUR - 60, fetch=t, directory=d, ctx=ctx)
    assert len(t.calls) == 2
    uw.run_due(root, NOW + 30 * HOUR, fetch=t, directory=d, ctx=ctx)  # next 3 h slot
    assert len(t.calls) == 3


def test_second_docs_change_inside_7_days_only_joins_the_log(tmp_path):
    root, ctx, _lines = _two_reads(tmp_path, page(), page(types=TYPES + ["UniqueRelics"]))
    d = _sources(tmp_path)
    t = Transport(page(types=TYPES + ["UniqueRelics", "Runes"]))
    uw.run_due(root, NOW + 2 * DAY, fetch=t, directory=d, ctx=ctx)
    assert len(t.calls) == 1 and len(_pending(root, "ninjadocs")) == 1
    log = (tmp_path / "logs" / "diff-20261123.txt").read_text(encoding="utf-8")
    assert "Runes" in log and "joins the ninjadocs row" in log
    t.body = page(types=TYPES + ["UniqueRelics", "Runes", "Talismans"])
    uw.run_due(root, NOW + 8 * DAY, fetch=t, directory=d, ctx=ctx)
    assert len(_pending(root, "ninjadocs")) == 2


def test_source_lists_only_the_docs_url():
    src = uw.normalize(ninja_docs)
    assert src["home"] == "loop" and src["needs_web_data"] is True
    assert src["urls"] == ["https://poe.ninja/docs/api"]
    assert uw.is_network(src)
    shape = uw.normalize(ninja_shape)
    assert shape["local"] and not shape["needs_web_data"]


def _flag(root, doc):
    path = root / "ops" / "runtime" / "ninja" / "SHAPE_DRIFT"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="ascii")
    return path


def test_flag_file_files_one_ninja_shape_row_once(tmp_path):
    root = _root(tmp_path, web_data=False, contact=None)
    d = _sources(tmp_path, ("ninja_shape",))
    ctx = {"root": root}
    assert uw.run_due(root, NOW, directory=d, ctx=ctx) == []  # absent flag: nothing to do
    _flag(root, {"family": "item", "type": "UniqueWeapons",
                 "missing": ["name", "primaryValue", "listingCount"],
                 "first_seen": "2026-11-20T08:00:00-06:00"})
    for k in range(4):
        uw.run_due(root, NOW + k * HOUR, directory=d, ctx=ctx)
        uw.run_due(root, NOW + k * DAY, directory=d, ctx=ctx)
    found = _pending(root, "ninjashape")
    assert [f["tokens"] for f in found] == [{"family": "item", "n": "3", "since": "2026-11-20"}]
    row_id, text = _render(found[0])
    assert row_id == "NINJA-SHAPE-20261121"
    assert "poe.ninja item bodies miss 3 read keys since 2026-11-20" in text
    assert "UniqueWeapons" not in text and "primaryValue" not in text


def test_flag_records_merge_and_bad_flags_are_shape_errors(tmp_path):
    root = _root(tmp_path)
    recs = [{"family": "leagues", "type": "leagues", "missing": ["id"],
             "first_seen": "2026-11-19"},
            {"family": "exchange", "type": "Currency", "missing": ["id", "core"],
             "first_seen": "2026-11-21"},
            {"family": "exchange", "type": "Fragments", "missing": ["core", "lines"],
             "first_seen": "2026-11-18"},
            {"family": "gems", "missing": ["x"], "first_seen": "2026-11-18"}]
    _flag(root, recs)
    st = {"data": {}, "seen": []}
    found = ninja_shape.check(st, NOW, None, {"root": root})
    assert [f["tokens"] for f in found] == [{"family": "exchange", "n": "3",
                                             "since": "2026-11-18"}]
    assert ninja_shape.check({"data": {}}, NOW, None, {}) == []
    path = _flag(root, {"family": "gems"})
    for text in ("not json", json.dumps({"family": "gems"})):
        path.write_text(text, encoding="ascii")
        try:
            ninja_shape.check({"data": {}}, NOW, None, {"root": root})
        except uw.SourceError as exc:
            assert exc.cause == "shape"
        else:
            raise AssertionError("a bad flag must be a shape error")
