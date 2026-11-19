"""MATH-SKILL-SPLIT (theorycraft/skillsplit.py) and the calc outputs cache
(theorycraft/pobout.py).

The build XML below is real-shaped: PoB's Build element with PlayerStat
entries and one FullDPSSkill per contributing skill, the attributes PoB's
Build.lua save loop writes (research 0031 section 2); the values are
invented. The live leg reads the public reference build from the sidecar
cache when it is there.
"""

import math

import pytest

from server.al.theorycraft import calcwire, model, pobout, skillsplit
from tc_live_util import LIVE_CALC


def _xml(skills="", stats=""):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<PathOfBuilding2>\n'
            '<Build level="90" className="Monk" ascendClassName="Invoker" '
            'targetVersion="0_1" mainSocketGroup="1">\n'
            + stats + skills +
            '</Build>\n<Skills></Skills>\n<Items></Items>\n</PathOfBuilding2>\n')


def _ps(stat, value):
    return f'<PlayerStat stat="{stat}" value="{value}"/>\n'


def _skill(name, value, part="", source="", count=None):
    extra = f' count="{count}"' if count is not None else ""
    return (f'<FullDPSSkill stat="{name}" value="{value}" skillPart="{part}" '
            f'source="{source}"{extra}/>\n')


def _build(skills="", stats=""):
    return model.parse(_xml(skills, stats))


def test_one_skill_has_full_share():
    doc = skillsplit.split(_build(_skill("Ice Strike", "12345.6")))
    assert doc["source"] == "PoB"
    assert [s["name"] for s in doc["skills"]] == ["Ice Strike"]
    assert doc["skills"][0]["dps"] == 12345.6
    assert doc["skills"][0]["share"] == 1.0
    assert doc["total"] == 12345.6


def test_several_skills_sorted_with_count_and_share():
    doc = skillsplit.split(_build(
        _skill("Frost Wall", "1000", source="Skill:FrostWall")
        + _skill("2x Ice Strike", "3000", part="Third Strike")))
    names = [s["name"] for s in doc["skills"]]
    assert names == ["Ice Strike", "Frost Wall"]
    top = doc["skills"][0]
    assert top["count"] == 2 and top["part"] == "Third Strike"
    assert doc["skills"][1]["count"] is None and doc["skills"][1]["source"] == "Skill:FrostWall"
    assert top["share"] == pytest.approx(0.75)
    assert doc["total"] == 4000


def test_no_skills_gives_empty_split():
    doc = skillsplit.split(_build(stats=_ps("Life", 1000)))
    assert doc["skills"] == [] and doc["total"] is None and doc["ailments"] == []


def test_no_build():
    doc = skillsplit.split(None)
    assert doc["skills"] == [] and doc["ailments"] == []


@pytest.mark.parametrize("bad", ["nan", "inf", "-inf", "x", "", "0", "-5"])
def test_non_finite_or_non_positive_value_dropped(bad):
    doc = skillsplit.split(_build(_skill("Ice Strike", "500") + _skill("Bad", bad)))
    assert [s["name"] for s in doc["skills"]] == ["Ice Strike"]
    assert doc["skills"][0]["share"] == 1.0


def test_nameless_skill_dropped_and_odd_count_text_kept_as_name():
    doc = skillsplit.split(_build(_skill("", "100") + _skill("0x Spark", "50")
                                  + _skill("1.5x Arc", "60") + _skill("Best Ignite DPS", "5",
                                                                     source="Arc")))
    assert [(s["name"], s["count"]) for s in doc["skills"]] == [
        ("Arc", 1.5), ("0x Spark", None), ("Best Ignite DPS", None)]
    assert doc["skills"][2]["source"] == "Arc"


def test_ailments_from_playerstat_nonzero_only():
    doc = skillsplit.split(_build(stats=_ps("BleedDPS", "0") + _ps("IgniteDPS", "812.5")
                                  + _ps("PoisonDPS", "nan") + _ps("TotalDotDPS", "812.5")))
    assert [(a["id"], a["dps"]) for a in doc["ailments"]] == [
        ("IgniteDPS", 812.5), ("TotalDotDPS", 812.5)]
    assert doc["ailments"][0]["label"] == "Ignite"
    assert doc["from_calc"] is False


def test_calc_outputs_win_over_playerstat():
    b = _build(stats=_ps("IgniteDPS", "100"))
    doc = skillsplit.split(b, {"IgniteDPS": 250.0, "PoisonDPS": float("inf")})
    assert [(a["id"], a["dps"]) for a in doc["ailments"]] == [("IgniteDPS", 250.0)]
    assert doc["from_calc"] is True


def test_malformed_xml_gives_no_skills():
    assert skillsplit.skills("<not xml") == []
    assert skillsplit.skills(None) == []


def test_api_build_carries_skill_split(tmp_path):
    from server.al.theorycraft.store import BuildStore
    store = BuildStore(tmp_path / "last.txt")
    store.build = _build(_skill("Ice Strike", "900"))
    snap = store.snapshot()
    assert snap["skill_split"]["skills"][0]["name"] == "Ice Strike"
    store.build = None
    assert store.snapshot()["skill_split"]["skills"] == []


# ---- pobout: calc outputs for the build view ----------------------------

class _Calc:
    def __init__(self, table=None, fail=False):
        self.table = table if table is not None else {"IgniteDPS": 5.0}
        self.fail = fail
        self.calls = []

    def __call__(self, build, swaps):
        return {"dps": 1.0, "ehp": 1.0}

    def raw(self, build, keys):
        self.calls.append(tuple(keys))
        if self.fail:
            raise RuntimeError("bridge down")
        return self.table


def test_outputs_cache_off_is_none():
    cache = pobout.OutputsCache(lambda: None, ["Life"], sync=True)
    assert cache.get(_build()) is None
    assert cache.get(None) is None


def test_outputs_cache_calc_without_raw_is_none():
    cache = pobout.OutputsCache(lambda: (lambda b, s: {}), ["Life"], sync=True)
    assert cache.get(_build()) is None


def test_outputs_cache_fetches_once_per_build_and_cleans():
    calc = _Calc({"Life": 10, "Bad": float("nan"), "PreciseTechnique": True, "Name": "x"})
    ready = []
    cache = pobout.OutputsCache(lambda: calc, ["Life"], on_ready=lambda: ready.append(1),
                                sync=True)
    b = _build()
    assert cache.get(b) == {"Life": 10, "PreciseTechnique": True}
    assert cache.get(b) == {"Life": 10, "PreciseTechnique": True}
    assert len(calc.calls) == 1 and calc.calls[0] == ("Life",) and ready == [1]


def test_outputs_cache_hides_table_once_calc_turned_off():
    on = [True]
    calc = _Calc()
    cache = pobout.OutputsCache(lambda: calc if on[0] else None, ["IgniteDPS"], sync=True)
    b = _build()
    assert cache.get(b) == {"IgniteDPS": 5.0}
    on[0] = False
    assert cache.get(b) is None


def test_outputs_cache_failure_retries_later():
    now = [0.0]
    calc = _Calc(fail=True)
    cache = pobout.OutputsCache(lambda: calc, ["Life"], clock=lambda: now[0], sync=True)
    b = _build()
    assert cache.get(b) is None and cache.get(b) is None
    assert len(calc.calls) == 1
    now[0] = pobout.RETRY_S + 1
    calc.fail = False
    assert cache.get(b) == {"IgniteDPS": 5.0}


def test_outputs_cache_background_thread_calls_on_ready():
    import threading
    done = threading.Event()
    calc = _Calc()
    cache = pobout.OutputsCache(lambda: calc, ["IgniteDPS"], on_ready=done.set)
    b = _build()
    assert cache.get(b) is None
    assert done.wait(5)
    assert cache.get(b) == {"IgniteDPS": 5.0}


class _Bridge:
    def __init__(self):
        self.loaded = []
        self.asked = None

    def load_build(self, xml):
        self.loaded.append(xml)

    def outputs(self, keys=None):
        self.asked = keys
        return {"IgniteDPS": 7.0, "FullDPS": 1.0, "TotalEHP": 2.0}


def test_calcwire_raw_loads_build_once_and_asks_keys():
    br = _Bridge()
    calc = calcwire.make_calc(lambda: br)
    b = _build()
    assert calc.raw(b, ("IgniteDPS",)) == {"IgniteDPS": 7.0, "FullDPS": 1.0, "TotalEHP": 2.0}
    calc.raw(b, ("IgniteDPS",))
    assert len(br.loaded) == 1 and br.asked == ["IgniteDPS"]


def test_core_build_view_uses_calc_outputs(tmp_path):
    from server.al.core import Core
    core = Core(runtime=tmp_path, tail=False)
    try:
        calc = _Calc({"IgniteDPS": 42.0, "StunThreshold": 900.0})
        core.tc_calc = calc
        core.pob_outputs._sync = True
        core.builds.build = _build(_skill("Ice Strike", "10"))
        snap = core.builds.snapshot()
        assert snap["skill_split"]["ailments"][0]["dps"] == 42.0
        assert any(r["id"] == "StunThreshold" for r in snap["health"]["defence"])
        assert core.state.build_info.get("calc_rev") == 1
        assert set(calc.calls[0]) >= {"IgniteDPS", "StunThreshold", "PreciseTechnique"}
    finally:
        core.close()


# ---- live leg: the public reference build (sidecar cache) ---------------

def test_live_reference_build_skill_split():
    from tc_live_util import reference
    ref = reference()
    if ref is None:
        pytest.skip("reference build absent (sidecar Cache\\tc_bridge)")
    b = model.parse(ref[1])
    doc = skillsplit.split(b)
    assert doc["skills"], "PoB saves FullDPSSkill in every build"
    assert all(math.isfinite(s["dps"]) and s["dps"] > 0 for s in doc["skills"])
    assert sum(s["share"] for s in doc["skills"]) == pytest.approx(1.0)
    # PoB's own FullDPS is the sum of its FullDPSSkill entries
    assert doc["total"] == pytest.approx(b.stats["FullDPS"], rel=1e-9)
    assert [s["name"] for s in doc["skills"]][:2] == ["Ice Shot", "Snipe"]
    assert [a["id"] for a in doc["ailments"]] == ["IgniteDPS", "TotalDotDPS"]


@LIVE_CALC
def test_live_calc_outputs_for_build_view():
    from tc_live_util import reference
    from server.al.theorycraft import bridge, health
    ref = reference()
    if ref is None or not bridge.available():
        pytest.skip("calc component or reference build absent")
    calc = calcwire.make_calc(bridge.shared)
    try:
        b = model.parse(ref[1])
        out = pobout.clean(calc.raw(b, health.CALC_KEYS + skillsplit.KEYS))
        doc = health.health(b, out)
        ids = [r["id"] for r in doc["defence"]]
        # CalcDefence values the saved build lacks, from the live calc
        assert "StunThreshold" in ids and "IgniteAvoidChance" in ids
        assert doc["calc_on"] is True
        assert out.get("LifeUnreserved") == pytest.approx(b.stats["LifeUnreserved"], rel=1e-6)
    finally:
        bridge.shutdown_shared()
