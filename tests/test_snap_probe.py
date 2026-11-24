"""DATA-SNAP-PROBE (F-143): a fetched snapshot file is probed before it
replaces the cached one (server/al/theorycraft/snapprobe.py, called by
snapshot.run).

No real network request: every fetch is a stub. Cache, runtime and log
folders are tmp_path; the core is a test core (tmp runtime, no tailer).
"""

import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from server.al import diag, diag_data
from server.al.core import Core
from server.al.theorycraft import snapprobe, snapshot, weights

ROOT = Path(__file__).resolve().parents[1]
NOW = 1_800_000_000
AREAS_URL = snapshot.SOURCES["world_areas"]
STATS_URL = snapshot.SOURCES["stat_translations"]
LIFE_ID = "explicit.stat_3299347043"


@pytest.fixture(autouse=True)
def _fresh():
    diag_data.reset()
    snapprobe._cache.clear()
    yield
    diag_data.reset()
    snapprobe._cache.clear()


def _areas(n=120, drop=()):
    out = {}
    for i in range(n):
        e = {"name": f"Zone {i}", "area_level": 1 + i % 60, "is_town": i == 0,
             "has_waypoint": i % 2 == 0, "connections": [], "id": f"G1_{i}"}
        for k in drop:
            e.pop(k, None)
        out[f"G1_{i}"] = e
    return out


def _body(doc):
    return json.dumps(doc).encode("ascii")


class Fake:
    def __init__(self, bodies):
        self.bodies = dict(bodies)

    def __call__(self, url, headers):
        return 200, {}, self.bodies[url]


def _run(tmp_path, fake, **kw):
    return snapshot.run(tmp_path / "cache", fetch=fake, sources={"world_areas": AREAS_URL},
                        probes=snapprobe.PROBES, runtime=tmp_path / "rt",
                        log_dir=tmp_path / "logs", **kw)


def _report(tmp_path):
    return json.loads(snapprobe.report_path(tmp_path / "rt").read_text(encoding="ascii"))


def test_wrong_shape_body_leaves_the_cache_untouched_and_the_row_names_the_source(tmp_path):
    good = _body(_areas())
    fake = Fake({AREAS_URL: good})
    assert _run(tmp_path, fake, now=NOW) == {"world_areas": "fetched"}
    cache = tmp_path / "cache"
    manifest = (cache / "manifest.json").read_bytes()
    for bad, why in ((b"[]", "top level is not a JSON object"),
                     (_body(_areas(n=5)), "only 5 entries, at least 100 expected"),
                     (_body(_areas(drop=("area_level",))), "no entry has area_level")):
        fake.bodies[AREAS_URL] = bad
        out = _run(tmp_path, fake, force=True, now=NOW + 10)
        assert out == {"world_areas": "error: probe: " + why}
        assert (cache / "world_areas.json").read_bytes() == good
        assert (cache / "manifest.json").read_bytes() == manifest
        assert not (cache / "world_areas.prev.json").exists()
    entry = _report(tmp_path)["sources"][0]
    assert entry["source"] == "world_areas" and entry["verdict"] == "fail"
    assert entry["missing_keys"] == ["area_level"] and entry["lost"] == ["area_level"]
    # Checks: one failing row naming the source, through the DATA-DIAG-SEAM
    core = Core(runtime=tmp_path / "rt", tail=False)
    try:
        f = core.diag_facts(NOW)
        v = diag.view(f, "1.0.0", now=NOW)
    finally:
        core.close()
    rows = [r for r in v["checks"] if r["id"].startswith(snapprobe.ROW_PREFIX)]
    assert [r["id"] for r in rows] == ["snap_probe_world_areas"]
    row = rows[0]
    assert row["status"] == "fail" and row["label"] == "Game data" and row["fix"]
    assert "zone list" in row["detail"] and "world_areas" in row["detail"]
    assert "kept the copy it had" in row["detail"]
    # a later good body clears the row
    fake.bodies[AREAS_URL] = _body(_areas(n=121))
    assert _run(tmp_path, fake, force=True, now=NOW + 20) == {"world_areas": "fetched"}
    f = snapprobe.diag_facts(SimpleNamespace(runtime=tmp_path / "rt"))
    assert snapprobe.diag_rows(f, NOW) == []


def test_drift_report_names_a_lost_field_and_a_count_change_over_20_percent(tmp_path):
    old = snapprobe.stats("world_areas", _areas(n=200))
    new = snapprobe.stats("world_areas", _areas(n=150, drop=("id",)))
    d = snapprobe.drift(old, new)
    assert d["lost"] == ["id"] and d["count"] == [200, 150] and d["changed"]
    assert snapprobe.drift(old, snapprobe.stats("world_areas", _areas(n=180)))["count"] is None
    assert snapprobe.drift(None, new) == {"lost": [], "count": None, "fields": [],
                                          "weights": None, "changed": False}
    # through a run: the drift line names the lost field and the count change
    fake = Fake({AREAS_URL: _body(_areas(n=200))})
    _run(tmp_path, fake, now=NOW)
    fake.bodies[AREAS_URL] = _body(_areas(n=150, drop=("id",)))
    assert _run(tmp_path, fake, force=True, now=NOW + 5) == {"world_areas": "fetched"}
    log = (tmp_path / "logs" / snapprobe.LOG_NAME).read_text(encoding="ascii")
    last = log.strip().splitlines()[-1]
    assert "world_areas | pass" in last and "count 200 -> 150" in last
    assert "lost: id" in last
    assert (tmp_path / "cache" / "world_areas.prev.json").is_file()
    # a lost field no reader uses is logged but not a reader loss
    assert _report(tmp_path)["sources"][0]["lost"] == []


def test_probe_json_holds_source_verdict_missing_count_and_time(tmp_path):
    fake = Fake({AREAS_URL: _body(_areas()), STATS_URL: b"{}"})
    out = snapshot.run(tmp_path / "cache", fetch=fake,
                       sources={"world_areas": AREAS_URL, "stat_translations": STATS_URL},
                       probes=snapprobe.PROBES, runtime=tmp_path / "rt",
                       log_dir=tmp_path / "logs", now=NOW)
    assert out["world_areas"] == "fetched"
    assert out["stat_translations"] == "error: probe: top level is not a JSON list"
    doc = _report(tmp_path)
    assert doc["schema"] == 1 and doc["updated"] == snapshot._utc(NOW)
    by = {e["source"]: e for e in doc["sources"]}
    assert [e["source"] for e in doc["sources"]] == ["stat_translations", "world_areas"]
    assert by["world_areas"]["verdict"] == "pass" and by["world_areas"]["missing"] == 0
    assert by["world_areas"]["time"] == snapshot._utc(NOW)
    assert by["world_areas"]["count"] == 120
    assert by["stat_translations"]["verdict"] == "fail"
    assert by["stat_translations"]["missing"] == 1
    for e in doc["sources"]:
        assert {"source", "verdict", "missing", "time"} <= set(e)
    # a later run probing one source keeps the other's entry
    fake.bodies[AREAS_URL] = b"[]"
    _run(tmp_path, fake, force=True, now=NOW + 60)
    by = {e["source"]: e for e in _report(tmp_path)["sources"]}
    assert by["world_areas"]["verdict"] == "fail"
    assert by["stat_translations"]["time"] == snapshot._utc(NOW)
    # nothing probed: no report and no log are written
    snapshot.run(tmp_path / "c2", fetch=Fake({AREAS_URL: b"[]"}),
                 sources={"world_areas": AREAS_URL}, runtime=tmp_path / "rt2",
                 log_dir=tmp_path / "logs2", now=NOW)
    assert not (tmp_path / "rt2").exists() and not (tmp_path / "logs2").exists()


def test_stat_translations_probe_counts_default_weight_coverage():
    def entry(text=None):
        rows = ([{"id": LIFE_ID, "text": text, "type": "explicit"}] if text else None)
        return {"English": [], "ids": [], "trade_stats": rows}

    doc = [entry() for _ in range(2500)] + [entry("+# to maximum Life")]
    r = snapprobe.probe("stat_translations", doc)
    assert r["verdict"] == "pass" and r["count"] == 2501
    assert r["weights"] == {"keys": len(weights.DEFAULT_WEIGHTS), "mapped": 1}
    s = snapprobe.stats("stat_translations", doc)
    assert s["weights"]["mapped"] == 1 and s["fields"]["trade_stats"] == 2501
    doc2 = doc + [{"English": [], "ids": [], "trade_stats": [
        {"id": "explicit.stat_1", "text": "+# to maximum Energy Shield", "type": "explicit"}]}]
    d = snapprobe.drift(s, snapprobe.stats("stat_translations", doc2))
    assert d["weights"] == [1, 2] and d["changed"]
    line = snapprobe.drift_line("stat_translations", r, d, NOW)
    assert "weight keys mapped 1 -> 2" in line
    # a list with no trade_stats field at all fails the probe
    bare = [{"English": [], "ids": []} for _ in range(2500)]
    r = snapprobe.probe("stat_translations", bare)
    assert r["verdict"] == "fail" and r["missing"] == ["trade_stats"]
    assert r["weights"]["mapped"] == 0


def test_snapprobe_never_imports_snapshot():
    src = (ROOT / "server" / "al" / "theorycraft" / "snapprobe.py").read_text(encoding="ascii")
    tree = ast.parse(src)
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names += [node.module or ""] + [a.name for a in node.names]
    for bad in ("snapshot", "urllib", "http", "socket", "ssl", "webfetch", "ninja"):
        assert not any(bad in n.split(".") for n in names), bad
    # the default tables of a run probe every real source by name
    assert set(snapshot.SOURCES) <= set(snapprobe.PROBES)
    assert snapprobe.probe("not_a_source", {}) is None


# --- DATA-GEMS-SNAP: the gems probe ---------------------------------------

GEMS_URL = snapshot.SOURCES["gems"]


def _gems(n=200, named=True, nest=False):
    out = {}
    for i in range(n):
        if not named:
            e = {"tags": ["x"], "requirements": {"level": 1}}
        elif nest:
            e = {"base_item": {"display_name": f"Gem {i}"},
                 "per_level": {"1": {"requirements": {"level": 1 + i % 60}}}}
        else:
            e = {"display_name": f"Gem {i}", "requirements": {"level": 1 + i % 60}}
        out[f"Metadata/Items/Gems/SkillGem{i}"] = e
    return out


def test_gems_probe_passes_both_name_shapes():
    for nest in (False, True):
        res = snapprobe.probe("gems", _gems(nest=nest))
        assert res["verdict"] == snapprobe.PASS, res
        assert res["names"] == 200 and res["count"] == 200


def test_gems_probe_fails_without_readable_names_or_entries():
    res = snapprobe.probe("gems", _gems(named=False))
    assert res["verdict"] == snapprobe.FAIL and "gem names" in res["reason"]
    res = snapprobe.probe("gems", _gems(n=20))
    assert res["verdict"] == snapprobe.FAIL and "entries" in res["reason"]
    assert snapprobe.probe("gems", [])["verdict"] == snapprobe.FAIL


def test_a_bad_gems_body_keeps_the_cached_file(tmp_path):
    def run(fake, now):
        return snapshot.run(tmp_path / "cache", fetch=fake, sources={"gems": GEMS_URL},
                            probes=snapprobe.PROBES, runtime=tmp_path / "rt",
                            log_dir=tmp_path / "logs", force=True, now=now)
    good = _body(_gems())
    assert run(Fake({GEMS_URL: good}), NOW) == {"gems": "fetched"}
    out = run(Fake({GEMS_URL: _body(_gems(named=False))}), NOW + 5)
    assert out["gems"].startswith("error: probe: only 0 gem names")
    assert (tmp_path / "cache" / "gems.json").read_bytes() == good
    doc = json.loads(snapprobe.report_path(tmp_path / "rt").read_text(encoding="ascii"))
    entry = {e["source"]: e for e in doc["sources"]}["gems"]
    assert entry["verdict"] == "fail"
    rows = snapprobe.diag_rows({snapprobe.FACT: doc["sources"]}, NOW)
    assert [r["id"] for r in rows] == ["snap_probe_gems"]
    assert "skill gem list" in rows[0]["detail"]
