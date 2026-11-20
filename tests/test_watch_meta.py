"""LOOP-WATCH-META (W4, W5 of docs/plan/06; AUTO-05, F-030; decision 0069):
the repoe-fork and GGG passive tree export watch sources. Hermetic: the two
source files are copied into a tmp folder and run through the
tools/upstream_watch.py frame with a fake transport; every state file lives
under tmp_path. No socket is ever opened."""

import datetime as dt
import json
import shutil
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import loop_base  # noqa: E402
import upstream_watch as uw  # noqa: E402
import watch_gate  # noqa: E402
import webfetch as dive_fetch  # noqa: E402

from server.al import NAME  # noqa: E402

SRC_DIR = ROOT / "tools" / "watch_sources"
STEMS = ("repoe_fork", "ggg_tree")
NOW = dt.datetime(2026, 11, 20, 12, 0).timestamp()
DAY = 24 * 3600.0

RF_COMMITS = "https://api.github.com/repos/repoe-fork/poe2/commits"
GT_HEAD = "https://api.github.com/repos/grindinggear/poe2-skilltree-export/commits/main"
GT_TAGS = "https://api.github.com/repos/grindinggear/poe2-skilltree-export/tags"


def _sha(n):
    return f"{n:040x}"


def _commit(n, title, date="2026-11-18T05:00:00Z"):
    return {"sha": _sha(n), "commit": {"message": title + "\n\nbody line",
                                       "committer": {"date": date}}}


class Upstream:
    """A fake webfetch transport answering the three metadata URLs."""

    def __init__(self):
        self.calls = []
        self.rf = [_commit(2, "Version 0.5.5.10"), _commit(1, "Export 0.5.5.9")]
        self.head = _commit(9, "0.5.5")
        self.tags = [{"name": "0.4.0", "commit": {"sha": _sha(3)}},
                     {"name": "0.5.2", "commit": {"sha": _sha(4)}}]

    def __call__(self, method, url, headers, body=None):
        self.calls.append((method, url, dict(headers)))
        doc = {RF_COMMITS: self.rf, GT_HEAD: self.head, GT_TAGS: self.tags}.get(url)
        if doc is None:
            return 404, {}, b"{}"
        return 200, {"ETag": '"e1"'}, json.dumps(doc).encode("utf-8")


def _root(tmp_path, web_data=True):
    root = tmp_path / "root"
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "local.json").write_text(
        json.dumps({"web_data": web_data}), encoding="utf-8")
    return root


def _sources(tmp_path, stems=STEMS):
    d = tmp_path / "sources"
    d.mkdir(exist_ok=True)
    for stem in stems:
        shutil.copyfile(SRC_DIR / f"{stem}.py", d / f"{stem}.py")
    return d


def _run(root, d, t, now, stems=STEMS):
    """Run the frame until every listed source ran once at `now` (one
    network source per tick, so one tick per source)."""
    lines = []
    for _ in range(len(stems)):
        lines += uw.run_due(root, now, fetch=t, directory=d, ctx={"root": root})
    return lines


def _data(root, name):
    return uw.load_state(root)["sources"][name]["data"]


def _dive(root):
    path = root / uw.DIVE_REL
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def test_new_version_is_recorded_once(tmp_path):
    root, d, t = _root(tmp_path), _sources(tmp_path), Upstream()
    lines = _run(root, d, t, NOW)
    assert not any("failed" in line for line in lines), lines
    rf = _data(root, "repoe-fork")
    assert rf["version"] == "0.5.5.10" and rf["live_version"] == "0.5.5.10"
    assert rf["title"] == "Version 0.5.5.10" and rf["preview"] is False
    assert rf["seen_at"] == loop_base.iso(NOW)
    gt = _data(root, "ggg-tree")
    assert gt["version"] == "0.5.5" and gt["live_version"] == "0.5.5"
    assert gt["preview"] is False and gt["sha"] == _sha(9)
    first = {"rf": dict(rf), "gt": dict(gt)}

    _run(root, d, t, NOW + DAY + 60)                     # same upstream, a day on
    assert _data(root, "repoe-fork")["seen_at"] == first["rf"]["seen_at"]
    assert _data(root, "repoe-fork")["live_seen_at"] == first["rf"]["live_seen_at"]
    assert _data(root, "ggg-tree")["seen_at"] == first["gt"]["seen_at"]
    assert uw.pending(root) == []                        # no row template, no finding
    assert _dive(root) is None                           # first sighting is no change

    t.rf.insert(0, _commit(5, "Version 0.5.5.11"))
    _run(root, d, t, NOW + 2 * DAY + 120)
    rf = _data(root, "repoe-fork")
    assert rf["version"] == "0.5.5.11"
    assert rf["seen_at"] == loop_base.iso(NOW + 2 * DAY + 120)
    assert _dive(root) is None                           # fourth part only


def test_preview_title_is_noted_and_never_live(tmp_path):
    root, d, t = _root(tmp_path), _sources(tmp_path), Upstream()
    _run(root, d, t, NOW)
    t.head = _commit(10, "1.0.0 Preview")
    t.rf.insert(0, _commit(6, "Export 1.0.0.1 preview"))
    lines = _run(root, d, t, NOW + DAY + 60)
    assert not any("failed" in line for line in lines), lines
    gt = _data(root, "ggg-tree")
    assert gt["preview"] is True and gt["title"] == "1.0.0 Preview"
    assert gt["version"] == "1.0.0"
    assert gt["live_version"] == "0.5.5"                 # never live
    rf = _data(root, "repoe-fork")
    assert rf["preview"] is True and rf["live_version"] == "0.5.5.10"
    assert _dive(root) is None                           # a preview asks no dive

    t.head = _commit(11, "1.0.0 Preview 2")              # a second preview
    _run(root, d, t, NOW + 2 * DAY + 120)
    assert _data(root, "ggg-tree")["live_version"] == "0.5.5"
    assert _dive(root) is None


def test_version_change_writes_one_dive_request(tmp_path):
    root, d, t = _root(tmp_path), _sources(tmp_path), Upstream()
    _run(root, d, t, NOW)
    t.rf.insert(0, _commit(7, "Version 1.0.0.1"))
    _run(root, d, t, NOW + DAY + 60)
    req = _dive(root)
    assert req is not None
    assert "repoe-fork" in req["topic"] and "0.5.5.10 -> 1.0.0.1" in req["topic"]
    assert all(dive_fetch.allowed(u)[0] for u in req["urls"])
    assert _data(root, "repoe-fork")["dive_at"] == loop_base.iso(NOW + DAY + 60)

    (root / uw.DIVE_REL).unlink()
    _run(root, d, t, NOW + 2 * DAY + 120)                # same version again
    assert _dive(root) is None                           # exactly one request

    t.tags.append({"name": "1.0.0", "commit": {"sha": _sha(12)}})  # tree: a 1.0 tag
    _run(root, d, t, NOW + 3 * DAY + 180)
    req = _dive(root)
    assert req is not None and "tree" in req["topic"] and "0.5.5 -> 1.0.0" in req["topic"]
    assert all(dive_fetch.allowed(u)[0] for u in req["urls"])
    assert _data(root, "ggg-tree")["live_version"] == "1.0.0"


def test_window_2026_12_05_to_12_24_uses_the_12_h_cadence(tmp_path):
    srcs = {s["name"]: s for s in uw.discover(_sources(tmp_path))}
    assert set(srcs) == {"repoe-fork", "ggg-tree"}

    def at(y, m, day, h=12):
        return dt.datetime(y, m, day, h, 0).timestamp()

    for src in srcs.values():
        assert src["home"] == "loop" and uw.is_network(src)
        assert uw.cadence_at(src, at(2026, 12, 4)) == DAY
        assert uw.cadence_at(src, at(2026, 12, 5, 0)) == DAY / 2
        assert uw.cadence_at(src, at(2026, 12, 15)) == DAY / 2
        assert uw.cadence_at(src, at(2026, 12, 24, 23)) == DAY / 2
        assert uw.cadence_at(src, at(2026, 12, 25, 0)) == DAY
        # 13 h after the last run: due inside the window, not before it.
        entry = {"last_run": loop_base.iso(at(2026, 12, 10) - 13 * 3600)}
        assert uw._due(src, entry, at(2026, 12, 10))
        entry = {"last_run": loop_base.iso(at(2026, 11, 30) - 13 * 3600)}
        assert not uw._due(src, entry, at(2026, 11, 30))


def test_no_data_file_url_is_requested(tmp_path):
    root, d, t = _root(tmp_path), _sources(tmp_path), Upstream()
    for i in range(4):
        t.rf.insert(0, _commit(20 + i, f"Version 0.5.{6 + i}.1"))
        t.head = _commit(30 + i, f"0.5.{6 + i} Preview" if i % 2 else f"0.5.{6 + i}")
        _run(root, d, t, NOW + i * DAY + i)
    srcs = {s["name"]: s for s in uw.discover(d)}
    assert t.calls, "the sources made no request"
    assert {u for _m, u, _h in t.calls} == {RF_COMMITS, GT_HEAD, GT_TAGS}
    for src in srcs.values():
        assert src["urls"] == [] and src["hosts"] == ["api.github.com"]
    for method, url, headers in t.calls:
        parts = urllib.parse.urlsplit(url)
        assert method == "GET" and parts.hostname == "api.github.com"
        assert watch_gate._github_metadata(parts)
        for src in srcs.values():
            watch_gate.check_url(src, url)               # raises on a refused URL
        low = url.lower()
        assert not any(w in low for w in ("raw", "data.json", "github.io", "contents",
                                          "archive", "pathofexile"))
        assert NAME in headers.get("User-Agent", "")
        assert not any(k.lower() == "cookie" for k in headers)
    for name in srcs:                                    # every run ended well
        assert uw.load_state(root)["sources"][name]["fails"] == 0


def test_web_data_off_makes_zero_requests(tmp_path):
    d, t = _sources(tmp_path), Upstream()
    root = _root(tmp_path, web_data=False)
    lines = []
    for i in range(4):
        lines += uw.run_due(root, NOW + i * DAY, fetch=t, directory=d, ctx={"root": root})
    (root / "config" / "local.json").unlink()            # no config reads as off too
    lines += uw.run_due(root, NOW + 5 * DAY, fetch=t, directory=d, ctx={"root": root})
    assert t.calls == []
    recs = uw.load_state(root)["sources"]
    for name in ("repoe-fork", "ggg-tree"):
        assert recs[name]["idle"] == uw.IDLE_OFF
        assert recs[name]["last_run"] is None and recs[name]["data"] == {}
    assert _dive(root) is None
    assert any(uw.IDLE_OFF in line for line in lines)
